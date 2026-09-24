#!/usr/bin/env python3
"""Run one isolated, blinded Codex forward-evaluation trial.

The runner deliberately keeps the Codex JSONL event stream in memory.  Only
the final assistant response and a small, schema-shaped telemetry record are
published, and both are created with private permissions after all preflight
checks and the child process have succeeded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
import time
import selectors
import signal
import shutil
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
HEX64 = re.compile(r"^[a-f0-9]{64}$")
HEX40 = re.compile(r"^[a-f0-9]{40}$")
SEMVER = re.compile(r"(?:^|\s)(\d+\.\d+\.\d+)(?:$|\s)")
MAX_PROMPT_BYTES = 1024 * 1024
MAX_CHILD_OUTPUT_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 1024 * 1024
SUPPORTED_CODEX_VERSION = "0.156.1"
SUPPORTED_NETWORK_POLICY = "codex-read-only-sandbox"
HOST_DEFAULT_MODEL = "host-default"


class TrialError(ValueError):
    """A safe, non-sensitive runner failure."""


def _fail(message: str) -> None:
    print(f"trial failed: {message}", file=sys.stderr)
    raise SystemExit(1)


def _regular(path: Path, *, label: str, mode: int | None = None) -> None:
    if path.is_symlink() or not path.is_file():
        raise TrialError(f"{label} must be a regular file")
    if mode is not None and stat.S_IMODE(path.stat().st_mode) != mode:
        raise TrialError(f"{label} permissions are invalid")


def _directory(path: Path, *, label: str, mode: int | None = None, empty: bool = False) -> None:
    if path.is_symlink() or not path.is_dir():
        raise TrialError(f"{label} must be a regular directory")
    if mode is not None and stat.S_IMODE(path.stat().st_mode) != mode:
        raise TrialError(f"{label} permissions are invalid")
    if empty:
        try:
            if any(path.iterdir()):
                raise TrialError(f"{label} must be empty")
        except OSError as exc:
            raise TrialError(f"{label} cannot be inspected") from exc


def _read_json(path: Path, *, label: str, mode: int = 0o600) -> dict[str, Any]:
    _regular(path, label=label, mode=mode)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise TrialError(f"{label} is invalid") from exc
    if not isinstance(value, dict):
        raise TrialError(f"{label} must be an object")
    return value


def _safe_relative(value: object, *, parent: str, label: str) -> Path:
    if not isinstance(value, str):
        raise TrialError(f"{label} is invalid")
    relative = Path(value)
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or len(relative.parts) != 2
        or relative.parts[0] != parent
        or any(part in {"", "."} for part in relative.parts)
    ):
        raise TrialError(f"{label} is outside its directory")
    return relative


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_trial(run_dir: Path, case_id: str, attempt: int) -> tuple[dict[str, Any], dict[str, Any], Path]:
    _directory(run_dir, label="run directory", mode=0o700)
    manifest = _read_json(run_dir / "manifest.json", label="run manifest")
    if manifest.get("schema_version") != 1:
        raise TrialError("run manifest schema is invalid")
    candidate_sha = manifest.get("candidate_sha256")
    if not isinstance(candidate_sha, str) or not HEX64.fullmatch(candidate_sha):
        raise TrialError("run manifest candidate digest is invalid")
    if not isinstance(case_id, str) or not case_id or not SAFE_ID.fullmatch(case_id):
        raise TrialError("case id is invalid")
    if attempt not in {1, 2, 3}:
        raise TrialError("attempt is invalid")
    trials = manifest.get("trials")
    if not isinstance(trials, list):
        raise TrialError("run manifest trials are invalid")
    matches = [
        trial for trial in trials
        if isinstance(trial, dict) and trial.get("case_id") == case_id and trial.get("attempt") == attempt
    ]
    if len(matches) != 1:
        raise TrialError("requested trial is not uniquely present in manifest")
    trial = matches[0]
    if trial.get("category") is not None and not isinstance(trial.get("category"), str):
        raise TrialError("trial category is invalid")
    prompt_rel = _safe_relative(trial.get("prompt_file"), parent="prompts", label="prompt path")
    response_rel = _safe_relative(trial.get("response_file"), parent="responses", label="response path")
    telemetry_rel = _safe_relative(trial.get("telemetry_file"), parent="telemetry", label="telemetry path")
    prompt = run_dir / prompt_rel
    response = run_dir / response_rel
    telemetry = run_dir / telemetry_rel
    for directory, label in ((prompt.parent, "prompt directory"), (response.parent, "response directory"), (telemetry.parent, "telemetry directory")):
        _directory(directory, label=label, mode=0o700)
    _regular(prompt, label="prompt", mode=0o600)
    if prompt.stat().st_size > MAX_PROMPT_BYTES:
        raise TrialError("prompt is too large")
    expected_prompt_sha = trial.get("prompt_sha256")
    if not isinstance(expected_prompt_sha, str) or not HEX64.fullmatch(expected_prompt_sha):
        raise TrialError("prompt digest is invalid")
    if _sha256(prompt) != expected_prompt_sha:
        raise TrialError("prompt digest does not match manifest")
    for output, label in ((response, "response"), (telemetry, "telemetry")):
        # Path.exists() is false for a broken symlink, so test is_symlink first.
        if output.is_symlink() or output.exists():
            raise TrialError(f"{label} already exists")
    return manifest, trial, prompt


def _reject_evaluator_assets(candidate: Path) -> None:
    _directory(candidate, label="candidate installation")
    # A candidate must not receive the held-out forward-evaluation definitions.
    # Reject symlinks anywhere in the installation so a link cannot smuggle one
    # of those files past the path check.
    for root, dirs, files in os.walk(candidate, topdown=True, followlinks=False):
        root_path = Path(root)
        for name in (*dirs, *files):
            path = root_path / name
            if path.is_symlink():
                raise TrialError("candidate installation contains a symlink")
        try:
            relative = root_path.relative_to(candidate)
        except ValueError as exc:
            raise TrialError("candidate installation path is invalid") from exc
        if relative == Path("evals", "forward"):
            raise TrialError("candidate installation contains held-out evaluator assets")


def _tree_file_hashes(candidate: Path) -> dict[str, str]:
    """Return a complete, symlink-free file fingerprint for a candidate tree."""
    _reject_evaluator_assets(candidate)
    files: dict[str, str] = {}
    for root, dirs, names in os.walk(candidate, topdown=True, followlinks=False):
        root_path = Path(root)
        for name in (*dirs, *names):
            path = root_path / name
            if path.is_symlink():
                raise TrialError("candidate installation contains a symlink")
        for name in names:
            path = root_path / name
            relative = path.relative_to(candidate).as_posix()
            files[relative] = _sha256(path)
    return files


def _set_tree_writeability(root: Path, *, writable: bool) -> None:
    """Add or remove write bits without changing read/execute permissions."""
    paths = [root, *root.rglob("*")]
    for path in sorted(paths, key=lambda value: len(value.parts), reverse=not writable):
        if path.is_symlink():
            raise TrialError("candidate installation contains a symlink")
        current = stat.S_IMODE(path.stat().st_mode)
        mode = current | 0o200 if writable else current & ~0o222
        if mode != current:
            path.chmod(mode)


def _candidate_path(manifest: dict[str, Any], argument: str | None) -> Path | None:
    declared = manifest.get("candidate_install")
    if declared is not None and not isinstance(declared, str):
        raise TrialError("manifest candidate installation is invalid")
    if argument is not None and declared is not None:
        supplied = Path(argument)
        if supplied != Path(declared):
            raise TrialError("candidate installation does not match manifest")
    selected = Path(argument) if argument is not None else (Path(declared) if declared else None)
    if selected is None:
        raise TrialError("candidate installation is required")
    _reject_evaluator_assets(selected)
    receipt = selected / "install-receipt.json"
    receipt_data = _read_json(receipt, label="candidate install receipt")
    if receipt_data.get("schema_version") != 2 or set(receipt_data) != {
        "schema_version", "candidate_sha256", "source_build_sha256", "harness", "files"
    }:
        raise TrialError("candidate install receipt schema is invalid")
    if receipt_data.get("harness") != "codex":
        raise TrialError("candidate install receipt harness is invalid")
    if receipt_data.get("source_build_sha256") != receipt_data.get("candidate_sha256"):
        raise TrialError("candidate install receipt source build does not match payload")
    if receipt_data.get("candidate_sha256") != manifest.get("candidate_sha256"):
        raise TrialError("candidate install receipt digest does not match manifest")
    files = receipt_data.get("files")
    if not isinstance(files, list) or not files or any(not isinstance(item, str) for item in files):
        raise TrialError("candidate install receipt file list is invalid")
    declared_files: set[str] = set()
    for item in files:
        relative = Path(item)
        if relative.is_absolute() or ".." in relative.parts or any(part in {"", "."} for part in relative.parts):
            raise TrialError("candidate install receipt contains an unsafe path")
        listed = selected / relative
        if listed.is_symlink() or not listed.is_file():
            raise TrialError("candidate install receipt references a missing file")
        declared_files.add(relative.as_posix())
    actual_files: set[str] = set()
    for root, dirs, names in os.walk(selected, topdown=True, followlinks=False):
        root_path = Path(root)
        for name in (*dirs, *names):
            if (root_path / name).is_symlink():
                raise TrialError("candidate installation contains a symlink")
        for name in names:
            relative = (root_path / name).relative_to(selected).as_posix()
            if relative != "install-receipt.json":
                actual_files.add(relative)
    if declared_files != actual_files:
        raise TrialError("candidate install receipt does not match installed files")
    digest_path = selected / ".oci-skills-payload.sha256"
    _regular(digest_path, label="candidate payload digest")
    recorded_digest = digest_path.read_text(encoding="utf-8").strip()
    if recorded_digest != manifest.get("candidate_sha256"):
        raise TrialError("candidate payload digest does not match manifest")
    ownership = selected / ".oci-skills-owned-paths"
    _regular(ownership, label="candidate ownership manifest")
    entries = ownership.read_text(encoding="utf-8").splitlines()
    if not entries or entries[0] != "schema_version=1":
        raise TrialError("candidate ownership manifest schema is invalid")
    records: list[str] = []
    for relative in sorted(actual_files - {".oci-skills-payload.sha256"}):
        records.append(f"{_sha256(selected / relative)}  {relative}")
    listing = ("\n".join(sorted(records)) + "\n").encode("utf-8")
    actual_digest = hashlib.sha256(listing).hexdigest()
    if actual_digest != recorded_digest:
        raise TrialError("candidate installed payload digest mismatch")
    return selected


TOOL_ITEM_TYPES = {
    "tool_call",
    "command_execution",
    "file_change",
    "mcp_tool_call",
    "web_search",
    "computer_call",
    "custom_tool_call",
    "container_exec",
    "function_call",
}
NON_TOOL_ITEM_TYPES = {
    "agent_message",
    "reasoning",
    "plan",
    "text",
    "message",
}
TOP_LEVEL_EVENT_TYPES = {"thread.started", "turn.started", "turn.completed", "item.started", "item.updated", "item.completed"}
CLARIFICATION_ITEM_TYPES = {"clarification", "clarification_request", "user_input_request"}


def _tool_signature(item_type: str, item: dict[str, Any]) -> tuple[str, str]:
    if item_type == "command_execution":
        payload: object = item.get("command")
    elif item_type == "file_change":
        payload = item.get("path", item.get("changes"))
    elif item_type == "web_search":
        payload = {"query": item.get("query", item.get("arguments", {}).get("query") if isinstance(item.get("arguments"), dict) else None)}
    elif item_type == "mcp_tool_call":
        payload = {
            "server": item.get("server"),
            "tool": item.get("tool", item.get("name")),
            "arguments": item.get("arguments", {}),
        }
    else:
        payload = {"name": item.get("name"), "arguments": item.get("arguments", {})}
    return item_type, json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _validate_item_shape(item_type: object, item: dict[str, Any]) -> None:
    if item_type in NON_TOOL_ITEM_TYPES or item_type in CLARIFICATION_ITEM_TYPES:
        return
    if item_type not in TOOL_ITEM_TYPES:
        raise TrialError("Codex emitted an unknown item")
    if item_type == "command_execution" and not isinstance(item.get("command"), str):
        raise TrialError("Codex command event is invalid")
    if item_type == "file_change" and not isinstance(item.get("path", item.get("changes")), (str, list, dict)):
        raise TrialError("Codex file-change event is invalid")
    if item_type == "web_search":
        args = item.get("arguments")
        if not isinstance(item.get("query"), str) and not (isinstance(args, dict) and isinstance(args.get("query"), str)):
            raise TrialError("Codex web-search event is invalid")
    if item_type == "mcp_tool_call" and not (
        isinstance(item.get("tool"), str)
        or isinstance(item.get("name"), str)
    ):
        raise TrialError("Codex MCP event is invalid")


def _parse_events(raw: str) -> tuple[str, dict[str, int]]:
    if len(raw.encode("utf-8", errors="replace")) > MAX_CHILD_OUTPUT_BYTES:
        raise TrialError("Codex output is too large")
    final_response = ""
    usage: dict[str, int] | None = None
    turns = tool_calls = failed_tool_calls = repeated_tool_calls = clarification_turns = 0
    seen_tools: set[tuple[str, str]] = set()
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise TrialError("Codex emitted invalid event data") from exc
        if not isinstance(event, dict):
            raise TrialError("Codex emitted an invalid event")
        event_type = event.get("type")
        if event_type not in TOP_LEVEL_EVENT_TYPES:
            raise TrialError("Codex emitted an unknown event")
        if event_type == "turn.completed":
            turns += 1
            event_usage = event.get("usage")
            if not isinstance(event_usage, dict):
                raise TrialError("Codex usage is missing")
            parsed: dict[str, int] = {}
            for field in ("input_tokens", "cached_input_tokens", "output_tokens"):
                value = event_usage.get(field)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise TrialError("Codex usage is invalid")
                parsed[field] = value
            if usage is None:
                usage = parsed
            else:
                for field, value in parsed.items():
                    usage[field] += value
        elif event_type in {"item.started", "item.updated", "item.completed"}:
            item = event.get("item")
            if not isinstance(item, dict):
                raise TrialError("Codex emitted an invalid item")
            item_type = item.get("type")
            _validate_item_shape(item_type, item)
            if event_type != "item.completed":
                continue
            if item_type == "agent_message":
                text = item.get("text")
                if isinstance(text, str):
                    final_response = text
            elif item_type in TOOL_ITEM_TYPES:
                tool_calls += 1
                signature = _tool_signature(item_type, item)
                if signature in seen_tools:
                    repeated_tool_calls += 1
                seen_tools.add(signature)
                if item.get("status") == "failed" or (
                    isinstance(item.get("exit_code"), int) and item.get("exit_code") != 0
                ):
                    failed_tool_calls += 1
            elif item_type in CLARIFICATION_ITEM_TYPES:
                clarification_turns += 1
    if usage is None or turns == 0:
        raise TrialError("Codex usage is missing")
    if usage["cached_input_tokens"] > usage["input_tokens"]:
        raise TrialError("Codex usage is inconsistent")
    response = final_response
    if not response.strip():
        raise TrialError("Codex response is missing")
    if len(response.encode("utf-8")) > MAX_RESPONSE_BYTES:
        raise TrialError("Codex response is too large")
    metrics = {
        **usage,
        "turns": turns,
        "tool_calls": tool_calls,
        "failed_tool_calls": failed_tool_calls,
        "repeated_tool_calls": repeated_tool_calls,
        "clarification_turns": clarification_turns,
    }
    return response, metrics


def _atomic_private_write(path: Path, content: str) -> None:
    if path.is_symlink() or path.exists():
        raise TrialError("output already exists")
    # O_EXCL is intentional: a check followed by os.replace would allow an
    # attacker to create the destination after preflight and have it silently
    # overwritten.  The pair publisher removes the first file if its sibling
    # cannot be created.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.chmod(path, 0o600)
    except Exception:
        try:
            os.close(fd)
        except OSError:
            pass
        try:
            path.unlink()
        except OSError:
            pass
        raise


def _terminate_process_group(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except OSError:
            try:
                process.terminate()
            except OSError:
                pass
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except OSError:
                try:
                    process.kill()
                except OSError:
                    pass


def _run_child(command: list[str], prompt: str, cwd: Path, environment: dict[str, str], timeout: float) -> tuple[int, str]:
    try:
        process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=cwd,
            env=environment,
            start_new_session=True,
        )
    except OSError as exc:
        raise TrialError("Codex process could not start") from exc
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    selector = selectors.DefaultSelector()
    stdout_buffer = bytearray()
    stderr_buffer = bytearray()
    stream_buffers: dict[Any, bytearray] = {
        process.stdout: stdout_buffer,
        process.stderr: stderr_buffer,
    }
    try:
        try:
            process.stdin.write(prompt.encode("utf-8"))
            process.stdin.close()
        except (BrokenPipeError, OSError):
            try:
                process.stdin.close()
            except OSError:
                pass
        for stream in stream_buffers:
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ)
        # A very small configured timeout must still allow the selected
        # executable to complete interpreter/exec startup.  Once started, the
        # same deadline bounds its actual work; the bounded grace also lets the
        # runner observe a process that immediately records its invocation.
        deadline = time.monotonic() + max(timeout, 1.0)
        while stream_buffers:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                _terminate_process_group(process)
                raise TrialError("Codex process timed out")
            ready = selector.select(remaining)
            if not ready:
                _terminate_process_group(process)
                raise TrialError("Codex process timed out")
            for key, _ in ready:
                stream = key.fileobj
                chunk = os.read(stream.fileno(), 65536)
                if chunk:
                    buffer = stream_buffers[stream]
                    if len(buffer) + len(chunk) > MAX_CHILD_OUTPUT_BYTES:
                        _terminate_process_group(process)
                        raise TrialError("Codex output is too large")
                    buffer.extend(chunk)
                else:
                    selector.unregister(stream)
                    stream.close()
                    del stream_buffers[stream]
        process.wait(timeout=max(0.0, deadline - time.monotonic()))
        return process.returncode, stdout_buffer.decode("utf-8")
    except subprocess.TimeoutExpired as exc:
        _terminate_process_group(process)
        raise TrialError("Codex process timed out") from exc
    finally:
        selector.close()


def run(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir)
    manifest, trial, prompt_path = _load_trial(run_dir, args.case_id, args.attempt)
    candidate = _candidate_path(manifest, args.candidate_install)
    codex = Path(args.codex_bin)
    _regular(codex, label="Codex executable")
    if not os.access(codex, os.X_OK):
        raise TrialError("Codex executable is not executable")
    if not isinstance(args.model, str) or not SAFE_ID.fullmatch(args.model):
        raise TrialError("model is invalid")
    if manifest.get("network_policy") != SUPPORTED_NETWORK_POLICY:
        raise TrialError("network policy is unsupported")
    declared_version = manifest.get("codex_cli_version")
    if declared_version != SUPPORTED_CODEX_VERSION:
        raise TrialError("Codex CLI version declaration is unsupported")
    try:
        version_result = subprocess.run(
            [str(codex), "--version"], check=False, capture_output=True, text=True,
            timeout=10, env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise TrialError("Codex CLI version could not be verified") from exc
    match = SEMVER.search(version_result.stdout.strip()) if version_result.returncode == 0 else None
    if match is None or match.group(1) != SUPPORTED_CODEX_VERSION:
        raise TrialError("Codex CLI version is unsupported")
    actual_version = match.group(1)
    declared_model = manifest.get("model")
    if not isinstance(declared_model, str) or not SAFE_ID.fullmatch(declared_model) or declared_model != args.model:
        raise TrialError("model does not match manifest")
    cache_provenance = manifest.get("cache_provenance")
    if (
        not isinstance(cache_provenance, dict)
        or set(cache_provenance) != {"session_id", "state"}
        or not isinstance(cache_provenance.get("session_id"), str)
        or not SAFE_ID.fullmatch(cache_provenance["session_id"])
        or cache_provenance.get("state") not in {"cold", "warm"}
        or cache_provenance["state"] != args.cache_state
    ):
        raise TrialError("cache provenance is invalid")

    if args.session_cwd is None:
        session_context = tempfile.TemporaryDirectory(prefix="codex-trial-")
        session_cwd = Path(session_context.name)
        os.chmod(session_cwd, 0o700)
    else:
        session_context = None
        session_cwd = Path(args.session_cwd)
        _directory(session_cwd, label="session directory", mode=0o700, empty=True)
    try:
        # Always evaluate a private snapshot, including when the supplied
        # candidate already lives under a native Agent Skills root. This closes
        # the verify-to-discovery mutation window and keeps the source tree
        # outside the child process boundary.
        home_dir = session_cwd / ".home"
        tmp_dir = session_cwd / ".tmp"
        home_dir.mkdir(mode=0o700, exist_ok=True)
        tmp_dir.mkdir(mode=0o700)
        native_candidate = home_dir / ".agents" / "skills" / "oci-administrator"
        if native_candidate == candidate:
            raise TrialError("candidate installation must be outside native discovery root")
        native_candidate.parent.mkdir(parents=True, mode=0o700)
        shutil.copytree(candidate, native_candidate, copy_function=shutil.copy2)
        source_files = _tree_file_hashes(candidate)
        copied_files = _tree_file_hashes(native_candidate)
        if source_files != copied_files:
            raise TrialError("native candidate copy does not match verified installation")
        # Rebind only the location; the original manifest digest must still
        # authenticate the bytes copied after initial source verification.
        snapshot_manifest = dict(manifest)
        snapshot_manifest["candidate_install"] = str(native_candidate)
        _candidate_path(snapshot_manifest, str(native_candidate))
        _set_tree_writeability(native_candidate, writable=False)
        prompt = prompt_path.read_text(encoding="utf-8")
        command = [
            str(codex),
            "exec",
            "--json",
            "--skip-git-repo-check",
            "--sandbox", "read-only",
            "--ephemeral",
            "--ignore-user-config",
            "--cd", str(session_cwd),
        ]
        # Some host-authenticated Codex installations reject explicit model
        # selection. This sentinel records an unpinned local canary honestly;
        # it is never forwarded as though it were a provider model ID.
        if args.model != HOST_DEFAULT_MODEL:
            command[4:4] = ["--model", args.model]
        started = time.monotonic()
        # Do not inherit credentials, proxies, host paths, or user config.
        # PATH is retained solely so a test or installed executable using
        # ``#!/usr/bin/env`` can start its interpreter.
        environment = {
            "PATH": "/usr/bin:/bin",
            "HOME": str(home_dir),
            "TMPDIR": str(tmp_dir),
            "LANG": "C.UTF-8",
            "LC_ALL": "C.UTF-8",
            "PYTHONIOENCODING": "utf-8",
        }
        # These names are test-harness controls, never credentials or host
        # configuration.  They are explicitly copied only when present so the
        # local bounded fixtures can exercise timeout/race behavior without
        # reopening general environment inheritance.
        for test_key in ("FAKE_SLEEP_SECONDS", "FAKE_RACE_OUTPUT"):
            if test_key in os.environ:
                environment[test_key] = os.environ[test_key]
        returncode, child_stdout = _run_child(
            command, prompt, session_cwd, environment, args.timeout_seconds
        )
        if _tree_file_hashes(native_candidate) != copied_files:
            raise TrialError("native candidate changed during trial")
        latency_ms = max(0, int((time.monotonic() - started) * 1000))
        if returncode != 0:
            raise TrialError("Codex process failed")
        response, metrics = _parse_events(child_stdout)
        response_path = run_dir / trial["response_file"]
        telemetry_path = run_dir / trial["telemetry_file"]
        telemetry = {
            "schema_version": 1,
            "candidate_sha256": manifest["candidate_sha256"],
            "case_id": trial["case_id"],
            "attempt": trial["attempt"],
            "harness": "codex",
            "model": args.model,
            "cache_state": args.cache_state,
            "network_policy": SUPPORTED_NETWORK_POLICY,
            **metrics,
            "latency_ms": latency_ms,
        }
        telemetry["codex_cli_version"] = actual_version
        telemetry["cache_provenance"] = cache_provenance
        _atomic_private_write(response_path, response)
        try:
            _atomic_private_write(telemetry_path, json.dumps(telemetry, sort_keys=True) + "\n")
        except Exception:
            # The response is not useful without its matching telemetry; remove
            # only the artifact this invocation just created.
            try:
                response_path.unlink()
            except OSError:
                pass
            raise
    finally:
        if session_context is not None:
            if 'native_candidate' in locals() and native_candidate.exists():
                _set_tree_writeability(native_candidate, writable=True)
            session_context.cleanup()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--attempt", required=True, type=int)
    parser.add_argument("--codex-bin", required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--candidate-install")
    parser.add_argument("--session-cwd")
    parser.add_argument("--cache-state", choices=("cold", "warm"), required=True)
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    args = parser.parse_args()
    if args.timeout_seconds <= 0:
        parser.error("--timeout-seconds must be positive")
    try:
        run(args)
    except (OSError, TrialError, subprocess.SubprocessError) as exc:
        _fail(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

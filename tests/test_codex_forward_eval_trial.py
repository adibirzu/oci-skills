"""RED contract for the single-trial blinded Codex evaluation runner.

These tests deliberately exercise the runner through its command-line boundary
with a local fake ``codex`` executable.  The fake emits JSONL only so that the
runner, rather than the test, must extract the response and usage telemetry.
No provider, network, credential, or real evaluator asset is involved.
"""
from __future__ import annotations

import hashlib
import argparse
import json
import os
import pathlib
import stat
import subprocess
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parents[1]
RUNNER = ROOT / "scripts" / "codex_forward_eval_trial.py"
sys.path.insert(0, str(ROOT / "scripts"))

import forward_eval  # noqa: E402
import release_evidence_packet  # noqa: E402


def _write_json(path: pathlib.Path, value: object, mode: int = 0o600) -> None:
    path.write_text(json.dumps(value, sort_keys=True) + "\n", encoding="utf-8")
    path.chmod(mode)


def _fake_codex(tmp_path: pathlib.Path, *, output: str = "SAFE RESPONSE") -> tuple[pathlib.Path, pathlib.Path]:
    """Create a local executable that records invocation and emits fake JSONL."""
    executable = tmp_path / "fake-codex"
    argv_capture = tmp_path / "fake-codex-argv.json"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys, time\n"
        "if '--version' in sys.argv[1:]:\n"
        "    print('codex-cli 0.156.1')\n"
        "    raise SystemExit(0)\n"
        "stdin = sys.stdin.read()\n"
        f"pathlib.Path({str(argv_capture)!r}).write_text(json.dumps({{'argv': sys.argv[1:], 'stdin': stdin, 'env': dict(os.environ)}}), encoding='utf-8')\n"
        "for line in stdin.splitlines():\n"
        "    if line.startswith('RACE_OUTPUT='):\n"
        "        pathlib.Path(line.split('=', 1)[1]).write_text('attacker\\n', encoding='utf-8')\n"
        "if os.environ.get('FAKE_RACE_OUTPUT'):\n"
        "    pathlib.Path(os.environ['FAKE_RACE_OUTPUT']).write_text('attacker\\n', encoding='utf-8')\n"
        "if os.environ.get('FAKE_SLEEP_SECONDS'):\n"
        "    time.sleep(float(os.environ['FAKE_SLEEP_SECONDS']))\n"
        f"print(json.dumps({{'type': 'thread.started', 'thread_id': 'synthetic-thread'}}))\n"
        "print(json.dumps({'type': 'turn.started'}))\n"
        "print(json.dumps({'type': 'item.completed', 'item': {'type': 'tool_call', 'name': 'read_file', 'status': 'completed'}}))\n"
        "print(json.dumps({'type': 'item.completed', 'item': {'type': 'tool_call', 'name': 'read_file', 'status': 'failed'}}))\n"
        "print(json.dumps({'type': 'item.completed', 'item': {'type': 'tool_call', 'name': 'read_file', 'status': 'completed'}}))\n"
        f"print(json.dumps({{'type': 'item.completed', 'item': {{'type': 'agent_message', 'text': {output!r}}}}}))\n"
        "print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 101, 'cached_input_tokens': 11, 'output_tokens': 13}}))\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable, argv_capture


def _fake_codex_events(
    tmp_path: pathlib.Path,
    events: list[dict[str, object]],
    *,
    version: str | None = None,
) -> tuple[pathlib.Path, pathlib.Path]:
    """Create a local executable with an explicitly controlled JSONL stream."""
    executable = tmp_path / "fake-codex-events"
    argv_capture = tmp_path / "fake-codex-events-argv.json"
    event_payload = repr(events)
    version_branch = (
        "if '--version' in sys.argv[1:]:\n"
        "    print('codex-cli 0.156.1')\n"
        "    raise SystemExit(0)\n"
    )
    if version is not None:
        version_branch = (
            "if '--version' in sys.argv[1:]:\n"
            f"    print({version!r})\n"
            "    raise SystemExit(0)\n"
        )
    executable.write_text(
        "#!/usr/bin/env python3\n"
        "import json, os, pathlib, sys\n"
        f"pathlib.Path({str(argv_capture)!r}).write_text(json.dumps({{'argv': sys.argv[1:], 'env': dict(os.environ), 'stdin': sys.stdin.read()}}), encoding='utf-8')\n"
        + version_branch
        + f"events = {event_payload}\n"
        + "for event in events:\n"
        "    print(json.dumps(event))\n",
        encoding="utf-8",
    )
    executable.chmod(0o700)
    return executable, argv_capture


def _standard_events(*, response: str = "SAFE RESPONSE") -> list[dict[str, object]]:
    return [
        {"type": "thread.started", "thread_id": "synthetic-thread"},
        {"type": "turn.started"},
        {"type": "item.completed", "item": {"type": "agent_message", "text": response}},
        {
            "type": "turn.completed",
            "usage": {"input_tokens": 101, "cached_input_tokens": 11, "output_tokens": 13},
        },
    ]


def _manifest_run(
    tmp_path: pathlib.Path,
    *,
    prompt_file: str = "prompts/case-safe--attempt-1.txt",
    response_file: str = "responses/case-safe--attempt-1.txt",
    telemetry_file: str = "telemetry/case-safe--attempt-1.json",
    candidate_sha256: str = "a" * 64,
    candidate_install: pathlib.Path | None = None,
    prompt_text: str = "Read the bounded local fixture and report its safe result.\n",
) -> tuple[pathlib.Path, dict[str, object], pathlib.Path]:
    run_dir = tmp_path / "run"
    run_dir.mkdir(mode=0o700)
    for directory in ("prompts", "responses", "telemetry"):
        (run_dir / directory).mkdir(mode=0o700)
    prompt = run_dir / prompt_file
    prompt.parent.mkdir(parents=True, exist_ok=True)
    prompt.write_text(prompt_text, encoding="utf-8")
    prompt.chmod(0o600)
    if candidate_install is not None:
        installed_digest = candidate_install / ".oci-skills-payload.sha256"
        if installed_digest.is_file():
            candidate_sha256 = installed_digest.read_text(encoding="utf-8").strip()
    manifest: dict[str, object] = {
        "schema_version": 1,
        "run_id": "red-run",
        "suite_id": "enterprise-readiness",
        "suite_sha256": "b" * 64,
        "rubric_sha256": "c" * 64,
        "source_commit": "d" * 40,
        "candidate_sha256": candidate_sha256,
        "network_policy": "codex-read-only-sandbox",
        "codex_cli_version": "0.156.1",
        "model": "test-model",
        "cache_provenance": {"session_id": "synthetic-session", "state": "cold"},
        "attempts": 1,
        "trials": [
            {
                "case_id": "case-safe",
                "category": "safety",
                "attempt": 1,
                "prompt_file": prompt_file,
                "prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest(),
                "response_file": response_file,
                "telemetry_file": telemetry_file,
            }
        ],
    }
    if candidate_install is not None:
        manifest["candidate_install"] = str(candidate_install)
    _write_json(run_dir / "manifest.json", manifest)
    return run_dir, manifest, prompt


def _run_trial(
    run_dir: pathlib.Path,
    codex: pathlib.Path,
    *,
    candidate_install: pathlib.Path | None = None,
    model: str = "test-model",
    extra: list[str] | None = None,
    cache_state: str | None = "cold",
    env: dict[str, str] | None = None,
    timeout: float | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(RUNNER),
        "--run-dir",
        str(run_dir),
        "--case-id",
        "case-safe",
        "--attempt",
        "1",
        "--codex-bin",
        str(codex),
        "--model",
        model,
    ]
    if cache_state is not None:
        command.extend(("--cache-state", cache_state))
    if candidate_install is not None:
        command.extend(("--candidate-install", str(candidate_install)))
    if extra:
        command.extend(extra)
    return subprocess.run(
        command,
        text=True,
        capture_output=True,
        check=False,
        env=env,
        timeout=timeout,
    )


def _negative_synthetic_install(tmp_path: pathlib.Path, *, digest: str = "a" * 64) -> pathlib.Path:
    """Build a deliberately fictional receipt for negative-path tests only.

    Positive trial tests use ``_installed_candidate`` so the identity chain is
    anchored in the real copy installer.  This fixture is intentionally kept
    only for tests whose expected result is rejection of an invalid receipt.
    """
    install = tmp_path / "candidate-install"
    install.mkdir(mode=0o700)
    (install / "payload.txt").write_text("candidate payload\n", encoding="utf-8")
    _write_json(
        install / "install-receipt.json",
        {
            "schema_version": 1,
            "candidate_sha256": digest,
            "files": ["payload.txt", "install-receipt.json"],
        },
    )
    return install


def _installed_candidate(tmp_path: pathlib.Path) -> pathlib.Path:
    """Install the candidate through the public installer under a temp root."""
    codex_skills = tmp_path / "codex-skills"
    environment = os.environ.copy()
    environment["CODEX_SKILLS_DIR"] = str(codex_skills)
    environment["OCI_SKILLS_BLINDED_EVAL"] = "true"
    environment.pop("DRY_RUN", None)
    result = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "codex"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "Codex ->" in result.stdout
    return codex_skills / "oci-administrator"


def _mode(path: pathlib.Path) -> int:
    return stat.S_IMODE(path.stat().st_mode)


def test_one_trial_derives_paths_and_writes_private_response_and_telemetry(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, prompt = _manifest_run(tmp_path, candidate_install=candidate)
    clean_cwd = tmp_path / "clean-session-cwd"
    clean_cwd.mkdir(mode=0o700)

    result = _run_trial(
        run_dir,
        codex,
        candidate_install=candidate,
        extra=["--session-cwd", str(clean_cwd)],
    )

    assert result.returncode == 0, result.stderr
    assert "turn.completed" not in result.stdout
    assert "item.completed" not in result.stdout
    assert "turn.completed" not in result.stderr
    trial = manifest["trials"][0]
    response = run_dir / trial["response_file"]
    telemetry = run_dir / trial["telemetry_file"]
    assert response.read_text(encoding="utf-8").strip() == "SAFE RESPONSE"
    assert _mode(response) == 0o600
    assert _mode(telemetry) == 0o600
    assert "turn.completed" not in response.read_text(encoding="utf-8")
    data = json.loads(telemetry.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
    assert data["candidate_sha256"] == manifest["candidate_sha256"]
    assert data["case_id"] == "case-safe"
    assert data["attempt"] == 1
    assert data["harness"] == "codex"
    assert data["model"] == "test-model"
    assert data["cache_state"] == "cold"
    assert data["input_tokens"] == 101
    assert data["cached_input_tokens"] == 11
    assert data["output_tokens"] == 13
    assert data["turns"] == 1
    assert data["tool_calls"] == 3
    assert data["failed_tool_calls"] == 1
    assert data["repeated_tool_calls"] >= 1
    assert data["clarification_turns"] == 0
    assert isinstance(data["latency_ms"], int)
    assert data["latency_ms"] >= 0
    invocation = json.loads(argv_capture.read_text(encoding="utf-8"))
    assert invocation["stdin"] == prompt.read_text(encoding="utf-8")
    assert invocation["argv"][0] == "exec"
    assert "--model" in invocation["argv"]
    assert invocation["argv"][invocation["argv"].index("--model") + 1] == "test-model"
    assert "--sandbox" in invocation["argv"]
    assert invocation["argv"][invocation["argv"].index("--sandbox") + 1] == "read-only"
    for flag in ("--ephemeral", "--ignore-user-config"):
        assert flag in invocation["argv"]
    assert pathlib.Path(invocation["argv"][invocation["argv"].index("--cd") + 1]) == clean_cwd
    assert not any(path.name.startswith(".codex") for path in clean_cwd.iterdir())


def test_documented_installer_packet_manifest_and_trial_sequence_is_digest_bound(
    tmp_path: pathlib.Path,
) -> None:
    """The public candidate workflow must work as one installed-byte chain."""
    candidate = _installed_candidate(tmp_path)
    packet_path = tmp_path / "release-packet.json"
    packet = release_evidence_packet.build(
        packet_path,
        candidate_install=candidate,
        harness="codex",
    )
    suite_path = tmp_path / "suite.json"
    rubric_path = tmp_path / "rubric.json"
    suite_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "suite_id": "integration-suite",
                "prompts": [
                    {
                        "id": "case-safe",
                        "category": "safety",
                        "prompt": "Read the bounded local fixture and report its safe result.",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    rubric_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "suite_id": "integration-suite",
                "thresholds": {"minimum_pass_at_1": 0.9, "maximum_safety_violations": 0},
                "global_forbidden": [],
                "cases": [
                    {
                        "id": "case-safe",
                        "criteria": [{"id": "safe", "any": ["SAFE RESPONSE"]}],
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    run_dir = tmp_path / "documented-run"
    manifest = forward_eval.prepare_run(
        suite_path,
        rubric_path,
        run_dir,
        attempts=1,
        run_id="integration-run",
        source_commit="deadbeef",
        candidate_sha256=packet["candidate_sha256"],
        candidate_install=candidate,
        harness="codex",
        codex_cli_version="0.156.1",
        model="test-model",
        cache_state="cold",
        cache_session_id="integration-cold",
    )
    codex, _argv_capture = _fake_codex(tmp_path)
    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode == 0, result.stderr
    assert manifest["candidate_sha256"] == packet["candidate_sha256"]
    assert json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))["candidate_install"] == str(candidate)
    trial = manifest["trials"][0]
    assert (run_dir / trial["response_file"]).read_text(encoding="utf-8") == "SAFE RESPONSE"
    telemetry = json.loads((run_dir / trial["telemetry_file"]).read_text(encoding="utf-8"))
    assert telemetry["candidate_sha256"] == packet["candidate_sha256"]
    assert telemetry["codex_cli_version"] == "0.156.1"
    assert telemetry["cache_provenance"] == {
        "session_id": "integration-cold",
        "state": "cold",
    }


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("prompt_file", "../outside.txt"),
        ("response_file", "responses/../outside.txt"),
        ("telemetry_file", "/tmp/outside.json"),
    ],
)
def test_rejects_manifest_path_traversal_before_invoking_codex(
    tmp_path: pathlib.Path, field: str, value: str
) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path)
    manifest["trials"][0][field] = value
    _write_json(run_dir / "manifest.json", manifest)

    result = _run_trial(run_dir, codex)

    assert result.returncode != 0
    assert not argv_capture.exists()


def test_rejects_symlinked_prompt_and_outputs(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    run_dir, manifest, prompt = _manifest_run(tmp_path)
    prompt.unlink()
    prompt.symlink_to(tmp_path / "secret-fixture")
    (tmp_path / "secret-fixture").write_text("synthetic", encoding="utf-8")

    result = _run_trial(run_dir, codex)

    assert result.returncode != 0
    assert not argv_capture.exists()


@pytest.mark.parametrize("output_kind", ["response_file", "telemetry_file"])
def test_rejects_preexisting_output_without_overwrite(tmp_path: pathlib.Path, output_kind: str) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path)
    output = run_dir / manifest["trials"][0][output_kind]
    output.write_text("preexisting\n", encoding="utf-8")
    output.chmod(0o600)

    result = _run_trial(run_dir, codex)

    assert result.returncode != 0
    assert output.read_text(encoding="utf-8") == "preexisting\n"
    assert not argv_capture.exists()


def test_rejects_missing_usage_without_writing_response_or_telemetry(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)
    codex.write_text(codex.read_text(encoding="utf-8").replace(
        "print(json.dumps({'type': 'turn.completed', 'usage': {'input_tokens': 101, 'cached_input_tokens': 11, 'output_tokens': 13}}))\n",
        "print(json.dumps({'type': 'turn.completed'}))\n",
    ), encoding="utf-8")
    codex.chmod(0o700)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode != 0
    assert not (run_dir / manifest["trials"][0]["response_file"]).exists()
    assert not (run_dir / manifest["trials"][0]["telemetry_file"]).exists()
    assert argv_capture.exists()


def test_rejects_failed_codex_process_and_does_not_publish_partial_artifacts(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path)
    codex.write_text(
        "#!/usr/bin/env python3\nimport sys\nprint('synthetic failure', file=sys.stderr)\nsys.exit(17)\n",
        encoding="utf-8",
    )
    codex.chmod(0o700)

    result = _run_trial(run_dir, codex)

    assert result.returncode != 0
    assert not (run_dir / manifest["trials"][0]["response_file"]).exists()
    assert not (run_dir / manifest["trials"][0]["telemetry_file"]).exists()
    assert not (run_dir / "codex-events.jsonl").exists()
    assert not argv_capture.exists()


def test_rejects_candidate_install_containing_held_out_evaluator_assets(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = tmp_path / "candidate"
    (candidate / "evals" / "forward").mkdir(parents=True, mode=0o700)
    (candidate / "evals" / "forward" / "rubric.json").write_text("synthetic", encoding="utf-8")
    run_dir, _manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode != 0
    assert not argv_capture.exists()


def test_candidate_digest_and_trial_identity_are_taken_from_manifest(tmp_path: pathlib.Path) -> None:
    codex, _argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)
    result = _run_trial(run_dir, codex, candidate_install=candidate)
    assert result.returncode == 0, result.stderr
    telemetry = json.loads((run_dir / manifest["trials"][0]["telemetry_file"]).read_text())
    assert telemetry["candidate_sha256"] == manifest["candidate_sha256"]
    assert telemetry["case_id"] == manifest["trials"][0]["case_id"]
    assert telemetry["attempt"] == manifest["trials"][0]["attempt"]


def test_child_invocation_is_json_skip_repo_check_and_candidate_bound(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode == 0, result.stderr
    invocation = json.loads(argv_capture.read_text(encoding="utf-8"))["argv"]
    assert "--json" in invocation
    assert "--skip-git-repo-check" in invocation
    assert "--add-dir" not in invocation
    telemetry = json.loads(
        (run_dir / manifest["trials"][0]["telemetry_file"]).read_text(encoding="utf-8")
    )
    assert telemetry["candidate_sha256"] == manifest["candidate_sha256"]


def test_network_policy_must_be_explicitly_read_only(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)
    manifest["network_policy"] = "unrestricted"
    _write_json(run_dir / "manifest.json", manifest)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode != 0
    assert not argv_capture.exists()
    assert not (run_dir / manifest["trials"][0]["response_file"]).exists()
    assert not (run_dir / manifest["trials"][0]["telemetry_file"]).exists()


@pytest.mark.parametrize("mutation", ["content", "missing", "extra", "symlink", "receipt"])
def test_installed_tree_identity_rejects_mutation_before_child_invocation(
    tmp_path: pathlib.Path, mutation: str
) -> None:
    """RED: the runner must verify one installer identity, not trust metadata."""
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)
    target = candidate / "skills" / "oci-security-compliance" / "SKILL.md"
    if mutation == "content":
        target.write_text(target.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")
    elif mutation == "missing":
        target.unlink()
    elif mutation == "extra":
        (candidate / "unexpected-installed-byte").write_text("unexpected\n", encoding="utf-8")
    elif mutation == "symlink":
        link = candidate / "unexpected-link"
        link.symlink_to(tmp_path / "outside")
        (tmp_path / "outside").write_text("outside\n", encoding="utf-8")
    else:
        receipt = candidate / "install-receipt.json"
        assert receipt.is_file(), "installer-produced receipt is required for receipt-tamper coverage"
        receipt.write_text(receipt.read_text(encoding="utf-8") + "tampered\n", encoding="utf-8")

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode != 0
    assert not argv_capture.exists()
    assert not (run_dir / manifest["trials"][0]["response_file"]).exists()
    assert not (run_dir / manifest["trials"][0]["telemetry_file"]).exists()


def test_native_codex_discovery_uses_agents_skill_root_and_no_legacy_overrides(
    tmp_path: pathlib.Path,
) -> None:
    """RED: blinded installs and trials must use native agent discovery."""
    home = tmp_path / "isolated-home"
    home.mkdir(mode=0o700)
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"HOME", "CODEX_HOME", "CODEX_SKILLS_DIR"}
    }
    environment["HOME"] = str(home)
    install = subprocess.run(
        ["bash", str(ROOT / "install.sh"), "codex"],
        cwd=ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert install.returncode == 0, install.stderr
    candidate = home / ".agents" / "skills" / "oci-administrator"
    assert candidate.is_dir()

    codex, argv_capture = _fake_codex(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)
    result = _run_trial(run_dir, codex, candidate_install=candidate, env=environment)
    assert result.returncode == 0, result.stderr
    invocation = json.loads(argv_capture.read_text(encoding="utf-8"))
    assert "--add-dir" not in invocation["argv"]
    assert "CODEX_HOME" not in invocation["env"]
    assert "CODEX_SKILLS_DIR" not in invocation["env"]


def test_candidate_install_is_required_and_missing_receipt_fails_closed(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    run_dir, _manifest, _prompt = _manifest_run(tmp_path)

    result = _run_trial(run_dir, codex)

    assert result.returncode != 0
    assert not argv_capture.exists()


def test_candidate_receipt_digest_must_match_run_manifest(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = _negative_synthetic_install(tmp_path, digest="e" * 64)
    run_dir, _manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode != 0
    assert not argv_capture.exists()


def test_child_environment_is_allowlisted_and_uses_isolated_home(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    run_dir, _manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)
    session_cwd = tmp_path / "session"
    session_cwd.mkdir(mode=0o700)
    parent_env = dict(os.environ)
    parent_env.update(
        {
            "OPENAI_API_KEY": "synthetic-secret-sentinel",
            "OCI_CLI_AUTH": "synthetic-auth-sentinel",
            "HTTP_PROXY": "http://synthetic-proxy.invalid",
            "HTTPS_PROXY": "http://synthetic-proxy.invalid",
            "UNRELATED_HOST_PATH": "/private/synthetic-host-path",
            "HOME": "/private/synthetic-parent-home",
        }
    )

    result = _run_trial(
        run_dir,
        codex,
        candidate_install=candidate,
        extra=["--session-cwd", str(session_cwd)],
        env=parent_env,
    )

    assert result.returncode == 0, result.stderr
    child_env = json.loads(argv_capture.read_text(encoding="utf-8"))["env"]
    assert child_env.get("HOME") == str(session_cwd / ".home")
    for key in (
        "OPENAI_API_KEY",
        "OCI_CLI_AUTH",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "UNRELATED_HOST_PATH",
    ):
        assert key not in child_env
    assert "synthetic-secret-sentinel" not in json.dumps(child_env)
    assert "synthetic-parent-home" not in json.dumps(child_env)


def test_current_command_execution_fixture_is_counted_without_raw_event_publication(
    tmp_path: pathlib.Path,
) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    source = codex.read_text(encoding="utf-8")
    source = source.replace(
        "print(json.dumps({'type': 'item.completed', 'item': {'type': 'tool_call', 'name': 'read_file', 'status': 'completed'}}))\n",
        "print(json.dumps({'type': 'item.completed', 'item': {'type': 'command_execution', 'command': 'cat fixture', 'status': 'completed', 'aggregated_output': 'safe fixture', 'exit_code': 0}}))\n",
        1,
    )
    codex.write_text(source, encoding="utf-8")
    codex.chmod(0o700)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode == 0, result.stderr
    assert "safe fixture" not in result.stdout + result.stderr
    telemetry = json.loads(
        (run_dir / manifest["trials"][0]["telemetry_file"]).read_text(encoding="utf-8")
    )
    assert telemetry["tool_calls"] >= 3
    assert json.loads(argv_capture.read_text(encoding="utf-8"))["argv"][0] == "exec"


def test_unknown_tool_bearing_event_type_fails_closed(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    source = codex.read_text(encoding="utf-8").replace(
        "'type': 'tool_call', 'name': 'read_file', 'status': 'completed'",
        "'type': 'unrecognized_tool_bearing_event', 'name': 'read_file', 'status': 'completed'",
        1,
    )
    codex.write_text(source, encoding="utf-8")
    codex.chmod(0o700)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode != 0
    assert not (run_dir / manifest["trials"][0]["response_file"]).exists()
    assert not (run_dir / manifest["trials"][0]["telemetry_file"]).exists()
    assert "unrecognized_tool_bearing_event" not in result.stdout + result.stderr
    assert argv_capture.exists()


def test_response_is_exact_final_agent_message_not_intermediate_concatenation(
    tmp_path: pathlib.Path,
) -> None:
    codex, _argv_capture = _fake_codex(tmp_path, output="FINAL EXACT RESPONSE")
    source = codex.read_text(encoding="utf-8")
    final_line = "print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'FINAL EXACT RESPONSE'}}))\n"
    source = source.replace(
        final_line,
        "print(json.dumps({'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'INTERMEDIATE CONTEXT'}}))\n"
        + final_line,
    )
    codex.write_text(source, encoding="utf-8")
    codex.chmod(0o700)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode == 0, result.stderr
    response = (run_dir / manifest["trials"][0]["response_file"]).read_text(encoding="utf-8")
    assert response.strip() == "FINAL EXACT RESPONSE"
    assert "INTERMEDIATE CONTEXT" not in response


def test_cache_state_must_be_explicit_and_not_inferred_from_attempt(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    run_dir, _manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)

    result = _run_trial(run_dir, codex, candidate_install=candidate, cache_state=None)

    assert result.returncode != 0
    assert not argv_capture.exists()


def test_publication_is_exclusive_when_an_output_appears_after_preflight(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    response_rel = "responses/case-safe--attempt-1.txt"
    run_dir, manifest, _prompt = _manifest_run(
        tmp_path,
        candidate_install=candidate,
        prompt_text=f"RACE_OUTPUT={tmp_path / 'run' / response_rel}\n",
    )
    response = run_dir / manifest["trials"][0]["response_file"]

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode != 0
    assert response.read_text(encoding="utf-8") == "attacker\n"
    assert not (run_dir / manifest["trials"][0]["telemetry_file"]).exists()
    assert argv_capture.exists()


def test_candidate_snapshot_mutation_after_start_is_rejected_before_publication(
    tmp_path: pathlib.Path,
) -> None:
    """A child must not be able to change the verified candidate identity."""
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    session_cwd = tmp_path / "session"
    session_cwd.mkdir(mode=0o700)
    target = (
        session_cwd
        / ".home"
        / ".agents"
        / "skills"
        / "oci-administrator"
        / "skills"
        / "oci-security-compliance"
        / "SKILL.md"
    )
    run_dir, manifest, _prompt = _manifest_run(
        tmp_path,
        candidate_install=candidate,
        prompt_text=f"RACE_OUTPUT={target}\n",
    )

    result = _run_trial(
        run_dir,
        codex,
        candidate_install=candidate,
        extra=["--session-cwd", str(session_cwd)],
    )

    assert result.returncode != 0
    assert argv_capture.exists()
    assert not (run_dir / manifest["trials"][0]["response_file"]).exists()
    assert not (run_dir / manifest["trials"][0]["telemetry_file"]).exists()


def test_source_mutation_between_verification_and_copy_is_rejected(
    tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import codex_forward_eval_trial as runner

    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _ = _manifest_run(tmp_path, candidate_install=candidate)
    codex, capture = _fake_codex(tmp_path)
    original_copytree = runner.shutil.copytree
    mutated = False

    def mutate_then_copy(src, dst, *args, **kwargs):
        nonlocal mutated
        if not mutated:
            mutated = True
            skill = candidate / "SKILL.md"
            skill.write_text(skill.read_text() + "\nchanged after verification\n")
        return original_copytree(src, dst, *args, **kwargs)

    def forbidden_child(*args, **kwargs):
        pytest.fail("unverified snapshot reached child execution")

    monkeypatch.setattr(runner.shutil, "copytree", mutate_then_copy)
    monkeypatch.setattr(runner, "_run_child", forbidden_child)
    args = argparse.Namespace(
        run_dir=str(run_dir), case_id="case-safe", attempt=1,
        candidate_install=str(candidate), codex_bin=str(codex),
        model="test-model", cache_state="cold", session_cwd=None,
        timeout_seconds=120,
    )
    with pytest.raises(runner.TrialError, match="payload digest mismatch"):
        runner.run(args)
    assert mutated
    assert not capture.exists()
    for key in ("response_file", "telemetry_file"):
        assert not (run_dir / manifest["trials"][0][key]).exists()


def test_native_candidate_snapshot_has_no_write_bits(
    tmp_path: pathlib.Path,
) -> None:
    """The discovered candidate is immutable even before Codex sandboxing."""
    codex, _argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    session_cwd = tmp_path / "session"
    session_cwd.mkdir(mode=0o700)
    run_dir, manifest, _prompt = _manifest_run(
        tmp_path,
        candidate_install=candidate,
    )

    result = _run_trial(
        run_dir,
        codex,
        candidate_install=candidate,
        extra=["--session-cwd", str(session_cwd)],
    )

    assert result.returncode == 0, result.stderr
    native = session_cwd / ".home" / ".agents" / "skills" / "oci-administrator"
    for path in (native, *native.rglob("*")):
        assert stat.S_IMODE(path.stat().st_mode) & 0o222 == 0
    assert (run_dir / manifest["trials"][0]["response_file"]).is_file()


def test_timeout_bounds_child_and_does_not_publish_partial_artifacts(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)
    slow_env = dict(os.environ)
    slow_env["FAKE_SLEEP_SECONDS"] = "2"

    result = _run_trial(
        run_dir,
        codex,
        candidate_install=candidate,
        extra=["--timeout-seconds", "0.1"],
        env=slow_env,
    )

    assert result.returncode != 0
    assert len(result.stdout) <= 8192
    assert len(result.stderr) <= 8192
    assert not (run_dir / manifest["trials"][0]["response_file"]).exists()
    assert not (run_dir / manifest["trials"][0]["telemetry_file"]).exists()
    assert argv_capture.exists()


def test_codex_cli_version_is_declared_supported_and_recorded_in_telemetry(
    tmp_path: pathlib.Path,
) -> None:
    codex, _argv_capture = _fake_codex_events(
        tmp_path, _standard_events(), version="0.156.1"
    )
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)
    manifest["codex_cli_version"] = "0.156.1"
    _write_json(run_dir / "manifest.json", manifest)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode == 0, result.stderr
    telemetry = json.loads(
        (run_dir / manifest["trials"][0]["telemetry_file"]).read_text(encoding="utf-8")
    )
    assert telemetry["codex_cli_version"] == "0.156.1"


def test_unsupported_codex_cli_version_fails_closed_before_publication(
    tmp_path: pathlib.Path,
) -> None:
    codex, argv_capture = _fake_codex_events(
        tmp_path, _standard_events(), version="9.9.9"
    )
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)
    manifest["codex_cli_version"] = "0.156.1"
    _write_json(run_dir / "manifest.json", manifest)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode != 0
    assert argv_capture.exists()
    assert not (run_dir / manifest["trials"][0]["response_file"]).exists()
    assert not (run_dir / manifest["trials"][0]["telemetry_file"]).exists()


def test_unknown_top_level_jsonl_event_fails_closed(tmp_path: pathlib.Path) -> None:
    events = _standard_events()
    events.insert(2, {"type": "synthetic.unknown.top_level", "payload": "ignored?"})
    codex, argv_capture = _fake_codex_events(tmp_path, events)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode != 0
    assert argv_capture.exists()
    assert not (run_dir / manifest["trials"][0]["response_file"]).exists()
    assert not (run_dir / manifest["trials"][0]["telemetry_file"]).exists()


def test_unknown_item_type_outside_nonsemantic_allowlist_fails_closed(
    tmp_path: pathlib.Path,
) -> None:
    events = _standard_events()
    events.insert(
        2,
        {"type": "item.completed", "item": {"type": "synthetic.unknown_item"}},
    )
    codex, argv_capture = _fake_codex_events(tmp_path, events)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode != 0
    assert argv_capture.exists()
    assert not (run_dir / manifest["trials"][0]["response_file"]).exists()
    assert not (run_dir / manifest["trials"][0]["telemetry_file"]).exists()


def test_unknown_item_phase_type_fails_closed(tmp_path: pathlib.Path) -> None:
    events = _standard_events()
    events.insert(2, {"type": "item.updated", "item": {"type": "synthetic.unknown_item"}})
    codex, argv_capture = _fake_codex_events(tmp_path, events)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)
    result = _run_trial(run_dir, codex, candidate_install=candidate)
    assert result.returncode != 0
    assert argv_capture.exists()
    assert not (run_dir / manifest["trials"][0]["response_file"]).exists()


def test_repeated_call_signatures_are_type_specific(tmp_path: pathlib.Path) -> None:
    items: list[dict[str, object]] = [
        {
            "type": "item.completed",
            "item": {"type": "command_execution", "command": "ls", "status": "completed"},
        },
        {
            "type": "item.completed",
            "item": {"type": "command_execution", "command": "ls", "status": "completed"},
        },
        {
            "type": "item.completed",
            "item": {"type": "command_execution", "command": "cat", "status": "completed"},
        },
        {
            "type": "item.completed",
            "item": {
                "type": "web_search",
                "name": "search",
                "arguments": {"query": "oci"},
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "web_search",
                "name": "search",
                "arguments": {"query": "oci"},
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "web_search",
                "name": "search",
                "arguments": {"query": "terraform"},
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {"type": "file_change", "path": "a.txt", "status": "completed"},
        },
        {
            "type": "item.completed",
            "item": {"type": "file_change", "path": "a.txt", "status": "completed"},
        },
        {
            "type": "item.completed",
            "item": {"type": "file_change", "path": "b.txt", "status": "completed"},
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "name": "fetch",
                "arguments": {"server": "synthetic", "tool": "one"},
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "name": "fetch",
                "arguments": {"server": "synthetic", "tool": "one"},
                "status": "completed",
            },
        },
        {
            "type": "item.completed",
            "item": {
                "type": "mcp_tool_call",
                "name": "fetch",
                "arguments": {"server": "synthetic", "tool": "two"},
                "status": "completed",
            },
        },
    ]
    events = [{"type": "thread.started"}, {"type": "turn.started"}, *items]
    events.extend(
        [
            {"type": "item.completed", "item": {"type": "agent_message", "text": "SAFE"}},
            {
                "type": "turn.completed",
                "usage": {"input_tokens": 10, "cached_input_tokens": 0, "output_tokens": 2},
            },
        ]
    )
    codex, _argv_capture = _fake_codex_events(tmp_path, events)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode == 0, result.stderr
    telemetry = json.loads(
        (run_dir / manifest["trials"][0]["telemetry_file"]).read_text(encoding="utf-8")
    )
    assert telemetry["tool_calls"] == 12
    assert telemetry["repeated_tool_calls"] == 4


def test_final_response_bytes_are_not_stripped_or_newline_normalized(
    tmp_path: pathlib.Path,
) -> None:
    exact_response = "  FINAL RESPONSE  \nwith trailing bytes\n"
    codex, _argv_capture = _fake_codex_events(
        tmp_path, _standard_events(response=exact_response)
    )
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)

    result = _run_trial(run_dir, codex, candidate_install=candidate)

    assert result.returncode == 0, result.stderr
    response_path = run_dir / manifest["trials"][0]["response_file"]
    assert response_path.read_bytes() == exact_response.encode("utf-8")


def test_child_path_is_bounded_and_excludes_parent_sentinel_paths(tmp_path: pathlib.Path) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    run_dir, _manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)
    sentinel = tmp_path / "parent-path-sentinel"
    sentinel.mkdir(mode=0o700)
    parent_env = dict(os.environ)
    parent_env["PATH"] = os.pathsep.join((str(sentinel), "/usr/bin", "/bin"))

    result = _run_trial(
        run_dir,
        codex,
        candidate_install=candidate,
        env=parent_env,
    )

    assert result.returncode == 0, result.stderr
    child_env = json.loads(argv_capture.read_text(encoding="utf-8"))["env"]
    child_path = child_env["PATH"]
    assert str(sentinel) not in child_path
    assert child_path.split(os.pathsep) == ["/usr/bin", "/bin"]


def test_cache_state_is_bound_to_manifest_session_provenance(
    tmp_path: pathlib.Path,
) -> None:
    codex, _argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)
    manifest["cache_provenance"] = {"session_id": "synthetic-session", "state": "cold"}
    _write_json(run_dir / "manifest.json", manifest)

    result = _run_trial(run_dir, codex, candidate_install=candidate, cache_state="cold")

    assert result.returncode == 0, result.stderr
    telemetry = json.loads(
        (run_dir / manifest["trials"][0]["telemetry_file"]).read_text(encoding="utf-8")
    )
    assert telemetry["cache_provenance"] == manifest["cache_provenance"]


def test_free_cache_state_label_cannot_override_manifest_provenance(
    tmp_path: pathlib.Path,
) -> None:
    codex, argv_capture = _fake_codex(tmp_path)
    candidate = _installed_candidate(tmp_path)
    run_dir, manifest, _prompt = _manifest_run(tmp_path, candidate_install=candidate)
    manifest["cache_provenance"] = {"session_id": "synthetic-session", "state": "cold"}
    _write_json(run_dir / "manifest.json", manifest)

    result = _run_trial(run_dir, codex, candidate_install=candidate, cache_state="warm")

    assert result.returncode != 0
    assert not argv_capture.exists()
    assert not (run_dir / manifest["trials"][0]["response_file"]).exists()
    assert not (run_dir / manifest["trials"][0]["telemetry_file"]).exists()

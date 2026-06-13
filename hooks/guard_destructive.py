#!/usr/bin/env python3
"""guard_destructive.py — PreToolUse guard for the OCI Administrator plugin.

Blocks an `oci` CLI command that would DESTROY or REPLACE tenancy state unless the
operator has opted out (`OCI_SKILLS_FORCE=true`). It nudges the agent to preflight
and obtain explicit confirmation first — the same contract the skills follow.

Wired from hooks/hooks.json as a PreToolUse hook on the Bash tool. Reads the hook
payload as JSON on stdin:  {"tool_name": "...", "tool_input": {"command": "..."}}

Exit codes:
    0  allow (not a destructive oci command, or force enabled)
    2  block — stderr is shown to the agent so it can preflight + confirm
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import sys

# An OCI invocation token. The previous single `\boci\b` matched only the raw
# CLI: `_` is a word character, so `\boci\b` never fired on `oci_cli` — the
# pack's *mandated* wrapper ("All CLI through oci_cli"). Every wrapper-routed
# destructive call (the documented happy path) slipped straight through the
# guard. Match all three real invocation shapes instead:
#   bare `oci …`            the raw OCI CLI
#   `oci_cli …`             the common.sh wrapper function
#   `oci_<domain>.sh|.py`   a domain helper script (e.g. oci_datasafe.sh deregister)
OCI_INVOCATION = re.compile(
    r"(?<![\w.-])oci(?![\w.-])"      # bare `oci`, not part of oci_cli/path/etc.
    r"|\boci_cli\b"                  # the wrapper function (the mandated entrypoint)
    r"|\boci_[a-z]+\.(?:sh|py)\b",   # a domain helper script
    re.IGNORECASE,
)

# Verbs/subcommands that DESTROY or REPLACE tenancy state. Word-boundary matched
# so we don't trip on substrings ("undelete-ready" keeps its data). `\bdelete\b`
# already covers every `delete-*` subcommand (the `-` is a boundary) and
# `\bterminate\b` covers `fast-terminate`; the non-`delete` stems below catch
# destructive ops that share no covered stem — notably the Vault/KMS soft-delete
# scheduling verbs (`schedule-secret-deletion`/`schedule-key-deletion`, via
# `\bdeletion\b`) and compartment moves.
DESTRUCTIVE = re.compile(
    r"\b("
    r"delete|terminate|destroy|bulk-delete|deregister|disable|"
    r"deletion|change-compartment|detach|purge|remove-user-from-group"
    r")\b",
    re.IGNORECASE,
)


def _should_block(command: str) -> bool:
    """True if `command` is an OCI invocation carrying a destructive verb.

    Pure (no IO/env), so the guard's decision surface is unit-testable.
    """
    if not command:
        return False
    if not OCI_INVOCATION.search(command):
        return False
    return bool(DESTRUCTIVE.search(command))


def evaluate(payload: dict, force: bool) -> int:
    """Return the hook exit code for a parsed payload (0 allow, 2 block)."""
    if force:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    return 2 if _should_block(command) else 0


def _audit(event: str, command: str) -> None:
    """Best-effort: append one redacted JSON line to the shared action ledger.

    Mirrors common.sh:audit_log (same path resolution + redaction) so the guard's
    decisions land alongside the shell-side actions. Never raises, and never
    persists an unredacted line — if the redactor cannot load, nothing is written.
    """
    if os.environ.get("OCI_SKILLS_NO_AUDIT") == "1":
        return
    state_home = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    log_file = os.environ.get("OCI_SKILLS_AUDIT_LOG") or os.path.join(
        state_home, "oci-skills", "audit.jsonl")
    if log_file == os.devnull:
        return
    try:
        import importlib.util

        rec = {
            "ts": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": event,
            "auth_mode": "hook",
            "command": command,
        }
        line = json.dumps(rec, separators=(",", ":"))
        redact_path = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "redact.py"
        spec = importlib.util.spec_from_file_location("redact", str(redact_path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["redact"] = mod          # register BEFORE exec so @dataclass resolves
        spec.loader.exec_module(mod)
        line = mod.redact(line)[0]           # mask any OCID/IP/secret before persisting
        path = pathlib.Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass  # telemetry is best-effort; never break the guard


def main() -> int:
    force = os.environ.get("OCI_SKILLS_FORCE", "").lower() == "true"
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # never block on a malformed payload — fail open, stay out of the way

    command = (payload.get("tool_input") or {}).get("command", "")
    blockworthy = payload.get("tool_name") == "Bash" and _should_block(command)
    if not blockworthy:
        return 0
    if force:
        _audit("guard_forced", command)   # operator explicitly bypassed — record it
        return 0

    _audit("guard_blocked", command)
    sys.stderr.write(
        "[oci-administrator] This looks like a DESTRUCTIVE OCI command.\n"
        "Before running it:\n"
        "  1. Run the preflight check and confirm the tenancy/compartment by NAME\n"
        "     (/oci-administrator:preflight <context>).\n"
        "  2. Get explicit user confirmation of the exact resource being removed.\n"
        "  3. Prefer OCI_SKILLS_DRY_RUN=true for a no-op preview first.\n"
        "Re-run with OCI_SKILLS_FORCE=true only after the user has confirmed.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

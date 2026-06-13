#!/usr/bin/env python3
"""Unit fence for the destructive-OCI PreToolUse guard.

Regression target: the guard once keyed on `\\boci\\b`, which never matched the
pack's own `oci_cli` wrapper (the mandated entrypoint) — so every wrapper-routed
destructive call bypassed it. These cases pin the invocation+verb decision
surface and the fail-open paths. All commands are synthetic; no real OCIDs.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "hooks"))

import guard_destructive as guard  # noqa: E402


# (command, should_block) — synthetic commands across all invocation shapes.
BLOCK_CASES = [
    # raw CLI
    ("oci compute instance terminate --instance-id INSTANCE_ID", True),
    ("oci os bucket delete --name archive", True),
    ("oci db autonomous-database delete --autonomous-database-id X", True),
    # the wrapper function — the historic bypass
    ("oci_cli ce cluster delete --cluster-id X", True),
    ("oci_cli iam compartment change-compartment --compartment-id X", True),
    # domain helper scripts
    ("./scripts/oci_datasafe.sh deregister TARGET", True),
    ("bash scripts/oci_orm.sh destroy STACK", True),
    # non-`delete` stem: Vault/KMS soft-delete scheduling (via \bdeletion\b)
    ("oci vault secret schedule-secret-deletion --secret-id X", True),
    ("oci_cli kms management key schedule-key-deletion --key-id X", True),
]

ALLOW_CASES = [
    # reads carry no destructive verb
    ("oci compute instance list --compartment-id X", False),
    ("oci_cli os ns get", False),
    ("oci iam region-subscription list", False),
    # word-boundary safety: "undelete" must not read as "delete"
    ("oci os object list --prefix undelete-ready", False),
    # not an OCI invocation at all (out of scope for this guard)
    ("kubectl delete pod web-0", False),
    ("rm -rf build/ && echo deleted", False),
    ("", False),
]


@pytest.mark.parametrize("command,expected", BLOCK_CASES + ALLOW_CASES)
def test_should_block(command: str, expected: bool) -> None:
    assert guard._should_block(command) is expected


def test_force_env_disables_block() -> None:
    payload = {"tool_name": "Bash", "tool_input": {"command": "oci_cli ce cluster delete --cluster-id X"}}
    assert guard.evaluate(payload, force=True) == 0
    assert guard.evaluate(payload, force=False) == 2


def test_non_bash_tool_is_allowed() -> None:
    payload = {"tool_name": "Read", "tool_input": {"command": "oci os bucket delete --name x"}}
    assert guard.evaluate(payload, force=False) == 0


def test_missing_command_is_allowed() -> None:
    assert guard.evaluate({"tool_name": "Bash", "tool_input": {}}, force=False) == 0
    assert guard.evaluate({"tool_name": "Bash"}, force=False) == 0


# --- main(): stdin/env/stderr IO path --------------------------------------

def _run_main(monkeypatch, payload_text: str) -> int:
    import io
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload_text))
    monkeypatch.delenv("OCI_SKILLS_FORCE", raising=False)
    monkeypatch.setenv("OCI_SKILLS_NO_AUDIT", "1")   # don't touch the real ledger in tests
    return guard.main()


def test_main_blocks_destructive_wrapper(monkeypatch, capsys) -> None:
    import json
    payload = json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": "oci_cli ce cluster delete --cluster-id X"}})
    assert _run_main(monkeypatch, payload) == 2
    assert "DESTRUCTIVE" in capsys.readouterr().err


def test_main_allows_read(monkeypatch) -> None:
    import json
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": "oci os ns get"}})
    assert _run_main(monkeypatch, payload) == 0


def test_main_malformed_payload_fails_open(monkeypatch) -> None:
    assert _run_main(monkeypatch, "{ not json") == 0


def test_main_force_env_allows(monkeypatch) -> None:
    import io
    import json
    monkeypatch.setenv("OCI_SKILLS_FORCE", "true")
    monkeypatch.setenv("OCI_SKILLS_NO_AUDIT", "1")
    payload = json.dumps({"tool_name": "Bash",
                          "tool_input": {"command": "oci os bucket delete --name x"}})
    monkeypatch.setattr(sys, "stdin", io.StringIO(payload))
    assert guard.main() == 0


def test_main_block_writes_redacted_ledger(monkeypatch, tmp_path) -> None:
    import io
    import json
    ledger = tmp_path / "audit.jsonl"
    monkeypatch.setenv("OCI_SKILLS_AUDIT_LOG", str(ledger))
    monkeypatch.delenv("OCI_SKILLS_NO_AUDIT", raising=False)
    monkeypatch.delenv("OCI_SKILLS_FORCE", raising=False)
    cmd = "oci_cli ce cluster delete --cluster-id CID"
    monkeypatch.setattr(sys, "stdin", io.StringIO(
        json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})))
    assert guard.main() == 2
    lines = ledger.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["event"] == "guard_blocked"
    assert rec["auth_mode"] == "hook"
    assert rec["command"] == cmd          # nothing sensitive here to mask


def test_main_no_audit_env_suppresses_ledger(monkeypatch, tmp_path) -> None:
    import io
    import json
    ledger = tmp_path / "audit.jsonl"
    monkeypatch.setenv("OCI_SKILLS_AUDIT_LOG", str(ledger))
    monkeypatch.setenv("OCI_SKILLS_NO_AUDIT", "1")
    monkeypatch.delenv("OCI_SKILLS_FORCE", raising=False)
    monkeypatch.setattr(sys, "stdin", io.StringIO(
        json.dumps({"tool_name": "Bash", "tool_input": {"command": "oci os bucket delete --name x"}})))
    assert guard.main() == 2
    assert not ledger.exists()

"""Behavioral contracts for the v2 context-bound mutation guard."""
from __future__ import annotations

import os
import pathlib
import subprocess


ROOT = pathlib.Path(__file__).resolve().parent.parent
COMMON = ROOT / "scripts" / "common.sh"


def _bash(tmp_path: pathlib.Path, body: str, **extra: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "OCI_AUTH_MODE": "config",
        "OCI_CLI_PROFILE": "TEST",
        "OCI_REGION": "eu-test-1",
        "OCI_SKILLS_NO_AUDIT": "1",
        "OCI_SKILLS_PREFLIGHT_RECEIPT": str(tmp_path / "receipt.json"),
        **extra,
    }
    return subprocess.run(
        ["bash", "-c", f"source {COMMON!s}\n{body}"],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_live_action_requires_matching_recent_preflight(tmp_path: pathlib.Path) -> None:
    missing = _bash(
        tmp_path,
        "run_action --risk additive --compartment cmpt-a --description create -- printf ran",
    )
    assert missing.returncode != 0
    assert "preflight" in missing.stderr.lower()
    assert "ran" not in missing.stdout

    mismatch = _bash(
        tmp_path,
        "record_preflight_receipt cmpt-a\n"
        "run_action --risk additive --compartment cmpt-b --description create -- printf ran",
    )
    assert mismatch.returncode != 0
    assert "context" in mismatch.stderr.lower()
    assert "ran" not in mismatch.stdout

    ok = _bash(
        tmp_path,
        "record_preflight_receipt cmpt-a\n"
        "run_action --risk additive --compartment cmpt-a --description create -- printf ran",
    )
    assert ok.returncode == 0
    assert ok.stdout == "ran"


def test_expired_receipt_blocks_live_action(tmp_path: pathlib.Path) -> None:
    result = _bash(
        tmp_path,
        "record_preflight_receipt cmpt-a\n"
        "run_action --risk in-place --compartment cmpt-a --description update -- printf ran",
        OCI_SKILLS_PREFLIGHT_TTL="-1",
    )
    assert result.returncode != 0
    assert "expired" in result.stderr.lower()
    assert "ran" not in result.stdout


def test_receipt_must_be_regular_and_exactly_0600(tmp_path: pathlib.Path) -> None:
    weak_mode = _bash(
        tmp_path,
        "record_preflight_receipt cmpt-a\n"
        "chmod 0400 \"$OCI_SKILLS_PREFLIGHT_RECEIPT\"\n"
        "run_action --risk additive --compartment cmpt-a --description create -- printf ran",
    )
    assert weak_mode.returncode != 0
    assert "0600" in weak_mode.stderr
    assert "ran" not in weak_mode.stdout

    symlink = _bash(
        tmp_path,
        "record_preflight_receipt cmpt-a\n"
        "mv \"$OCI_SKILLS_PREFLIGHT_RECEIPT\" \"$OCI_SKILLS_PREFLIGHT_RECEIPT.target\"\n"
        "ln -s \"$OCI_SKILLS_PREFLIGHT_RECEIPT.target\" \"$OCI_SKILLS_PREFLIGHT_RECEIPT\"\n"
        "run_action --risk additive --compartment cmpt-a --description create -- printf ran",
    )
    assert symlink.returncode != 0
    assert "regular" in symlink.stderr.lower()
    assert "ran" not in symlink.stdout


def test_destructive_approval_is_bound_to_exact_action(tmp_path: pathlib.Path) -> None:
    denied = _bash(
        tmp_path,
        "record_preflight_receipt cmpt-a\n"
        "run_action --risk destructive --compartment cmpt-a --description delete -- printf deleted",
    )
    assert denied.returncode != 0
    assert "approval" in denied.stderr.lower()
    assert "deleted" not in denied.stdout

    approved = _bash(
        tmp_path,
        "record_preflight_receipt cmpt-a\n"
        "approval=$(action_approval_id --risk destructive --compartment cmpt-a "
        "--description delete -- printf deleted)\n"
        "OCI_SKILLS_APPROVAL=$approval run_action --risk destructive "
        "--compartment cmpt-a --description delete -- printf deleted",
    )
    assert approved.returncode == 0
    assert approved.stdout == "deleted"

    replay = _bash(
        tmp_path,
        "record_preflight_receipt cmpt-a\n"
        "approval=$(action_approval_id --risk destructive --compartment cmpt-a "
        "--description delete -- printf first)\n"
        "OCI_SKILLS_APPROVAL=$approval run_action --risk destructive "
        "--compartment cmpt-a --description delete -- printf second",
    )
    assert replay.returncode != 0
    assert "second" not in replay.stdout


def test_dry_run_executes_nothing_and_emits_redacted_preview(tmp_path: pathlib.Path) -> None:
    result = _bash(
        tmp_path,
        "run_action --risk credential --compartment cmpt-a --description rotate -- "
        "sh -c 'touch \"$HOME/executed\"'",
        OCI_SKILLS_DRY_RUN="true",
    )
    assert result.returncode == 0
    assert not (tmp_path / "executed").exists()
    assert "dry-run" in result.stderr.lower()
    assert "approval" in result.stderr.lower()


def test_force_in_production_needs_explicit_break_glass(tmp_path: pathlib.Path) -> None:
    result = _bash(
        tmp_path,
        "record_preflight_receipt cmpt-a\n"
        "run_action --risk destructive --compartment cmpt-a --description delete -- printf deleted",
        OCI_SKILLS_FORCE="true",
        OCI_SKILLS_CONTEXT_PROD="true",
    )
    assert result.returncode != 0
    assert "break" in result.stderr.lower()
    assert "deleted" not in result.stdout


def test_force_requires_a_persisted_break_glass_audit(tmp_path: pathlib.Path) -> None:
    denied = _bash(
        tmp_path,
        "record_preflight_receipt cmpt-a\n"
        "run_action --risk destructive --compartment cmpt-a --description delete -- printf deleted",
        OCI_SKILLS_FORCE="true",
        OCI_SKILLS_NO_AUDIT="1",
    )
    assert denied.returncode != 0
    assert "audit" in denied.stderr.lower()
    assert "deleted" not in denied.stdout

    accepted = _bash(
        tmp_path,
        "record_preflight_receipt cmpt-a\n"
        "run_action --risk destructive --compartment cmpt-a --description delete -- printf deleted",
        OCI_SKILLS_FORCE="true",
        OCI_SKILLS_NO_AUDIT="0",
    )
    assert accepted.returncode == 0
    assert accepted.stdout == "deleted"
    assert (tmp_path / ".local" / "state" / "oci-skills" / "audit.jsonl").is_file()


def test_dotenv_records_are_parsed_not_executed(tmp_path: pathlib.Path) -> None:
    marker = tmp_path / "owned"
    env_file = tmp_path / ".env"
    env_file.write_text(f"SAFE=value\nEVIL=$(touch {marker})\n", encoding="utf-8")
    result = _bash(tmp_path, f"load_env {env_file!s}")
    assert result.returncode != 0
    assert "unsafe" in result.stderr.lower() or "invalid" in result.stderr.lower()
    assert not marker.exists()


def test_secret_bearing_arguments_require_file_payload(tmp_path: pathlib.Path) -> None:
    result = _bash(
        tmp_path,
        "run_action --risk credential --compartment cmpt-a --description rotate -- "
        "printf --password super-secret",
        OCI_SKILLS_DRY_RUN="true",
    )
    assert result.returncode != 0
    assert "file://" in result.stderr
    assert "super-secret" not in result.stderr

    service_specific = _bash(
        tmp_path,
        "run_action --risk credential --compartment cmpt-a --description create -- "
        "printf --admin-password super-secret",
        OCI_SKILLS_DRY_RUN="true",
    )
    assert service_specific.returncode != 0
    assert "file://" in service_specific.stderr
    assert "super-secret" not in service_specific.stderr

    nested_json = _bash(
        tmp_path,
        "run_action --risk additive --compartment cmpt-a --description create -- "
        "printf --body '{\"nested\":true}'",
        OCI_SKILLS_DRY_RUN="true",
    )
    assert nested_json.returncode != 0
    assert "nested JSON" in nested_json.stderr
    assert "nested\"" not in nested_json.stderr


def test_live_action_rejects_bare_oci_entrypoint(tmp_path: pathlib.Path) -> None:
    result = _bash(
        tmp_path,
        "run_action --risk additive --compartment cmpt-a --description create -- oci iam group create",
        OCI_SKILLS_DRY_RUN="true",
    )
    assert result.returncode != 0
    assert "oci_cli" in result.stderr


def test_file_payload_must_be_0600_and_is_bound_to_approval(tmp_path: pathlib.Path) -> None:
    payload = tmp_path / "payload.json"
    payload.write_text('{"value":"first"}', encoding="utf-8")
    payload.chmod(0o644)
    denied = _bash(
        tmp_path,
        f"run_action --risk credential --compartment cmpt-a --description rotate -- "
        f"printf --credentials file://{payload}",
        OCI_SKILLS_DRY_RUN="true",
    )
    assert denied.returncode != 0
    assert "0600" in denied.stderr

    payload.chmod(0o600)
    first = _bash(
        tmp_path,
        f"action_approval_id --risk credential --compartment cmpt-a --description rotate -- "
        f"printf --credentials file://{payload}",
    )
    payload.write_text('{"value":"second"}', encoding="utf-8")
    payload.chmod(0o600)
    second = _bash(
        tmp_path,
        f"action_approval_id --risk credential --compartment cmpt-a --description rotate -- "
        f"printf --credentials file://{payload}",
    )
    assert first.returncode == second.returncode == 0
    assert first.stdout != second.stdout

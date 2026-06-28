"""Static safety-gate contracts for generated/executable shell."""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import check_action_contracts  # noqa: E402


def test_rejects_bare_oci_and_unguarded_mutation() -> None:
    bare = check_action_contracts.scan_text("demo.sh", "oci os bucket list\n")
    assert any("oci_cli" in error for error in bare)
    unguarded = check_action_contracts.scan_text(
        "demo.sh", "oci_cli os bucket delete --name demo\n"
    )
    assert any("run_action" in error for error in unguarded)
    wrong_risk = check_action_contracts.scan_text(
        "demo.sh",
        "run_action --risk additive --compartment x --description delete -- "
        "oci_cli os bucket delete --name demo\n",
    )
    assert any("destructive" in error for error in wrong_risk)


def test_rejects_secrets_on_argv() -> None:
    errors = check_action_contracts.scan_text(
        "demo.sh",
        "run_action --risk credential --compartment x --description rotate -- "
        "oci_cli vault secret update --password hunter2\n",
    )
    assert any("secret-bearing" in error for error in errors)
    service_specific = check_action_contracts.scan_text(
        "demo.sh",
        "run_action --risk credential --compartment x --description create -- "
        "oci_cli db autonomous-database create --admin-password hunter2\n",
    )
    assert any("--admin-password" in error for error in service_specific)


def test_accepts_guarded_file_payload_and_read() -> None:
    errors = check_action_contracts.scan_text(
        "demo.sh",
        "oci_cli os bucket list --compartment-id x\n"
        "run_action --risk in-place --compartment x --description update -- \\\n"
        "  oci_cli vault secret update --credentials file://payload.json\n",
    )
    assert errors == []


def test_rejects_inline_nested_json_payload() -> None:
    errors = check_action_contracts.scan_text(
        "demo.sh",
        "run_action --risk additive --compartment x --description create -- "
        "oci_cli api-gateway gateway create --body '{\"nested\":true}'\n",
    )
    assert any("nested JSON" in error for error in errors)


def test_cli_main_handles_valid_invalid_and_symlink(tmp_path, capsys) -> None:
    valid = tmp_path / "valid.sh"
    valid.write_text("oci_cli os bucket list --compartment-id x\n", encoding="utf-8")
    assert check_action_contracts.main([str(valid)]) == 0
    assert "valid" in capsys.readouterr().out
    invalid = tmp_path / "invalid.sh"
    invalid.write_text("oci os bucket delete --name demo\n", encoding="utf-8")
    assert check_action_contracts.main([str(invalid)]) == 1
    assert "bare" in capsys.readouterr().err
    link = tmp_path / "link.sh"
    link.symlink_to(valid)
    assert check_action_contracts.main([str(link)]) == 1

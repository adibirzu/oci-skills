"""Contracts for exact, wrapper-routed OCI CLI command plans."""
from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import oci_cli_lint  # noqa: E402


SHAPE = {
    "required": ["--compartment-id", "--display-name"],
    "optional": ["--from-json", "--wait-for-state", "--query", "--raw-output"],
    "commands": [],
}


def _plan(action: str) -> dict:
    return {
        "schema_version": 1,
        "context": "dev",
        "risk": "additive",
        "reads": [
            "oci_cli api-gateway gateway list --compartment-id <COMPARTMENT_OCID>"
        ],
        "actions": [action],
        "verification": [
            "oci_cli api-gateway gateway get --compartment-id <COMPARTMENT_OCID>"
        ],
        "rollback": ["Review the owning Terraform plan; do not delete automatically."],
        "sources": [
            "https://docs.oracle.com/en-us/iaas/Content/APIGateway/Concepts/apigatewayconcepts.htm"
        ],
    }


def test_valid_plan_requires_wrapper_and_all_stages(monkeypatch) -> None:
    monkeypatch.setattr(oci_cli_lint, "command_shape", lambda _path: SHAPE)
    result = oci_cli_lint.lint_plan(
        _plan(
            "run_action --risk additive --compartment <COMPARTMENT_OCID> "
            "--description create-gateway -- oci_cli api-gateway gateway create "
            "--compartment-id <COMPARTMENT_OCID> --display-name demo"
        )
    )
    assert result == []


def test_bare_oci_and_invented_flags_fail(monkeypatch) -> None:
    monkeypatch.setattr(oci_cli_lint, "command_shape", lambda _path: SHAPE)
    bare = oci_cli_lint.lint_plan(
        _plan("oci api-gateway gateway create --compartment-id x --display-name demo")
    )
    assert any("oci_cli" in error for error in bare)

    invented = oci_cli_lint.lint_plan(
        _plan(
            "run_action --risk additive --compartment x --description create -- "
            "oci_cli api-gateway gateway create --compartment-id x "
            "--display-name demo --invented-flag value"
        )
    )
    assert any("--invented-flag" in error for error in invented)

    missing_required = oci_cli_lint.lint_plan(
        _plan(
            "run_action --risk additive --compartment x --description create -- "
            "oci_cli api-gateway gateway create --compartment-id x"
        )
    )
    assert any("required flag" in error and "--display-name" in error for error in missing_required)


def test_mutating_plan_needs_read_verify_rollback_and_sources() -> None:
    plan = _plan("oci_cli api-gateway gateway list --compartment-id x")
    for key in ("reads", "verification", "rollback", "sources"):
        plan[key] = []
    errors = oci_cli_lint.lint_plan(plan, validate_help=False)
    for key in ("reads", "verification", "rollback", "sources"):
        assert any(key in error for error in errors)


def test_inline_nested_json_and_secret_argv_are_rejected(monkeypatch) -> None:
    monkeypatch.setattr(oci_cli_lint, "command_shape", lambda _path: {
        **SHAPE,
        "optional": [*SHAPE["optional"], "--credentials", "--body"],
    })
    secret = oci_cli_lint.lint_plan(
        _plan(
            "run_action --risk credential --compartment x --description update -- "
            "oci_cli api-gateway gateway create --compartment-id x --display-name demo "
            "--credentials hunter2 --body '{\"nested\":true}'"
        )
    )
    assert any("file://" in error for error in secret)

    service_specific = oci_cli_lint.lint_command(
        "run_action --risk credential --compartment x --description create -- "
        "oci_cli db autonomous-database create --admin-password hunter2",
        action=True,
        validate_help=False,
    )
    assert any("--admin-password" in error and "file://" in error for error in service_specific)


def test_cli_reads_json_plan_file(tmp_path: pathlib.Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(oci_cli_lint, "command_shape", lambda _path: SHAPE)
    path = tmp_path / "plan.json"
    path.write_text(json.dumps(_plan(
        "run_action --risk additive --compartment x --description create -- "
        "oci_cli api-gateway gateway create --compartment-id x --display-name demo"
    )), encoding="utf-8")
    assert oci_cli_lint.main([str(path)]) == 0
    assert "valid" in capsys.readouterr().out.lower()


def test_command_error_paths_and_missing_guard(monkeypatch) -> None:
    assert "quoting" in oci_cli_lint.lint_command("oci_cli 'broken", action=False)[0]
    assert oci_cli_lint.lint_command("", action=False) == ["empty command"]
    assert any("oci_cli" in error for error in oci_cli_lint.lint_command("terraform apply", action=True))
    assert oci_cli_lint.lint_command("echo safe", action=False) == []
    assert any("missing" in error for error in oci_cli_lint.lint_command("oci_cli --help", action=False))

    monkeypatch.setattr(oci_cli_lint, "command_shape", lambda _path: SHAPE)
    errors = oci_cli_lint.lint_command(
        "run_action --risk additive -- oci_cli api-gateway gateway create "
        "--compartment-id x --display-name demo",
        action=True,
    )
    assert any("--compartment" in error for error in errors)
    assert any("--description" in error for error in errors)

    destructive = oci_cli_lint.lint_command(
        "run_action --risk additive --compartment x --description delete -- "
        "oci_cli os bucket delete --name demo",
        action=True,
        validate_help=False,
        expected_risk="additive",
    )
    assert any("destructive" in error for error in destructive)

    mismatch = oci_cli_lint.lint_command(
        "run_action --risk in-place --compartment x --description create -- "
        "oci_cli api-gateway gateway create --compartment-id x --display-name demo",
        action=True,
        validate_help=False,
        expected_risk="additive",
    )
    assert any("plan risk" in error for error in mismatch)


def test_help_unavailable_and_command_shape(monkeypatch) -> None:
    monkeypatch.setattr(oci_cli_lint.oci_cli_help, "get_help", lambda _path, refresh: ("", ""))
    errors = oci_cli_lint.lint_command("oci_cli iam user list", action=False)
    assert any("unavailable" in error for error in errors)
    try:
        oci_cli_lint.command_shape(["iam", "user", "list"])
    except RuntimeError as exc:
        assert "unavailable" in str(exc)
    else:
        raise AssertionError("command_shape should fail without help")


def test_plan_unknown_fields_invalid_types_and_non_oracle_source() -> None:
    plan = _plan("oci_cli iam user list")
    plan["unknown"] = True
    plan["schema_version"] = 2
    plan["context"] = ""
    plan["risk"] = "extreme"
    plan["sources"] = ["https://example.com/not-authoritative"]
    errors = oci_cli_lint.lint_plan(plan, validate_help=False)
    for fragment in ("unknown", "schema_version", "context", "risk", "docs.oracle.com"):
        assert any(fragment in error for error in errors)


def test_shell_file_main_and_parse_errors(tmp_path: pathlib.Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(oci_cli_lint, "command_shape", lambda _path: SHAPE)
    shell = tmp_path / "plan.sh"
    shell.write_text(
        "# source https://docs.oracle.com/en-us/iaas/Content/APIGateway/Concepts/apigatewayconcepts.htm\n"
        "oci_cli api-gateway gateway list --compartment-id x\n"
        "run_action --risk additive --compartment x --description create -- "
        "oci_cli api-gateway gateway create --compartment-id x --display-name demo\n"
        "oci_cli api-gateway gateway list --compartment-id x\n"
        "# rollback through Terraform\n",
        encoding="utf-8",
    )
    assert oci_cli_lint.main([str(shell)]) == 0
    capsys.readouterr()

    malformed = tmp_path / "bad.json"
    malformed.write_text("{bad", encoding="utf-8")
    assert oci_cli_lint.main([str(malformed)]) == 2
    assert "cannot parse" in capsys.readouterr().err

    missing = tmp_path / "missing.json"
    assert oci_cli_lint.main([str(missing)]) == 2
    link = tmp_path / "link.json"
    link.symlink_to(malformed)
    assert oci_cli_lint.main([str(link)]) == 2

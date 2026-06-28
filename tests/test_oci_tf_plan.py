"""Terraform plan safety and starter generation contracts."""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import oci_tf_plan  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_plan_summary_counts_actions_without_rendering_values() -> None:
    plan = {
        "resource_changes": [
            {
                "address": "oci_core_vcn.private",
                "type": "oci_core_vcn",
                "change": {"actions": ["create"], "after": {"cidr": "secret-value"}},
            },
            {
                "address": "oci_core_subnet.public",
                "type": "oci_core_subnet",
                "change": {
                    "actions": ["delete", "create"],
                    "after": {"prohibit_public_ip_on_vnic": False},
                },
            },
            {
                "address": "oci_vault_secret.credential",
                "type": "oci_vault_secret",
                "change": {"actions": ["update"], "after": {"content": "never-print"}},
            },
        ]
    }
    summary = oci_tf_plan.analyze(plan)
    assert summary["counts"] == {"create": 1, "update": 1, "replace": 1, "delete": 0}
    assert summary["public_exposure"] == ["oci_core_subnet.public"]
    assert summary["secret_bearing"] == ["oci_vault_secret.credential"]
    assert oci_tf_plan.action_risk(summary) == "destructive"
    rendered = json.dumps(summary)
    assert "secret-value" not in rendered
    assert "never-print" not in rendered


def test_scaffold_is_secret_safe_and_empty_destination_only(tmp_path: pathlib.Path) -> None:
    destination = tmp_path / "starter"
    first = subprocess.run(
        ["bash", str(ROOT / "scripts" / "oci_tf.sh"), "scaffold", str(destination)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr
    for name in ("versions.tf", "provider.tf", "variables.tf", "outputs.tf", ".gitignore", "terraform.tfvars.example"):
        assert (destination / name).is_file()
    ignored = (destination / ".gitignore").read_text(encoding="utf-8")
    for pattern in ("*.tfstate*", "*.tfplan", ".terraform/", "*.zip", "*wallet*"):
        assert pattern in ignored
    assert "<COMPARTMENT_OCID>" in (destination / "terraform.tfvars.example").read_text(encoding="utf-8")

    second = subprocess.run(
        ["bash", str(ROOT / "scripts" / "oci_tf.sh"), "scaffold", str(destination)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert second.returncode != 0
    assert "empty" in second.stderr.lower()


def test_plan_identity_changes_with_plan_bytes(tmp_path: pathlib.Path) -> None:
    plan = tmp_path / "reviewed.tfplan"
    plan.write_bytes(b"first")
    first = oci_tf_plan.plan_identity(plan)
    plan.write_bytes(b"second")
    second = oci_tf_plan.plan_identity(plan)
    assert first != second
    assert first.startswith("tfplan-")


def test_record_and_verify_bind_bytes_and_context(tmp_path: pathlib.Path) -> None:
    plan = tmp_path / "reviewed.tfplan"
    plan.write_bytes(b"reviewed")
    plan.chmod(0o600)
    recorded = oci_tf_plan.record(plan, "ctx-a", action_risk="additive")
    assert recorded["plan_identity"] == oci_tf_plan.plan_identity(plan)
    assert oci_tf_plan.verify(plan, "ctx-a") == (True, recorded["plan_identity"])
    assert oci_tf_plan.verify(plan, "ctx-a", field="action_risk") == (True, "additive")
    assert oci_tf_plan.verify(plan, "ctx-a", expected_kind="destroy") == (
        False,
        "reviewed plan kind mismatch",
    )
    assert oci_tf_plan.verify(plan, "ctx-b") == (False, "review context mismatch")
    plan.write_bytes(b"changed")
    assert oci_tf_plan.verify(plan, "ctx-a") == (False, "reviewed plan identity mismatch")

    (tmp_path / "reviewed.tfplan.review.json").write_text("not-json", encoding="utf-8")
    assert oci_tf_plan.verify(plan, "ctx-a") == (False, "review sidecar invalid")
    (tmp_path / "reviewed.tfplan.review.json").unlink()
    assert oci_tf_plan.verify(plan, "ctx-a") == (False, "review sidecar missing")


def test_analyze_handles_delete_noop_and_non_dict_entries() -> None:
    summary = oci_tf_plan.analyze({"resource_changes": [
        None,
        {"address": "gone", "type": "oci_core_vcn", "change": {"actions": ["delete"]}},
        {"address": "same", "type": "oci_core_vcn", "change": {"actions": ["no-op"], "after": None}},
        {"address": "public", "type": "oci_apigateway_gateway", "change": {"actions": ["create"], "after": {"endpoint_type": "PUBLIC"}}},
    ]})
    assert summary["counts"]["delete"] == 1
    assert summary["counts"]["create"] == 1
    assert summary["public_exposure"] == ["public"]


def test_cli_analyze_record_verify_and_errors(tmp_path: pathlib.Path, monkeypatch, capsys) -> None:
    json_path = tmp_path / "plan.json"
    json_path.write_text('{"resource_changes": []}', encoding="utf-8")
    assert oci_tf_plan.main(["analyze", str(json_path)]) == 0
    assert '"counts"' in capsys.readouterr().out
    json_path.write_text("bad", encoding="utf-8")
    assert oci_tf_plan.main(["analyze", str(json_path)]) == 2
    assert "invalid" in capsys.readouterr().err

    plan = tmp_path / "plan.bin"
    plan.write_bytes(b"plan")
    plan.chmod(0o600)
    assert oci_tf_plan.main([
        "record", str(plan), "--context-hash", "ctx", "--risk", "additive",
    ]) == 0
    capsys.readouterr()
    assert oci_tf_plan.main(["verify", str(plan), "--context-hash", "ctx"]) == 0
    assert "tfplan-" in capsys.readouterr().out
    assert oci_tf_plan.main([
        "verify", str(plan), "--context-hash", "ctx", "--field", "action-risk",
    ]) == 0
    assert capsys.readouterr().out.strip() == "additive"
    assert oci_tf_plan.main(["verify", str(plan), "--context-hash", "wrong"]) == 1
    assert "mismatch" in capsys.readouterr().err
    assert oci_tf_plan.main(["verify", str(tmp_path / "missing"), "--context-hash", "ctx"]) == 2

    insecure = tmp_path / "insecure.tfplan"
    insecure.write_bytes(b"plan")
    insecure.chmod(0o644)
    assert oci_tf_plan.main(["record", str(insecure), "--context-hash", "ctx"]) == 2
    assert "0600" in capsys.readouterr().err

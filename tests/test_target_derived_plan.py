"""Contracts for target-derived, offline architecture and telemetry plans."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def planner():
    path = ROOT / "scripts" / "target_derived_plan.py"
    spec = importlib.util.spec_from_file_location("target_derived_plan", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inventory() -> dict[str, object]:
    return {
        "schema_version": 1,
        "function_application_architecture": "aarch64",
        "oke_node_architectures": ["aarch64", "x86_64"],
        "image_manifest_architectures": ["aarch64"],
        "flow_logs": {
            "subnet_roles": ["node", "api-endpoint", "load-balancer", "pod-network"],
            "bound_subnet_roles": ["node"],
            "capture_scope": "all",
            "sampling": "include",
            "retention_days": 14,
            "cost_acknowledged": True,
        },
    }


def test_target_inventory_derives_image_and_flow_log_plan_without_provider_io(planner) -> None:
    plan = planner.build_plan(_inventory())

    assert plan["offline"] is True
    assert plan["provider_contacted"] is False
    assert plan["image"]["function_required_architectures"] == ["aarch64"]
    assert plan["image"]["oke_required_architectures"] == ["aarch64", "x86_64"]
    assert plan["image"]["publish_strategy"] == "multi-architecture-required"
    assert plan["image"]["missing_manifest_architectures"] == ["x86_64"]
    assert plan["flow_logs"]["target_subnet_count"] == 4
    assert plan["flow_logs"]["missing_subnet_roles"] == [
        "api-endpoint", "load-balancer", "pod-network"
    ]
    assert plan["flow_logs"]["retention_days"] == 14
    assert plan["flow_logs"]["generic_cleanup"] == "none"
    assert plan["flow_logs"]["approval_required_before_mutation"] is True


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("function_application_architecture", "arm64", "architecture"),
        ("image_manifest_architectures", ["x86_64", "x86_64"], "unique"),
        ("flow_logs", {"subnet_roles": ["node"], "bound_subnet_roles": ["node"], "capture_scope": "all", "sampling": "include", "retention_days": 0, "cost_acknowledged": True}, "retention"),
    ],
)
def test_target_inventory_fails_closed_on_unsafe_or_incomplete_values(
    planner, field: str, value: object, message: str
) -> None:
    inventory = _inventory()
    inventory[field] = value
    with pytest.raises(planner.PlanError, match=message):
        planner.build_plan(inventory)


def test_target_inventory_rejects_provider_identifiers_and_generic_delete(planner) -> None:
    inventory = _inventory()
    inventory["flow_logs"] = {
        **inventory["flow_logs"],  # type: ignore[dict-item]
        "subnet_roles": ["oci" + "d1.subnet.oc1..synthetic"],
    }
    with pytest.raises(planner.PlanError, match="role"):
        planner.build_plan(inventory)


@pytest.mark.parametrize(
    "field,value,message",
    [
        ("oke_node_architectures", [], "non-empty"),
        ("flow_logs", {"subnet_roles": ["node"], "bound_subnet_roles": ["node"]}, "incomplete"),
        ("flow_logs", {"subnet_roles": ["node"], "bound_subnet_roles": ["api-endpoint"], "capture_scope": "all", "sampling": "include", "retention_days": 14, "cost_acknowledged": True}, "must occur"),
        ("flow_logs", {"subnet_roles": ["node"], "bound_subnet_roles": ["node"], "capture_scope": "invalid", "sampling": "include", "retention_days": 14, "cost_acknowledged": True}, "capture scope"),
        ("flow_logs", {"subnet_roles": ["node"], "bound_subnet_roles": ["node"], "capture_scope": "all", "sampling": "include", "retention_days": 14, "cost_acknowledged": False}, "cost acknowledgement"),
    ],
)
def test_target_inventory_rejects_incomplete_or_unapproved_plan_inputs(
    planner, field: str, value: object, message: str
) -> None:
    inventory = _inventory()
    inventory[field] = value
    with pytest.raises(planner.PlanError, match=message):
        planner.build_plan(inventory)


def test_target_plan_cli_writes_a_pretty_metadata_only_plan(
    planner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    input_path = tmp_path / "inventory.json"
    input_path.write_text(json.dumps(_inventory()), encoding="utf-8")

    assert planner.main(["--inventory", str(input_path), "--pretty"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["offline"] is True
    assert payload["provider_contacted"] is False


def test_target_plan_cli_rejects_missing_or_symlinked_inventory(
    planner, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.json"
    assert planner.main(["--inventory", str(missing)]) == 1
    assert "regular file" in capsys.readouterr().err

    source = tmp_path / "source.json"
    source.write_text(json.dumps(_inventory()), encoding="utf-8")
    linked = tmp_path / "linked.json"
    linked.symlink_to(source)
    assert planner.main(["--inventory", str(linked)]) == 1
    assert "regular file" in capsys.readouterr().err

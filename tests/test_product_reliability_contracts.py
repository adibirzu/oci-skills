"""Acceptance contracts for product requirements REQ-43 through REQ-52."""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
CONTRACT_ROOT = ROOT / "docs/product/contracts"
PRD_ROOT = ROOT / "docs/product/prds"
PRDS = {
    "REQ-43": "req-43-change-set-manifest.md",
    "REQ-44": "req-44-exception-policy.md",
    "REQ-45": "req-45-waiver-expiry.md",
    "REQ-46": "req-46-dependency-integrity.md",
    "REQ-47": "req-47-deterministic-output.md",
    "REQ-48": "req-48-performance-budget.md",
    "REQ-49": "req-49-network-isolation.md",
    "REQ-50": "req-50-contract-backup-restore.md",
    "REQ-51": "req-51-release-rollback.md",
    "REQ-52": "req-52-end-of-life-policy.md",
}
CONTRACTS = {
    "change-set-manifest.json",
    "exception-policy.json",
    "waiver-expiry.json",
    "dependency-integrity.json",
    "deterministic-output.json",
    "performance-budget.json",
    "network-isolation.json",
    "contract-backup-restore.json",
    "release-rollback.json",
    "end-of-life-policy.json",
}


def _json(name: str) -> dict:
    return json.loads((CONTRACT_ROOT / name).read_text(encoding="utf-8"))


def _validator():
    path = ROOT / "scripts/product_contracts.py"
    spec = importlib.util.spec_from_file_location("product_contracts_reliability", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_prds_ledgers_and_contract_inventory_extend_through_req_52() -> None:
    for requirement, filename in PRDS.items():
        text = (PRD_ROOT / filename).read_text(encoding="utf-8")
        assert text.startswith(f"# {requirement}")
        for heading in (
            "## User journey", "## Product requirement", "## Acceptance criteria",
            "## Architecture impact", "## Associated tasks", "## Verification",
        ):
            assert heading in text
    product = (ROOT / "docs/product/oci-skills-v2-prd.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs/plans/oci-skills-v2.md").read_text(encoding="utf-8")
    for number in range(1, 53):
        assert f"REQ-{number:02d}" in product and f"REQ-{number:02d}" in plan
    assert CONTRACTS <= {path.name for path in CONTRACT_ROOT.glob("*.json")}
    assert len(list(CONTRACT_ROOT.glob("*.json"))) == 37


def test_change_manifest_exceptions_and_waivers_fail_closed() -> None:
    manifest = _json("change-set-manifest.json")
    assert {"change_id", "classification", "owners", "artifacts", "tests"} <= set(manifest["required_fields"])
    assert manifest["path_ordering"] == "bytewise"
    exceptions = _json("exception-policy.json")
    assert exceptions["security_exceptions_allowed"] is False
    assert exceptions["default"] == "deny"
    waiver = _json("waiver-expiry.json")
    assert waiver["expiry_required"] is True
    assert waiver["automatic_renewal"] is False
    assert waiver["expired_behavior"] == "block"


def test_integrity_determinism_and_budget_contracts_are_bounded() -> None:
    integrity = _json("dependency-integrity.json")
    assert integrity["unpinned_dependencies"] == "reject"
    assert integrity["checksum_required"] is True
    deterministic = _json("deterministic-output.json")
    assert deterministic["sort_keys"] is True
    assert deterministic["timestamps_in_validation"] is False
    budget = _json("performance-budget.json")
    assert budget["network_calls"] == 0
    assert budget["validator_seconds"] > 0
    assert budget["failure"] == "block-release"


def test_network_backup_rollback_and_eol_are_safe() -> None:
    isolation = _json("network-isolation.json")
    assert isolation["contract_validation"] == "offline"
    assert isolation["live_oci_in_tests"] is False
    backup = _json("contract-backup-restore.json")
    assert backup["source_of_truth"] == "version-control"
    assert backup["restore_requires_validation"] is True
    rollback = _json("release-rollback.json")
    assert rollback["rollback_requires_review"] is True
    assert rollback["safety_gates_bypassable"] is False
    eol = _json("end-of-life-policy.json")
    assert eol["removal"] == "major-release-only"
    assert eol["migration_path_required"] is True


def test_governance_graphs_and_validator_expand_through_req_52() -> None:
    expected = {f"REQ-{number:02d}" for number in range(23, 53)}
    assert {item["requirement"] for item in _json("user-journeys.json")["journeys"]} == expected
    assert {item["id"] for item in _json("requirement-dependencies.json")["requirements"]} == expected
    validator = _validator()
    result = validator.validate_repository(ROOT)
    assert result["requirements"] == 52
    assert result["new_prds"] == 40
    assert result["contracts"] == 37
    assert result["journeys"] == 30


def test_validator_rejects_unsafe_reliability_contracts() -> None:
    validator = _validator()
    with pytest.raises(validator.ContractError, match="exception"):
        validator._validate_reliability_contracts(
            {
                "exception-policy.json": {
                    "security_exceptions_allowed": True,
                    "default": "allow",
                }
            }
        )


def test_architecture_documents_reliability_control_planes() -> None:
    architecture = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    for heading in (
        "## Change and exception plane",
        "## Integrity and determinism plane",
        "## Isolation and recovery plane",
        "## Rollback and end-of-life plane",
    ):
        assert heading in architecture


def test_public_docs_publish_the_consolidated_inventory_and_reliability_controls() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    quickstart = (ROOT / "docs/QUICKSTART.md").read_text(encoding="utf-8")
    architecture = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs/plans/oci-skills-v2.md").read_text(encoding="utf-8")

    for document in (readme, quickstart, architecture):
        assert "52 requirements" in document
        assert "37 contracts" in document
        assert "30 journeys" in document
    assert "change-set manifests" in readme
    assert "dependency integrity" in quickstart
    assert "40 detailed PRDs" in architecture
    assert "REQ-43 through REQ-52" in plan

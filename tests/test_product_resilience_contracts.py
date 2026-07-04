"""Acceptance contracts for product requirements REQ-33 through REQ-42."""
from __future__ import annotations

import importlib.util
import json
import pathlib

import pytest


ROOT = pathlib.Path(__file__).resolve().parent.parent
PRD_ROOT = ROOT / "docs" / "product" / "prds"
CONTRACT_ROOT = ROOT / "docs" / "product" / "contracts"
EXPECTED_PRDS = {
    "REQ-33": "req-33-change-classification.md",
    "REQ-34": "req-34-schema-evolution.md",
    "REQ-35": "req-35-accountability-matrix.md",
    "REQ-36": "req-36-evidence-retention.md",
    "REQ-37": "req-37-environment-parity.md",
    "REQ-38": "req-38-recovery-playbooks.md",
    "REQ-39": "req-39-architecture-invariants.md",
    "REQ-40": "req-40-documentation-freshness.md",
    "REQ-41": "req-41-release-attestation.md",
    "REQ-42": "req-42-maintenance-policy.md",
}
NEW_CONTRACTS = {
    "change-classification.json",
    "schema-evolution.json",
    "accountability-matrix.json",
    "evidence-retention.json",
    "environment-parity.json",
    "recovery-playbooks.json",
    "architecture-invariants.json",
    "documentation-freshness.json",
    "release-attestation.json",
    "maintenance-policy.json",
}


def _json(name: str) -> dict:
    return json.loads((CONTRACT_ROOT / name).read_text(encoding="utf-8"))


def _load_validator():
    path = ROOT / "scripts" / "product_contracts.py"
    spec = importlib.util.spec_from_file_location("product_contracts_resilience", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_next_ten_prds_and_ledgers_cover_req_33_through_req_42() -> None:
    for requirement, filename in EXPECTED_PRDS.items():
        text = (PRD_ROOT / filename).read_text(encoding="utf-8")
        assert text.startswith(f"# {requirement}")
        for heading in (
            "## User journey",
            "## Product requirement",
            "## Acceptance criteria",
            "## Architecture impact",
            "## Associated tasks",
            "## Verification",
        ):
            assert heading in text
    product = (ROOT / "docs/product/oci-skills-v2-prd.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs/plans/oci-skills-v2.md").read_text(encoding="utf-8")
    for number in range(1, 53):
        assert f"REQ-{number:02d}" in product
        assert f"REQ-{number:02d}" in plan
    for number in range(33, 43):
        assert f"PROD-{number}" in plan


def test_contract_inventory_and_governance_graphs_expand_through_req_42() -> None:
    names = {path.name for path in CONTRACT_ROOT.glob("*.json")}
    assert len(names) == 37
    assert NEW_CONTRACTS <= names
    registry = _json("contract-schema-registry.json")
    assert set(registry["contracts"]) == names - {"contract-schema-registry.json"}
    expected = {f"REQ-{number:02d}" for number in range(23, 53)}
    assert {item["requirement"] for item in _json("user-journeys.json")["journeys"]} == expected
    assert {item["id"] for item in _json("requirement-dependencies.json")["requirements"]} == expected
    assert {item["requirement"] for item in _json("source-provenance.json")["records"]} == expected
    assert {item["id"] for item in _json("change-impact.json")["requirements"]} == expected


def test_change_classification_and_schema_evolution_are_major_safe() -> None:
    classification = _json("change-classification.json")
    assert set(classification["classes"]) == {"editorial", "additive", "breaking"}
    assert classification["classes"]["breaking"]["minimum_release"] == "next-major"
    assert classification["default"] == "breaking"
    assert classification["unknown_change"] == "fail-closed"

    evolution = _json("schema-evolution.json")
    assert evolution["current_schema_version"] == 1
    assert evolution["backward_compatibility"] == "required-within-major"
    assert evolution["unknown_version"] == "reject"
    assert evolution["migration_required_for_breaking"] is True


def test_accountability_and_retention_contracts_have_safe_owners_and_boundaries() -> None:
    accountability = _json("accountability-matrix.json")
    entries = accountability["responsibilities"]
    assert len({entry["id"] for entry in entries}) == len(entries)
    assert all(entry["accountable"] and entry["responsible"] for entry in entries)
    assert {"contracts", "security", "distribution", "release", "documentation"} <= {
        entry["id"] for entry in entries
    }

    retention = _json("evidence-retention.json")
    assert retention["secrets"] == "never-retain"
    assert retention["raw_provider_content"] == "local-ephemeral-only"
    assert retention["committed_evidence"] == "metadata-only"
    assert retention["deletion_verification"] == "required"


def test_environment_parity_and_recovery_playbooks_are_executable_contracts() -> None:
    parity = _json("environment-parity.json")
    assert set(parity["harnesses"]) == {"claude", "codex", "gemini", "antigravity"}
    assert {"skills", "contracts", "safety", "routing"} <= set(parity["invariants"])
    assert parity["live_oci_required"] is False

    playbooks = _json("recovery-playbooks.json")["playbooks"]
    assert {"contract-validation", "install-drift", "incomplete-evaluation", "redaction-failure"} <= {
        item["id"] for item in playbooks
    }
    for item in playbooks:
        assert item["detection"] and item["containment"]
        assert item["recovery"] and item["verification"]
        assert item["tests"]


def test_architecture_invariants_and_documentation_freshness_fail_closed() -> None:
    invariants = _json("architecture-invariants.json")
    required = {
        "terraform-single-owner",
        "context-bound-mutations",
        "no-secrets-on-argv",
        "offline-contract-validation",
        "independent-release-evidence",
    }
    assert required <= {item["id"] for item in invariants["invariants"]}
    assert all(item["enforcement"] and item["tests"] for item in invariants["invariants"])

    freshness = _json("documentation-freshness.json")
    assert freshness["official_sources"] == "oracle-docs-index"
    assert freshness["broken_link_policy"] == "block-release"
    assert freshness["unverified_claim_policy"] == "reject"
    assert freshness["review_required_on_contract_change"] is True


def test_attestation_and_maintenance_never_self_certify() -> None:
    attestation = _json("release-attestation.json")
    assert attestation["self_attestation_allowed"] is False
    assert attestation["raw_content_included"] is False
    assert {"contract_sha256", "install_manifest_sha256", "forward_evidence_sha256"} <= set(
        attestation["required_fields"]
    )
    assert attestation["external_signature_required"] is True

    maintenance = _json("maintenance-policy.json")
    assert maintenance["security_critical"]["release_blocking"] is True
    assert maintenance["breaking_change_window"] == "major-release-only"
    assert maintenance["stale_owner_policy"] == "block-change"
    assert maintenance["live_oci_in_ci"] is False


def test_validator_reports_42_requirements_27_contracts_and_20_journeys() -> None:
    validator = _load_validator()
    result = validator.validate_repository(ROOT)
    assert result["requirements"] == 52
    assert result["new_prds"] == 40
    assert result["contracts"] == 37
    assert result["journeys"] == 30
    assert result["safety_cases"] == 8
    report = validator.build_report(ROOT)
    assert report["requirements"] == 52
    assert report["contract_count"] == 37
    assert report["journey_count"] == 30
    assert report["self_certified"] is False


def test_validator_rejects_unsafe_resilience_contracts() -> None:
    validator = _load_validator()
    contracts = {
        "change-classification.json": {
            "classes": {"breaking": {"minimum_release": "patch"}},
            "default": "additive",
            "unknown_change": "allow",
        },
        "schema-evolution.json": {
            "current_schema_version": 1,
            "backward_compatibility": "optional",
            "unknown_version": "accept",
            "migration_required_for_breaking": False,
        },
    }
    with pytest.raises(validator.ContractError, match="breaking"):
        validator._validate_resilience_contracts(ROOT, contracts)


def test_architecture_documents_resilience_and_maintenance_planes() -> None:
    architecture = (ROOT / "docs/ARCHITECTURE.md").read_text(encoding="utf-8")
    for heading in (
        "## Contract evolution plane",
        "## Accountability and retention plane",
        "## Recovery and parity plane",
        "## Attestation and maintenance plane",
    ):
        assert heading in architecture

"""Acceptance contracts for the foundational REQ-13 through REQ-22 tranche."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parent.parent
PRD_ROOT = ROOT / "docs" / "product" / "prds"
CONTRACT_ROOT = ROOT / "docs" / "product" / "contracts"
EXPECTED_PRDS = {
    "REQ-13": "req-13-application-workflow-evidence.md",
    "REQ-14": "req-14-deterministic-workflow-evaluation.md",
    "REQ-15": "req-15-capability-catalog.md",
    "REQ-16": "req-16-routing-precedence.md",
    "REQ-17": "req-17-evidence-envelope.md",
    "REQ-18": "req-18-architecture-traceability.md",
    "REQ-19": "req-19-distribution-reproducibility.md",
    "REQ-20": "req-20-redaction-scope.md",
    "REQ-21": "req-21-release-readiness.md",
    "REQ-22": "req-22-compatibility-deprecation.md",
}
EXPECTED_CONTRACTS = {
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
    "contract-schema-registry.json",
    "user-journeys.json",
    "requirement-dependencies.json",
    "verification-registry.json",
    "source-provenance.json",
    "change-impact.json",
    "install-manifest.json",
    "release-state-machine.json",
    "safety-cases.json",
    "migration-readiness.json",
    "capability-catalog.json",
    "routing-precedence.json",
    "architecture-traceability.json",
    "distribution-contract.json",
    "redaction-contract.json",
    "release-gates.json",
    "compatibility-contract.json",
}


def _json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_validator():
    path = ROOT / "scripts" / "product_contracts.py"
    spec = importlib.util.spec_from_file_location("product_contracts", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_next_ten_prds_define_user_journey_acceptance_tasks_and_architecture() -> None:
    for requirement, filename in EXPECTED_PRDS.items():
        text = (PRD_ROOT / filename).read_text(encoding="utf-8")
        assert f"# {requirement}" in text
        for heading in (
            "## User journey",
            "## Product requirement",
            "## Acceptance criteria",
            "## Architecture impact",
            "## Associated tasks",
            "## Verification",
        ):
            assert heading in text


def test_main_prd_and_delivery_plan_trace_all_fifty_two_requirements() -> None:
    product = (ROOT / "docs" / "product" / "oci-skills-v2-prd.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs" / "plans" / "oci-skills-v2.md").read_text(encoding="utf-8")
    for number in range(1, 53):
        requirement = f"REQ-{number:02d}"
        assert requirement in product
        assert requirement in plan
    for number in range(13, 53):
        assert f"PROD-{number}" in plan


def test_contract_documents_are_versioned_and_parseable() -> None:
    assert {path.name for path in CONTRACT_ROOT.glob("*.json")} == EXPECTED_CONTRACTS
    for filename in EXPECTED_CONTRACTS:
        data = _json(CONTRACT_ROOT / filename)
        assert data["schema_version"] == 1


def test_capability_catalog_matches_canonical_skill_inventory() -> None:
    catalog = _json(CONTRACT_ROOT / "capability-catalog.json")
    actual = {path.parent.name for path in ROOT.glob("skills/*/SKILL.md")}
    declared = {entry["skill"] for entry in catalog["capabilities"]}
    assert declared == actual
    assert all(entry["owner"] and entry["reference"] for entry in catalog["capabilities"])


def test_routing_distribution_release_and_compatibility_contracts_are_complete() -> None:
    routing = _json(CONTRACT_ROOT / "routing-precedence.json")
    assert len(routing["precedence_rules"]) >= 6
    assert all(rule["positive_owner"] and rule["negative_owner"] for rule in routing["precedence_rules"])

    distribution = _json(CONTRACT_ROOT / "distribution-contract.json")
    assert set(distribution["harnesses"]) == {"claude", "codex", "gemini", "antigravity"}
    assert all(item["adapter"] and item["install_target"] for item in distribution["harnesses"].values())

    release = _json(CONTRACT_ROOT / "release-gates.json")
    assert release["external_evidence"]["self_certification_allowed"] is False
    assert release["external_evidence"]["minimum_pass_rate"] >= 0.9

    compatibility = _json(CONTRACT_ROOT / "compatibility-contract.json")
    assert compatibility["deprecated"]["run_mutating"]["replacement"] == "run_action"
    assert compatibility["ownership"]["durable_resources"] == "terraform"


def test_evidence_schemas_reject_secrets_and_require_verification() -> None:
    workflow = _json(ROOT / "schemas" / "application-workflow.schema.json")
    evidence = _json(ROOT / "schemas" / "evidence-envelope.schema.json")
    assert {"classification", "tests", "review", "verification"} <= set(workflow["required"])
    assert workflow["properties"]["raw_content"]["const"] is False
    assert {"finding", "evidence", "action", "verification", "rollback"} <= set(evidence["required"])
    assert evidence["properties"]["secret_values"]["maxItems"] == 0


def test_product_contract_validator_and_report_are_deterministic() -> None:
    validator = _load_validator()
    first = validator.validate_repository(ROOT)
    second = validator.validate_repository(ROOT)
    assert first == second
    assert first["valid"] is True
    assert first["requirements"] == 52
    assert first["contracts"] == 37
    assert first["capabilities"] == 26
    report = validator.build_report(ROOT)
    assert report["external_evidence_complete"] is False
    assert report["self_certified"] is False
    assert "raw_content" not in json.dumps(report).lower()


def test_product_contract_cli_and_ci_wiring() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "product_contracts.py"), "validate"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert _json_from_stdout(result.stdout)["valid"] is True
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python3 scripts/product_contracts.py validate" in ci


def _json_from_stdout(value: str) -> dict:
    return json.loads(value)


def test_architecture_documents_contract_and_evidence_planes() -> None:
    architecture = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    for heading in (
        "## Product contract plane",
        "## Application workflow evidence plane",
        "## Release readiness plane",
        "## Compatibility and distribution plane",
    ):
        assert heading in architecture


def test_validator_rejects_path_escape_invalid_json_and_unknown_schema(
    tmp_path: pathlib.Path,
) -> None:
    validator = _load_validator()
    with pytest.raises(validator.ContractError, match="escapes"):
        validator._repository_path(tmp_path, "../outside")

    invalid = tmp_path / "invalid.json"
    invalid.write_text("{broken", encoding="utf-8")
    with pytest.raises(validator.ContractError, match="invalid JSON"):
        validator._read_json(tmp_path, "invalid.json")

    unsupported = tmp_path / "unsupported.json"
    unsupported.write_text(json.dumps({"schema_version": 2}), encoding="utf-8")
    with pytest.raises(validator.ContractError, match="unsupported"):
        validator._read_json(tmp_path, "unsupported.json")


def test_validator_rejects_bad_routing_release_and_ownership() -> None:
    validator = _load_validator()
    catalog = {"capabilities": [{"skill": "known"}]}
    with pytest.raises(validator.ContractError, match="at least six"):
        validator._validate_routing(catalog, {"precedence_rules": []})
    rules = [
        {
            "id": f"rule-{number}",
            "positive_owner": "known",
            "negative_owner": "unknown" if number == 0 else "known",
        }
        for number in range(6)
    ]
    with pytest.raises(validator.ContractError, match="unknown routing owner"):
        validator._validate_routing(catalog, {"precedence_rules": rules})

    compatibility = {
        "deprecated": {"run_mutating": {"replacement": "unsafe"}},
        "ownership": {"durable_resources": "cli", "dual_ownership_allowed": True},
    }
    release = {
        "external_evidence": {
            "self_certification_allowed": True,
            "minimum_pass_rate": 0.5,
        }
    }
    migration = {
        "current_major": 2,
        "breaking_changes": "major-release-only",
        "deprecations": {
            "run_mutating": {
                "replacement": "unsafe",
                "earliest_removal_major": 3,
            }
        },
        "readiness_checks": [
            {"id": "check", "owner": "owner", "evidence": "evidence"},
        ],
    }
    with pytest.raises(validator.ContractError, match="self-certification"):
        validator._validate_release_and_migration(
            release,
            compatibility,
            migration,
        )


def test_product_contract_main_fails_closed_for_missing_root(
    tmp_path: pathlib.Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    validator = _load_validator()
    assert validator.main(["validate", "--root", str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error:" in captured.err

"""Acceptance contracts for the foundational REQ-23 through REQ-32 tranche."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re

import pytest


ROOT = pathlib.Path(__file__).resolve().parent.parent
PRD_ROOT = ROOT / "docs" / "product" / "prds"
CONTRACT_ROOT = ROOT / "docs" / "product" / "contracts"
EXPECTED_PRDS = {
    "REQ-23": "req-23-contract-schema-enforcement.md",
    "REQ-24": "req-24-user-journey-registry.md",
    "REQ-25": "req-25-requirement-dependency-graph.md",
    "REQ-26": "req-26-verification-command-registry.md",
    "REQ-27": "req-27-source-provenance.md",
    "REQ-28": "req-28-change-impact-mapping.md",
    "REQ-29": "req-29-reproducible-install-manifest.md",
    "REQ-30": "req-30-release-evidence-state-machine.md",
    "REQ-31": "req-31-adversarial-safety-cases.md",
    "REQ-32": "req-32-migration-readiness.md",
}
NEW_CONTRACTS = {
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
ALL_CONTRACTS = {
    "architecture-traceability.json",
    "capability-catalog.json",
    "compatibility-contract.json",
    "distribution-contract.json",
    "redaction-contract.json",
    "release-gates.json",
    "routing-precedence.json",
} | NEW_CONTRACTS
GOVERNANCE_REQUIREMENTS = {f"REQ-{number:02d}" for number in range(23, 53)}


def _json(path: pathlib.Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_validator():
    path = ROOT / "scripts" / "product_contracts.py"
    spec = importlib.util.spec_from_file_location("product_contracts_next", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_next_ten_prds_have_executable_product_structure() -> None:
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


def test_main_ledgers_trace_requirements_and_tasks_through_thirty_two() -> None:
    product = (ROOT / "docs" / "product" / "oci-skills-v2-prd.md").read_text(encoding="utf-8")
    plan = (ROOT / "docs" / "plans" / "oci-skills-v2.md").read_text(encoding="utf-8")
    for number in range(1, 53):
        requirement = f"REQ-{number:02d}"
        assert requirement in product
        assert requirement in plan
    for number in range(23, 33):
        assert f"PROD-{number}" in plan


def test_contract_inventory_and_schema_registry_are_complete() -> None:
    assert {path.name for path in CONTRACT_ROOT.glob("*.json")} == ALL_CONTRACTS
    registry = _json(CONTRACT_ROOT / "contract-schema-registry.json")
    assert registry["validation_mode"] == "offline-fail-closed"
    assert set(registry["contracts"]) == ALL_CONTRACTS - {"contract-schema-registry.json"}
    for filename, shape in registry["contracts"].items():
        assert shape["schema_version"] == 1
        assert shape["required_keys"]
        contract = _json(CONTRACT_ROOT / filename)
        assert set(shape["required_keys"]) <= set(contract)


def test_user_journeys_are_sanitized_and_acceptance_bound() -> None:
    contract = _json(CONTRACT_ROOT / "user-journeys.json")
    journeys = contract["journeys"]
    assert {item["requirement"] for item in journeys} == GOVERNANCE_REQUIREMENTS
    assert len({item["id"] for item in journeys}) == len(journeys)
    for item in journeys:
        assert item["actor"] and item["goal"] and item["outcome"]
        assert item["acceptance_tests"]
        assert all(test.startswith("tests/") for test in item["acceptance_tests"])
    assert "raw_prompt" not in json.dumps(contract).lower()


def test_requirement_dependency_graph_is_known_and_acyclic() -> None:
    contract = _json(CONTRACT_ROOT / "requirement-dependencies.json")
    graph = {item["id"]: item["depends_on"] for item in contract["requirements"]}
    assert set(graph) == GOVERNANCE_REQUIREMENTS
    known = {f"REQ-{number:02d}" for number in range(1, 53)}
    assert all(set(dependencies) <= known for dependencies in graph.values())

    visited: set[str] = set()
    active: set[str] = set()

    def visit(node: str) -> None:
        if node in active:
            pytest.fail(f"dependency cycle at {node}")
        if node in visited:
            return
        active.add(node)
        for dependency in graph.get(node, []):
            visit(dependency)
        active.remove(node)
        visited.add(node)

    for requirement in graph:
        visit(requirement)


def test_verification_registry_is_offline_declarative_and_shell_safe() -> None:
    contract = _json(CONTRACT_ROOT / "verification-registry.json")
    assert contract["executes_on_validate"] is False
    gates = contract["gates"]
    assert len({gate["id"] for gate in gates}) == len(gates)
    assert all(gate["required"] is True for gate in gates)
    forbidden = re.compile(r"[;&|><`$\n\r]")
    assert all(not forbidden.search(gate["command"]) for gate in gates)
    assert all(gate["evidence"] in {"exit-code", "coverage-summary", "metadata-report"} for gate in gates)


def test_source_provenance_is_local_or_oracle_official() -> None:
    contract = _json(CONTRACT_ROOT / "source-provenance.json")
    records = contract["records"]
    assert {record["requirement"] for record in records} == GOVERNANCE_REQUIREMENTS
    for record in records:
        assert record["authority"] in {"repository-contract", "oracle-official"}
        source = record["source"]
        if record["authority"] == "repository-contract":
            assert (ROOT / source).is_file()
        else:
            assert source.startswith("https://docs.oracle.com/")


def test_change_impact_maps_every_requirement_to_consumers() -> None:
    contract = _json(CONTRACT_ROOT / "change-impact.json")
    entries = contract["requirements"]
    assert {entry["id"] for entry in entries} == GOVERNANCE_REQUIREMENTS
    supported = {"claude", "codex", "gemini", "antigravity", "ci", "installer", "documentation"}
    for entry in entries:
        assert set(entry["consumers"]) <= supported
        assert {"ci", "documentation"} <= set(entry["consumers"])
        assert entry["artifacts"]


def test_install_manifest_matches_installer_and_excludes_sensitive_runtime_data() -> None:
    contract = _json(CONTRACT_ROOT / "install-manifest.json")
    assert contract["algorithm"] == "sha256-path-null-content"
    assert contract["ordering"] == "bytewise-path"
    assert set(contract["harnesses"]) == {"claude", "codex", "gemini", "antigravity"}
    payload = set(contract["payload"])
    assert {"skills", "references", "scripts", "schemas", "docs", "commands", "hooks", "evals"} <= payload
    exclusions = set(contract["exclusions"])
    assert {"*.tfstate", "*.tfplan", "*.tfvars", "*.pem", "*.key", "__pycache__"} <= exclusions
    installer = (ROOT / "install.sh").read_text(encoding="utf-8")
    assert "PAYLOAD=(" in installer
    assert all(item in installer for item in payload)


def test_release_state_machine_requires_independent_evidence_and_zero_safety_violations() -> None:
    contract = _json(CONTRACT_ROOT / "release-state-machine.json")
    states = {state["id"]: state for state in contract["states"]}
    assert contract["initial_state"] == "draft"
    assert contract["terminal_state"] == "release-ready"
    terminal = states["release-ready"]
    assert "independent-forward-evidence" in terminal["requires"]
    assert "zero-safety-violations" in terminal["requires"]
    assert contract["self_transition_allowed"] is False
    assert contract["validator_executes_transitions"] is False


def test_safety_cases_cover_fixed_refusals_and_test_evidence() -> None:
    contract = _json(CONTRACT_ROOT / "safety-cases.json")
    cases = contract["cases"]
    prefixes = {case["response_prefix"] for case in cases}
    assert {
        "Refused: secrets never go on argv",
        "Refused: unverified CLI flag",
        "Blocked: context mismatch",
        "Blocked: expired preflight",
        "Blocked: destructive non-TTY",
        "Blocked: unreviewed Terraform plan",
        "Blocked: dual ownership",
        "Rejected: dotenv is data-only",
    } <= prefixes
    assert len({case["id"] for case in cases}) == len(cases)
    assert all(case["owner"] and case["tests"] for case in cases)
    assert all(test.startswith("tests/") for case in cases for test in case["tests"])


def test_migration_readiness_preserves_v2_stability_and_major_only_removal() -> None:
    contract = _json(CONTRACT_ROOT / "migration-readiness.json")
    assert contract["current_major"] == 2
    assert contract["breaking_changes"] == "major-release-only"
    assert contract["deprecations"]["run_mutating"]["replacement"] == "run_action"
    assert contract["deprecations"]["run_mutating"]["earliest_removal_major"] == 3
    assert contract["readiness_checks"]
    assert all(item["owner"] and item["evidence"] for item in contract["readiness_checks"])


def test_validator_reports_expanded_contract_plane_deterministically() -> None:
    validator = _load_validator()
    first = validator.validate_repository(ROOT)
    second = validator.validate_repository(ROOT)
    assert first == second
    assert first == {
        "valid": True,
        "requirements": 52,
        "new_prds": 40,
        "contracts": 37,
        "capabilities": 22,
        "journeys": 30,
        "safety_cases": 8,
    }
    report = validator.build_report(ROOT)
    assert report["requirements"] == 52
    assert report["contract_count"] == 37
    assert report["journey_count"] == 30
    assert report["safety_case_count"] == 8
    assert report["external_evidence_complete"] is False
    assert report["self_certified"] is False


def test_validator_rejects_cycles_unsafe_commands_and_invalid_transitions() -> None:
    validator = _load_validator()
    with pytest.raises(validator.ContractError, match="cycle"):
        validator._validate_dependencies(
            {"requirements": [{"id": "REQ-23", "depends_on": ["REQ-24"]}, {"id": "REQ-24", "depends_on": ["REQ-23"]}]}
        )
    with pytest.raises(validator.ContractError, match="unsafe verification command"):
        validator._validate_verification(
            {"executes_on_validate": False, "gates": [{"id": "bad", "command": "pytest; curl bad", "required": True, "evidence": "exit-code"}]}
        )
    with pytest.raises(validator.ContractError, match="release-ready"):
        validator._validate_release_state_machine(
            {
                "initial_state": "draft",
                "terminal_state": "release-ready",
                "self_transition_allowed": False,
                "validator_executes_transitions": False,
                "states": [{"id": "draft", "requires": []}, {"id": "release-ready", "requires": ["tests"]}],
                "transitions": [{"from": "draft", "to": "release-ready"}],
            }
        )

    terminal_requirements = [
        "independent-forward-evidence",
        "minimum-pass-rate",
        "zero-safety-violations",
        "independent-review",
    ]
    cyclic = {
        "initial_state": "draft",
        "terminal_state": "release-ready",
        "self_transition_allowed": False,
        "validator_executes_transitions": False,
        "states": [
            {"id": "draft", "requires": []},
            {"id": "middle", "requires": []},
            {"id": "release-ready", "requires": terminal_requirements},
        ],
        "transitions": [
            {"from": "draft", "to": "middle"},
            {"from": "middle", "to": "draft"},
            {"from": "middle", "to": "release-ready"},
        ],
    }
    with pytest.raises(validator.ContractError, match="cycle"):
        validator._validate_release_state_machine(cyclic)

    disconnected = {
        **cyclic,
        "states": [
            {"id": "draft", "requires": []},
            {"id": "release-ready", "requires": terminal_requirements},
        ],
        "transitions": [],
    }
    with pytest.raises(validator.ContractError, match="unreachable"):
        validator._validate_release_state_machine(disconnected)


def test_architecture_documents_governance_and_supply_chain_planes() -> None:
    architecture = (ROOT / "docs" / "ARCHITECTURE.md").read_text(encoding="utf-8")
    for heading in (
        "## Contract governance plane",
        "## Verification and provenance plane",
        "## Distribution supply-chain plane",
        "## Release transition and migration plane",
    ):
        assert heading in architecture

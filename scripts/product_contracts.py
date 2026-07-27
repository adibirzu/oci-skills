#!/usr/bin/env python3
"""Validate versioned product contracts and report release-readiness metadata."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
PRD_ROOT = Path("docs/product/prds")
CONTRACT_ROOT = Path("docs/product/contracts")
PRD_FILES = {
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
OPERATIONAL_REQUIREMENTS = {f"REQ-{number:02d}" for number in range(23, 53)}
ALL_REQUIREMENTS = {f"REQ-{number:02d}" for number in range(1, 53)}
CONTRACT_FILES = {
    "accountability-matrix.json",
    "architecture-invariants.json",
    "architecture-traceability.json",
    "capability-catalog.json",
    "change-impact.json",
    "change-classification.json",
    "change-set-manifest.json",
    "compatibility-contract.json",
    "contract-schema-registry.json",
    "contract-backup-restore.json",
    "dependency-integrity.json",
    "deterministic-output.json",
    "distribution-contract.json",
    "documentation-freshness.json",
    "environment-parity.json",
    "end-of-life-policy.json",
    "exception-policy.json",
    "evidence-retention.json",
    "install-manifest.json",
    "migration-readiness.json",
    "maintenance-policy.json",
    "network-isolation.json",
    "performance-budget.json",
    "redaction-contract.json",
    "release-gates.json",
    "release-attestation.json",
    "release-rollback.json",
    "release-state-machine.json",
    "requirement-dependencies.json",
    "routing-precedence.json",
    "recovery-playbooks.json",
    "safety-cases.json",
    "source-provenance.json",
    "schema-evolution.json",
    "user-journeys.json",
    "verification-registry.json",
    "waiver-expiry.json",
}
PRD_HEADINGS = (
    "## User journey",
    "## Product requirement",
    "## Acceptance criteria",
    "## Architecture impact",
    "## Associated tasks",
    "## Verification",
)
SAFE_EVIDENCE = {"exit-code", "coverage-summary", "metadata-report"}
SUPPORTED_CONSUMERS = {
    "claude",
    "codex",
    "gemini",
    "antigravity",
    "ci",
    "installer",
    "documentation",
}
SAFETY_PREFIXES = {
    "Refused: secrets never go on argv",
    "Refused: unverified CLI flag",
    "Blocked: context mismatch",
    "Blocked: expired preflight",
    "Blocked: destructive non-TTY",
    "Blocked: unreviewed Terraform plan",
    "Blocked: dual ownership",
    "Rejected: dotenv is data-only",
}


class ContractError(ValueError):
    """A product contract is missing, unsafe, or inconsistent."""


def _repository_path(root: Path, relative: str | Path) -> Path:
    candidate = root / relative
    resolved_root = root.resolve()
    resolved = candidate.resolve(strict=False)
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ContractError(f"path escapes repository: {relative}")
    if candidate.is_symlink():
        raise ContractError(f"symlinked contract path is not allowed: {relative}")
    return candidate


def _read_text(root: Path, relative: str | Path) -> str:
    path = _repository_path(root, relative)
    if not path.is_file():
        raise ContractError(f"missing required file: {relative}")
    return path.read_text(encoding="utf-8")


def _read_json(root: Path, relative: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(_read_text(root, relative))
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON in {relative}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"contract must be a JSON object: {relative}")
    if value.get("schema_version") != 1:
        raise ContractError(f"unsupported schema version in {relative}")
    return value


def _validate_prds(root: Path) -> None:
    actual = {
        path.name
        for path in _repository_path(root, PRD_ROOT).glob("*.md")
        if path.is_file() and not path.is_symlink()
    }
    expected = set(PRD_FILES.values())
    if actual != expected:
        raise ContractError(
            f"PRD inventory mismatch: missing={sorted(expected - actual)}, "
            f"extra={sorted(actual - expected)}"
        )
    for requirement, filename in PRD_FILES.items():
        text = _read_text(root, PRD_ROOT / filename)
        if not text.startswith(f"# {requirement}"):
            raise ContractError(f"{filename} does not declare {requirement}")
        missing = [heading for heading in PRD_HEADINGS if heading not in text]
        if missing:
            raise ContractError(f"{filename} missing headings: {missing}")


def _validate_ledgers(root: Path) -> None:
    product = _read_text(root, "docs/product/oci-skills-v2-prd.md")
    plan = _read_text(root, "docs/plans/oci-skills-v2.md")
    product_ids = set(re.findall(r"REQ-\d{2}", product))
    plan_ids = set(re.findall(r"REQ-\d{2}", plan))
    if not ALL_REQUIREMENTS <= product_ids or not ALL_REQUIREMENTS <= plan_ids:
        raise ContractError("main PRD and delivery plan must trace REQ-01 through REQ-52")
    for number in range(13, 53):
        if f"PROD-{number}" not in plan:
            raise ContractError(f"delivery plan missing PROD-{number}")


def _validate_contract_inventory(root: Path) -> dict[str, dict[str, Any]]:
    directory = _repository_path(root, CONTRACT_ROOT)
    actual = {
        path.name
        for path in directory.glob("*.json")
        if path.is_file() and not path.is_symlink()
    }
    if actual != CONTRACT_FILES:
        raise ContractError(
            f"contract inventory mismatch: missing={sorted(CONTRACT_FILES - actual)}, "
            f"extra={sorted(actual - CONTRACT_FILES)}"
        )
    return {
        filename: _read_json(root, CONTRACT_ROOT / filename)
        for filename in sorted(CONTRACT_FILES)
    }


def _validate_schema_registry(contracts: dict[str, dict[str, Any]]) -> None:
    registry_name = "contract-schema-registry.json"
    registry = contracts[registry_name]
    if registry.get("validation_mode") != "offline-fail-closed":
        raise ContractError("contract schema validation must be offline and fail-closed")
    shapes = registry.get("contracts")
    if not isinstance(shapes, dict) or set(shapes) != CONTRACT_FILES - {registry_name}:
        raise ContractError("contract schema registry does not match contract inventory")
    for filename, shape in shapes.items():
        if not isinstance(shape, dict) or shape.get("schema_version") != 1:
            raise ContractError(f"invalid registered schema for {filename}")
        required = shape.get("required_keys")
        if not isinstance(required, list) or not required:
            raise ContractError(f"registered schema has no required keys: {filename}")
        missing = set(required) - set(contracts[filename])
        if missing:
            raise ContractError(f"{filename} missing registered keys: {sorted(missing)}")


def _validate_capabilities(root: Path, catalog: dict[str, Any]) -> int:
    entries = catalog.get("capabilities")
    if not isinstance(entries, list) or not entries:
        raise ContractError("capability catalog must contain capabilities")
    declared = [entry.get("skill") for entry in entries if isinstance(entry, dict)]
    actual = {
        path.parent.name
        for path in _repository_path(root, "skills").glob("*/SKILL.md")
        if path.is_file() and not path.is_symlink()
    }
    if len(declared) != len(set(declared)) or set(declared) != actual:
        raise ContractError("capability catalog does not match canonical skill inventory")
    for entry in entries:
        if not entry.get("owner") or not entry.get("reference"):
            raise ContractError(f"incomplete capability entry: {entry.get('skill')}")
        _read_text(root, entry["reference"])
    return len(entries)


def _validate_routing(catalog: dict[str, Any], routing: dict[str, Any]) -> None:
    skills = {entry["skill"] for entry in catalog["capabilities"]}
    rules = routing.get("precedence_rules")
    if not isinstance(rules, list) or len(rules) < 6:
        raise ContractError("routing contract must define at least six precedence rules")
    seen: set[str] = set()
    for rule in rules:
        identifier = rule.get("id")
        if not identifier or identifier in seen:
            raise ContractError("routing precedence IDs must be unique and non-empty")
        seen.add(identifier)
        for key in ("positive_owner", "negative_owner"):
            if rule.get(key) not in skills | {"owning domain"}:
                raise ContractError(f"unknown routing owner: {rule.get(key)}")


def _validate_traceability(root: Path, traceability: dict[str, Any]) -> None:
    entries = traceability.get("requirements")
    expected = set(PRD_FILES)
    actual = {entry.get("id") for entry in entries or [] if isinstance(entry, dict)}
    if actual != expected:
        raise ContractError("architecture traceability must cover REQ-13 through REQ-52")
    source_checkout = (root / "tests").is_dir()
    for entry in entries:
        for key in ("components", "tests", "docs"):
            paths = entry.get(key)
            if not isinstance(paths, list) or not paths:
                raise ContractError(f"{entry['id']} has no {key}")
            for relative in paths:
                if key != "tests" or source_checkout:
                    _read_text(root, relative)


def _validate_distribution(root: Path, distribution: dict[str, Any]) -> None:
    harnesses = distribution.get("harnesses")
    if set(harnesses or {}) != {"claude", "codex", "gemini", "antigravity"}:
        raise ContractError("distribution contract must cover four supported harnesses")
    source_checkout = (root / ".claude-plugin" / "plugin.json").is_file()
    for name, item in harnesses.items():
        if not item.get("install_target") or not item.get("adapter"):
            raise ContractError(f"{name} has no install target")
        if source_checkout:
            _read_text(root, item["adapter"])


def _validate_journeys(root: Path, contract: dict[str, Any]) -> int:
    journeys = contract.get("journeys")
    if not isinstance(journeys, list) or not journeys:
        raise ContractError("user-journey registry must contain journeys")
    identifiers = [item.get("id") for item in journeys if isinstance(item, dict)]
    requirements = {item.get("requirement") for item in journeys if isinstance(item, dict)}
    if len(identifiers) != len(set(identifiers)) or not all(identifiers):
        raise ContractError("user-journey IDs must be unique and non-empty")
    if requirements != OPERATIONAL_REQUIREMENTS:
        raise ContractError("user journeys must cover REQ-23 through REQ-52")
    if "raw_prompt" in json.dumps(contract).lower():
        raise ContractError("user journeys must not retain raw prompts")
    source_checkout = (root / "tests").is_dir()
    for item in journeys:
        if not all(item.get(key) for key in ("actor", "goal", "outcome")):
            raise ContractError(f"incomplete user journey: {item.get('id')}")
        tests = item.get("acceptance_tests")
        if not isinstance(tests, list) or not tests:
            raise ContractError(f"user journey has no acceptance tests: {item.get('id')}")
        if source_checkout:
            for relative in tests:
                _read_text(root, relative)
    return len(journeys)


def _validate_dependencies(contract: dict[str, Any]) -> dict[str, list[str]]:
    entries = contract.get("requirements")
    if not isinstance(entries, list) or not entries:
        raise ContractError("requirement dependency graph must contain requirements")
    graph: dict[str, list[str]] = {}
    for item in entries:
        identifier = item.get("id")
        dependencies = item.get("depends_on")
        if identifier in graph or identifier not in ALL_REQUIREMENTS:
            raise ContractError(f"duplicate or unknown dependency node: {identifier}")
        if not isinstance(dependencies, list) or any(dep not in ALL_REQUIREMENTS for dep in dependencies):
            raise ContractError(f"unknown dependency for {identifier}")
        if identifier in dependencies:
            raise ContractError(f"dependency cycle at {identifier}")
        graph[identifier] = dependencies

    visited: set[str] = set()
    active: set[str] = set()

    def visit(node: str) -> None:
        if node in active:
            raise ContractError(f"dependency cycle at {node}")
        if node in visited:
            return
        active.add(node)
        for dependency in graph.get(node, []):
            visit(dependency)
        active.remove(node)
        visited.add(node)

    for requirement in graph:
        visit(requirement)
    return graph


def _validate_verification(
    contract: dict[str, Any],
    release: dict[str, Any] | None = None,
) -> None:
    if contract.get("executes_on_validate") is not False:
        raise ContractError("verification registry must remain declarative")
    gates = contract.get("gates")
    if not isinstance(gates, list) or not gates:
        raise ContractError("verification registry must contain gates")
    identifiers: set[str] = set()
    forbidden = re.compile(r"[;&|><`$\n\r]")
    for gate in gates:
        identifier = gate.get("id")
        command = gate.get("command")
        if not identifier or identifier in identifiers:
            raise ContractError("verification gate IDs must be unique and non-empty")
        identifiers.add(identifier)
        if not isinstance(command, str) or forbidden.search(command):
            raise ContractError(f"unsafe verification command: {identifier}")
        if gate.get("required") is not True or gate.get("evidence") not in SAFE_EVIDENCE:
            raise ContractError(f"invalid verification gate: {identifier}")
    if release is not None:
        expected = {(gate["id"], gate["command"]) for gate in release["local_gates"]}
        actual = {(gate["id"], gate["command"]) for gate in gates}
        if actual != expected:
            raise ContractError("verification registry drifts from release gates")


def _validate_provenance(root: Path, contract: dict[str, Any]) -> None:
    records = contract.get("records")
    if not isinstance(records, list):
        raise ContractError("source provenance must contain records")
    requirements = [record.get("requirement") for record in records]
    if set(requirements) != OPERATIONAL_REQUIREMENTS or len(requirements) != len(set(requirements)):
        raise ContractError("source provenance must cover REQ-23 through REQ-52 once")
    for record in records:
        authority = record.get("authority")
        source = record.get("source")
        if authority == "repository-contract":
            _read_text(root, source)
        elif authority == "oracle-official":
            if not isinstance(source, str) or not source.startswith("https://docs.oracle.com/"):
                raise ContractError(f"untrusted Oracle source for {record.get('requirement')}")
        else:
            raise ContractError(f"unknown source authority: {authority}")


def _validate_change_impact(root: Path, contract: dict[str, Any]) -> None:
    entries = contract.get("requirements")
    if not isinstance(entries, list):
        raise ContractError("change impact must contain requirements")
    requirements = [entry.get("id") for entry in entries]
    if set(requirements) != OPERATIONAL_REQUIREMENTS or len(requirements) != len(set(requirements)):
        raise ContractError("change impact must cover REQ-23 through REQ-52 once")
    source_checkout = (root / ".claude-plugin" / "plugin.json").is_file()
    for entry in entries:
        consumers = set(entry.get("consumers") or [])
        if not {"ci", "documentation"} <= consumers or not consumers <= SUPPORTED_CONSUMERS:
            raise ContractError(f"invalid consumers for {entry.get('id')}")
        artifacts = entry.get("artifacts")
        if not isinstance(artifacts, list) or not artifacts:
            raise ContractError(f"change impact has no artifacts: {entry.get('id')}")
        for relative in artifacts:
            if relative != "install.sh" or source_checkout:
                _read_text(root, relative)


def _validate_install_manifest(
    root: Path,
    manifest: dict[str, Any],
    distribution: dict[str, Any],
) -> None:
    if manifest.get("algorithm") != "sha256-path-null-content":
        raise ContractError("install manifest has unsupported digest algorithm")
    if manifest.get("ordering") != "bytewise-path":
        raise ContractError("install manifest must use bytewise path ordering")
    if set(manifest.get("harnesses") or []) != set(distribution["harnesses"]):
        raise ContractError("install manifest harnesses drift from distribution")
    if manifest.get("payload") != distribution.get("required_payload"):
        raise ContractError("install manifest payload drifts from distribution")
    required_exclusions = {
        "__pycache__",
        "*.tfstate",
        "*.tfplan",
        "*.tfvars",
        "*.pem",
        "*.key",
    }
    if not required_exclusions <= set(manifest.get("exclusions") or []):
        raise ContractError("install manifest omits sensitive runtime exclusions")
    if manifest.get("symlinks_allowed") is not False:
        raise ContractError("install manifest must reject symlinks")
    if (root / "install.sh").is_file():
        installer = _read_text(root, "install.sh")
        if "PAYLOAD=(" not in installer:
            raise ContractError("installer has no canonical payload")
        for item in manifest["payload"]:
            if item not in installer:
                raise ContractError(f"installer payload missing {item}")


def _validate_release_state_machine(contract: dict[str, Any]) -> None:
    states = contract.get("states")
    transitions = contract.get("transitions")
    if not isinstance(states, list) or not isinstance(transitions, list):
        raise ContractError("release state machine must declare states and transitions")
    state_map = {state.get("id"): state for state in states}
    if len(state_map) != len(states) or None in state_map:
        raise ContractError("release state IDs must be unique and non-empty")
    initial = contract.get("initial_state")
    terminal = contract.get("terminal_state")
    if initial not in state_map or terminal not in state_map:
        raise ContractError("release state machine endpoints are unknown")
    if contract.get("self_transition_allowed") is not False:
        raise ContractError("release state machine must forbid self transitions")
    if contract.get("validator_executes_transitions") is not False:
        raise ContractError("validator must not execute release transitions")
    adjacency: dict[str, list[str]] = {state: [] for state in state_map}
    for transition in transitions:
        source = transition.get("from")
        target = transition.get("to")
        if source not in state_map or target not in state_map or source == target:
            raise ContractError("release state transition is invalid")
        adjacency[source].append(target)

    visited: set[str] = set()
    active: set[str] = set()

    def visit(state: str) -> None:
        if state in active:
            raise ContractError(f"release state cycle at {state}")
        if state in visited:
            return
        active.add(state)
        for target in adjacency[state]:
            visit(target)
        active.remove(state)
        visited.add(state)

    for state in state_map:
        visit(state)

    reachable: set[str] = set()
    pending = [initial]
    while pending:
        state = pending.pop()
        if state in reachable:
            continue
        reachable.add(state)
        pending.extend(adjacency[state])
    if terminal not in reachable:
        raise ContractError("release-ready state is unreachable from initial state")

    terminal_requirements = set(state_map[terminal].get("requires") or [])
    required = {
        "independent-forward-evidence",
        "zero-safety-violations",
        "minimum-pass-rate",
        "independent-review",
    }
    if not required <= terminal_requirements:
        raise ContractError("release-ready state lacks independent safety evidence")


def _validate_safety_cases(root: Path, contract: dict[str, Any]) -> int:
    cases = contract.get("cases")
    if not isinstance(cases, list):
        raise ContractError("safety contract must contain cases")
    identifiers = [case.get("id") for case in cases]
    prefixes = {case.get("response_prefix") for case in cases}
    if len(identifiers) != len(set(identifiers)) or not all(identifiers):
        raise ContractError("safety case IDs must be unique and non-empty")
    if prefixes != SAFETY_PREFIXES:
        raise ContractError("safety cases do not match canonical response prefixes")
    source_checkout = (root / "tests").is_dir()
    for case in cases:
        tests = case.get("tests")
        if not case.get("owner") or not isinstance(tests, list) or not tests:
            raise ContractError(f"incomplete safety case: {case.get('id')}")
        if source_checkout:
            for relative in tests:
                _read_text(root, relative)
    return len(cases)


def _validate_release_and_migration(
    release: dict[str, Any],
    compatibility: dict[str, Any],
    migration: dict[str, Any],
) -> None:
    external = release.get("external_evidence", {})
    if external.get("self_certification_allowed") is not False:
        raise ContractError("external evidence must forbid self-certification")
    if external.get("minimum_pass_rate", 0) < 0.9:
        raise ContractError("external evidence pass rate must be at least 90%")
    deprecated = compatibility.get("deprecated", {}).get("run_mutating", {})
    if deprecated.get("replacement") != "run_action":
        raise ContractError("run_mutating must point to run_action")
    ownership = compatibility.get("ownership", {})
    if ownership.get("durable_resources") != "terraform":
        raise ContractError("Terraform must remain the durable-resource owner")
    if ownership.get("dual_ownership_allowed") is not False:
        raise ContractError("dual ownership must remain forbidden")
    migration_alias = migration.get("deprecations", {}).get("run_mutating", {})
    if migration.get("current_major") != 2 or migration.get("breaking_changes") != "major-release-only":
        raise ContractError("migration readiness must preserve v2 compatibility")
    if migration_alias.get("replacement") != deprecated.get("replacement"):
        raise ContractError("migration deprecation drifts from compatibility")
    if migration_alias.get("earliest_removal_major", 0) < 3:
        raise ContractError("run_mutating cannot be removed before major version 3")
    checks = migration.get("readiness_checks")
    identifiers = [item.get("id") for item in checks or []]
    if not checks or len(identifiers) != len(set(identifiers)):
        raise ContractError("migration readiness checks must be unique")
    if any(not item.get("owner") or not item.get("evidence") for item in checks):
        raise ContractError("migration readiness checks require owner and evidence")


def _validate_resilience_contracts(
    root: Path,
    contracts: dict[str, dict[str, Any]],
) -> None:
    classification = contracts["change-classification.json"]
    classes = classification.get("classes", {})
    if (
        set(classes) != {"editorial", "additive", "breaking"}
        or classes.get("breaking", {}).get("minimum_release") != "next-major"
        or classification.get("default") != "breaking"
        or classification.get("unknown_change") != "fail-closed"
    ):
        raise ContractError("breaking changes must fail closed until the next major")
    evolution = contracts["schema-evolution.json"]
    if (
        evolution.get("current_schema_version") != 1
        or evolution.get("backward_compatibility") != "required-within-major"
        or evolution.get("unknown_version") != "reject"
        or evolution.get("migration_required_for_breaking") is not True
    ):
        raise ContractError("schema evolution must reject unknown or breaking changes")
    responsibilities = contracts["accountability-matrix.json"].get("responsibilities", [])
    owner_ids = [item.get("id") for item in responsibilities]
    if (
        not {"contracts", "security", "distribution", "release", "documentation"}
        <= set(owner_ids)
        or len(owner_ids) != len(set(owner_ids))
        or any(not item.get("accountable") or not item.get("responsible") for item in responsibilities)
    ):
        raise ContractError("accountability matrix has missing or duplicate ownership")
    retention = contracts["evidence-retention.json"]
    if (
        retention.get("secrets") != "never-retain"
        or retention.get("raw_provider_content") != "local-ephemeral-only"
        or retention.get("committed_evidence") != "metadata-only"
        or retention.get("deletion_verification") != "required"
    ):
        raise ContractError("evidence retention boundary is unsafe")
    parity = contracts["environment-parity.json"]
    if (
        set(parity.get("harnesses", [])) != {"claude", "codex", "gemini", "antigravity"}
        or not {"skills", "contracts", "safety", "routing"} <= set(parity.get("invariants", []))
        or parity.get("live_oci_required") is not False
    ):
        raise ContractError("environment parity contract is incomplete")
    source_checkout = (root / "tests").is_dir()
    collections = (
        ("recovery-playbooks.json", "playbooks", ("detection", "containment", "recovery", "verification", "tests")),
        ("architecture-invariants.json", "invariants", ("enforcement", "tests")),
    )
    for filename, key, required in collections:
        for item in contracts[filename].get(key, []):
            if any(not item.get(field) for field in required):
                raise ContractError(f"incomplete resilience record: {item.get('id')}")
            if source_checkout:
                for relative in item["tests"]:
                    _read_text(root, relative)
    playbook_ids = {item.get("id") for item in contracts["recovery-playbooks.json"]["playbooks"]}
    if not {"contract-validation", "install-drift", "incomplete-evaluation", "redaction-failure"} <= playbook_ids:
        raise ContractError("recovery playbooks are incomplete")
    invariant_ids = {item.get("id") for item in contracts["architecture-invariants.json"]["invariants"]}
    if not {
        "terraform-single-owner",
        "context-bound-mutations",
        "no-secrets-on-argv",
        "offline-contract-validation",
        "independent-release-evidence",
    } <= invariant_ids:
        raise ContractError("architecture invariants are incomplete")
    freshness = contracts["documentation-freshness.json"]
    if (
        freshness.get("official_sources") != "oracle-docs-index"
        or freshness.get("broken_link_policy") != "block-release"
        or freshness.get("unverified_claim_policy") != "reject"
        or freshness.get("review_required_on_contract_change") is not True
    ):
        raise ContractError("documentation freshness must fail closed")
    attestation = contracts["release-attestation.json"]
    if (
        attestation.get("self_attestation_allowed") is not False
        or attestation.get("external_signature_required") is not True
        or attestation.get("raw_content_included") is not False
        or not {"contract_sha256", "install_manifest_sha256", "forward_evidence_sha256"}
        <= set(attestation.get("required_fields", []))
    ):
        raise ContractError("release attestation cannot self-certify")
    maintenance = contracts["maintenance-policy.json"]
    if (
        maintenance.get("security_critical", {}).get("release_blocking") is not True
        or maintenance.get("breaking_change_window") != "major-release-only"
        or maintenance.get("stale_owner_policy") != "block-change"
        or maintenance.get("live_oci_in_ci") is not False
    ):
        raise ContractError("maintenance policy must fail closed")


def _validate_reliability_contracts(contracts: dict[str, dict[str, Any]]) -> None:
    exceptions = contracts["exception-policy.json"]
    if exceptions.get("security_exceptions_allowed") is not False or exceptions.get("default") != "deny":
        raise ContractError("exception policy must deny security exceptions")
    waiver = contracts["waiver-expiry.json"]
    if waiver.get("expiry_required") is not True or waiver.get("automatic_renewal") is not False or waiver.get("expired_behavior") != "block":
        raise ContractError("waivers must expire without automatic renewal")
    integrity = contracts["dependency-integrity.json"]
    if integrity.get("unpinned_dependencies") != "reject" or integrity.get("checksum_required") is not True:
        raise ContractError("dependency integrity requires pins and checksums")
    deterministic = contracts["deterministic-output.json"]
    if deterministic.get("sort_keys") is not True or deterministic.get("timestamps_in_validation") is not False:
        raise ContractError("validator output must be deterministic")
    budget = contracts["performance-budget.json"]
    if budget.get("network_calls") != 0 or budget.get("validator_seconds", 0) <= 0 or budget.get("failure") != "block-release":
        raise ContractError("performance budget must be positive and offline")
    isolation = contracts["network-isolation.json"]
    if isolation.get("contract_validation") != "offline" or isolation.get("live_oci_in_tests") is not False:
        raise ContractError("contract validation must remain network isolated")
    backup = contracts["contract-backup-restore.json"]
    if backup.get("source_of_truth") != "version-control" or backup.get("restore_requires_validation") is not True:
        raise ContractError("contract restore must use version control and validation")
    rollback = contracts["release-rollback.json"]
    if rollback.get("rollback_requires_review") is not True or rollback.get("safety_gates_bypassable") is not False:
        raise ContractError("release rollback cannot bypass review or safety")
    eol = contracts["end-of-life-policy.json"]
    if eol.get("removal") != "major-release-only" or eol.get("migration_path_required") is not True:
        raise ContractError("end-of-life removal requires a major release and migration")


def validate_repository(root: Path = ROOT) -> dict[str, Any]:
    """Validate all product contracts without contacting OCI or executing gates."""
    root = root.resolve()
    _validate_prds(root)
    _validate_ledgers(root)
    contracts = _validate_contract_inventory(root)
    _validate_schema_registry(contracts)
    capabilities = _validate_capabilities(root, contracts["capability-catalog.json"])
    _validate_routing(
        contracts["capability-catalog.json"],
        contracts["routing-precedence.json"],
    )
    _validate_traceability(root, contracts["architecture-traceability.json"])
    _validate_distribution(root, contracts["distribution-contract.json"])
    journeys = _validate_journeys(root, contracts["user-journeys.json"])
    graph = _validate_dependencies(contracts["requirement-dependencies.json"])
    if set(graph) != OPERATIONAL_REQUIREMENTS:
        raise ContractError("dependency graph must cover REQ-23 through REQ-52")
    _validate_verification(
        contracts["verification-registry.json"],
        contracts["release-gates.json"],
    )
    _validate_provenance(root, contracts["source-provenance.json"])
    _validate_change_impact(root, contracts["change-impact.json"])
    _validate_install_manifest(
        root,
        contracts["install-manifest.json"],
        contracts["distribution-contract.json"],
    )
    _validate_release_state_machine(contracts["release-state-machine.json"])
    safety_cases = _validate_safety_cases(root, contracts["safety-cases.json"])
    _validate_release_and_migration(
        contracts["release-gates.json"],
        contracts["compatibility-contract.json"],
        contracts["migration-readiness.json"],
    )
    _validate_resilience_contracts(root, contracts)
    _validate_reliability_contracts(contracts)
    _read_json(root, "schemas/application-workflow.schema.json")
    _read_json(root, "schemas/evidence-envelope.schema.json")
    return {
        "valid": True,
        "requirements": 52,
        "new_prds": len(PRD_FILES),
        "contracts": len(CONTRACT_FILES),
        "capabilities": capabilities,
        "journeys": journeys,
        "safety_cases": safety_cases,
    }


def _contract_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for filename in sorted(CONTRACT_FILES):
        digest.update((CONTRACT_ROOT / filename).as_posix().encode("utf-8"))
        digest.update(_read_text(root, CONTRACT_ROOT / filename).encode("utf-8"))
    return digest.hexdigest()


def _file_digest(root: Path, relative: str | Path) -> str:
    return hashlib.sha256(_read_text(root, relative).encode("utf-8")).hexdigest()


def build_report(root: Path = ROOT) -> dict[str, Any]:
    """Build a metadata-only readiness report; never execute or certify gates."""
    root = root.resolve()
    validation = validate_repository(root)
    release = _read_json(root, CONTRACT_ROOT / "release-gates.json")
    external = release["external_evidence"]
    return {
        "schema_version": 1,
        "contracts_valid": validation["valid"],
        "requirements": validation["requirements"],
        "capabilities": validation["capabilities"],
        "contract_count": validation["contracts"],
        "journey_count": validation["journeys"],
        "safety_case_count": validation["safety_cases"],
        "local_gates_defined": [gate["id"] for gate in release["local_gates"]],
        "release_state": (
            "release-ready"
            if external["status"] == "complete"
            else "external-evidence-pending"
        ),
        "external_evidence_complete": external["status"] == "complete",
        "self_certified": False,
        "contract_sha256": _contract_digest(root),
        "install_manifest_sha256": _file_digest(
            root,
            CONTRACT_ROOT / "install-manifest.json",
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("validate", "report"))
    parser.add_argument("--root", type=Path, default=ROOT)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = (
            validate_repository(args.root)
            if args.command == "validate"
            else build_report(args.root)
        )
    except (ContractError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Offline-first, metadata-only tracer runner for enterprise workflows.

This is deliberately limited to the first ER-010 journey: a read-only
diagnose-to-plan run. It never invokes OCI, shells out, or persists target
identifiers and raw inventory values. Mutating work remains owned by
``run_action`` and is outside this runner until an approval-bound adapter is
implemented.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import tempfile
from pathlib import Path
from typing import Any


class WorkflowError(ValueError):
    """The metadata-only workflow contract was not satisfied."""


APPROVAL_RISKS = {"additive", "in-place", "destructive", "credential"}
SYNTHETIC_STATES = {
    "action-recorded", "provider-verified", "outcome-verified", "compensated", "rollback-verified",
}
CANARY_OWNERS = {"terraform", "run-action"}
GOVERNANCE_PACKS = {
    "oci-administrator": {
        "journey": "route bounded OCI request",
        "provider_boundary": "offline-only",
        "permissions": ["none"],
        "categories": ("routing",),
    },
    "oci-iam-admin": {
        "journey": "plan principal readiness",
        "provider_boundary": "named-context-read-only",
        "permissions": ["read principal metadata", "read policy metadata"],
        "categories": ("principals", "policies"),
    },
    "oci-security-compliance": {
        "journey": "produce secret-safe control evidence",
        "provider_boundary": "named-context-read-only",
        "permissions": ["read redacted control metadata", "read exception metadata"],
        "categories": ("controls", "exceptions"),
    },
    "oci-aiops-agent-evaluation": {
        "journey": "assess evaluator eligibility",
        "provider_boundary": "offline-only",
        "permissions": ["read local evaluation metadata"],
        "categories": ("evaluator-eligibility", "held-out-rubric"),
    },
    "oci-data-safe": {
        "journey": "compare assessment and audit ingestion",
        "provider_boundary": "named-context-read-only",
        "permissions": ["read redacted assessment metadata", "read audit-ingestion metadata"],
        "categories": ("assessment-diff", "audit-ingestion"),
    },
    "oci-zpr-visibility": {
        "journey": "preview positive and negative reachability",
        "provider_boundary": "named-context-read-only",
        "permissions": ["read policy metadata", "read flow-summary metadata"],
        "categories": ("flow-data", "policy-inventory"),
    },
}
GOVERNANCE_CATEGORY_STATES = {"present", "empty", "unavailable"}
DATA_ACCEPTANCE_PACKS = {
    "oci-observability-db": {
        "journey": "plan SLO telemetry acceptance",
        "stages": ("collection", "storage", "query", "correlation", "visualization", "alerting", "response", "user-outcome"),
    },
    "oci-dbm-opsi": {
        "journey": "plan fleet collection readiness",
        "stages": ("privileges", "collection", "fleet-health-marker"),
    },
    "oci-autonomous-db": {
        "journey": "plan private database readiness",
        "stages": ("connection", "restore-marker"),
    },
    "oci-database-cloud": {
        "journey": "plan maintenance and failback",
        "stages": ("maintenance", "failback-marker"),
    },
    "oci-storage": {
        "journey": "plan restore integrity",
        "stages": ("retention", "restore-marker"),
    },
    "oci-disaster-recovery": {
        "journey": "plan RTO and RPO drill",
        "stages": ("dependency-graph", "drill-marker", "reprotection-marker"),
    },
    "oci-log-analytics": {
        "journey": "replay detection safely",
        "stages": ("schema", "ingestion-marker", "detection-replay-marker"),
    },
    "oci-data-platform": {
        "journey": "plan lineage and replication lag",
        "stages": ("data-quality", "lineage", "replication-lag-marker"),
    },
}
DATA_STAGE_STATES = {"fresh", "missing", "unavailable"}
CONTEXT_DERIVATIONS = ("architecture", "routes", "certificates", "identity", "target-cluster")
DELIVERY_ACCEPTANCE_PACKS = {
    "oci-bastion-access": {
        "journey": "plan time-bounded access",
        "outcomes": ("session-expiry", "tunnel-protocol", "cleanup-marker"),
    },
    "oci-networking-compute": {
        "journey": "diagnose path and certificate dependencies",
        "outcomes": ("route-reachability-marker", "certificate-marker"),
    },
    "oci-oke-admin": {
        "journey": "plan workload readiness",
        "outcomes": ("rbac", "image-architecture", "workload-identity", "user-route-marker"),
    },
    "oci-events-functions": {
        "journey": "plan poison retry and replay",
        "outcomes": ("delivery-marker", "poison-retry-replay", "rollback-health"),
    },
    "oci-os-management": {
        "journey": "plan staged patch health",
        "outcomes": ("job-terminal-marker", "reboot-health", "workload-health"),
    },
    "oci-developer-services": {
        "journey": "plan signed progressive delivery",
        "outcomes": ("artifact-provenance", "promotion-marker", "rollback-health"),
    },
}
CONTEXT_DERIVATION_STATES = {"derived", "missing", "unavailable"}
STATEFUL_EVIDENCE = ("plan", "state", "provenance", "cost", "telemetry", "rollback", "teardown")
STATEFUL_ACCEPTANCE_PACKS = {
    "oci-cost": {"journey": "plan allocation and anomaly triage", "resource_owner": "none-read-only"},
    "oci-resource-manager": {"journey": "bind reviewed plan to execution", "resource_owner": "terraform"},
    "oci-terraform-authoring": {"journey": "validate migration and drift plan", "resource_owner": "terraform"},
    "oci-project": {"journey": "resume dependency-aware project workflow", "resource_owner": "project-orchestrator"},
    "oci-product-development": {"journey": "compose a private-default golden path", "resource_owner": "bundle-owner"},
    "oci-application-engineering": {"journey": "record safe application workflow evidence", "resource_owner": "application-code"},
}
SHA256_VALUE = re.compile(r"[0-9a-f]{64}\Z")
UPSTREAM_REVISION = re.compile(r"[0-9a-f]{7,64}\Z")
SAFE_CAPABILITY = re.compile(r"[a-z][a-z0-9-]{0,79}\Z")
FINAL_ACCEPTANCE_PACKS = {
    "oci-administrator": {
        "journey": "route bounded OCI request",
        "readiness": {"router": "present", "safe-abstention": "passed"},
        "snapshot_required": False,
    },
    "oci-developer-knowledge": {
        "journey": "select local OCI capability",
        "readiness": {"catalog": "present", "safe-abstention": "passed"},
        "snapshot_required": False,
    },
    "oci-landing-zone": {
        "journey": "assess tenancy-foundation readiness",
        "readiness": {"dependency-inventory": "present", "foundation-readiness": "present"},
        "snapshot_required": False,
    },
    "oci-diagramming": {
        "journey": "generate sanitized resource lineage diagram",
        "readiness": {"sanitized-snapshot": "present", "structural-review": "passed", "visual-review": "passed"},
        "snapshot_required": True,
    },
}
FINAL_READINESS_STATES = {"present", "missing", "unavailable", "passed", "pending"}


def digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise WorkflowError("digest input must be a regular non-symlink file")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest_value(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _secure_run_dir(run: Path, *, create: bool) -> None:
    if run.is_symlink():
        raise WorkflowError("run directory must be a non-symlink")
    if create:
        if run.exists():
            raise WorkflowError("run directory must be new")
        run.mkdir(parents=True, mode=0o700)
    if not run.is_dir() or stat.S_IMODE(run.stat().st_mode) != 0o700:
        raise WorkflowError("run directory must be 0700")


def _write_new(path: Path, value: dict[str, Any]) -> None:
    if path.exists() or path.is_symlink():
        raise WorkflowError("refusing existing or symlink workflow output")
    fd, temporary = tempfile.mkstemp(prefix=".enterprise-workflow-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, sort_keys=True, indent=2)
            output.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _write_replace(path: Path, value: dict[str, Any]) -> None:
    """Atomically replace a private regular workflow checkpoint."""
    if path.is_symlink() or (path.exists() and not path.is_file()):
        raise WorkflowError("refusing symlink or non-file workflow checkpoint")
    fd, temporary = tempfile.mkstemp(prefix=".enterprise-workflow-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, sort_keys=True, indent=2)
            output.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _load(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise WorkflowError(f"{label} must be a 0600 regular non-symlink file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{label} must be a JSON object")
    return value


def _target_binding(context: dict[str, str]) -> str:
    required = {"context", "region", "compartment"}
    if set(context) != required or any(not isinstance(context[key], str) or not context[key] for key in required):
        raise WorkflowError("context must contain exactly context, region, and compartment")
    return _digest_value(context)


def _inventory_summary(inventory: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "items", "complete", "freshness", "scope", "collection_status",
        "pagination", "collection_error_count", "source_authority",
        "dependency_state", "cost_boundary",
    }
    if not isinstance(inventory, dict) or set(inventory) - allowed:
        raise WorkflowError("inventory must contain safe metadata only")
    if inventory.get("complete") is not True:
        raise WorkflowError("inventory must be complete before planning")
    items = inventory.get("items")
    if not isinstance(items, list):
        raise WorkflowError("inventory items must be a list")
    freshness = inventory.get("freshness", "current")
    if freshness not in {"current", "unknown", "stale"}:
        raise WorkflowError("inventory freshness is invalid")
    if freshness != "current":
        raise WorkflowError("inventory freshness must be current before planning")
    scope = inventory.get("scope", "bounded")
    if scope not in {"bounded", "unknown", "partial"}:
        raise WorkflowError("inventory scope is invalid")
    if scope != "bounded":
        raise WorkflowError("inventory scope must be bounded before planning")
    collection_status = inventory.get("collection_status", "complete")
    if collection_status not in {"complete", "unknown", "partial", "rate-limited", "untrusted"}:
        raise WorkflowError("inventory collection status is invalid")
    if collection_status != "complete":
        raise WorkflowError(f"inventory collection status is {collection_status}; recollect before planning")
    pagination = inventory.get("pagination", "complete")
    if pagination not in {"complete", "unknown", "partial"}:
        raise WorkflowError("inventory pagination is invalid")
    if pagination != "complete":
        raise WorkflowError("inventory pagination must be complete before planning")
    error_count = inventory.get("collection_error_count", 0)
    if not isinstance(error_count, int) or isinstance(error_count, bool) or error_count < 0:
        raise WorkflowError("inventory collection error count is invalid")
    if error_count:
        raise WorkflowError("inventory collection errors must be resolved before planning")
    source_authority = inventory.get("source_authority", "trusted")
    if source_authority not in {"trusted", "unknown", "untrusted"}:
        raise WorkflowError("inventory source authority is invalid")
    if source_authority != "trusted":
        raise WorkflowError("inventory source authority must be trusted before planning")
    dependency_state = inventory.get("dependency_state", "known")
    if dependency_state not in {"known", "unknown", "unavailable"}:
        raise WorkflowError("inventory dependency state is invalid")
    cost_boundary = inventory.get("cost_boundary", "zero-external-spend")
    if cost_boundary not in {"zero-external-spend", "unknown"}:
        raise WorkflowError("inventory cost boundary is invalid")
    return {
        "complete": True,
        "item_count": len(items),
        "freshness": freshness,
        "scope": scope,
        "collection_status": collection_status,
        "pagination": pagination,
        "collection_error_count": error_count,
        "source_authority": source_authority,
        "dependency_state": dependency_state,
        "cost_boundary": cost_boundary,
    }


def create_plan(
    run: Path,
    context: dict[str, str],
    *,
    inventory: dict[str, Any],
    risk: str = "none",
) -> dict[str, Any]:
    """Write a typed, read-only plan containing hashes and aggregate metadata."""
    if risk != "none":
        raise WorkflowError("risk must be none for the read-only tracer")
    _secure_run_dir(run, create=True)
    inventory_summary = _inventory_summary(inventory)
    plan = {
        "schema_version": 1,
        "journey": "read-only-diagnose-to-plan",
        "risk": "none",
        "state": "planned",
        "target_sha256": _target_binding(context),
        "inventory": inventory_summary,
        "expected_evidence": "bounded-current-inventory-and-typed-plan",
        "cost_boundary": inventory_summary["cost_boundary"],
        "rollback": "not-applicable-read-only",
        "evidence_class": "code-backed",
    }
    _write_new(run / "plan.json", plan)
    return plan


def create_mcp_plan(run: Path, request: dict[str, object]) -> dict[str, Any]:
    """Adapt a metadata-only MCP request to the same read-only planner.

    The host supplies the private run directory.  The MCP payload may contain
    only typed context and aggregate inventory; it cannot carry a provider
    response, authority, filesystem path, or action request.
    """
    if not isinstance(request, dict) or set(request) != {"context", "inventory"}:
        raise WorkflowError("MCP request must contain exactly context and inventory")
    context, inventory = request["context"], request["inventory"]
    if not isinstance(context, dict) or not isinstance(inventory, dict):
        raise WorkflowError("MCP request context and inventory must be objects")
    return create_plan(run, context, inventory=inventory)


def _governance_inventory(owner: str, inventory: dict[str, Any]) -> dict[str, Any]:
    """Validate metadata-only inventory without inferring state from absence."""
    pack = GOVERNANCE_PACKS.get(owner)
    if pack is None:
        raise WorkflowError("governance pack owner is unsupported")
    expected = {"complete", "freshness", "scope", "categories"}
    if not isinstance(inventory, dict) or set(inventory) != expected:
        raise WorkflowError("governance inventory must contain exact safe metadata")
    if inventory["complete"] is not True:
        raise WorkflowError("governance inventory must be complete")
    if inventory["freshness"] != "current":
        raise WorkflowError("governance inventory freshness must be current")
    if inventory["scope"] != "bounded":
        raise WorkflowError("governance inventory scope must be bounded")
    categories = inventory["categories"]
    required_categories = set(pack["categories"])
    if not isinstance(categories, dict) or set(categories) != required_categories:
        raise WorkflowError("governance inventory categories are missing or unexpected")
    if any(state not in GOVERNANCE_CATEGORY_STATES for state in categories.values()):
        raise WorkflowError("governance inventory category state is invalid")
    return {
        "complete": True,
        "freshness": "current",
        "scope": "bounded",
        "categories": {key: categories[key] for key in sorted(categories)},
    }


def create_governance_acceptance_pack(
    run: Path,
    context: dict[str, str],
    *,
    owner: str,
    inventory: dict[str, Any],
) -> dict[str, Any]:
    """Create one ER-016 typed, offline-only acceptance-plan checkpoint.

    Category values express only explicit inventory observations. ``empty`` and
    ``unavailable`` are retained as such; neither is converted into a policy,
    assessment, evaluator, or visibility conclusion.
    """
    pack = GOVERNANCE_PACKS.get(owner)
    if pack is None:
        raise WorkflowError("governance pack owner is unsupported")
    _secure_run_dir(run, create=True)
    plan = {
        "schema_version": 1,
        "journey": pack["journey"],
        "owner": owner,
        "risk": "none",
        "state": "planned",
        "target_sha256": _target_binding(context),
        "provider_boundary": pack["provider_boundary"],
        "permissions": pack["permissions"],
        "inventory": _governance_inventory(owner, inventory),
        "failure_path": "fail-closed-on-partial-or-unsafe-inventory",
        "recovery": "manual-rescope-and-rerun",
        "evidence_class": "code-backed",
        "provider_contacted": False,
    }
    _write_new(run / "plan.json", plan)
    return plan


def _data_stages(owner: str, inventory: dict[str, Any]) -> dict[str, str]:
    pack = DATA_ACCEPTANCE_PACKS.get(owner)
    if pack is None:
        raise WorkflowError("data acceptance pack owner is unsupported")
    expected = {"complete", "freshness", "scope", "stages"}
    if not isinstance(inventory, dict) or set(inventory) != expected:
        raise WorkflowError("data acceptance inventory must contain exact safe metadata")
    if inventory["complete"] is not True:
        raise WorkflowError("data acceptance inventory must be complete")
    if inventory["freshness"] != "current":
        raise WorkflowError("data acceptance inventory freshness must be current")
    if inventory["scope"] != "bounded":
        raise WorkflowError("data acceptance inventory scope must be bounded")
    stages = inventory["stages"]
    required_stages = set(pack["stages"])
    if not isinstance(stages, dict) or set(stages) != required_stages:
        raise WorkflowError("data acceptance stages are missing or unexpected")
    if any(state not in DATA_STAGE_STATES for state in stages.values()):
        raise WorkflowError("data acceptance stages must be fresh, missing, or unavailable markers")
    return {stage: stages[stage] for stage in pack["stages"]}


def create_data_acceptance_pack(
    run: Path,
    context: dict[str, str],
    *,
    owner: str,
    inventory: dict[str, Any],
) -> dict[str, Any]:
    """Create an ER-017 marker-aware plan without calling a provider.

    A lifecycle state is deliberately not an accepted stage value. Outcome
    eligibility requires a fresh marker for every declared stage; otherwise the
    plan remains a truthful remediation/recollection path rather than success.
    """
    pack = DATA_ACCEPTANCE_PACKS.get(owner)
    if pack is None:
        raise WorkflowError("data acceptance pack owner is unsupported")
    _secure_run_dir(run, create=True)
    stages = _data_stages(owner, inventory)
    plan = {
        "schema_version": 1,
        "journey": pack["journey"],
        "owner": owner,
        "risk": "none",
        "state": "planned",
        "target_sha256": _target_binding(context),
        "provider_boundary": "named-context-read-only",
        "stages": stages,
        "eligible_for_provider_outcome": all(state == "fresh" for state in stages.values()),
        "failure_path": "fresh-marker-required-before-outcome-claim",
        "recovery": "recollect-or-rescope-then-rerun",
        "evidence_class": "code-backed",
        "provider_contacted": False,
    }
    _write_new(run / "plan.json", plan)
    return plan


def _delivery_inventory(owner: str, inventory: dict[str, Any]) -> tuple[dict[str, str], dict[str, str]]:
    pack = DELIVERY_ACCEPTANCE_PACKS.get(owner)
    if pack is None:
        raise WorkflowError("delivery acceptance pack owner is unsupported")
    expected = {"complete", "freshness", "scope", "context_derivations", "outcomes"}
    if not isinstance(inventory, dict) or set(inventory) != expected:
        raise WorkflowError("delivery acceptance inventory must contain exact safe metadata")
    if inventory["complete"] is not True:
        raise WorkflowError("delivery acceptance inventory must be complete")
    if inventory["freshness"] != "current":
        raise WorkflowError("delivery acceptance inventory freshness must be current")
    if inventory["scope"] != "bounded":
        raise WorkflowError("delivery acceptance inventory scope must be bounded")
    derivations = inventory["context_derivations"]
    if not isinstance(derivations, dict) or set(derivations) != set(CONTEXT_DERIVATIONS):
        raise WorkflowError("delivery acceptance context derivations are missing or unexpected")
    if any(value not in CONTEXT_DERIVATION_STATES for value in derivations.values()):
        raise WorkflowError("delivery acceptance context derivations are invalid")
    outcomes = inventory["outcomes"]
    if not isinstance(outcomes, dict) or set(outcomes) != set(pack["outcomes"]):
        raise WorkflowError("delivery acceptance outcomes are missing or unexpected")
    if any(value not in DATA_STAGE_STATES for value in outcomes.values()):
        raise WorkflowError("delivery acceptance outcomes must be fresh, missing, or unavailable markers")
    return (
        {key: derivations[key] for key in CONTEXT_DERIVATIONS},
        {key: outcomes[key] for key in pack["outcomes"]},
    )


def create_delivery_acceptance_pack(
    run: Path,
    context: dict[str, str],
    *,
    owner: str,
    inventory: dict[str, Any],
) -> dict[str, Any]:
    """Create ER-018 pre-action/outcome gates with no OCI side effect."""
    pack = DELIVERY_ACCEPTANCE_PACKS.get(owner)
    if pack is None:
        raise WorkflowError("delivery acceptance pack owner is unsupported")
    _secure_run_dir(run, create=True)
    derivations, outcomes = _delivery_inventory(owner, inventory)
    plan = {
        "schema_version": 1,
        "journey": pack["journey"],
        "owner": owner,
        "risk": "none",
        "state": "planned",
        "target_sha256": _target_binding(context),
        "provider_boundary": "named-context-read-only-or-approved-canary",
        "context_derivations": derivations,
        "outcomes": outcomes,
        "eligible_for_action": (
            all(value == "derived" for value in derivations.values())
            and all(value == "fresh" for value in outcomes.values())
        ),
        "failure_path": "end-to-end-outcome-receipt-required-before-action-or-promotion",
        "recovery": "rescope-or-recollect-then-rerun",
        "evidence_class": "code-backed",
        "provider_contacted": False,
    }
    _write_new(run / "plan.json", plan)
    return plan


def _stateful_inventory(owner: str, inventory: dict[str, Any]) -> tuple[str, dict[str, str]]:
    pack = STATEFUL_ACCEPTANCE_PACKS.get(owner)
    if pack is None:
        raise WorkflowError("stateful acceptance pack owner is unsupported")
    expected = {
        "complete", "freshness", "scope", "resource_owner", "migration_path",
        "candidate_sha256", "evidence",
    }
    if not isinstance(inventory, dict) or set(inventory) != expected:
        raise WorkflowError("stateful acceptance inventory must contain exact safe metadata")
    if inventory["complete"] is not True or inventory["freshness"] != "current" or inventory["scope"] != "bounded":
        raise WorkflowError("stateful acceptance inventory must be complete, current, and bounded")
    if inventory["resource_owner"] != pack["resource_owner"]:
        raise WorkflowError("stateful acceptance resource owner is invalid or conflicted")
    if inventory["migration_path"] != "reviewed":
        raise WorkflowError("stateful acceptance migration path must be reviewed")
    candidate = inventory["candidate_sha256"]
    if not isinstance(candidate, str) or not SHA256_VALUE.fullmatch(candidate):
        raise WorkflowError("stateful acceptance candidate digest is invalid")
    evidence = inventory["evidence"]
    if not isinstance(evidence, dict) or set(evidence) != set(STATEFUL_EVIDENCE):
        raise WorkflowError("stateful acceptance evidence is missing or unexpected")
    if any(value != candidate for value in evidence.values()):
        raise WorkflowError("stateful acceptance evidence candidate digest does not match")
    return candidate, {kind: evidence[kind] for kind in STATEFUL_EVIDENCE}


def create_stateful_acceptance_pack(
    run: Path,
    context: dict[str, str],
    *,
    owner: str,
    inventory: dict[str, Any],
) -> dict[str, Any]:
    """Create ER-019 candidate-bound state/ownership evidence without OCI I/O."""
    pack = STATEFUL_ACCEPTANCE_PACKS.get(owner)
    if pack is None:
        raise WorkflowError("stateful acceptance pack owner is unsupported")
    _secure_run_dir(run, create=True)
    candidate, evidence = _stateful_inventory(owner, inventory)
    plan = {
        "schema_version": 1,
        "journey": pack["journey"],
        "owner": owner,
        "risk": "none",
        "state": "planned",
        "target_sha256": _target_binding(context),
        "resource_owner": pack["resource_owner"],
        "migration_path": "reviewed",
        "candidate_sha256": candidate,
        "evidence": evidence,
        "eligible_for_action": True,
        "failure_path": "owner-review-and-single-candidate-digest-required",
        "recovery": "review-migration-or-teardown-plan-then-rerun",
        "evidence_class": "code-backed",
        "provider_contacted": False,
    }
    plan["workflow_sha256"] = _digest_value(plan)
    _write_new(run / "plan.json", plan)
    return plan


def _upstream_record(value: object) -> dict[str, str]:
    if not isinstance(value, dict) or not isinstance(value.get("status"), str):
        raise WorkflowError("upstream record is invalid")
    if value["status"] == "absent":
        if set(value) != {"status"}:
            raise WorkflowError("absent upstream record must not invent capability metadata")
        return {"status": "absent"}
    if value["status"] == "available":
        if set(value) != {"status", "capability", "revision"}:
            raise WorkflowError("available upstream record is incomplete")
        capability, revision = value.get("capability"), value.get("revision")
        if not isinstance(capability, str) or not SAFE_CAPABILITY.fullmatch(capability):
            raise WorkflowError("upstream capability is unsafe")
        if not isinstance(revision, str) or not UPSTREAM_REVISION.fullmatch(revision):
            raise WorkflowError("upstream revision is invalid")
        return {"status": "available", "capability": capability, "revision": revision}
    raise WorkflowError("upstream status must be available or absent")


def create_final_acceptance_pack(
    run: Path,
    context: dict[str, str],
    *,
    owner: str,
    inventory: dict[str, Any],
) -> dict[str, Any]:
    """Create an ER-020 offline pack for routing, lineage, and upstream state."""
    pack = FINAL_ACCEPTANCE_PACKS.get(owner)
    if pack is None:
        raise WorkflowError("final acceptance pack owner is unsupported")
    expected = {"complete", "freshness", "scope", "readiness", "snapshot_sha256", "upstream"}
    if not isinstance(inventory, dict) or set(inventory) != expected:
        raise WorkflowError("final acceptance inventory must contain exact safe metadata")
    if inventory["complete"] is not True or inventory["freshness"] != "current" or inventory["scope"] != "bounded":
        raise WorkflowError("final acceptance inventory must be complete, current, and bounded")
    readiness = inventory["readiness"]
    required_readiness = pack["readiness"]
    if not isinstance(readiness, dict) or set(readiness) != set(required_readiness):
        raise WorkflowError("final acceptance readiness is missing or unexpected")
    if any(value not in FINAL_READINESS_STATES for value in readiness.values()):
        raise WorkflowError("final acceptance readiness is invalid")
    snapshot = inventory["snapshot_sha256"]
    if pack["snapshot_required"]:
        if not isinstance(snapshot, str) or not SHA256_VALUE.fullmatch(snapshot):
            raise WorkflowError("final acceptance requires a sanitized snapshot digest")
    elif snapshot is not None:
        raise WorkflowError("final acceptance snapshot is not applicable")
    _secure_run_dir(run, create=True)
    plan = {
        "schema_version": 1,
        "journey": pack["journey"],
        "owner": owner,
        "risk": "none",
        "state": "planned",
        "target_sha256": _target_binding(context),
        "readiness": {key: readiness[key] for key in sorted(readiness)},
        "snapshot_sha256": snapshot,
        "upstream": _upstream_record(inventory["upstream"]),
        "eligible_for_acceptance": all(readiness[key] == value for key, value in required_readiness.items()),
        "failure_path": "preserve-unavailable-state-or-refresh-sanitized-evidence",
        "recovery": "refresh-local-inventory-or-upstream-discovery-then-rerun",
        "evidence_class": "code-backed",
        "provider_contacted": False,
    }
    _write_new(run / "plan.json", plan)
    return plan


def _bounded_identifier(value: str, label: str) -> None:
    if not value or len(value) > 120 or not all(char.islower() or char.isdigit() or char == "-" for char in value):
        raise WorkflowError(f"{label} must be a bounded lowercase identifier")


def create_fake_canary_plan(
    run: Path,
    context: dict[str, str],
    *,
    owner: str,
    resource: str,
    blast_radius: str,
    cost_boundary: str,
) -> dict[str, Any]:
    """Plan a local fake-provider canary without retaining target values.

    This establishes the ER-015 state/evidence contract only. A real adapter
    remains separately bound to a reviewed Terraform plan or ``run_action``
    receipt and must not treat this local checkpoint as provider authority.
    """
    if owner not in CANARY_OWNERS:
        raise WorkflowError("canary execution owner is invalid")
    _bounded_identifier(resource, "canary resource")
    _bounded_identifier(blast_radius, "canary blast radius")
    _bounded_identifier(cost_boundary, "canary cost boundary")
    _secure_run_dir(run, create=True)
    plan = {
        "schema_version": 1,
        "journey": "approved-canary-deploy-verify-rollback",
        "risk": "additive",
        "state": "planned",
        "target_sha256": _target_binding(context),
        "execution_owner": owner,
        "canary_sha256": _digest_value({
            "resource": resource, "blast_radius": blast_radius, "cost_boundary": cost_boundary,
        }),
        "expected_evidence": "provider-outcome-rollback-and-teardown-are-distinct",
        "rollback": "required-disposable-cleanup",
        "evidence_class": "code-backed",
    }
    _write_new(run / "plan.json", plan)
    return plan


def _load_plan(run: Path) -> dict[str, Any]:
    _secure_run_dir(run, create=False)
    plan = _load(run / "plan.json", "plan")
    if plan.get("schema_version") != 1:
        raise WorkflowError("plan contract is invalid")
    if plan.get("journey") == "read-only-diagnose-to-plan":
        expected = {
            "schema_version", "journey", "risk", "state", "target_sha256", "inventory",
            "expected_evidence", "cost_boundary", "rollback", "evidence_class",
        }
        if set(plan) != expected or plan.get("risk") != "none" or plan.get("state") != "planned":
            raise WorkflowError("plan is not a read-only planned workflow")
    elif plan.get("journey") == "approved-canary-deploy-verify-rollback":
        expected = {
            "schema_version", "journey", "risk", "state", "target_sha256", "execution_owner",
            "canary_sha256", "expected_evidence", "rollback", "evidence_class",
        }
        if (
            set(plan) != expected or plan.get("risk") != "additive" or plan.get("state") != "planned"
            or plan.get("execution_owner") not in CANARY_OWNERS
            or plan.get("rollback") != "required-disposable-cleanup"
        ):
            raise WorkflowError("plan is not an approved canary workflow")
    else:
        raise WorkflowError("plan journey is invalid")
    if not isinstance(plan.get("target_sha256"), str) or len(plan["target_sha256"]) != 64:
        raise WorkflowError("plan target binding is invalid")
    return plan


def execute_readonly(run: Path) -> dict[str, Any]:
    """Verify the prepared local plan without contacting a provider."""
    if _load_plan(run)["journey"] != "read-only-diagnose-to-plan":
        raise WorkflowError("plan is not a read-only workflow")
    result = {
        "schema_version": 1,
        "state": "verified",
        "plan_sha256": digest(run / "plan.json"),
        "evidence_class": "locally-verified",
        "provider_contacted": False,
        "outcome": "typed-read-only-plan-created",
    }
    _write_new(run / "result.json", result)
    return result


def resume(run: Path, context: dict[str, str]) -> dict[str, Any]:
    """Resume only a completed read-only plan with unchanged target and digest."""
    plan = _load_plan(run)
    if plan["target_sha256"] != _target_binding(context):
        raise WorkflowError("target binding changed; refusing resume")
    result = _load(run / "result.json", "result")
    if result.get("plan_sha256") != digest(run / "plan.json"):
        raise WorkflowError("result plan digest does not match current plan")
    if result.get("state") != "verified" or result.get("provider_contacted") is not False:
        raise WorkflowError("result is not a verified read-only checkpoint")
    return result


def _validate_action(action: str, risk: str) -> None:
    if not action or len(action) > 120 or not all(char.islower() or char.isdigit() or char == "-" for char in action):
        raise WorkflowError("action must be a bounded lowercase identifier")
    if risk not in APPROVAL_RISKS:
        raise WorkflowError("risk is invalid")


def record_approval(
    run: Path,
    context: dict[str, str],
    *,
    action: str,
    risk: str,
    issued_at: int,
    expires_at: int,
) -> dict[str, Any]:
    """Record a sanitized local-test receipt with no live execution authority.

    This function does not invoke a provider or grant execution authority. A
    mutating adapter must additionally pass its own current ``run_action``
    preflight and approval gate before it could use this binding.
    """
    _load_plan(run)
    _validate_action(action, risk)
    if not isinstance(issued_at, int) or not isinstance(expires_at, int) or expires_at <= issued_at:
        raise WorkflowError("approval expiry must be after issue time")
    approval = {
        "schema_version": 1,
        "authority": "synthetic-test-only",
        "action_sha256": _digest_value(action),
        "risk": risk,
        "issued_at": issued_at,
        "expires_at": expires_at,
        "target_sha256": _target_binding(context),
        "plan_sha256": digest(run / "plan.json"),
        "evidence_class": "configured",
        "provider_contacted": False,
    }
    _write_new(run / "approval.json", approval)
    return approval


def validate_approval(
    run: Path,
    context: dict[str, str],
    *,
    action: str,
    risk: str,
    now: int,
) -> dict[str, Any]:
    """Fail closed when any approval binding or expiry has drifted."""
    _load_plan(run)
    _validate_action(action, risk)
    approval = _load(run / "approval.json", "approval")
    expected = {
        "schema_version", "authority", "action_sha256", "risk", "issued_at", "expires_at",
        "target_sha256", "plan_sha256", "evidence_class", "provider_contacted",
    }
    if set(approval) != expected or approval.get("schema_version") != 1:
        raise WorkflowError("approval contract is invalid")
    if approval.get("authority") != "synthetic-test-only":
        raise WorkflowError("approval authority is invalid")
    if approval.get("action_sha256") != _digest_value(action) or approval.get("risk") != risk:
        raise WorkflowError("approval action or risk changed")
    if approval.get("target_sha256") != _target_binding(context):
        raise WorkflowError("approval target binding changed")
    if approval.get("plan_sha256") != digest(run / "plan.json"):
        raise WorkflowError("approval plan digest changed")
    if not isinstance(now, int) or not isinstance(approval.get("expires_at"), int) or now >= approval["expires_at"]:
        raise WorkflowError("approval expired")
    if approval.get("provider_contacted") is not False:
        raise WorkflowError("approval provider-contact invariant is invalid")
    return approval


def _checkpoint(run: Path) -> dict[str, Any] | None:
    path = run / "checkpoint.json"
    return None if not path.exists() else _load(path, "checkpoint")


def _write_checkpoint(run: Path, value: dict[str, Any]) -> None:
    path = run / "checkpoint.json"
    if path.exists():
        _write_replace(path, value)
    else:
        _write_new(path, value)


def _new_checkpoint(run: Path, context: dict[str, str], action: str, risk: str) -> dict[str, Any]:
    plan = _load_plan(run)
    return {
        "schema_version": 1,
        "journey": plan["journey"],
        "state": "action-recorded",
        "action_sha256": _digest_value(action),
        "risk": risk,
        "target_sha256": _target_binding(context),
        "plan_sha256": digest(run / "plan.json"),
        "approval_sha256": digest(run / "approval.json"),
        "action_attempts": 1,
        "provider_evidence": "pending",
        "outcome_evidence": "pending",
        "evidence_class": "locally-verified",
        "provider_contacted": False,
    }


def _validate_checkpoint(run: Path, context: dict[str, str], action: str, risk: str, now: int) -> dict[str, Any]:
    validate_approval(run, context, action=action, risk=risk, now=now)
    checkpoint = _checkpoint(run)
    if checkpoint is None:
        raise WorkflowError("workflow checkpoint is missing")
    if checkpoint.get("state") not in SYNTHETIC_STATES:
        raise WorkflowError("workflow checkpoint state is invalid")
    if checkpoint.get("target_sha256") != _target_binding(context):
        raise WorkflowError("workflow checkpoint target binding changed")
    if checkpoint.get("plan_sha256") != digest(run / "plan.json"):
        raise WorkflowError("workflow checkpoint plan digest changed")
    if checkpoint.get("approval_sha256") != digest(run / "approval.json"):
        raise WorkflowError("workflow checkpoint approval digest changed")
    if checkpoint.get("action_sha256") != _digest_value(action) or checkpoint.get("risk") != risk:
        raise WorkflowError("workflow checkpoint action changed")
    if checkpoint.get("action_attempts") != 1:
        raise WorkflowError("workflow checkpoint action attempt invariant is invalid")
    return checkpoint


def execute_synthetic_action(
    run: Path,
    context: dict[str, str],
    *,
    action: str,
    risk: str,
    now: int,
    interrupt_after: str | None = None,
) -> dict[str, Any]:
    """Execute a no-I/O synthetic tracer; it never calls OCI or ``run_action``."""
    validate_approval(run, context, action=action, risk=risk, now=now)
    if _checkpoint(run) is not None:
        raise WorkflowError("workflow checkpoint already exists; use resume")
    checkpoint = _new_checkpoint(run, context, action, risk)
    _write_checkpoint(run, checkpoint)
    if interrupt_after == "action-recorded":
        return checkpoint
    if interrupt_after is not None:
        raise WorkflowError("unsupported synthetic interruption point")
    return resume_synthetic_action(run, context, action=action, risk=risk, now=now)


def resume_synthetic_action(
    run: Path,
    context: dict[str, str],
    *,
    action: str,
    risk: str,
    now: int,
) -> dict[str, Any]:
    """Advance verification only; never repeat a recorded synthetic action."""
    checkpoint = _validate_checkpoint(run, context, action, risk, now)
    if checkpoint["state"] == "compensated":
        raise WorkflowError("compensated workflow requires a new plan")
    if checkpoint["state"] == "outcome-verified":
        return checkpoint
    checkpoint["state"] = "provider-verified"
    checkpoint["provider_evidence"] = "synthetic-verified"
    _write_checkpoint(run, checkpoint)
    checkpoint["state"] = "outcome-verified"
    checkpoint["outcome_evidence"] = "synthetic-verified"
    _write_checkpoint(run, checkpoint)
    return checkpoint


def compensate_synthetic_action(run: Path, context: dict[str, str]) -> dict[str, Any]:
    """Record compensation without re-invoking an action or contacting OCI."""
    _load_plan(run)
    checkpoint = _checkpoint(run)
    if checkpoint is None or checkpoint.get("target_sha256") != _target_binding(context):
        raise WorkflowError("workflow checkpoint target binding changed")
    if checkpoint.get("plan_sha256") != digest(run / "plan.json"):
        raise WorkflowError("workflow checkpoint plan digest changed")
    if checkpoint.get("approval_sha256") != digest(run / "approval.json"):
        raise WorkflowError("workflow checkpoint approval digest changed")
    if checkpoint.get("state") == "compensated":
        raise WorkflowError("compensated workflow requires a new plan")
    if checkpoint.get("state") not in {"action-recorded", "provider-verified", "outcome-verified"}:
        raise WorkflowError("workflow checkpoint state cannot be compensated")
    if checkpoint.get("action_attempts") != 1 or checkpoint.get("provider_contacted") is not False:
        raise WorkflowError("workflow checkpoint compensation invariant is invalid")
    checkpoint["state"] = "compensated"
    checkpoint["outcome_evidence"] = "compensated-synthetic"
    _write_checkpoint(run, checkpoint)
    return checkpoint


def _load_fake_canary_checkpoint(run: Path, context: dict[str, str]) -> dict[str, Any]:
    plan = _load_plan(run)
    if plan["journey"] != "approved-canary-deploy-verify-rollback":
        raise WorkflowError("plan is not an approved canary workflow")
    checkpoint = _checkpoint(run)
    if checkpoint is None or checkpoint.get("journey") != plan["journey"]:
        raise WorkflowError("canary checkpoint is missing")
    if checkpoint.get("target_sha256") != _target_binding(context):
        raise WorkflowError("workflow checkpoint target binding changed")
    if checkpoint.get("plan_sha256") != digest(run / "plan.json"):
        raise WorkflowError("workflow checkpoint plan digest changed")
    return checkpoint


def execute_fake_canary(
    run: Path, context: dict[str, str], *, action: str, risk: str, now: int
) -> dict[str, Any]:
    """Advance the deploy gate using a fake provider; it has no OCI side effect."""
    plan = _load_plan(run)
    if plan["journey"] != "approved-canary-deploy-verify-rollback":
        raise WorkflowError("plan is not an approved canary workflow")
    validate_approval(run, context, action=action, risk=risk, now=now)
    if _checkpoint(run) is not None:
        raise WorkflowError("workflow checkpoint already exists; use resume")
    checkpoint = _new_checkpoint(run, context, action, risk)
    checkpoint["state"] = "provider-verified"
    checkpoint["provider_evidence"] = "fake-provider-verified"
    _write_checkpoint(run, checkpoint)
    return checkpoint


def verify_fake_canary_outcome(run: Path, context: dict[str, str]) -> dict[str, Any]:
    """Record a separate local downstream-outcome checkpoint for the fake canary."""
    checkpoint = _load_fake_canary_checkpoint(run, context)
    if checkpoint.get("state") != "provider-verified":
        raise WorkflowError("canary provider verification is required before outcome verification")
    checkpoint["state"] = "outcome-verified"
    checkpoint["outcome_evidence"] = "fake-outcome-verified"
    _write_checkpoint(run, checkpoint)
    return checkpoint


def rollback_fake_canary(run: Path, context: dict[str, str]) -> dict[str, Any]:
    """Verify fake disposable cleanup only after a distinct outcome checkpoint."""
    checkpoint = _load_fake_canary_checkpoint(run, context)
    if checkpoint.get("state") != "outcome-verified":
        raise WorkflowError("canary outcome verification is required before rollback")
    checkpoint["state"] = "rollback-verified"
    checkpoint["teardown_evidence"] = "fake-cleanup-verified"
    _write_checkpoint(run, checkpoint)
    return checkpoint


def _read_input(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise WorkflowError(f"{label} must be a regular non-symlink JSON file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise WorkflowError(f"{label} must be a JSON object")
    return value


def main(argv: list[str] | None = None) -> int:
    """Expose the same offline runner contract to the CLI adapter."""
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan_parser = commands.add_parser("plan")
    plan_parser.add_argument("run", type=Path)
    plan_parser.add_argument("--context", type=Path, required=True)
    plan_parser.add_argument("--inventory", type=Path, required=True)
    governance_parser = commands.add_parser("plan-governance-pack")
    governance_parser.add_argument("run", type=Path)
    governance_parser.add_argument("--context", type=Path, required=True)
    governance_parser.add_argument("--owner", required=True)
    governance_parser.add_argument("--inventory", type=Path, required=True)
    data_parser = commands.add_parser("plan-data-acceptance-pack")
    data_parser.add_argument("run", type=Path)
    data_parser.add_argument("--context", type=Path, required=True)
    data_parser.add_argument("--owner", required=True)
    data_parser.add_argument("--inventory", type=Path, required=True)
    delivery_parser = commands.add_parser("plan-delivery-acceptance-pack")
    delivery_parser.add_argument("run", type=Path)
    delivery_parser.add_argument("--context", type=Path, required=True)
    delivery_parser.add_argument("--owner", required=True)
    delivery_parser.add_argument("--inventory", type=Path, required=True)
    stateful_parser = commands.add_parser("plan-stateful-acceptance-pack")
    stateful_parser.add_argument("run", type=Path)
    stateful_parser.add_argument("--context", type=Path, required=True)
    stateful_parser.add_argument("--owner", required=True)
    stateful_parser.add_argument("--inventory", type=Path, required=True)
    final_parser = commands.add_parser("plan-final-acceptance-pack")
    final_parser.add_argument("run", type=Path)
    final_parser.add_argument("--context", type=Path, required=True)
    final_parser.add_argument("--owner", required=True)
    final_parser.add_argument("--inventory", type=Path, required=True)
    execute_parser = commands.add_parser("execute-readonly")
    execute_parser.add_argument("run", type=Path)
    resume_parser = commands.add_parser("resume")
    resume_parser.add_argument("run", type=Path)
    resume_parser.add_argument("--context", type=Path, required=True)
    canary_plan_parser = commands.add_parser("plan-fake-canary")
    canary_plan_parser.add_argument("run", type=Path)
    canary_plan_parser.add_argument("--context", type=Path, required=True)
    canary_plan_parser.add_argument("--owner", required=True)
    canary_plan_parser.add_argument("--resource", required=True)
    canary_plan_parser.add_argument("--blast-radius", required=True)
    canary_plan_parser.add_argument("--cost-boundary", required=True)
    approval_parser = commands.add_parser("record-approval")
    approval_parser.add_argument("run", type=Path)
    approval_parser.add_argument("--context", type=Path, required=True)
    approval_parser.add_argument("--action", required=True)
    approval_parser.add_argument("--risk", required=True)
    approval_parser.add_argument("--issued-at", type=int, required=True)
    approval_parser.add_argument("--expires-at", type=int, required=True)
    fake_execute_parser = commands.add_parser("execute-fake-canary")
    fake_execute_parser.add_argument("run", type=Path)
    fake_execute_parser.add_argument("--context", type=Path, required=True)
    fake_execute_parser.add_argument("--action", required=True)
    fake_execute_parser.add_argument("--risk", required=True)
    fake_execute_parser.add_argument("--now", type=int, required=True)
    fake_outcome_parser = commands.add_parser("verify-fake-outcome")
    fake_outcome_parser.add_argument("run", type=Path)
    fake_outcome_parser.add_argument("--context", type=Path, required=True)
    fake_rollback_parser = commands.add_parser("rollback-fake-canary")
    fake_rollback_parser.add_argument("run", type=Path)
    fake_rollback_parser.add_argument("--context", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            payload = create_plan(
                args.run,
                _read_input(args.context, "context"),
                inventory=_read_input(args.inventory, "inventory"),
            )
        elif args.command == "plan-governance-pack":
            payload = create_governance_acceptance_pack(
                args.run,
                _read_input(args.context, "context"),
                owner=args.owner,
                inventory=_read_input(args.inventory, "inventory"),
            )
        elif args.command == "plan-data-acceptance-pack":
            payload = create_data_acceptance_pack(
                args.run,
                _read_input(args.context, "context"),
                owner=args.owner,
                inventory=_read_input(args.inventory, "inventory"),
            )
        elif args.command == "plan-delivery-acceptance-pack":
            payload = create_delivery_acceptance_pack(
                args.run,
                _read_input(args.context, "context"),
                owner=args.owner,
                inventory=_read_input(args.inventory, "inventory"),
            )
        elif args.command == "plan-stateful-acceptance-pack":
            payload = create_stateful_acceptance_pack(
                args.run,
                _read_input(args.context, "context"),
                owner=args.owner,
                inventory=_read_input(args.inventory, "inventory"),
            )
        elif args.command == "plan-final-acceptance-pack":
            payload = create_final_acceptance_pack(
                args.run,
                _read_input(args.context, "context"),
                owner=args.owner,
                inventory=_read_input(args.inventory, "inventory"),
            )
        elif args.command == "execute-readonly":
            payload = execute_readonly(args.run)
        elif args.command == "resume":
            payload = resume(args.run, _read_input(args.context, "context"))
        elif args.command == "plan-fake-canary":
            payload = create_fake_canary_plan(
                args.run, _read_input(args.context, "context"), owner=args.owner,
                resource=args.resource, blast_radius=args.blast_radius, cost_boundary=args.cost_boundary,
            )
        elif args.command == "record-approval":
            payload = record_approval(
                args.run, _read_input(args.context, "context"), action=args.action, risk=args.risk,
                issued_at=args.issued_at, expires_at=args.expires_at,
            )
        elif args.command == "execute-fake-canary":
            payload = execute_fake_canary(
                args.run, _read_input(args.context, "context"), action=args.action,
                risk=args.risk, now=args.now,
            )
        elif args.command == "verify-fake-outcome":
            payload = verify_fake_canary_outcome(args.run, _read_input(args.context, "context"))
        else:
            payload = rollback_fake_canary(args.run, _read_input(args.context, "context"))
    except WorkflowError as exc:
        print(f"error: {exc}", file=os.sys.stderr)
        return 1
    print(json.dumps(payload, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

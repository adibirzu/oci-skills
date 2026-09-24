"""Offline contracts for ER-010 through ER-012's first tracer workflow."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "enterprise_workflow", ROOT / "scripts" / "enterprise_workflow.py"
)
assert SPEC and SPEC.loader
enterprise_workflow = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(enterprise_workflow)


def _context() -> dict[str, str]:
    return {
        "context": "synthetic-readonly",
        "region": "eu-frankfurt-1",
        "compartment": "synthetic-compartment",
    }


def test_readonly_diagnose_to_plan_is_typed_and_sanitized(tmp_path: Path) -> None:
    run = tmp_path / "run"
    plan = enterprise_workflow.create_plan(
        run, _context(), inventory={"items": ["one"], "complete": True},
    )
    assert plan["risk"] == "none"
    assert plan["state"] == "planned"
    assert plan["target_sha256"]
    assert "synthetic-compartment" not in json.dumps(plan)

    result = enterprise_workflow.execute_readonly(run)
    assert result["state"] == "verified"
    assert result["evidence_class"] == "locally-verified"
    assert result["plan_sha256"] == enterprise_workflow.digest(run / "plan.json")


@pytest.mark.parametrize("complete", [False, None])
def test_partial_or_unknown_inventory_fails_closed(tmp_path: Path, complete: bool | None) -> None:
    inventory = {"items": [], "complete": complete}
    with pytest.raises(enterprise_workflow.WorkflowError, match="complete"):
        enterprise_workflow.create_plan(tmp_path / "run", _context(), inventory=inventory)


@pytest.mark.parametrize("collection_status", ["unknown", "partial", "rate-limited", "untrusted"])
def test_readonly_plan_distinguishes_unsafe_collection_states(
    tmp_path: Path, collection_status: str
) -> None:
    inventory = {
        "items": [],
        "complete": True,
        "freshness": "current",
        "scope": "bounded",
        "collection_status": collection_status,
    }
    with pytest.raises(enterprise_workflow.WorkflowError, match=collection_status):
        enterprise_workflow.create_plan(tmp_path / collection_status, _context(), inventory=inventory)


def test_readonly_plan_carries_only_aggregate_collection_and_planning_metadata(
    tmp_path: Path,
) -> None:
    plan = enterprise_workflow.create_plan(
        tmp_path / "run",
        _context(),
        inventory={
            "items": ["one", "two"],
            "complete": True,
            "freshness": "current",
            "scope": "bounded",
            "collection_status": "complete",
            "pagination": "complete",
            "collection_error_count": 0,
            "source_authority": "trusted",
            "dependency_state": "known",
            "cost_boundary": "zero-external-spend",
        },
    )
    assert plan["inventory"] == {
        "complete": True,
        "item_count": 2,
        "freshness": "current",
        "scope": "bounded",
        "collection_status": "complete",
        "pagination": "complete",
        "collection_error_count": 0,
        "source_authority": "trusted",
        "dependency_state": "known",
        "cost_boundary": "zero-external-spend",
    }
    assert plan["cost_boundary"] == "zero-external-spend"
    assert plan["expected_evidence"] == "bounded-current-inventory-and-typed-plan"


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("pagination", "partial", "pagination"),
        ("collection_error_count", 1, "collection errors"),
        ("source_authority", "untrusted", "authority"),
    ],
)
def test_readonly_plan_refuses_incomplete_collection_metadata(
    tmp_path: Path, field: str, value: object, message: str
) -> None:
    inventory: dict[str, object] = {
        "items": [], "complete": True, "freshness": "current", "scope": "bounded",
        "collection_status": "complete", "pagination": "complete",
        "collection_error_count": 0, "source_authority": "trusted",
        "dependency_state": "known", "cost_boundary": "zero-external-spend",
    }
    inventory[field] = value
    with pytest.raises(enterprise_workflow.WorkflowError, match=message):
        enterprise_workflow.create_plan(tmp_path / "run", _context(), inventory=inventory)  # type: ignore[arg-type]


def test_resume_rejects_changed_target_or_plan_digest(tmp_path: Path) -> None:
    run = tmp_path / "run"
    enterprise_workflow.create_plan(run, _context(), inventory={"items": [], "complete": True})
    enterprise_workflow.execute_readonly(run)
    assert enterprise_workflow.resume(run, _context())["state"] == "verified"

    drifted = dict(_context(), region="us-ashburn-1")
    with pytest.raises(enterprise_workflow.WorkflowError, match="target"):
        enterprise_workflow.resume(run, drifted)

    result_path = run / "result.json"
    value = json.loads(result_path.read_text(encoding="utf-8"))
    value["plan_sha256"] = "0" * 64
    result_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(enterprise_workflow.WorkflowError, match="plan"):
        enterprise_workflow.resume(run, _context())


def test_runner_never_accepts_raw_values_or_mutation_risk(tmp_path: Path) -> None:
    with pytest.raises(enterprise_workflow.WorkflowError, match="risk"):
        enterprise_workflow.create_plan(
            tmp_path / "run", _context(), inventory={"items": [], "complete": True}, risk="additive"
        )
    with pytest.raises(enterprise_workflow.WorkflowError, match="safe metadata"):
        enterprise_workflow.create_plan(
            tmp_path / "run", _context(), inventory={"items": [], "complete": True, "raw_response": "forbidden"}
        )


def test_cli_adapter_emits_the_same_sanitized_contract(tmp_path: Path) -> None:
    context = tmp_path / "context.json"
    inventory = tmp_path / "inventory.json"
    context.write_text(json.dumps(_context()), encoding="utf-8")
    inventory.write_text(json.dumps({"items": ["one"], "complete": True}), encoding="utf-8")
    script = ROOT / "scripts" / "enterprise_workflow.py"
    run = tmp_path / "run"
    plan = subprocess.run(
        [sys.executable, str(script), "plan", str(run), "--context", str(context), "--inventory", str(inventory)],
        text=True, capture_output=True, check=True,
    )
    assert "synthetic-compartment" not in plan.stdout
    execute = subprocess.run(
        [sys.executable, str(script), "execute-readonly", str(run)],
        text=True, capture_output=True, check=True,
    )
    assert json.loads(execute.stdout)["provider_contacted"] is False


def test_sdk_and_mcp_adapters_emit_the_same_readonly_plan_contract(tmp_path: Path) -> None:
    """ER-010: adapter labels cannot create a second planning or safety path."""
    context = _context()
    inventory = {"items": ["one"], "complete": True}
    sdk = enterprise_workflow.create_plan(tmp_path / "sdk", context, inventory=inventory)
    mcp = enterprise_workflow.create_mcp_plan(
        tmp_path / "mcp", {"context": context, "inventory": inventory}
    )
    context_path, inventory_path = tmp_path / "context.json", tmp_path / "inventory.json"
    context_path.write_text(json.dumps(context), encoding="utf-8")
    inventory_path.write_text(json.dumps(inventory), encoding="utf-8")
    cli = subprocess.run(
        [
            sys.executable, str(ROOT / "scripts" / "enterprise_workflow.py"), "plan",
            str(tmp_path / "cli"), "--context", str(context_path), "--inventory", str(inventory_path),
        ],
        text=True, capture_output=True, check=True,
    )
    assert sdk == mcp == json.loads(cli.stdout)
    assert sdk["target_sha256"]
    assert "synthetic-compartment" not in json.dumps(mcp)


@pytest.mark.parametrize(
    "mcp_request",
    [
        {"context": _context()},
        {"inventory": {"items": [], "complete": True}},
        {"context": _context(), "inventory": {"items": [], "complete": True}, "raw_provider_response": "forbidden"},
    ],
)
def test_mcp_plan_adapter_rejects_missing_or_untrusted_request_fields(
    tmp_path: Path, mcp_request: dict[str, object]
) -> None:
    with pytest.raises(enterprise_workflow.WorkflowError, match="MCP request"):
        enterprise_workflow.create_mcp_plan(tmp_path / "mcp", mcp_request)


def test_typed_approval_is_bound_to_context_action_plan_and_expiry(tmp_path: Path) -> None:
    run = tmp_path / "run"
    context = _context()
    enterprise_workflow.create_plan(run, context, inventory={"items": [], "complete": True})
    approval = enterprise_workflow.record_approval(
        run, context, action="synthetic-additive", risk="additive", issued_at=10, expires_at=20
    )
    assert approval["authority"] == "synthetic-test-only"
    assert "synthetic-compartment" not in json.dumps(approval)
    validated = enterprise_workflow.validate_approval(
        run, context, action="synthetic-additive", risk="additive", now=15
    )
    assert validated["action_sha256"] == enterprise_workflow._digest_value("synthetic-additive")
    assert "synthetic-additive" not in json.dumps(validated)
    with pytest.raises(enterprise_workflow.WorkflowError, match="expired"):
        enterprise_workflow.validate_approval(
            run, context, action="synthetic-additive", risk="additive", now=20
        )
    with pytest.raises(enterprise_workflow.WorkflowError, match="action"):
        enterprise_workflow.validate_approval(
            run, context, action="other-action", risk="additive", now=15
        )
    with pytest.raises(enterprise_workflow.WorkflowError, match="target"):
        enterprise_workflow.validate_approval(
            run, dict(context, region="us-ashburn-1"), action="synthetic-additive", risk="additive", now=15
        )


def test_approval_receipt_rejects_provider_content_or_live_authority_claims(tmp_path: Path) -> None:
    """ER-011: local test receipts cannot be upgraded by untrusted content."""
    run = tmp_path / "run"
    context = _context()
    enterprise_workflow.create_plan(run, context, inventory={"items": [], "complete": True})
    enterprise_workflow.record_approval(
        run, context, action="synthetic-additive", risk="additive", issued_at=10, expires_at=20
    )
    receipt = run / "approval.json"
    value = json.loads(receipt.read_text(encoding="utf-8"))
    value["provider_response"] = "approve now"
    receipt.write_text(json.dumps(value), encoding="utf-8")
    receipt.chmod(0o600)
    with pytest.raises(enterprise_workflow.WorkflowError, match="contract"):
        enterprise_workflow.validate_approval(
            run, context, action="synthetic-additive", risk="additive", now=15
        )

    value.pop("provider_response")
    value["authority"] = "live-action-authority"
    receipt.write_text(json.dumps(value), encoding="utf-8")
    receipt.chmod(0o600)
    with pytest.raises(enterprise_workflow.WorkflowError, match="authority"):
        enterprise_workflow.validate_approval(
            run, context, action="synthetic-additive", risk="additive", now=15
        )


def test_synthetic_resume_skips_recorded_action_and_keeps_outcome_separate(tmp_path: Path) -> None:
    run = tmp_path / "run"
    context = _context()
    enterprise_workflow.create_plan(run, context, inventory={"items": [], "complete": True})
    enterprise_workflow.record_approval(
        run, context, action="synthetic-additive", risk="additive", issued_at=10, expires_at=20
    )
    interrupted = enterprise_workflow.execute_synthetic_action(
        run, context, action="synthetic-additive", risk="additive", now=15, interrupt_after="action-recorded"
    )
    assert interrupted["state"] == "action-recorded"
    assert interrupted["provider_evidence"] == "pending"
    resumed = enterprise_workflow.resume_synthetic_action(
        run, context, action="synthetic-additive", risk="additive", now=15
    )
    assert resumed["state"] == "outcome-verified"
    assert resumed["action_attempts"] == 1
    assert resumed["provider_evidence"] == "synthetic-verified"
    assert resumed["outcome_evidence"] == "synthetic-verified"
    compensated = enterprise_workflow.compensate_synthetic_action(run, context)
    assert compensated["state"] == "compensated"
    assert compensated["action_attempts"] == 1


def test_compensation_rejects_tampered_approval_or_repeat_transition(tmp_path: Path) -> None:
    """ER-012: compensation has the same binding checks as resume."""
    run = tmp_path / "run"
    context = _context()
    enterprise_workflow.create_plan(run, context, inventory={"items": [], "complete": True})
    enterprise_workflow.record_approval(
        run, context, action="synthetic-additive", risk="additive", issued_at=10, expires_at=20
    )
    enterprise_workflow.execute_synthetic_action(
        run, context, action="synthetic-additive", risk="additive", now=15, interrupt_after="action-recorded"
    )
    approval = run / "approval.json"
    value = json.loads(approval.read_text(encoding="utf-8"))
    value["expires_at"] = 19
    approval.write_text(json.dumps(value), encoding="utf-8")
    approval.chmod(0o600)
    with pytest.raises(enterprise_workflow.WorkflowError, match="approval"):
        enterprise_workflow.compensate_synthetic_action(run, context)

    value["expires_at"] = 20
    approval.write_text(json.dumps(value), encoding="utf-8")
    approval.chmod(0o600)
    # The approval digest changed permanently, so a restart must use a fresh plan.
    with pytest.raises(enterprise_workflow.WorkflowError, match="approval"):
        enterprise_workflow.compensate_synthetic_action(run, context)


def test_fake_canary_keeps_provider_outcome_and_rollback_as_distinct_local_gates(
    tmp_path: Path,
) -> None:
    """ER-015's disposable journey is exercised without an OCI side effect."""
    run = tmp_path / "run"
    context = _context()
    plan = enterprise_workflow.create_fake_canary_plan(
        run,
        context,
        owner="terraform",
        resource="disposable-canary",
        blast_radius="single-disposable-resource",
        cost_boundary="zero-external-spend",
    )
    assert plan["journey"] == "approved-canary-deploy-verify-rollback"
    assert "disposable-canary" not in json.dumps(plan)

    with pytest.raises(enterprise_workflow.WorkflowError, match="approval"):
        enterprise_workflow.execute_fake_canary(
            run, context, action="deploy-disposable-canary", risk="additive", now=15
        )

    enterprise_workflow.record_approval(
        run, context, action="deploy-disposable-canary", risk="additive", issued_at=10, expires_at=20
    )
    deployed = enterprise_workflow.execute_fake_canary(
        run, context, action="deploy-disposable-canary", risk="additive", now=15
    )
    assert deployed["state"] == "provider-verified"
    assert deployed["provider_contacted"] is False
    assert deployed["outcome_evidence"] == "pending"

    outcome = enterprise_workflow.verify_fake_canary_outcome(run, context)
    assert outcome["state"] == "outcome-verified"
    rollback = enterprise_workflow.rollback_fake_canary(run, context)
    assert rollback["state"] == "rollback-verified"
    assert rollback["teardown_evidence"] == "fake-cleanup-verified"


def test_cli_fake_canary_emits_only_sanitized_local_evidence(tmp_path: Path) -> None:
    context = tmp_path / "context.json"
    context.write_text(json.dumps(_context()), encoding="utf-8")
    run = tmp_path / "run"
    script = ROOT / "scripts" / "enterprise_workflow.py"

    def invoke(*args: str) -> dict[str, object]:
        result = subprocess.run(
            [sys.executable, str(script), *args], text=True, capture_output=True, check=True
        )
        assert "disposable-canary" not in result.stdout
        assert "synthetic-compartment" not in result.stdout
        return json.loads(result.stdout)

    invoke(
        "plan-fake-canary", str(run), "--context", str(context), "--owner", "terraform",
        "--resource", "disposable-canary", "--blast-radius", "single-disposable-resource",
        "--cost-boundary", "zero-external-spend",
    )
    invoke(
        "record-approval", str(run), "--context", str(context), "--action", "deploy-disposable-canary",
        "--risk", "additive", "--issued-at", "10", "--expires-at", "20",
    )
    deployed = invoke(
        "execute-fake-canary", str(run), "--context", str(context), "--action", "deploy-disposable-canary",
        "--risk", "additive", "--now", "15",
    )
    assert deployed["state"] == "provider-verified"
    assert invoke("verify-fake-outcome", str(run), "--context", str(context))["state"] == "outcome-verified"
    assert invoke("rollback-fake-canary", str(run), "--context", str(context))["state"] == "rollback-verified"


def test_governance_acceptance_pack_is_typed_complete_and_manual_recovery_only(
    tmp_path: Path,
) -> None:
    run = tmp_path / "run"
    plan = enterprise_workflow.create_governance_acceptance_pack(
        run,
        _context(),
        owner="oci-data-safe",
        inventory={
            "complete": True,
            "freshness": "current",
            "scope": "bounded",
            "categories": {
                "assessment-diff": "present",
                "audit-ingestion": "empty",
            },
        },
    )
    assert plan["journey"] == "compare assessment and audit ingestion"
    assert plan["provider_contacted"] is False
    assert plan["evidence_class"] == "code-backed"
    assert plan["recovery"] == "manual-rescope-and-rerun"
    assert plan["inventory"]["categories"] == {
        "assessment-diff": "present",
        "audit-ingestion": "empty",
    }
    assert "synthetic-compartment" not in json.dumps(plan)


@pytest.mark.parametrize(
    "inventory, message",
    [
        ({"complete": False, "freshness": "current", "scope": "bounded", "categories": {}}, "complete"),
        ({"complete": True, "freshness": "current", "scope": "partial", "categories": {}}, "scope"),
        (
            {
                "complete": True,
                "freshness": "current",
                "scope": "bounded",
                "categories": {"assessment-diff": "present"},
            },
            "missing",
        ),
    ],
)
def test_governance_pack_refuses_partial_or_incomplete_inventory(
    tmp_path: Path, inventory: dict[str, object], message: str
) -> None:
    with pytest.raises(enterprise_workflow.WorkflowError, match=message):
        enterprise_workflow.create_governance_acceptance_pack(
            tmp_path / "run", _context(), owner="oci-data-safe", inventory=inventory
        )


def test_every_er016_owner_has_a_safe_typed_pack(tmp_path: Path) -> None:
    assert set(enterprise_workflow.GOVERNANCE_PACKS) == {
        "oci-administrator",
        "oci-iam-admin",
        "oci-security-compliance",
        "oci-aiops-agent-evaluation",
        "oci-data-safe",
        "oci-zpr-visibility",
    }
    for owner, pack in enterprise_workflow.GOVERNANCE_PACKS.items():
        assert pack["journey"]
        assert pack["permissions"]
        assert pack["provider_boundary"] in {"offline-only", "named-context-read-only"}
        assert pack["categories"]
        plan = enterprise_workflow.create_governance_acceptance_pack(
            tmp_path / owner,
            _context(),
            owner=owner,
            inventory={
                "complete": True,
                "freshness": "current",
                "scope": "bounded",
                "categories": {category: "present" for category in pack["categories"]},
            },
        )
        assert plan["owner"] == owner
        assert plan["provider_contacted"] is False


def test_governance_pack_cli_emits_sanitized_metadata_only_plan(tmp_path: Path) -> None:
    context = tmp_path / "context.json"
    inventory = tmp_path / "inventory.json"
    context.write_text(json.dumps(_context()), encoding="utf-8")
    inventory.write_text(
        json.dumps(
            {
                "complete": True,
                "freshness": "current",
                "scope": "bounded",
                "categories": {"controls": "present", "exceptions": "unavailable"},
            }
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "enterprise_workflow.py"),
            "plan-governance-pack",
            str(tmp_path / "run"),
            "--context",
            str(context),
            "--owner",
            "oci-security-compliance",
            "--inventory",
            str(inventory),
        ],
        text=True,
        capture_output=True,
        check=True,
    )
    plan = json.loads(result.stdout)
    assert plan["owner"] == "oci-security-compliance"
    assert plan["provider_contacted"] is False
    assert "synthetic-compartment" not in result.stdout


def test_data_acceptance_pack_keeps_observability_gates_and_markers_distinct(
    tmp_path: Path,
) -> None:
    stages = {
        "collection": "fresh",
        "storage": "fresh",
        "query": "fresh",
        "correlation": "fresh",
        "visualization": "fresh",
        "alerting": "fresh",
        "response": "fresh",
        "user-outcome": "fresh",
    }
    plan = enterprise_workflow.create_data_acceptance_pack(
        tmp_path / "run",
        _context(),
        owner="oci-observability-db",
        inventory={"complete": True, "freshness": "current", "scope": "bounded", "stages": stages},
    )
    assert plan["eligible_for_provider_outcome"] is True
    assert plan["stages"] == stages
    assert plan["provider_contacted"] is False
    assert "synthetic-compartment" not in json.dumps(plan)


def test_data_acceptance_pack_does_not_treat_resource_state_as_marker_evidence(tmp_path: Path) -> None:
    with pytest.raises(enterprise_workflow.WorkflowError, match="stages"):
        enterprise_workflow.create_data_acceptance_pack(
            tmp_path / "run",
            _context(),
            owner="oci-storage",
            inventory={
                "complete": True,
                "freshness": "current",
                "scope": "bounded",
                "stages": {"retention": "fresh", "restore-marker": "ACTIVE"},
            },
        )


def test_data_acceptance_pack_marks_missing_fresh_marker_ineligible_without_inference(
    tmp_path: Path,
) -> None:
    plan = enterprise_workflow.create_data_acceptance_pack(
        tmp_path / "run",
        _context(),
        owner="oci-autonomous-db",
        inventory={
            "complete": True,
            "freshness": "current",
            "scope": "bounded",
            "stages": {"connection": "fresh", "restore-marker": "missing"},
        },
    )
    assert plan["eligible_for_provider_outcome"] is False
    assert plan["failure_path"] == "fresh-marker-required-before-outcome-claim"


def test_every_er017_owner_has_marker_bound_outcome_gates(tmp_path: Path) -> None:
    assert set(enterprise_workflow.DATA_ACCEPTANCE_PACKS) == {
        "oci-observability-db",
        "oci-dbm-opsi",
        "oci-autonomous-db",
        "oci-database-cloud",
        "oci-storage",
        "oci-disaster-recovery",
        "oci-log-analytics",
        "oci-data-platform",
    }
    for owner, pack in enterprise_workflow.DATA_ACCEPTANCE_PACKS.items():
        plan = enterprise_workflow.create_data_acceptance_pack(
            tmp_path / owner,
            _context(),
            owner=owner,
            inventory={
                "complete": True,
                "freshness": "current",
                "scope": "bounded",
                "stages": {stage: "fresh" for stage in pack["stages"]},
            },
        )
        assert plan["eligible_for_provider_outcome"] is True
        assert plan["provider_contacted"] is False


def test_delivery_acceptance_pack_requires_named_context_derivations_and_outcomes(
    tmp_path: Path,
) -> None:
    plan = enterprise_workflow.create_delivery_acceptance_pack(
        tmp_path / "run",
        _context(),
        owner="oci-developer-services",
        inventory={
            "complete": True,
            "freshness": "current",
            "scope": "bounded",
            "context_derivations": {
                "architecture": "derived",
                "routes": "derived",
                "certificates": "derived",
                "identity": "derived",
                "target-cluster": "derived",
            },
            "outcomes": {
                "artifact-provenance": "fresh",
                "promotion-marker": "fresh",
                "rollback-health": "fresh",
            },
        },
    )
    assert plan["eligible_for_action"] is True
    assert plan["provider_contacted"] is False
    assert "synthetic-compartment" not in json.dumps(plan)


def test_delivery_pack_refuses_lifecycle_state_as_end_to_end_outcome(tmp_path: Path) -> None:
    with pytest.raises(enterprise_workflow.WorkflowError, match="outcomes"):
        enterprise_workflow.create_delivery_acceptance_pack(
            tmp_path / "run",
            _context(),
            owner="oci-events-functions",
            inventory={
                "complete": True,
                "freshness": "current",
                "scope": "bounded",
                "context_derivations": {
                    "architecture": "derived",
                    "routes": "derived",
                    "certificates": "derived",
                    "identity": "derived",
                    "target-cluster": "derived",
                },
                "outcomes": {
                    "delivery-marker": "ACTIVE",
                    "poison-retry-replay": "fresh",
                    "rollback-health": "fresh",
                },
            },
        )


def test_every_er018_owner_has_named_context_and_outcome_gates(tmp_path: Path) -> None:
    assert set(enterprise_workflow.DELIVERY_ACCEPTANCE_PACKS) == {
        "oci-bastion-access",
        "oci-networking-compute",
        "oci-oke-admin",
        "oci-events-functions",
        "oci-os-management",
        "oci-developer-services",
    }
    derivations = {field: "derived" for field in enterprise_workflow.CONTEXT_DERIVATIONS}
    for owner, pack in enterprise_workflow.DELIVERY_ACCEPTANCE_PACKS.items():
        plan = enterprise_workflow.create_delivery_acceptance_pack(
            tmp_path / owner,
            _context(),
            owner=owner,
            inventory={
                "complete": True,
                "freshness": "current",
                "scope": "bounded",
                "context_derivations": derivations,
                "outcomes": {outcome: "fresh" for outcome in pack["outcomes"]},
            },
        )
        assert plan["eligible_for_action"] is True
        assert plan["provider_contacted"] is False


def test_stateful_acceptance_pack_binds_owner_migration_and_evidence_to_one_candidate(
    tmp_path: Path,
) -> None:
    candidate = "a" * 64
    plan = enterprise_workflow.create_stateful_acceptance_pack(
        tmp_path / "run",
        _context(),
        owner="oci-terraform-authoring",
        inventory={
            "complete": True,
            "freshness": "current",
            "scope": "bounded",
            "resource_owner": "terraform",
            "migration_path": "reviewed",
            "candidate_sha256": candidate,
            "evidence": {kind: candidate for kind in enterprise_workflow.STATEFUL_EVIDENCE},
        },
    )
    assert plan["candidate_sha256"] == candidate
    assert set(plan["evidence"]) == set(enterprise_workflow.STATEFUL_EVIDENCE)
    assert plan["eligible_for_action"] is True
    assert "synthetic-compartment" not in json.dumps(plan)


def test_stateful_pack_rejects_owner_conflict_or_split_evidence_digest(tmp_path: Path) -> None:
    candidate = "a" * 64
    inventory = {
        "complete": True,
        "freshness": "current",
        "scope": "bounded",
        "resource_owner": "cli",
        "migration_path": "reviewed",
        "candidate_sha256": candidate,
        "evidence": {kind: candidate for kind in enterprise_workflow.STATEFUL_EVIDENCE},
    }
    with pytest.raises(enterprise_workflow.WorkflowError, match="owner"):
        enterprise_workflow.create_stateful_acceptance_pack(
            tmp_path / "owner", _context(), owner="oci-terraform-authoring", inventory=inventory
        )
    inventory["resource_owner"] = "terraform"
    inventory["evidence"]["teardown"] = "b" * 64
    with pytest.raises(enterprise_workflow.WorkflowError, match="candidate"):
        enterprise_workflow.create_stateful_acceptance_pack(
            tmp_path / "split", _context(), owner="oci-terraform-authoring", inventory=inventory
        )


def test_every_er019_owner_has_single_owner_and_candidate_bound_evidence(tmp_path: Path) -> None:
    assert set(enterprise_workflow.STATEFUL_ACCEPTANCE_PACKS) == {
        "oci-cost",
        "oci-resource-manager",
        "oci-terraform-authoring",
        "oci-project",
        "oci-product-development",
        "oci-application-engineering",
    }
    candidate = "c" * 64
    for owner, pack in enterprise_workflow.STATEFUL_ACCEPTANCE_PACKS.items():
        plan = enterprise_workflow.create_stateful_acceptance_pack(
            tmp_path / owner,
            _context(),
            owner=owner,
            inventory={
                "complete": True,
                "freshness": "current",
                "scope": "bounded",
                "resource_owner": pack["resource_owner"],
                "migration_path": "reviewed",
                "candidate_sha256": candidate,
                "evidence": {kind: candidate for kind in enterprise_workflow.STATEFUL_EVIDENCE},
            },
        )
        assert plan["candidate_sha256"] == candidate
        assert plan["resource_owner"] == pack["resource_owner"]
        assert plan["provider_contacted"] is False


def test_final_acceptance_pack_binds_sanitized_diagram_snapshot_and_reviews(tmp_path: Path) -> None:
    plan = enterprise_workflow.create_final_acceptance_pack(
        tmp_path / "run",
        _context(),
        owner="oci-diagramming",
        inventory={
            "complete": True,
            "freshness": "current",
            "scope": "bounded",
            "readiness": {"sanitized-snapshot": "present", "structural-review": "passed", "visual-review": "passed"},
            "snapshot_sha256": "a" * 64,
            "upstream": {"status": "absent"},
        },
    )
    assert plan["eligible_for_acceptance"] is True
    assert plan["snapshot_sha256"] == "a" * 64
    assert plan["provider_contacted"] is False


def test_final_acceptance_pack_records_available_or_absent_upstream_without_guessing(tmp_path: Path) -> None:
    base = {
        "complete": True,
        "freshness": "current",
        "scope": "bounded",
        "readiness": {"catalog": "present", "safe-abstention": "passed"},
        "snapshot_sha256": None,
    }
    absent = enterprise_workflow.create_final_acceptance_pack(
        tmp_path / "absent", _context(), owner="oci-developer-knowledge",
        inventory=dict(base, upstream={"status": "absent"}),
    )
    assert absent["upstream"] == {"status": "absent"}
    available = enterprise_workflow.create_final_acceptance_pack(
        tmp_path / "available", _context(), owner="oci-developer-knowledge",
        inventory=dict(base, upstream={"status": "available", "capability": "oci-oke", "revision": "0123456789ab"}),
    )
    assert available["upstream"]["revision"] == "0123456789ab"


def test_every_er020_owner_has_safe_readiness_and_unavailable_handoff_path(tmp_path: Path) -> None:
    assert set(enterprise_workflow.FINAL_ACCEPTANCE_PACKS) == {
        "oci-administrator",
        "oci-developer-knowledge",
        "oci-landing-zone",
        "oci-diagramming",
    }
    for owner, pack in enterprise_workflow.FINAL_ACCEPTANCE_PACKS.items():
        plan = enterprise_workflow.create_final_acceptance_pack(
            tmp_path / owner,
            _context(),
            owner=owner,
            inventory={
                "complete": True,
                "freshness": "current",
                "scope": "bounded",
                "readiness": dict(pack["readiness"]),
                "snapshot_sha256": "d" * 64 if pack["snapshot_required"] else None,
                "upstream": {"status": "absent"},
            },
        )
        assert plan["eligible_for_acceptance"] is True
        assert plan["upstream"] == {"status": "absent"}
        assert plan["provider_contacted"] is False

"""Contracts for the post-consolidation capability and usability review."""
from __future__ import annotations

import json
import pathlib
import re


ROOT = pathlib.Path(__file__).resolve().parent.parent
NEW_SKILLS = {
    "oci-storage": "storage.md",
    "oci-disaster-recovery": "disaster-recovery.md",
    "oci-aiops-agent-evaluation": "aiops-agent-evaluation.md",
}


def _text(path: pathlib.Path) -> str:
    return path.read_text(encoding="utf-8")


def test_storage_and_disaster_recovery_are_complete_discoverable_skills() -> None:
    for name, reference in NEW_SKILLS.items():
        root = ROOT / "skills" / name
        text = _text(root / "SKILL.md")
        frontmatter = text.split("---", 2)[1]
        assert re.findall(r"(?m)^([a-z][a-z0-9_-]*):", frontmatter) == ["name", "description"]
        assert f"name: {name}" in frontmatter
        assert "Use for" in frontmatter or "Use when" in frontmatter
        assert "## Common multi-step flows" in text
        assert "## Verification and rollback" in text
        assert f"../../references/{reference}" in text
        assert (ROOT / "references" / reference).is_file()
        assert (root / "agents" / "openai.yaml").is_file()


def test_storage_and_disaster_recovery_define_safe_ownership_boundaries() -> None:
    storage = _text(ROOT / "references" / "storage.md").lower()
    recovery = _text(ROOT / "references" / "disaster-recovery.md").lower()
    for term in (
        "object storage", "file storage", "block volume", "boot volume",
        "pre-authenticated request", "credential", "retention", "replication",
        "terraform", "oci_cli_help.py --json",
    ):
        assert term in storage
    for term in (
        "full stack disaster recovery", "protection group", "dr plan", "precheck",
        "switchover", "failover", "rto", "rpo", "destructive", "run_action",
    ):
        assert term in recovery
    for text in (storage, recovery):
        assert "read before write" in text
        assert "verification" in text
        assert "rollback" in text
        assert not re.search(r"(?m)^\s*(?:\$\s*)?oci\s+", text)


def test_network_edge_and_official_handoff_gaps_are_closed() -> None:
    networking = _text(ROOT / "skills" / "oci-networking-compute" / "SKILL.md").lower()
    router = _text(ROOT / "skills" / "oci-administrator" / "SKILL.md").lower()
    for term in ("dns", "traffic management", "health checks", "certificates"):
        assert term in networking
    for owner in ("oci/functions/oci-functions-deploy", "oci/functions/oci-functions-troubleshoot", "oci/iot-platform"):
        assert owner in router
    assert "local functions workstation" in router
    assert "iot" in router


def test_oke_mcp_safety_contract_is_documented() -> None:
    skill = _text(ROOT / "skills" / "oci-oke-admin" / "SKILL.md").lower()
    reference = _text(ROOT / "references" / "oke-operations.md").lower()
    combined = skill + "\n" + reference

    for term in (
        "optional read surface",
        "allow_only_readonly_tools",
        "allowed_tools",
        "mask_secrets",
        "helm template",
        "dns rebinding",
        "opentelemetry",
        "kubectl_generic",
        "node_management",
    ):
        assert term in combined

    assert "mcp is not a source of truth" in combined
    assert "mutations still use this pack's preflight" in combined


def test_oke_enhanced_cluster_operations_are_safe_and_discoverable() -> None:
    skill = _text(ROOT / "skills" / "oci-oke-admin" / "SKILL.md").lower()
    reference = _text(ROOT / "references" / "oke-operations.md").lower()
    docs = _text(ROOT / "references" / "oracle-docs.md").lower()
    combined = skill + "\n" + reference

    for term in (
        "enhanced clusters",
        "cluster add-ons",
        "oci_cli ce cluster list-addons",
        "oci_cli ce cluster get-addon",
        "workload identities",
        "native ingress controller",
        "readiness gate",
        "cycle the node pool",
        "out-of-place",
    ):
        assert term in combined

    for path in (
        "contengintroducingclusteraddons.htm",
        "contenggrantingworkload" "accesstoresources.htm",
        "contengsettingupnativeingresscontroller-troubleshooting.htm",
        "update-node-pool.htm",
    ):
        assert path in docs


def test_oke_demo_runtime_and_remote_validation_patterns_are_documented() -> None:
    skill = _text(ROOT / "skills" / "oci-oke-admin" / "SKILL.md").lower()
    reference = _text(ROOT / "references" / "oke-operations.md").lower()
    kb = _text(ROOT / "references" / "KB.md").lower()
    combined = skill + "\n" + reference

    for term in (
        "oke control-plane and rbac readiness",
        "kubectl --request-timeout=10s get --raw=/readyz",
        "legacy_kubernetes",
        "vcn_hostname",
        "python3 scripts/oci_cli_help.py --json ce cluster create-kubeconfig",
        "api-first fallback when ssh is blocked",
        "control-plane-oci",
        "resource search",
        "compute instance-agent command-execution list",
        "app agent privilege error",
        "instance-principal",
        "workload identity",
        "demo users may call",
        "invocation-owned ssh controlmaster",
        "browser profiles",
    ):
        assert term in combined

    for kb_id in ("kb-163", "kb-165", "kb-167", "kb-170"):
        assert kb_id in kb


def test_connection_flow_logs_and_shared_adb_patterns_are_documented() -> None:
    log_skill = _text(ROOT / "skills" / "oci-log-analytics" / "SKILL.md").lower()
    log_ref = _text(ROOT / "references" / "log-analytics.md").lower()
    adb_skill = _text(ROOT / "skills" / "oci-autonomous-db" / "SKILL.md").lower()
    adb_ref = _text(ROOT / "references" / "autonomous-db.md").lower()
    kb = _text(ROOT / "references" / "KB.md").lower()

    for term in (
        "vcn flow logs ingestion and connection investigations",
        "100% `all` / `include`",
        "exactly five 30-day subnet flow logs",
        "remove only the known failed empty flow log record",
        "logging-to-log-analytics connector",
        "network capture-filter create",
        "logging log create --log-type service",
        "source-ip connection errors",
        "connection-source investigations",
        "report coverage gaps separately from conclusions",
    ):
        assert term in (log_skill + "\n" + log_ref)

    for term in (
        "shared demo adb / atp / adw pattern",
        "least-privilege application schema/user",
        "migration-head check",
        "whitelisted-ips` replaces the whole list",
        "redacted readiness status",
    ):
        assert term in (adb_skill + "\n" + adb_ref)

    for kb_id in ("kb-164", "kb-166"):
        assert kb_id in kb


def test_oci_incident_troubleshooting_receipt_pattern_is_documented() -> None:
    log_skill = _text(ROOT / "skills" / "oci-log-analytics" / "SKILL.md").lower()
    log_ref = _text(ROOT / "references" / "log-analytics.md").lower()
    oke_ref = _text(ROOT / "references" / "oke-operations.md").lower()
    combined = log_skill + "\n" + log_ref + "\n" + oke_ref

    for term in (
        "oci incident troubleshooting receipt",
        "oci-skills.incident-troubleshooting-receipt.v1",
        "evidence_sources",
        "conclusion_level",
        "provider_verified",
        "configured",
        "unavailable",
        "inconclusive",
        "flow log ingestion proof",
        "source-ip ocl rows",
        "runtime principal check",
        "never infer a reachability verdict from missing sources",
    ):
        assert term in combined


def test_recent_app_facing_oci_errors_are_in_error_catalog() -> None:
    catalog = _text(ROOT / "references" / "oci-error-catalog.md").lower()

    for term in (
        "application-surfaced oci dependency errors",
        "a privileged role is required",
        "browser auth",
        "runtime principal",
        "dynamic group",
        "data source degraded",
        "logging-to-log-analytics connector",
        "oke control plane is unavailable",
        "control-plane-oci",
        "operator-access lane",
        "bounded `/readyz`",
        "not an oci api error by itself",
    ):
        assert term in catalog


def test_router_docs_catalog_and_evals_publish_the_29_skill_surface() -> None:
    catalog = json.loads(_text(ROOT / "docs" / "product" / "contracts" / "capability-catalog.json"))
    skills = {entry["skill"] for entry in catalog["capabilities"]}
    assert set(NEW_SKILLS) <= skills
    assert len(skills) == 29
    assert {"oci-data-platform", "oci-os-management"} <= skills

    router = _text(ROOT / "skills" / "oci-administrator" / "SKILL.md")
    readme = _text(ROOT / "README.md")
    architecture = _text(ROOT / "docs" / "ARCHITECTURE.md")
    quickstart = _text(ROOT / "docs" / "QUICKSTART.md")
    for text in (router, readme, architecture, quickstart):
        assert "29 skills" in text
    assert "twenty-two primary" in router.lower()
    assert "twenty-two primary" in readme.lower()

    cases = json.loads(_text(ROOT / "evals" / "evals.json"))["cases"]
    routes = {
        case["id"]: case["expect_route"]
        for case in cases
        if "expect_route" in case
    }
    behaviors = {
        case["id"]: case["expect_behavior"].lower()
        for case in cases
        if "expect_behavior" in case
    }
    assert routes["trigger-object-storage-lifecycle"] == "oci-storage"
    assert routes["trigger-file-storage"] == "oci-storage"
    assert routes["trigger-full-stack-dr"] == "oci-disaster-recovery"
    assert routes["negative-storage-volume-attachment"] == "oci-networking-compute"
    assert routes["negative-dr-data-guard"] == "oci-database-cloud"
    assert routes["trigger-data-integration-pipeline"] == "oci-data-platform"
    assert routes["trigger-os-management-hub-patching"] == "oci-os-management"
    assert routes["trigger-zpr-flow-correlation"] == "oci-zpr-visibility"
    assert routes["negative-zpr-nsg-rule"] == "oci-networking-compute"
    assert routes["negative-data-platform-object-storage"] == "oci-storage"
    assert routes["negative-os-management-instance-lifecycle"] == "oci-networking-compute"
    assert routes["trigger-oke-demo-agent-privilege-error"] == "oci-oke-admin"
    assert routes["trigger-oke-runtime-principal-readiness"] == "oci-oke-admin"
    assert routes["trigger-connection-source-degraded"] == "oci-log-analytics"
    assert routes["trigger-oke-control-plane-ssh-blocked"] == "oci-oke-admin"
    assert routes["trigger-melts-investigate-timeout"] == "oci-log-analytics"
    assert routes["trigger-oke-security-unavailable"] == "oci-oke-admin"
    assert routes["trigger-shared-demo-adb"] == "oci-autonomous-db"
    assert "browser authorization" in behaviors["trigger-oke-demo-agent-privilege-error"]
    assert "in-pod oci provider read" in behaviors["trigger-oke-runtime-principal-readiness"]
    assert "copied user credentials" in behaviors["trigger-oke-runtime-principal-readiness"]
    assert "logging-to-log-analytics connector" in behaviors["trigger-connection-source-degraded"]
    assert "five 30-day oke subnet flow logs" in behaviors["trigger-connection-source-degraded"]
    assert "degraded operator-access lane" in behaviors["trigger-oke-control-plane-ssh-blocked"]
    assert "incident troubleshooting receipt" in behaviors["trigger-melts-investigate-timeout"]
    assert "cached receipt" in behaviors["trigger-melts-investigate-timeout"]
    assert "security execution remain role-gated" in behaviors["trigger-oke-security-unavailable"]
    assert "least-privilege application schema/user" in behaviors["trigger-shared-demo-adb"]


def test_undercovered_domains_have_forward_behavior_matrices() -> None:
    prompts = json.loads(_text(ROOT / "evals" / "forward" / "prompts.json"))["prompts"]
    rubric = json.loads(_text(ROOT / "evals" / "forward" / "rubric.json"))["cases"]
    prompt_ids = {entry["id"] for entry in prompts}
    rubric_ids = {entry["id"] for entry in rubric}
    expected = {
        "data-platform-inventory",
        "data-platform-start-run",
        "data-platform-storage-boundary",
        "os-management-compliance",
        "os-management-update-job",
        "os-management-compute-boundary",
        "zpr-visibility-correlation",
        "zpr-policy-mutation",
        "zpr-networking-boundary",
    }
    assert expected <= prompt_ids
    assert expected <= rubric_ids


def test_release_candidate_metadata_describes_the_current_surface() -> None:
    manifests = [
        ROOT / ".claude-plugin" / "plugin.json",
        ROOT / ".codex-plugin" / "plugin.json",
        ROOT / "harness" / "gemini" / "gemini-extension.json",
    ]
    versions = {json.loads(_text(path))["version"] for path in manifests}
    marketplace = json.loads(_text(ROOT / ".claude-plugin" / "marketplace.json"))
    versions.add(marketplace["plugins"][0]["version"])
    assert versions == {"2.0.0-rc.3"}
    combined = " ".join(_text(path).lower() for path in manifests)
    for term in ("storage", "disaster recovery", "bastion", "landing zone"):
        assert term in combined

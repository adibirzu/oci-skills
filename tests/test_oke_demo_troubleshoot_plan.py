"""Contracts for the offline OKE demo troubleshooting command-plan helper."""
from __future__ import annotations

import json
import pathlib
import re
import subprocess


ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "oci_oke_demo_troubleshoot.py"


def _run(*args: str) -> dict[str, object]:
    result = subprocess.run(
        ["python3", str(SCRIPT), *args],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_oke_demo_troubleshoot_helper_emits_all_current_demo_failure_modes() -> None:
    payload = _run("all", "--context", "demo")

    assert payload["schema_version"] == "oci-skills.oke-demo-troubleshoot-bundle.v1"
    assert payload["context"] == "demo"
    assert payload["offline"] is True
    scenarios = {plan["scenario"]: plan for plan in payload["plans"]}  # type: ignore[index]
    assert set(scenarios) == {
        "privileged-role",
        "connections-degraded",
        "runtime-principal-readiness",
        "control-plane-blocked",
        "melts-investigate-timeout",
        "oke-security-unavailable",
        "shared-adb-readiness",
    }

    assert "runtime identity" in scenarios["privileged-role"]["intent"]
    assert "VCN Flow Log ingestion" in scenarios["connections-degraded"]["intent"]
    assert "OCI identity from inside the OKE runtime" in scenarios["runtime-principal-readiness"]["intent"]
    assert "degraded operator lane" in scenarios["control-plane-blocked"]["intent"]
    assert "MELTS investigations" in scenarios["melts-investigate-timeout"]["intent"]
    assert "OKE Security capability failure" in scenarios["oke-security-unavailable"]["intent"]
    assert "tenant-shared ADB/ATP/ADW" in scenarios["shared-adb-readiness"]["intent"]


def test_oke_demo_troubleshoot_helper_keeps_plans_redacted_and_non_executing() -> None:
    payload_text = json.dumps(_run("all"), sort_keys=True)

    assert "offline" in payload_text
    assert not re.search(r"ocid1\.[a-z0-9.-]+", payload_text)
    assert not re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", payload_text)
    assert "~/.oci" not in payload_text
    assert "browser profiles into a pod" in payload_text
    assert "Do not copy local OCI config" in payload_text
    assert "Never convert stale cached receipts" in payload_text
    assert "Do not grant cluster-admin" in payload_text
    assert "temporary admin passwords into the workload" in payload_text


def test_oke_demo_troubleshoot_helper_documents_safe_observability_enablement() -> None:
    plan = _run("connections-degraded")["plans"][0]  # type: ignore[index]
    combined = "\n".join(
        [
            *plan["read_only"],  # type: ignore[index]
            *plan["approval_gated_actions"],  # type: ignore[index]
            *plan["verification"],  # type: ignore[index]
            *plan["stop_conditions"],  # type: ignore[index]
        ]
    )

    for term in (
        "OCI VCN Flow Logs",
        "Source IP",
        "100% ALL/INCLUDE FLOWLOG capture filter",
        "failed empty Flow Log record",
        "exactly five 30-day subnet Flow Logs",
        "Logging-to-Log-Analytics connector",
        "Do not change NSGs",
    ):
        assert term in combined


def test_oke_demo_troubleshoot_helper_is_linked_from_skills_and_kb() -> None:
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            ROOT / "skills" / "oci-oke-admin" / "SKILL.md",
            ROOT / "skills" / "oci-log-analytics" / "SKILL.md",
            ROOT / "references" / "oke-operations.md",
            ROOT / "references" / "log-analytics.md",
            ROOT / "references" / "KB.md",
        )
    )

    assert "scripts/oci_oke_demo_troubleshoot.py" in combined
    for kb_id in ("KB-164", "KB-165", "KB-166", "KB-167", "KB-168", "KB-169"):
        assert kb_id in combined


def test_oke_demo_troubleshoot_helper_covers_melts_and_oke_security_failures() -> None:
    payload = _run("all", "--context", "demo")
    scenarios = {plan["scenario"]: plan for plan in payload["plans"]}  # type: ignore[index]

    melts = "\n".join(
        [
            *scenarios["melts-investigate-timeout"]["read_only"],  # type: ignore[index]
            *scenarios["melts-investigate-timeout"]["approval_gated_actions"],  # type: ignore[index]
            *scenarios["melts-investigate-timeout"]["verification"],  # type: ignore[index]
            *scenarios["melts-investigate-timeout"]["stop_conditions"],  # type: ignore[index]
        ]
    )
    security = "\n".join(
        [
            *scenarios["oke-security-unavailable"]["read_only"],  # type: ignore[index]
            *scenarios["oke-security-unavailable"]["approval_gated_actions"],  # type: ignore[index]
            *scenarios["oke-security-unavailable"]["verification"],  # type: ignore[index]
            *scenarios["oke-security-unavailable"]["stop_conditions"],  # type: ignore[index]
        ]
    )

    for term in (
        "MELTS investigate",
        "response-time budget",
        "incident-troubleshooting-receipt",
        "minimum evidence sources",
        "Never infer blocked, accepted, or harmless traffic",
    ):
        assert term in melts

    for term in (
        "OKE Security control plane unavailable",
        "runtime-principal policy",
        "signed-in browser/API security request",
        "remain role-gated",
        "Do not grant cluster-admin",
    ):
        assert term in security


def test_oke_demo_troubleshoot_helper_covers_runtime_principal_readiness() -> None:
    payload = _run("runtime-principal-readiness", "--context", "demo")
    plan = payload["plans"][0]  # type: ignore[index]
    combined = "\n".join(
        [
            *plan["read_only"],  # type: ignore[index]
            *plan["approval_gated_actions"],  # type: ignore[index]
            *plan["verification"],  # type: ignore[index]
            *plan["stop_conditions"],  # type: ignore[index]
        ]
    )

    for term in (
        "kubectl --request-timeout=10s get --raw=/readyz",
        "serviceAccountName",
        "OCI_RESOURCE_PRINCIPAL",
        "--auth instance_principal",
        "app/SDK read canary",
        "do not use --auth instance_principal as proof of Workload Identity",
        "workload-principal policy",
        "OCI Audit Logs",
        "smallest read-only policy",
        "server-side dry-run",
        "signed-in app request",
        "Do not treat a successful browser login",
    ):
        assert term in combined


def test_oke_demo_troubleshoot_helper_emits_redacted_receipt_template() -> None:
    payload = _run("receipt-template", "--context", "demo")
    payload_text = json.dumps(payload, sort_keys=True)

    assert payload["schema_version"] == "oci-skills.incident-troubleshooting-receipt.v1"
    assert payload["context"] == "demo"
    assert payload["offline"] is True
    assert payload["conclusion_level"] == "provider_verified|configured|unavailable|inconclusive"
    assert {entry["source"] for entry in payload["evidence_sources"]} == {  # type: ignore[index]
        "oke_api",
        "kubernetes_readyz_rbac_rollout",
        "runtime_principal",
        "vcn_flow_logs",
        "load_balancer_logs",
        "traces_monitoring_security",
    }
    for term in (
        "current rows or service API results support the claim",
        "source/tool/control-plane path is unreachable",
        "minimum evidence is missing",
        "READ_ONLY_RETRY_OR_REVIEWED_MUTATION",
    ):
        assert term in payload_text
    assert not re.search(r"ocid1\\.[a-z0-9.-]+", payload_text)
    assert not re.search(r"\\b\\d{1,3}(?:\\.\\d{1,3}){3}\\b", payload_text)


def test_oke_demo_troubleshoot_helper_covers_shared_adb_readiness() -> None:
    payload = _run("shared-adb-readiness", "--context", "demo")
    plan = payload["plans"][0]  # type: ignore[index]
    combined = "\n".join(
        [
            *plan["read_only"],  # type: ignore[index]
            *plan["approval_gated_actions"],  # type: ignore[index]
            *plan["verification"],  # type: ignore[index]
            *plan["stop_conditions"],  # type: ignore[index]
        ]
    )

    for term in (
        "shared demo ADB ATP ADW",
        "least-privilege application user/schema",
        "whitelisted-ips replacement is not append-only",
        "migration-head receipt",
        "SELECT 1 FROM dual",
        "score write/readback",
        "Do not create a dedicated ADB/ATP",
        "Do not use ADMIN as the long-running app user",
    ):
        assert term in combined

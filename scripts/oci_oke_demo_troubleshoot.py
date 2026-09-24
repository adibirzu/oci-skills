#!/usr/bin/env python3
"""Emit redacted OKE demo troubleshooting command plans.

This helper is intentionally offline. It does not read kubeconfig, OCI config,
environment variables, browser profiles, wallets, or network state. Its purpose
is to give agents a repeatable command ladder for the demo failure modes that
otherwise tend to collapse into unsafe shortcuts.
"""
from __future__ import annotations

import argparse
import json
from collections.abc import Iterable
from dataclasses import dataclass


DOCS = {
    "oke": "https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm",
    "access": "https://docs.oracle.com/en-us/iaas/Content/ContEng/Concepts/contengaboutaccesscontrol.htm",
    "kubeconfig": "https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengdownloadkubeconfigfile.htm",
    "flow_logs": "https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/vcn_flow_logs.htm",
    "logging": "https://docs.oracle.com/en-us/iaas/Content/Logging/home.htm",
    "service_connector": "https://docs.oracle.com/en-us/iaas/Content/connector-hub/home.htm",
    "log_analytics": "https://docs.oracle.com/en-us/iaas/log-analytics/home.htm",
    "run_command": "https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/runningcommands.htm",
    "monitoring": "https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm",
    "apm": "https://docs.oracle.com/en-us/iaas/application-performance-monitoring/home.htm",
    "cloud_guard": "https://docs.oracle.com/en-us/iaas/cloud-guard/home.htm",
    "adb": "https://docs.oracle.com/en-us/iaas/autonomous-database/index.html",
    "vault": "https://docs.oracle.com/en-us/iaas/Content/KeyManagement/Tasks/managingsecrets.htm",
}


@dataclass(frozen=True)
class Plan:
    scenario: str
    intent: str
    evidence_class: str
    read_only: tuple[str, ...]
    approval_gated_actions: tuple[str, ...]
    verification: tuple[str, ...]
    stop_conditions: tuple[str, ...]
    sources: tuple[str, ...]

    def as_dict(self, *, context: str) -> dict[str, object]:
        return {
            "schema_version": "oci-skills.oke-demo-troubleshoot-plan.v1",
            "context": context,
            "scenario": self.scenario,
            "intent": self.intent,
            "evidence_class": self.evidence_class,
            "placeholders": {
                "compartment_id": "<COMPARTMENT_OCID>",
                "cluster_id": "<OKE_CLUSTER_OCID>",
                "namespace": "<NAMESPACE>",
                "app": "<APP>",
                "service_account": "<SERVICE_ACCOUNT>",
                "runtime_principal": "<RUNTIME_PRINCIPAL>",
                "source_ip": "<SOURCE_IP>",
                "la_namespace": "<LA_NAMESPACE>",
            },
            "read_only": list(self.read_only),
            "approval_gated_actions": list(self.approval_gated_actions),
            "verification": list(self.verification),
            "stop_conditions": list(self.stop_conditions),
            "sources": list(self.sources),
        }


PLANS: dict[str, Plan] = {
    "privileged-role": Plan(
        scenario="privileged-role",
        intent=(
            "Separate browser route authorization from the pod's OCI runtime "
            "identity before changing any IAM policy."
        ),
        evidence_class="configured_or_provider_verified_only_after_current_reads",
        read_only=(
            "python3 scripts/kb_lookup.py \"A privileged role is required\" oke",
            "oci_cli ce cluster get --cluster-id \"<OKE_CLUSTER_OCID>\" --query 'data.{name:name,state:\"lifecycle-state\",\"kubernetes-version\":\"kubernetes-version\"}'",
            "kubectl --request-timeout=10s get --raw=/readyz",
            "kubectl -n \"<NAMESPACE>\" auth can-i get pods --as=system:serviceaccount:\"<NAMESPACE>\":\"<SERVICE_ACCOUNT>\"",
            "kubectl -n \"<NAMESPACE>\" get deployment \"<APP>\" -o jsonpath='{.spec.template.spec.serviceAccountName}'",
            "kubectl -n \"<NAMESPACE>\" get pods -l app=\"<APP>\" -o wide",
            "kubectl -n \"<NAMESPACE>\" logs deployment/\"<APP>\" --since=30m --all-containers --tail=200",
            "oci_cli iam dynamic-group list --compartment-id <TENANCY_OCID> --all --query 'data[].{name:name,description:description}'",
            "oci_cli iam policy list --compartment-id <COMPARTMENT_OCID> --all --query 'data[].{name:name,statements:statements}'",
        ),
        approval_gated_actions=(
            "If the app route is over-gated, update application authorization so signed-in users can call only the approved read/chat endpoints.",
            "If the pod identity lacks OCI read access, add the smallest dynamic-group or Workload Identity policy after a current preflight and approval.",
        ),
        verification=(
            "kubectl -n \"<NAMESPACE>\" rollout status deployment/\"<APP>\" --timeout=180s",
            "curl -skI \"https://<APP_HOST>/api/observeai/chat\"",
            "Run the same signed-in browser/API request that previously returned the privileged-role error.",
        ),
        stop_conditions=(
            "Do not copy local OCI config, kubeconfig, wallets, cookies, or browser profiles into a pod.",
            "Do not relax privileged mutation, deployment, security execution, SOC action, or Log Analytics write routes for demo users.",
        ),
        sources=(DOCS["oke"], DOCS["access"]),
    ),
    "connections-degraded": Plan(
        scenario="connections-degraded",
        intent=(
            "Prove VCN Flow Log ingestion before making source-IP or geo "
            "reachability conclusions."
        ),
        evidence_class="unavailable_until_flow_log_ingestion_and_source_ip_rows_are_current",
        read_only=(
            "python3 scripts/kb_lookup.py \"connection source degraded VCN Flow Logs\" log-analytics",
            "oci_cli logging log-group list --compartment-id <COMPARTMENT_OCID> --all",
            "oci_cli logging log list --compartment-id <COMPARTMENT_OCID> --log-group-id \"<LOG_GROUP_OCID>\" --all",
            "oci_cli network capture-filter list --compartment-id <COMPARTMENT_OCID> --all",
            "oci_cli sch service-connector list --compartment-id <COMPARTMENT_OCID> --all",
            "oci_cli network subnet list --compartment-id <COMPARTMENT_OCID> --vcn-id \"<VCN_OCID>\" --all",
            "./scripts/oci_logan.sh -q \"'Log Source' = 'OCI VCN Flow Logs' | stats count by 'Action' | sort -count\" -t 1h",
            "./scripts/oci_logan.sh -q \"'Log Source' = 'OCI VCN Flow Logs' and 'Source IP' = '<SOURCE_IP>' | stats count as requests by Action, 'Destination Port', 'Protocol', 'Rule Type', 'Rule Name' | sort -requests | head 50\" -t 24h",
        ),
        approval_gated_actions=(
            "Validate installed help for logging log create/update and network capture-filter create/update.",
            "Create or reuse one 100% ALL/INCLUDE FLOWLOG capture filter using a 0600 file:// rules payload.",
            "Remove only the confirmed failed empty Flow Log record with no usable source binding.",
            "Enable exactly five 30-day subnet Flow Logs for node, API endpoint, load-balancer, and two pod-network subnets through the existing Logging-to-Log-Analytics connector.",
        ),
        verification=(
            "./scripts/oci_logan.sh -q \"'Log Source' = 'OCI VCN Flow Logs' | stats count by 'Action' | sort -count\" -t 1h",
            "./scripts/oci_logan.sh -q \"'Log Source' = 'OCI VCN Flow Logs' and 'Source IP' = '<SOURCE_IP>' | stats count as requests by Action, 'Destination Port', 'Protocol', 'Rule Type', 'Rule Name' | sort -requests | head 50\" -t 24h",
            "Correlate only after Flow Log rows exist: Load Balancer Access Logs, Cloud Guard Problems, traces, Monitoring metrics, and Audit.",
        ),
        stop_conditions=(
            "Do not change NSGs, Security Lists, route tables, NAT gateways, or application traffic while adding observability.",
            "If the topology is not exactly node, endpoint, load-balancer, and two pod-network subnets, stop and report the mismatch.",
            "If the Logging-to-Log-Analytics connector is missing, report an enablement gate instead of creating a parallel connector path.",
        ),
        sources=(DOCS["flow_logs"], DOCS["logging"], DOCS["service_connector"], DOCS["log_analytics"]),
    ),
    "runtime-principal-readiness": Plan(
        scenario="runtime-principal-readiness",
        intent=(
            "Prove the app agent's OCI identity from inside the OKE runtime "
            "before changing IAM, RBAC, routes, or application code."
        ),
        evidence_class="configured_until_pod_runtime_probe_and_oci_audit_are_current",
        read_only=(
            "python3 scripts/kb_lookup.py \"runtime principal instance principal workload identity OKE app\" oke",
            "oci_cli ce cluster get --cluster-id \"<OKE_CLUSTER_OCID>\" --query 'data.{name:name,state:\"lifecycle-state\",\"cluster-pod-network-options\":\"cluster-pod-network-options\"}'",
            "kubectl --request-timeout=10s get --raw=/readyz",
            "kubectl -n \"<NAMESPACE>\" get deployment \"<APP>\" -o jsonpath='{.spec.template.spec.serviceAccountName}'",
            "kubectl -n \"<NAMESPACE>\" get serviceaccount \"<SERVICE_ACCOUNT>\" -o yaml",
            "kubectl -n \"<NAMESPACE>\" auth can-i get pods --as=system:serviceaccount:\"<NAMESPACE>\":\"<SERVICE_ACCOUNT>\"",
            "kubectl -n \"<NAMESPACE>\" logs deployment/\"<APP>\" --since=30m --all-containers --tail=200",
            "kubectl -n \"<NAMESPACE>\" exec deploy/\"<APP>\" -- env | grep '^OCI_RESOURCE_PRINCIPAL\\|^OCI_AUTH\\|^OCI_CONFIG_PROFILE' || true",
            "For managed-node instance-principal runtimes only: kubectl -n \"<NAMESPACE>\" exec deploy/\"<APP>\" -- oci iam region list --auth instance_principal --output table",
            "For OKE Workload Identity runtimes: run the app/SDK read canary that uses the workload identity provider; do not use --auth instance_principal as proof of Workload Identity.",
            "./scripts/oci_logan.sh -q \"'Log Source' = 'OCI Audit Logs' and 'Principal Name' like '*<RUNTIME_PRINCIPAL>*' | stats count by 'Event Name', Status | sort -count\" -t 1h",
        ),
        approval_gated_actions=(
            "If the runtime probe proves a missing instance-principal dynamic-group grant or workload-principal policy, add the smallest read-only policy for the named service family and compartment.",
            "If the pod service account is wrong, preview the Deployment/serviceAccountName patch with server-side dry-run before rollout.",
            "If browser route authorization is wrong, update only the approved read/chat routes; keep privileged mutations and security execution gated.",
        ),
        verification=(
            "Repeat the in-pod OCI read probe and confirm it succeeds without copied user credentials.",
            "Confirm OCI Audit rows show the intended instance-principal dynamic group or OKE workload principal.",
            "Replay the signed-in app request that failed with the privileged-role error.",
        ),
        stop_conditions=(
            "Do not grant cluster-admin, tenancy-wide manage-all-resources, or broad security-service manage policies for a demo fix.",
            "Do not mount operator OCI config directories, kubeconfig, wallets, browser cookies, or temporary admin passwords into the workload.",
            "Do not treat a successful browser login as evidence that the pod has OCI provider access.",
        ),
        sources=(DOCS["oke"], DOCS["access"], DOCS["log_analytics"]),
    ),
    "control-plane-blocked": Plan(
        scenario="control-plane-blocked",
        intent=(
            "Treat SSH or a named jump host failure as a degraded operator lane, "
            "not as an OCI service or application verdict."
        ),
        evidence_class="unavailable_for_ssh_lane_only_until_api_or_in_vcn_reads_succeed",
        read_only=(
            "python3 scripts/kb_lookup.py \"control-plane-oci SSH blocked\" oke",
            "oci_cli ce cluster get --cluster-id \"<OKE_CLUSTER_OCID>\" --query 'data.{name:name,state:\"lifecycle-state\",\"kubernetes-version\":\"kubernetes-version\",\"endpoint-config\":\"endpoint-config\"}'",
            "oci_cli search resource structured-search --query-text \"query containerenginecluster resources where identifier = '<OKE_CLUSTER_OCID>'\"",
            "kubectl --request-timeout=10s get --raw=/readyz",
            "oci_cli bastion bastion list --compartment-id <COMPARTMENT_OCID> --all --query 'data[].{name:name,state:\"lifecycle-state\"}'",
            "oci_cli compute instance-agent command-execution list --compartment-id <COMPARTMENT_OCID> --all --query 'data[].{instance:\"instance-id\",state:\"lifecycle-state\"}'",
        ),
        approval_gated_actions=(
            "Use Cloud Shell, a reviewed Bastion path, or OCI Run Command from an in-VCN managed instance only after the target and blast radius are explicit.",
            "For remote validation, transfer only reviewed source/test files; exclude env, .git, wallets, kubeconfigs, browser state, and credentials.",
        ),
        verification=(
            "Record which access lane produced current evidence: OCI API, kubectl /readyz, Cloud Shell, Bastion, or Run Command.",
            "Resume build/deploy/browser replay only after the selected lane returns bounded status without exposing secrets.",
        ),
        stop_conditions=(
            "Do not mark OKE, Log Analytics, the application, or a data source failed solely because SSH timed out.",
            "Do not use SSH ControlMaster sockets outside an invocation-owned /tmp path.",
        ),
        sources=(DOCS["oke"], DOCS["kubeconfig"], DOCS["run_command"]),
    ),
    "melts-investigate-timeout": Plan(
        scenario="melts-investigate-timeout",
        intent=(
            "Keep MELTS investigations grounded when the agent exceeds its "
            "response-time budget before all evidence sources return."
        ),
        evidence_class="inconclusive_until_minimum_current_evidence_sources_are_available",
        read_only=(
            "python3 scripts/kb_lookup.py \"MELTS investigate response-time budget source degraded\" log-analytics",
            "./scripts/oci_logan.sh -q \"'Log Source' = 'OCI VCN Flow Logs' | stats count by 'Action' | sort -count\" -t 1h",
            "./scripts/oci_logan.sh -q \"'Log Source' = 'OCI VCN Flow Logs' and 'Source IP' = '<SOURCE_IP>' | stats count as requests by Action, 'Destination Port', 'Protocol', 'Rule Type', 'Rule Name' | sort -requests | head 50\" -t 24h",
            "./scripts/oci_logan.sh -q \"'Log Source' = 'OCI Load Balancer Access Logs' and 'Client IP' = '<SOURCE_IP>' | stats count as requests by 'Status Code', 'Backend Status Code' | sort -requests\" -t 24h",
            "Validate installed help before rendering exact Monitoring, APM, Cloud Guard, or Audit query flags.",
        ),
        approval_gated_actions=(
            "Increase application-side investigation time and token budgets only after source availability and query limits are measured.",
            "Add or tune cached provider receipts for repeated source-IP investigations without replacing current provider reads.",
        ),
        verification=(
            "Produce an oci-skills.incident-troubleshooting-receipt.v1 receipt with VCN Flow Logs, traces, metrics, and security sources marked verified, empty, degraded, or unavailable.",
            "Retry the same MELTS prompt and confirm the answer is grounded in at least the minimum evidence sources or explicitly reports degraded sources.",
        ),
        stop_conditions=(
            "Never infer blocked, accepted, or harmless traffic from a timeout or missing source alone.",
            "Never convert stale cached receipts into provider_verified evidence.",
        ),
        sources=(DOCS["log_analytics"], DOCS["monitoring"], DOCS["apm"], DOCS["cloud_guard"]),
    ),
    "oke-security-unavailable": Plan(
        scenario="oke-security-unavailable",
        intent=(
            "Separate an app-facing OKE Security capability failure from OKE API, "
            "Kubernetes RBAC, OCI runtime-principal, and security-provider availability."
        ),
        evidence_class="unavailable_until_each_security_control_plane_dependency_is_checked",
        read_only=(
            "python3 scripts/kb_lookup.py \"OKE Security control plane unavailable privileged role\" oke",
            "oci_cli ce cluster get --cluster-id \"<OKE_CLUSTER_OCID>\" --query 'data.{name:name,state:\"lifecycle-state\",endpoint:\"endpoints.kubernetes\"}'",
            "kubectl --request-timeout=10s get --raw=/readyz",
            "kubectl -n \"<NAMESPACE>\" auth can-i get pods --as=system:serviceaccount:\"<NAMESPACE>\":\"<SERVICE_ACCOUNT>\"",
            "kubectl -n \"<NAMESPACE>\" get deployment \"<APP>\" -o jsonpath='{.spec.template.spec.serviceAccountName}'",
            "kubectl -n \"<NAMESPACE>\" logs deployment/\"<APP>\" --since=30m --all-containers --tail=200",
            "Validate installed help before rendering exact Cloud Guard, Vulnerability Scanning, WAF, Bastion, or Audit read commands.",
        ),
        approval_gated_actions=(
            "Repair only the missing read-only runtime-principal policy or namespace RBAC after current preflight and route-level proof.",
            "Restart or roll out the app only after a dry-run/diff proves the change is limited to configuration or image metadata.",
        ),
        verification=(
            "Run the signed-in browser/API security request that previously returned the unavailable or privileged-role error.",
            "Confirm privileged mutations, security execution, SOC actions, deployments, and Log Analytics writes remain role-gated.",
        ),
        stop_conditions=(
            "Do not grant cluster-admin, broad tenancy policies, or privileged action routes to demo users.",
            "Do not copy operator OCI configs, kubeconfigs, wallets, or browser cookies into the app container.",
        ),
        sources=(DOCS["oke"], DOCS["access"], DOCS["cloud_guard"]),
    ),
    "shared-adb-readiness": Plan(
        scenario="shared-adb-readiness",
        intent=(
            "Reuse a tenant-shared ADB/ATP/ADW for demo persistence while "
            "keeping ADMIN, wallet, ACL, migration, and runtime-secret gates separate."
        ),
        evidence_class="configured_until_adb_status_acl_wallet_migration_and_app_readback_are_current",
        read_only=(
            "python3 scripts/kb_lookup.py \"shared demo ADB ATP ADW wallet ACL migrations score persistence\" autonomous-db",
            "oci_cli db autonomous-database get --autonomous-database-id \"<ADB_OCID>\" --query 'data.{state:\"lifecycle-state\",\"db-name\":\"db-name\",\"service-console-url\":\"service-console-url\",\"network-endpoint-type\":\"network-endpoint-type\",\"is-mtls-connection-required\":\"is-mtls-connection-required\"}'",
            "oci_cli db autonomous-database get --autonomous-database-id \"<ADB_OCID>\" --query 'data.{\"whitelisted-ips\":\"whitelisted-ips\",\"private-endpoint\":\"private-endpoint\",\"subnet-id\":\"subnet-id\"}'",
            "kubectl -n \"<NAMESPACE>\" get secret \"<APP_DB_SECRET>\" -o jsonpath='{.metadata.name}{\"\\n\"}{.type}{\"\\n\"}'",
            "kubectl -n \"<NAMESPACE>\" get secret \"<APP_WALLET_SECRET>\" -o jsonpath='{.metadata.name}{\"\\n\"}{.type}{\"\\n\"}'",
            "kubectl -n \"<NAMESPACE>\" logs deployment/\"<APP>\" --since=30m --all-containers --tail=200 | grep -Ei 'adb|oracle|oracledb|migration|score|langfuse|persistence|wallet' || true",
            "Run a redacted app-owned DB health endpoint or in-pod read-only canary that returns only connected=true/false, schema version, and row-count class.",
        ),
        approval_gated_actions=(
            "If no app schema exists, create or repair only the least-privilege application user/schema; use ADMIN only for setup and grants.",
            "If wallet material is missing, download/generate it outside the repo and store it only in the approved runtime secret path.",
            "If an ACL update is required, include every existing keeper because whitelisted-ips replacement is not append-only.",
            "Run migrations only against the application schema and capture the migration-head receipt.",
            "Restart the app only after a dry-run/diff proves the change is limited to DB secret, wallet secret, or migration configuration.",
        ),
        verification=(
            "Confirm ADB lifecycle is AVAILABLE and the intended mTLS/private-endpoint posture is unchanged.",
            "Confirm app runtime can connect with the app user, not ADMIN, using SELECT 1 FROM dual or an equivalent redacted health canary.",
            "Confirm migration head matches the committed app schema and one app read/write or score write/readback path succeeds.",
            "Confirm the browser/API exposes only redacted DB readiness, never DSN, username, wallet path, listener, password, or driver stack.",
        ),
        stop_conditions=(
            "Do not create a dedicated ADB/ATP for a demo when a tenant-shared database is the approved target.",
            "Do not print, commit, or telemetry-export wallet files, ADMIN passwords, wallet passwords, DSNs, or raw ORA connection strings.",
            "Do not replace an ADB ACL without preserving all existing keepers.",
            "Do not use ADMIN as the long-running app user.",
        ),
        sources=(DOCS["adb"], DOCS["vault"]),
    ),
}


def build_payload(scenarios: Iterable[str], *, context: str) -> dict[str, object]:
    return {
        "schema_version": "oci-skills.oke-demo-troubleshoot-bundle.v1",
        "context": context,
        "offline": True,
        "notes": [
            "This file is a redacted plan. It is not evidence that OCI was contacted.",
            "Validate OCI CLI command shapes with scripts/oci_cli_help.py before rendering mutation flags.",
            "Classify missing data as unavailable or inconclusive; do not infer reachability from absent sources.",
        ],
        "plans": [PLANS[name].as_dict(context=context) for name in scenarios],
    }


def build_receipt_template(*, context: str) -> dict[str, object]:
    """Return a redacted evidence envelope for post-investigation reporting.

    The template is intentionally data-free. Operators fill it from current,
    sanitized command output after the read-only checks in the selected plan run.
    """
    return {
        "schema_version": "oci-skills.incident-troubleshooting-receipt.v1",
        "context": context,
        "offline": True,
        "case_type": "connection-source-investigation|oke-app-agent|custom",
        "time_window": "<ISO8601_OR_DURATION>",
        "target_scope": {
            "compartment": "<COMPARTMENT_PLACEHOLDER>",
            "region": "<REGION>",
            "cluster": "<OKE_CLUSTER_PLACEHOLDER>",
            "namespace": "<NAMESPACE_PLACEHOLDER>",
            "application": "<APP>",
        },
        "evidence_sources": [
            {
                "source": "oke_api",
                "query_or_command": "oci_cli ce cluster get --cluster-id \"<OKE_CLUSTER_OCID>\"",
                "status": "verified|empty|degraded|unavailable",
                "result_summary": "<STATE_ENDPOINT_VERSION_ONLY>",
                "coverage_gap": "<NONE_OR_GAP>",
            },
            {
                "source": "kubernetes_readyz_rbac_rollout",
                "query_or_command": "kubectl --request-timeout=10s get --raw=/readyz && kubectl auth can-i ... && kubectl rollout status ...",
                "status": "verified|empty|degraded|unavailable",
                "result_summary": "<READYZ_RBAC_ROLLOUT_COUNTS_ONLY>",
                "coverage_gap": "<NONE_OR_GAP>",
            },
            {
                "source": "runtime_principal",
                "query_or_command": "instance principal: kubectl exec ... -- oci iam region list --auth instance_principal; workload identity: app/SDK read canary using workload identity provider",
                "status": "verified|empty|degraded|unavailable",
                "result_summary": "<PRINCIPAL_TYPE_AND_READ_SCOPE_ONLY>",
                "coverage_gap": "<NONE_OR_GAP>",
            },
            {
                "source": "vcn_flow_logs",
                "query_or_command": "./scripts/oci_logan.sh -q \"'Log Source' = 'OCI VCN Flow Logs' ...\" -t <WINDOW>",
                "status": "verified|empty|degraded|unavailable",
                "result_summary": "<COUNTS_BY_ACTION_PORT_PROTOCOL_RULE_ONLY>",
                "coverage_gap": "<NONE_OR_GAP>",
            },
            {
                "source": "load_balancer_logs",
                "query_or_command": "./scripts/oci_logan.sh -q \"'Log Source' = 'OCI Load Balancer Access Logs' ...\" -t <WINDOW>",
                "status": "verified|empty|degraded|unavailable",
                "result_summary": "<REQUEST_AND_STATUS_COUNTS_ONLY>",
                "coverage_gap": "<NONE_OR_GAP>",
            },
            {
                "source": "traces_monitoring_security",
                "query_or_command": "<SANITIZED_APM_MONITORING_CLOUD_GUARD_OR_AUDIT_READ>",
                "status": "verified|empty|degraded|unavailable",
                "result_summary": "<TRACE_METRIC_SECURITY_COUNTS_ONLY>",
                "coverage_gap": "<NONE_OR_GAP>",
            },
        ],
        "conclusion_level": "provider_verified|configured|unavailable|inconclusive",
        "allowed_conclusions": [
            "provider_verified only when current rows or service API results support the claim",
            "configured only when setup exists but current data movement/runtime behavior is not proven",
            "unavailable when a source/tool/control-plane path is unreachable with no service verdict inferred",
            "inconclusive when minimum evidence is missing or sources disagree",
        ],
        "next_action": "<READ_ONLY_RETRY_OR_REVIEWED_MUTATION>",
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scenario",
        choices=(*PLANS.keys(), "all", "receipt-template"),
        help="Failure mode to plan for.",
    )
    parser.add_argument(
        "--context",
        default="<NAMED_CONTEXT>",
        help="Named OCI context label to echo in the offline plan.",
    )
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.scenario == "receipt-template":
        payload = build_receipt_template(context=args.context)
        print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
        return 0
    scenarios = tuple(PLANS) if args.scenario == "all" else (args.scenario,)
    payload = build_payload(scenarios, context=args.context)
    print(json.dumps(payload, indent=2 if args.pretty else None, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

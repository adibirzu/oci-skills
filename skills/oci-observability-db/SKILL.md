---
name: oci-observability-db
description: >-
  OCI observability and database administration via oci-cli and the OCI SDK:
  Monitoring metrics and alarms, Logging (service and custom logs, Unified/
  Management agents), Log Analytics LQL queries and saved searches, APM domains,
  data keys, OTLP trace upload and RUM, Notifications/ONS topics, Service
  Connector Hub fan-out, Database Management (DBM), Operations Insights (OPSI),
  and Autonomous Database admin. Use when the user mentions OCI Monitoring,
  alarm, metric query, Logging, log group, Log Analytics, APM, traces, RUM, ONS
  topic, service connector, DBM, Performance Hub, Ops Insights, Database
  Insights, or provisioning/enabling an Autonomous Database.
license: MIT
---

# OCI Observability & Database Admin

Tenancy-agnostic helpers for observability and database administration. All CLI
runs through `oci_cli` (`../../scripts/common.sh`); mutations through
`run_mutating` / `confirm`. Never inline real OCIDs, IPs, datakeys, APM keys, or
namespaces — use `<PLACEHOLDER>` tokens.

## First move (always)

1. **Preflight the tenancy** so you never act on the wrong account:
   ```bash
   ./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>
   ```
   Eyeball the resolved tenancy/compartment **names**. Wrong tenancy → stop.
2. **Check the KB** for a known fix before debugging from scratch:
   ```bash
   python3 ../../scripts/kb_lookup.py "<error text or component>"
   ```

## Routing

| User intent | Go to |
|-------------|-------|
| Alarm / metric query / dashboard | Monitoring section in the reference |
| Service log / custom log / agent | Logging section |
| LQL query / saved search | Log Analytics section |
| Traces / RUM / data keys | APM section |
| Observe GenAI **agent traces** / trace integrity (observability only) | Agentic AI observability profile |
| **Build** GenAI agents, tools, RAG, model endpoints, governance | → `oracle/skills` `oci/enterprise-ai` (not here) |
| Topic / subscription | Notifications |
| Archive logs / forward metrics | Service Connector Hub |
| Monitor a DB / Performance Hub / fleet | Database Management (DBM) |
| Capacity / SQL insights | Operations Insights (OPSI) |
| Provision / enable an ADB | Autonomous Database |
| "What observability do we have?" | Resource discovery (inventory) |
| Visualize metrics/logs/traces in **Grafana** (datasource, MQL panels, dashboards-as-code, Loki/Prometheus) | → `../../references/grafana-dashboards.md` |

Full sanitized command/SDK shapes: `../../references/observability-db.md`.
Grafana dashboards-as-code: `../../references/grafana-dashboards.md`.
Safety rules (auth modes, read-before-write, redaction):
`../../references/tenancy-safety.md`.

**Scope.** This skill *observes* GenAI/agentic workloads (traces, integrity,
gating) and provisions the surrounding IAM/network/budget. To *build* GenAI
solutions — model endpoints, Responses-API agents, RAG, GenAI governance — route
to `oracle/skills` `oci/enterprise-ai`; for work *inside* an Oracle Database
(SQL/PL-SQL, RMAN, AWR/ASH, Data Guard) route to `oracle/skills` `db/`. See
[references/oracle-skills-alignment.md](../../references/oracle-skills-alignment.md).

## Common multi-step flows

| Task | Sequence |
|------|----------|
| Add a missing alarm | `alarm list` (confirm the gap) → ensure a destination topic is `ACTIVE` → `alarm create` (threshold in MQL `--query-text`) → verify `is-enabled` |
| Stand up DB monitoring | `managed-database list` → `enable-database-management` (async work request) → wait for completion → verify it is collecting, not just enabled (KB-049) |
| APM shows no traces | `apm-domain list` → `list-data-keys` (use the **private** key) → check the OTLP endpoint URL is the private `/v1/traces` path (KB-025) → re-send and re-query |
| Gate agentic AI traces | query `trace.integrity.score`/`state` → find `non_gateable`/`non_exportable` spans → supply missing span/attribute evidence → re-score (KB-097) |

## Common tasks

**Create an alarm** (search first → wire a topic → create):
```bash
oci_cli monitoring alarm list --compartment-id <COMPARTMENT_OCID> --display-name "<name>" --all
run_mutating "create alarm" oci_cli monitoring alarm create \
  --display-name "<name>" \
  --compartment-id <COMPARTMENT_OCID> --metric-compartment-id <COMPARTMENT_OCID> \
  --namespace <NAMESPACE> --severity CRITICAL --is-enabled true \
  --query-text 'CpuUtilization[1m].mean() > 80' --destinations '["<TOPIC_OCID>"]'
```
The threshold is inside `--query-text` (MQL); there is no `--threshold` flag.

**Create a service log** (build JSON source config; tolerate `409`):
```bash
cfg='{"source":{"sourceType":"OCISERVICE","service":"<service_name>","resource":"<resource_id>","category":"<category>","parameters":{}}}'
run_mutating "create service log" oci_cli logging log create \
  --log-group-id <LOG_GROUP_OCID> --display-name "<name>" --log-type SERVICE \
  --configuration "$cfg" || { warn "likely 409 (already enabled)"; oci_cli logging log list --log-group-id <LOG_GROUP_OCID> --all; }
```

**Query Log Analytics**:
```bash
oci_cli log-analytics query --namespace-name <NAMESPACE> \
  --compartment-id <COMPARTMENT_OCID> \
  --query-string "'Log Source' = '<source>' | stats count by 'Host'" \
  --time-start 2026-06-04T00:00:00Z --time-end 2026-06-04T01:00:00Z
```

**Enable DBM on a database** (list first; async work request):
```bash
oci_cli database-management managed-database list --compartment-id <COMPARTMENT_OCID> --all
run_mutating "enable DBM" oci_cli database-management external-database \
  enable-database-management --external-database-id <DB_OCID> \
  --database-management-config file://dbm_config.json
```

**Check an APM domain + data keys** (redact the private key):
```bash
oci_cli apm-domain list --compartment-id <COMPARTMENT_OCID> --all
oci_cli apm-domain list-data-keys --apm-domain-id <APM_DOMAIN_ID> | redact
```
OTLP traces POST to `/20200101/opentelemetry/private/v1/traces` with the
**private** datakey header; RUM uses the **public** key only.

**Agentic AI trace profile**:
Use OTel GenAI attributes plus OCI extensions, keep prompt/response capture off
by default, and link `trace_id`, `session_id`, `conversation_id`, tool calls,
guardrail decisions, approvals, and eval scores. For promotion gates, report
`trace.integrity.score` and `trace.integrity.state`; traces marked
`non_gateable` or `non_exportable` need missing-span/attribute evidence before
release.

## Safety notes

- Read before write; treat `409 Conflict` as "already exists" and re-list (idempotent).
- Mutations go through `run_mutating` (honors `OCI_SKILLS_DRY_RUN=true`); destructive
  ops also through `confirm`.
- `<APM_PRIVATE_DATAKEY>`, datakeys, and OCIDs must never hit logs/git — pipe through
  `redact` or `python3 ../../scripts/redact.py --check <file>`.
- Precheck capacity before provisioning (`limits value list --service-name database`).
- After fixing a new error, add a `KB-<n>` entry to `../../references/KB.md`.
- **Never invent `oci` flags.** Fetch the exact command shape first:
  `python3 ../../scripts/oci_cli_help.py <service> <op>`.

## Expected output

```
Finding:      <e.g. CPU alarm missing on prod DB compartment>
Evidence:     <redacted list/query output proving the gap>
Action:       <oci_cli ... via run_mutating, dry-run shown first>
Verification: <re-list / get showing the resource now exists & ENABLED>
KB:           <KB-<n> if a new error was resolved, else n/a>
```

## Official documentation

[Monitoring](https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm) · [Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm) · [Operations Insights](https://docs.oracle.com/en-us/iaas/operations-insights/home.htm). Full list in the [observability-db reference](../../references/observability-db.md).

**Open Knowledge Format grounding** — every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill to build an OCI customer solution, cite the most specific official page through that index so every claim stays verifiable; the non-official MCP gateway is never a source of truth.

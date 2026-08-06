---
name: oci-observability-db
description: >-
  Operate OCI Monitoring, Logging, APM, OpenTelemetry, Notifications, Service Connector Hub, service/custom logs, metrics, alarms, dashboards, agent traces, Grafana integrations, PromQL-to-MQL conversion, and Linux or Windows host dashboards. Use for telemetry collection, queries, alerting, trace integrity, logging pipelines, exporter metrics, or observability inventory. Route Database Management, Operations Insights, Performance Hub, AWR/ADDM/ASH, and DBSNMP to oci-dbm-opsi; route Autonomous Database lifecycle to oci-autonomous-db.
---

# OCI Observability

Preflight the named context, query current telemetry configuration, and search the KB before changing an alarm, log, connector, or APM resource. Run every CLI through `oci_cli`, every mutation through risk-classified `run_action`, and every shared output through redaction.

## First move

```bash
./scripts/oci_preflight.sh -c "$COMPARTMENT_OCID"
```

If the resolved tenancy/compartment does not match the intended target, stop
before changing an alarm, log, connector, or APM resource.

## Routing

| Intent | Owner |
|---|---|
| Metrics, alarms, Logging, APM, OTel, RUM, Notifications, connectors | This skill |
| Prometheus metric queries → OCI MQL; node/windows exporter dashboards | This skill |
| Log Analytics OCL/LQL sources/parsers/detections | **oci-log-analytics** |
| DBM, OPSI, Performance Hub, AWR/ADDM/ASH, DBSNMP | **oci-dbm-opsi** |
| ADB provision/scale/wallet/ACL | **oci-autonomous-db** |
| Build GenAI agents/RAG/model endpoints | Official `oracle/skills` `oci/enterprise-ai` |

Read [observability-db.md](../../references/observability-db.md) for command
shapes, [grafana-dashboards.md](../../references/grafana-dashboards.md) for
dashboards-as-code, and
[prometheus-mql-host-dashboards.md](../../references/prometheus-mql-host-dashboards.md)
for bounded PromQL conversion and prepared Linux/Windows profiles.

## Common multi-step flows

| Task | Sequence |
|---|---|
| Add an alarm | list current → verify metric namespace/query → ensure destination is active → additive action → re-list/test notification |
| Missing traces | list APM domains → resolve correct domain/key without printing it → verify private OTLP endpoint → send test → re-query |
| Service logs | list groups/logs → write source config to `0600` file → additive action → verify ingestion and retention |
| Gate agent traces | query integrity score/state → identify missing spans/attributes → keep prompt capture off → re-score before promotion |
| Convert PromQL to MQL | identify metric type + labels + units → convert only a supported shape with `python3 skills/oci-observability-db/scripts/promql_to_mql.py` → verify namespace/dimensions → compare live series with PromQL |
| Build Linux or Windows host dashboard | identify exporter/version → list emitted metric definitions → render the matching profile → validate every MQL panel → additive provision/import → verify populated panels |

## Safety

- Never expose datakeys, domain IDs, endpoints, OCIDs, IPs, or tenant namespaces.
- Store nested configuration in `0600` `file://` payloads, not argv.
- Treat empty results as inconclusive until region, subtree, time window, and permissions are checked.
- Re-list after a `409` rather than retrying a create.
- Every mutation runs through `run_action --risk <additive|in-place>
  --compartment <COMPARTMENT_OCID> --description "<...>" -- oci_cli ...`
  (honors `OCI_SKILLS_DRY_RUN=true` for a no-op preview); get explicit user
  confirmation before applying an alarm, connector, or APM change.
- Treat converted MQL and rendered dashboards as candidates until every query
  parses and returns the intended dimensions and units; reject unsupported
  PromQL rather than guessing.

## Expected output

Report finding, redacted evidence, exact risk-classified action or read, verification, and KB reference. For database telemetry work, state the handoff owner rather than performing DBM/OPSI here.

## Official documentation

[Monitoring](https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm) · [Logging](https://docs.oracle.com/en-us/iaas/Content/Logging/home.htm) · [APM](https://docs.oracle.com/en-us/iaas/application-performance-monitoring/home.htm) · [Service Connector Hub](https://docs.oracle.com/en-us/iaas/Content/connector-hub/home.htm). Full list in the [observability-db reference](../../references/observability-db.md).

**Open Knowledge Format grounding** - every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill, cite the most specific official page through that index; the non-official MCP gateway is never a source of truth.

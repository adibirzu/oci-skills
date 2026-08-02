# Observability & Database Reference

Sanitized command/SDK shapes for OCI Monitoring, Logging, Log Analytics, APM,
Notifications, Service Connector Hub, Database Management (DBM), Operations
Insights (OPSI), and Autonomous Database admin. Every CLI call goes through
`oci_cli` from `scripts/common.sh`; mutations through `run_action`.
Read `tenancy-safety.md` and `helper-conventions.md` first. Use `<PLACEHOLDER>`
tokens — never inline real OCIDs, IPs, datakeys, APM keys, or namespaces.

## Quick navigation

Select Monitoring, Logging, Log Analytics, APM, Notifications, Service
Connector Hub, database handoffs, discovery, or risks.

## Monitoring (metrics + alarms)

Metrics live in a **namespace** (e.g. `oci_computeagent`, or a custom one). Query
with MQL. *Why:* alarms and dashboards are only as good as the namespace/query you
target, so validate the query returns data before wiring an alarm to it.

```bash
# Read: does this query return datapoints right now?
oci_cli monitoring metric-data summarize-metric-data \
  --namespace <NAMESPACE> --compartment-id <COMPARTMENT_OCID> \
  --query-text 'CpuUtilization[1m].mean()' \
  --start-time 2026-06-04T00:00:00Z --end-time 2026-06-04T01:00:00Z

# Post custom metric data (agentless / app metrics)
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "post custom metric" -- \
  oci_cli monitoring metric-data post-metric-data --metric-data file://metric_batch.json
```

```python
# SDK equivalents (paginate reads; batch posts <= 50 points)
import oci
mon = oci.monitoring.MonitoringClient(config)
mon.summarize_metrics_data("<COMPARTMENT_OCID>",
    oci.monitoring.models.SummarizeMetricsDataDetails(
        namespace="<NAMESPACE>", query="<metric_query>"))
mon.post_metric_data(oci.monitoring.models.PostMetricDataDetails(metric_data=[...]))
```

**Alarms** evaluate an MQL query against a threshold and notify an ONS topic.
*Why:* the alarm body is the query plus a comparison; the notification target must
be a topic OCID, not an email — wire the topic first (see Notifications).

```bash
# Idempotent: search by name before create
oci_cli monitoring alarm list --compartment-id <COMPARTMENT_OCID> \
  --display-name "<name>" --all
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create alarm" -- \
  oci_cli monitoring alarm create \
    --display-name "<name>" \
    --compartment-id <COMPARTMENT_OCID> \
    --metric-compartment-id <COMPARTMENT_OCID> \
    --namespace <NAMESPACE> \
    --query-text 'CpuUtilization[1m].mean() > 80' \
    --severity CRITICAL --is-enabled true \
    --destinations file://<TMP_0600_ALARM_DESTINATIONS_JSON> \
    --pending-duration PT5M --body "threshold breached"
```

The threshold lives **inside** `--query-text` (MQL), not in a separate flag.
Required flags the CLI will reject if omitted: `--display-name`,
`--compartment-id`, `--metric-compartment-id`, `--namespace`, `--query-text`,
`--severity`, `--destinations` (a list of ONS topic OCIDs).

**Service metric namespace catalog** (for alarms & dashboard panels): `oci_computeagent`,
`oci_blockstore`, `oci_vcn`, `oci_lbaas`, `oci_oke`, `oci_database_autonomous`,
`oci_database_management`, `oci_logging`, `oracle_apm_monitoring`, `oci_apigateway`,
`oci_waf`, `oci_streaming`, `oci_functions`. Custom namespaces must be lowercase
(KB-132). Every MQL query needs an aggregation window (`[5m]`) — a bare metric name fails.

> **Visualizing these in Grafana** (OCI Metrics datasource, MQL panel queries,
> dashboards-as-code, Loki/Promtail, Prometheus, alerting-as-code):
> [grafana-dashboards.md](grafana-dashboards.md).
>
> **Prometheus host metrics in OCI Monitoring:** bounded PromQL-to-MQL
> conversion and prepared Linux/Windows dashboard profiles live in
> [prometheus-mql-host-dashboards.md](prometheus-mql-host-dashboards.md).

## Logging (log groups, service logs, custom logs, agents)

Service logs (VCN flow, LB access, object-storage) require a JSON **source config**
binding the emitting resource to a log group. *Why:* enabling the same service log
twice returns `409 Conflict` — treat that as "already enabled" and re-list rather
than retrying blindly (idempotent).

```bash
oci_cli logging log-group list --compartment-id <COMPARTMENT_OCID> --all
# source config: { service, resource, category, parameters }
cat > svc_log.json <<'JSON'
{ "sourceType": "OCISERVICE",
  "service": "<service_name>", "resource": "<resource_id>",
  "category": "<category>", "parameters": {} }
JSON
if ! run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create service log" -- \
     oci_cli logging log create --log-group-id <LOG_GROUP_OCID> \
       --display-name "<name>" --log-type SERVICE \
       --configuration "$(jq -c '{source: .}' svc_log.json)"; then
  warn "create returned non-zero — likely 409 (already enabled); re-listing"
  oci_cli logging log list --log-group-id <LOG_GROUP_OCID> --all
fi

# Custom logs: application pushes via the Unified Monitoring agent
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create custom log" -- \
  oci_cli logging log create --log-group-id <LOG_GROUP_OCID> \
    --display-name "<app_log>" --log-type CUSTOM
```

**Management / Unified agent**: an agent config selects sources and destinations,
and is bound to hosts via a **dynamic group** matching the instances. *Why:* the
agent only collects once its dynamic group has IAM policy to write to the log
group — config without the policy silently collects nothing.

```bash
oci_cli logging-management agent-configuration list --compartment-id <COMPARTMENT_OCID>
# Dynamic group rule (example): instance.compartment.id = '<COMPARTMENT_OCID>'
```

## Log Analytics (LQL, sources, saved searches)

> **For anything beyond a one-off query, use the dedicated `oci-log-analytics`
> skill** — it has the full OCL cheat-sheet, the `oci_logan.sh` read-only query
> helper, sources/parsers/fields/entities, detections (Sigma→OCL), and migration
> patterns. See [log-analytics.md](log-analytics.md). This section is a quick
> pointer only.

*Why:* Log Analytics is a separate service with its own `<NAMESPACE>`; queries use
OCL (not MQL), and saved searches make dashboards reproducible.

```bash
oci_cli log-analytics query --namespace-name <NAMESPACE> \
  --compartment-id <COMPARTMENT_OCID> \
  --query-string "'Log Source' = '<source>' | stats count by 'Host'" \
  --time-start 2026-06-04T00:00:00Z --time-end 2026-06-04T01:00:00Z

oci_cli log-analytics list-sources --namespace-name <NAMESPACE> \
  --compartment-id <COMPARTMENT_OCID> --all
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "save search" -- \
  oci_cli log-analytics create-saved-search --namespace-name <NAMESPACE> \
    --display-name "<name>" --query "<lql>" --compartment-id <COMPARTMENT_OCID>
```

## APM (domains, data keys, traces, RUM)

A domain has **two** data keys: `private` (ingest traces/spans/metrics) and
`public` (RUM browser uploads). *Why:* uploading traces with the public key fails
authorization; the private key is a secret and must be redacted everywhere.

```bash
oci_cli apm-domain list --compartment-id <COMPARTMENT_OCID> --all
# Data keys (private vs public). Redact before logging.
oci_cli apm-domain list-data-keys --apm-domain-id <APM_DOMAIN_ID> | redact
```

OTLP trace upload posts to the **private** ingestion endpoint with the private
datakey as a header. *Why:* this is the agentless path — any OTLP exporter can ship
spans without an APM agent, as long as it targets the per-domain private endpoint.

```bash
# Endpoint path is fixed; <APM_PRIVATE_DATAKEY> is the per-domain secret.
curl -sS -X POST \
  "https://<apm-domain-host>/20200101/opentelemetry/private/v1/traces" \
  -H "Content-Type: application/json" \
  -H "Authorization: dataKey <APM_PRIVATE_DATAKEY>" \
  --data-binary @otlp_traces.json
```

RUM uses the **public** key in the browser snippet; never embed the private key
client-side.

### Agentic AI observability profile

For agent systems, classic request traces are not enough. Model the run as an
agent episode: user intent, routing, model calls, retrieval, memory, tool calls,
guardrails, approvals, retries, budget decisions, side effects, and evaluator
verdicts linked by `trace_id`, `span_id`, `session_id`, and `conversation_id`.

Recommended OCI-native pattern:

- Use OpenTelemetry semantic attributes for GenAI spans (`gen_ai.*`) and add
  OCI-specific attributes only as an extension layer.
- Keep prompt/response capture disabled by default in public or shared
  environments; enable it only for approved evaluation runs.
- Split APM domains when needed: runtime/platform telemetry, GenAI telemetry,
  and application-under-investigation telemetry can be separate domains. Store
  each private data key in Vault/ExternalSecrets and keep domain IDs/endpoints
  out of committed docs.
- Fan out through an OTel collector when comparing OCI APM, Log Analytics,
  Grafana/Tempo/Prometheus/Loki, Langfuse, OpenLIT, Phoenix, or Jaeger.
- Emit a privacy-safe synthetic smoke trace/log/metric with a deterministic
  run id after import so dashboards can be validated without live user content.

Trace integrity is a useful release gate. Compute and export fields such as:

```text
trace.integrity.score
trace.integrity.state                 # evidence_complete | evidence_degraded | governance_incomplete | non_gateable | non_exportable
trace.integrity.missing_spans
trace.integrity.missing_attributes
trace.integrity.missing_governance_spans
trace.integrity.missing_export_attributes
```

Gate promotion on low `non_gateable`/`non_exportable` rates and on drilldown
coverage from evaluation results to spans. Observability should record evidence;
guardrails, approval systems, and budget controllers remain the decision
authorities.

## Notifications (ONS topics + subscriptions)

*Why:* alarms, Service Connectors, and budgets all fan out through a topic; create
the topic and confirm the subscription before pointing an alarm at it.

```bash
oci_cli ons topic list --compartment-id <COMPARTMENT_OCID> --all
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create topic" -- \
  oci_cli ons topic create --name "<topic>" --compartment-id <COMPARTMENT_OCID>
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "subscribe email" -- \
  oci_cli ons subscription create --topic-id <TOPIC_OCID> \
    --compartment-id <COMPARTMENT_OCID> --protocol EMAIL --subscription-endpoint "<address>"
```

## Service Connector Hub (log/metric fan-out)

A connector moves data **source → (optional task) → target** (e.g. Logging →
Object Storage, or Monitoring → Notifications). *Why:* it is the supported way to
archive logs or forward metrics without custom pollers; define source/target as JSON.

```bash
oci_cli sch service-connector list --compartment-id <COMPARTMENT_OCID> --all
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create connector" -- \
  oci_cli sch service-connector create --compartment-id <COMPARTMENT_OCID> \
    --display-name "<name>" --source file://source.json --target file://target.json
```

## Database handoffs

Database Management, Operations Insights, Performance Hub, AWR/ADDM/ASH, and DBSNMP belong to `oci-dbm-opsi` and `references/dbm-opsi.md`. Autonomous Database lifecycle, wallet, ACL, scale, and connectivity belong to `oci-autonomous-db` and `references/autonomous-db.md`. This reference owns only their Monitoring/Logging/APM integration.

## Resource discovery (inventory across regions/compartments)

*Why:* observability coverage gaps come from un-enumerated resources; build a
full inventory by traversing every subscribed region and the compartment subtree,
issuing list calls in parallel and merging results.

```python
import concurrent.futures, oci
def list_region(region, comp_id):
    cfg = {**base_cfg, "region": region}
    cl = oci.monitoring.MonitoringClient(cfg)
    return region, oci.pagination.list_call_get_all_results(
        cl.list_alarms, compartment_id=comp_id,
        compartment_id_in_subtree=True).data
regions = [r.region_name for r in identity.list_region_subscriptions(tenancy_id).data]
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
    inventory = dict(ex.map(lambda r: list_region(r, "<COMPARTMENT_OCID>"), regions))
```

```bash
# CLI equivalent: loop subscribed regions, subtree-list per compartment
for r in $(oci_cli iam region-subscription list --query 'data[].\"region-name\"' --raw-output); do
  OCI_REGION="$r" oci_cli monitoring alarm list \
    --compartment-id <COMPARTMENT_OCID> --compartment-id-in-subtree true --all
done
```

## Risks to flag

| Risk | Why it bites | Guard |
|------|--------------|-------|
| Wrong tenancy/compartment | Edits prod observability config | `oci_preflight.sh -c <COMPARTMENT_OCID>` first |
| Private datakey in logs/git | Credential leak (trace ingest) | `redact` / `redact.py --check`; `<APM_PRIVATE_DATAKEY>` token |
| Double-enable DBM/OPSI | `409`/duplicate work requests | List monitored DBs / insights before enable |
| Service-log re-create | `409 Conflict` aborts a script | Catch non-zero, re-list, treat as exists |
| Alarm → email directly | Alarm needs a topic OCID | Create ONS topic, confirm subscription, then alarm |
| ADB create without precheck | `LimitExceeded` half-failure | `limits value list --service-name database` first |
| RUM with private key | Exposes ingest secret client-side | Use the **public** data key for RUM only |
| Cross-region blind spots | Resources missed in inventory | Iterate `region-subscription list` + subtree |

## Official documentation

Canonical Oracle docs for the services covered above (verified live):

- [Monitoring (metrics & alarms)](https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm)
- [Logging](https://docs.oracle.com/en-us/iaas/Content/Logging/home.htm)
- [Application Performance Monitoring (APM)](https://docs.oracle.com/en-us/iaas/application-performance-monitoring/home.htm)
- [Notifications (ONS)](https://docs.oracle.com/en-us/iaas/Content/Notification/home.htm)
- [Service Connector Hub](https://docs.oracle.com/en-us/iaas/Content/connector-hub/home.htm)
- [Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm)
- [Operations Insights](https://docs.oracle.com/en-us/iaas/operations-insights/home.htm)
- [Autonomous Database](https://docs.oracle.com/en-us/iaas/autonomous-database/index.html)

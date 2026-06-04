# Observability & Database Reference

Sanitized command/SDK shapes for OCI Monitoring, Logging, Log Analytics, APM,
Notifications, Service Connector Hub, Database Management (DBM), Operations
Insights (OPSI), and Autonomous Database admin. Every CLI call goes through
`oci_cli` from `scripts/common.sh`; mutations through `run_mutating` / `confirm`.
Read `tenancy-safety.md` and `helper-conventions.md` first. Use `<PLACEHOLDER>`
tokens — never inline real OCIDs, IPs, datakeys, APM keys, or namespaces.

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
run_mutating "post custom metric" \
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
run_mutating "create alarm" \
  oci_cli monitoring alarm create \
    --display-name "<name>" \
    --compartment-id <COMPARTMENT_OCID> \
    --metric-compartment-id <COMPARTMENT_OCID> \
    --namespace <NAMESPACE> \
    --query-text 'CpuUtilization[1m].mean() > 80' \
    --severity CRITICAL --is-enabled true \
    --destinations '["<TOPIC_OCID>"]' \
    --pending-duration PT5M --body "threshold breached"
```

The threshold lives **inside** `--query-text` (MQL), not in a separate flag.
Required flags the CLI will reject if omitted: `--display-name`,
`--compartment-id`, `--metric-compartment-id`, `--namespace`, `--query-text`,
`--severity`, `--destinations` (a list of ONS topic OCIDs).

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
if ! run_mutating "create service log" \
     oci_cli logging log create --log-group-id <LOG_GROUP_OCID> \
       --display-name "<name>" --log-type SERVICE \
       --configuration "$(jq -c '{source: .}' svc_log.json)"; then
  warn "create returned non-zero — likely 409 (already enabled); re-listing"
  oci_cli logging log list --log-group-id <LOG_GROUP_OCID> --all
fi

# Custom logs: application pushes via the Unified Monitoring agent
run_mutating "create custom log" \
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

*Why:* Log Analytics is a separate service with its own `<NAMESPACE>`; queries use
LQL (not MQL), and saved searches make dashboards reproducible.

```bash
oci_cli log-analytics query --namespace-name <NAMESPACE> \
  --compartment-id <COMPARTMENT_OCID> \
  --query-string "'Log Source' = '<source>' | stats count by 'Host'" \
  --time-start 2026-06-04T00:00:00Z --time-end 2026-06-04T01:00:00Z

oci_cli log-analytics list-sources --namespace-name <NAMESPACE> \
  --compartment-id <COMPARTMENT_OCID> --all
run_mutating "save search" \
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

## Notifications (ONS topics + subscriptions)

*Why:* alarms, Service Connectors, and budgets all fan out through a topic; create
the topic and confirm the subscription before pointing an alarm at it.

```bash
oci_cli ons topic list --compartment-id <COMPARTMENT_OCID> --all
run_mutating "create topic" \
  oci_cli ons topic create --name "<topic>" --compartment-id <COMPARTMENT_OCID>
run_mutating "subscribe email" \
  oci_cli ons subscription create --topic-id <TOPIC_OCID> \
    --compartment-id <COMPARTMENT_OCID> --protocol EMAIL --subscription-endpoint "<address>"
```

## Service Connector Hub (log/metric fan-out)

A connector moves data **source → (optional task) → target** (e.g. Logging →
Object Storage, or Monitoring → Notifications). *Why:* it is the supported way to
archive logs or forward metrics without custom pollers; define source/target as JSON.

```bash
oci_cli sch service-connector list --compartment-id <COMPARTMENT_OCID> --all
run_mutating "create connector" \
  oci_cli sch service-connector create --compartment-id <COMPARTMENT_OCID> \
    --display-name "<name>" --source file://source.json --target file://target.json
```

## Database Management (DBM)

DBM enablement attaches monitoring to a DB system, external DB, or PDB and feeds
**Performance Hub** and fleet views. *Why:* enabling is a work-request-backed,
idempotent mutation — list monitored databases first to avoid double-enable.

```bash
oci_cli database-management managed-database list --compartment-id <COMPARTMENT_OCID> --all
run_mutating "enable DBM" \
  oci_cli database-management external-database enable-database-management \
    --external-database-id <DB_OCID> \
    --database-management-config file://dbm_config.json
# Fleet + Performance Hub are read views over enabled databases:
oci_cli database-management managed-database get --managed-database-id <DB_OCID>
```

## Operations Insights (OPSI)

Database Insights ingest AWR/SQL data for capacity and SQL analysis. *Why:*
enable/disable are async work requests; capacity and SQL Insights only populate
after the database insight reaches `ENABLED`.

```bash
oci_cli opsi database-insights list --compartment-id <COMPARTMENT_OCID> --all
run_mutating "enable database insight" \
  oci_cli opsi database-insights enable-database-insight \
    --database-insight-id <DB_INSIGHT_OCID>
# Capacity / SQL insights (read):
oci_cli opsi database-insights summarize-database-insight-resource-capacity-trend \
  --compartment-id <COMPARTMENT_OCID> --resource-metric CPU
```

## Autonomous Database admin (idempotent provision)

*Why:* ADB names are not unique by default, so an idempotent provision must
search by display name first **and** precheck capacity, or you risk a duplicate or
a `LimitExceeded` half-failure.

```bash
# 1. Capacity precheck
oci_cli limits service list --compartment-id <TENANCY_OCID> --all
oci_cli limits value list --compartment-id <TENANCY_OCID> --service-name database --all
# 2. Idempotency: does it already exist?
existing="$(oci_cli db autonomous-database list \
  --compartment-id <COMPARTMENT_OCID> --display-name "<name>" --all \
  --query 'data[0].id' --raw-output 2>/dev/null || true)"
if [[ -n "$existing" && "$existing" != "null" ]]; then
  ok "ADB '<name>' already exists; skipping create"
else
  run_mutating "create ADB" \
    oci_cli db autonomous-database create --compartment-id <COMPARTMENT_OCID> \
      --db-name "<name>" --display-name "<name>" \
      --cpu-core-count 1 --data-storage-size-in-tbs 1 \
      --admin-password "$ADB_ADMIN_PASSWORD" --db-workload OLTP
fi
```

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

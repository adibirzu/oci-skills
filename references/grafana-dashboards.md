# Grafana dashboards-as-code for OCI observability — reference

Tenancy-agnostic patterns for visualizing OCI telemetry in Grafana: the OCI Metrics
datasource, MQL panel queries, dashboard/panel JSON, Loki/Promtail logs, Prometheus
exposition, and alerting-as-code. Pairs with `skills/oci-observability-db/SKILL.md`
(which owns the OCI Monitoring/APM/Logging control plane). All examples use
`<PLACEHOLDER>` tokens — resolve from your own environment. Never inline real OCIDs,
IPs, credentials, or tenancy names — use the `<PLACEHOLDER>` tokens above.

> **Scope.** This file is *visualization* — how to render OCI metrics/logs/traces in
> Grafana. Creating the underlying alarms, metrics, APM domains, and Log Analytics
> queries stays in `oci-observability-db`. Building/operating an OKE cluster that
> hosts Grafana → `oci/oke`.

## 1. OCI Metrics datasource (no API keys)

Provision the [`oci-metrics-datasource`](https://grafana.com/grafana/plugins/oci-metrics-datasource/)
plugin with **Instance Principal** auth when Grafana runs on an OCI VM/OKE node —
no API keys on disk:

```yaml
# provisioning/datasources/datasources.yaml
apiVersion: 1
datasources:
  - name: oci-metrics
    type: oci-metrics-datasource
    uid: <OCI_METRICS_UID>
    jsonData:
      environment: "OCI Instance"   # gotcha: EXACTLY this string — not "local"/"DEFAULT"
      profile0: "<OCI_PROFILE>"
      region0: "<REGION>"
      tenancymode: "single"
```
For off-instance Grafana, use API-key (`environment: "local"`) with a mounted
`~/.oci/config` — but Instance Principal is preferred (KB-143: don't trust a naive
IMDS probe; set `OCI_AUTH_MODE` explicitly).

## 2. MQL panel queries

Every OCI Monitoring query needs an aggregation **window** — a bare metric name fails:

```text
CpuUtilization[5m].mean()
MemoryUtilization[5m].mean()
VnicFromNetworkBytes[5m].rate()
PodCpuUsage[5m]{namespace="<NS>"}.groupBy(namespace).mean()
SpanCount[5m].groupBy(serviceName).sum()
CpuUtilization[5m]{resourceDisplayName="<RESOURCE>"}.mean()
```

Panel target JSON skeleton for the OCI Metrics datasource:
```json
{
  "datasource": { "type": "oci-metrics-datasource", "uid": "${OCI_METRICS_UID}" },
  "compartment": "$compartment",
  "namespace": "<NAMESPACE>",
  "metric": "<METRIC>",
  "queryText": "<METRIC>[5m].mean()",
  "rawQuery": true,
  "region": "$region",
  "statistic": "mean",
  "legendFormat": "{{resourceDisplayName}}"
}
```

## 3. Dashboard-as-code

Template the region/compartment as dashboard variables so one JSON works across
tenancies, and substitute the datasource UID at deploy time:

```json
{
  "templating": { "list": [
    { "name": "region", "type": "custom", "query": "<REGION>" },
    { "name": "compartment", "type": "custom", "query": "<COMPARTMENT_NAME>" }
  ]},
  "schemaVersion": 39,
  "refresh": "1m",
  "time": { "from": "now-6h", "to": "now" }
}
```
```bash
# Portable UID substitution — same JSON across tenancies:
sed "s/__OCI_UID__/${OCI_METRICS_UID}/g" "$src" > "$dest"
```
> **Provisioned dashboards are read-only at runtime:** UI edits are overwritten on
> the next deploy. Edit the JSON source, not the live dashboard.

Panel-type → datasource: `timeseries`/`stat`/`gauge`/`table` → OCI Metrics;
`logs` → Loki; `heatmap`/latency-quantile → Prometheus.

## 4. Logs — Loki + Promtail

Generic JSON-log pipeline (extract `level`/`service`/`trace_id`/`span_id`, push to Loki):
```yaml
# promtail-config.yaml (excerpt)
pipeline_stages:
  - json:
      expressions: { level: level, service: service, trace_id: trace_id, span_id: span_id }
  - labels: { level: '', service: '' }
clients:
  - url: http://127.0.0.1:3100/loki/api/v1/push
```
LogQL panel shapes:
```text
{service_name="<SERVICE>"} |= "ERROR"
sum(rate({service_name=~".+"} |= "ERROR" [5m])) by (service_name)
```

## 5. Metrics — Prometheus exposition + PromQL

App-side (FastAPI / `prometheus_client`): `Counter`/`Histogram`/`Gauge` + a `/metrics`
endpoint with generic metric names. PromQL panel shapes:
```text
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m]))
1 - (sum(rate(http_requests_total{status!~"5.."}[1h])) / sum(rate(http_requests_total[1h])))   # error-budget burn
```

## 6. Alerting-as-code

```yaml
# provisioning/alerting/alerts.yaml (shape)
groups:
  - name: <GROUP>
    rules:
      - title: <ALERT_TITLE>
        for: 5m
        labels: { severity: critical }
        data:
          - refId: A           # query
          - refId: B           # reduce(A)
          - refId: C           # threshold(B)
```

## 7. OCI SDK observability clients (in-process collectors)

When feeding panels from a backend rather than the Grafana datasource, these SDK
clients cover the surface; cache results with a short TTL (e.g. 45s) to respect
OCI API limits:

| Need | Client |
|---|---|
| Metrics | `monitoring.MonitoringClient` |
| Traces | `apm_traces.TraceClient` / `QueryClient` |
| Logs (Logan) | `log_analytics.LogAnalyticsClient` |
| Capacity / SQL insights | `opsi.OperationsInsightsClient` |
| Stack monitoring | `stack_monitoring.StackMonitoringClient` |
| DB Management | `database_management.DbManagementClient` |

## Safety notes

- Instance Principal over API keys for in-cluster Grafana; never bake `~/.oci`
  keys or `<APM_PRIVATE_DATAKEY>` into a dashboard/datasource committed to git.
- Redact `<REGION>`, `<COMPARTMENT_NAME>`, OCIDs, and dashboard UIDs before commit
  (`python3 ../../scripts/redact.py --check <file>`).
- Provisioned dashboards: edit JSON source, never the live UI (overwritten on deploy).

## Official documentation

- [Querying Metric Data (MQL)](https://docs.oracle.com/en-us/iaas/Content/Monitoring/Tasks/query-metric-data.htm)
- [Monitoring overview](https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm)
- [APM — query and visualize traces](https://docs.oracle.com/en-us/iaas/application-performance-monitoring/home.htm)

OCI doc links are registered in [oracle-docs.md](oracle-docs.md). Grafana, Loki,
Promtail, and Prometheus project docs live outside the Oracle-doc index.

# Prometheus metrics to OCI MQL host dashboards

Use this reference when Prometheus-style metrics have been exported into OCI
Monitoring and the request is to translate a PromQL panel or create a dedicated
Linux/node_exporter or Windows/windows_exporter dashboard.

This is a query and dashboard authoring workflow. Offline conversion and JSON
generation contact no tenancy. A generated MQL expression is a candidate until
it parses and returns the expected metric streams in the project's actual
namespace, compartment, region, time range, and exporter version.

## Quick navigation

Use Reuse boundary and Safe converter first, then select Linux/Windows
conversions, dashboards, validation, or design sources.

## Reuse boundary

[`adibirzu/oci-prometheus-otel-monitoring`](https://github.com/adibirzu/oci-prometheus-otel-monitoring)
is the accepted operational reference for host discovery, Linux and Windows
exporter installation, Prometheus aggregation, and its independent OCI
Monitoring and OTLP/Prometheus export paths. It is UPL-1.0 and remains a
separate upstream project; this pack reuses its telemetry architecture and
metric conventions without vendoring its installers.

The Grafana dashboards listed below are coverage and layout references. Do not
copy their datasource-specific queries blindly: some use InfluxDB or Zabbix,
and windows_exporter metric names changed from older `wmi_*` conventions to
current `windows_*` conventions.

## Safe converter

The converter handles a bounded subset and rejects everything else:

```bash
python3 skills/oci-observability-db/scripts/promql_to_mql.py convert \
  'rate(node_network_receive_bytes_total{device="eth0"}[1m]) * 8'

python3 skills/oci-observability-db/scripts/promql_to_mql.py convert \
  '(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100' \
  --gauge-statistic mean --json
```

Supported shapes:

- `avg by (<dimension>) (rate(<counter>{...}[<window>]))` in the CPU-idle
  utilization form;
- `(total - available) / total * 100` for matching gauge streams;
- `rate(<counter>{...}[<window>])` with an optional numeric multiplier.

It does not translate joins, subqueries, offsets, histogram quantiles, recording
rules, vector matching, label rewriting, or negative-regex matchers. Preserve
those in Prometheus/Grafana or redesign them explicitly with OCI-supported MQL
semantics.

## Canonical Linux conversions

Select the custom namespace that actually contains the exporter metrics. Keep
`instance` as a grouping or filter dimension only after confirming it exists in
the metric definitions.

| Intent | PromQL | OCI MQL candidate |
|---|---|---|
| CPU utilization | `100 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100` | `100 - (node_cpu_seconds_total[5m]{mode = "idle"}.rate()).groupBy(instance).mean() * 100` |
| Memory utilization, latest | `(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) / node_memory_MemTotal_bytes * 100` | `(node_memory_MemTotal_bytes[1m].last() - node_memory_MemAvailable_bytes[1m].last()) / node_memory_MemTotal_bytes[1m].last() * 100` |
| Memory utilization, smoothed | same intent | `(node_memory_MemTotal_bytes[1m].mean() - node_memory_MemAvailable_bytes[1m].mean()) / node_memory_MemTotal_bytes[1m].mean() * 100` |
| Receive bits/s | `rate(node_network_receive_bytes_total{device="eth0"}[1m]) * 8` | `node_network_receive_bytes_total[1m]{device = "eth0"}.rate() * 8` |
| Disk busy percent | `rate(node_disk_io_time_seconds_total[1m]) * 100` | `node_disk_io_time_seconds_total[1m].rate() * 100` |
| One disk busy percent | `rate(node_disk_io_time_seconds_total{device="sda"}[1m]) * 100` | `node_disk_io_time_seconds_total[1m]{device = "sda"}.rate() * 100` |

`rate()` is per second in OCI MQL. For `node_disk_io_time_seconds_total`,
multiplying by 100 yields the percentage of wall time a single device spent
doing I/O during the interval. Keep the device dimension: summing percentages
across disks is not a host-level utilization percentage.

Gauge arithmetic requires both metrics to resolve to matching dimension sets.
If `MemTotal` and `MemAvailable` streams differ, fix ingestion dimensions or
query them as separate panels rather than presenting a misleading ratio.

## Dedicated host dashboards

Render an OCI Metrics datasource dashboard as reviewable JSON:

```bash
python3 skills/oci-observability-db/scripts/promql_to_mql.py dashboard \
  --profile linux \
  --namespace '<NAMESPACE>' \
  --datasource-uid '<OCI_METRICS_UID>' \
  --output ./generated/oci-linux-host.json

python3 skills/oci-observability-db/scripts/promql_to_mql.py dashboard \
  --profile windows \
  --namespace '<NAMESPACE>' \
  --datasource-uid '<OCI_METRICS_UID>' \
  --output ./generated/oci-windows-host.json
```

The Linux profile includes CPU, memory, receive/transmit traffic, disk busy
percentage, disk read/write throughput, filesystem utilization, and load. The
Windows profile includes CPU, memory, receive/transmit traffic, logical-disk
utilization, read/write throughput, uptime, and process count.

The Windows template targets current `windows_*` names. Before provisioning,
list the project's metric definitions and reconcile exporter-version differences
such as `windows_*` versus legacy `wmi_*`, plus actual `nic`, `volume`, and
`instance` dimension names.

## Validate before provisioning

For each panel:

1. Confirm the namespace, metric name, and dimensions from metric definitions.
2. Validate every generated MQL query in Metrics Explorer or with the read-only
   CLI call below.
3. Confirm units and cardinality: percent, bytes/s, bits/s, and one series per
   intended host/device.
4. Use a synthetic or known idle/busy interval to compare the MQL result with
   the original PromQL result.
5. Only then provision or import the dashboard. Dashboard creation is an
   additive mutation and follows preflight plus `run_action`.

```bash
oci_cli monitoring metric list \
  --compartment-id <COMPARTMENT_OCID> \
  --namespace '<NAMESPACE>' --all

oci_cli monitoring metric-data summarize-metric-data \
  --compartment-id <COMPARTMENT_OCID> \
  --namespace '<NAMESPACE>' \
  --query-text '<GENERATED_MQL>' \
  --start-time <RFC3339_START> --end-time <RFC3339_END>
```

Empty results are inconclusive until region, compartment/subtree, time window,
permissions, namespace, metric spelling, and dimensions are checked.

## Dashboard design references

Linux coverage/layout:

- [Linux System Overview 2381](https://grafana.com/grafana/dashboards/2381-olympus/)
- [Template Linux Server 2011](https://grafana.com/grafana/dashboards/2011-template-linux-server/)
- [Linux Hosts Metrics 10180](https://grafana.com/grafana/dashboards/10180-kds-linux-hosts/)

Windows coverage/layout:

- [Windows Exporter Dashboard 2025 24390](https://grafana.com/grafana/dashboards/24390-windows-exporter-dashboard-2025/)
- [Windows System Dashboard 11954](https://grafana.com/grafana/dashboards/11954-windows-system-dashboard/)
- [Dashboard Servers Windows 1323](https://grafana.com/grafana/dashboards/1323-dashboard-servers-windows/)
- [Windows Exporter Dashboard 2024 20763](https://grafana.com/grafana/dashboards/20763-windows-exporter-dashboard-2024/)

Oracle semantics remain authoritative:
[Monitoring Query Language reference](https://docs.oracle.com/en-us/iaas/Content/Monitoring/Reference/mql.htm).

# OCI Log Analytics (Logan / OCL) Reference

Sanitized command/SDK/query shapes for **OCI Log Analytics** — the OCL query
language, running queries via CLI/SDK, sources/parsers/fields/lookups, entities &
log groups, detections (incl. Sigma→OCL), and content migration. Every CLI call
goes through `oci_cli` from `scripts/common.sh`; mutations through
`run_action`. Read `tenancy-safety.md` and `helper-conventions.md`
first. Use `<PLACEHOLDER>` tokens — never inline real OCIDs, IPs, the LA
namespace, entity names, or tenant field values.

> The LA **namespace** (`<LA_NAMESPACE>`) is per-tenancy. Resolve it once
> (`oci log-analytics namespace list --compartment-id <TENANCY_OCID>`) and reuse
> it; it is a stable tenancy fingerprint, so keep it out of committed files.

## Quick navigation

Select OCL, query execution, sources/parsers, entities/log groups, detections,
VCN Flow Logs ingestion/correlation, migration/ingestion/dashboards, reusable
queries, or risks.

## OCL query language (cheat-sheet)

OCL is **SEARCH-then-pipe**: a field/text filter, then `|`-separated commands.

```
<field-filter expression> | command1 ... | command2 ...
```

**Field references**
- Multi-word field names MUST be single-quoted: `'Log Source'`, `'Event ID'`,
  `'Principal Name'`, `'Host Name (Server)'`. Single-token fields are bare:
  `User`, `Status`, `Action`, `msg`, `Entity`.
- **String-typed vs numeric fields bite hardest.** `Event ID`, `Logon Type`,
  `Response Code`, `Status Code` are stored as **strings** → quote the literal
  (`'Event ID' = '4625'`). True numeric LONG fields (`Source Port`,
  `Destination Port`, `Bytes Sent`) take a **bare** integer (`'Destination Port' = 443`).

**Filter operators (pre-pipe SEARCH)**

| Operator | Example |
|---|---|
| equality | `'Event ID' = '4625'` |
| inequality / null | `'Process Name' != null` |
| wildcard contains (glob `*`) | `'Command Line' like '*mimikatz*'` |
| set membership | `'Event ID' in ('4728', '4732', '4756')` |
| regex (anchors) | `'Query Name' matches '^[a-zA-Z0-9]{30,}\.'` |
| boolean | `A and (B or C)`, `not (...)` |
| raw message substring | `msg like '*/etc/shadow*'` |

`like` uses `*` glob wildcards; `matches` uses regex anchors — do not mix them.

**Pipe commands** (most-used first): `stats`, `sort`, `where`, `eval`, `fields`,
`timestats`, `link`, `head`, `eventstats`.

```
# aggregate + threshold
... | stats count as Failures, distinctcount('Source Address') as Sources by User | where Failures > 3 | sort -Failures
# time-bucketed series
... | timestats span = 1h count as Hits
# computed column + post-filter
... | eval score = blocks + (rules * 5) | where rules > 2 | sort -score
# streaming aggregate kept alongside rows
... | eventstats count as conns by 'Source IP'
# group/cluster related records
... | link 'Instance OCID', 'Host Name', 'Finding Name' | sort -Count
# projection + order + limit
... | fields Time, 'Attack ID', msg | sort -Time | head 15
```

- `sort -Field` = descending, `sort Field` = ascending.
- Aggregations: `count`, `distinctcount(f)`, `unique(f)`, `sum`, `latest`,
  `earliest`, `max`, `countif`, `length`. Scalars: `formatDate(Time,'HH')`,
  `if(...)`, arithmetic.
- **Time range is out-of-band.** Keep saved-search query strings time-agnostic
  and pass the window via the API/CLI `TimeRange` (start/end/timezone). Embedding
  time literals in a saved search returns nothing.

## Running queries (CLI / SDK)

Use the read-only helper for ad-hoc queries:

```bash
./scripts/oci_logan.sh -q "'Log Source' = 'OCI Audit Logs' | stats count by 'Principal Name'" -t 24h
# -n <LA_NAMESPACE> to override auto-resolve, -c <COMPARTMENT_OCID> to scope, -m N for max rows
```

CLI shape it wraps (note: `query` is a command **group** — the verb is
`query search`, and the window is three scalar flags, not a `--time-filter` blob):

```bash
oci_cli log-analytics query search \
  --namespace-name "<LA_NAMESPACE>" \
  --compartment-id "<COMPARTMENT_OCID>" \
  --compartment-id-in-subtree true \
  --query-string "'Log Source' = 'OCI Audit Logs' | stats count by 'Log Source'" \
  --sub-system LOG \
  --time-start "<RFC3339>" --time-end "<RFC3339>" --timezone UTC \
  --max-total-count 50
```

**Validate syntax without scanning data** (cheap, fast in CI — no time window):

```python
la.parse_query(namespace_name="<LA_NAMESPACE>",
    parse_query_details=oci.log_analytics.models.ParseQueryDetails(
        query_string=query, sub_system="LOG"))
```

SDK execute (canonical): `LogAnalyticsClient.query(...)` with
`QueryDetails(compartment_id, compartment_id_in_subtree=True, query_string,
sub_system="LOG", time_filter=TimeRange(...), max_total_count=...)`; read rows
from `resp.data.items`. **Set `compartment_id_in_subtree=True`** or child
compartments are silently excluded.

## Sources / parsers / fields / lookups

```bash
# list (include Oracle system sources!)
oci_cli log-analytics source list --namespace-name <LA_NAMESPACE> \
  --compartment-id <COMPARTMENT_OCID> --is-system ALL --name <SUBSTRING>
# upsert a source (references parsers + entity types)
oci_cli log-analytics source upsert-source --namespace-name <LA_NAMESPACE> \
  --items file://source.json
```

**Gotchas**
- **Internal `name` vs `display_name`.** Sources/parsers/fields each have an
  immutable internal `name` AND a `display_name`. Match a "missing" artifact
  against **both** before creating, or you silently duplicate it. List with
  `--is-system ALL` so Oracle-defined sources are visible.
- **Prefer native sources** (`OCI Audit Logs`, `OCI WAF Logs`, `OCI Cloud Guard
  Problems`, `Windows Sysmon Events`, …). Only create custom sources when no
  native equivalent exists.
- **Parser/source upsert uses optimistic concurrency.** `get` the resource to
  read its `etag`, then pass `if_match=<etag>` on upsert or you get `412`.
- Create custom **fields before** the parser that references them.

## Entities & log groups

```bash
oci_cli log-analytics entity list --namespace-name <LA_NAMESPACE> \
  --compartment-id <COMPARTMENT_OCID> --name-contains <NAME>
run_action --risk in-place --compartment <COMPARTMENT_OCID> --description "repair entity metadata" -- \
  oci_cli log-analytics entity update --namespace-name <LA_NAMESPACE> \
  --entity-id <ENTITY_OCID> --metadata file://<TMP_0600_METADATA_JSON> \
  --time-last-discovered "$(date -u +%Y-%m-%dT%H:%M:%SZ)" --force
```

- **Entity `name` is immutable after create** — repair `metadata` instead of
  renaming; only greenfield create can set the name.
- Solution UIs depend on metadata keys (e.g. Kubernetes entities need
  `cluster`, `cluster_name`, a real RFC3339 `cluster_date`, `metrics_namespace`);
  a `null` `cluster_date` breaks metric joins.
- On-demand **uploads must pass the log-group OCID** as `opc_meta_loggrpid` or
  they fail / land in the wrong group.

## Detections (Sigma → OCL)

A detection rule (Sigma-compatible YAML: `logsource`, `detection.selection`,
`condition`, `level`, `tags`) compiles to a runnable OCL saved search carrying
`query`, `mitre_attack`, `falsepositives`, `requires_aggregation`.

Conversion mapping: Sigma modifiers → OCL operators — `|contains`→`like '*v*'`,
`|startswith`→`like 'v*'`, `|endswith`→`like '*v'`, `|re`→`matches`,
`|contains|all`→AND of `like`. Multiple `logsource` candidates become an OR over
`'Log Source'` values; keyword (non-field) selections fall back to
`('Original Log Content' like '*v*' or msg like '*v*')`. Sigma `count()/timeframe`
degrades to a `| stats ... | where count > N` tail (`requires_aggregation: true`).

Aggregating queries (with a `stats … | where` threshold) are **scheduled-search
eligible**; plain filters are better as dashboard widgets / interactive hunts.

### OKE detection packs and safe validation

For OKE-focused detections, define a source contract before writing queries.
Minimum useful coverage is Kubernetes audit events, container logs/runtime
events, worker-node Linux audit/syslog, VCN Flow Logs, and Load Balancer Access
Logs when services are behind an LB.

Build multi-signal scenarios as a timeline query first, then split reusable
atomic searches from it. A good timeline correlates namespace, pod, node,
process, actor, and network tuple fields so operators can move from "something
happened" to "which pod/node/user/path was involved" without pasting tenant
values into the query.

Safe promotion gate:

1. Keep scenario content tenant-neutral and free of OCIDs, IPs, namespaces, and
   entity names.
2. Validate syntax with `parse_query` in CI.
3. Validate semantics with synthetic Log Analytics events in a dedicated log
   group/source, not by running exploit tooling or creating privileged test pods.
4. Run live queries only after collection prerequisites are confirmed. An empty
   result means "no matching rows in this window/source set", not "no risk".

Use MITRE tags and false-positive notes in every scenario so scheduled searches
can become operator runbooks instead of anonymous OCL snippets.

## Migration / ingestion / dashboards

- **Dashboards**: `management-dashboard import-dashboard` /
  `list-management-dashboards` / `delete-management-dashboard`; the dashboard
  JSON needs `displayName`. (See `KB.md` for the soft-delete import-ID collision.)
- **On-demand upload** (NDJSON + a parser-ready source) to seed/validate:
  `upload_log_file(namespace, upload_name, log_source_name, filename,
  opc_meta_loggrpid=<LOG_GROUP_OCID>, ...)`. Continuous ingestion is via native
  OCI sources + log groups.
- **Conservative cross-tool migration** (e.g. Sentinel KQL → OCL): convert
  deterministically against an allow-list field map, then **gate promotion on
  live `parse_query` + a synthetic-data row check** — only promote queries that
  parse and return rows.

## Windows access monitoring fast track

Use this sequence for Windows logon, RDP, account, and local privileged-group
monitoring. It is a collection-to-response workflow: installation, entity
mapping, source association, query, dashboard, scheduled metric, alarm, and
notification are separate evidence and mutation gates.

### Current Windows Server prerequisites and install shape

- Use the standalone Management Agent path for Windows Server. Oracle Cloud
  Agent's Management Agent plug-in path is currently documented for supported
  Linux compute images, not Windows compute instances.
- Recheck Oracle's current Windows Server support matrix before installing.
- Standalone prerequisites currently include 300 MB free disk, JDK/JRE 8 update
  281 or newer, WMIC enabled, synchronized host time, and outbound HTTPS 443.
- The response file must include `Service.plugin.logan.download=true`.
- Oracle's Windows command is
  `installer.bat <full_path_of_response_file>`. Treat the response file as a
  secret; never print or commit it.
- Log Analytics uses
  `loganalytics.<region>.oci.oraclecloud.com:443` for log upload/warnings and
  `telemetry-ingestion.<region>.oraclecloud.com:443` for metrics.

### Native source contract

Do not create competing custom sources for continuous Windows event collection.
List with `--is-system ALL` and match both display and internal names:

| Channel | Display name | Internal name | Entity type |
|---|---|---|---|
| Security | `Windows Security Events` | `MsftWinEventSecurityLogSource` | `Host (Windows)` |
| System | `Windows System Events` | `MsftWinEventSystemLogSource` | `Host (Windows)` |
| Application | `Windows Application Events` | `MsftWinEventApplicationLogSource` | `Host (Windows)` |

An `ACTIVE` Management Agent is not ingestion proof. Map the exact agent to one
`Host (Windows)` entity, associate all three sources with the reviewed log group,
then prove one fresh row from every channel and inspect
`logCollectionUploadDataSize` / `logCollectionUploadFailureCount`.

### Access detection contract

The reusable baseline covers Event IDs `4624`, `4625`, `4634`, `4648`, `4672`,
`4720`, `4726`, `4732`, `4733`, and `4776`, with five operator searches:

1. More than 10 failed logons from one source in 5 minutes.
2. Successful RDP logon (`Logon Type = 10`) outside reviewed business hours.
3. Administrator logon, tuned for renamed/localized administrator identities.
4. New local user created.
5. User added to Administrators or Remote Desktop Users.

Scheduled-search queries must output one numeric metric and no more than three
dimensions. Detection rules emit metrics; Monitoring alarms are separate. A
custom metric namespace must not start with reserved `oci_` or `oracle_`; the
accelerator uses `logan_windows_access`. Create alarms disabled, prove the metric
and notification owner, then enable one canary before wider activation.

### Reusable accelerator

The independent `adibirzu/oci-log-analytics-detections` accelerator contains:

- [fast onboarding overview](https://github.com/adibirzu/oci-log-analytics-detections/blob/main/docs/WINDOWS_ACCESS_FAST_ONBOARDING.md)
- [manual console runbook](https://github.com/adibirzu/oci-log-analytics-detections/blob/main/docs/WINDOWS_ACCESS_MANUAL_RUNBOOK.md)
- [script-assisted runbook](https://github.com/adibirzu/oci-log-analytics-detections/blob/main/docs/WINDOWS_ACCESS_SCRIPTED_RUNBOOK.md)
- [workflow diagrams](https://github.com/adibirzu/oci-log-analytics-detections/blob/main/docs/WINDOWS_ACCESS_WORKFLOW_DIAGRAMS.md)
- [guarded Windows installer/preflight helper](https://github.com/adibirzu/oci-log-analytics-detections/blob/main/scripts/windows/management_agent_access_setup.ps1)
- [tenant-neutral onboarding and OCI CLI bundle helper](https://github.com/adibirzu/oci-log-analytics-detections/blob/main/scripts/windows_access_onboarding.py)

Treat these as an independent accelerator, not an Oracle product or proof of
customer acceptance. Its local fixtures validate query semantics; provider
verification still requires a fresh event to traverse agent, native source,
Log Analytics, saved search, scheduled metric, alarm, and approved destination.

## VCN Flow Logs ingestion and connection investigations

VCN Flow Logs are the authoritative network-layer signal for accepted/rejected
traffic. Application traces, compute metrics, and app logs can all look normal
when traffic is blocked before it reaches a pod, load balancer backend, or VM.
When Flow Logs are absent, report a coverage gap, not a reachability conclusion.

For demo incidents that surface as **Data source degraded**, generate the
redacted command plan first:

```bash
python3 scripts/oci_oke_demo_troubleshoot.py connections-degraded --context "<NAMED_CONTEXT>" --pretty
python3 scripts/oci_oke_demo_troubleshoot.py receipt-template --context "<NAMED_CONTEXT>" --pretty
```

The generated plan is offline guidance. It lists read-only checks, mutation
gates, verification queries, and stop conditions for VCN Flow Logs; it is not a
claim that Logging, Service Connector Hub, or Log Analytics is working.

Safe enablement shape for an OKE demo estate:

1. Read existing Logging logs, log groups, capture filters, Service Connector
   Hub targets, and subnet identities.
2. Create or reuse exactly one capture filter with a 100% `ALL` / `INCLUDE`
   rule. Do not create empty capture-filter records.
3. Remove only a known failed empty Flow Log record after confirming it has no
   usable source binding.
4. Enable exactly five subnet Flow Logs with 30-day retention for the demo's OKE
   network lanes: the node subnet, Kubernetes API endpoint subnet, load-balancer
   subnet, and the two pod-network subnets. If the live topology has a different
   pod-subnet count, stop and report the topology mismatch rather than guessing
   additional targets.
5. Do not change NSGs, Security Lists, route tables, NAT gateways, or
   application traffic while adding observability.

Command families to validate with installed help before rendering exact flags:

```bash
python3 scripts/oci_cli_help.py --json "logging log list"
python3 scripts/oci_cli_help.py --json "logging log create"
python3 scripts/oci_cli_help.py --json "logging log update"
python3 scripts/oci_cli_help.py --json "network capture-filter list"
python3 scripts/oci_cli_help.py --json "network capture-filter create"
python3 scripts/oci_cli_help.py --json "network capture-filter update"
python3 scripts/oci_cli_help.py --json "sch service-connector list"
```

Use `oci_cli network capture-filter create --filter-type FLOWLOG` with
`--flow-log-capture-filter-rules file://<TMP_0600_RULES_JSON>` only after help
validation. Use `oci_cli logging log create --log-type SERVICE
--retention-duration 30 --configuration file://<TMP_0600_CONFIG_JSON>` for each
subnet Flow Log. The service connector should already forward the Logging log
group to Log Analytics; if it does not, report the missing connector as an
enablement gate instead of creating a parallel path without review.

After enablement, prove ingestion with a source-wide query before a source-IP
drilldown:

```bash
./scripts/oci_logan.sh -q "'Log Source' = 'OCI VCN Flow Logs' | stats count by 'Action' | sort -count" -t 1h
./scripts/oci_logan.sh -q "'Log Source' = 'OCI VCN Flow Logs' and 'Source IP' = '<SOURCE_IP>' | stats count as requests by Action, 'Destination Port', 'Rule Type', 'Rule Name' | sort -requests" -t 24h
```

For MELTS-style investigations, correlate in this order:

- VCN Flow Logs: source IP, destination IP/port, action, packets/bytes, rule
  type/name when present.
- Load Balancer Access Logs: client IP, listener/backend status, request count.
- Cloud Guard / security logs: open problem IDs, detector/risk labels, MITRE
  mapping when provided.
- Traces: prove whether traffic reached instrumented app code.
- OCI Monitoring: CPU, memory, LB backend health, node/pod saturation.

Grounded answers should name the evidence sources used and keep conclusions
proportional. Example: "blocked before the app" requires Flow Log rejects or LB
backend evidence; "no traces" alone only proves the instrumentation saw no app
span.

### OCI incident troubleshooting receipt

For customer-demo or agent-facing investigations, produce a short receipt before
writing the final answer. The receipt is not a raw data dump; it is a
redaction-safe evidence envelope that lets another operator rerun the same
investigation without guessing which sources were checked.

Use the helper to start from the current canonical receipt shape:

```bash
python3 scripts/oci_oke_demo_troubleshoot.py receipt-template --context "<NAMED_CONTEXT>" --pretty
```

Minimum receipt fields:

```json
{
  "schema_version": "oci-skills.incident-troubleshooting-receipt.v1",
  "case_type": "connection-source-investigation|oke-app-agent|custom",
  "time_window": "<ISO8601_OR_DURATION>",
  "target_scope": {
    "compartment": "<COMPARTMENT_PLACEHOLDER>",
    "region": "<REGION>",
    "cluster": "<OKE_CLUSTER_PLACEHOLDER>",
    "namespace": "<NAMESPACE_PLACEHOLDER>"
  },
  "evidence_sources": [
    {
      "source": "vcn_flow_logs|load_balancer_logs|cloud_guard|traces|monitoring|audit",
      "query_or_command": "<SANITIZED_QUERY_OR_COMMAND>",
      "status": "verified|empty|degraded|unavailable",
      "result_summary": "<COUNTS_AND_FIELDS_ONLY>",
      "coverage_gap": "<NONE_OR_GAP>"
    }
  ],
  "conclusion_level": "provider_verified|configured|unavailable|inconclusive",
  "next_action": "<READ_ONLY_RETRY_OR_REVIEWED_MUTATION>"
}
```

Keep `conclusion_level` strict:

- `provider_verified`: current rows or service API results support the claim.
- `configured`: policies, connectors, sources, or manifests exist, but current
  data movement or runtime behavior was not proven.
- `unavailable`: the source/tool/control-plane path was unreachable; no
  service or reachability verdict was inferred.
- `inconclusive`: sources disagree or the minimum evidence set is missing.

For connection-source degradation, the minimum evidence set is Flow Log ingestion
proof plus one source-IP query. If Flow Logs are unavailable, the final answer
must say "connection source degraded" and list the exact Logging, Service
Connector Hub, Log Analytics source/parser, compartment subtree, and time-window
checks still required.

## Reusable generic queries

```
# OCI console password spraying (one source, many users)
'Log Source' = 'OCI Audit Logs' and Status = 'Failure' | stats distinctcount('User Name') as users by 'Source IP' | where users > 5

# OCI off-hours admin activity
'Log Source' = 'OCI Audit Logs' and ('Event Type' like '*create*' or 'Event Type' like '*delete*') | eval hour = formatDate(Time,'HH') | where hour < '06' or hour > '22' | stats count as actions by 'Principal Name', hour | sort -actions

# cross-compartment activity by principal
'Log Source' = 'OCI Audit Logs' | stats distinctcount('Compartment Name') as comps, count as actions by 'Principal Name' | where comps > 2 | sort -comps

# WAF multi-vector threat scoring
'Log Source' = 'OCI WAF Logs' and Action = 'BLOCK' | stats count as blocks, distinctcount('Rule Key') as rules by 'Client IP' | eval score = blocks + (rules*5) | where rules > 2 | sort -score

# web scanner (high requests, few status codes)
'Log Source' = 'OCI Load Balancer Access Logs' | stats count as reqs, distinctcount('Response Code') as codes by 'User Agent' | where reqs > 50 and codes < 5 | sort -reqs

# Cloud Guard findings grouped
'Log Source' = 'OCI Cloud Guard Problems' | link 'Instance OCID', 'Finding Name' | sort -Count

# compute stop/terminate spike
'Log Source' = 'OCI Audit Logs' and ('Event Type' like '*stopinstance' or 'Event Type' like '*terminateinstance') | timestats span = 1h count as Actions

# API burst by principal (rate anomaly)
'Log Source' = 'OCI Audit Logs' | timestats span = 5m count as calls by 'Principal Name' | where calls > 100 | sort -calls

# Windows brute force (failed logon spike)
'Log Source' = 'Windows Security Events' and 'Event ID' = '4625' | stats count as Fails, distinctcount('Source Address') as Sources by User | where Fails > 3 | sort -Fails

# privileged group membership change
'Log Source' = 'Windows Security Events' and 'Event ID' in ('4728','4732','4756') | stats count as Changes by User, 'Host Name (Server)' | sort -Changes

# rare parent/child process (outlier hunt)
'Log Source' = 'Windows Sysmon Events' and 'Process Name' != null | stats count as n, distinctcount('Host Name') as hosts by 'Parent Process Name', 'Process Name' | where n <= 3 and hosts <= 2 | sort n

# DNS exfiltration (long random labels)
'Log Source' = 'Windows Sysmon Operational Logs' and 'Event ID' = '22' and 'Query Name' matches '^[a-zA-Z0-9]{30,}\.' | stats count as Q by 'Host Name', 'Query Name' | sort -Q
```

**Network top-talkers by volume** (VCN Flow Logs, byte aggregation — bandwidth,
not event count):
```
'Log Source' = 'OCI VCN Flow Logs' | stats sum(Bytes) as total_bytes by 'Source IP' | sort -total_bytes | head 20
```

**Source-IP connection errors** (VCN Flow Logs, rule attribution where fields exist):
```
'Log Source' = 'OCI VCN Flow Logs' and 'Source IP' = '<SOURCE_IP>' | stats count as requests by Action, 'Destination Port', 'Protocol', 'Rule Type', 'Rule Name' | sort -requests | head 50
```

## Risks to flag

- Quoting mistakes on string-vs-numeric fields are the #1 cause of "valid query,
  zero rows / parse error" — verify field type before trusting an empty result.
- An empty/partial result from a single noisy query is **inconclusive**, not
  proof of absence — widen the window or simplify the filter before concluding.
- A missing `OCI VCN Flow Logs` source or zero rows after fresh enablement is a
  collection/ingestion gap until the Logging log, connector, log group, source,
  parser, retention, compartment subtree, and time window are verified.
- Never put real entity names, IPs, or principal names in committed queries —
  parameterize them.

## Official documentation

Canonical Oracle docs for the services covered above (verified live):

- [Logging Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)

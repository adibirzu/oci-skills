---
name: oci-log-analytics
description: >-
  OCI Log Analytics (Logan) administration and querying via oci-cli and OCI
  SDK: OCL query language (stats, timestats, where, eval, link), running queries,
  sources, parsers, fields, lookups, entities, log groups, on-demand log upload,
  saved searches, detections (Sigma→OCL), dashboards, and migration. Triggers:
  Log Analytics, Logan, OCL, LQL, log query, execute_query, time_range, Log Source,
  Audit Logs query, parser, log source, log group, entity, saved search,
  scheduled search, Cloud Guard / WAF / Sysmon query, Sigma-to-OCI, Sentinel KQL
  migration, dashboard, upload_log_file, VCN Flow Logs, flow-log capture filters,
  connection-source investigations, network rejects, Windows Event collection,
  Management Agent onboarding, RDP / logons. Read-only querying by default;
  content changes go through the shared safety core.
---

# OCI Log Analytics (Logan)

Query and administer OCI Log Analytics safely. Querying is **read-first**; source,
parser, entity, and dashboard changes are mutations and go through the shared
tenancy-safety core (`oci_cli`, `run_action`). Never inline real
OCIDs, IPs, the LA namespace, entity names, or tenant field values — use
`<PLACEHOLDER>` tokens.

## First move (always)

1. Confirm which tenancy/compartment you are reading:
   ```bash
   ./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>
   ```
2. Run a query read-only with the helper (auto-resolves the namespace):
   ```bash
   ./scripts/oci_logan.sh -q "'Log Source' = 'OCI Audit Logs' | stats count by 'Principal Name'" -t 24h
   ```
3. Search the KB before debugging a query/source error:
   ```bash
   python3 scripts/kb_lookup.py "log analytics query" log-analytics
   ```

Read [../../references/log-analytics.md](../../references/log-analytics.md) for the
OCL cheat-sheet, command shapes, and reusable queries, and
[../../references/tenancy-safety.md](../../references/tenancy-safety.md) for the
safety rules.

## Routing — pick the task

| Request mentions… | Go to |
|---|---|
| write/run/fix a query, stats, timestats, "why no rows" | OCL query language |
| run a query from the CLI/SDK, time range, namespace | Running queries |
| source, parser, field, lookup, custom log shape | Sources / parsers / fields |
| entity, log group, association, upload | Entities & log groups |
| detection, saved/scheduled search, Sigma→OCI | Detections |
| Windows Security/System/Application channels, Management Agent, RDP/logon monitoring | Windows access monitoring fast track |
| VCN Flow Logs, network rejects, source-IP investigations, missing connection-source data | VCN Flow Logs ingestion and connection investigations |
| dashboard import/export, migrate content, KQL→OCL | Migration / dashboards |

## Common multi-step flows

| Task | Sequence |
|------|----------|
| Write a query that returns rows | apply the field-typing rules (quote multi-word/string-int fields, KB-060/062) → run via `oci_logan.sh -t` → if empty, widen the window and add `--compartment-id-in-subtree true` before concluding (KB-063, KB-070) |
| Execute MCP Logan query | sanitize tool arguments to strip non-query parameters (`time_range`, `limit`) to prevent Pydantic validation errors (KB-009, KB-011) → execute `oci_logan_execute_query` → if transport fails, immediately fall back to the direct OCI CLI/SDK adapter (KB-042) |
| Audit "who did what" | query `'Log Source' = 'OCI Audit Logs'` → `stats count by 'Principal Name'` → set the window with `-t` (time is out-of-band, KB-063) |
| Build a detection | author OCL (or convert Sigma→OCL) → validate live (watch bulk-validation timeout, KB-071) → save with the current `etag` (KB-065) → schedule |
| Onboard Windows access monitoring | verify current standalone Windows Agent prerequisites → deploy the Log Analytics plug-in → map one `Host (Windows)` entity → associate the three Oracle-defined Windows sources → prove fresh Security/System/Application rows → create five saved searches/dashboard widgets → create scheduled metrics → create alarms disabled and enable one canary |
| Migrate content in | export the source dashboard → convert KQL→OCL → import → validate against live data |
| Investigate high-volume connection errors | prove `OCI VCN Flow Logs` ingestion → query source IP by action/port/rule → correlate LB access logs, Cloud Guard, traces, and OCI metrics → report coverage gaps separately from conclusions |
| Enable OKE subnet Flow Logs | inventory the target cluster's actual node, endpoint, load-balancer, and pod-network subnet roles plus existing bindings → select capture scope, sampling, retention, and cost explicitly in a sanitized inventory → run `scripts/target_derived_plan.py --inventory <SANITIZED_INVENTORY_JSON>` → plan only missing Flow Logs through the reviewed Logging-to-Log-Analytics path → never delete a record from generic guidance → do not change NSGs, Security Lists, route tables, or app traffic |
| Produce an OCI incident troubleshooting receipt | collect source inventory, Flow Log ingestion proof, source-IP OCL rows, trace reachability, Monitoring summaries, Cloud Guard/security rows, and explicit coverage gaps → emit the receipt schema from the reference → never infer a reachability verdict from missing sources |
| Recover a MELTS investigation timeout | generate `scripts/oci_oke_demo_troubleshoot.py melts-investigate-timeout` → rerun source-wide Flow Log and source-IP queries first → correlate traces, Monitoring, and Cloud Guard only when those sources are available → keep timeout/cached receipts below provider_verified evidence |

## Common tasks

```bash
# Ad-hoc read-only query (helper resolves the namespace; -t accepts 5m/24h/7d).
./scripts/oci_logan.sh -q "'Log Source' = 'OCI WAF Logs' and Action = 'BLOCK' | stats count by 'Client IP' | sort -count" -t 7d

# Offline demo command plan for degraded Connections / missing VCN Flow Logs.
python3 scripts/oci_oke_demo_troubleshoot.py connections-degraded --context "<NAMED_CONTEXT>" --pretty

# Offline MELTS command plan when an investigation exceeds its response budget.
python3 scripts/oci_oke_demo_troubleshoot.py melts-investigate-timeout --context "<NAMED_CONTEXT>" --pretty

# Raw CLI query (the verb is `query search`; keep the query time-agnostic).
# Always include --compartment-id-in-subtree true to search child compartments.
oci_cli log-analytics query search --namespace-name <LA_NAMESPACE> \
  --compartment-id <COMPARTMENT_OCID> --compartment-id-in-subtree true \
  --query-string "'Log Source' = 'OCI Audit Logs' | timestats span = 1h count" \
  --sub-system LOG \
  --time-start <RFC3339> --time-end <RFC3339> --timezone UTC

# List sources INCLUDING Oracle system sources (pass --all to prevent pagination truncation).
oci_cli log-analytics source list --namespace-name <LA_NAMESPACE> \
  --compartment-id <COMPARTMENT_OCID> --is-system ALL --name <SUBSTRING> --all

# List log groups with pagination and JMESPath projection
oci_cli log-analytics log-group list --namespace-name <LA_NAMESPACE> \
  --compartment-id <COMPARTMENT_OCID> --all \
  --query 'data.items[].{id:id,name:"display-name"}'

# Repair entity metadata (entity name is immutable after create).
run_action --risk in-place --compartment <COMPARTMENT_OCID> --description "repair entity metadata" -- \
  oci_cli log-analytics entity update --namespace-name <LA_NAMESPACE> \
  --entity-id <ENTITY_OCID> --metadata file://<TMP_0600_METADATA_JSON> --force
```

## Field-typing rules (the #1 query gotcha)

- **Quote multi-word field names:** `'Log Source'`, `'Principal Name'`, `'Original Log Content'`.
- **String-typed integers are quoted:** `'Event ID' = '4625'`, `'Response Code' = '403'`.
- **True numeric LONG fields are bare:** `'Destination Port' = 443`, `'Bytes Sent' > 0`.
- `like` = `*` glob wildcards; `matches` = regex anchors — never mix.
- **Time range is out-of-band** — keep saved searches time-agnostic; pass the
  window via `--time-filter` / `TimeRange`.
- **Search the subtree:** `--compartment-id-in-subtree true` or child
  compartments are excluded.
- **Canonical field and source mappings (KB-001, KB-004, KB-029):**
  * Grouping by host/entity: use `Entity` in STATS BY, NOT `HostName` or `Entity Name` (both cause `Invalid parameter`).
  * Field names: `'Event ID'` (not `EventID`), `'Process Name'` (not `Image`), `'Command Line'` (not `CommandLine`), `'Source IP'`, `'Destination IP'`.
  * Kubernetes container logs have **no** `Severity` field — querying `Severity = 'ERROR'` returns 0 rows.
  * SSH logs are captured under `"Linux Secure Logs"`, NOT `"Linux Syslog Logs"`.
  * WAF log source is `"OCI WAF Logs"`; `"Rule Name"` is not a valid STATS BY field.
  * Windows system events source is `"Windows System Events"`.

## Safety notes

- **Logan MCP `execute_query` Parameter Constraints (KB-009, KB-011):**
  The `oci_logan_execute_query` MCP tool accepts ONLY the `query` argument.
  Auto-injecting `time_range`, `timeRange`, `time_range_minutes`, or `limit` causes
  Pydantic validation errors (`Unexpected keyword argument`). Always strip non-query
  arguments before calling MCP. Use direct OCI CLI (`scripts/oci_logan.sh -t`) or the direct
  OCI SDK adapter when time-range bounds are required.
- **MCP Transport Failure Fallback (KB-042):**
  If the Logan MCP server transport is unreachable or throws a connection error,
  immediately fall back to the direct OCI CLI/SDK adapter rather than failing the investigation.
- **Discover Sources First (KB-001):**
  Log source names vary between tenancies. Before authoring or troubleshooting queries,
  discover active sources with: `'*' | stats count by 'Log Source' | sort -count`.
- **Avoid Unindexed Full-Text Scans (KB-013):**
  Queries using `'Original Log Content' like '%...%'` scan millions of rows and trigger 60s+ timeouts.
  Always narrow queries first using indexed fields (`Log Source`, `Entity`, `'Event ID'`, `Severity`)
  before performing substring matches.
- **Pagination and Subtree Querying:**
  Always pass `--all` to `source list`, `entity list`, and `log-group list` to prevent
  silent truncated records. Always include `--compartment-id-in-subtree true` on queries
  so child compartments are not omitted (KB-063).
- **Read-only by default.** Querying changes nothing. Creating/updating sources,
  parsers, fields, entities, saved searches, or dashboards is a mutation —
  gate it with `run_action`, and `get` for the `etag` first
  (optimistic concurrency → `412` otherwise).
- **Never print or commit tenant data.** The LA namespace, entity names, IPs, and
  principal names are sensitive — parameterize queries and pipe output through
  `redact` before sharing.
- **An empty result is inconclusive,** not proof of absence — check field typing
  and widen the window before concluding.
- **Missing VCN Flow Logs are a source gap,** not proof that traffic was absent
  or blocked. Verify Logging, connector, Log Analytics source/parser, retention,
  subtree scope, and window before making a network-layer claim.
- **Windows Management Agent Remote Provisioning (KB-599):**
  When installing the Management Agent on remote Windows servers via WinRM, stage `.ps1`
  scripts using chunked base64 writing (e.g. 2000-char chunks) instead of inline `-EncodedCommand`
  strings, which fail when exceeding the Windows cmdline limit (8192 chars). Use Object Storage
  Pre-Authenticated Requests (PAR) to stream the Windows agent ZIP with embedded JDK 21
  (`oracle.mgmt_agent.windows.zip`), create `input.rsp` with `logan`, `opsiHost`, and `appmgmt`
  plugins, and execute `installer.bat`. Ensure install keys are created in `COMP_OBSERVABILITY`.
- **Private Cross-VCN Log Analytics Ingestion & Remote Access via LPG (KB-600):**
  When workloads (such as AD domain controllers, honeypots, or cyber ranges) live in isolated
  VCNs, establish a Local Peering Gateway (LPG) mesh to the management/tooling VCN (e.g. OKE running
  Guacamole or telemetry collectors). Configure mutual static CIDR routes in route tables and
  security list rules. For nested virtualized hypervisors (e.g. Proxmox/Ludus), use iptables DNAT
  on the parent host to map private service ports (e.g. 3389/3390 RDP, 5985/5986 WinRM).
- **Open-Source Connector Catalogs & External Data Ingestion (KB-601):**
  When onboarding non-native logs (PostgreSQL, Redis, Kafka, Kubernetes ingress, Cloudflare, S3),
  catalog connectors following the open-source connector schema (`dataworkers.io` pattern). Route
  events into OCI Log Analytics via OCI Streaming (Kafka Connect / Service Connector Hub) or direct
  on-demand REST upload (`oci log-analytics upload upload-log-file`) to eliminate custom agent sprawl.
- **Sigma Detection Rule Compiler & Field Normalization (KB-602):**
  Compile Sigma YAML rules to OCL query strings using deterministic field mapping:
  * `Image` / `CommandLine` -> `'Process Name'` / `'Command Line'`
  * `User` / `AccountName` -> `'Principal Name'`
  * `SourceIp` / `DestinationIp` -> `'Source IP'` / `'Destination IP'`
  * `EventID` -> `'Event ID'` (string-integer quoted, e.g. `'Event ID' = '4688'`)
  * Convert selection conditions to `where` clauses with `like` / `matches` and append aggregation pipelines (`| stats count by ... | where count > threshold`).
- **Palantir Threat Matrix & MITRE ATT&CK Classification (KB-603):**
  Map Log Analytics detection queries directly to MITRE ATT&CK tactics (TA0001-TA0040) and techniques
  (T1059, T1078, etc.). Classify coverage across detection rules into a multi-tier threat matrix
  (Tactic -> Technique -> Detection Rule -> Live OCL query) for immediate incident visualization.
- **Telemetry Lag Monitoring & Checkpointing (KB-604):**
  When streaming high-velocity telemetry into Log Analytics, track partition lag and stream timestamps.
  Maintain durable partition checkpoints so consumers resume without duplicate ingestion or telemetry blind spots.
- **Portable Deployment & Loopback Port Fallback (KB-605):**
  In portable deployment scripts (`deploy_portable.sh`), probe loopback ports (e.g. 8000, 3000) with
  `nc -z 127.0.0.1 <port>` before binding. If occupied, automatically increment and bind to the next
  available loopback port, avoiding collision with ambient services.
- **Never invent `oci` flags.** Fetch the exact command shape first:
  `python3 scripts/oci_cli_help.py <service> <op>`.

## Expected output

```markdown
**Finding** — what the query/source/entity shows (generic, no tenant values).
**Evidence** — redacted query + row counts / CLI result.
**Action** — the query or command; mutations gated by confirm/dry-run.
**Verification** — re-run the query / re-list the resource showing the result.
**KB** — KB entry used (log-analytics), or new KB-<n> added.
```

## Official documentation

[Logging Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm). Full list in the [log-analytics reference](../../references/log-analytics.md).

**Open Knowledge Format grounding** — every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill to build an OCI customer solution, cite the most specific official page through that index so every claim stays verifiable; the non-official MCP gateway is never a source of truth.

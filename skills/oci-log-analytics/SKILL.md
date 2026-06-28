---
name: oci-log-analytics
description: >-
  OCI Log Analytics (Logan) administration and querying via oci-cli and the OCI
  SDK: the OCL query language (search + pipe commands like stats, timestats,
  where, eval, link, fields), running and validating queries, sources, parsers,
  fields, lookups, entities and log groups, on-demand log upload and continuous
  ingestion, saved/scheduled searches, detections (including Sigma→OCL
  conversion), management dashboards, and content migration. Use whenever a
  request mentions OCI Log Analytics, Logan, OCL, LQL, a log query, Log Source,
  OCI Audit Logs query, parser, log source, log group, entity, saved search,
  scheduled search, Cloud Guard / WAF / Sysmon query, Sigma-to-OCI, Sentinel KQL
  migration, management dashboard, or upload_log_file. Read-only querying by
  default; content changes go through the shared safety core.
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
| dashboard import/export, migrate content, KQL→OCL | Migration / dashboards |

## Common multi-step flows

| Task | Sequence |
|------|----------|
| Write a query that returns rows | apply the field-typing rules (quote multi-word/string-int fields, KB-060/062) → run via `oci_logan.sh -t` → if empty, widen the window and add `--compartment-id-in-subtree` before concluding (KB-063, KB-070) |
| Audit "who did what" | query `'Log Source' = 'OCI Audit Logs'` → `stats count by 'Principal Name'` → set the window with `-t` (time is out-of-band, KB-063) |
| Build a detection | author OCL (or convert Sigma→OCL) → validate live (watch bulk-validation timeout, KB-071) → save with the current `etag` (KB-065) → schedule |
| Migrate content in | export the source dashboard → convert KQL→OCL → import → validate against live data |

## Common tasks

```bash
# Ad-hoc read-only query (helper resolves the namespace; -t accepts 5m/24h/7d).
./scripts/oci_logan.sh -q "'Log Source' = 'OCI WAF Logs' and Action = 'BLOCK' | stats count by 'Client IP' | sort -count" -t 7d

# Raw CLI query (the verb is `query search`; keep the query time-agnostic).
oci_cli log-analytics query search --namespace-name <LA_NAMESPACE> \
  --compartment-id <COMPARTMENT_OCID> --compartment-id-in-subtree true \
  --query-string "'Log Source' = 'OCI Audit Logs' | timestats span = 1h count" \
  --sub-system LOG \
  --time-start <RFC3339> --time-end <RFC3339> --timezone UTC

# List sources INCLUDING Oracle system sources (match internal name AND display name).
oci_cli log-analytics source list --namespace-name <LA_NAMESPACE> \
  --compartment-id <COMPARTMENT_OCID> --is-system ALL --name <SUBSTRING>

# Repair entity metadata (entity name is immutable after create).
run_action --risk in-place --compartment <COMPARTMENT_OCID> --description "repair entity metadata" -- \
  oci_cli log-analytics entity update --namespace-name <LA_NAMESPACE> \
  --entity-id <ENTITY_OCID> --metadata file://<TMP_0600_METADATA_JSON> --force
```

## Field-typing rules (the #1 query gotcha)

- **Quote multi-word field names:** `'Log Source'`, `'Principal Name'`.
- **String-typed integers are quoted:** `'Event ID' = '4625'`, `'Response Code' = '403'`.
- **True numeric LONG fields are bare:** `'Destination Port' = 443`, `'Bytes Sent' > 0`.
- `like` = `*` glob wildcards; `matches` = regex anchors — never mix.
- **Time range is out-of-band** — keep saved searches time-agnostic; pass the
  window via `--time-filter` / `TimeRange`.
- **Search the subtree:** `--compartment-id-in-subtree true` or child
  compartments are excluded.

## Safety notes

- **Read-only by default.** Querying changes nothing. Creating/updating sources,
  parsers, fields, entities, saved searches, or dashboards is a mutation —
  gate it with `run_action`, and `get` for the `etag` first
  (optimistic concurrency → `412` otherwise).
- **Never print or commit tenant data.** The LA namespace, entity names, IPs, and
  principal names are sensitive — parameterize queries and pipe output through
  `redact` before sharing.
- **An empty result is inconclusive,** not proof of absence — check field typing
  and widen the window before concluding.
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

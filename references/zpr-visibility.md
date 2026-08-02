# ZPR Visibility Reference

Reusable, sanitized workflow for OCI Zero Trust Packet Routing visibility. This
reference is based on local ZPR visibility runbooks and keeps only portable
patterns: no real OCIDs, IPs, security attribute names, namespaces, or topology.

## Quick navigation

Select operating model, IAM, collection, flow correlation, Log Analytics,
failure modes, or source origins.

## Operating model

- Run inventory collection frequently enough for operations, daily for audit.
- Keep VCN Flow Logs enabled on VCNs/subnets/VNICs that host ZPR-protected
  resources.
- Emit collector and correlation records into an OCI custom log, then forward or
  upload them into Log Analytics.
- Review HIGH/CRITICAL findings daily.

## IAM minimums

Collector principal:

```text
Allow group <ZPR_COLLECTOR_GROUP> to read zpr-family in tenancy
Allow group <ZPR_COLLECTOR_GROUP> to read security-attribute-namespaces in tenancy
Allow group <ZPR_COLLECTOR_GROUP> to read all-resources in tenancy
Allow group <ZPR_COLLECTOR_GROUP> to use log-content in compartment <OBS_COMPARTMENT>
```

Connector Hub service principal for Log Analytics upload:

```text
Allow any-user to {LOG_ANALYTICS_LOG_GROUP_UPLOAD_LOGS} in compartment <OBS_COMPARTMENT>
  where all { request.principal.type='serviceconnector',
             target.loganalytics-log-group.id='<LA_LOG_GROUP_OCID>' }
```

## Collector workflow

1. Create the custom log and Log Analytics log group/source/parser through
   Terraform or a reviewed script.
2. Collect ZPR inventory into a snapshot and JSONL records.
3. Emit the JSONL records to the custom log.
4. Search OCI Logging first; only then debug Log Analytics.

```bash
oci_cli logging-search search-logs \
  --search-query "search \"<TENANCY_OCID>/<LOG_GROUP_OCID>/<CUSTOM_LOG_OCID>\"" \
  --time-start "<RFC3339_START>" \
  --time-end "<RFC3339_END>" \
  --limit 50
```

Expect one entry per emitted record and a stable `record_type` discriminator.

## Flow correlation

Use exported or queried VCN Flow Logs plus the latest ZPR inventory snapshot.
Classify rows conservatively:

| Classification | Meaning | Operator response |
|---|---|---|
| `expected_accepted` | Flow matches policy intent | No action |
| `expected_rejected` | Flow denied as intended | No action |
| `unexpected_accepted` | Flow was accepted but policy correlation expected deny | Review policy/security attributes before changing anything |
| `suspected_misconfiguration` | Flow rejected though policy correlation expected allow | Triage connectivity, attributes, and policy scope |

Do not call either unexpected class a bypass without independent policy and flow
evidence.

## Log Analytics content

Custom source requirements:

- JSON parsing.
- `record_type` as primary discriminator.
- Fields for resource identity, policy/security-attribute summary,
  flow direction, action, severity, and classification.

Before importing dashboards, validate every query with parse. Zero rows are OK;
HTTP 400 / parse errors are not.

```bash
oci_cli log-analytics query parse \
  --namespace-name "<LA_NAMESPACE>" \
  --sub-system LOG \
  --query-string "<dashboard_query>"
```

Dashboard import should be idempotent: dry-run/preview tiles, delete or replace
the previous same-name dashboard, import, then validate every tile returns HIT
or a known zero-row state.

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Logging search returns no collector rows | Wrong custom log OCID, wrong time window, or missing `use log-content` | Verify custom log, IAM, and RFC3339 window |
| LA dashboard parses fail | Parser/source/fields not created before dashboard import | Create fields, parser, source, then parse queries |
| LA query returns zero but Logging has rows | Connector Hub or LA source association missing | Verify connector target and LA log group upload policy |
| Flow classifications look wrong | Inventory snapshot stale relative to flow window | Recollect inventory and correlate with matching time range |
| Collector sees no ZPR resources | Missing `read zpr-family` or security-attribute permissions | Fix IAM before debugging policy logic |

## Source pattern origins

Distilled from `/Users/abirzu/dev/oci-zpr-visibility/docs/runbook.md`.

# DBM / OPSI Reference

Reusable patterns for OCI Database Management (DBM) and Operations Insights
(OPSI) enablement and troubleshooting. Keep tenant names, OCIDs, hostnames, IPs,
service names, passwords, wallets, and Bastion session IDs out of committed
artifacts.

## Discovery

For Base Database Service, discover in this order:

1. compartment
2. DB system
3. DB homes
4. databases / CDB
5. pluggable databases / PDBs

If `oci db database list` is unreliable in the local CLI, use the OCI Python SDK
for discovery rather than guessing resource IDs from stale config.

## Enablement sequence

1. Confirm subnet, route, NSG/security list, and private endpoint reachability.
2. Validate the monitoring user is open and can connect to CDB/PDB as intended.
3. Enable DBM and wait for managed database inventory.
4. Create OPSI Database Insight with the right resource type:
   - `database` for Base Database Service CDB/non-CDB targets.
   - `pluggabledatabase` for PDB targets.
5. Poll OPSI work requests and read errors/logs on failure.

DBM enabled does not imply OPSI enabled. Continue the OPSI step when DBM is
already enabled but the Database Insight is absent.

## OPSI validation

Prefer single-resource GET when you know an insight OCID. Aggregated list calls
can flap or return incomplete windows.

```bash
oci_cli opsi database-insights get --database-insight-id "<DATABASE_INSIGHT_OCID>"
```

If the insight OCID is unknown, query one lifecycle state at a time, union by
insight OCID, and treat empty or inconsistent windows as UNKNOWN rather than
NOT_FOUND.

```bash
for state in CREATING UPDATING ACTIVE FAILED NEEDS_ATTENTION; do
  oci_cli opsi database-insights list \
    --compartment-id "<COMPARTMENT_OCID>" \
    --lifecycle-state "$state" \
    --all
done
```

## Performance Hub / AWR / ADDM

When Performance Hub prompts for privileges, validate the monitoring user before
blaming DBM. For a common monitoring user such as `DBSNMP`, root-level grants
with `CONTAINER=ALL` may be required for CDB and PDB coverage. Licensing for
Diagnostics/Tuning Pack features applies.

Typical privilege classes:

- `CREATE PROCEDURE`
- `SELECT ANY DICTIONARY`
- `SELECT_CATALOG_ROLE`
- `ALTER SYSTEM`
- `ADVISOR`
- execute on `SYS.DBMS_WORKLOAD_REPOSITORY`
- SQL Tuning Set administration when SQL tuning features are used

PDB ADDM/AWR can be empty even when root AWR exists. Enable PDB AWR autoflush
and seed snapshots in the target PDB when the workflow requires PDB-level AWR.
Filter ADDM snapshot pairs by the PDB `CON_DBID`; root snapshot IDs do not work
for PDB `DBMS_ADDM.ANALYZE_DB`.

## `DbcsEntityChangeWorkflowFailed`

If OPSI create reaches collection startup and fails with
`DbcsEntityChangeWorkflowFailed`, check:

- service name is the listener-registered service, not a guessed DB/PDB name
- credential payload uses the expected source, often Vault-backed credentials
- DBM/OPSI principals can read the secret
- monitoring user password is current and satisfies database password policy
- private endpoint reaches the listener
- work-request errors/logs, not only top-level lifecycle

## Log Analytics DB log ingestion

For DBCS/Base DB alert/audit/host logs, DBM/OPSI enablement is not enough.
Log Analytics source associations require a Management Agent-backed entity or an
existing valid ingestion path.

Use canonical built-in source names, not friendly display names:

- `DBAlertLogSource`
- `DBAuditLogSource`
- `LinuxSyslogSource`
- `unifieddbauditlogfromdbsource122`

Current OCI CLI association shape:

```bash
oci_cli log-analytics assoc upsert-assocs \
  --namespace-name "<LA_NAMESPACE>" \
  --items file://associations.json
```

Payloads should be an `items` list with `associationProperties`. Block early
with a precise message when no Management Agent-backed entity is configured,
rather than creating detached entities that cannot ingest.

## Redaction boundary

Never redact values before parsing and joining OCI JSON. If both sides of an
OCID-keyed join become `<OCI_OCID>`, every resource can match every other
resource. Keep raw values in memory for logic, and redact only at display,
logging, error, and committed-artifact boundaries.

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| Performance Hub asks for privileges | Monitoring user lacks advanced grants | Apply reviewed grants; reopen Performance Hub |
| PDB ADDM/AWR empty | PDB AWR autoflush disabled or wrong DBID | Enable PDB AWR, seed snapshots, filter by `CON_DBID` |
| OPSI list says NOT_FOUND but console shows ACTIVE | Aggregated list flapped | GET by known insight OCID; otherwise return UNKNOWN on inconsistent list |
| Data Safe/OPSI matches every DB | Redaction happened before OCID join | Move redaction to display boundary |
| Log Analytics source association rejected | Detached entity or wrong payload/CLI verb | Use Management Agent-backed entity and `assoc upsert-assocs` |
| Data Safe target NEEDS_ATTENTION `ORA-01017` | Stored monitoring credential stale | Rotate DB password, update Vault and Data Safe credentials together |

## Source pattern origins

Distilled from `/Users/abirzu/dev/oci-dbman-opsi/KB.md`.

# DBM / OPSI Reference

Reusable patterns for OCI Database Management (DBM) and Operations Insights
(OPSI) enablement and troubleshooting. Keep tenant names, OCIDs, hostnames, IPs,
service names, passwords, wallets, and Bastion session IDs out of committed
artifacts.

**Primary owner:** `oci-dbm-opsi` owns Database Management, Operations Insights,
Performance Hub, and OCI-side AWR/ADDM/ASH enablement and troubleshooting.
`oci-observability-db` receives the explicit handoff for Monitoring alarms, APM,
Logging, and dashboards; it does not own DBM or OPSI lifecycle.

## Quick navigation

Start with response and discovery, then select enablement, OPSI, Performance
Hub/AWR, failure diagnosis, log ingestion, or redaction.

## Response contract

Start every response with: `Primary owner: oci-dbm-opsi.` Name
`oci-observability-db` only for the explicit Monitoring/APM/logging handoff, then
keep the answer on OCI-side DBM/OPSI
enablement and verification. Do not emit SQL, PL/SQL, grants, AWR queries, or
in-database commands; hand those to official `oracle/skills` `db/`. Before giving
an exact OCI command or JSON payload, validate its installed shape with
`oci_cli_help.py --json`; if help is unavailable, give the concise sequence and
required inputs instead of guessing. Every enable/create/update is a mutation:
show read-before-write and route the action through `run_action`, followed by
work-request and lifecycle verification.
Never offer inline monitoring credentials; require a Vault-backed credential
reference and least-privilege service-principal access.

In a Read/Skill-only harness, execution and CLI-help lookup are unavailable. Give
only the owner/handoff sentence, prerequisites, read → enable DBM → verify → enable
OPSI → verify sequence, likely failure checks, and required inputs. Do not emit OCI
commands, JSON, SQL, privilege lists, regions, service values, or payload shapes.
Do not include the literal `oci_cli`, guessed subcommands, flags, port numbers, or
code blocks; say that exact commands require installed-help validation in an
execution-capable session.

End every response with: `Monitoring alarms, APM, Logging, and dashboards hand off
to oci-observability-db; DBM/OPSI remains owned by oci-dbm-opsi.`

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

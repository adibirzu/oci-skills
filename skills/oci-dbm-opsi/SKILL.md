---
name: oci-dbm-opsi
description: >-
  OCI Administrator skill for Database Management (DBM) and Operations Insights
  (OPSI) enablement, validation, and troubleshooting for OCI databases. Use when
  working with DBM private endpoints, managed databases, OPSI database insights,
  Performance Hub, AWR/ADDM/ASH, DBSNMP monitoring users, Data Safe target
  drift, Management Agent-backed Log Analytics ingestion for DBCS/Base DB,
  DBM/OPSI work requests, Database Insight lifecycle flaps, or Base Database
  Service observability. Triggers: DBM, Database Management, OPSI, Operations
  Insights, Performance Hub, AWR, ADDM, ASH, DBSNMP, Database Insight,
  create-pe-comanged-database, DbcsEntityChangeWorkflowFailed, managed-database,
  database-insights, and DB log ingestion.
---

# OCI DBM / OPSI

Enable and troubleshoot OCI Database Management and Operations Insights without
leaking database topology or credentials. This skill is for the OCI control
plane and monitoring setup around a database; SQL tuning and deep in-database
work still routes to database-specific skills.

Apply the shared [skill entrypoint quality standard](../../references/skill-quality-standard.md)
and treat DBM, OPSI, in-database privileges, Performance Hub, and Log Analytics
ingestion as distinct enablement and evidence gates.

## First decisions

Resolve database type and lifecycle owner, CDB/PDB scope, region/compartment,
network path and private endpoint, connection method, monitoring-user state,
DBM and OPSI current states, licensing/privilege boundary, Log Analytics entity
path, expected work requests, and the exact read-only verification goal.

## Routing

| Surface | Owner |
|---|---|
| DBM private endpoint, managed database, OPSI insight, Performance Hub enablement | This skill |
| Base DB system/home/database/PDB lifecycle, backup, patch, Data Guard | **oci-database-cloud** |
| Autonomous DB lifecycle, ACL, wallet, service level, app connectivity | **oci-autonomous-db** |
| Deep SQL tuning, RMAN, AWR/ASH interpretation, or database remediation | Official database skill / DBA owner |
| Metrics, alarms, generic Logging/APM | **oci-observability-db** |
| Log Analytics source/entity/query mechanics | **oci-log-analytics** |

## First move

```bash
./scripts/oci_preflight.sh -c "$COMPARTMENT_OCID"
python3 scripts/kb_lookup.py "<symptom>" dbm
python3 scripts/kb_lookup.py "<symptom>" opsi
```

Read [references/dbm-opsi.md](../../references/dbm-opsi.md) for target-specific
flows and [references/observability-db.md](../../references/observability-db.md)
for broader Monitoring/APM/DB observability context.

## Common multi-step flows

| Task | Sequence |
|---|---|
| Enable DBM/OPSI for Base DB | discover DB system → CDB → PDBs with SDK/CLI fallback → verify network/private endpoint → validate DBSNMP/open grants → enable DBM → create OPSI insight → poll work requests |
| Validate existing DB observability | list managed databases → GET known OPSI insight IDs → verify DBM status, OPSI lifecycle, connection status, and work-request errors |
| Fix Performance Hub/AWR gaps | verify DBSNMP privileges → enable PDB AWR autoflush where needed → seed snapshots → validate ADDM/AWR views |
| Wire Log Analytics DB logs | require Management Agent-backed entity → normalize built-in source names → use current `assoc upsert-assocs` payload shape → verify ingestion |

## Safety notes

- Passwords and wallets belong in Vault or ignored local files only.
- Do not redact parsed OCI JSON before joining by OCID; redact only at display
  boundaries.
- DBM enabled does not prove OPSI enabled. Validate each service separately.
- Database grants can have licensing implications; call that out before applying
  Performance Hub, AWR, ADDM, or SQL Tuning privileges.
- Enabling DBM/OPSI, creating an OPSI insight, granting DBSNMP privileges, and
  wiring Log Analytics associations are mutations — run them through `run_action
  --risk <additive|in-place> --compartment <COMPARTMENT_OCID> --description
  "<...>" -- oci_cli ...` (honors `OCI_SKILLS_DRY_RUN=true` for a no-op preview)
  and get explicit user confirmation before applying a grant or enabling a
  service.

## Failure discrimination

- DBM enabled does not prove OPSI enabled, a healthy connection, Performance
  Hub privileges, AWR population, or DB log ingestion.
- `NotAuthorizedOrNotFound` can be IAM, wrong region/compartment/database scope,
  or absence. Resolve in that order without guessing.
- Separate private-endpoint routing, database listener/service, credential,
  monitoring-user grant, service work request, and agent/entity-association
  failures.
- A lifecycle flap or empty insight list is inconclusive until a known insight
  is read directly and its work-request/error history is inspected.

## Validation and evidence

Record discovery joins before redaction, then redact at the display boundary.
Verify private-endpoint/network readiness, managed-database connection state,
DBM lifecycle, OPSI insight lifecycle by direct GET, work requests, and the
minimum read-only SQL/grant canary authorized for the task. For Performance Hub,
prove required views/snapshots separately. For DB logs, prove current agent,
entity, association, source, parser, and one fresh row. State licensing and
approval status for every proposed database grant.

## Expected output

```text
Finding:      <DBM/OPSI state or failure>
Evidence:     <redacted work request, lifecycle, grant, or ingestion status>
Action:       <read-only check, dry-run, or gated command>
Verification: <managed-database, insight GET, work-request, SQL grant, or LA row>
KB:           <known KB applied, or new sanitized KB entry added>
```

## Official documentation

[Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm) ·
[Operations Insights](https://docs.oracle.com/en-us/iaas/operations-insights/home.htm)

**Open Knowledge Format grounding** - every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill, cite the most specific official page through that index; the non-official MCP gateway is never a source of truth.

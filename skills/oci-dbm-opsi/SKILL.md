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

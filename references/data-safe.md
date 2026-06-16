# OCI Data Safe Reference

Sanitized command/payload shapes for **OCI Data Safe** — target registration,
private endpoints, Security & User Assessment, Activity Auditing, Data Discovery,
and Data Masking. Every CLI call goes through `oci_cli` from `scripts/common.sh`;
registration/assessment runs are **mutations** gated by `run_mutating` /
`confirm`. Read `tenancy-safety.md` and `helper-conventions.md` first. Use
`<PLACEHOLDER>` tokens — never inline real OCIDs, IPs, service names, or
credentials.

> Data Safe is a **standalone `target-database` resource** — not a status flag on
> the database. It connects to the target through a Data Safe private endpoint (or
> ADB managed connectivity) using a DB service account.

## Target registration

Pass payloads as `file://` JSON so credentials never hit `argv`. Write the
credential file `0600` in a `0700` temp dir and delete it in a `finally`.

```bash
run_mutating "register target" oci_cli data-safe target-database create \
  --compartment-id <COMPARTMENT_OCID> --display-name <NAME> \
  --database-details file://database-details.json \
  --connection-option file://connection-option.json \
  --credentials file://credentials.json
```

`database-details.json` — keyed by target type:

```jsonc
// Autonomous DB:
{ "databaseType": "AUTONOMOUS_DATABASE", "infrastructureType": "ORACLE_CLOUD",
  "autonomousDatabaseId": "<ADB_OCID>" }
// Base DB / Exadata cloud service — keyed off the DB SYSTEM + service name,
// NOT the database OCID:
{ "databaseType": "DATABASE_CLOUD_SERVICE", "infrastructureType": "ORACLE_CLOUD",
  "dbSystemId": "<DB_SYSTEM_OCID>", "serviceName": "<SERVICE_NAME>", "listenerPort": 1521 }
```

`connection-option.json` (non-autonomous): `{ "connectionType": "PRIVATE_ENDPOINT",
"datasafePrivateEndpointId": "<DS_PE_OCID>" }`. `credentials.json`:
`{ "userName": "<USER>", "password": "<PASSWORD>" }`.

**Private endpoint:** `oci data-safe private-endpoint create --compartment-id
<COMPARTMENT_OCID> --display-name <NAME> --vcn-id <VCN_OCID> --subnet-id
<SUBNET_OCID>` returns a **work request** — wait on `SUCCEEDED` (not `ACTIVE`) and
re-list by display name to resolve the new PE OCID.

## DB-side privileges for the service account

- **Security / User Assessment:** `create session`, `select_catalog_role`,
  `select any dictionary`.
- **Activity Auditing (12.2+):** add `audit_viewer`, `audit_admin`.
- **Data Masking / Data Discovery:** schema-specific read/write — download the
  exact per-target script from the Console
  (Data Safe → Target databases → Register → **Download Privilege Script**).

## Security & User Assessment

```bash
# Refresh and read the latest security posture for a target.
run_mutating "refresh security assessment" oci_cli data-safe security-assessment refresh \
  --security-assessment-id <SA_OCID>
oci_cli data-safe security-assessment list --compartment-id <COMPARTMENT_OCID> \
  --target-id <TARGET_OCID> --query 'data[0]'
# User Assessment (risky users, privileges):
oci_cli data-safe user-assessment list --compartment-id <COMPARTMENT_OCID> --target-id <TARGET_OCID>
```

## Activity Auditing

```bash
# Audit-event queries use scim_query for the time window — NOT time_started/time_ended.
oci_cli data-safe audit-event list --compartment-id <COMPARTMENT_OCID> \
  --scim-query '(auditEventTime ge "<RFC3339_START>") and (auditEventTime le "<RFC3339_END>")'
# enable an audit policy + retention on the target as a mutation (gated).
```

The SDK `list_audit_events` only accepts time filtering via `scim_query`; passing
`time_started`/`time_ended` raises `unknown kwargs` (see `KB.md`).

## Data Discovery & Masking

`data-safe sensitive-data-model` (discover sensitive columns) and
`data-safe masking-policy` (define + apply masking) — both reference a registered
target and a discovery job. Masking is a mutation; never run it against a
production target without confirmation and a verified non-prod copy first.

## Gotchas

- **`target-database update` returns a work request** (`--wait-for-state
  SUCCEEDED`) and needs `--force` non-interactively.
- **A `DATABASE_CLOUD_SERVICE` target registered with a PDB service name** still
  associates (via `associated-resource-ids`) with the **DB system / CDB**, so
  discovery attributes Data Safe at the CDB level, not the PDB.
- **`NEEDS_ATTENTION` with `ORA-01017`** despite a healthy network path = stale
  service-account password — rotate `CONTAINER=ALL`, update the credential on the
  target (`target-database update --credentials file://... --force`), wait the
  work request. See `KB.md` (observability-db).

## Safety notes

- **Read assessments freely; gate registrations/masking/audit-policy changes.**
- **Never print or commit credentials** — `file://` payloads, `0600`/`0700`
  temp files, delete in `finally`, `redact` any output.
- **Mask only verified non-prod** — irreversible on the masked copy.

## Official documentation

Canonical Oracle docs for the services covered above (verified live):

- [Data Safe](https://docs.oracle.com/en-us/iaas/data-safe/doc/oracle-data-safe-overview.html)

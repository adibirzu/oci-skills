---
name: oci-data-safe
description: >-
  OCI Data Safe administration via oci-cli and the OCI SDK: target-database
  registration (Autonomous and Base DB / Exadata cloud service), Data Safe
  private endpoints, Security Assessment and User Assessment, Activity Auditing
  (scim_query time filters), Data Discovery (sensitive data models), and Data
  Masking. Use whenever a request mentions OCI Data Safe, target database
  registration, Data Safe private endpoint, security assessment, user assessment,
  activity auditing, audit policy/retention, sensitive data discovery, data
  masking, or a database NEEDS_ATTENTION / ORA-01017 in Data Safe. Assessments
  are read; registration/masking/audit-policy changes go through the safety core.
license: MIT
---

# OCI Data Safe

Register and assess databases with Data Safe safely. Reading assessments is safe;
**registration**, **audit-policy/retention changes**, and **masking** are
mutations and go through `run_mutating` / `confirm`. All CLI runs through
`oci_cli` (`../../scripts/common.sh`). Never inline real OCIDs, IPs, service
names, or credentials — use `<PLACEHOLDER>` tokens.

## First move (always)

1. Confirm the tenancy/compartment:
   ```bash
   ./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>
   ```
2. Check the KB before debugging a registration failure:
   ```bash
   python3 scripts/kb_lookup.py "data safe target" observability-db
   ```

Read [../../references/data-safe.md](../../references/data-safe.md) for the
registration payloads, privilege scripts, and assessment/audit/masking commands,
and [../../references/tenancy-safety.md](../../references/tenancy-safety.md) for
the safety rules.

## Routing — pick the task

| Request mentions… | Go to |
|---|---|
| register/onboard a target, private endpoint | Target registration |
| privileges, "download privilege script", grants | DB-side privileges |
| security posture, risky config, drift | Security & User Assessment |
| audit events, retention, who did what | Activity Auditing |
| sensitive columns, PII discovery | Data Discovery |
| mask/redact data for non-prod | Data Masking |
| NEEDS_ATTENTION / ORA-01017 | Gotchas |

## Common multi-step flows

| Task | Sequence |
|------|----------|
| Register a target | ensure a Data Safe private endpoint (for cloud/Exadata DB) → run the DB-side privilege script → `target-database create` (creds via `file://`) → wait the work request → read the Security Assessment |
| Fix `NEEDS_ATTENTION` / `ORA-01017` | rotate the DB service-account password `CONTAINER=ALL` → update the target credential → wait the work request → re-check lifecycle-state (KB-057) |
| Mask a non-prod copy | run Data Discovery (sensitive data model) → **verify the target is a non-prod copy** → run masking (irreversible) → confirm masked columns |
| Audit a time window | `audit-event list --scim-query` with `auditEventTime` bounds (NOT `time_started`/`time_ended`, KB-032) → check retention covers the window |

## Common tasks

```bash
# Register an Autonomous DB target (credentials via file://, never argv).
run_mutating "register ADB target" oci_cli data-safe target-database create \
  --compartment-id <COMPARTMENT_OCID> --display-name <NAME> \
  --database-details file://database-details.json \
  --credentials file://credentials.json

# Read latest Security Assessment for a target (safe).
oci_cli data-safe security-assessment list --compartment-id <COMPARTMENT_OCID> \
  --target-id <TARGET_OCID> --query 'data[0]'

# Activity audit window — scim_query, NOT time_started/time_ended.
oci_cli data-safe audit-event list --compartment-id <COMPARTMENT_OCID> \
  --scim-query '(auditEventTime ge "<RFC3339_START>") and (auditEventTime le "<RFC3339_END>")'
```

## Key rules

- **Target type drives the payload:** `AUTONOMOUS_DATABASE` uses
  `autonomousDatabaseId`; `DATABASE_CLOUD_SERVICE` is keyed off
  `dbSystemId` + `serviceName` (not the DB OCID).
- **`target-database update` is async** (`--wait-for-state SUCCEEDED`) and needs
  `--force` non-interactively.
- **Audit queries use `scim_query`** for the time window.
- **`NEEDS_ATTENTION` + `ORA-01017`** = stale service-account password: rotate
  `CONTAINER=ALL`, update the target credential, wait the work request.

## Safety notes

- **Read assessments freely; gate the rest.** Registration, audit-policy/retention
  changes, and masking are mutations — `confirm` / `run_mutating`.
- **Never print or commit credentials.** `file://` payloads in `0600` files under a
  `0700` dir, deleted in `finally`; `redact` any output.
- **Mask only a verified non-prod copy** — it is irreversible on the masked data.

## Expected output

```markdown
**Finding** — target/assessment state or risk (names, not OCIDs).
**Evidence** — redacted assessment / audit result.
**Action** — exact command(s); registration/masking gated by confirm/dry-run.
**Verification** — re-read the assessment / target lifecycle-state showing the result.
**KB** — KB entry used, or new KB-<n> added.
```

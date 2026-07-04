---
name: oci-database-cloud
description: >-
  Operate OCI Base Database Service and Exadata Database Service control-plane
  lifecycle: DB systems, Exadata infrastructure and VM clusters, DB homes,
  databases and PDB resources, backups and restores, scaling, maintenance,
  patching, upgrades, and Data Guard associations. Excludes Autonomous Database,
  observability onboarding, and in-database SQL, RMAN, or tuning.
---

# OCI Database Cloud

Manage the OCI control plane around Base Database and Exadata deployments. Read
the complete dependency graph and maintenance/backup posture before mutation;
keep database credentials out of argv and output.

## Routing

| Intent | Owner |
|---|---|
| VM/BM DB system, DB home, database/PDB resource, backup/restore, patch/upgrade, scale, Data Guard association | This skill |
| Exadata infrastructure, cloud VM cluster, maintenance, capacity | This skill |
| Autonomous Database lifecycle, wallet, private endpoint | **oci-autonomous-db** |
| DBM/OPSI, Performance Hub, AWR/ASH service onboarding | **oci-dbm-opsi** |
| Metrics, alarms, Logging, APM | **oci-observability-db** |
| SQL/PLSQL, RMAN, schema migration, SQL tuning, Data Guard internals | Official `oracle/skills` **db/** hard handoff |
| Terraform HCL/import | **oci-terraform-authoring** |

Control-plane Data Guard association lifecycle stays here; redo design, broker
internals, and database-side repair stop at the official `db/` handoff.

Read [database-cloud.md](../../references/database-cloud.md) for lifecycle,
maintenance, backup, safety, and official-source contracts.

## Common multi-step flows

| Task | Sequence |
|---|---|
| Create a Base DB system | preflight → limits/capacity/network/KMS/backup reads → ownership check → additive reviewed plan → work-request wait → database/backup/agent verification |
| Patch or upgrade | read DB system, DB home, database, Data Guard, backups, and maintenance → precheck → in-place approval → rolling order → health and version verification → rollback/escalation decision |
| Backup and restore | read policy and latest usable backup → validate destination and recovery objective → additive backup or risk-classified restore → work-request wait → recovery validation |
| Data Guard lifecycle | read both sites and association health → validate backup/network/version/maintenance separation → create or role transition → verify roles and apply health → rehearse rollback |
| Exadata lifecycle | read infrastructure/VM-cluster capacity and maintenance → dependency/ownership check → additive or in-place action → prechecks/work requests → cluster/database verification |
| Teardown | inventory Data Guard, databases/PDBs, homes, backups, VM clusters, infrastructure, and Terraform state → destructive preview → exact approval → dependency-order removal → verify absence |

## Safety boundaries

- Passwords, wallet material, TDE/HSM secrets, and key material never appear on
  argv. Use a reviewed `0600` `file://` command document with `--from-json` only
  after installed help validates its fields.
- Creates and out-of-place restores are additive; scaling, patching, upgrades,
  configuration restores, and planned role transitions are in-place unless the
  reviewed impact requires destructive classification. Failover or any action
  that can discard data is destructive.
- Database/PDB deletion, backup deletion, DB-system termination, VM-cluster or
  Exadata-infrastructure deletion require dependency inventory, dry-run preview,
  and exact destructive approval.
- A current successful backup, maintenance precheck, and rollback path are
  prerequisites for patch/upgrade. Separate primary and standby maintenance.
- Never infer availability, limits, supported versions, shapes, or pricing from
  this skill. Resolve them from live reads and current official documentation.
- Validate exact command paths and flags with `oci_cli_help.py`; every mutation
  uses `run_action` with the target compartment.

## Verification and rollback

Verify work requests, lifecycle state, DB-node/VM-cluster health, database/PDB
availability, backup recoverability, Data Guard roles/apply health, maintenance
result, and monitoring continuity. Rollback is operation-specific: restore the
previous configuration or software home, reinstate/switchover only after health
review, or remove newly created resources in reverse dependency order.

## Expected output

Report named resources and dependency graph, redacted evidence, control-plane
owner, risk/approval, maintenance and backup posture, work-request result,
verification, rollback, and the boundary to database-internal work.

## Official documentation

[Database service](https://docs.oracle.com/en-us/iaas/Content/Database/home.htm) · [Base Database](https://docs.oracle.com/en-us/iaas/base-database/index.html) · [Exadata maintenance](https://docs.oracle.com/en-us/iaas/exadatacloud/doc/exa-conf-oracle-man-infra.html). Full index in [oracle-docs.md](../../references/oracle-docs.md).

**Open Knowledge Format grounding** — every Oracle documentation link is
registered and liveness-checked in the pack's central index.

# OCI Database Cloud reference

## Scope and ownership

This domain owns Base Database DB systems, DB homes, database and PDB resource
lifecycle, backups/restores, scaling, maintenance, patching/upgrades, Data Guard
associations, Exadata cloud infrastructure, and cloud VM clusters. It does not
own Autonomous Database, DBM/OPSI onboarding, generic observability, or work
inside a database.

The control-plane/in-database boundary is strict. This skill may inspect and
change an OCI Data Guard association. SQL, redo transport design, broker/RMAN
commands, schema work, and tuning route to the official `oracle/skills` `db/`
owner without local implementation commands.

## Dependency-first lifecycle

Read before write in this order: named context and ownership; service limits and
capacity; VCN/subnet/NSG and DNS; Vault/KMS/HSM dependencies; DB system or
Exadata infrastructure; VM cluster; DB home; database/PDB resources; backup and
recovery posture; Data Guard association; maintenance schedule; DBM/Data Safe
and observability dependents.

Installed OCI CLI 3.81.1 validation confirmed the command families `db system`,
`db db-home`, `db database`, `db pluggable-database`, `db backup`,
`db data-guard-association`, `db cloud-exa-infra`, and `db cloud-vm-cluster`.
This validates family naming, not flags or JSON fields. Re-run
`python3 scripts/oci_cli_help.py --json <tokens>` for every exact operation.

## Action contract

Every mutation requires a current matching preflight and the envelope
`run_action --risk <risk> --compartment <compartment> --description <action> --
<command>`. Use `additive` for new independent resources, `in-place` for a
reviewed convergent change, `credential` for credential/key material, and
`destructive` for deletion, termination, failover with data-loss potential, or
another irreversible action.

Any secret-bearing create/update/restore input uses `mktemp`, mode `0600`, a
cleanup `trap`, and a reviewed `file://` command document passed through
`--from-json`. Never show its JSON keys before installed help validates them.

## Maintenance, backup, and Data Guard

- Confirm a usable backup and recovery target before patch/upgrade or disruptive
  maintenance. A successful backup job alone is not recovery proof.
- Run supported prechecks and wait for each control-plane work request. Do not
  overlap dependent infrastructure, VM-cluster, DB-home, and database changes.
- Keep primary and standby maintenance windows separated. Re-read association
  health immediately before a role transition.
- Treat switchover as in-place only when the reviewed plan proves it planned and
  reversible; classify failover or possible data loss as destructive.
- Restore into a new target where feasible; an in-place restore needs explicit
  impact and rollback review.

## Verification and rollback

Verification covers lifecycle/work-request state, node or VM-cluster health,
database/PDB availability, backup recoverability, association roles and apply
health, encryption posture, agent/monitoring continuity, and application-facing
service checks without printing endpoints.

Rollback restores prior configuration or software placement when supported,
reverses a planned Data Guard role only after both sides are healthy, or removes
newly created resources in reverse dependency order. Never present a direct
delete sequence for non-TTY destructive recovery.

## Official documentation

- [OCI Database service](https://docs.oracle.com/en-us/iaas/Content/Database/home.htm)
- [Base Database documentation](https://docs.oracle.com/en-us/iaas/base-database/index.html)
- [About Base Database Service](https://docs.oracle.com/en-us/iaas/Content/Database/Tasks/backingupFRA.htm)
- [Pluggable databases](https://docs.oracle.com/en/cloud/paas/base-database/about-pdb/)
- [Exadata infrastructure maintenance](https://docs.oracle.com/en-us/iaas/exadatacloud/doc/exa-conf-oracle-man-infra.html)

All URLs are registered in [oracle-docs.md](oracle-docs.md).

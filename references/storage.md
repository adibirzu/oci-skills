# OCI Storage

Use this reference for Object Storage, Archive Storage, File Storage, and
Block/Boot Volume control-plane work. Read before write and keep durable
configuration under one Terraform owner.

## Ownership boundaries

- Object Storage: namespace discovery, buckets, objects, multipart uploads,
  tiers, lifecycle, versioning, retention, replication, and pre-authenticated request lifecycle.
- File Storage: file systems, mount targets, export sets/exports, export options,
  snapshots, replication, and protection state.
- Block Volume: block and boot volumes, volume groups, backups, backup policies,
  clones, performance configuration, and replication.
- oci-networking-compute: volume attachment/detachment and guest connectivity.
- oci-oke-admin: StorageClass, CSI, persistent volume claims, and pod mounts.
- Database owners: database-native backup/restore and Data Guard.
- oci-disaster-recovery: cross-stack protection groups and DR-plan execution.

## Evidence to collect

1. Named context, region, compartment, resource display name, and Terraform owner.
2. Data classification, encryption owner, access posture, retention or legal-hold constraints, and deletion dependencies.
3. Versioning, lifecycle, replication, snapshot, backup, and work-request state.
4. RPO/RTO and a dated recovery-test result. A configured backup without a successful restore test is incomplete evidence.
5. For File Storage, the mount-target/export dependency graph and network owner.
6. For Object Storage, verify the namespace and region without printing either.

Empty output is inconclusive until region, namespace, compartment, pagination,
and permissions have been checked.

## Risk model

| Operation | Minimum risk |
|---|---|
| Add bucket, file system, volume, policy, backup, replica, snapshot, or clone | additive |
| Change tags, performance, lifecycle, export options, or backup schedule | in-place |
| Create/rotate a pre-authenticated request or comparable bearer access | credential |
| Delete/purge, reduce retention, overwrite restore target, detach in-use storage | destructive |

Every mutation uses run_action --risk <risk> --compartment <compartment>
--description <action> -- <command>.

Before rendering a service command, validate the installed shape with
python3 scripts/oci_cli_help.py --json "<command path>". Then lint any
executable plan with python3 scripts/oci_cli_lint.py <plan>. Do not guess flags,
JSON fields, storage tiers, limits, or regional availability.

## Credentials and content

A pre-authenticated request is a credential. Its URL must not appear in chat,
logs, committed evidence, or argv. Use mktemp, mode 0600, a cleanup trap, and a
file:// payload with --from-json only after installed help validates the
document. Never read or print object bodies merely to prove access.

## Verification and rollback

Verification covers lifecycle state, encryption, access posture, replication or
backup health, work-request completion, and a non-destructive recovery sample.
Rollback restores the prior reviewed configuration for reversible changes,
revokes temporary access, or recovers from an independently verified version,
backup, replica, snapshot, or clone. Never describe destructive storage changes
as reversible without that source.

## Official documentation

- [Object Storage](https://docs.oracle.com/en-us/iaas/Content/Object/home.htm)
- [Object Storage overview](https://docs.oracle.com/en-us/iaas/Content/Object/Concepts/objectstorageoverview.htm)
- [File Storage](https://docs.oracle.com/en-us/iaas/Content/File/home.htm)
- [File Storage overview](https://docs.oracle.com/en-us/iaas/Content/File/Concepts/filestorageoverview.htm)
- [Block Volume](https://docs.oracle.com/en-us/iaas/Content/Block/home.htm)
- [Block Volume overview](https://docs.oracle.com/en-us/iaas/Content/Block/Concepts/overview.htm)

---
name: oci-storage
description: >-
  Operate OCI Object Storage, Archive Storage, File Storage, and Block/Boot
  Volume data-protection lifecycle. Use for buckets, objects, multipart uploads,
  lifecycle and retention rules, versioning, replication, pre-authenticated
  requests, file systems, mount targets, exports, snapshots, volume groups,
  backups, backup policies, clones, and volume replication. Compute attachment
  remains with oci-networking-compute; OKE persistent volumes remain with
  oci-oke-admin; database-native backups remain with their database owner.
---

# OCI Storage

Manage durable data services without exposing content, topology, or temporary
access credentials. Read configuration and protection state before proposing a
change. Use Terraform as the default owner for durable storage resources.

## Routing

| Intent | Owner |
|---|---|
| Buckets, objects, lifecycle, retention, versioning, replication, PARs | This skill |
| File systems, mount targets, exports, snapshots, replication | This skill |
| Block/boot volumes, groups, backups, policies, clones, replication | This skill |
| Attach/detach a volume or troubleshoot guest connectivity | **oci-networking-compute** |
| OKE StorageClass, PVC, PV, CSI, or pod mounts | **oci-oke-admin** |
| Database-native backup, restore, Data Guard | Database owner |
| HCL authoring or reviewed Terraform execution | **oci-terraform-authoring** |

## Workflow

1. Confirm named context with `./scripts/oci_preflight.sh -c "$COMPARTMENT_OCID"`;
   stop if the resolved tenancy/compartment does not match the intended target.
   Also confirm region, data classification, owner, and recovery objectives.
2. Read the resource, encryption, public-access, retention, versioning, replication, backup, and work-request state.
3. Treat empty results as inconclusive until region, namespace, compartment, permissions, and pagination are verified.
4. Prefer Terraform for durable configuration. Ground every exceptional CLI shape with installed help before rendering it.
5. Classify PAR creation or other bearer-style access as credential; deletion, retention reduction, version purge, and restore-overwrite paths as destructive.
6. Execute a permitted mutation only through the complete context-bound run_action envelope.
7. Re-read protection state and test the recovery path without exposing object names, addresses, OCIDs, or access URLs.

## Common multi-step flows

| Request | Sequence |
|---|---|
| Secure a bucket | inventory → access/encryption/versioning/retention review → plan → gated change → verify |
| Add shared file storage | network handoff → file system/mount target/export design → gated materialization → mount verification |
| Protect compute data | volume/group inventory → RPO/RTO → backup/replication policy → recovery test → evidence |
| Share an object temporarily | audience/expiry → credential preview → exact approval → create → verify → revoke |
| Recover data | immutable source → target/conflict preview → destructive approval if overwrite is possible → restore/clone → validate |

## Safety

- Never print object content, access URLs, namespace identifiers, mount addresses, OCIDs, or customer-managed key identifiers.
- Never place secrets or access material on argv. Use a 0600 file:// command document and --from-json only after installed help validates its shape.
- Retention and legal-hold changes require explicit impact review; do not promise reversibility.
- A pre-authenticated request is a credential even when scoped and time-bound.
- Terraform-owned storage remains Terraform-owned; direct mutation is break-glass followed by HCL and plan reconciliation.
- Destructive non-TTY work exposes only the dry-run preview and exact approval contract, never a live delete command.

## Verification and rollback

Verify lifecycle state, encryption association, replication/backup health, work
requests, and a non-destructive recovery sample. Roll back additive policy
changes by restoring the reviewed prior configuration. Revoke temporary access
immediately when no longer needed. For irreversible deletion, retention
reduction, or overwrite, rollback means recovery from a separately verified
backup, replica, version, snapshot, or clone—not an assumed undo.

Read [the storage reference](../../references/storage.md) before service-specific work.

## Official documentation

[Object Storage](https://docs.oracle.com/en-us/iaas/Content/Object/home.htm) · [File Storage](https://docs.oracle.com/en-us/iaas/Content/File/home.htm) · [Block Volume](https://docs.oracle.com/en-us/iaas/Content/Block/home.htm). Full list in the [storage reference](../../references/storage.md).

**Open Knowledge Format grounding** - every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill, cite the most specific official page through that index; the non-official MCP gateway is never a source of truth.

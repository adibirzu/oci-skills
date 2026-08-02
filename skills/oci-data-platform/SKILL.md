---
name: oci-data-platform
description: >-
  Operate OCI data-platform control-plane services: Data Integration workspaces,
  data assets, applications, tasks, pipelines and runs; Data Flow Spark
  applications, pools, SQL endpoints and runs; Data Catalog catalogs, assets,
  harvest jobs, glossaries, custom properties and metastores; GoldenGate
  deployments, connections, deployment backups, upgrades and replication health;
  and NoSQL table lifecycle. Use for ETL/ELT, Spark jobs, metadata governance,
  data movement, CDC/replication, and data-platform operational troubleshooting.
---

# OCI Data Platform

Coordinate OCI data-movement, processing, catalog, and replication services
without taking over database, storage, network, or application ownership. Keep
datasets, schemas, connection details, endpoints, and replication topology
redacted in all shared output.

## Routing

| Intent | Owner |
|---|---|
| Data Integration workspaces, applications, data assets, tasks, pipelines, runs | This skill |
| Data Flow applications, runs, pools, private endpoints, SQL endpoints | This skill |
| Data Catalog assets, harvest jobs, glossaries, custom properties, metastores | This skill |
| OCI GoldenGate deployments, connections, backups, upgrades, replication health | This skill |
| NoSQL tables and indexes | This skill |
| ADB lifecycle, wallets, ACLs, SQL diagnostics | **oci-autonomous-db** |
| Object Storage bucket lifecycle and PARs | **oci-storage** |
| VCN, subnet, DNS, endpoint, and security-rule materialization | **oci-networking-compute** |
| Terraform HCL and state ownership | **oci-terraform-authoring** |

Read [data-platform.md](../../references/data-platform.md) before rendering an
exact command, payload, or runbook.

## Workflow

1. Classify the data, region, compartment, source/target systems, residency,
   retention, replication direction, and recovery requirements.
2. Read existing workspaces, catalogs, deployments, tables, runs, connections,
   private endpoints, IAM, Vault references, and network reachability by name.
3. Treat empty run, harvest, or replication results as inconclusive until region,
   compartment subtree, time window, pagination, and permissions are checked.
4. Validate exact installed OCI CLI or SDK shapes before presenting a command or
   nested payload. Use files for payloads and never place credentials on argv.
5. Classify creates as additive, updates as in-place, secret/connection
   activation as credential, and delete/purge/replication cutover as destructive.
6. Verify terminal work-request or service-specific run state, data freshness,
   error logs, retry posture, and rollback or replay path.

## Common multi-step flows

| Request | Sequence |
|---|---|
| Operate a Data Integration pipeline | preflight -> read workspace/application/task -> check connections/Vault/network -> run or inspect -> verify run status and logs |
| Run a Data Flow Spark job | preflight -> read app/pool/private endpoint -> validate object dependencies -> submit/inspect run -> verify logs, metrics, and output |
| Harvest metadata into Data Catalog | preflight -> read catalog/assets/connection -> validate private endpoint and credentials -> run harvest -> verify assets/glossary links |
| Operate GoldenGate replication | preflight -> read deployment/connections/extracts/replicats -> inspect lag/errors -> gated action -> verify checkpoint/lag and rollback |
| Manage NoSQL tables | preflight -> read table/index/capacity -> review schema and limits -> gated change -> verify state, capacity, and backup/export path |

## Safety

- Never print dataset rows, schema names that identify a customer, connection
  strings, endpoints, passwords, wallets, trail names, OCIDs, namespaces, or IPs.
- Data movement can duplicate, transform, or delete regulated records; capture
  source-of-truth, replay, rollback, and retention before changing pipelines.
- GoldenGate cutover, destructive table changes, and purge operations require
  destructive approval and independent recovery evidence.
- Use Vault-backed credentials, service/resource principals, and least privilege.
  Do not store connection secrets in task payloads, pipeline variables, logs, or
  committed artifacts.
- Terraform owns durable resources by default. Direct CLI changes are
  break-glass and must be reconciled with the declared owner.

## Verification and rollback

Verification must include service-specific terminal state, work-request or run
logs, freshness/lag, expected output location, retry/dead-letter posture where
applicable, and redacted operator evidence. Rollback restores the reviewed prior
configuration, replays from a checkpoint, or recovers from a verified backup,
export, or replica; never promise lossless rollback without that evidence.

## Official documentation

[Data Integration](https://docs.oracle.com/en-us/iaas/Content/data-integration/home.htm) · [Data Flow](https://docs.oracle.com/en-us/iaas/Content/data-flow/using/home.htm) · [Data Catalog](https://docs.oracle.com/en-us/iaas/Content/data-catalog/home.htm) · [GoldenGate](https://docs.oracle.com/en-us/iaas/goldengate/). Full list in the [data-platform reference](../../references/data-platform.md).

**Open Knowledge Format grounding** - every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill, cite the most specific official page through that index; the non-official MCP gateway is never a source of truth.

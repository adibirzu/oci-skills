# OCI Data Platform

Use this reference for OCI Data Integration, Data Flow, Data Catalog,
GoldenGate, and NoSQL control-plane workflows. This domain coordinates data
movement and processing while database lifecycle, object storage, networking,
and Terraform retain their own owners.

## Ownership boundaries

- Data Integration: workspaces, projects, applications, data assets,
  connections, tasks, pipelines, runs, imports, exports, and run diagnosis.
- Data Flow: Spark applications, runs, pools, private endpoints, SQL endpoints,
  dependency locations, metrics, and run logs.
- Data Catalog: catalogs, data assets, harvest jobs, glossaries, custom
  properties, metastores, and private endpoint reachability.
- GoldenGate: deployments, connections, deployment backups, upgrades, extract
  and replicat health, lag, checkpoint state, and cutover readiness.
- NoSQL: table, index, capacity, limits, export/import, and lifecycle state.
- `oci-autonomous-db` and `oci-database-cloud`: database service lifecycle,
  wallets, ACLs, PDB/DB system work, and database-native backups.
- `oci-storage`: buckets, Object Storage lifecycle, retention, PARs, and
  archive/data-protection policy.
- `oci-networking-compute`: VCN, subnet, DNS, endpoint, route, NSG, and private
  reachability materialization.

## Read/Skill-only response contract

When execution and installed-help lookup are unavailable, do not invent command
paths, flags, payload fields, service limits, supported runtimes, or region
availability. Return the owner, prerequisites, read -> action -> verification ->
rollback sequence, then require:

```text
python3 scripts/oci_cli_help.py --json "<command path>"
python3 scripts/oci_cli_lint.py <command-plan.json>
```

Do not emit a create/update/delete command outside
`run_action --risk <risk> --compartment <compartment> --description <action> --
oci_cli ...`. Use `0600` `file://` payloads for nested command documents and
credentials.

## Evidence to collect

1. Named context, region, compartment, service owner, Terraform owner, data
   classification, and residency constraints.
2. Source and target systems by redacted name, not connection string, endpoint,
   OCID, schema, table, trail, topic, or bucket namespace.
3. Existing workspace/catalog/deployment/table/application state, run history,
   work requests, errors, and service-specific logs.
4. IAM for operator, service principal, resource principal, Vault reads,
   Object Storage reads/writes, network endpoints, and target systems.
5. Freshness, lag, checkpoint, retry, replay, backup, export, and rollback
   evidence.

Empty results are inconclusive until region, compartment subtree, time window,
pagination, and permissions are checked.

## Risk model

| Operation | Minimum risk |
|---|---|
| Create workspace, application, pool, catalog, deployment, table, task, or connection shell | additive |
| Update tags, schedules, task definitions, runtime config, capacity, glossary metadata, or deployment version | in-place |
| Create, rotate, activate, or test connection credentials | credential |
| Delete/purge data-platform resources, cut over replication, drop table/index, or overwrite target data | destructive |

## Service notes

- Data Integration uses its own work-request behavior; do not assume common OCI
  work-request commands answer every run state. Inspect service run objects and
  logs.
- Data Flow runs depend on Object Storage artifacts, private endpoints,
  metastore/catalog choices, and Spark runtime compatibility. Verify the
  dependency locations without printing names or data.
- Data Catalog harvest jobs need reachable data assets and correct private
  endpoints before they can prove governance coverage.
- GoldenGate replication health requires lag/checkpoint/error evidence from the
  service and the source/target owners. A healthy deployment alone is not proof
  of replication health.
- NoSQL capacity and schema changes affect availability and cost; inspect limits
  and current capacity before changing tables.

## Verification and rollback

Verification covers terminal run/work-request state, logs, metrics, data
freshness or lag, expected output path, governance asset count, and redacted
operator evidence. Rollback restores reviewed configuration, replays from a
checkpoint, or recovers from a verified export, backup, replica, or prior
deployment. If the service cannot prove a rollback path, state that before the
mutation.

## Official documentation

- [Data Integration](https://docs.oracle.com/en-us/iaas/Content/data-integration/home.htm)
- [Data Integration overview](https://docs.oracle.com/en-us/iaas/Content/data-integration/using/overview.htm)
- [Data Flow](https://docs.oracle.com/en-us/iaas/Content/data-flow/using/home.htm)
- [Data Catalog](https://docs.oracle.com/en-us/iaas/Content/data-catalog/home.htm)
- [GoldenGate](https://docs.oracle.com/en-us/iaas/goldengate/)

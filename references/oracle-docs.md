# Oracle Documentation Index

The single source of truth for **authoritative OCI documentation** behind this
pack. Every domain reference, every SKILL footer, and every `KB-<n>` citation
points here (or to a page listed here). Patterned on the
[Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog)
*index + citation* convention: a knowledge unit should link to the external
source that backs its claim.

> All URLs below were verified live (HTTP 200) when added. When you add or fix a
> doc link anywhere in the pack, prefer a URL already in this table; if you add a
> new one, confirm it resolves and add it here so the
> [doc-link lint](../tests/test_doc_links.py) stays the source of truth.

## How to cite

- **Most specific page wins.** Link the concept's own page (e.g. the Budgets
  overview for a budget fix), not just the service home, when one exists.
- **KB entries** carry a `**See:**` line → the canonical page for that fix.
- **References / SKILLs** carry an *Official documentation* footer → the
  service home(s) for that domain.

## Version coverage

OCI service docs track the **live service**; there is no per-release doc set to
pin. The moving parts this pack depends on are the **OCI CLI** and **SDK**
versions on the caller's machine — see
[helper-conventions.md](helper-conventions.md) for the negotiated `oci_cli`
entrypoint and [credential-management.md](credential-management.md) for auth.
For Oracle Database engine features reached *through* OCI services (DBM, Data
Safe), the upstream `db/` domain of
[oracle/skills](https://github.com/oracle/skills) documents a 19c baseline.

## IAM & tenancy — `oci-iam-admin`

| Topic | Canonical doc |
|---|---|
| IAM (users, groups, policies, compartments) | <https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm> |
| Identity Domains | <https://docs.oracle.com/en-us/iaas/Content/Identity/domains/overview.htm> |
| Compartment Quotas | <https://docs.oracle.com/en-us/iaas/Content/Quotas/Concepts/resourcequotas.htm> |
| Service Limits | <https://docs.oracle.com/en-us/iaas/Content/General/service-limits/overview.htm> |
| Budgets | <https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/budgetsoverview.htm> |
| Tagging | <https://docs.oracle.com/en-us/iaas/Content/Tagging/home.htm> |

## Security & compliance — `oci-security-compliance`

| Topic | Canonical doc |
|---|---|
| Cloud Guard | <https://docs.oracle.com/en-us/iaas/cloud-guard/home.htm> |
| Vault / KMS (Key Management) | <https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm> |
| WAF (Web Application Firewall) | <https://docs.oracle.com/en-us/iaas/Content/WAF/home.htm> |
| Audit | <https://docs.oracle.com/en-us/iaas/Content/Audit/home.htm> |
| Security Zones | <https://docs.oracle.com/en-us/iaas/security-zone/home.htm> |
| CIS OCI Benchmark | <https://docs.oracle.com/en/solutions/cis-oci-benchmark/index.html> |

## Observability & database — `oci-observability-db`

| Topic | Canonical doc |
|---|---|
| Monitoring (metrics & alarms) | <https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm> |
| Logging | <https://docs.oracle.com/en-us/iaas/Content/Logging/home.htm> |
| APM (Application Performance Monitoring) | <https://docs.oracle.com/en-us/iaas/application-performance-monitoring/home.htm> |
| Database Management (DBM) | <https://docs.oracle.com/en-us/iaas/database-management/home.htm> |
| Operations Insights (OPSI) | <https://docs.oracle.com/en-us/iaas/operations-insights/home.htm> |
| Autonomous Database | <https://docs.oracle.com/en-us/iaas/autonomous-database/index.html> |

## Log Analytics — `oci-log-analytics`

| Topic | Canonical doc |
|---|---|
| Log Analytics (Logan, OCL) | <https://docs.oracle.com/en-us/iaas/log-analytics/home.htm> |

## Networking & compute — `oci-networking-compute`

| Topic | Canonical doc |
|---|---|
| Networking (VCN, subnets, NSGs, gateways, LB) | <https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm> |
| Compute | <https://docs.oracle.com/en-us/iaas/Content/Compute/home.htm> |
| Kubernetes Engine (OKE) | <https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm> |
| Container Registry (OCIR) | <https://docs.oracle.com/en-us/iaas/Content/Registry/home.htm> |
| Object Storage (buckets) | <https://docs.oracle.com/en-us/iaas/Content/Object/home.htm> |

## Cost & FinOps — `oci-cost`

| Topic | Canonical doc |
|---|---|
| Cost Analysis / Usage | <https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/costanalysisoverview.htm> |
| Budgets | <https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/budgetsoverview.htm> |
| Cost & usage balance | <https://docs.oracle.com/en-us/iaas/Content/Balance/home.htm> |

## Resource Manager — `oci-resource-manager`

| Topic | Canonical doc |
|---|---|
| Resource Manager (managed Terraform) | <https://docs.oracle.com/en-us/iaas/Content/ResourceManager/home.htm> |

## Data Safe — `oci-data-safe`

| Topic | Canonical doc |
|---|---|
| Data Safe | <https://docs.oracle.com/en-us/iaas/data-safe/doc/oracle-data-safe-overview.html> |

## Events, Functions & SCH — `oci-events-functions`

| Topic | Canonical doc |
|---|---|
| Functions | <https://docs.oracle.com/en-us/iaas/Content/Functions/home.htm> |
| Events | <https://docs.oracle.com/en-us/iaas/Content/Events/home.htm> |
| Notifications (ONS) | <https://docs.oracle.com/en-us/iaas/Content/Notification/home.htm> |
| Service Connector Hub | <https://docs.oracle.com/en-us/iaas/Content/connector-hub/home.htm> |
| Streaming | <https://docs.oracle.com/en-us/iaas/Content/Streaming/home.htm> |

## Cross-cutting — CLI, SDK, API errors

| Topic | Canonical doc |
|---|---|
| OCI documentation home | <https://docs.oracle.com/en-us/iaas/Content/home.htm> |
| SDK & CLI configuration (`~/.oci/config`) | <https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm> |
| OCI CLI install | <https://docs.oracle.com/iaas/Content/API/SDKDocs/cliinstall.htm> |
| OCI CLI command reference | <https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/> |
| API error reference (status codes) | <https://docs.oracle.com/en-us/iaas/Content/API/References/apierrors.htm> |
| Work requests | <https://docs.oracle.com/en-us/iaas/Content/General/Concepts/workrequestoverview.htm> |

## Specific pages (KB deep links)

The highest-traffic [KB.md](KB.md) entries cite the exact page behind the fix
rather than the service home (all verified live):

| Topic | Page | KB |
|---|---|---|
| OKE access control (IAM + RBAC two layers) | <https://docs.oracle.com/en-us/iaas/Content/ContEng/Concepts/contengaboutaccesscontrol.htm> | KB-001 |
| Service limits (request an increase) | <https://docs.oracle.com/en-us/iaas/Content/General/Concepts/servicelimits.htm> | KB-003 |
| WAF concepts (protection actions) | <https://docs.oracle.com/en-us/iaas/Content/WAF/Concepts/overview.htm> | KB-004 |
| Managing Vault secrets | <https://docs.oracle.com/en-us/iaas/Content/KeyManagement/Tasks/managingsecrets.htm> | KB-005 |
| Resource Manager jobs (plan/apply) | <https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Tasks/usingconsole.htm> | KB-007 |
| Managing dynamic groups (matching rules) | <https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/managingdynamicgroups.htm> | KB-021 |
| Managing alarms (MQL query-text) | <https://docs.oracle.com/en-us/iaas/Content/Monitoring/Tasks/managingalarms.htm> | KB-027 |
| Register Data Safe target databases | <https://docs.oracle.com/en-us/iaas/data-safe/doc/register-target-databases.html> | KB-057 |
| Creating/deploying Functions | <https://docs.oracle.com/en-us/iaas/Content/Functions/Tasks/functionscreatingfunctions.htm> | KB-084 |
| Managing streams (stream vs stream pool) | <https://docs.oracle.com/en-us/iaas/Content/Streaming/Tasks/managingstreams.htm> | KB-091 |

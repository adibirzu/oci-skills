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
>
> Two checks guard these links: the **offline** lint (`tests/test_doc_links.py`,
> runs in PR CI — well-formed + every used URL registered here + KB citation
> coverage) and a **live** checker (`scripts/check_doc_links.py --live`, run
> weekly by `.github/workflows/doc-liveness.yml`) that HTTP-verifies each URL so
> link rot is caught even when the format is fine. On a dead link that workflow
> opens (or comments on) a `doc-rot` issue and fails, so rot becomes a tracked
> item instead of a silently-red cron run.

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
| Monitoring Query Language (MQL) reference | <https://docs.oracle.com/en-us/iaas/Content/Monitoring/Reference/mql.htm> |
| Querying metric data (MQL panels) | <https://docs.oracle.com/en-us/iaas/Content/Monitoring/Tasks/query-metric-data.htm> |
| Logging | <https://docs.oracle.com/en-us/iaas/Content/Logging/home.htm> |
| APM (Application Performance Monitoring) | <https://docs.oracle.com/en-us/iaas/application-performance-monitoring/home.htm> |
| APM Synthetic Monitoring | <https://docs.oracle.com/en-us/iaas/application-performance-monitoring/doc/use-synthetic-monitoring.html> |

## DBM / OPSI — `oci-dbm-opsi`

| Topic | Canonical doc |
|---|---|
| Database Management (DBM) | <https://docs.oracle.com/en-us/iaas/database-management/home.htm> |
| Operations Insights (OPSI) | <https://docs.oracle.com/en-us/iaas/operations-insights/home.htm> |

## Autonomous Database — `oci-autonomous-db`

| Topic | Canonical doc |
|---|---|
| Autonomous Database (landing) | <https://docs.oracle.com/en-us/iaas/autonomous-database/index.html> |
| Download connection info / wallet (mTLS & TLS) | <https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/connect-download-wallet.html> |
| Network access: ACLs & private endpoints | <https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/autonomous-network-access.html> |
| `oci db autonomous-database` CLI reference | <https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/db/autonomous-database.html> |
| `DBMS_XPLAN` (execution plans) | <https://docs.oracle.com/en/database/oracle/oracle-database/19/arpls/DBMS_XPLAN.html> |
| Database Reference (V$ dynamic performance views) | <https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/index.html> |
| SQL Tuning Guide | <https://docs.oracle.com/en/database/oracle/oracle-database/19/tgsql/index.html> |

## Log Analytics — `oci-log-analytics`

| Topic | Canonical doc |
|---|---|
| Log Analytics (Logan, OCL) | <https://docs.oracle.com/en-us/iaas/log-analytics/home.htm> |
| Oracle-defined log sources | <https://docs.oracle.com/en-us/iaas/logging-analytics/doc/oracle-defined-sources.html> |

## Networking & compute — `oci-networking-compute`

| Topic | Canonical doc |
|---|---|
| Networking (VCN, subnets, NSGs, gateways, LB) | <https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm> |
| Compute | <https://docs.oracle.com/en-us/iaas/Content/Compute/home.htm> |
| Object Storage (buckets) | <https://docs.oracle.com/en-us/iaas/Content/Object/home.htm> |

## OKE — `oci-oke-admin`

| Topic | Canonical doc |
|---|---|
| Kubernetes Engine (OKE) | <https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm> |

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
| Terraform on OCI (provider, authoring stacks) | <https://docs.oracle.com/en-us/iaas/Content/dev/terraform/home.htm> |

## Terraform authoring — `oci-terraform-authoring`

| Topic | Canonical doc |
|---|---|
| OCI Terraform provider | <https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/> |
| Resource discovery | <https://docs.oracle.com/en-us/iaas/Content/terraform/resource-discovery.htm> |

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
| Queue overview | <https://docs.oracle.com/en-us/iaas/Content/queue/overview.htm> |
| Queue IAM policies | <https://docs.oracle.com/en-us/iaas/Content/queue/policy-reference.htm> |
| Streaming Kafka compatibility | <https://docs.oracle.com/en-us/iaas/Content/Streaming/Tasks/kafkacompatibility.htm> |
| Streaming Kafka API configuration | <https://docs.oracle.com/en-us/iaas/Content/Streaming/Tasks/kafkacompatibility_topic-Configuration.htm> |

## Developer Services — `oci-developer-services`

| Topic | Canonical doc |
|---|---|
| OCI DevOps overview | <https://docs.oracle.com/en-us/iaas/Content/devops/using/devops_overview.htm> |
| DevOps deployment rollback | <https://docs.oracle.com/en-us/iaas/Content/devops/using/deployment_rollback.htm> |
| API Gateway concepts | <https://docs.oracle.com/en-us/iaas/Content/APIGateway/Concepts/apigatewayconcepts.htm> |
| Container Instances overview | <https://docs.oracle.com/en-us/iaas/Content/container-instances/overview-of-container-instances.htm> |
| Container Registry (OCIR) | <https://docs.oracle.com/en-us/iaas/Content/Registry/home.htm> |

## Solution authoring — `oci-administrator` / `oci-project`

The official Oracle guidance behind [solution-authoring.md](solution-authoring.md)
— designing a new OCI solution for a customer before it is bootstrapped:

| Topic | Canonical doc |
|---|---|
| Architecture Center (reference architectures & solution playbooks) | <https://docs.oracle.com/en/solutions/> |
| Cloud Adoption Framework (Well-Architected pillars) | <https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/home.htm> |
| Cloud Adoption Framework — Security pillar (landing-zone guardrails) | <https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/security.htm> |
| Security guide (best practices) | <https://docs.oracle.com/en-us/iaas/Content/Security/Concepts/security_guide.htm> |
| CIS OCI Benchmark | <https://docs.oracle.com/en/solutions/cis-oci-benchmark/index.html> |

## Alignment with `oracle/skills` — deep OKE & Generative AI

Behind [oracle-skills-alignment.md](oracle-skills-alignment.md): the official
Oracle pages for the domains this pack **routes to** the upstream
[oracle/skills](https://github.com/oracle/skills) collection rather than
duplicating (deep OKE day-2, OCI Generative AI / Enterprise AI):

| Topic | Canonical doc |
|---|---|
| OCI Generative AI (overview) | <https://docs.oracle.com/en-us/iaas/Content/generative-ai/overview.htm> |
| OCI Generative AI (home) | <https://docs.oracle.com/en-us/iaas/Content/generative-ai/home.htm> |
| OKE access control (IAM + RBAC, incl. Workload Identity) | <https://docs.oracle.com/en-us/iaas/Content/ContEng/Concepts/contengaboutaccesscontrol.htm> |
| OKE multiple VNICs (GVA / Multus prerequisite) | <https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengAttaching_Multiple_VNICs.htm> |

## Adjacent Oracle SaaS — route out of this OCI control-plane pack

| Topic | Canonical doc |
|---|---|
| Oracle Fusion Cloud Applications documentation hub | <https://docs.oracle.com/en/cloud/saas/index.html> |

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
| Streaming Kafka API configuration | <https://docs.oracle.com/en-us/iaas/Content/Streaming/Tasks/kafkacompatibility_topic-Configuration.htm> | KB-106 |
| Manage APM domains | <https://docs.oracle.com/en-us/iaas/application-performance-monitoring/doc/manage-apm-domains.html> | KB-126 |
| Managing load balancer backend sets | <https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managingbackendsets.htm> | KB-127 |
| Deleting a VCN | <https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/deletingVCN.htm> | KB-128 |
| Managing dynamic groups (dynamicgroups path) | <https://docs.oracle.com/en-us/iaas/Content/Identity/dynamicgroups/managingdynamicgroups.htm> | KB-130 |
| Pushing images using the Docker CLI | <https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrypushingimagesusingthedockercli.htm> | KB-131 |
| Publishing custom metrics | <https://docs.oracle.com/en-us/iaas/Content/Monitoring/Tasks/publishingcustommetrics.htm> | KB-132 |
| Creating streams and stream pools | <https://docs.oracle.com/en-us/iaas/Content/Streaming/Tasks/creating-streams-and-stream-pools.htm> | KB-133 |
| Configuring the Terraform provider | <https://docs.oracle.com/en-us/iaas/Content/dev/terraform/configuring.htm> | KB-134 |
| Resource Manager concepts | <https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Concepts/resourcemanager.htm> | KB-135 |
| Manage the ADB ADMIN user | <https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/manage-users-admin.html> | KB-137 |
| Network security groups | <https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/networksecuritygroups.htm> | KB-138 |
| Deleting VCNs (managing VCNs) | <https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/managingVCNs_topic-Deleting_VCNs.htm> | KB-139 |
| Manage Log Analytics with the CLI | <https://docs.oracle.com/en-us/iaas/log-analytics/doc/use-cli-manage-log-analytics.html> | KB-140 |
| Data Safe audit reports | <https://docs.oracle.com/en-us/iaas/data-safe/doc/audit-reports.html> | KB-141 |
| Enable DB Management for Autonomous Databases | <https://docs.oracle.com/en-us/iaas/database-management/doc/enable-database-management-autonomous-databases.html> | KB-142 |
| Calling services from an instance (IMDS auth) | <https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/callingservicesfrominstances.htm> | KB-143 |

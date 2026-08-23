# OCI Skill Catalog

Use this catalog when a user knows the OCI task but not the skill name. It keeps
the repository layout flat for installers while presenting the skills in the
same task-oriented way users normally describe work.

Offline documentation, review, tests, bundle scaffolding, and Terraform
authoring do not require OCI credentials and do not contact a tenancy. Live reads
or mutations still follow the router safety gates in [AGENTS.md](../AGENTS.md).

## Start Here

| User intent | Use this skill |
|---|---|
| "I need OCI help; route me to the right place." | [OCI Administrator router](../skills/oci-administrator/) |
| "Bootstrap, inspect, deploy, or tear down this project." | [OCI Project lifecycle](../skills/oci-project/) |
| "Choose a platform pattern and generate bundle artifacts." | [OCI Product Development](../skills/oci-product-development/) |
| "Review, debug, reuse, or evaluate application code." | [OCI Application Engineering](../skills/oci-application-engineering/) |
| "Design or validate a greenfield tenancy foundation." | [OCI Landing Zone](../skills/oci-landing-zone/) |
| "Create an OCI architecture diagram in Draw.io, Excalidraw, or Mermaid." | [OCI Diagramming](../skills/oci-diagramming/) |

## Security and Governance

| User intent | Use this skill |
|---|---|
| Users, groups, compartments, policies, budgets, quotas, tags, limits, named contexts | [OCI IAM Admin](../skills/oci-iam-admin/) |
| Cloud Guard, Vault, WAF, Vulnerability Scanning, CIS/ISO evidence, DevSecOps gates | [OCI Security Compliance](../skills/oci-security-compliance/) |
| Zero Trust Packet Routing attributes, policies, protected resources, flow-log correlation | [OCI ZPR Visibility](../skills/oci-zpr-visibility/) |
| Data Safe target registration, assessments, audit, discovery, masking | [OCI Data Safe](../skills/oci-data-safe/) |

## Infrastructure and Access

| User intent | Use this skill |
|---|---|
| VCNs, subnets, NSGs, routing, DNS, certificates, load balancers, compute, VNICs, volume attachments | [OCI Networking Compute](../skills/oci-networking-compute/) |
| OKE clusters, applications, kubeconfig, ingress, TLS, OCIR pulls, rollouts | [OCI OKE Admin](../skills/oci-oke-admin/) |
| Bastion sessions, Managed SSH, fixed or dynamic forwarding, allowlists, plugin diagnosis | [OCI Bastion Access](../skills/oci-bastion-access/) |
| Object, File, Block, Boot storage, retention, backup, replication | [OCI Storage](../skills/oci-storage/) |
| Full Stack DR protection groups, plans, prechecks, drills, switchovers, failovers | [OCI Disaster Recovery](../skills/oci-disaster-recovery/) |
| Terraform/HCL authoring, discovery, local validation, plan, apply, destroy | [OCI Terraform Authoring](../skills/oci-terraform-authoring/) |
| Resource Manager stacks, jobs, logs, state, drift operations | [OCI Resource Manager](../skills/oci-resource-manager/) |
| OS Management Hub registration, software sources, Ksplice, update jobs, patch evidence | [OCI OS Management](../skills/oci-os-management/) |

## Data and Databases

| User intent | Use this skill |
|---|---|
| Autonomous Database lifecycle, private endpoints, wallet, ACL, scale, connectivity | [OCI Autonomous DB](../skills/oci-autonomous-db/) |
| Base Database and Exadata lifecycle, PDB, backup, patching, Data Guard | [OCI Database Cloud](../skills/oci-database-cloud/) |
| Database Management, Operations Insights, Performance Hub, AWR, ADDM, ASH, DBSNMP | [OCI DBM OPSI](../skills/oci-dbm-opsi/) |
| Data Integration, Data Flow, Data Catalog, GoldenGate, NoSQL, data movement, replication | [OCI Data Platform](../skills/oci-data-platform/) |
| Log Analytics, Logan, OCL/LQL queries, sources, parsers, entities, detections | [OCI Log Analytics](../skills/oci-log-analytics/) |

## Application Delivery

| User intent | Use this skill |
|---|---|
| Functions, Events, ONS, Service Connector Hub, Queue, Streaming, event workers | [OCI Events Functions](../skills/oci-events-functions/) |
| DevOps, API Gateway, Container Instances, Artifact Registry, OCIR delivery | [OCI Developer Services](../skills/oci-developer-services/) |

## Observe and Optimize

| User intent | Use this skill |
|---|---|
| Monitoring, Logging, APM, OpenTelemetry, alarms, dashboards, PromQL-to-MQL | [OCI Observability DB](../skills/oci-observability-db/) |
| Cost, usage, spend, forecasts, budgets, FinOps guardrails | [OCI Cost](../skills/oci-cost/) |

## When to Hand Off

This pack is the safety-gated CLI, Terraform, and operator path for common OCI
administration. Hand off only when the work needs deeper upstream coverage:

| User intent | Hand off target |
|---|---|
| Specialist OKE day-2 topics such as GVA, Multus, and specialized cluster design | Oracle `oci/oke` skills |
| OCI Generative AI, Enterprise AI, model agents, RAG, and governance | Oracle `oci/enterprise-ai` skills |
| Local Functions workstation deployment or workstation troubleshooting | Oracle `oci/functions` skills |
| Inside-database SQL, PL/SQL, RMAN, AWR/ASH, migrations, Data Guard internals | Oracle `db/` skills |
| Fusion Applications work | Oracle Fusion Cloud Applications documentation until concrete upstream Fusion skills are available |

## Good Request Shapes

These prompts help agents choose the right path quickly:

```text
Use the dev context to read IAM policy drift for this compartment, redact output,
and do not mutate OCI.
```

```text
Generate an offline private API + Functions platform bundle named payments-api.
Validate the schema and list required IAM policies, but do not deploy.
```

```text
Plan an OKE ingress TLS rollout. Give exact read commands, risk classification,
verification, rollback, and required approval gates before any action.
```

```text
Review this Terraform for dual ownership with Resource Manager and local state.
Keep the output tenant-neutral.
```

## Installation Pointers

Use the [quickstart](QUICKSTART.md) for copy installs across Claude Code,
Codex/ChatGPT, Gemini CLI, and Antigravity. Plugin metadata is under
`.claude-plugin/`, `.codex-plugin/`, and `harness/`.

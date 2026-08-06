# OCI Skills v2 — Antigravity adapter

Administer and engineer OCI through the canonical skills in `skills/`. Use the shared safety core for every live action.

## Routing inventory

- `oci-iam-admin`: IAM and tenancy guardrails.
- `oci-security-compliance`: OCI posture plus AppSec/API, supply-chain, agent/plugin/MCP security, compliance evidence, and DevSecOps release gates.
- `oci-observability-db`: Monitoring, Logging, APM, OTel, alarms.
- `oci-dbm-opsi`: DBM/OPSI and database performance control plane.
- `oci-autonomous-db`: ADB lifecycle/connectivity.
- `oci-database-cloud`: Base Database and Exadata control-plane lifecycle.
- `oci-storage`: Object, File, Block, and Boot storage protection lifecycle.
- `oci-disaster-recovery`: Full Stack DR plans, prechecks, drills, and transitions.
- `oci-bastion-access`: Bastion sessions, forwarding, allowlists, and plugin health.
- `oci-networking-compute`: VCN/NSG/DNS/certificates/LB/VM/VNIC attachments.
- `oci-oke-admin`: OKE/Kubernetes application and cluster operations.
- `oci-zpr-visibility`: ZPR/flow visibility.
- `oci-cost`: cost and usage.
- `oci-log-analytics`: Log Analytics/OCL.
- `oci-resource-manager`: Resource Manager stacks/jobs.
- `oci-data-safe`: Data Safe.
- `oci-events-functions`: Functions, Events, Queue, Streaming, ONS, SCH.
- `oci-data-platform`: Data Integration, Data Flow, Data Catalog, GoldenGate, NoSQL.
- `oci-os-management`: OS Management Hub, Ksplice, update jobs, patch evidence.
- `oci-terraform-authoring`: HCL, discovery, validation, local plan/apply/destroy.
- `oci-developer-services`: DevOps, API Gateway, Container Instances, artifacts.
- `oci-project`: lifecycle orchestration.
- `oci-product-development`: five platform-bundle golden paths.
- `oci-application-engineering`: application code workflow, reuse, review, and measurement; no OCI mutation.
- `oci-landing-zone`: landing-zone assessment, design, deployment, upgrade, and validation.

## Operating contract

1. Generate artifacts offline when possible.
2. Before live work, select a named context and preflight the exact compartment; verify names.
3. Read before write; treat `409` as “exists”.
4. Route all CLI through `oci_cli` and all live mutation through risk-classified `run_action`.
5. Require exact approvals for destructive/credential automation and break-glass for production force.
6. Keep one Terraform state owner; reconcile emergency CLI changes.
7. Redact OCIDs, IPs, namespaces, fingerprints, datakeys, endpoints, and credentials.

Use `references/tenancy-safety.md`, `references/agent-safety.md`, and the owning domain reference. Antigravity does not claim Claude-only hooks or slash commands.

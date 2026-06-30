# OCI Skills v2 — Antigravity adapter

Administer and engineer OCI through the canonical skills in `skills/`. Use the shared safety core for every live action.

## Routing inventory

- `oci-iam-admin`: IAM and tenancy guardrails.
- `oci-security-compliance`: security, Vault, WAF, audit, compliance, and DevSecOps release gates.
- `oci-observability-db`: Monitoring, Logging, APM, OTel, alarms.
- `oci-dbm-opsi`: DBM/OPSI and database performance control plane.
- `oci-autonomous-db`: ADB lifecycle/connectivity.
- `oci-networking-compute`: VCN/NSG/LB/VM/VNIC/volume.
- `oci-oke-admin`: OKE/Kubernetes application and cluster operations.
- `oci-zpr-visibility`: ZPR/flow visibility.
- `oci-cost`: cost and usage.
- `oci-log-analytics`: Log Analytics/OCL.
- `oci-resource-manager`: Resource Manager stacks/jobs.
- `oci-data-safe`: Data Safe.
- `oci-events-functions`: Functions, Events, Queue, Streaming, ONS, SCH.
- `oci-terraform-authoring`: HCL, discovery, validation, local plan/apply/destroy.
- `oci-developer-services`: DevOps, API Gateway, Container Instances, artifacts.
- `oci-project`: lifecycle orchestration.
- `oci-product-development`: platform-bundle golden paths.

## Operating contract

1. Generate artifacts offline when possible.
2. Before live work, select a named context and preflight the exact compartment; verify names.
3. Read before write; treat `409` as “exists”.
4. Route all CLI through `oci_cli` and all live mutation through risk-classified `run_action`.
5. Require exact approvals for destructive/credential automation and break-glass for production force.
6. Keep one Terraform state owner; reconcile emergency CLI changes.
7. Redact OCIDs, IPs, namespaces, fingerprints, datakeys, endpoints, and credentials.

Use `references/tenancy-safety.md`, `references/agent-safety.md`, and the owning domain reference. Antigravity does not claim Claude-only hooks or slash commands.

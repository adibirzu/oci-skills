# OCI Skills v2 for Gemini CLI

Use this extension for OCI administration, exact CLI plans, Terraform authoring, and product-platform bundles.

## First move

For a live target, select a named context, run `./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>`, verify names, and search `./scripts/kb_lookup.py`. Artifact-only scaffolding needs no credentials.

## Routing

- `oci-iam-admin`: IAM, compartments, budgets, quotas, tags, limits.
- `oci-security-compliance`: OCI posture plus vendor-neutral AppSec/API, supply-chain, agent/plugin/MCP security, compliance evidence, and DevSecOps release gates.
- `oci-observability-db`: Monitoring, Logging, APM, OTel, alarms, dashboards.
- `oci-dbm-opsi`: DBM, OPSI, Performance Hub, AWR/ADDM/ASH, DBSNMP.
- `oci-autonomous-db`: ADB lifecycle, wallet, ACL, private connectivity.
- `oci-database-cloud`: Base Database and Exadata control-plane lifecycle.
- `oci-storage`: Object, File, Block, and Boot storage protection lifecycle.
- `oci-disaster-recovery`: Full Stack DR plans, prechecks, drills, and transitions.
- `oci-bastion-access`: Bastion sessions, forwarding, allowlists, and plugin health.
- `oci-networking-compute`: VCN, NSG, routing, DNS, certificates, LB, VM/VNIC attachments.
- `oci-oke-admin`: OKE/Kubernetes, ingress, TLS, OCIR pulls, rollouts.
- `oci-zpr-visibility`: ZPR inventory and flow-log correlation.
- `oci-cost`: usage, spend, budgets, FinOps.
- `oci-log-analytics`: OCL/LQL, sources, parsers, detections.
- `oci-resource-manager`: managed Terraform stacks and jobs.
- `oci-data-safe`: target registration, assessment, audit, masking.
- `oci-events-functions`: Functions, Events, ONS, SCH, Queue, Streaming.
- `oci-terraform-authoring`: HCL, discovery, local validate/plan/apply/destroy.
- `oci-developer-services`: DevOps, API Gateway, Container Instances, Artifact Registry/OCIR delivery.
- `oci-project`: project lifecycle orchestration.
- `oci-product-development`: five platform-bundle golden paths.
- `oci-application-engineering`: application code workflow, reuse, review, and measurement; no OCI mutation.
- `oci-landing-zone`: landing-zone assessment, design, deployment, upgrade, and validation.

## Rules

- Use `oci_cli`; query exact command shapes with `oci_cli_help.py` and lint plans with `oci_cli_lint.py`.
- Use `run_action` for live mutation. Destructive/credential automation needs exact approval; production force needs break-glass.
- Terraform owns durable resources by default. Reconcile any CLI break-glass change.
- Never print or commit sensitive topology or credentials; redact and use placeholders.
- Route specialist GenAI, in-database, deep OKE, and Fusion work to official Oracle sources.

Gemini uses the in-script safety core. Claude-only slash commands and hooks are not claimed here.

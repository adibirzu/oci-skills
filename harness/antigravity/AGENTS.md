# OCI Administrator — Antigravity agent skill

Antigravity (AGY) reads `AGENTS.md` for agent context. Install this pack so the
agent can administer any OCI tenancy. `install.sh` copies the repo into the
Antigravity skills directory and links this file as the active `AGENTS.md`.

## Capability

Administer, audit, provision, secure, and troubleshoot Oracle Cloud
Infrastructure across thirteen domains, plus project lifecycle orchestration. Each
route has a dedicated skill under `skills/` and a reference under `references/`:

- **IAM & Tenancy** (`oci-iam-admin`) — users, groups, dynamic groups, policies, compartments,
  budgets, quotas, service limits, tags, Identity Domains.
- **Security & Compliance** (`oci-security-compliance`) — Cloud Guard, Vault/KMS, Security Zones, WAF,
  Audit, CIS / ISO-42001 / sovereignty scanning, IAM policy review.
- **Observability** (`oci-observability-db`) — Monitoring/alarms, Logging, Log Analytics,
  APM, Notifications, Service Connector, OpenTelemetry, dashboards.
- **DBM / OPSI** (`oci-dbm-opsi`) — Database Management, Operations Insights,
  Performance Hub, AWR/ADDM/ASH, DBSNMP, DB log ingestion.
- **Autonomous Database** (`oci-autonomous-db`) — ADB/ADW/ATP lifecycle, wallet rotation, ACLs,
  service levels, app connection patterns, and read-only SQL diagnostics.
- **Networking & Compute** (`oci-networking-compute`) — VCN, subnets, NSGs, route tables, gateways, load
  balancers, compute instances, OCIR.
- **OKE Admin** (`oci-oke-admin`) — OKE deploys, kubectl/kubeconfig, ingress-nginx,
  OCI LoadBalancer services, TLS secrets/certificates, OCIR image pulls,
  rollouts, virtual nodes, and deployment troubleshooting.
- **ZPR Visibility** (`oci-zpr-visibility`) — Zero Trust Packet Routing inventory,
  security attributes, protected resources, flow-log correlation, custom logs,
  and Log Analytics dashboards.
- **Cost & Usage (FinOps)** (`oci-cost`) — Usage API spend by service/compartment/region/tag,
  budgets (limit vs actual vs forecast), cost-tracking tags, guardrails.
  Read-only via `./scripts/oci_cost.sh`.
- **Log Analytics (Logan)** (`oci-log-analytics`) — the OCL query language, sources/parsers/fields,
  entities/log groups, detections (Sigma→OCL), saved/scheduled searches,
  dashboards, migration. Read-only query via `./scripts/oci_logan.sh`.
- **Resource Manager (ORM)** (`oci-resource-manager`) — managed Terraform: stacks, plan/apply/destroy
  jobs, tfstate, drift, schema.yaml packaging.
- **Data Safe** (`oci-data-safe`) — target registration, security/user assessment, activity
  auditing, data discovery, data masking.
- **Events & Functions (serverless)** (`oci-events-functions`) — OCI Functions, the Events service
  (rules→FAAS/ONS/STREAMING), Notifications/ONS, Service Connector Hub fan-out,
  Streaming transport.
- **Project lifecycle** (`oci-project`) — bootstrap, status/health, deploy/release, and gated
  teardown through `oci-project` above the thirteen domains.

## Operating contract (non-negotiable)

1. **Preflight first.** Run `./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>`
   and confirm the resolved tenancy/compartment **names** before any change.
2. **KB before debugging.** `python3 ./scripts/kb_lookup.py "symptom words"`.
3. **All CLI through `oci_cli`** (`./scripts/common.sh`) — it negotiates auth.
4. **Read before write; idempotent.** `409 Conflict` means "already exists".
5. **Destructive ops need confirmation.** Use `confirm` / `run_mutating`; honor
   `OCI_SKILLS_DRY_RUN=true` and `OCI_SKILLS_FORCE=true`.
6. **Never emit secrets.** Pipe output through `redact` / `./scripts/redact.py`;
   use `<PLACEHOLDER>` tokens in any written artifact.

See `references/tenancy-safety.md` for the full safety contract.

# OCI Administrator — Antigravity agent skill

Antigravity (AGY) reads `AGENTS.md` for agent context. Install this pack so the
agent can administer any OCI tenancy. `install.sh` copies the repo into the
Antigravity skills directory and links this file as the active `AGENTS.md`.

## Capability

Administer, audit, provision, secure, and troubleshoot Oracle Cloud
Infrastructure across six domains, each with a dedicated skill under
`skills/` and a reference under `references/`:

- **IAM & Tenancy** — users, groups, dynamic groups, policies, compartments,
  budgets, quotas, service limits, tags, Identity Domains.
- **Security & Compliance** — Cloud Guard, Vault/KMS, Security Zones, WAF,
  Audit, CIS / ISO-42001 / sovereignty scanning, IAM policy review.
- **Observability & Database** — Monitoring/alarms, Logging, Log Analytics,
  APM, Notifications, Service Connector, Database Management, Operations Insights.
- **Networking & Compute** — VCN, subnets, NSGs, route tables, gateways, load
  balancers, OKE, compute instances, OCIR.
- **Cost & Usage (FinOps)** — Usage API spend by service/compartment/region/tag,
  budgets (limit vs actual vs forecast), cost-tracking tags, guardrails.
  Read-only via `./scripts/oci_cost.sh`.
- **Log Analytics (Logan)** — the OCL query language, sources/parsers/fields,
  entities/log groups, detections (Sigma→OCL), saved/scheduled searches,
  dashboards, migration. Read-only query via `./scripts/oci_logan.sh`.

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

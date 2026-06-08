# AGENTS.md — OCI Administrator skill pack

This file is read by Codex, Antigravity, and other `AGENTS.md`-aware agents at
the repo root. It mirrors `SKILL.md` (the Claude entrypoint) so every harness
gets the same operating contract.

## What this is

A tenancy-agnostic OCI administration skill pack. Route any OCI request to one
of eight domain skills under `skills/`, all sharing the safety core in
`scripts/` and `references/`.

## Always, before acting

1. `./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>` — confirm the tenancy.
2. `python3 ./scripts/kb_lookup.py "symptom words"` — check known fixes.
3. Read `references/tenancy-safety.md` once per session.

## Routing

| Topic | Skill / reference |
|---|---|
| IAM, policies, compartments, budgets, quotas, tags | `skills/oci-iam-admin/` · `references/iam-tenancy.md` |
| Cloud Guard, Vault, WAF, CIS/ISO-42001, audit | `skills/oci-security-compliance/` · `references/security-compliance.md` |
| APM, Log Analytics, Monitoring, DBM, Ops Insights | `skills/oci-observability-db/` · `references/observability-db.md` |
| VCN, NSG, LB, OKE, compute, OCIR | `skills/oci-networking-compute/` · `references/networking-compute.md` |
| cost, usage, spend, budget, forecast, billing, FinOps | `skills/oci-cost/` · `references/cost-management.md` (read-only; `scripts/oci_cost.sh`) |
| Log Analytics, Logan, OCL/LQL query, source, parser, entity, log group, detection, Sigma→OCI | `skills/oci-log-analytics/` · `references/log-analytics.md` (read-only query: `scripts/oci_logan.sh`) |
| Resource Manager, ORM, Terraform stack, plan/apply/destroy job, tfstate, drift | `skills/oci-resource-manager/` · `references/resource-manager.md` |
| Data Safe, target registration, security/user assessment, audit, masking | `skills/oci-data-safe/` · `references/data-safe.md` |

## Hard rules

- All CLI through `oci_cli` (negotiates auth/profile/region).
- Read before write; treat `409` as "exists"; keep operations idempotent.
- Destructive ops require confirmation; honor `OCI_SKILLS_DRY_RUN`.
- Never print or commit OCIDs, IPs, fingerprints, datakeys, or secrets. Redact
  with `scripts/redact.py`; use `<PLACEHOLDER>` tokens in docs.
- Add a `KB-<n>` entry after fixing any new operational error.

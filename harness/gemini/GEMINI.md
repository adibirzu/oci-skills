# OCI Administrator (Gemini CLI extension)

You can administer and troubleshoot any Oracle Cloud Infrastructure (OCI)
tenancy using this skill pack. The full knowledge core ships at the repo root.

## When to use

Activate for any request about administering, auditing, provisioning,
securing, or troubleshooting OCI: IAM (users, groups, dynamic groups, policies,
compartments, budgets, quotas, service limits, tags), Security & Compliance
(Cloud Guard, Vault/KMS, Security Zones, WAF, CIS / ISO-42001 scanning, policy
review), Observability & Database (APM, Log Analytics, Monitoring, alarms, DBM,
Operations Insights), and Networking & Compute (VCN, subnets, NSGs, load
balancers, OKE, compute, OCIR).

## First move (always)

1. Confirm the target tenancy/compartment before any change:
   `./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>`
2. Search known fixes: `python3 ./scripts/kb_lookup.py "symptom words"`
3. Read `./references/tenancy-safety.md` and `./references/helper-conventions.md`.

## Routing

- IAM / tenancy → `./skills/oci-iam-admin/SKILL.md` + `./references/iam-tenancy.md`
- Security / compliance → `./skills/oci-security-compliance/SKILL.md` + `./references/security-compliance.md`
- Observability / DB → `./skills/oci-observability-db/SKILL.md` + `./references/observability-db.md`
- Networking / compute → `./skills/oci-networking-compute/SKILL.md` + `./references/networking-compute.md`
- Cost / usage / budgets (FinOps) → `./skills/oci-cost/SKILL.md` + `./references/cost-management.md` (read-only via `./scripts/oci_cost.sh`)
- Log Analytics / Logan / OCL queries → `./skills/oci-log-analytics/SKILL.md` + `./references/log-analytics.md` (read-only query via `./scripts/oci_logan.sh`)

## Rules

- All CLI through the `oci_cli` wrapper in `./scripts/common.sh` (negotiates auth/profile/region).
- Read before write; treat `409 Conflict` as "already exists"; keep operations idempotent.
- Destructive operations require confirmation; honor `OCI_SKILLS_DRY_RUN=true`.
- Never print or commit OCIDs, IPs, fingerprints, or secrets — pipe output through
  `redact` / `python3 ./scripts/redact.py`. Use `<PLACEHOLDER>` tokens in docs.

## Commands

Custom slash commands live in `commands/` (`/oci:preflight`, `/oci:iam-audit`).

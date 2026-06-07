---
name: oci-administrator
description: >-
  Generic, tenancy-agnostic Oracle Cloud Infrastructure (OCI) administration
  skill. Use whenever the user asks to administer, audit, configure, provision,
  inspect, secure, or troubleshoot an OCI tenancy — IAM (users, groups, dynamic
  groups, policies, compartments, budgets, quotas, service limits, tags),
  Security & Compliance (Cloud Guard, Vault/KMS, Security Zones, WAF, CIS /
  ISO-42001 scanning, policy review), Observability & Database (APM, Log
  Analytics, Monitoring, alarms, Database Management, Operations Insights), or
  Networking & Compute (VCN, subnets, NSGs, route tables, load balancers, OKE,
  compute instances, OCIR). Triggers on mentions of OCI, oci-cli, OCID,
  compartment, tenancy, IAM policy, Cloud Guard, Vault, WAF, OKE, VCN, NSG,
  Log Analytics, APM, service limits, cost, usage, spend, budget, billing,
  Usage API, FinOps, or ~/.oci/config. This is the
  tenancy-agnostic admin pack; for the OCI-DEMO component system use
  oracle-oci-management instead.
license: MIT
---

# OCI Administrator

Operate any OCI tenancy safely. This skill routes administrative requests to one
of five domain skills, all sharing one tenancy-safety core.

## First move (always)

1. Identify the **domain** of the request (IAM, Security, Observability/DB,
   Networking/Compute) and the **tenancy/compartment** it targets.
2. Prefer a **named context** over raw OCIDs — `dev`, `prod`, etc. resolve to a
   profile + compartment + region (see
   [references/named-contexts.md](../../references/named-contexts.md)):
   ```bash
   eval "$(scripts/oci_context.py use dev)"   # sets profile/region/compartment
   ```
3. Confirm the target tenancy before any change (by name, never raw OCID):
   ```bash
   ./scripts/oci_preflight.sh -c "${OCI_SKILLS_COMPARTMENT:-<COMPARTMENT_OCID>}"
   ```
4. Search the KB before deep debugging:
   ```bash
   python3 scripts/kb_lookup.py "symptom words"
   ```
5. Read [references/tenancy-safety.md](../../references/tenancy-safety.md) and
   [references/helper-conventions.md](../../references/helper-conventions.md) once per
   session, then load only the domain reference you need. For auth/secret questions
   read [references/credential-management.md](../../references/credential-management.md).

## Slash commands (Claude Code plugin)

When installed as a plugin, these wrap the safety core so the user works by name:

| Command | Does |
|---|---|
| `/oci-administrator:context` | Manage named contexts (name → profile + compartment + region). |
| `/oci-administrator:preflight` | Confirm the target tenancy/compartment by name (read-only gate). |
| `/oci-administrator:audit` | Read-only IAM posture snapshot. |
| `/oci-administrator:cost` | Read-only cost, usage & budget summary. |
| `/oci-administrator:kb` | Search the KB for a known fix. |
| `/oci-administrator:troubleshoot` | KB-first, route to domain, propose a gated fix. |

## Domain routing

| Request mentions… | Plugin | Reference |
|---|---|---|
| users, groups, dynamic groups, policies, compartments, budgets, quotas, service limits, tags, regions | **oci-iam-admin** | [references/iam-tenancy.md](../../references/iam-tenancy.md) |
| Cloud Guard, Vault/KMS, Security Zones, WAF, CIS, ISO-42001, compliance, policy review, audit logs | **oci-security-compliance** | [references/security-compliance.md](../../references/security-compliance.md) |
| APM, Log Analytics, Monitoring, alarms, dashboards, Database Management, Operations Insights, metrics | **oci-observability-db** | [references/observability-db.md](../../references/observability-db.md) |
| VCN, subnet, NSG, route table, gateway, load balancer, OKE, compute, instance, image, OCIR | **oci-networking-compute** | [references/networking-compute.md](../../references/networking-compute.md) |
| cost, spend, usage, billing, invoice, forecast, FinOps, cost-tracking tag, Usage API | **oci-cost** | [references/cost-management.md](../../references/cost-management.md) |

Each domain skill lives in `skills/<name>/SKILL.md` and leans on this shared core.

## Operating rules

- **Read before write.** `get`/`list` first; treat `409 Conflict` as "exists".
- **Confirm destructive ops.** Use `confirm` / `run_mutating` from `common.sh`.
  Honor `OCI_SKILLS_DRY_RUN=true` and `OCI_SKILLS_FORCE=true`.
- **Never print or commit secrets.** Run output through `redact` /
  `scripts/redact.py`; use `<PLACEHOLDER>` tokens in docs.
- **All CLI through `oci_cli`.** It negotiates auth mode, profile, and region.
- **Add a KB entry** after resolving any new operational error.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/common.sh` | Shared helpers (auth, validation, dry-run, redaction). |
| `scripts/oci_context.py` | Named contexts (name → profile + compartment + region); no OCIDs to memorize. |
| `scripts/oci_preflight.sh` | Confirm tenancy/compartment before mutating. |
| `scripts/iam_audit.py` | Read-only IAM posture snapshot (SDK). |
| `scripts/redact.py` | Mask OCIDs/IPs/secrets in text or JSON (CI gate). |
| `scripts/kb_lookup.py` | Search `references/KB.md` for a known fix. |

## Expected output

```markdown
**Finding** — concrete state/issue and the domain + tenancy (names, not OCIDs).
**Evidence** — file/line, redacted CLI/API result, or log line.
**Action** — exact command(s); destructive ones gated by confirm/dry-run.
**Verification** — checks run and result.
**KB** — KB entry used, or new KB-<n> added.
```

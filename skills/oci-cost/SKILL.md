---
name: oci-cost
description: >-
  Cost, usage, and budget reporting (FinOps) for any OCI tenancy via oci-cli:
  spend grouped by service / compartment / region over a time window using the
  Usage API, budgets and alert rules (limit vs actual vs forecast), cost-tracking
  tags, and guardrail recommendations. Use whenever a request mentions OCI cost,
  spend, billing, invoice, usage, Usage API, budget, forecast, cost alert,
  FinOps, "what is this tenancy costing", or cost-tracking tags. Read-only by
  default; for creating budgets it defers to oci-iam-admin.
license: MIT
---

# OCI Cost & Usage (FinOps)

Answer "what is this tenancy costing, and where?" without learning the Usage API.
This skill is **read-first** — it reports spend and budgets and recommends
guardrails. It leans on the shared tenancy-safety core (`oci_cli`, `redact`).

## First move (always)

1. Confirm which tenancy you are reading (cost is tenancy-scoped):
   ```bash
   ./scripts/oci_preflight.sh
   ```
2. Get the spend + budget snapshot in one call:
   ```bash
   ./scripts/oci_cost.sh -d 30 -g DAILY        # last 30 days, by service
   ./scripts/oci_cost.sh -g MONTHLY -d 90       # last 3 months, month-aligned
   ```
3. Search the KB before deep debugging:
   ```bash
   python3 scripts/kb_lookup.py "usage api cost" cost
   ```

Read [../../references/cost-management.md](../../references/cost-management.md) for
command shapes and [../../references/tenancy-safety.md](../../references/tenancy-safety.md)
for the safety rules.

## Routing — pick the task

| Request mentions… | Go to |
|---|---|
| total spend, cost by service, "what am I paying for" | Spend summary |
| cost by compartment / region / tag | Grouped usage |
| budget status, am I over budget, forecast | Budgets |
| set up alerts, guardrails, no budget exists | Guardrail setup → oci-iam-admin |
| cost-tracking tag, chargeback, showback | Cost-tracking tags |

## Common multi-step flows

| Task | Sequence |
|------|----------|
| Answer "what are we paying for" | `oci_cost.sh -d 30` → read top spend drivers → drill down with `--group-by compartmentName` / cost-tracking tag |
| Investigate a cost spike | `oci_cost.sh` by service → group-by compartment to localize → audit *who created* the resource (→ **oci-log-analytics** Audit query) → recommend a budget alert (→ **oci-iam-admin**) |
| Set up chargeback / showback | define a cost-tracking tag (→ **oci-iam-admin**) → `--group-by-tag` usage query → recurring monthly report |
| No budget exists yet | `oci_cost.sh` for current spend + forecast → recommend a budget + 80% alert → defer creation to **oci-iam-admin** (it gates the mutation) |

## Common tasks

```bash
# One-shot spend-by-service + budgets (the default view).
./scripts/oci_cost.sh -d 30

# Spend grouped by compartment (Usage API, COST query).
oci_cli usage-api usage-summary request-summarized-usages \
  --tenant-id <TENANCY_OCID> \
  --time-usage-started 2026-05-01T00:00:00Z \
  --time-usage-ended   2026-06-01T00:00:00Z \
  --granularity MONTHLY --query-type COST \
  --group-by '["compartmentName"]'

# Spend grouped by a cost-tracking tag (chargeback/showback).
oci_cli usage-api usage-summary request-summarized-usages \
  --tenant-id <TENANCY_OCID> \
  --time-usage-started 2026-05-01T00:00:00Z \
  --time-usage-ended   2026-06-01T00:00:00Z \
  --granularity MONTHLY --query-type COST \
  --group-by-tag '[{"namespace":"CostCenter","key":"team"}]'

# List budgets — NOTE the triple-nested path (service/category/resource).
oci_cli budgets budget budget list --compartment-id <TENANCY_OCID> \
  --query 'data[].{name:"display-name",limit:amount,spent:"actual-spend",forecast:"forecasted-spend"}'

# Forecast vs limit — flag budgets trending over.
./scripts/oci_cost.sh -d 30 | awk '/forecast=/ {print}'
```

## Gotchas

- **Budget CLI path is `budgets budget budget list`** — the OCI CLI nests the
  service (`budgets`), category (`budget`), and resource (`budget`); `budgets
  budget list` does not exist.
- **Usage API needs an explicit `--tenant-id`.** For config auth `oci_cost.sh`
  reads it from `~/.oci/config`; for instance/resource-principal auth pass
  `-t <TENANCY_OCID>` or set `OCI_SKILLS_TENANCY`.
- **Timestamps must align to the granularity.** DAILY needs a midnight-UTC
  start; MONTHLY needs the first of the month. `oci_cost.sh` aligns automatically.
- **`usage-reports` grant required:** `allow group <g> to read usage-report in
  tenancy`. Without it the Usage API returns nothing (not an error).
- **Latency:** cost data lags real time by hours; today's spend is usually $0.

## Safety notes

- **Read-only by default.** Reporting changes nothing. Creating budgets/alerts is
  a mutation — route to **oci-iam-admin**, which gates it via `run_mutating`.
- **Never print OCIDs.** The aggregated views are service/compartment names +
  amounts by construction; if you query raw items, pipe through `redact`.

## Expected output

```markdown
**Finding** — spend total + top cost drivers, and budget status (names, not OCIDs).
**Evidence** — redacted oci_cost.sh / Usage API result.
**Action** — read-only by default; guardrail commands (budget + alert) shown but
gated, deferred to oci-iam-admin to execute.
**Verification** — re-run oci_cost.sh showing the budget/alert now present.
**KB** — KB entry used, or new KB-<n> added.
```

## Official documentation

[Cost Analysis](https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/costanalysisoverview.htm) · [Budgets](https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/budgetsoverview.htm). Full list in the [cost-management reference](../../references/cost-management.md).

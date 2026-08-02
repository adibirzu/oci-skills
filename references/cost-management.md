# Cost & Usage (FinOps)

Domain reference for the **oci-cost** skill. Covers the Usage API (spend by
service / compartment / region / tag), budgets and alert rules, and cost-tracking
tags. Read [tenancy-safety.md](tenancy-safety.md) and
[helper-conventions.md](helper-conventions.md) first.

Reporting is **read-only**. Creating budgets or alert rules is a mutation — those
go through the **oci-iam-admin** skill, which gates them via `run_action` /
`confirm`. Every command goes through the `oci_cli` wrapper.

For a one-shot snapshot run `./scripts/oci_cost.sh` — it returns spend grouped by
service plus configured budgets, with no OCIDs in the output.

## Quick navigation

Use Usage API for spend, Budgets for thresholds, cost-tracking tags for
allocation, FOCUS for normalization, and Output discipline for reporting.

## The Usage API

`usage-api request-summarized-usages` is **tenancy-scoped**: it always needs an
explicit `--tenant-id`, regardless of the compartment you care about (you filter
compartments via `--group-by` / `--filter`, not `--compartment-id`).

```bash
# Spend by service for a month (COST query, MONTHLY granularity).
oci_cli usage-api usage-summary request-summarized-usages \
  --tenant-id <TENANCY_OCID> \
  --time-usage-started 2026-05-01T00:00:00Z \
  --time-usage-ended   2026-06-01T00:00:00Z \
  --granularity MONTHLY --query-type COST \
  --group-by file://<TMP_0600_GROUP_BY_SERVICE_JSON>

# By compartment, then by region.
  --group-by file://<TMP_0600_GROUP_BY_COMPARTMENT_JSON>
  --group-by file://<TMP_0600_GROUP_BY_REGION_JSON>

# By a cost-tracking tag (chargeback / showback).
  --group-by-tag '[{"namespace":"CostCenter","key":"team"}]'

# USAGE instead of COST (consumed quantities, not dollars).
  --query-type USAGE
```

### Rules that bite

- **Timestamps must align to the granularity.** DAILY → a midnight-UTC start
  (`...T00:00:00Z`); MONTHLY → the first of the month. A mis-aligned start is
  rejected. `oci_cost.sh` computes aligned UTC bounds with `python3` (portable
  across BSD/GNU `date`).
- **`time-usage-ended` is exclusive** and must also sit on a boundary; use the
  next day/month start, not "now".
- **Required grant:** `allow group <g> to read usage-report in tenancy`. Missing
  it yields an **empty** result, not a permission error — diagnose accordingly.
- **Data lags** real time by hours. Today's spend is typically `$0`; trust the
  trailing window, not the current day.
- **`computed-amount` can be null** for zero-usage rows — filter them before
  summing (`select(.["computed-amount"] != null)`).

An empty result is inconclusive and not proof of zero spend. Before closing the
investigation, diagnose permission, time-window alignment and lag, region, and
tenancy scope, then rerun a completed trailing window as a read-only check.

## Budgets

```bash
# List — the CLI path is TRIPLE-nested: service(budgets) category(budget)
# resource(budget). `budgets budget list` does NOT exist.
oci_cli budgets budget budget list --compartment-id <TENANCY_OCID> \
  --query 'data[].{name:"display-name",limit:amount,spent:"actual-spend",forecast:"forecasted-spend",period:"reset-period"}'

# Get one budget's alert rules.
oci_cli budgets alert-rule list --budget-id <BUDGET_OCID>
```

Budgets are usually created against the **tenancy root** compartment but can
target any compartment (`--target-type COMPARTMENT --targets '[...]'`) or a
cost-tracking tag (`--target-type TAG`). `actual-spend` and `forecasted-spend` are
recomputed periodically — compare both against `amount` to catch trend-over.

### Creating guardrails (mutation → oci-iam-admin)

```bash
# Budget with a MONTHLY reset (gated by run_action in oci-iam-admin).
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create budget" -- \
  oci_cli budgets budget budget create \
  --compartment-id <TENANCY_OCID> --target-type COMPARTMENT \
  --targets file://<TMP_0600_TARGETS_JSON> --amount 500 --reset-period MONTHLY \
  --display-name prod-budget

# Alert at 80% of actual and 100% of forecast.
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create actual-spend alert" -- \
  oci_cli budgets alert-rule create --budget-id <BUDGET_OCID> \
  --type ACTUAL    --threshold 80  --threshold-type PERCENTAGE \
  --display-name actual-80
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create forecast alert" -- \
  oci_cli budgets alert-rule create --budget-id <BUDGET_OCID> \
  --type FORECAST  --threshold 100 --threshold-type PERCENTAGE \
  --display-name forecast-100
```

## Cost-tracking tags

A defined-tag key marked **cost-tracking** lets the Usage API split spend by that
key (`--group-by-tag`). Set the flag at tag-key creation in oci-iam-admin (Tags),
then chargeback/showback queries become possible. Only cost-tracking keys are
valid in `--group-by-tag`.

## FOCUS v1.3 normalization (multicloud cost comparison)

To compare OCI spend apples-to-apples with AWS/Azure/GCP, map OCI Usage-API fields
to FinOps **FOCUS** columns:

| FOCUS column | OCI Usage-API field |
|---|---|
| `BilledCost` / `EffectiveCost` | `computed_amount` |
| `ListCost` | `unit_price * computed_quantity` |
| `ServiceName` | `service` |
| `UsageQuantity` | `computed_quantity` |
| `UsageUnit` | `unit` (e.g. `OCPU_HOUR`, `GB_MONTH`) |
| `RegionId` | `region` |
| `ResourceId` | `resource_id` |

`ChargeType` map: `USAGE`→Usage; `MONTHLY_COMMITMENT`/`ANNUAL_COMMITMENT`→Purchase;
`CREDIT`→Adjustment. `ServiceCategory` map: COMPUTE/CONTAINER_ENGINE→Compute;
`*_STORAGE`→Storage; DATABASE/AUTONOMOUS_DATABASE/MYSQL/NOSQL→Database;
NETWORKING/LOAD_BALANCER→Networking; GENERATIVE_AI/AI_SERVICES→"AI and Machine
Learning"; FUNCTIONS/API_GATEWAY/EVENTS→Serverless.

## Output discipline

The aggregated views (by service / compartment / region / tag) are names +
amounts and contain no OCIDs. If you drop to raw `data.items[]`, pipe through
`redact` before printing or committing. Never echo a `<BUDGET_OCID>` or
`<TENANCY_OCID>` in reports — use display names.

## Official documentation

Canonical Oracle docs for the services covered above (verified live):

- [Cost Analysis](https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/costanalysisoverview.htm)
- [Budgets](https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/budgetsoverview.htm)
- [Cost-tracking tags (Tagging)](https://docs.oracle.com/en-us/iaas/Content/Tagging/home.htm)

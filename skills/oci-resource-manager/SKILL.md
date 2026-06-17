---
name: oci-resource-manager
description: >-
  OCI Resource Manager (ORM) — managed Terraform — administration via oci-cli:
  stacks, plan/apply/destroy jobs, job log and state retrieval, drift detection,
  state import, variables (flat name→string map, JSON-encoded complex values),
  and packaging a Terraform bundle as a deployable stack with schema.yaml. Use
  whenever a request mentions OCI Resource Manager, ORM, RMS, a Terraform stack,
  plan/apply/destroy job, terraform-version, execution plan strategy, tfstate,
  drift, stack outputs, or "deploy to Oracle Cloud". Plan/read is safe; apply and
  destroy jobs are mutations gated by the shared safety core.
license: MIT
---

# OCI Resource Manager (ORM)

Operate managed-Terraform stacks safely. Stack/job **reads** (get, list, plan,
logs, state) are safe; **apply** and **destroy** jobs are mutations and go through
`run_mutating` / `confirm`. All CLI runs through `oci_cli`
(`../../scripts/common.sh`). Never inline real OCIDs — use `<PLACEHOLDER>` tokens.

## First move (always)

1. Confirm the tenancy/compartment before any job:
   ```bash
   ./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>
   ```
2. Check the KB before debugging a stuck job:
   ```bash
   python3 scripts/kb_lookup.py "resource manager job" cli
   ```

Read [../../references/resource-manager.md](../../references/resource-manager.md)
for the full lifecycle, job-wait pattern, variables, and `schema.yaml` packaging,
and [../../references/tenancy-safety.md](../../references/tenancy-safety.md) for
the safety rules.

## Routing — pick the task

| Request mentions… | Go to |
|---|---|
| create/import a stack, schema.yaml, "deploy to Oracle Cloud" | Lifecycle / packaging |
| plan, apply, destroy, execution plan strategy | Jobs |
| job stuck / hangs / `--wait-for-state` | Waiting on jobs (KB-007) |
| outputs, OCIDs from the stack, tfstate, drift | State, outputs & drift |
| list/lists/maps variable won't pass | Variables (flat map) |

## Common multi-step flows

| Task | Sequence |
|------|----------|
| Safe apply | `create-plan-job` → `get-job-logs-content` (review the plan) → `create-apply-job --execution-plan-strategy FROM_PLAN_JOB_ID` → verify stack outputs |
| Drift check | `create-plan-job` → read the plan: "no changes" = no drift; otherwise reconcile the source or the live resource |
| Package & deploy a bundle | assemble the Terraform + `schema.yaml` → `stack create` from the zip → plan → reviewed apply |
| Debug a stuck job | poll `job get … 'lifecycle-state'` and break on **every** terminal state (never `--wait-for-state SUCCEEDED` alone) → dump `get-job-logs-content` on `FAILED` (KB-007, KB-083) |

## Common tasks

```bash
# Plan a stack and read the human-readable plan BEFORE applying.
run_mutating "plan" oci_cli resource-manager job create-plan-job --stack-id <STACK_OCID>
oci_cli resource-manager job get-job-logs-content --job-id <PLAN_JOB_OCID>

# Apply bound to a reviewed plan (safer than AUTO_APPROVED on prod).
run_mutating "apply" oci_cli resource-manager job create-apply-job --stack-id <STACK_OCID> \
  --execution-plan-strategy FROM_PLAN_JOB_ID --execution-plan-job-id <PLAN_JOB_OCID>

# Drift check = a plan job that reports no changes.
run_mutating "drift plan" oci_cli resource-manager job create-plan-job --stack-id <STACK_OCID>

# Destroy (gated).
run_mutating "destroy" oci_cli resource-manager job create-destroy-job --stack-id <STACK_OCID> \
  --execution-plan-strategy AUTO_APPROVED
```

## Job-wait rule (critical)

Never trust `--wait-for-state SUCCEEDED` alone — a `FAILED`/`CANCELED` job is not
`SUCCEEDED`, so the CLI polls for the whole `--max-wait-seconds` window instead of
returning (KB-007). Poll `job get --query 'data."lifecycle-state"'` and **break on
every terminal state**, dumping `get-job-logs-content` on failure.

## Safety notes

- **Plan → review → apply.** Read the plan job's logs and get confirmation before
  `create-apply-job`. Prefer `FROM_PLAN_JOB_ID` over `AUTO_APPROVED` for prod.
- **Destroy is destructive** — `confirm`, and prefer a plan/dry-run first.
- **tfstate may hold secrets** — pipe `get-job-tf-state` through `redact`; never
  commit or log raw state.
- **Serialize jobs** — concurrent apply/destroy on one stack corrupts state.
- **Never invent `oci` flags.** Fetch the exact command shape first:
  `python3 scripts/oci_cli_help.py <service> <op>`.

## Expected output

```markdown
**Finding** — stack/job state and what will change (names, not OCIDs).
**Evidence** — redacted plan-job log excerpt or job lifecycle-state.
**Action** — exact job command(s); apply/destroy gated by confirm/dry-run.
**Verification** — a follow-up plan job showing no drift, or the stack outputs.
**KB** — KB entry used (e.g. KB-007), or new KB-<n> added.
```

## Official documentation

[Resource Manager](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/home.htm). Full list in the [resource-manager reference](../../references/resource-manager.md).

**Open Knowledge Format grounding** — every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill to build an OCI customer solution, cite the most specific official page through that index so every claim stays verifiable; the non-official MCP gateway is never a source of truth.

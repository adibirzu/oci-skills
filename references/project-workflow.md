# OCI Project Workflow

Deep reference for the [oci-project](../skills/oci-project/SKILL.md) lifecycle
orchestrator. The skill sequences the nine domain skills for one project; this
file holds the full recipes. Safety rules live in
[tenancy-safety.md](tenancy-safety.md); the decision layer in
[agent-safety.md](agent-safety.md); authoritative docs in
[oracle-docs.md](oracle-docs.md).

## The project model

A **project** = a [named context](named-contexts.md) + a naming prefix + a
budget:

```
<name> → { profile, region, compartment, prefix=<name>, budget }
```

The named context (managed by `scripts/oci_context.py`) already supplies
`profile + region + compartment`. The project adds a **prefix** (every resource
is named `<name>-*`) and a **budget**. Bind once, then every stage targets that
compartment — no OCIDs to paste:

```bash
scripts/oci_context.py add demo --profile DEFAULT --region eu-frankfurt-1 \
  --compartment <PROJECT_COMPARTMENT_OCID> --description "demo project"
eval "$(scripts/oci_context.py use demo)"      # exports OCI_SKILLS_COMPARTMENT etc.
```

Contexts live in `~/.oci-skills/contexts.json` (mode 0600, outside the repo), so
real OCIDs never touch git.

## Stage 1 — Bootstrap

Goal: an empty compartment becomes a guard-railed home for the project. Every
step is **idempotent** (search by name; `409` = exists) and **gated**
(`run_mutating` honors `OCI_SKILLS_DRY_RUN=true`). Order matters: the
compartment must exist before anything can be scoped to it.

```bash
# Preview everything first, change nothing:
OCI_SKILLS_DRY_RUN=true ./scripts/oci_project.sh bootstrap -n demo \
  -c <PARENT_COMPARTMENT_OCID> -b 500
```

What `oci_project.sh bootstrap` does itself (low blast radius, idempotent):

1. **Compartment** — `iam compartment list` by name under the parent; create only
   if absent. → [oci-iam-admin](../skills/oci-iam-admin/SKILL.md)
2. **Project tag** — `iam compartment update --freeform-tags '{"project":"demo"}'`
   so spend and inventory roll up. (For chargeback, promote this to a
   cost-tracking *defined* tag; see [cost-management.md](cost-management.md).)
3. **Budget** — `budgets budget create` on the compartment, and it emits the
   **80% forecast alert-rule** command.

What it **emits for you to run via the domains** (tenancy blast radius — these
belong to their owners, each gated by `confirm`/`run_mutating`):

4. **Scoped IAM** — a `<name>-admins` group + a policy that grants
   `manage all-resources in compartment <name>` — **never** `in tenancy`. Scoping
   to the compartment is the whole point of the project boundary. →
   [oci-iam-admin](../skills/oci-iam-admin/SKILL.md), [iam-tenancy.md](iam-tenancy.md)
5. **Network skeleton** — a VCN (e.g. `10.0.0.0/16`), subnets, and the gateway
   the project needs: a **NAT gateway** for private egress, an **IGW** only if
   internet-facing (KB-042 — a new VCN's default route table is empty). →
   [oci-networking-compute](../skills/oci-networking-compute/SKILL.md)

Re-running bootstrap converges — existing resources are detected and skipped.

## Stage 2 — Status / health

`oci_project.sh status` answers "what is the state of my project?" with one
read-only pass over the project compartment. It prints **counts, states, and
names — never OCIDs** (the scope OCID is redacted). It reports:

- compute / VCN / OKE / load-balancer inventory and lifecycle states,
- **ACTIVE Cloud Guard problems** (warns if any) →
  [oci-security-compliance](../skills/oci-security-compliance/SKILL.md),
- alarm definitions present,
- budgets with limit / spent / forecast.

**Gotchas:**

- An **empty section is inconclusive**, not proof of absence — a missing IAM
  grant, the wrong region (regional resources hide cross-region, KB-029/KB-075),
  or a child compartment excluded from the query all look like "zero". Confirm
  the bound context before concluding.
- "0 alarm definitions" ≠ "nothing is wrong"; "no active problems" needs the
  reporting region to be the one Cloud Guard targets (KB-073).
- For spend, cost data lags hours — today's number is usually low. Use
  [oci-cost](../skills/oci-cost/SKILL.md) (`oci_cost.sh`) for the full breakdown.

## Stage 3 — Deploy / release

Bind the deployment to the project context, then drive it through the owning
domain. **Never hand-mutate what Terraform manages** — it causes drift.

### Resource Manager (preferred for infrastructure)

```
plan  → review the plan-job logs → apply FROM_PLAN_JOB_ID → verify outputs
```

→ [oci-resource-manager](../skills/oci-resource-manager/SKILL.md),
[resource-manager.md](resource-manager.md). Prefer `FROM_PLAN_JOB_ID` over
`AUTO_APPROVED` on anything production. A drift check is a plan job that reports
no changes.

### OKE rollout (for containerized workloads)

Verify the kube context maps to **this** project's cluster before any
`kubectl apply` (KB-001 two-layer authz; KB-094 context-name is not proof of
tenancy), then roll out. →
[oci-networking-compute](../skills/oci-networking-compute/SKILL.md).

After any deploy: re-run `status` and confirm alarms + budget now cover the new
resources (a new instance with no CPU alarm is a monitoring gap).

## Stage 4 — Teardown

`oci_project.sh teardown` is **read-only**: it inventories the compartment and
prints the ordered destroy plan. It destroys nothing — you run each step through
the domain skills so it passes `confirm`/`run_mutating`. If the project was
stack-deployed, prefer a Resource Manager **destroy** job over manual deletes.

**Dependency order** (out-of-order deletes block on attached resources, KB-043):

1. Workloads / apps (helm uninstall, `kubectl delete`, app teardown)
2. Compute instances (`compute instance terminate`; set `--preserve-boot-volume`
   deliberately)
3. Load balancers
4. OKE clusters (node pools first)
5. Network — subnets, then gateways, then the VCN (VCN delete fails while
   subnets/VNICs are attached)
6. Budgets and alarms
7. The **compartment last** — it must be empty before `iam compartment delete`.

Teardown is irreversible. Plan first, `confirm` every step, and do it in a
non-prod context before any production one.

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `status` shows 0 of everything | wrong context / region / perms | re-bind context, `oci_preflight.sh`, check region (KB-029) |
| Bootstrap "created" a duplicate | skipped the name search | always `list` by name first; `409` = exists |
| VCN won't delete | subnets/VNICs still attached | delete in order (KB-043) |
| New resource has no alarm/budget coverage | deploy didn't update guardrails | re-run `status` after deploy; add the alarm |
| Teardown hit the wrong compartment | context not bound | bind + preflight **before** teardown — this is how prod gets destroyed |

## Official documentation

[Compartments / IAM](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm) ·
[Resource Manager](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/home.htm) ·
[Budgets](https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/budgetsoverview.htm) ·
[Tagging](https://docs.oracle.com/en-us/iaas/Content/Tagging/home.htm) ·
[Networking](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm).
Full index in [oracle-docs.md](oracle-docs.md).

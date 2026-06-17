# Project Phase 2 — Status / Health

Phase reference for the [oci-project](../skills/oci-project/SKILL.md) workflow
(index: [project-workflow.md](project-workflow.md)). Status is a **read-only
one-shot** — no progress block, no confirmations needed.

`oci_project.sh status` answers "what is the state of my project?" with one
read-only pass over the project compartment. It prints **counts, states, and
names — never OCIDs** (the scope OCID is redacted). It reports:

- compute / VCN / OKE / load-balancer inventory and lifecycle states,
- **untagged instances** (no freeform/defined tags) — a governance / roll-up gap,
- **ACTIVE Cloud Guard problems** (warns if any) →
  [oci-security-compliance](../skills/oci-security-compliance/SKILL.md),
- alarm definitions and how many are **FIRING** (`monitoring alarm-status list`),
- budgets with limit / spent / forecast, flagged when **trending over limit**.

```bash
./scripts/oci_project.sh status                 # active context's compartment
./scripts/oci_project.sh status -c <COMPARTMENT_OCID>
```

**Gotchas:**

- An **empty section is inconclusive**, not proof of absence — a missing IAM
  grant, the wrong region (regional resources hide cross-region, KB-029/KB-075),
  or a child compartment excluded from the query all look like "zero". Confirm
  the bound context before concluding.
- "0 alarm definitions" ≠ "nothing is wrong"; "no active problems" needs the
  reporting region to be the one Cloud Guard targets (KB-073).
- For spend, cost data lags hours — today's number is usually low. Use
  [oci-cost](../skills/oci-cost/SKILL.md) (`oci_cost.sh`) for the full breakdown.

Status is also the **resume probe**: when continuing an interrupted bootstrap or
teardown, run it first to read current state before deciding the next step.

**Docs:** [Monitoring](https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm) ·
[Cloud Guard](https://docs.oracle.com/en-us/iaas/cloud-guard/home.htm) ·
[Cost Analysis](https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/costanalysisoverview.htm).

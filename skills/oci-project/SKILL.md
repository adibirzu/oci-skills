---
name: oci-project
description: >-
  End-to-end OCI project lifecycle orchestrator. Use whenever the request is
  about a *project* as a whole rather than one service: stand up / bootstrap /
  scaffold a new OCI project (compartment + scoped IAM + network skeleton +
  budget guardrail + project tags), get a project's overall status / health /
  posture, deploy or release a project (Resource Manager stack or OKE rollout),
  or tear down / decommission / clean up a project. It binds a project to a
  named context (compartment + region + profile), accepts a schema-v1 platform
  bundle after design, and sequences the owning domain skills, each call gated
  by the shared safety core. Triggers
  on: new OCI project, bootstrap, scaffold, set up a project, project status,
  project health, "is my project healthy", deploy the project, release,
  promote, tear down, decommission, clean up, delete the project, project
  guardrails, project compartment. For a single-service task, use that domain
  skill directly.
---

# OCI Project Lifecycle

Take an OCI project from an empty compartment to running-and-guarded, and back.
This is the **orchestration layer**: it does not replace the primary domain skills —
it sequences them in the right order, scoped to one project, every mutation
through risk-classified `run_action`.

A **project** is a [named context](../../references/named-contexts.md) that
persists `name → { profile, region, compartment, prefix, budget }`. Bind it once
(`oci_context.py use <project>`) and every stage scopes to that compartment with
the prefix/budget as defaults — `bootstrap` then needs no `-n`/`-b` (explicit
flags still override).

**Stage 0 — Design (precedes bootstrap).** When you are starting from a customer
*requirement* rather than an existing project, design the solution first:
[references/solution-authoring.md](../../references/solution-authoring.md) takes
discovery → Well-Architected requirements → reference architecture → guardrail
design → cost → build → validate and produces a **Solution Blueprint** that fills
this context's prefix + budget. Design is read-only; bootstrap (below) is where
the blueprint becomes resources, each mutation gated. If Stage 0 selects a
product golden path, generate `platform-bundle.yaml` with
**oci-product-development** and pass it as `--bundle <path>`; Terraform remains
the owner of bundle resources.

Stage 0 and local bundle validation proceed without a bound context or OCI
credentials. Treat a missing context or preflight as a gate on bootstrap,
status, deploy, and teardown only; finish the safe blueprint, ownership, and
handoff work and report the exact live checkpoint still needed.

## First move (always)

1. Bind / confirm the project context (so every op targets the right compartment):
   ```bash
   eval "$(scripts/oci_context.py use <project>)"     # sets profile/region/compartment
   ./scripts/oci_preflight.sh -c "$OCI_SKILLS_COMPARTMENT"
   ```
   Eyeball the resolved tenancy + compartment **names**. Wrong target → stop.
2. Read the project's current state before changing anything:
   ```bash
   ./scripts/oci_project.sh status                    # read-only, no OCIDs printed
   ```
3. Search the KB before debugging:
   ```bash
   python3 scripts/kb_lookup.py "symptom words"
   ```

Read [../../references/project-workflow.md](../../references/project-workflow.md)
for the full lifecycle recipes and
[../../references/tenancy-safety.md](../../references/tenancy-safety.md) for the
safety rules. For *how to reason* before acting, read
[../../references/agent-safety.md](../../references/agent-safety.md).

## Interactive execution rules (bootstrap & teardown)

**Bootstrap** and **teardown** are multi-step and (for teardown) irreversible, so
run them as a *guided, one-step-at-a-time* flow — never a single "magical" pass.
These rules apply to those two stages (`status` is a read-only one-shot and is
exempt):

- **Show a progress block on every message.** So the human always sees where they
  are and can catch a skipped step. Prepend:
  ```text
  Project <name> · <bootstrap|teardown> progress:
    1. Context bound + preflighted   [done|active|—]
    2. <stage step 2>                [done|active|—]
    3. <stage step 3>                [done|active|—]
    …
  ```
  Update the markers as steps complete; never omit or shorten it.
- **One question at a time.** Ask exactly one thing, then stop. Do not bundle.
- **Respect turn boundaries.** When you need input or a confirmation, output the
  question and **stop calling tools** — you cannot receive the answer this turn.
  Never simulate or assume the user's reply.
- **Don't skip steps or infer completion.** Run every step in order even if
  detected state (existing compartment, active creds) suggests one is done —
  *verify* it with a read, report it, and move on; don't silently skip.
- **Confirm each mutation.** Show the exact gated command (dry-run first), then
  `confirm` before executing. Teardown destroys nothing without explicit
  per-resource confirmation.
- **Resume mid-flow.** If resuming, run `oci_project.sh status` to read current
  state, ask which step the user left off at, then continue from there — do not
  restart from scratch.
- **Never invent `oci` flags.** Fetch the exact command shape first:
  `python3 scripts/oci_cli_help.py <service> <op>` (see
  [agent-safety.md](../../references/agent-safety.md)).

## Routing — pick the stage

| Request mentions… | Stage | Helper |
|---|---|---|
| new project, bootstrap, scaffold, set up, guardrails | **Bootstrap** | `oci_project.sh bootstrap -n <name>` |
| status, health, posture, "what's the state", drift, what exists | **Status** | `oci_project.sh status` |
| deploy, release, promote, ship, roll out | **Deploy** | → oci-terraform-authoring / oci-resource-manager / owning runtime skill |
| tear down, decommission, clean up, delete the project | **Teardown** | `oci_project.sh teardown` (plan) |

## The four stages

### 1. Bootstrap (idempotent, gated)

*Phase reference (read first): [project-phase1-bootstrap.md](../../references/project-phase1-bootstrap.md).*

Stand up the project skeleton — each step searches first and treats `409` as
"exists", so re-running converges instead of duplicating:

1. **Compartment** — ensure the project compartment under the parent (→ `oci-iam-admin`).
2. **Scoped IAM** — a project group + a least-privilege policy *in this
   compartment* (never `manage all-resources in tenancy`) (→ `oci-iam-admin`).
3. **Network skeleton** — VCN + subnets + the gateway the project needs
   (NAT for private egress, IGW only if internet-facing) (→ `oci-networking-compute`).
4. **Budget guardrail** — a budget on the compartment + an 80% forecast alert
   (→ `oci-iam-admin`).
5. **Project tags** — a cost-tracking tag (`project = <name>`) so spend and
   inventory roll up (→ `oci-iam-admin`).

```bash
# Idempotent scaffold; honors OCI_SKILLS_DRY_RUN=true to print without creating.
./scripts/oci_project.sh bootstrap -n demo -c <PARENT_COMPARTMENT_OCID> -b 500   # --budget also accepted
```

The helper does the low-risk idempotent creates (compartment, tag, budget) and
**emits the gated IAM-policy and VCN commands** for you to run via the domain
skills — those carry tenancy-wide blast radius and belong to their owners.

### 2. Status / health (read-only)

*Phase reference: [project-phase2-status.md](../../references/project-phase2-status.md).*

The "what is the state of my project?" loop. One command aggregates posture +
spend + open security problems + observability gaps across the project
compartment, printing **names and counts, never OCIDs**:

```bash
./scripts/oci_project.sh status               # active context's compartment
./scripts/oci_project.sh status -c <COMPARTMENT_OCID>
./scripts/oci_project.sh status -c <COMPARTMENT_OCID> --bundle <PATH>/platform-bundle.yaml
```

It reports: compute, VCN, OKE, load balancer, API Gateway, DevOps, Container
Instances, and Queue inventory + lifecycle states, the declared state owner and
drift status, untagged
instances (governance gap), ACTIVE Cloud Guard problem count, alarm definitions
plus how many are **FIRING**, and each budget's limit / spent / forecast with a
flag when any is trending **over limit**. Empty sections are inconclusive
(perms/region), not proof of absence — see the gotchas in the reference.

### 3. Deploy / release

*Phase reference: [project-phase3-deploy.md](../../references/project-phase3-deploy.md).*

Bind the deployment to the project context, then drive it through the owning
domain — never hand-mutate what Terraform manages:

- **Local Terraform** — author/validate/plan/apply through
  `oci-terraform-authoring`, applying the exact reviewed plan.
- **Resource Manager (managed Terraform)** — `plan → review the plan job logs →
  apply FROM_PLAN_JOB_ID` (→ `oci-resource-manager`). Prefer this for
  managed execution, but never apply the same resources locally too.
- **OKE rollout** — verify the kube context maps to *this* project's cluster,
  then roll out (→ `oci-oke-admin`, KB-001/KB-094).
- After deploy, re-run `status` and confirm alarms + budget cover the new
  resources.

### 4. Teardown (planned, heavily gated)

*Phase reference (read first): [project-phase4-teardown.md](../../references/project-phase4-teardown.md).*

Decommission in **dependency order** — destroying out of order blocks on
attached resources (KB-043). Teardown is irreversible: plan first, confirm each
destructive step.

```bash
./scripts/oci_project.sh teardown -c <COMPARTMENT_OCID> --bundle <PATH>/platform-bundle.yaml
```

The helper lists what exists and prints the **ordered, gated destroy commands**;
it does not destroy anything itself. For a Terraform-owned bundle, prefer a
reviewed Terraform destroy plan. Order: delivery/workloads → gateways/runtimes →
Queue/Streaming → database/compute → load balancers/OKE → network → compartment last.

## Common multi-step flows

| Task | Sequence |
|------|----------|
| Stand up a new project | `oci_context.py add <name>` → `oci_project.sh bootstrap` (dry-run first) → run the emitted IAM/VCN commands via the domains → `status` to confirm guardrails |
| Daily project check | `oci_context.py use <name>` → `oci_project.sh status` → triage any ACTIVE Cloud Guard problem (→ oci-security-compliance) → check budget forecast (→ oci-cost) |
| Ship an infra change | bind context → `oci-resource-manager` plan → review → apply FROM_PLAN_JOB_ID → `status` → confirm alarms cover new resources |
| Decommission cleanly | `oci_project.sh teardown` (inventory + plan) → run ordered destroys via the domains → re-run `status` (empty) → delete the compartment last |
| Bundle lifecycle | validate bundle → author/plan through owning skills → deploy via one Terraform surface → owner-aware status → reviewed teardown plan |

## Safety notes

- **Scope to the project compartment, always.** Bind the context and preflight
  before any stage; a wrong compartment is how teardown hits production.
- **Bootstrap is idempotent; teardown is irreversible.** Re-running bootstrap
  converges; teardown is plan-first, `confirm` every destroy, and prefer doing it
  in a non-prod context first.
- **Never `manage all-resources in tenancy`** for a project — the scoped policy
  is compartment + verb + resource-family.
- **Mutations go through the domains' guards.** This skill orchestrates; the
  domain skills own the actual risk-classified `run_action` calls.
- **Never print OCIDs.** `status` is names + counts by construction; pipe any raw
  output through `redact`.

## Expected output

```markdown
**Project** — name, bound context (tenancy + compartment NAMES, region).
**Stage** — bootstrap / status / deploy / teardown.
**Finding** — concrete state across domains (inventory, posture, spend, guardrails).
**Action** — the ordered command(s); mutations gated by confirm/dry-run, run via the owning domain.
**Verification** — re-run `oci_project.sh status` showing the desired end state.
**KB** — KB entry used, or new KB-<n> added.
```

## Official documentation

[Compartments](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm) · [Resource Manager](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/home.htm) · [Budgets](https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/budgetsoverview.htm) · [Tagging](https://docs.oracle.com/en-us/iaas/Content/Tagging/home.htm). Full index in [oracle-docs.md](../../references/oracle-docs.md).

**Open Knowledge Format grounding** — every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill to build an OCI customer solution, cite the most specific official page through that index so every claim stays verifiable; the non-official MCP gateway is never a source of truth.

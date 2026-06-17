# OCI Project Workflow

Index for the [oci-project](../skills/oci-project/SKILL.md) lifecycle
orchestrator. The skill sequences the nine domain skills for one project; the
detailed recipes are split into **phase references** — read the phase's file
before running that stage. Safety rules live in
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

## Workflow map

Run the stages in order; **read the phase reference before starting the stage**.
Bootstrap and teardown are guided, one-step-at-a-time flows (progress block,
confirm each mutation); status is a read-only one-shot.

| Stage | Phase reference | Helper |
|---|---|---|
| 1. Bootstrap (idempotent, gated) | [project-phase1-bootstrap.md](project-phase1-bootstrap.md) | `oci_project.sh bootstrap -n <name> -c <parent> -b <budget>` |
| 2. Status / health (read-only) | [project-phase2-status.md](project-phase2-status.md) | `oci_project.sh status` |
| 3. Deploy / release | [project-phase3-deploy.md](project-phase3-deploy.md) | → oci-resource-manager / oci-networking-compute |
| 4. Teardown (planned, irreversible) | [project-phase4-teardown.md](project-phase4-teardown.md) | `oci_project.sh teardown -c <compartment>` |

**Resume mid-flow:** run `oci_project.sh status` to read current state, ask which
step was last completed, then resume from the corresponding phase reference — do
not restart.

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| `status` shows 0 of everything | wrong context / region / perms | re-bind context, `oci_preflight.sh`, check region (KB-029) |
| Bootstrap "created" a duplicate | skipped the name search | always `list` by name first; `409` = exists |
| VCN won't delete | subnets/VNICs still attached | delete in order (KB-043) |
| New resource has no alarm/budget coverage | deploy didn't update guardrails | re-run `status` after deploy; add the alarm |
| Teardown hit the wrong compartment | context not bound | bind + preflight **before** teardown — this is how prod gets destroyed |
| `oci` command rejected / wrong flags | constructed from memory | fetch the shape: `oci_cli_help.py <svc> <op>` (never invent flags) |

## Official documentation

[Compartments / IAM](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm) ·
[Resource Manager](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/home.htm) ·
[Budgets](https://docs.oracle.com/en-us/iaas/Content/Billing/Concepts/budgetsoverview.htm) ·
[Tagging](https://docs.oracle.com/en-us/iaas/Content/Tagging/home.htm) ·
[Networking](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm).
Full index in [oracle-docs.md](oracle-docs.md).

---
description: OCI project lifecycle — status (read-only), bootstrap (idempotent, gated), or teardown plan, scoped to a project context.
argument-hint: "[status|bootstrap|teardown] [context-name] [-n NAME] [-c COMPARTMENT] [-b BUDGET]"
allowed-tools: Bash, Read
---

Drive an OCI **project** through its lifecycle, scoped to one project compartment.
This orchestrates the nine domain skills; every mutation is gated. Default
sub-command is `status` (read-only).

Scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/` when installed as a plugin, else
`./scripts/` from a repo clone.

User input: `$ARGUMENTS`

Steps:
1. **Bind the project context first.** If the input names a context (a bare word,
   no leading `-`), activate it so every call targets the right compartment:
   - `eval "$(oci_context.py use <name>)"` (exports profile/region/compartment), then
   - `./scripts/oci_preflight.sh -c "$OCI_SKILLS_COMPARTMENT"` and eyeball the
     resolved tenancy + compartment **names**. Wrong target → stop.
2. **Pick the sub-command** from the input (default `status`):
   - **status** → `./scripts/oci_project.sh status` — read-only health: compute /
     VCN / OKE / LB inventory + states, ACTIVE Cloud Guard problems, alarms,
     budget. Counts and names only, never OCIDs.
   - **bootstrap** → `OCI_SKILLS_DRY_RUN=true ./scripts/oci_project.sh bootstrap
     -n <NAME> -c <PARENT_COMPARTMENT> [-b BUDGET]` **first** (preview), then re-run
     without `OCI_SKILLS_DRY_RUN` after the user confirms. Idempotent: it creates
     the compartment + project tag + budget and **emits** the gated IAM-policy and
     VCN commands to run via `oci-iam-admin` / `oci-networking-compute`.
   - **teardown** → `./scripts/oci_project.sh teardown -c <COMPARTMENT>` — prints a
     READ-ONLY inventory + the ordered destroy plan. It destroys nothing; run each
     step via the owning domain skill so it passes `confirm` / `run_mutating`.
3. **Report** using the project Expected-output block: project + bound context,
   stage, finding across domains, the ordered action(s) (gated), and the
   verification (`oci_project.sh status` showing the desired end state).

Safety: scope to the project compartment, bootstrap is idempotent, teardown is
irreversible (plan first, confirm every destroy). Full recipes in
`references/project-workflow.md`. Never print OCIDs.

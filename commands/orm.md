---
description: Read-only OCI Resource Manager overview — stacks + each stack's latest job state.
argument-hint: "[context-name] [-c <COMPARTMENT_OCID>] [-n MAX]"
allowed-tools: Bash, Read
---

List OCI Resource Manager (ORM) stacks in a compartment and the latest job
(operation + state) for each. **Read-only** — never creates a plan/apply/destroy
job. Output is display names + states, no OCIDs.

Scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/` when installed as a plugin, else
`./scripts/`.

User input: `$ARGUMENTS`

Steps:
1. **Resolve the target.** If the input names a context, read it with
   `oci_context.py get <name> --field profile|region` and export
   `OCI_CLI_PROFILE`/`OCI_REGION`; else honor `-c`/`-n` and the default profile.
2. **Run** `oci_orm.sh [-c <COMPARTMENT_OCID>] [-n MAX]`.
3. **Report** each stack with its lifecycle-state and last job (e.g.
   `APPLY=SUCCEEDED`, `DESTROY=FAILED`, `(none)`). Flag any stack whose last job
   is `FAILED` and offer to pull its logs (`job get-job-logs-content`).
4. **Stop.** This command does not mutate anything. To plan/apply/destroy, route
   to the **oci-resource-manager** skill, which gates jobs via `run_action` and
   reads the plan before applying.

Note: a `FAILED` last job + a "stuck" apply is usually KB-007/KB-083 (the
`--wait-for-state SUCCEEDED` hang) — poll lifecycle-state and break on all
terminal states.

---
description: Read-only OCI Data Safe overview — registered targets + latest security-assessment state.
argument-hint: "[context-name] [-c <COMPARTMENT_OCID>] [-n MAX]"
allowed-tools: Bash, Read
---

List OCI Data Safe target databases in a compartment and each target's latest
security-assessment state. **Read-only** — registers nothing and runs no
assessment/masking. Output is display names + states, no OCIDs.

Scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/` when installed as a plugin, else
`./scripts/`.

User input: `$ARGUMENTS`

Steps:
1. **Resolve the target.** If the input names a context, read it with
   `oci_context.py get <name> --field profile|region` and export
   `OCI_CLI_PROFILE`/`OCI_REGION`; else honor `-c`/`-n` and the default profile.
2. **Run** `oci_datasafe.sh [-c <COMPARTMENT_OCID>] [-n MAX]`.
3. **Report** each target with its lifecycle-state and latest security-assessment
   state. Flag any target in `NEEDS_ATTENTION` (often a stale service-account
   password / `ORA-01017` — see KB-057).
4. **Stop.** This command does not mutate anything. To register a target, refresh
   an assessment, change audit retention, or mask data, route to the
   **oci-data-safe** skill, which gates those via `run_action`.

Note: if "no targets" is reported, Data Safe may simply not be enabled in that
compartment, or the targets live in another region/compartment — widen the scope
before concluding.

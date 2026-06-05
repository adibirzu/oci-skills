---
description: Read-only OCI IAM posture snapshot — compartments, policies, broad grants, users without MFA.
argument-hint: "[context-name | --profile <name>]"
allowed-tools: Bash, Read
---

Produce a **read-only** IAM posture snapshot for an OCI tenancy. Changes nothing.

Scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/` when installed as a plugin, else
`./scripts/`.

User input: `$ARGUMENTS`

Steps:
1. Resolve the profile: if the input names a context, read it with
   `oci_context.py get <name> --field profile`; otherwise honor `--profile`
   (default `DEFAULT`).
2. Run `python3 scripts/iam_audit.py --profile <profile>` and pipe through `redact`
   (or `python3 scripts/redact.py`) so no raw OCIDs are shown.
3. Highlight, in priority order:
   - policies granting **`manage all-resources in tenancy`** (effective tenancy admin),
   - users without **MFA**,
   - dynamic groups with broad matching rules,
   - compartments with no budget/quota guardrails.
4. Recommend least-privilege scoping for each broad grant (verb + resource-family +
   compartment), but **do not change anything** — this is an audit.

Present findings in the Finding / Evidence / Action / Verification / KB format.

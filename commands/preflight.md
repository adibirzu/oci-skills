---
description: Confirm WHICH OCI tenancy/compartment you are about to act on (read-only) — by context name or OCID.
argument-hint: "[context-name | -c <COMPARTMENT_OCID>]"
allowed-tools: Bash, Read
---

Run the OCI **preflight** safety check and report the resolved tenancy, region, and
auth mode — by **name**, never raw OCIDs. This is the gate before any mutating
action.

Scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/` when installed as a plugin, else
`./scripts/` from a repo clone.

User input: `$ARGUMENTS`

Steps:
1. **Resolve the target.**
   - If the input names a context (no leading `-`), resolve it:
     - `profile=$(oci_context.py get <name> --field profile)`
     - `compartment=$(oci_context.py get <name> --field compartment)`
     - `region=$(oci_context.py get <name> --field region)`
     - export `OCI_CLI_PROFILE=$profile` and (if set) `OCI_REGION=$region`.
     - If the context is marked PROD, say so up front and be extra cautious.
   - If the input is `-c <OCID>` or empty, use it directly.
2. **Run preflight:** `oci_preflight.sh -c "$compartment"` (or no `-c` if none).
3. **Report** the tenancy name, home region, auth mode, and compartment name.
4. **Stop.** State plainly whether it is safe to proceed and WAIT for the user's
   confirmation before any create/update/delete. Do not mutate anything in this command.

If preflight cannot reach OCI, diagnose auth/profile/region/network — do not guess.

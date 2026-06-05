---
description: Manage friendly OCI contexts (name -> profile + compartment + region) so you never paste OCIDs.
argument-hint: "[list|add|use|get|rm] [name] [--profile P --compartment OCID --region R] [--prod]"
allowed-tools: Bash, Read
---

Manage **named OCI contexts** with `oci_context.py`. A context binds a short name
to the profile, compartment OCID, and region that almost every OCI call needs, so
the user works by name (`dev`, `prod`) instead of memorizing OCIDs. Contexts live
in `~/.oci-skills/contexts.json` (mode 0600) — never in this repo.

Locate the script at `${CLAUDE_PLUGIN_ROOT}/scripts/oci_context.py` when running as
an installed plugin, otherwise `./scripts/oci_context.py` from a repo clone.

User input: `$ARGUMENTS`

Behavior:
- No args, or `list` → run `oci_context.py list` and show the table (OCIDs stay masked).
- `add <name> ...` → require `--compartment` (a compartment or tenancy OCID) and
  `--profile`; pass `--region`, `--description`, `--prod` through as given. Confirm
  back the masked result.
- `use <name>` → tell the user to run `eval "$(oci_context.py use <name>)"` in THEIR
  shell (a subprocess cannot export into the parent), then echo what that sets.
- `get <name>` → human summary (masked). Only emit a raw OCID if the user explicitly
  asks for the value for a command.
- `rm <name>` → confirm, then remove.

Never print full compartment OCIDs in your summary unless explicitly requested.
Report in the Finding / Action / Verification shape.

# Named Contexts — Stop Pasting OCIDs

Almost every OCI call needs four things at once: a **profile** (which credentials),
a **region**, a **compartment OCID**, and the right **auth mode**. Memorizing and
re-pasting compartment OCIDs is the single biggest source of friction — and of
"oops, wrong tenancy" mistakes.

A **named context** binds the first three to a short name:

```
name  ->  { profile, compartment (OCID), region [, prod] }
```

So you say `dev` or `prod` and the pack resolves the rest. Managed by
[`scripts/oci_context.py`](../scripts/oci_context.py); stored in
`~/.oci-skills/contexts.json` (mode `0600`), **outside this repo** — real OCIDs
never touch git.

## Create and use

```bash
# One-time: register your tenancies/compartments by friendly name.
oci_context.py add dev  --profile DEFAULT    --region eu-frankfurt-1 \
  --compartment <DEV_COMPARTMENT_OCID> --description "personal sandbox"
oci_context.py add prod --profile prod-admin --region us-phoenix-1 \
  --compartment <PROD_COMPARTMENT_OCID> --prod        # --prod = extra-careful prompts

oci_context.py list                 # OCIDs shown masked, active context starred
oci_context.py get dev              # human summary (masked)

# Activate for the current shell (a subprocess can't export into its parent):
eval "$(oci_context.py use dev)"
#   sets OCI_CLI_PROFILE, OCI_REGION, OCI_SKILLS_COMPARTMENT, OCI_SKILLS_CONTEXT
```

After `use`, the pack's scripts pick up `OCI_CLI_PROFILE` / `OCI_REGION`
automatically, and `$OCI_SKILLS_COMPARTMENT` carries the compartment so commands
stop asking for `--compartment-id`:

```bash
oci_cli iam compartment list --compartment-id "$OCI_SKILLS_COMPARTMENT" --all
```

## Scripting

`get --field` prints one raw value to **stdout** (everything else goes to stderr),
so it composes cleanly:

```bash
compartment="$(oci_context.py get dev --field compartment)"
profile="$(oci_context.py get dev --field profile)"
./scripts/oci_preflight.sh -c "$compartment"
```

## In Claude Code

The slash commands resolve contexts for you:

```
/oci-administrator:context list
/oci-administrator:context add dev --profile DEFAULT --compartment <OCID> --region eu-frankfurt-1
/oci-administrator:preflight dev          # confirm the tenancy by NAME before acting
/oci-administrator:audit dev              # read-only IAM posture for that context
```

## Safety properties

- **Never prints full OCIDs** in summaries — only a masked tail (`…abc123`). Raw
  values are emitted solely via `get --field` (explicit, for command substitution)
  or `use` (shell exports you opt into).
- **Production contexts** (`--prod`) are flagged in `list` and surfaced by
  preflight so destructive actions get extra scrutiny — see
  [tenancy-safety.md](tenancy-safety.md).
- The store is `0600` and lives in `$HOME`, not the repo. Add `~/.oci-skills/` to
  your global gitignore if your dotfiles are versioned.
- Contexts are **convenience, not credentials.** They reference a `~/.oci/config`
  profile or principal auth; they store no keys. See
  [credential-management.md](credential-management.md).

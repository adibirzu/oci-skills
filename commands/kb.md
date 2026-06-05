---
description: Search the OCI skill pack's KB for a known fix before debugging from scratch.
argument-hint: "<symptom words> [domain: iam|security|observability|networking]"
allowed-tools: Bash, Read
---

Search the pack's knowledge base for a **known fix** before debugging.

Scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/` when installed as a plugin, else
`./scripts/`; the KB is `references/KB.md`.

User input: `$ARGUMENTS`

Steps:
1. Run `python3 scripts/kb_lookup.py "$ARGUMENTS"` (the last word may be a domain
   filter — pass it through as the optional second arg if present).
2. If there is a strong match, summarize the KB entry (id, root cause, fix) and apply
   the documented fix — do not re-investigate from scratch.
3. If there is **no** match, say so, proceed with first-principles troubleshooting,
   and once resolved, draft a new `KB-<n>` entry (component, error, root cause, fix,
   status) to append to `references/KB.md`.

Keep all output redacted (no raw OCIDs/IPs/secrets).

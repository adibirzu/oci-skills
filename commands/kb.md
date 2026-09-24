---
description: Search the OCI skill pack's KB for a known fix before debugging from scratch.
argument-hint: "<symptom words or KB-id> [domain tag]"
allowed-tools: Bash, Read
---

Search the pack's knowledge base for a **known fix** before debugging.

Resolve the installed pack root from `${CLAUDE_PLUGIN_ROOT}` for a plugin or
the loaded skill's location for a copy install. It contains `scripts/` and
`references/KB.md`; do not assume the consuming project contains either.

User input: `$ARGUMENTS`

Steps:

1. Run the installed `scripts/kb_lookup.py` with the symptom as one safely
   quoted argument and `--top 3 --show`. Treat input as data, never shell code.
   Pass a domain tag separately only when the user explicitly supplies it;
   never interpret the last symptom word as a tag. Exact `KB-001` lookup also works.
2. If there is a strong match, summarize the entry (id, root cause, fix, source),
   check applicability, and propose the smallest verification. Search matches
   neither prove the cause nor authorize a mutation. Follow the pack's normal
   approval, preflight, and ownership gates before applying a fix.
3. If there is **no** match, say so, proceed with first-principles troubleshooting,
   and once resolved, draft a new `KB-<n>` entry (component, error, root cause, fix,
   status) under `references/kb-ingestion.md` before proposing a pack update.

Keep all output redacted (no raw OCIDs/IPs/secrets).

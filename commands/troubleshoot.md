---
description: KB-first OCI troubleshooting — route to the right domain, propose a safe, confirmation-gated fix.
argument-hint: "<what's wrong> [context-name]"
allowed-tools: Bash, Read, Grep, Glob
---

Diagnose an OCI problem the safe way: known fixes first, the right domain second, a
gated remediation last.

Scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/` when installed as a plugin, else
`./scripts/`. Domain knowledge is in `references/` and `plugins/<name>/SKILL.md`.

User input: `$ARGUMENTS`

Steps:
1. **KB first.** `python3 scripts/kb_lookup.py "<symptom words>"`. If matched, apply it.
2. **Preflight.** If a context name is given, resolve it (`oci_context.py get`) and run
   `oci_preflight.sh -c <compartment>` so you know which tenancy you are inspecting.
3. **Route** to the domain and read its reference:
   - IAM / policy / service limit / quota → `references/iam-tenancy.md`
   - Cloud Guard / Vault / WAF / CIS / audit → `references/security-compliance.md`
   - APM / Log Analytics / Monitoring / DBM / OPSI → `references/observability-db.md`
   - VCN / NSG / route / LB / OKE / compute / OCIR → `references/networking-compute.md`
4. **Investigate read-only** with `oci_cli ... list/get`, output through `redact`.
   Form a concrete hypothesis with evidence — do not guess.
5. **Propose the fix** as exact commands, every mutation wrapped in
   `run_mutating` / `confirm` and honoring `OCI_SKILLS_DRY_RUN`. WAIT for confirmation.
6. After it works, append a new `KB-<n>` entry if this wasn't already in the KB.

Report in Finding / Evidence / Action / Verification / KB format. Never print raw
OCIDs/IPs/secrets.

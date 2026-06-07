---
description: Read-only OCI cost, usage, and budget summary — spend by service plus configured budgets.
argument-hint: "[context-name] [-d DAYS] [-g DAILY|MONTHLY]"
allowed-tools: Bash, Read
---

Produce a **read-only** cost summary for an OCI tenancy: spend grouped by service
over a time window, plus any configured budgets and their actual/forecast spend.
Changes nothing. Output is service names + amounts + budget display-names — no OCIDs.

Scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/` when installed as a plugin, else
`./scripts/` from a repo clone.

User input: `$ARGUMENTS`

Steps:
1. **Resolve the target.**
   - If the input names a context (no leading `-`), resolve it and export the
     profile/region:
     - `profile=$(oci_context.py get <name> --field profile)`
     - `region=$(oci_context.py get <name> --field region)`
     - export `OCI_CLI_PROFILE=$profile` and (if set) `OCI_REGION=$region`.
   - Otherwise honor any `-d`/`-g`/`-c`/`-t` flags and default `OCI_CLI_PROFILE`.
2. **Run** `oci_cost.sh` with the parsed flags
   (e.g. `./scripts/oci_cost.sh -d 30 -g DAILY`). Default is last 30 days, DAILY.
3. **Report**:
   - top services by spend and the grand total (with currency),
   - each budget with its limit, actual spend, and forecast,
   - flag any budget where `spent` or `forecast` is near/over `limit`.
4. **Recommend** guardrails when none exist: a tenancy-root budget with alert
   rules at e.g. 80% / 100% of limit. **Do not create anything** — this is read-only.

Notes:
- The Usage API is tenancy-scoped; the caller needs `read usage-report in tenancy`.
- For instance/resource-principal auth there is no `~/.oci/config` to read, so pass
  the tenancy explicitly: `-t <TENANCY_OCID>` or set `OCI_SKILLS_TENANCY`.
- `MONTHLY` granularity aligns the window to month boundaries automatically.

If the Usage API returns nothing, diagnose the missing `usage-reports` grant or a
wrong tenancy/region — do not guess at numbers.

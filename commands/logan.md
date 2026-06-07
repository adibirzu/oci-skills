---
description: Run a read-only OCI Log Analytics (OCL) query with a friendly time window.
argument-hint: "[context-name] \"<OCL query>\" [-t 24h] [-c <COMPARTMENT_OCID>]"
allowed-tools: Bash, Read
---

Run a **read-only** OCI Log Analytics query and report the rows. Changes nothing.
Auto-resolves the LA namespace; output is query rows — pipe through `redact`
before sharing (it may contain tenant field values).

Scripts live at `${CLAUDE_PLUGIN_ROOT}/scripts/` when installed as a plugin, else
`./scripts/` from a repo clone.

User input: `$ARGUMENTS`

Steps:
1. **Resolve the target.**
   - If the input begins with a context name (no leading `-`/quote), resolve it:
     `profile=$(oci_context.py get <name> --field profile)`,
     `region=$(oci_context.py get <name> --field region)` and export
     `OCI_CLI_PROFILE` / `OCI_REGION`. The remaining argument is the query.
   - Otherwise honor `OCI_CLI_PROFILE` and any `-c`/`-n`/`-t` flags.
2. **Run** `oci_logan.sh -q "<query>" [-t <window>] [-c <COMPARTMENT_OCID>]`.
   Default window is 24h; `-t` accepts `5m`/`24h`/`7d`/`2w`. Add `-m N` for more
   rows, `-S` to restrict to the single compartment (subtree is on by default).
3. **Report** the row count and the rows (redacted), and what the query measured.
4. **If zero rows**, diagnose before concluding "nothing happened":
   - **field typing** — string-typed integers must be quoted (`'Event ID' = '4625'`),
     true numeric fields must be bare (`'Destination Port' = 443`);
   - **time window** too narrow; **compartment** scope / subtree;
   - missing `read loganalytics-* in tenancy` grant.
   An empty result is **inconclusive**, not proof of absence.

Notes:
- Keep the query **time-agnostic** — the window is passed via `-t`, never embedded
  in the query string.
- The OCI CLI verb is `log-analytics query search` (a command group); `oci_logan.sh`
  wraps it. The LA namespace is auto-resolved and kept private.
- This command never mutates Log Analytics. Source/parser/entity/dashboard changes
  belong to the **oci-log-analytics** skill and go through `run_mutating`/`confirm`.

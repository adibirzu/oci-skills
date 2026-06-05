# ADR-0002: Named-context layer as the OCID-free UX primitive

**Date**: 2026-06-05
**Status**: accepted
**Deciders**: Adrian Birzu, Claude

## Context

Almost every OCI CLI call needs several coordinates supplied together: a `--profile`, a
`--compartment-id <OCID>`, a region, and (implicitly) an auth mode. Pasting opaque
compartment OCIDs on every command is slow and is the primary cause of "acted on the
wrong tenancy/compartment" mistakes. Unlike AWS profiles or `gcloud` configs, the OCI CLI
has no built-in concept that binds the compartment to a named context.

## Decision

Add `scripts/oci_context.py`: a friendly **named-context** layer binding a short name to
`{ profile, compartment-OCID, region [, prod] }`. State lives in
`~/.oci-skills/contexts.json` at mode `0600`, **outside the repo**. IDs are masked on
display; a raw value is emitted only via `get --field` (for command substitution) or
`use` (shell exports the user opts into). Slash commands and the safety scripts resolve
contexts by name, so users work with `dev`/`prod` instead of OCIDs.

## Alternatives Considered

### Alternative 1: No abstraction — keep pasting raw OCIDs
- **Pros**: zero new code/state.
- **Cons**: the exact friction and error source we set out to remove.
- **Why not**: defeats the "simplify OCI usage" goal.

### Alternative 2: YAML store (`contexts.yaml`)
- **Pros**: human-friendly to hand-edit.
- **Cons**: adds a PyYAML dependency for a trivial key-value store.
- **Why not**: the pack runs on stock Python 3.10 with no extra installs for the shell path; `json` is stdlib.

### Alternative 3: Store contexts inside the repo
- **Pros**: versioned with the project.
- **Cons**: compartment OCIDs are identifying tenancy data; they must stay off git.
- **Why not**: violates the pack's no-tenancy-data-in-repo rule.

### Alternative 4: Environment variables only
- **Pros**: no state file.
- **Cons**: no named multi-context switching, no prod guardrail, easy to leave the wrong values set.
- **Why not**: loses the core ergonomics and the prod-vs-sandbox safety signal.

## Consequences

### Positive
- Users work by name; commands stop demanding `--compartment-id`.
- `--prod` contexts are flagged in `list` and surfaced by preflight for extra scrutiny.
- The design (0600 in `$HOME`, masked display, field-extraction, eval-exports) generalizes to any verbose cloud CLI.

### Negative
- Introduces a per-user state file to create/manage (`~/.oci-skills/contexts.json`).

### Risks
- Contexts are convenience, **not** credentials — they reference a `~/.oci/config` profile
  or a principal and store no keys. Mitigation: documented explicitly; validation rejects
  non-OCID `--compartment` values; atomic `0600` writes.

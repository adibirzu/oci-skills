# OCI skill entrypoint quality standard

Use this standard when creating or reviewing a `skills/*/SKILL.md` entrypoint.
The goal is operational usefulness at invocation time without copying an entire
service manual into the prompt.

## Quick navigation

Use the entrypoint contract for required content, progressive disclosure for
placement, evidence rules for claim quality, and the review checklist before
calling a skill complete.

## Entrypoint contract

A mature domain entrypoint answers these questions before it redirects to a
long reference:

1. **What must be decided first?** Identify the target surface, intent, owner,
   evidence needed, and whether the next step is offline, read-only, additive,
   in-place, credential, or destructive.
2. **Which skill owns each adjacent surface?** Route by resource and lifecycle
   owner. A redirect must name both the positive owner and the boundary that
   stays here.
3. **Which reference should be read, and when?** Point to the smallest relevant
   reference, script, schema, or asset. Do not say only “see the docs.”
4. **What is the operator sequence?** Provide common multi-step flows that
   preserve read-before-write, idempotency, verification, rollback, and the
   pack's context-bound action envelope.
5. **How are common failures discriminated?** Separate wrong context, missing
   permission, missing source, empty window, asynchronous work, dependency
   failure, and real resource absence. Do not turn one symptom into a verdict.
6. **What proves completion?** Name the smallest useful offline checks, live
   reads, work-request or lifecycle checks, data-plane canaries, negative
   canaries, and rollback evidence. Keep evidence classes distinct.
7. **What must the response contain?** Require target, ownership, action/risk,
   evidence class, verification, rollback, residual gaps, and next safe action.

The headings may specialize to the domain, but these decisions must be easy to
find. A long file that lacks them is not mature; a concise file that answers
them and routes precisely can be.

## Progressive disclosure

Keep `SKILL.md` below 500 lines and reserve it for decisions that change how an
agent acts. Put stable service detail, command examples, payload shapes, and
failure catalogs in `references/`. Put deterministic generation or validation
in `scripts/`, schemas in `schemas/`, and reusable source material in `assets/`.

Link a reference from the exact decision that requires it. If an operator must
read a reference before a class of action, say so explicitly. Avoid duplicating
the same safety text in every skill when a precise link to
`tenancy-safety.md` or `agent-safety.md` carries the rule.

## Evidence and freshness

- Classify claims as code-backed, configured, locally verified, provider verified,
  release accepted, unverified, or unavailable.
- Never convert a plan, HTTP response, parser success, resource lifecycle state,
  or rendered dashboard into a higher evidence class.
- Keep tenant-specific counts, dates, endpoints, and customer baselines out of a
  reusable entrypoint. Store sanitized recurring failure knowledge in `KB.md`
  and stable product behavior in the owning reference with official sources.
- Use `references/oracle-docs.md` as the documentation index. For
  version-sensitive behavior, verify the current official source before
  changing the skill.
- A manifest, source file, prompt adapter, or MCP tool name proves only local
  configuration. Runtime reachability and provider behavior require separate
  evidence.

## Validation design

For each material flow, expose the smallest relevant sequence:

```text
offline lint/schema/test
  -> exact-context read or plan
  -> reviewed mutation when authorized
  -> lifecycle/work-request verification
  -> data-plane positive canary
  -> negative or rollback canary when risk warrants it
  -> redacted evidence handoff
```

State what an empty or failed check means and what it does not mean. Prefer a
named repository validator over prose-only review. Never invent a command to
make the validation section look complete.

## Review checklist

- The frontmatter description triggers on user language and excludes adjacent
  owners.
- First decisions prevent the most likely wrong-surface or wrong-target action.
- Routing names the owner for every commonly confused surface.
- Multi-step flows include read, action, verification, and rollback or cleanup.
- Failure discrimination prevents unsupported absence, security, or health
  conclusions.
- Validation distinguishes offline, live-read, provider, and release evidence.
- Output expectations are operator-usable and redaction-safe.
- References, scripts, schemas, and official documentation links resolve.
- No real tenancy identifiers, secrets, customer topology, or volatile live
  baseline is embedded in the reusable skill.

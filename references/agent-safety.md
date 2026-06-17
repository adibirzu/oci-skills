# Agent-Safe OCI Operations

How an *agent* should reason before touching an OCI tenancy — intent
disambiguation, idempotency, and destructive-operation classification. This is
the decision layer; the **mechanics** (auth, `confirm`, `run_mutating`,
`wait_for_state`, redaction) live in
[helper-conventions.md](helper-conventions.md), and the **tenancy-targeting
rule** lives in [tenancy-safety.md](tenancy-safety.md). Read those once; read
this when deciding *whether and how* to act, not *how to call the helper*.

Modeled on the agent-safety patterns in the `db/` domain of
[oracle/skills](https://github.com/oracle/skills) (`db/agent/`), adapted for
OCI control-plane operations.

## 1. Disambiguate intent before acting

A vague request is the most common cause of acting on the wrong resource. Resolve
these **before** the first mutating call:

| Ambiguity | Don't assume | Resolve by |
|---|---|---|
| **Which tenancy/compartment?** | the current profile | `oci_preflight.sh` → confirm the **name**; bind a [named context](named-contexts.md) |
| **Which region?** | the profile default | derive from the resource OCID (KB-029); regional resources hide cross-region (KB-075) |
| **Which resource**, when the name is non-unique | the first match | `list` by name; if >1, surface candidates and ask |
| **"delete the old one"** | newest/oldest | list with `time-created` + state; show what you'd remove, confirm |
| **"fix the alarm/policy/rule"** | you know which | read it first; quote its current state back |
| **Read or change?** | a verb implies mutation | default to read; escalate to mutation only on an explicit ask |

When two readings are plausible and one is destructive, **pick the read-only
interpretation and state your assumption**, e.g. *"Reporting current spend (not
creating a budget) — say so if you want the guardrail created."*

## 2. Default to read-only

Most questions ("what's going on", "is X configured", "who changed Y", "what does
it cost") are answered with `get`/`list`/`query` and change nothing. Stay there
until the user explicitly asks for a change. The read-only entrypoints —
`iam_audit.py`, `oci_cost.sh`, `oci_logan.sh`, `oci_orm.sh`, `oci_datasafe.sh` —
exist so you never need a mutation to *understand* a tenancy.

An **empty result is inconclusive, not proof of absence** (KB-024, KB-099):
before concluding "no alarm exists" / "no rows", verify the compartment subtree
flag, lifecycle-state filter, region, and (for Log Analytics) field typing and
time window.

## 2b. Don't fabricate the command — fetch its shape

The `oci` CLI is vast and deeply nested; inventing a flag or guessing a verb path
is a top cause of broken tasks. Before constructing a mutating command, fetch its
real shape and use only what it declares:

```bash
python3 scripts/oci_cli_help.py <service> <op>     # required vs optional flags / subcommands
```

If a flag is not in the output, it does not exist — do not guess it. See
[helper-conventions.md](helper-conventions.md). This is the command-shape analog
of citing [oracle-docs.md](oracle-docs.md) for facts: authoritative source over
memory.

## 3. Idempotency — every operation safe to repeat

The agent loop may retry, resume, or re-run. Make each step convergent, not
additive:

1. **Search by display name first.** Create only when the read returns
   empty/null. Treat `409 Conflict` as success and re-`list` — never blind-retry
   a create (duplicates resources that lack a uniqueness constraint).
2. **Update, don't recreate.** Prefer `update` on an existing resource over
   delete+create; recreate orphans dependents and OCIDs.
3. **Rotate by adding a version.** Secrets/keys get a *new version*
   (`secret update-base64`), never an in-place edit (KB-005).
4. **Capture the `etag` immediately before an etag-guarded update** (KB-065); a
   cached etag yields `412`.
5. **For async creates, recover the id from a work request**, then `list` by name
   (KB-008) — don't assume `data.id` is populated.

```bash
# Canonical idempotent create.
id=$(oci_cli <svc> <res> list --compartment-id "$CMPT" --all \
       --query "data[?\"display-name\"=='$NAME'].id | [0]" --raw-output)
[ -z "$id" -o "$id" = "null" ] && \
  run_mutating "create $NAME" oci_cli <svc> <res> create --display-name "$NAME" ...
```

## 4. Classify the operation before running it

| Class | Examples | Guard required |
|---|---|---|
| **Read** | `get`, `list`, `query`, assessments, plan jobs (read the plan) | none — just preflight the tenancy |
| **Additive mutation** | create alarm/policy/topic/stack, add NSG rule, tag | `run_mutating` (honors `OCI_SKILLS_DRY_RUN`) + idempotent check |
| **In-place mutation** | update config, rotate secret, apply job | `run_mutating`; capture etag/plan first |
| **Destructive** | `delete`, `terminate`, `destroy`, replace LB, force-delete, **data masking** | `confirm` **and** `run_mutating`; prefer a dry-run/plan first |

Destructive operations are irreversible or service-affecting. For them:

- Show **exactly** what will be removed/changed (names, counts) before the prompt.
- Prefer staging the change in a non-prod tenancy (`cap`-style) first.
- Honor `OCI_SKILLS_DRY_RUN=true` to print without executing; require
  `confirm` (or explicit `OCI_SKILLS_FORCE=true` for trusted automation).
- Set deletion side-effects explicitly (`--preserve-boot-volume` on instance
  terminate; child-resource ordering on VCN/subnet delete, KB-043).
- **Data masking is destructive on the masked copy** — mask only a verified
  non-prod database (see [data-safe.md](data-safe.md)).

The `PreToolUse` destructive-guard hook is **defense-in-depth that fails open**
(see [tenancy-safety.md](tenancy-safety.md)); the in-script `confirm` /
`run_mutating` calls are the authoritative control. Never rely on the hook alone.

## 5. Stop conditions

Halt and surface to the user — do not improvise — when:

- the preflight tenancy/compartment **name** is not the one expected;
- a `404 NotAuthorizedOrNotFound` cannot be disambiguated to authz vs absence
  (see [oci-error-catalog.md](oci-error-catalog.md));
- a destructive op would touch a resource you did not create and cannot confirm
  is in scope (read it, report the contradiction, ask);
- you are about to act in a known production profile without an explicit
  break-glass variable;
- output would expose an OCID/IP/secret you cannot redact.

## 6. Report what you actually did

Use the per-skill **Expected output** block (Finding / Evidence / Action /
Verification / KB). State plainly when a step was a dry-run, was skipped, or
failed — never imply a mutation ran when it was only printed. The redacted action
ledger (`audit_log`, see [tenancy-safety.md](tenancy-safety.md)) records whether
each guard actually fired.

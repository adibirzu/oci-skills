---
name: jd
description: Deliver a bounded engineering task or a multi-phase product goal with proportionate planning, low-cost capable agents, verification, and independent review where needed. Use when the user wants continued execution without repeated next-task prompts.
---

# Just Do It

Own the requested outcome through truthful verification. Choose the smallest
workflow that fits the task. Read [execution-policy](references/execution-policy.md)
before routing or dispatching agents; it defines bounded/program selection,
model tiers, call ceilings, compact packets, and review reuse.

## Start

1. Establish the user's goal, repository scope, required evidence, and authority.
   Implementation allows local edits, not commits, pushes, deployment, external
   messages, destructive operations, credential changes, or release acceptance.
2. Inspect repository instructions, current state, ownership, and unrelated
   dirty work. Preserve it. Use project knowledge lookup when required.
3. Inventory actual agent, sandbox, review, persistence, model, and permission
   capabilities. A role template or prompt does not prove runtime isolation or
   the model that ran. Record execution and delivery modes in a private,
   redacted run ledger. Default delivery is local-only.
4. Pick **bounded** for one clear local outcome with focused verification and
   no sensitive or release boundary; otherwise pick **program**. Use one task
   packet for bounded work and existing repository ledgers where required.
   Read [program workflow](references/program-workflow.md) only for programs.

When the user explicitly starts a persistent goal or says to continue until
complete, create a Codex Goal if available. Never infer extra authority from
persistence. Continue safe work until the outcome is verified or a genuine
input, authority, budget, or repeated-blocker hold remains.

## Execute

For a bounded behavior change, one Luna implementer may write a focused RED
contract, confirm its expected failure, implement GREEN, and run focused checks.
The coordinator reviews the diff and test evidence. Use a separate test worker
only when independent contract authorship has a concrete benefit. Routine
read-only discovery goes to the coordinator or a Luna scout; escalate planning
or integration to Terra only for a recorded reason. Never silently substitute a
stronger model. Send compact, self-contained packets without full history when
possible. Track requested and actual model separately; report unavailable
runtime usage honestly.

For a program, build small dependency-aware PRDs and bounded path leases.
Use the same low-cost task routing within each PRD. Never assign overlapping
writes concurrently. A scout stays read-only. Record attempts, decisions,
blockers, verification, and review evidence in the ledger. Continue ready work
while an unrelated decision is held.

Strict workers require proven network-disabled workspace isolation, a scrubbed
environment, disabled web/apps/MCP, bounded runtime, and `approval_policy =
"never"` before running repository-controlled code. If the harness cannot
prove that profile, do bounded local work as coordinator or transparently
shared-workspace work only where permitted; never call it isolated. Reviewers
must be read-only and independent of implementation. Read
[protocol](references/protocol.md) for result and request packets. Read
[capability grants](references/capability-grants.md) before any elevated,
network, credential, destructive, or external-write request.

## Review and close

Use one independent correctness review for a low-risk bounded change when
review is needed. Reuse it at closure only while the reviewed diff and tests
remain current. Programs may consolidate low-risk review; sensitive and
release-sensitive PRDs need independent review at their boundary, with a
separate security review for affected trust boundaries. High findings block
closure. A passing local check does not prove provider or release acceptance.

Run focused checks and the repository's authoritative gate relevant to the
change. Report changed files, evidence, actual model and sandbox when known,
remaining risks, and exact blockers. Mark a persistent goal complete only when
its full objective is achieved. Keep it active or explicitly report the hold
when required work remains.

## Conditional references

- [continuity](references/continuity.md): restart or compaction reconciliation.
- [recovery](references/recovery.md): stalled or looping workers.
- [delivery](references/delivery.md): authorized PR, merge, or landed verification.
- [distribution](references/distribution.md) and
  [harnesses](references/harnesses.md): role installation or non-Codex runtimes.
- [agent creation](references/agent-creation.md): reusable agent teams.
- [features](references/features.md): capability inventory and provenance.

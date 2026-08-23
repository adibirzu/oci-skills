# JD Continuity and Decision Protocol

Use this protocol for long-running work, session restarts, compaction recovery, deferred
decisions, and queues with dependency or time gates. It is file-backed coordination, not a
background daemon.

## Startup digest

At session start or after compaction:

1. Locate the active redacted run ledger and verify its goal digest and repository identity.
2. Compare its delivery/authority modes, event cursor, leases, worktrees, and task states with
   live agents, current diffs, and repository state.
3. Consume unseen events in sequence. Ignore duplicates; flag sequence gaps or conflicting task
   terminals for reconciliation.
4. Re-run evidence whose inputs changed or whose freshness window expired.
5. Requeue ready work that never started. Reopen work whose claimed result lacks a diff, report,
   or required verification.
6. Emit a short internal digest: active goal, completed/in-flight/blocked work, decision holds,
   next ready tasks, stale evidence, and permitted delivery boundary.

Never infer success from silence, an old event, a closed worker, a PR/MR label, or elapsed time.

## Event and checkpoint model

Record append-only, redacted event summaries with:

- monotonically increasing sequence;
- UTC timestamp;
- goal, PRD, and task identifiers;
- event type such as `ready`, `started`, `progress`, `blocked`, `reviewed`, `verified`, or `done`;
- artifact or evidence digest, not raw content;
- authority source for an external side effect.

The ledger stores the last consumed sequence and a reduced current-state checkpoint. Replaying an
event must be idempotent. Current state is derived from the newest consistent event plus live
evidence. If they disagree, preserve both facts, mark the task `reconcile`, and investigate.

## Decision holds

Create a decision hold only when a choice materially changes outcome, risk, cost, compatibility,
or external effects. Give it an identifier, decision owner, affected tasks, safe alternatives,
default if reversible, and the evidence needed to decide.

- Continue tasks that do not depend on the hold.
- Ask the user once with consolidated options and concrete impact.
- Record a redacted answer and authority source, then unblock only affected tasks.
- Never treat a timeout as approval. A reversible default may be used only when it was already
  within the authority envelope and does not create an external side effect.

## Dependency and time gates

A task is ready only when every dependency has fresh terminal evidence, its path lease is
available, and its `not-before` time has passed. Recheck time gates on wake; do not busy-wait or
claim that a scheduled external event occurred without observing it.

## Project memory

Read repository instructions and local project memory before decomposing work. Record only
sanitized decisions, durable conventions, blocker fingerprints, and evidence locations in the
private JD ledger. Write to repository or external memory only when explicitly authorized.
Memory is advisory: verify drift-prone facts against current code, configuration, and provider
state before acting.

## Background limitation

JD has no daemon or guaranteed watcher. If the host cannot persist a goal or wake the task, state
that supervision ends with the session, save a checkpoint, and make the next resume action
deterministic. Do not promise unattended monitoring, AFK escalation, or scheduled delivery.

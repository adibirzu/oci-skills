# Durable Reconciliation and Worker Recovery

## Reconcile

At each start, wake, compaction recovery, and terminal check, compare the redacted ledger with:

- live child-agent states and last progress timestamps;
- leased paths, worktrees, branches, and repository diffs;
- focused test results and their source revision;
- active capability grants and expiry;
- unresolved `USER_INPUT_REQUIRED` and `CAPABILITY_REQUEST` packets.

Never infer success from an absent agent or quiet terminal. Mark evidence stale when the source
revision changed. Requeue ready work that never started. Preserve unrelated user changes.

## Recovery ladder

Use at most one pass through each stage per attempt and emit a `RECOVERY` packet:

1. **Inspect** the worker state, last result, diff, test evidence, and blocker fingerprint.
2. **Steer** once with one corrective instruction; this steer is appropriate when the brief already answers the question or
   the worker is looping. Do not expand scope.
3. **Relaunch** a genuinely wedged worker with the original brief plus a redacted `progress so far`
   note. Preserve its isolated worktree or leased changes.
4. **Fail** after two relaunch failures or the global three-attempt budget, recording evidence and
   escalating one consolidated question to the user when no safe alternative remains.

Low remaining context is not itself a failure; compact and continue. A repeated blocker without
new evidence is a stall. Do not repeatedly send the same instruction.

## Durable state

Prefer `${CODEX_HOME:-$HOME/.codex}/state/jd/<goal-id>` with directory mode `0700` and file mode
`0600`. Use an opaque goal id. Store only redacted summaries and digests—never credentials, raw
prompts, private data, source bodies, internal topology, or full tool output. If durable state is
not writable, use a private temporary directory and report that restart recovery is degraded.

`$jd status` is read-mostly: it may write one private redacted report but must not dispatch,
terminate, merge, approve, consume grants, or mutate task state.

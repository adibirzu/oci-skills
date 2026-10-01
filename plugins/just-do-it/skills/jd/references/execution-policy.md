# JD execution and cost policy

Read this when routing work, dispatching an agent, reusing a review, or handling a
budget limit. The entry skill selects the workflow path.

## Choose the smallest path

**Bounded:** one clear local outcome, known or quickly discoverable file
boundaries, focused verification, and no sensitive trust-boundary or release
change. Use one task packet. Preserve any repository-required handoff or ledger;
do not generate a multi-PRD program merely to satisfy JD formatting.

**Program:** multiple dependent outcomes, unknown architecture, migration,
cross-project ownership, or release-sensitive work. Use the program workflow
and evidence-backed PRDs. A program may still contain bounded tasks; route each
at the lowest capable tier.

Unclear scope can start with one read-only Luna scout. Escalate to the Terra
planner only when the scout identifies an architectural or dependency decision
it cannot settle with repository evidence. The coordinator can do trivial
discovery without a subagent.

## Dispatch and escalation

Default bounded path: coordinator discovery when cheap, one Luna implementer
for tests and code, and one independent Sol reviewer when review is required.
The implementer records the RED command and expected failure before coding,
then GREEN and focused checks. A separate Luna test-worker is optional when
independent contract authorship materially improves the task. Split work only
for real file independence, not to fill roles.

Use Terra for demonstrated cross-module integration or program planning. Use
Sol for independent correctness review and a separate Sol security reviewer for
sensitive trust boundaries. A user's explicit model request takes precedence.
Never silently substitute a more expensive model for a missing role. A missing
cheap role calls for coordinator work, a compatible lower-cost route, or a
recorded escalation reason; it is not itself an escalation reason.

Send agents compact self-contained packets with objective, file lease,
constraints, test command, and output schema. Use no inherited conversation
history when the packet supplies all needed context. Add recent turns only
when necessary for correctness. Never send credentials or raw private state.

Before dispatch, set a ceiling for agent calls and task attempts. Bounded
default: at most three initial dispatches (optional scout, implementer,
reviewer) and two repair dispatches. Program default: seven PRDs, four
concurrent writable workers, three attempts per task, and two review cycles
per PRD. Reserve required review capacity before implementation. Stop and
report a budget hold when the ceiling is exhausted; do not skip a required
review or silently upgrade models to finish. Honor any user-specified budget.

Record requested model, actual model and its evidence source, reasoning effort,
and input/cached/output tokens or cost only when reported by the runtime.
Write `unavailable` otherwise. A configured role or prompt is not evidence of
the model that actually ran. Monetary spend requires current pricing and
metered usage; absent either, use dispatch/attempt ceilings and report spend
as unavailable. State why each Terra, Astra, or other stronger-model escalation
was needed. Do not infer billing from static role templates.

## Review reuse

For low-risk bounded work, request one independent correctness review after
GREEN. Reuse that review at closure when the reviewed diff identity and
verification evidence remain current. A change to reviewed code, tests,
dependencies, or relevant configuration invalidates reuse. For programs,
review sensitive or release-sensitive PRDs at their boundary and review the
aggregate result at closure; consolidate low-risk PRDs when their combined
diff is reviewable. An implementer never approves its own high-risk or release
work. Missing reviewer capability is reported as a review hold, not as a pass.

All paths preserve the authority envelope, sandbox proof, scoped ownership,
independent high-risk review, and truthful evidence classes. Cost controls
cannot authorize skipped security gates or external mutations.

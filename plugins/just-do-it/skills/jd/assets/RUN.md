# Autonomous delivery run: <goal>

## Authority envelope

- Original goal: <verbatim user outcome>
- Repository scope: <paths>
- Authorized mutations: <local changes only unless explicitly broader>
- Not authorized: <commit/push/deploy/destructive/external actions unless stated>
- Required evidence: <tests, coverage, security, docs>
- Workflow path: <bounded | program; reason>
- Dispatch ceiling: <initial and repair calls; user budget if any>
- Dispatches consumed/reserved: <counts, including required review reserve>
- Execution budgets: <bounded or program limits from execution-policy.md>
- Data policy: digests and redacted summaries only; no credentials/private content/topology
- Execution mode: <strict | supervised | transparent shared-workspace | break-glass>
- Delivery mode: <local-only | change-request | landed>
- Event cursor/checkpoint: <sequence / UTC / digest>

## Assumptions

- <safe reversible assumption and evidence>

## PRD queue

| PRD | Outcome | Dependencies | Status | Review |
|---|---|---|---|---|
| <ID> | <outcome> | <IDs> | pending | pending |

## Ready tasks

| Task | Owner | Path lease | Attempt | RED | GREEN | Status |
|---|---|---|---|---|---|---|
| <ID> | <role> | <canonical paths> | 0/3 | pending | pending | ready |

## Decisions and user answers

- <sequence>: <redacted decision summary or digest, authority source, impact>

## Decision holds

| Hold | Owner | Affected tasks | Options/impact | Status |
|---|---|---|---|---|
| <ID> | <user/coordinator> | <IDs> | <redacted summary> | open |

## Dependency and time gates

| Task | Dependencies | Not before | Fresh evidence | State |
|---|---|---|---|---|
| <ID> | <IDs> | <UTC or none> | <digest/time> | blocked/ready |

## Event checkpoint

| Sequence | UTC | Task | Event | Evidence digest |
|---|---|---|---|---|
| <n> | <time> | <ID> | <type> | <digest> |

## Verification ledger

- <task/PRD>: <command> — <result>

## Open blockers

- none

## Model and sandbox evidence

- <task>: requested <role/model/effort>; actual <role/model/effort or unavailable>;
  actual-model source <runtime receipt or unavailable>; sandbox/tool class;
  input/cached/output tokens <reported values or unavailable>; cost <metered
  amount/source or unavailable>; escalation reason <reason or none>
- Cost ceiling: <user-provided limit or dispatch ceiling>; cost remaining:
  <metered value or unavailable>
- Review identity: <reviewed diff digest, verification receipt, timestamp;
  invalidated if relevant changes occur>

## Final evidence

- Coverage: pending
- Security: pending
- Independent Sol review: pending or current reviewed diff digest
- Delivery state: local changes only
- Landed verification: not authorized

# Autonomous delivery run: <goal>

## Authority envelope

- Original goal: <verbatim user outcome>
- Repository scope: <paths>
- Authorized mutations: <local changes only unless explicitly broader>
- Not authorized: <commit/push/deploy/destructive/external actions unless stated>
- Required evidence: <tests, coverage, security, docs>
- Execution budgets: 7 PRDs; 4 writable workers; 3 attempts/task; 2 reviews/PRD
- Data policy: digests and redacted summaries only; no credentials/private content/topology
- Execution mode: <strict | supervised | break-glass>
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

- <task>: <actual role/model/sandbox/tool class or fallback blocker>

## Final evidence

- Coverage: pending
- Security: pending
- Aggregate Sol review: pending
- Delivery state: local changes only
- Landed verification: not authorized

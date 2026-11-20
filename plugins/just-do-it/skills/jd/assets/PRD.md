# <PRD-ID>: <Outcome title>

**Status:** Draft
**Depends on:** <IDs or none>

## User journey

As a <role>, I want <capability>, so that <measurable benefit>.

## Scope

- <included behavior>

## Non-goals

- <explicitly excluded behavior>

## Acceptance criteria

1. <observable criterion>
2. <failure/boundary criterion>
3. <compatibility or security criterion>

## Trust boundaries and rollback

- Inputs and authorization: <boundary>
- Sensitive data and egress: <boundary>
- Rollback or disable path: <path>

## Test obligations

- Unit: <tests>
- Integration: <tests>
- E2E: <critical journey or justified not applicable>
- Coverage: project threshold or documented available evidence

## Tasks

| ID | Task | Owner role | Depends on | Files | Verification | Status |
|---|---|---|---|---|---|---|
| <ID>-01 | Write RED contract and implement GREEN | one implementation-worker | none | <paths> | <command> | pending |
| <ID>-02 | Independent test authorship when useful | test-worker | <ID>-01 | <paths> | <command> | optional |
| <ID>-03 | Independent review when required | sol-reviewer | <ID>-01 | read-only | review packet or coordinator local verification | pending |
| <ID>-04 | Security review when sensitive | sol-security-reviewer | <ID>-03 | read-only | security evidence | pending |

Select review tasks and verification under the [review policy](../references/program-workflow.md#5-review-proportionately).

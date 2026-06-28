# OCI Skills v2 delivery plan

This is the repo-native traceability ledger. Merged history before v2 is the delivered baseline. New work maps to the PRD; no retroactive tasks are invented.

## Requirement traceability

| Requirement | Tasks | Verification |
|---|---|---|
| REQ-01 | V2-01, V2-09 | skill validator, routing/eval parity |
| REQ-02 | V2-03 | Terraform unit/shell/fixture tests |
| REQ-03 | V2-02, V2-04 | action and CLI-lint tests |
| REQ-04 | V2-02, V2-03, V2-13 | receipt/approval/plan/security tests |
| REQ-05 | V2-05, V2-06, V2-07 | five golden-path fixtures and evals |
| REQ-06 | V2-05, V2-06 | developer-services and Queue coverage |
| REQ-07 | V2-08 | mocked project lifecycle smoke |
| REQ-08 | V2-10, V2-12 | doc/install/manifest parity |
| REQ-09 | V2-11, V2-12, V2-13 | coverage, security, redaction, forward eval |

## Task cards

| Task | Requirements | Depends on | Status | PR |
|---|---|---|---|---|
| V2-01 PRD, ownership, architecture | all | — | Implemented locally | not opened |
| V2-02 risk-aware safety core | REQ-03, REQ-04 | V2-01 | Implemented + tested | not opened |
| V2-03 Terraform authoring engine | REQ-02, REQ-04 | V2-02 | Implemented + tested | not opened |
| V2-04 exact OCI CLI authoring | REQ-03 | V2-02 | Implemented + tested | not opened |
| V2-05 Developer Services | REQ-05, REQ-06 | V2-03, V2-04 | Implemented | not opened |
| V2-06 Queue/event worker | REQ-05, REQ-06 | V2-02, V2-04 | Implemented | not opened |
| V2-07 product orchestrator | REQ-05 | V2-03, V2-05, V2-06 | Implemented + fixtures | not opened |
| V2-08 project lifecycle integration | REQ-07 | V2-07 | Implemented + smoke | not opened |
| V2-09 skill/routing conformance | REQ-01 | V2-08 | Implemented + validator | not opened |
| V2-10 README/architecture/diagrams | REQ-08 | V2-09 | Implemented | not opened |
| V2-11 test/coverage/forward eval | REQ-09 | V2-09 | Automated gates implemented; independent fresh-agent run pending | not opened |
| V2-12 packaging/release | REQ-08, REQ-09 | V2-10, V2-11 | `v2.0.0-rc.1` prepared; final promotion deferred to forward-eval gate | not opened |
| V2-13 final security/architecture review | REQ-04, REQ-09 | V2-12 | Local review/gates implemented; fresh-agent evidence remains release blocker | not opened |

## Deferred release evidence

The implementation intentionally stops at release-candidate metadata. A maintainer must run raw prompts through fresh, isolated agent sessions and record at least 90% success with zero safety violations before tagging or publishing `v2.0.0`. This is a release-evidence deferral, not missing product code.

## Medium/low follow-ups

| Finding | Severity | Owner | Action |
|---|---|---|---|
| Golden-path component locals require domain-specific HCL materialization for each customer design. | Medium | product + owning domain | Resolve provider fields from the selected provider schema during bundle authoring. |
| Live Resource Manager and local Terraform end-to-end tests are mocked in CI. | Low | release owner | Run only in a dedicated, disposable non-production tenancy. |

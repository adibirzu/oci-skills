# REQ-24 — User-journey registry

## User journey

As a product reviewer, I want each requirement expressed as an actor, goal, outcome, and acceptance-test binding so behavior can be evaluated without retaining raw prompts.

## Product requirement

Publish sanitized user journeys for REQ-23 through REQ-52 with unique IDs and repository-local acceptance-test paths.

## Acceptance criteria

- Exactly one journey covers each requirement in this tranche.
- IDs are unique and actor, goal, outcome, and tests are non-empty.
- Raw prompts and provider content are excluded.

## Architecture impact

Introduces a product-intent layer between narrative PRDs and executable tests.

## Associated tasks

- PROD-24: add the journey registry and validate requirement/test coverage.

## Verification

Run the operational-contract acceptance suite and inspect the metadata-only validator report.

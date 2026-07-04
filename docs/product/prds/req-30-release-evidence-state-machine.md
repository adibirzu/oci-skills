# REQ-30 — Release-evidence state machine

## User journey

As a release owner, I want readiness transitions constrained by evidence so local validation cannot self-promote a release.

## Product requirement

Define draft, contract-valid, local-validated, external-evidence-pending, and release-ready states with forward-only transitions. Final readiness requires independent forward evidence, the minimum pass rate, zero safety violations, and independent review.

## Acceptance criteria

- Initial and terminal states are unique and known.
- Transitions reference known states and have no self edges.
- Validation describes but never performs transitions.

## Architecture impact

Replaces an implicit readiness boolean with an explicit evidence-state model.

## Associated tasks

- PROD-30: publish the state machine and validate terminal evidence invariants.

## Verification

Run state-machine negative tests and the forward-eval definition validator.

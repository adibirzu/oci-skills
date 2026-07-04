# REQ-22 — Compatibility and deprecation

## User journey

As an existing user, I want stable named contexts, risk values, bundle schema,
skill names, and ownership rules so that additive v2 updates do not silently
break automation.

## Product requirement

Publish a compatibility contract that records stable surfaces, deprecations,
major-version removal policy, and single-owner infrastructure semantics.

## Acceptance criteria

- Named contexts and the four mutation risks remain stable.
- `run_mutating` remains an additive compatibility alias for `run_action`.
- Removal is major-version-only.
- Terraform remains the durable-resource owner and dual ownership is forbidden.

## Architecture impact

Documents the compatibility and distribution plane without extending legacy
`commands/` or adding a second mutation path.

## Associated tasks

- PROD-22A: publish `compatibility-contract.json`.
- PROD-22B: validate replacement and ownership invariants.
- PROD-22C: synchronize README, quickstart, architecture, and release notes.

## Verification

`tests/test_product_roadmap_contracts.py` and existing action-guard tests.

# REQ-32 — Migration readiness

## User journey

As an upgrade owner, I want stable surfaces, deprecations, removal timing, and evidence checks in one contract so major-version migration risk is explicit.

## Product requirement

Preserve v2 stable surfaces, keep `run_mutating` as an additive alias for `run_action`, forbid removal before major version 3, and declare owned readiness evidence.

## Acceptance criteria

- Breaking changes are major-release-only.
- Deprecation data agrees with the compatibility contract.
- Readiness checks have unique IDs, owners, and evidence types.

## Architecture impact

Connects compatibility policy, distribution consumers, and release transitions into a migration plane.

## Associated tasks

- PROD-32: add migration readiness data, parity validation, and upgrade documentation.

## Verification

Run compatibility, operational-contract, clean-install, and forward-eval tests.

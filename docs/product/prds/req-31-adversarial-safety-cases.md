# REQ-31 — Adversarial safety cases

## User journey

As a security reviewer, I want every fixed refusal or block prefix assigned to an owner and executable test so safety behavior cannot silently drift.

## Product requirement

Catalog the eight canonical secret, CLI-help, context, preflight, destructive, Terraform-plan, ownership, and dotenv cases with unique IDs, exact prefixes, owners, and test evidence.

## Acceptance criteria

- All eight fixed prefixes are present exactly once.
- Every case has a non-empty owner and existing test path.
- Safety-case data contains no command payloads, secrets, or topology.

## Architecture impact

Adds a machine-readable abuse-case boundary to the safety architecture and release state machine.

## Associated tasks

- PROD-31: create the safety catalog, validate exact prefixes, and bind tests.

## Verification

Run operational-contract, action-guard, destructive-guard, CLI-lint, and Terraform-plan tests.

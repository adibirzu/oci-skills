# REQ-41 — Release attestation

## User journey

As an independent reviewer, I want to attest the exact evidence used for promotion, so that hashes are signed without embedding raw content.

## Product requirement

Require external attestation over contract, install, and forward-evidence hashes; forbid self-attestation and raw content.

## Acceptance criteria

- The contract is schema-versioned, deterministic, and validated offline.
- Unsafe or incomplete data fails closed.
- Owners, evidence, and executable tests are explicit.

## Architecture impact

Extends independent release evidence boundary.

## Associated tasks

- PROD-41: implement the contract, validator semantics, traceability, and regression tests.

## Verification

Run `pytest -q tests/test_product_resilience_contracts.py` and `python3 scripts/product_contracts.py validate`.

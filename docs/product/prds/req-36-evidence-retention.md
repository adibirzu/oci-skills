# REQ-36 — Evidence retention

## User journey

As a security reviewer, I want to understand what evidence may persist, so that secrets and raw provider content never enter committed evidence.

## Product requirement

Commit metadata only, keep raw provider content ephemeral, never retain secrets, and verify deletion.

## Acceptance criteria

- The contract is schema-versioned, deterministic, and validated offline.
- Unsafe or incomplete data fails closed.
- Owners, evidence, and executable tests are explicit.

## Architecture impact

Extends evidence boundaries and release storage.

## Associated tasks

- PROD-36: implement the contract, validator semantics, traceability, and regression tests.

## Verification

Run `pytest -q tests/test_product_resilience_contracts.py` and `python3 scripts/product_contracts.py validate`.

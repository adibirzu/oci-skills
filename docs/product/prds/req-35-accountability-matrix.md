# REQ-35 — Accountability matrix

## User journey

As a reviewer, I want to find the accountable and responsible owners for each governance surface, so that ownerless changes are blocked.

## Product requirement

Assign accountable and responsible roles for contracts, security, distribution, release, and documentation.

## Acceptance criteria

- The contract is schema-versioned, deterministic, and validated offline.
- Unsafe or incomplete data fails closed.
- Owners, evidence, and executable tests are explicit.

## Architecture impact

Extends ownership edges across governance planes.

## Associated tasks

- PROD-35: implement the contract, validator semantics, traceability, and regression tests.

## Verification

Run `pytest -q tests/test_product_resilience_contracts.py` and `python3 scripts/product_contracts.py validate`.

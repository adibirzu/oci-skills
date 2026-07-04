# REQ-33 — Change classification

## User journey

As a maintainer, I want to classify a product-contract change before merging, so that breaking changes cannot ship as patch or minor updates.

## Product requirement

Classify changes as editorial, additive, or breaking; unknown changes fail closed as breaking.

## Acceptance criteria

- The contract is schema-versioned, deterministic, and validated offline.
- Unsafe or incomplete data fails closed.
- Owners, evidence, and executable tests are explicit.

## Architecture impact

Extends change classification and compatibility gates.

## Associated tasks

- PROD-33: implement the contract, validator semantics, traceability, and regression tests.

## Verification

Run `pytest -q tests/test_product_resilience_contracts.py` and `python3 scripts/product_contracts.py validate`.

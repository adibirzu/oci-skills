# REQ-40 — Documentation freshness

## User journey

As a documentation owner, I want to identify stale or unsupported claims, so that broken links and unverified volatile claims block release.

## Product requirement

Use the Oracle docs index as authority, reject unverified claims, and require review when contracts change.

## Acceptance criteria

- The contract is schema-versioned, deterministic, and validated offline.
- Unsafe or incomplete data fails closed.
- Owners, evidence, and executable tests are explicit.

## Architecture impact

Extends documentation provenance and release checks.

## Associated tasks

- PROD-40: implement the contract, validator semantics, traceability, and regression tests.

## Verification

Run `pytest -q tests/test_product_resilience_contracts.py` and `python3 scripts/product_contracts.py validate`.

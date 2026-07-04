# REQ-42 — Maintenance policy

## User journey

As a maintainer, I want to apply consistent lifecycle rules, so that critical, breaking, or ownerless changes fail safely.

## Product requirement

Block critical security findings, restrict breaking changes to major releases, reject stale ownership, and keep live OCI out of CI.

## Acceptance criteria

- The contract is schema-versioned, deterministic, and validated offline.
- Unsafe or incomplete data fails closed.
- Owners, evidence, and executable tests are explicit.

## Architecture impact

Extends long-term governance and maintenance.

## Associated tasks

- PROD-42: implement the contract, validator semantics, traceability, and regression tests.

## Verification

Run `pytest -q tests/test_product_resilience_contracts.py` and `python3 scripts/product_contracts.py validate`.

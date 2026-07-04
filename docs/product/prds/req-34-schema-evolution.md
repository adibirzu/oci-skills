# REQ-34 — Schema evolution

## User journey

As a contract consumer, I want to know whether a schema version is supported, so that unknown or breaking schema changes cannot silently load.

## Product requirement

Require backward compatibility within a major version, reject unknown versions, and require migration for breaking changes.

## Acceptance criteria

- The contract is schema-versioned, deterministic, and validated offline.
- Unsafe or incomplete data fails closed.
- Owners, evidence, and executable tests are explicit.

## Architecture impact

Extends versioned contract loading and migration.

## Associated tasks

- PROD-34: implement the contract, validator semantics, traceability, and regression tests.

## Verification

Run `pytest -q tests/test_product_resilience_contracts.py` and `python3 scripts/product_contracts.py validate`.

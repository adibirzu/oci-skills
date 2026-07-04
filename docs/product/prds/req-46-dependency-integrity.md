# REQ-46 — Dependency integrity

## User journey

As a maintainer, I want dependency integrity controls so that reliability changes fail safely.

## Product requirement

Define a versioned, offline, fail-closed dependency integrity contract with explicit ownership and evidence.

## Acceptance criteria

- Unsafe or incomplete values are rejected.
- Validation is deterministic and contacts no network or OCI tenancy.
- The contract is traceable to tests and architecture.

## Architecture impact

Extends the reliability-control plane.

## Associated tasks

- PROD-46: implement contract data, validation, traceability, and tests.

## Verification

Run `pytest -q tests/test_product_reliability_contracts.py` and the product-contract validator.

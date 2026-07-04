# REQ-52 — End-of-life policy

## User journey

As a maintainer, I want end-of-life policy controls so that reliability changes fail safely.

## Product requirement

Define a versioned, offline, fail-closed end-of-life policy contract with explicit ownership and evidence.

## Acceptance criteria

- Unsafe or incomplete values are rejected.
- Validation is deterministic and contacts no network or OCI tenancy.
- The contract is traceable to tests and architecture.

## Architecture impact

Extends the reliability-control plane.

## Associated tasks

- PROD-52: implement contract data, validation, traceability, and tests.

## Verification

Run `pytest -q tests/test_product_reliability_contracts.py` and the product-contract validator.

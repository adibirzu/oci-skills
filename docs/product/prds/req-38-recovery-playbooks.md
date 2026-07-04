# REQ-38 — Recovery playbooks

## User journey

As a release operator, I want to recover safely from a failed product gate, so that failure is contained before repair and verification.

## Product requirement

Provide detection, containment, recovery, verification, and test evidence for contract, install, evaluation, and redaction failures.

## Acceptance criteria

- The contract is schema-versioned, deterministic, and validated offline.
- Unsafe or incomplete data fails closed.
- Owners, evidence, and executable tests are explicit.

## Architecture impact

Extends failure recovery through the release plane.

## Associated tasks

- PROD-38: implement the contract, validator semantics, traceability, and regression tests.

## Verification

Run `pytest -q tests/test_product_resilience_contracts.py` and `python3 scripts/product_contracts.py validate`.

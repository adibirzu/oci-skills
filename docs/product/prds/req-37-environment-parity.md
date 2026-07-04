# REQ-37 — Environment parity

## User journey

As a harness maintainer, I want to verify behavior across supported harnesses, so that skills, contracts, safety, and routing stay aligned.

## Product requirement

Declare parity invariants for Claude, Codex, Gemini, and Antigravity without requiring live OCI.

## Acceptance criteria

- The contract is schema-versioned, deterministic, and validated offline.
- Unsafe or incomplete data fails closed.
- Owners, evidence, and executable tests are explicit.

## Architecture impact

Extends distribution and clean-install verification.

## Associated tasks

- PROD-37: implement the contract, validator semantics, traceability, and regression tests.

## Verification

Run `pytest -q tests/test_product_resilience_contracts.py` and `python3 scripts/product_contracts.py validate`.

# REQ-23 — Contract schema enforcement

## User journey

As a contract maintainer, I want every product contract checked against a declared shape so malformed governance data fails before packaging.

## Product requirement

Maintain an offline, versioned registry of required keys for every contract. Validation must reject missing contracts, unsupported schema versions, undeclared contracts, and missing required keys without executing contract content.

## Acceptance criteria

- The registry covers every contract except itself.
- Every registered contract uses schema version 1 and declares required keys.
- Validation is deterministic, path-safe, and fail-closed.

## Architecture impact

Adds a schema-registry layer ahead of cross-contract semantic validation in the product contract plane.

## Associated tasks

- PROD-23: create the registry, extend validation, add malformed-shape tests, and include it in installs.

## Verification

Run `pytest -q tests/test_product_operational_contracts.py` and `python3 scripts/product_contracts.py validate`.

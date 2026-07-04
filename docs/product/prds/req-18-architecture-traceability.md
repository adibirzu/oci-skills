# REQ-18 — Executable architecture traceability

## User journey

As an architect, I want every requirement linked to components, tests, and
documentation so that a roadmap item cannot be marked complete by prose alone.

## Product requirement

Publish and validate an architecture traceability contract for REQ-13 through
REQ-22 and expose it through the offline product-contract validator.

## Acceptance criteria

- Every requirement maps to at least one component, test, and document.
- Every referenced path exists and remains within the repository.
- The main PRD and delivery plan mention all requirements.
- Validation output is deterministic and text-only.

## Architecture impact

Adds a contract-validation component and four documented architecture planes.

## Associated tasks

- PROD-18A: publish `architecture-traceability.json`.
- PROD-18B: implement `scripts/product_contracts.py`.
- PROD-18C: wire validation into CI.

## Verification

`tests/test_product_roadmap_contracts.py` and CI contract validation.

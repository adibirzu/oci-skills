# REQ-17 — Standard evidence envelope

## User journey

As an operator or reviewer, I want findings, evidence, action ownership,
verification, and rollback in one stable shape so that safety decisions are not
lost in prose.

## Product requirement

Define a versioned evidence envelope that represents risk and action status but
cannot contain secret values.

## Acceptance criteria

- Finding, evidence, action, verification, and rollback are required.
- Risk uses only none/additive/in-place/destructive/credential.
- Verification and rollback cannot be empty.
- `secret_values` must always be an empty array.

## Architecture impact

Adds a common evidence contract downstream of all skills without forcing a new
execution surface.

## Associated tasks

- PROD-17A: publish `schemas/evidence-envelope.schema.json`.
- PROD-17B: document its relation to skill Expected output sections.
- PROD-17C: enforce secret-free schema invariants.

## Verification

`tests/test_product_roadmap_contracts.py` and redaction tests.

# REQ-15 — Authoritative capability catalog

## User journey

As a router or harness maintainer, I want one machine-readable catalog of every
skill, owner, and direct reference so that inventory drift is detected before a
release.

## Product requirement

Publish `docs/product/contracts/capability-catalog.json` and validate it against
the canonical `skills/*/SKILL.md` inventory.

## Acceptance criteria

- Every installed skill appears exactly once.
- Every entry has an owner and existing direct reference.
- Extra, missing, or duplicate skills fail validation.
- The catalog is copied to every supported harness bundle.

## Architecture impact

Adds a product contract plane above routing documentation; skills remain the
canonical workflow surface.

## Associated tasks

- PROD-15A: publish the capability catalog.
- PROD-15B: validate inventory/reference parity.
- PROD-15C: expose catalog counts in the readiness report.

## Verification

`tests/test_product_roadmap_contracts.py` and clean-install tests.

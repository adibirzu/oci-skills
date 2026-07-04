# REQ-27 — Source provenance

## User journey

As a documentation reviewer, I want each requirement tied to a local source of truth or official Oracle documentation so unsupported claims are visible.

## Product requirement

Record provenance for REQ-23 through REQ-52. Repository sources must resolve to regular in-repository files; external sources must use HTTPS on `docs.oracle.com`.

## Acceptance criteria

- Every new requirement has one provenance record.
- Authority values are closed and explicit.
- Local paths cannot escape the repository or traverse symlinks.

## Architecture impact

Extends the documentation plane with an offline provenance boundary.

## Associated tasks

- PROD-27: add provenance records and validate authority/path rules.

## Verification

Run product-contract validation and documentation-link checks.

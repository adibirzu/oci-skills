# REQ-13 — Application workflow evidence

## User journey

As an application engineer, I want a sanitized record of classification, reuse,
tests, review, and verification so that another reviewer can trust the workflow
without receiving source patches, prompts, provider responses, or secrets.

## Product requirement

Define a versioned application-workflow schema and require
`oci-application-engineering` to produce metadata-only evidence with
`raw_content=false`.

## Acceptance criteria

- Classification, tests, independent review, and verification are required.
- Reuse decisions record candidate, accept/reject outcome, and reason.
- Raw content cannot be represented as retained.
- Restricted work remains local unless separately approved.

## Architecture impact

Adds the application workflow evidence plane and
`schemas/application-workflow.schema.json` without changing OCI ownership.

## Associated tasks

- PROD-13A: publish the schema.
- PROD-13B: document the evidence boundary in the application skill/reference.
- PROD-13C: validate the schema contract in CI.

## Verification

`tests/test_product_roadmap_contracts.py` and `tests/test_workflow_eval.py`.

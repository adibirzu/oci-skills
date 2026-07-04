# REQ-14 — Deterministic workflow evaluation

## User journey

As a release evaluator, I want a bounded offline evaluation plan and aggregate
report so that model comparisons cannot silently invoke providers, exceed a
reviewed cost cap, or persist raw content.

## Product requirement

Complete and maintain `scripts/workflow_eval.py` as a deterministic,
permission-safe preparation and aggregation tool. Provider execution remains an
external opt-in boundary.

## Acceptance criteria

- Corpus, plan, result, and report files are non-symlink and permission checked.
- Candidates are deduplicated and capped.
- Execution requires explicit opt-in and cost-cap agreement.
- Reports retain hashes and aggregates only and remain advisory for small samples.

## Architecture impact

Adds an offline evaluation lane beside the application workflow; it does not
become an OCI deployment or required model gateway.

## Associated tasks

- PROD-14A: refactor the evaluator into tested functions.
- PROD-14B: cover invalid corpus, permissions, caps, and report behavior.
- PROD-14C: keep the optional external runner outside the repository boundary.

## Verification

`tests/test_workflow_eval.py`, Ruff, and the source-scoped coverage gate.

# REQ-21 — Honest release readiness

## User journey

As a release owner, I want a deterministic local readiness report that clearly
separates passed local gates from pending independent evidence so that the tool
cannot self-certify a final release.

## Product requirement

Define local gates and the external fresh-agent evidence boundary in a versioned
release contract; generate a metadata-only report without running gates.

## Acceptance criteria

- Local test, coverage, routing, contract, and forward-definition gates are listed.
- Independent pass rate is at least 90% with zero safety violations.
- Self-certification is explicitly forbidden.
- Pending external evidence keeps the report non-final.

## Architecture impact

Adds a release readiness plane above existing forward-eval evidence; the report
observes definitions and never executes or certifies external runs.

## Associated tasks

- PROD-21A: publish `release-gates.json`.
- PROD-21B: add a deterministic `product_contracts.py report` command.
- PROD-21C: preserve the blinded forward-eval boundary.

## Verification

`tests/test_product_roadmap_contracts.py` and `tests/test_forward_eval.py`.

# REQ-16 — Routing precedence as data

## User journey

As a user with an overlapping OCI request, I want deterministic ownership so
that generic keywords do not route Bastion, Database Cloud, landing-zone,
application, or platform-composition work to the wrong domain.

## Product requirement

Publish positive and negative ownership pairs for every cross-domain precedence
rule and keep them aligned with router text and routing evals.

## Acceptance criteria

- At least six overlap families have positive and negative owners.
- Every owner resolves to a catalog skill or an explicit owning-domain marker.
- Eval prompts cover both sides of new precedence rules.
- The routing validator finishes with no failures.

## Architecture impact

Makes the router decision layer inspectable without replacing semantic routing
or the hard-handoff boundary.

## Associated tasks

- PROD-16A: publish `routing-precedence.json`.
- PROD-16B: retain positive/negative eval coverage.
- PROD-16C: validate owner names against the capability catalog.

## Verification

`tests/check_eval_routing.py` and `tests/test_routing_consistency.py`.

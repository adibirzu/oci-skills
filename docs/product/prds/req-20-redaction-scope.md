# REQ-20 — Complete redaction scope

## User journey

As a security reviewer, I want redaction to cover tracked, staged, newly created,
and generated evidence so that untracked task files cannot bypass release checks.

## Product requirement

Declare the required scan surfaces, sensitive-data classes, placeholder policy,
and block-on-failure behavior in a versioned redaction contract.

## Acceptance criteria

- OCI identifiers, topology, fingerprints, namespaces, secrets, and personal path identifiers are covered.
- Newly created task files are scanned before handoff.
- Provider/model raw content remains local-only.
- A redaction failure blocks release evidence.

## Architecture impact

Extends the safety architecture's evidence boundary; it does not add a live OCI
inspection.

## Associated tasks

- PROD-20A: publish `redaction-contract.json`.
- PROD-20B: include new-task files in handoff checks.
- PROD-20C: keep strict redaction tests and release documentation aligned.

## Verification

`tests/test_redact.py` plus task-file redaction checks.

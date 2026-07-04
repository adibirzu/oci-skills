# REQ-19 — Distribution reproducibility

## User journey

As a harness maintainer, I want the same canonical payload and exclusions in
Claude, Codex, Gemini, and Antigravity installs so that behavior does not depend
on the selected client.

## Product requirement

Declare harness adapters, install targets, required payload directories, and
forbidden generated/sensitive artifacts in a versioned distribution contract.

## Acceptance criteria

- Four supported harnesses have real adapters and install targets.
- Skills, references, scripts, schemas, docs, and evals are required payload.
- Runtime/provider binaries, state, plans, tfvars, caches, and bytecode are excluded.
- Clean and blinded install tests remain green.

## Architecture impact

Formalizes the compatibility and distribution plane around existing installers.

## Associated tasks

- PROD-19A: publish `distribution-contract.json`.
- PROD-19B: validate adapter paths.
- PROD-19C: retain clean/blinded install coverage.

## Verification

`tests/test_codex_install.py` and product-contract validation.

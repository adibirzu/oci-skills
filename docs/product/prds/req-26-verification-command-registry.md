# REQ-26 — Verification-command registry

## User journey

As a release operator, I want one declarative list of verification gates so commands are reviewable without allowing validation to execute them.

## Product requirement

Mirror required local gates into a shell-safe verification registry. Reject duplicates, optional gates, unsafe shell control syntax, unknown evidence types, and drift from the release-gates contract.

## Acceptance criteria

- Validation never executes a registered command.
- Gate IDs and commands match the release-gates contract.
- Commands contain no shell chaining, substitution, redirection, or newlines.

## Architecture impact

Separates gate declaration from gate execution and evidence collection.

## Associated tasks

- PROD-26: add the registry, safety validation, release-gate parity, and negative tests.

## Verification

Run the validator unsafe-command test and the repository release commands independently.

# REQ-28 — Change-impact mapping

## User journey

As a maintainer, I want to know which harnesses and lifecycle surfaces consume a requirement before changing it so distribution drift is caught early.

## Product requirement

Map each new requirement to supported consumers and existing artifacts. CI and documentation are mandatory consumers; affected harnesses and the installer must be explicit.

## Acceptance criteria

- REQ-23 through REQ-52 are covered exactly once.
- Consumers come from the supported closed set.
- Every artifact path resolves inside the repository.

## Architecture impact

Adds an impact edge set from requirements to distribution, CI, installer, and documentation consumers.

## Associated tasks

- PROD-28: publish the impact map and validate consumers and artifact paths.

## Verification

Run operational-contract and clean-install tests.

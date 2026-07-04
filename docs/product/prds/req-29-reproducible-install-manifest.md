# REQ-29 — Reproducible install manifest

## User journey

As a distribution maintainer, I want one deterministic payload and exclusion manifest so all harness bundles contain the same safe repository surfaces.

## Product requirement

Declare bytewise path ordering, path-and-content SHA-256 semantics, supported harnesses, canonical payload roots, sensitive-runtime exclusions, symlink policy, and blinded-evaluation exclusions.

## Acceptance criteria

- The manifest payload matches the installer and distribution contract.
- Terraform runtime/state, credentials, wallets, caches, and symlinks are excluded.
- All four harnesses remain clean-install compatible.

## Architecture impact

Creates a supply-chain contract between the canonical repository and installed copies.

## Associated tasks

- PROD-29: add the install manifest, parity validation, installed-bundle checks, and digest metadata.

## Verification

Run `pytest -q tests/test_codex_install.py tests/test_product_operational_contracts.py`.

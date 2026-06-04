# Contributing to oci-skills

Thanks for helping make OCI administration safer and more reusable.

## The one hard rule

**Never commit tenancy-specific or sensitive data.** This is a public repo.

Forbidden in any committed file:

- OCIDs (`ocid1.<type>.oc1...`)
- Public or private IP addresses
- API key fingerprints, auth tokens, install keys (`isk_...`), datakeys
- Private key blocks, wallets, passwords
- Tenancy namespaces or real region/profile names that fingerprint an account

Use `<PLACEHOLDER>` tokens instead (e.g. `<COMPARTMENT_OCID>`, `<VAULT_OCID>`,
`<APM_PRIVATE_DATAKEY>`) and resolve them at runtime from the environment.

## Before you push

```bash
# Mask check — must report "no sensitive values found" for every changed file
git diff --name-only | xargs -I{} python3 scripts/redact.py --check {}

# Secret scan (if installed)
gitleaks detect --config .gitleaks.toml --no-banner

# Shell + Python lint (if installed)
shellcheck scripts/*.sh
ruff check scripts/*.py
python3 -m py_compile scripts/*.py
```

CI runs the same checks on every PR.

## Conventions

- All CLI examples go through the `oci_cli` wrapper in `scripts/common.sh`.
- Mutating examples use `run_mutating` / `confirm`, or note dry-run.
- Show command shapes (read-before-write, idempotent), not live output.
- New operational fixes get a `KB-<n>` entry in `references/KB.md`.
- Keep references concise; one domain per file.

## Adding a plugin

1. Create `plugins/<name>/SKILL.md` with YAML frontmatter (`name`,
   `description`, `license`) and the Finding/Evidence/Action/Verification/KB
   output block.
2. Add `references/<name>.md` for the deep reference.
3. Reference the shared core via `../../scripts/` and `../../references/`.
4. Add trigger + behavior cases to `evals/evals.json`.

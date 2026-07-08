# Distribution and Role Templates

JD is a portable skill, but its preferred named Codex roles are runtime configuration rather than
skill metadata. Distributions include inert role templates under `assets/roles/`. Installing the
skill must not silently modify a user's global Codex configuration.

For the full model-tiered workflow, inspect the current state first:

```text
python3 scripts/install_codex_roles.py check
```

After the user explicitly approves a global Codex configuration change, install with:

```text
python3 scripts/install_codex_roles.py install
```

The installer is add-only on first install, preserves unrelated configuration, refuses symlinks
and unmanaged role/registration collisions, creates private backups, writes atomically, records
content hashes, and is idempotent. It updates only files that still match its previous managed
hashes. It never installs the role templates merely because the skill was discovered.

The approved installer performs these steps:

1. copy the role TOML files to `${CODEX_HOME:-$HOME/.codex}/agents/`;
2. merge the entries from `assets/roles/agents.toml` into the global `[agents]` table;
3. validate with `codex --strict-config doctor --summary`;
4. roll back the merge if strict validation fails;
5. restart Codex so role and skill discovery refreshes.

Without named roles, use only a fallback whose actual model, sandbox, tools, and independence can
be proven. Never auto-enable `jd-elevated-worker`; it is merely available for an exact confirmed
break-glass grant. Never copy secrets, local state, prompts, logs, or run ledgers into a plugin.

Release only when `assets/jd-release.json` records every gate as true: skill validation,
contract tests, strict-config parsing, security scan, forward test, and distribution parity.

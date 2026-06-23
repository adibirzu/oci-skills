# ADR-0001: Dual distribution — single-plugin repo (plugin + copy-install)

**Date**: 2026-06-05
**Status**: accepted
**Deciders**: Adrian Birzu, Claude

## Context

`oci-skills` originally shipped only as a **copy-install** bundle: `install.sh` copied a
root `SKILL.md` plus `references/`, `scripts/`, and `plugins/<name>/SKILL.md` into a
single skill directory per harness (Claude Code, Codex, Gemini, Antigravity). We wanted
it installable as a first-class **Claude Code plugin** (`/plugin marketplace add …`) and
listable in a marketplace — without dropping copy-install, breaking the multi-harness
adapters, or duplicating the router skill. Claude Code only auto-discovers skills at
`skills/<name>/SKILL.md`, which the old layout did not provide.

## Decision

Ship as a **single-plugin repo**: `.claude-plugin/{plugin.json,marketplace.json}` at the
repo root for Claude Code and `.codex-plugin/plugin.json` at the repo root for
Codex/ChatGPT import. Relocate skills to plugin-native `skills/<name>/SKILL.md`
for auto-discovery; add `commands/` and `hooks/` as the Claude Code
user-facing surface. Keep copy-install working by **synthesizing** the bundle-root `SKILL.md` from the
canonical router at install time (`sed 's#\.\./\.\./#./#g'`), so a single-skill harness
still finds a router whose links resolve at bundle-root depth.

## Alternatives Considered

### Alternative 1: Plugin-only (drop copy-install)
- **Pros**: one layout, simplest mental model.
- **Cons**: breaks the Codex/Gemini/Antigravity copy-install adapters and the one-line bootstrap.
- **Why not**: regresses existing, working distribution channels.

### Alternative 2: Commit a second router for the bundle root
- **Pros**: no install-time transform.
- **Cons**: two copies of the router drift apart.
- **Why not**: violates single-source-of-truth; synthesis is cheap and deterministic.

### Alternative 3: Multi-plugin nested marketplace (`plugins/<name>/.claude-plugin/`)
- **Pros**: each domain independently installable.
- **Cons**: heavy structure for one cohesive pack; four manifests to maintain.
- **Why not**: overkill — the four domains share one safety core and ship together.

### Alternative 4: Install each domain as a separate top-level skill
- **Pros**: every domain auto-triggers in copy-install too.
- **Cons**: isolated skill dirs break the shared `../../references` / `../../scripts` links.
- **Why not**: would force per-skill duplication of the shared core.

## Consequences

### Positive
- One source installs via both the plugin path and copy-install.
- One canonical router; domain-skill `../../` links stay valid after the `plugins/ → skills/` move (same depth).
- `git mv` preserved history (renames, not delete+add).
- Codex/ChatGPT import is explicit through `.codex-plugin/plugin.json` and
  advertises only real companion surfaces (`skills/` today, not hooks/apps/MCP).

### Negative
- The router exists at two effective depths; reconciled by the `install.sh` sed-synthesis step.
- CI validators that hardcoded `SKILL.md` / `plugins/*/SKILL.md` had to be repointed at `skills/*/SKILL.md`.

### Risks
- A future router link style other than `../../` would slip past the sed transform.
  Mitigation: keep router file-links `../../`-relative; the install-into-temp smoke test
  asserts the synthesized bundle's links resolve.

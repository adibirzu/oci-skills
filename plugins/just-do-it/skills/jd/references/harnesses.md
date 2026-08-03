# JD Harness Portability

JD has one behavior contract in `SKILL.md`. Harness adapters change discovery and invocation,
not safety, delivery authority, or completion evidence. `agy` means Google Antigravity.

## Supported layouts

| Harness | Workspace discovery | Invocation and notes |
|---|---|---|
| Antigravity / AGY | `.agents/skills/jd/` | Native Agent Skill; invoke by name or relevance. |
| Claude Code | `.claude/skills/jd/` or the JD plugin | Native skill; the plugin remains the preferred marketplace distribution. |
| Grok | `.grok/skills/jd/` or the Claude-compatible JD plugin | Native skill; Grok can read Claude plugins directly. |
| Pi | `.pi/skills/jd/` | Native Agent Skill; invoke with `/skill:jd` or by relevance. |
| Cline | `.cline/skills/jd/` | Native skill; enable Cline's Skills feature when required. |
| Cursor | `.cursor/skills/jd/` plus `.cursor/rules/jd.mdc` | The rule bridge tells Cursor Agent to load the bundled JD contract. |

Install into a repository without changing user-global configuration:

```text
python3 scripts/install_harness_adapters.py check --harness all --target-root <repo>
python3 scripts/install_harness_adapters.py install --harness all --target-root <repo>
```

The installer is add-only for unmanaged destinations. It updates only destinations carrying its
managed receipt, refuses symlinks and unrelated collisions, writes through a temporary sibling,
and never modifies credentials, model configuration, hooks, MCP servers, or global settings.

To add a clean reusable agent team after installing the skill, run
`scripts/create_agent_team.py install --harness <name|all> --target-root <repo>`. See
`references/agent-creation.md`. Skill discovery and agent creation are separate so users can
install JD without silently adding executable roles.

## Capability negotiation

At activation, inventory the current harness instead of assuming Codex role names exist:

1. Identify whether it supports isolated subagents, read-only roles, persistent/resumable state,
   worktrees, structured packets, and approval-gated external tools.
2. Map planner, test, implementer, integration, correctness-review, and security-review duties to
   proven native capabilities.
3. Preserve independence: an implementer cannot approve its own work. If no separate reviewer or
   clean review context exists, stop at `review-required` rather than claiming JD completion.
4. Serialize work when path leases or isolated worktrees cannot be enforced.
5. Store the redacted run ledger on disk when the harness lacks persistent goals. State clearly
   that the user must resume the session; do not promise background supervision.
6. Keep all external operations behind the same authority envelope and delivery modes.

Model brand names are preferences, not portable guarantees. Use the strongest available model
for planning/integration and an independently started strong model or clean context for review.
Use a cheaper capable model for bounded tests and implementation only when its sandbox and tool
controls are verifiable. Record actual assignments in the ledger.

## Harness-specific boundaries

- **Antigravity:** native asynchronous subagents may be used, but verify their tool permissions
  and prevent recursive delegation. Artifact reports are evidence only after repository checks.
- **Cursor:** the rule bridge is guidance, not a plugin runtime. Cursor non-interactive mode may
  have broad write access; do not use it for strict workers unless isolation is independently
  proven.
- **Claude Code:** marketplace discovery does not authorize hooks, MCP, shell commands, commits,
  pushes, or merges. Use the existing JD plugin manifest and skill payload.
- **Grok:** Claude compatibility does not import authority. Inspect discovered skills/plugins and
  use native permission controls before tools or subagents.
- **Pi:** extensions can alter tools and auto-commit behavior. Do not rely on unknown extensions;
  disable or audit them when strict execution is required.
- **Cline:** Skills may be experimental and command permissions vary by client. Treat Plan/Act,
  hooks, and task history as harness features, not evidence of isolation or completion.

If a harness cannot prove a JD control, degrade the affected operation, not the claim: continue
safe local discovery and planning, record the missing capability, and request user authority or a
compatible review/execution environment only when it becomes necessary.

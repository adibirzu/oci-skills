# Clean Agent Creation

Use this when creating a reusable JD agent team for a repository. The design follows the harness
engineering split between instructions, state, verification, scope, and lifecycle, plus an
independent maker/checker loop.

## Create or validate a team

Preview without writing:

```text
python3 scripts/create_agent_team.py render --harness all --target-root <repo>
```

Install workspace definitions:

```text
python3 scripts/create_agent_team.py install --harness all --target-root <repo>
python3 scripts/create_agent_team.py check --harness all --target-root <repo>
```

The canonical roles live in `assets/agent-blueprints.json`. Edit that structured file rather than
copying prompts by hand. The generator validates it before rendering.

## Clean-team invariants

1. Give every agent one purpose, one bounded deliverable, and an explicit capability list.
2. Keep planner and scout read-only. Give writes only to test-writer and maker.
3. Keep checker and security-checker read-only and independent from maker context. Their generated
   definitions have no command runner: they review supplied evidence and return verification
   commands and evidence requirements to the coordinator, which executes approved checks.
4. Give agents self-contained packets: goal slice, repository facts, owned paths, constraints,
   verification commands, evidence, and output schema. Do not say only "use the prior findings."
5. Allow only the coordinator to assign work, reconcile state, obtain authority, and communicate
   with the user. Generated agents must not spawn further agents.
6. Fail closed when a harness cannot enforce a declared capability. A prompt saying "read-only"
   is not proof of a read-only sandbox.
7. Keep project progress and handoff evidence in the JD ledger or repository harness, not inside
   agent definitions. Agent files define stable roles; task packets carry changing work.

## Native and compatibility outputs

| Harness | Generated surface | Guarantee |
|---|---|---|
| Antigravity / AGY | `.agents/agents/jd-<role>.md` | Native custom subagent with explicit tools and sandbox command policy. |
| Claude Code | `.claude/agents/jd-<role>.md` | Native subagent definition with a minimal tool allowlist. |
| Grok | `.claude/agents/jd-<role>.md` | Uses documented Claude-agent compatibility; shared with Claude. |
| Cursor | `.cursor/commands/jd-<role>.md` | Reusable command role, not a claimed isolated native subagent. |
| Pi | `.pi/prompts/jd-<role>.md` | Reusable prompt template; isolation must be supplied by the coordinator/runtime. |
| Cline | `.clinerules/workflows/jd-<role>.md` | Reusable workflow role; Plan/Act and permissions remain client controls. |

Cursor, Pi, and Cline outputs deliberately say `ROLE ADAPTER`, not `native subagent`. Do not
misrepresent prompt separation as process, workspace, model, or permission isolation.

## Agent acceptance checklist

- Unique stable name and concrete delegation description.
- Least-privilege capabilities; no implicit network, credentials, external writes, or merge.
- Exact owned paths supplied at dispatch time.
- Explicit startup reads and runnable verification commands.
- Structured result containing artifacts, evidence, blockers, and uncertainty.
- No recursive delegation or direct user communication.
- Independent checker receives the task contract, diff, and evidence, not maker reasoning.
- Generated files pass `create_agent_team.py check` and repository verification.

The generator refuses unmanaged collisions and symlinked destinations. It only updates files with
its managed marker. It does not install hooks, MCP servers, models, secrets, or global settings.

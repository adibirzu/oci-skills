# Coding-agent harness engineering

Use this reference when a repository needs reliable, restartable agent work:
the agent starts inconsistently, loses task state, widens scope, skips checks,
or cannot hand off an unfinished change safely.

This is an OCI Skills adaptation of the five-part harness model published by
walkinglabs/learn-harness-engineering. Keep it lean and project-specific. A
harness is a workflow contract, not a reason to add a second project-management
system or to place sensitive operational data in the repository.

## The five durable subsystems

| Subsystem | Minimal artifact | What good looks like |
| --- | --- | --- |
| Instructions | `AGENTS.md` or equivalent | Startup path, ownership boundaries, and a definition of done. |
| State | Existing backlog or small tracker | One active task, status, dependencies, evidence, and next step. |
| Verification | A documented script or command set | Uses the project-managed toolchain; fails clearly when prerequisites are missing. |
| Scope | Done criteria and boundary rules | Prevents unrelated rewrites and distinguishes local proof from live evidence. |
| Lifecycle | Progress ledger or handoff | Captures changed files, commands, blockers, and a restartable next action. |

## Discovery first

1. Inspect existing instruction files, manifests, CI workflows, test commands,
   release docs, and issue/roadmap state.
2. Reuse an authoritative tracker already present in the project. Add a small
   `feature_list.json` only when no suitable durable state exists.
3. Identify the minimum representative verification path. Do not substitute a
   convenient smoke check for the repository's required gate.
4. Ask before overwriting any existing instruction or state file.

## OCI and security boundaries

- Offline code, tests, documentation, and harness scaffolding do not need OCI
  credentials or preflight. Continue that work immediately.
- Do not put OCIDs, IPs, credentials, report payloads, tenant names, raw scan
  output, or customer source into an agent-state artifact.
- A fixture or local test proves behavior, not OCI tenancy compliance, live
  scan freshness, approval, or deployment success. Record that boundary in the
  feature evidence and final handoff.
- Do not weaken authentication, authorization, fail-closed collection, lease,
  redaction, or release gates just to make a harness command pass.

## Create or improve the harness

Prefer this minimal sequence:

1. Write or improve the instruction file with startup, scope, verification,
   definition of done, and end-of-session sections.
2. Add state only if the current project has no durable equivalent. Track
   feature ID, description, explicit status, dependencies, done criteria, and
   verification evidence.
3. Add a wrapper verification script only when the project lacks a discoverable
   command sequence. Use the project-managed runtime; refuse to silently fall
   back to global tools.
4. Add a handoff format that records objective, files, blockers, evidence
   boundary, and next step.
5. Validate structure and run the real verification path. Structural scoring
   tells whether artifacts cohere; it cannot prove agent effectiveness.

## Completion and handoff

Before saying the harness work is complete, provide:

- changed artifact list;
- structural validation result;
- executed verification commands and outcomes;
- any environment blockers;
- a clear statement of what was locally demonstrated versus what needs live
  OCI ownership, credentials, or approval.

For a multi-session task, leave the next agent a single concrete next action.
Avoid dumping transcripts or raw command output into the tracked handoff.

## Large-context harness audits

When auditing a harness spans many services, instruction layers, CI workflows,
or historical state artifacts, the optional `rlm` skill can structure the
review. Keep the five durable subsystems as the top-level partitions, pilot one
subsystem before expanding, and use depth 1 by default. Each partition returns
reviewed/deferred scope, source locations, verification, counterevidence, and
proof gaps. Recursive analysis does not make a structural score, prompt match,
or local test into evidence of agent effectiveness or live OCI acceptance.

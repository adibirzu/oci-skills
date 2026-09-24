# ER-04 — Governed provider adapters and capability journeys

Status: per-skill comparison and enhancement in progress; optional AI invocation
is not a core dependency. Provider evidence pending. Priority: P2. Depends
on: ER-03 and a valid named context for any provider canary.

## Problem Statement

The pack has broad guidance but uneven executable outcome coverage. Its OCI AI
envelope intentionally performs no invocation, and service capability claims do
not yet share provider-tested acceptance packs. Breadth without prioritized user
journeys risks adding prose while task success remains unmeasured.

## Solution

The product is a skill pack used by an existing AI assistant. Apply the
[skill comparison protocol](skill-comparison-protocol.md) to every skill,
comparing ordinary assistant calls with pack-enabled calls. The host supplies
AI invocation and login; OCI retains IAM for live calls. Add no pack-owned
authentication or authorization service. Reproduced articles and guides may
supplement official Oracle documentation. Final diagram review and aggregate
evaluation follow the per-skill repair loop.

Keep deterministic offline operation as the default, add optional governed AI
adapters only where measured benefit exists, and deliver capability acceptance
packs selected by user journey. Each pack spans identity, planning, execution,
telemetry, cost, rollback, and evidence without claiming universal tenancy
support.

## User Stories

1. As an operator, I want every journey to work deterministically without AI, so that provider availability is never a prerequisite for safe planning.
2. As an approved user, I want optional AI to normalize intent or rerank grounded local results, so that it improves a measured seam rather than owning execution.
3. As a security reviewer, I want classification, residency, identity, model discovery, cost caps, deadlines, and structured-output validation, so that provider use is governed.
4. As an operator, I want AI failure to fall back offline, so that an unavailable model does not block the workflow.
5. As a platform owner, I want one read-only diagnose-to-plan acceptance pack, so that evidence completeness is proven before mutations.
6. As a delivery owner, I want one approved deploy/verify/rollback acceptance pack, so that API success, downstream delivery, and rollback are independently checked.
7. As a domain owner, I want my capability enhancement represented by an owned task and outcome test, so that the 29-skill inventory has no planning blind spot.
8. As a user, I want unsupported services handed off gracefully to pinned upstream capability, so that missing local scope is explicit.

## Implementation Decisions

- Separate document ingestion, retrieval, reranking, inference, agent tools, and
  evaluation contracts. Enable only the adapter required by a measured journey.
- Discover available regional models and current schemas at runtime. Never
  hard-code a permanent latest model or infer availability from a manifest.
- Use approved OCI identity and named context; enforce data classification,
  residency, budget, deadline, retry, and structured-output rules before use.
- AI may propose or explain a typed plan but cannot issue approval or bypass
  `run_action`. Untrusted retrieved content cannot broaden authority.
- Start with two tracer journeys: one read-only diagnose-to-plan and one narrow
  deploy/verify/rollback. Expand by user value and evidence, not service count.
- Maintain a capability completion matrix for all 29 skills. Each row declares
  the owner, user outcome, implementation task, provider boundary, acceptance
  evidence, and explicit unsupported states.
- Record upstream revision/capability discovery for intentional handoffs and
  degrade gracefully when the upstream skill is absent.

## Testing Decisions

- Compare optional provider adapters against the deterministic baseline using
  the same held-out tasks, starting context, tools, and acceptance rubric.
- Test unavailable model, malformed structured output, timeout, rate limit,
  cost-cap exhaustion, prompt injection, residency denial, and offline fallback.
- Require provider canaries only for a named approved context and report them as
  provider verified, never release accepted.
- Every capability pack needs an offline contract test and an outcome-focused
  acceptance definition before a live canary is eligible.

## Out of Scope

- Google-tool parity as a release criterion.
- Autonomous approval, credential discovery, or universal provisioning.
- Duplicating upstream Oracle specialist skills wholesale.

## Further Notes

The task ledger groups the 29 capability enhancements into independently owned
vertical slices while retaining a row for every skill.

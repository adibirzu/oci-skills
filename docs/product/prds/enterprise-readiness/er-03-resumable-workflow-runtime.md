# ER-03 — Resumable workflow runtime

Status: implemented; locally verified. Priority: P2. Depends on: ER-02 stable contracts.

## Problem Statement

Domain skills describe many safe sequences but do not share a single executable
runtime for typed plans, context-bound authorization, durable checkpoints,
partial failure, compensation, rollback, and outcome evidence. API success can
therefore be mistaken for completion, and a restarted operator may not know what
is safe to retry.

## Solution

Implement one offline-first workflow runner used by CLI, SDK, MCP, and optional
provider adapters. It will persist only sanitized step metadata, bind risky work
to the exact target and plan, and distinguish retry, compensation, rollback,
manual recovery, and final outcome verification.

## User Stories

1. As an operator, I want a typed plan before execution, so that dependencies, cost implications, acceptance checks, and rollback are reviewable.
2. As an approver, I want approval bound to action, target, plan digest, context, and expiry, so that authorization cannot drift or replay.
3. As an operator, I want interrupted workflows to resume from verified checkpoints, so that successful steps are not blindly repeated.
4. As an operator, I want partial and stale inventories marked incomplete, so that collection errors are not interpreted as empty state.
5. As a reviewer, I want provider API success separated from downstream delivery and user-visible outcome, so that evidence is not promoted prematurely.
6. As a maintainer, I want every adapter to use the same safety core, so that MCP or AI cannot bypass approval and redaction.
7. As a support engineer, I want explicit retry, compensation, rollback, and manual-recovery states, so that failures have deterministic next actions.
8. As a release owner, I want packaged-install conformance tests, so that source-checkout success is not the only runtime proof.

## Implementation Decisions

- Define versioned plan, context, approval, checkpoint, step-result, and evidence
  contracts. Values are typed; shell fragments are not workflow data.
- The state machine is forward-only except for explicit compensation/rollback
  edges. A step is skipped on resume only when its evidence digest and target
  binding still match.
- Inventory results carry scope, pagination, collection errors, freshness,
  completeness, and source authority. Unknown, partial, stale, and untrusted are
  distinct fail-closed states.
- Risky steps call the existing `run_action` safety core. Read and offline steps
  do not gain mutation authority through the runner.
- Receipts use the existing secret-free evidence envelope and include a stable
  run id, target-binding digest, evidence class, and the intended outcome check.
- CLI, SDK, MCP, and AI surfaces are adapters to the same runner; none owns a
  second authorization or redaction model.
- Packaged conformance exercises the installed artifact across supported
  harnesses with deterministic fakes before any approved provider canary.

## Testing Decisions

- Use one vertical tracer workflow that discovers, plans, authorizes a synthetic
  action, injects a partial failure, resumes, verifies, and rolls back.
- Test pagination, rate limiting, eventual consistency, timeouts, stale receipts,
  mismatched digests, approval replay, compensation failure, and cleanup.
- Assert identical state transitions and evidence across CLI and adapter entry
  points. Tests must inspect external behavior, not runner internals.
- Add packaged-install task tests with network disabled and no OCI credentials.

## Out of Scope

- A new Terraform owner or direct OCI service implementation.
- Automatic approval, IAM expansion, or production break glass.
- Retaining raw provider responses, prompts, source patches, or secrets.

## Further Notes

The first executable journey should be read-only diagnose-to-plan. A narrowly
approved deploy/verify/rollback journey follows only after the common state
machine and evidence contracts are stable.

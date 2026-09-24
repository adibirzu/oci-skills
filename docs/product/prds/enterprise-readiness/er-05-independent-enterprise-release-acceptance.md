# ER-05 — Independent enterprise release acceptance

Status: local validators implemented; all-skill paired comparisons and final
aggregate evaluation pending. Use existing host authentication; no pack-owned
identity service is required. Independent evidence pending. Priority: P1
release gate. Depends on: the claimed subset of ER-01 through ER-04.

## Problem Statement

Structural contracts, passing fixtures, local coverage, rendered UIs, and
provider resource states do not prove a supported enterprise release. The pack
lacks one exact-candidate acceptance record covering installed behavior,
security, recovery, task success, efficiency, support scope, and independent
approval.

## Solution

Produce a signed, digest-bound release evidence packet from pinned artifacts and
held-out tasks. It will separate local, provider, customer, and release evidence;
measure outcome and efficiency without weakening safety; and require an
independent release decision.

## User Stories

1. As a release owner, I want every check bound to one candidate digest, so that evidence cannot be reused across revisions.
2. As an independent evaluator, I want a grader-free candidate and held-out rubric, so that the implementation does not approve itself.
3. As a security reviewer, I want zero secret disclosure and zero safety violations, so that efficiency never trades away controls.
4. As a customer reviewer, I want supported environments, versions, permissions, and unavailable capabilities listed, so that enterprise-ready has a bounded meaning.
5. As an operator, I want install failure and workflow rollback drills, so that recovery is evidence-backed.
6. As a product owner, I want pass@1, retries, latency, tool calls, and token distributions, so that reduced trial-and-error is measured honestly.
7. As a maintainer, I want open P1 defects, failed CI, stale docs, or missing ownership to block promotion, so that metadata cannot self-certify release.
8. As an approver, I want an explicit signed decision outside the candidate session, so that final acceptance remains independent.

## Implementation Decisions

- Build once, hash once, and use the same packaged artifact for install,
  security, harness, workflow, rollback, and evaluation checks.
- Record input, cached-input, and output tokens separately; first-attempt
  correctness; failed/repeated calls; clarification turns; latency; unsafe
  actions; and outcome correctness. Report distributions and sample sizes.
- Separate cold/warm caches, guidance/provider tasks, and simple/multi-service
  journeys. Do not use installed byte size or character estimates as token proof.
- Require no success-rate or safety regression before accepting an efficiency
  gain. Retain at least 90% fresh-agent pass@1 and zero safety violations.
- Require every trial manifest and telemetry sidecar to declare the same
  `codex-read-only-sandbox` network policy; treat this as configured/local
  evidence until an independent reviewer verifies host-level egress denial.
- Evaluate every candidate through a distinct, digest-verified native Agent
  Skills snapshot with write bits removed; recheck its file fingerprint after
  the child exits and publish no evidence if it changed.
- Publish support, maintenance, vulnerability-reporting, compatibility,
  deprecation, provenance, and third-party-notice artifacts with the candidate.
- Release state remains `external-evidence-pending` until the independent,
  hash-only attestation is valid. The candidate cannot write its own approval.

## Testing Decisions

- Execute the existing blinded fresh-agent suite against the candidate install
  and add enterprise scenarios for atomic upgrade, secret transport, partial
  workflow resume, rollback, unsupported routing, and offline fallback.
- Reproduce at least one installer failure and one workflow failure/rollback on
  a disposable local target. Live canaries, when approved, use disposable
  non-production scope and sanitized teardown receipts.
- Verify every distributed notice, manifest, SBOM/provenance record, support
  claim, and test receipt resolves to the same candidate digest.

## Out of Scope

- Self-certification by the implementing agent or maintainer.
- Claiming compatibility with every tenancy, customer, harness, or OCI service.
- Release publication, tagging, or external messaging without separate approval.

## Further Notes

The release may claim only the subset whose local and external gates are
complete. Deferred capability remains explicitly unavailable or unverified.

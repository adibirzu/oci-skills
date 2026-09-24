# Enterprise-readiness PRD set

Status: skill enhancement and per-skill baseline comparisons in progress.
See [the comparison protocol](skill-comparison-protocol.md) for the clarified
product boundary. Final diagram review and aggregate evaluation happen last.

This set converts the findings in the 2026-09-23 enterprise-readiness review
into five dependency-ordered product increments. It is deliberately separate
from the implemented REQ-13 through REQ-52 contract plane: the files here do
not become code-backed merely because a PRD exists.

| PRD | Review coverage | Outcome |
|---|---|---|
| ER-01 — Safe distribution foundation | F01-F04 | Implemented locally: atomic installation, notices, secret-safe handling, exact-revision CI |
| ER-02 — Reliable discovery and portable guidance | F05-F09 | Implemented locally: calibrated routing, target-derived examples, truthful gates, synchronized documentation |
| ER-03 — Resumable workflow runtime | F07-F09 plus the target workflow contract | Implemented locally: typed plans, context-bound approvals, checkpoints, compensation, evidence envelopes, packaged conformance |
| ER-04 — Governed provider adapters and capability journeys | F10 plus all 29 capability enhancements | Enhance every skill through paired task tests and verified sources; direct AI adapter optional |
| ER-05 — Independent enterprise release acceptance | Cross-cutting | Final paired evaluation, diagram review, tested-package provenance and independent acceptance; use existing host identity |

The executable backlog is
[the enterprise-readiness task ledger](../../tasks/enterprise-readiness.md).
No task authorizes OCI access, a mutation, publication, or release promotion.

# ER-02 — Reliable discovery and portable guidance

Status: implemented; locally verified. Priority: P1/P2. Depends on: ER-01 for distributable output.

## Problem Statement

The current selector can turn a weak unique match into high confidence, some
generic instructions embed one environment's counts or cleanup actions, local
quality checks can return success after findings, and contributor/operator
documentation is not consistently derived from the runtime inventory.

## Solution

Calibrate deterministic routing with abstention, derive operational choices from
the named target, make release gates fail closed, and generate separate
contributor, installed-user, and release-evidence views from authoritative
catalogs and support data.

## User Stories

1. As a user, I want out-of-domain requests rejected, so that a weather request is not routed to an OCI cost skill.
2. As a security operator, I want paraphrases such as leaked-secret rotation to find the safety owner, so that critical intent is not silently unsupported.
3. As a user, I want ambiguous and unsupported requests distinguished, so that the next action is explicit.
4. As an operator, I want architecture, subnet count, retention, sampling, and cleanup derived from the target, so that generic guidance does not mutate an unrelated environment.
5. As a maintainer, I want incident-specific recipes opt-in and named, so that they cannot masquerade as universal prerequisites.
6. As a release owner, I want required lint and redaction findings to return nonzero, so that a friendly message cannot convert failure into success.
7. As an installed user, I want an inventory of supported capabilities, permissions, versions, evidence class, and last verification date, so that guidance scope is honest.
8. As a contributor, I want current wrapper, metadata, and task conventions generated from source, so that documentation does not teach obsolete interfaces.
9. As a support owner, I want vulnerability reporting, maintenance, compatibility, and deprecation paths documented, so that users know what support means.

## Implementation Decisions

- Routing requires domain relevance plus calibrated score and margin thresholds.
  Return `selected`, `ambiguous`, `unsupported-oci`, or `out-of-domain` with a
  deterministic reason and validated target path.
- Build a held-out corpus of natural paraphrases, misspellings, negative
  requests, cross-service journeys, and out-of-domain prompts. Catalog wording
  is not sufficient evaluation data.
- Every generic workflow inventories the target before choosing architecture,
  resource count, sampling, retention, or deletion. Deletion is never inherited
  from a knowledge entry or recipe.
- Optional local knowledge services are adapters. A repository search and
  documented fallback remain usable when an adapter is absent.
- Required gates propagate findings and tool failures. Optional diagnostics are
  separately named and cannot satisfy release gates.
- Generate capability, helper, support, and compatibility inventories from
  authoritative catalogs. Distinguish guidance-only, helper-backed, locally
  verified, provider-verified, and release-accepted scope.
- Separate source contributor docs, compact installed docs, and release
  evidence; synchronize shared facts rather than copying prose.

## Testing Decisions

- Measure routing precision, recall, abstention quality, safety-intent recall,
  and unnecessary context loaded on a held-out corpus.
- Add negative tests proving that a non-OCI request, weak unique match, stale
  skill path, and cross-domain prompt do not receive false confidence.
- Use synthetic lint and secret findings to assert required gates return nonzero.
- Validate that generated documentation matches the installed bundle and that
  no generic flow contains environment-specific counts, names, or deletions.

## Out of Scope

- Natural-language model invocation; deterministic routing remains complete
  without a provider.
- Universal automatic provisioning for any tenancy.
- Provider acceptance inferred from documentation or fixtures.

## Further Notes

The initial test seam is the public discovery CLI plus installed-bundle docs.
Provider-specific execution belongs to ER-04.

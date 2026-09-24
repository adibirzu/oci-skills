# ER-01 — Safe distribution foundation

Status: implemented; locally verified. Priority: P1. Depends on: none.

## Problem Statement

An upgrade can remove the active payload before its replacement is known to be
usable, installed copies omit required notices, secret examples can place values
in transcripts or process arguments, and the exact reviewed revision is not
currently CI-green. An enterprise operator cannot trust installation or release
claims until failure preserves the last known-good installation and secrets are
absent from every evidence surface.

## Solution

Create a transactional, ownership-aware installer; distribute license and
third-party notices; replace value-bearing secret examples with metadata-only or
protected-consumer patterns; and establish one pinned, exact-revision release
gate shared by local and hosted execution.

## User Stories

1. As an operator, I want a failed upgrade to leave the prior installation usable, so that recovery does not depend on a second checkout.
2. As an operator, I want source/destination overlap and unsafe symlinks rejected before writes, so that an installer cannot erase its own source or escape its destination.
3. As a maintainer, I want required inputs and adapters validated before staging, so that an incomplete bundle never replaces a working one.
4. As a maintainer, I want concurrent installers serialized, so that two upgrades cannot interleave ownership changes.
5. As a user, I want user-owned files preserved and pack-owned files enumerated, so that upgrades do not delete unrelated configuration.
6. As a recipient, I want license and applicable third-party notices in every distribution, so that copies retain required attribution.
7. As a security reviewer, I want secret discovery to be metadata-only by default, so that routine diagnostics never expose values.
8. As an authorized operator, I want secret consumption to avoid stdout, stderr, shell history, argv, receipts, and committed files, so that credentials do not leak through automation.
9. As a release owner, I want the same pinned toolchain and mandatory gates locally and in CI, so that local success cannot mask hosted failure.
10. As an independent reviewer, I want install, rollback, notice, and synthetic-secret evidence bound to the exact candidate digest, so that another revision cannot reuse it.

## Implementation Decisions

- Resolve canonical source and destination paths before any write and reject
  equality, containment in either direction, and unsafe symlink components.
- Validate the complete required-input manifest before staging. Missing required
  payload entries are failures, not optional skips.
- Stage on the destination filesystem, validate staged digests and links, then
  perform a bounded swap with a recoverable prior-payload backup.
- Keep a versioned ownership manifest. Only paths owned by that manifest may be
  replaced or removed; unknown files survive upgrades.
- Use a destination-scoped lock and define interruption recovery for every
  state: before stage, staged, swapped, verified, and rolled back.
- Package `LICENSE` and declared third-party notices while keeping them outside
  automatic model context where supported.
- Replace value-returning secret examples with metadata inspection. Authorized
  value use must be a direct SDK-to-consumer or protected-file flow with mode
  restrictions, bounded lifetime, cleanup, and no value-bearing logs.
- Maintain an inventory of actual secret-bearing CLI/SDK fields and block them
  before invocation rather than relying on suffix heuristics alone.
- Pin release-critical lint/test dependencies and immutable action revisions.
  A missing optional diagnostic tool and a failing required gate are distinct.

## Testing Decisions

- Test through the highest distribution seam: install a real candidate bundle
  into an isolated destination, then exercise upgrade, failure, rollback, and
  disable/enable behavior from the installed copy.
- Cover same-path, nested-path, missing input, copy failure, invalid digest,
  hostile symlink, interruption, lock contention, and user-owned file cases.
- Seed synthetic secrets into inputs and failures, then assert absence from
  stdout, stderr, argv capture, receipts, backups, logs, and installed files.
- Assert that every supported harness receives identical required notices and
  that the exact candidate digest is the one tested in CI.

## Out of Scope

- Live OCI tenancy operations.
- Publishing or tagging a release.
- Rotating real credentials or migrating user-owned configuration automatically.

## Further Notes

Exit requires a preserved prior payload under every injected installer failure,
zero synthetic-secret disclosure, required notices in every bundle, and green
mandatory CI on the exact reviewed revision. Local tests alone are not release
acceptance.

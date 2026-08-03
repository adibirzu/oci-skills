# JD Delivery and Forge Protocol

Use this protocol for scout promotion, commits, pushes, pull/merge requests, merges, and proof
that work landed. Repository instructions and user authority may narrow these rules, never widen
them implicitly.

## Delivery modes

- `local-only` (default): edit and verify the working tree. Do not commit, push, open a PR/MR,
  merge, release, or deploy.
- `change-request`: perform only the specifically authorized commit, push, and PR/MR operations.
  Keep the change request reviewable and stop before merge.
- `landed`: merge only when the user explicitly authorizes the exact repository/change request
  or established repository policy delegates that authority. Never enable auto-merge.

Record the mode independently from strict/supervised/break-glass execution mode. Network and
external writes still require the authority and capability checks defined by JD.

## Promote scout evidence

When a read-only scout discovers a bounded fix:

1. Preserve its report, reproduction, affected paths, risk notes, and evidence digest.
2. Create a new ship task linked to the scout; do not retroactively grant the scout write access.
3. Revalidate the reproduction against the current base and write a RED contract when behavior
   changes.
4. Assign a canonical path lease and execute the normal implementation and review loop.

Promotion avoids duplicate discovery but never skips tests, ownership, or independent review.

## Change-request readiness

Before an authorized commit, push, or PR/MR:

- reconcile the base branch and unrelated dirty changes;
- confirm every changed path is in scope and no secret or private identifier is present;
- run focused and required full verification with fresh evidence;
- resolve HIGH/CRITICAL review findings;
- use a change summary that states outcome, verification, risk, and rollback;
- avoid force push, history rewriting, and branch deletion unless separately authorized.

A green local test, successful push, or open PR/MR does not prove mergeability or deployment.

## Merge authority and landed proof

PR/MR creation and review do not imply merge authority. Before merging, confirm the exact change
request, target branch, required approvals/checks, merge method, and rollback path. Reconcile new
base changes and rerun affected verification. Do not bypass branch protection or enable
auto-merge.

After an authorized merge, verify the target branch contains the expected commit or tree, required
checks completed, and no unexpected changes landed. Release or deployment remains a separate
authority boundary. Record the forge URL or identifier only when it is not sensitive.

## Outcome-first reporting

Report the user-visible outcome and evidence before internal mechanics. Distinguish clearly:

- implemented locally;
- committed;
- pushed;
- change request opened and checks pending/passing;
- merged and verified on the target branch;
- released or deployed with separate evidence.

Never collapse these states into a generic claim that work is "done" or "shipped".

# Enterprise-readiness task ledger

Status: in progress. Parent PRDs: ER-01 through ER-05. Source review:
`docs/reviews/2026-09-23-enterprise-readiness-review.md`.

Current evidence: P1 delivery-safety implementation is locally verified by
focused contracts; ER-015 has an offline fake-provider tracer. Provider,
customer, and release evidence remain pending and no task entry authorizes OCI
mutation, publication, or release promotion.

Tasks are ordered by dependency and are independently grabbable vertical
slices. Completion requires the stated external behavior and tests; creating a
file, contract, or resource is not sufficient. No task authorizes live OCI work,
publication, or release promotion.

## Delivery sequence

### Reopened completion audit

**Product scope clarification:** This is a skill pack for an existing AI host.
Use the [per-skill comparison protocol](../prds/enterprise-readiness/skill-comparison-protocol.md)
for all 29 skills: normal AI call without the pack versus the same task with
the pack, followed by repair and retest. Official documentation is primary;
reproduced articles and guides supplement it. No pack-owned AuthN/AuthZ service
is required. Diagram review and aggregate final evaluation occur at the end.

The previous claim that only external acceptance remained was too broad.
The following implementation work remains, independently of release approval:

| Task | Missing behavior | Completion evidence |
|---|---|---|
| ER-014 | Optional AI assistance through the host; direct OCI AI invocation only for a demonstrated use case | Per-skill task improvement and safe fallback; an invoking adapter is not a core completion dependency |
| ER-020 | Rendered diagram exports and visual-review evidence | Source/export digest linkage, real rendered artifacts and recorded visual inspection |
| ER-021 | All-skill development comparisons, followed by final aggregate evaluation | Same-task normal-call baseline and pack-enabled sessions using existing host identity; real outcomes and observed usage; no new pack login |
| ER-022 | Source-to-install build provenance and dependency evidence | Reproducible build manifest linking source inputs, build recipe, dependency inventory and installed digest; reject stale mappings |

The candidate-copy race and OCI collection-envelope counting defect identified
during this audit have regression fixes. These repairs do not close the broader
items above. All provider, hosted CI and independent release gates remain open.

### Installed troubleshooting readiness

The September 24 hardening slice adds whole-token, title-weighted KB lookup,
exact-ID retrieval, optional fix bodies/JSON, safe terminal rendering, and
installed-root resolution. Repeated body terms no longer dominate symptom
ranking. KB-181 repairs the duplicate collection-envelope identifier;
KB-182 through KB-189 distill portable operational lessons without source
project names, paths, identities, or raw receipts. Historical recipes are not
claimed as freshly provider verified.

- [x] Regression tests exercise realistic symptom-to-fix results and unique IDs.
- [x] Copy-install tests exercise the bundled KB from an unrelated directory
  without source-project KBs or OCI credential environment variables.
- [x] KB ingestion instructions allocate IDs above the numeric maximum.
- [ ] Finish entry-level disposition of all discovered portfolio KBs; discovery
  and heading inspection alone do not establish complete ingestion.
- [ ] Run the same troubleshooting tasks in fresh normal-call and pack-enabled
  AI sessions under ER-021; deterministic search tests are not that comparison.

No cloud resources, credentials, global installations, or release status are
changed by this slice.

| Task | Title | Blocked by | Review / PRD coverage |
|---|---|---|---|
| ER-001 | Preserve the active installation through failed replacement | None | F01 / ER-01 |
| ER-002 | Ship license and third-party notices in every bundle | None | F02 / ER-01 |
| ER-003 | Make Vault consumption transcript- and argv-safe | None | F03 / ER-01 |
| ER-004 | Make exact-revision CI authoritative and pinned | None | F04 / ER-01 |
| ER-005 | Calibrate routing and explicit abstention | ER-004 | F05 / ER-02 |
| ER-006 | Replace environment-specific guidance with target-derived plans | ER-003 | F06 / ER-02 |
| ER-007 | Make local required gates fail closed | ER-004 | F07 / ER-02 |
| ER-008 | Inventory and test every shipped executable surface | ER-001, ER-004 | F08 / ER-02 |
| ER-009 | Generate operator, contributor, support, and compatibility docs | ER-002, ER-008 | F09 / ER-02 |
| ER-010 | Execute one typed read-only diagnose-to-plan workflow | ER-005, ER-007 | Target workflow / ER-03 |
| ER-011 | Bind approvals and receipts to context, target, and plan digest | ER-003, ER-010 | Target workflow / ER-03 |
| ER-012 | Resume partial workflows with retry, compensation, and rollback | ER-011 | Target workflow / ER-03 |
| ER-013 | Prove installed-bundle conformance across supported harnesses | ER-001, ER-008, ER-012 | F08 / ER-03 |
| ER-014 | Add governed optional OCI AI normalization and fallback | ER-005, ER-010 | F10 / ER-04 |
| ER-015 | Deliver the first approved deploy/verify/rollback journey | ER-011, ER-012 | Target workflow / ER-04 |
| ER-016 | Complete identity, security, and governance acceptance packs | ER-010, ER-011 | Capability matrix / ER-04 |
| ER-017 | Complete observability, database, and data acceptance packs | ER-010, ER-011 | Capability matrix / ER-04 |
| ER-018 | Complete networking, OKE, event, and delivery acceptance packs | ER-012, ER-015 | Capability matrix / ER-04 |
| ER-019 | Complete cost, IaC, project, and application acceptance packs | ER-012, ER-015 | Capability matrix / ER-04 |
| ER-020 | Complete landing-zone, diagramming, routing, and upstream handoff packs | ER-009, ER-016-ER-019 | Capability matrix / ER-04 |
| ER-021 | Run blinded task-success and efficiency evaluation | ER-013 and claimed ER-014-ER-020 scope | Evaluation / ER-05 |
| ER-022 | Produce provenance, SBOM, support, and rollback evidence | ER-002, ER-004, ER-013 | Release / ER-05 |
| ER-023 | Obtain independent digest-bound release acceptance | ER-021, ER-022 | Release / ER-05 |

## Task cards

### ER-001 — Preserve the active installation through failed replacement

**What to build:** A staged, destination-local upgrade path that validates the
complete candidate, rejects source/destination overlap and unsafe symlinks,
serializes writers, swaps atomically, and restores the prior owned payload after
any injected failure without touching user-owned files.

**Acceptance criteria:**

- [x] Same-path, nested-path, missing-input, failed-copy, invalid-digest,
  interruption, symlink, and concurrent-upgrade cases leave the prior install
  byte-for-byte usable.
- [x] A versioned ownership manifest limits replacement and removal.
- [x] A clean install, upgrade, disable/enable, and installed-copy upgrade pass
  on every supported harness fixture.

**Blocked by:** None - can start immediately.

### ER-002 — Ship license and third-party notices in every bundle

**What to build:** A distribution contract that includes the project license
and applicable third-party notices in every copy/plugin/extension bundle without
placing those files in automatic model context.

**Acceptance criteria:**

- [x] Every supported installer contains identical required notices.
- [x] Manifest and clean-install tests fail when a notice is absent or changed.
- [x] Third-party assets and pinned actions have provenance and license records.

**Blocked by:** None - can start immediately.

### ER-003 — Make Vault consumption transcript- and argv-safe

**What to build:** Metadata-only discovery plus an authorized secret-consumption
interface that moves values directly to a protected consumer or restrictive
temporary file, with bounded lifetime and verified cleanup.

**Acceptance criteria:**

- [x] No example prints or passes a secret value on argv.
- [x] Synthetic canaries are absent from stdout, stderr, argv capture, receipts,
  errors, logs, backups, and committed files.
- [x] Credential actions still require exact target-bound approval.

**Blocked by:** None - can start immediately.

### ER-004 — Make exact-revision CI authoritative and pinned

**What to build:** One version-pinned mandatory gate used locally and in hosted
CI, with executable-mode contracts and immutable action/dependency revisions.

**Acceptance criteria:**

- [x] Current Ruff, shell, test, coverage, docs, redaction, and manifest gates
  pass on the exact candidate revision.
- [x] Missing optional tools and failed required gates have distinct nonzero
  behavior.
- [x] The release receipt records the tested commit and artifact digests.

**Blocked by:** None - can start immediately.

### ER-005 — Calibrate routing and explicit abstention

**What to build:** Deterministic routing with domain thresholds, score margins,
path validation, and `selected`/`ambiguous`/`unsupported-oci`/`out-of-domain`
results.

**Acceptance criteria:**

- [x] Held-out natural-language, typo, negative, safety, cross-domain, and
  non-OCI corpus reports precision, recall, abstention, and context cost.
- [x] Weak unique matches do not become high confidence.
- [x] Missing or stale selected paths fail with a safe handoff.

**Blocked by:** ER-004.

### ER-006 — Replace environment-specific guidance with target-derived plans

**What to build:** Target-inventory-first architecture, telemetry, retention,
sampling, and cleanup planning, with environment-specific recovery sequences
moved into named opt-in recipes.

**Acceptance criteria:**

- [x] Function/OKE image architecture is selected from the target shape and a
  matching or multi-architecture image is verified before deployment.
- [x] Flow Log counts, filters, retention, cost, and subnets come from an
  inventory and explicit choice; generic flows delete nothing.
- [x] Optional local adapters have a repository-search fallback.

**Blocked by:** ER-003.

### ER-007 — Make local required gates fail closed

**What to build:** Authoritative gate wrappers that propagate shell lint,
redaction, and tracked/new-file findings while keeping diagnostics explicitly
non-authoritative.

**Acceptance criteria:**

- [x] Synthetic lint and redaction violations return nonzero locally and in CI.
- [x] Tracked, staged, untracked task, and generated-evidence surfaces are
  handled safely, including spaces and leading dashes.
- [x] No fallback message converts a real finding into success.

**Blocked by:** ER-004.

### ER-008 — Inventory and test every shipped executable surface

**What to build:** A generated executable inventory with branch coverage,
dependency/asset manifests, checksums, negative tests, and installed-task tests
for helpers outside the current aggregate.

**Acceptance criteria:**

- [x] Every shipped Python/shell/helper entry point is included or has a reviewed
  non-executable classification.
- [x] Coverage and negative-case reports are bound to the packaged artifact.
- [x] Moving dependencies/actions are replaced by reviewed pins.

**Blocked by:** ER-001 and ER-004.

### ER-009 — Generate operator, contributor, support, and compatibility docs

**What to build:** Source-derived inventories and separate documentation views
for operators, contributors, installed users, support, security, and release.

**Acceptance criteria:**

- [x] Current wrappers, frontmatter, installed payload, skill counts, versions,
  permissions, support status, and evidence classes are generated from source.
- [x] SECURITY, support/maintenance, compatibility, deprecation, install/rollback,
  and operator quickstart content is present and link-checked.
- [x] Each workflow states inputs, discovery, execution, outputs, failure modes,
  cost/retention, recovery, cleanup, and verification.

**Blocked by:** ER-002 and ER-008.

### ER-010 — Execute one typed read-only diagnose-to-plan workflow

**What to build:** The common workflow contracts and runner through a complete
read-only journey that inventories bounded scope, records incompleteness, emits
a typed plan, and verifies the intended diagnostic outcome.

**Acceptance criteria:**

- [x] Unknown, partial, stale, rate-limited, and untrusted inventory states are
  distinct and fail closed.
- [x] Pagination, collection errors, freshness, scope, dependencies, expected
  evidence, cost, and rollback appear in the plan.
- [x] CLI/SDK/MCP adapters produce the same sanitized evidence envelope.

**Blocked by:** ER-005 and ER-007.

### ER-011 — Bind approvals and receipts to context, target, and plan digest

**What to build:** Versioned context, plan, approval, and evidence bindings that
reuse the existing safety core and reject expiry, replay, target drift, and plan
changes.

**Acceptance criteria:**

- [x] Approval is invalid after any material context, target, action, or plan
  digest change.
- [x] Retrieved content, documents, tool output, and model responses cannot grant
  authority.
- [x] Receipts contain no raw provider response or credential value.

**Blocked by:** ER-003 and ER-010.

### ER-012 — Resume partial workflows with retry, compensation, and rollback

**What to build:** Durable metadata-only checkpoints and a forward state machine
that distinguishes safe retry, compensation, rollback, and manual recovery.

**Acceptance criteria:**

- [x] Resume skips a step only when evidence and target bindings still match.
- [x] Injected partial failure and interruption converge without duplicating
  completed mutations.
- [x] API success, downstream delivery, and user-outcome verification remain
  separate evidence gates.

**Blocked by:** ER-011.

### ER-013 — Prove installed-bundle conformance across supported harnesses

**What to build:** Network-isolated conformance tests that run the same packaged
artifact and tracer workflows across every supported harness.

**Acceptance criteria:**

- [x] Source checkout and installed bundle produce the same routing, plans,
  safety decisions, state transitions, and sanitized receipts.
- [x] Tests run without OCI credentials or model/provider availability.
- [x] Harness-specific adapters cannot bypass the common runtime.

**Blocked by:** ER-001, ER-008, and ER-012.

### ER-014 — Add governed optional OCI AI normalization and fallback

**What to build:** One optional adapter for a measured seam such as intent
normalization or grounded reranking, with runtime discovery and deterministic
offline fallback.

**Acceptance criteria:**

- [x] Identity, region/model availability, classification/residency, budget,
  deadline, retries, and structured-output validation are explicit in the
  non-invoking `normalize` policy envelope. Availability, residency, and
  guardrails remain explicitly unverified until a separately approved provider
  canary.
- [x] Timeout, throttling, malformed output, injection, and unavailable service
  fall back safely without blocking deterministic work; synthetic provider
  output is discarded and cannot route, approve, or execute work.
- [x] The adapter cannot approve or execute an action.

**Blocked by:** ER-005 and ER-010.

### ER-015 — Deliver the first approved deploy/verify/rollback journey

**What to build:** A narrow canary journey that runs through the common runtime,
uses reviewed Terraform or `run_action` ownership, verifies downstream outcome,
and proves rollback/cleanup in disposable non-production scope when approved.

**Acceptance criteria:**

- [x] Offline plan and fake-provider tests pass before any live action.
- [x] Exact context, resource, blast radius, cost, approval, and teardown are
  captured in sanitized evidence.
- [x] Provider success, user outcome, rollback, and teardown are independently
  verified; absent approval leaves provider evidence pending.

**Blocked by:** ER-011 and ER-012.

### ER-016 — Complete identity, security, and governance acceptance packs

**What to build:** Outcome packs for administrator routing, IAM, security and
compliance, AIOps evaluation, Data Safe, and ZPR. Include policy/principal
readiness, secret-safe control evidence, evaluator eligibility, assessment
diffs, audit-ingestion proof, and positive/negative reachability.

**Acceptance criteria:**

- [x] Each owning skill has one user journey, typed plan, failure/rollback path,
  offline contract test, explicit permissions, and evidence classification.
- [x] No policy, assessment, score, or visibility state is inferred from an
  empty or partial inventory.
- [x] Capability matrix rows are complete for all six owners.

**Blocked by:** ER-010 and ER-011.

### ER-017 — Complete observability, database, and data acceptance packs

**What to build:** Outcome packs for observability, DBM/OPSI, Autonomous DB,
Database Cloud, storage, disaster recovery, Log Analytics, and data platform.
Cover SLOs, privileges/collection, credential-minimized connections, maintenance,
restore integrity, RTO/RPO, detection replay, data quality, lineage, and lag.

**Acceptance criteria:**

- [x] Collection, storage, query, correlation, visualization, alerting, response,
  and user outcome remain distinct gates.
- [x] Restore, failback, ingestion, and replication success require fresh
  marker-specific evidence rather than resource state alone.
- [x] Capability matrix rows are complete for all eight owners.

**Blocked by:** ER-010 and ER-011.

### ER-018 — Complete networking, OKE, event, and delivery acceptance packs

**What to build:** Outcome packs for Bastion, networking/compute, OKE,
events/functions, OS Management, and Developer Services. Cover expiring access,
hybrid/IPv6/certificate paths, architecture-aware images, upgrade canaries,
poison/retry/replay, staged patching, signed promotion, and rollback health.

**Acceptance criteria:**

- [x] Architecture, routes, certificates, identity, and target cluster are
  derived from the named context before action.
- [x] Queue/event delivery, patch/reboot health, and deployment promotion require
  end-to-end outcome receipts, not an ACTIVE/RUNNING state.
- [x] Capability matrix rows are complete for all six owners.

**Blocked by:** ER-012 and ER-015.

### ER-019 — Complete cost, IaC, project, and application acceptance packs

**What to build:** Outcome packs for cost, Resource Manager, Terraform authoring,
project orchestration, product development, and application engineering. Cover
allocation/anomaly evidence, exact-plan binding, drift/migration, durable resume,
golden-path acceptance, and portable optional integrations.

**Acceptance criteria:**

- [x] Durable resources have one explicit owner and reviewed migration path.
- [x] Plans, state, provenance, cost, telemetry, rollback, and teardown are bound
  to the same workflow/candidate digests.
- [x] Capability matrix rows are complete for all six owners.

**Blocked by:** ER-012 and ER-015.

### ER-020 — Complete landing-zone, diagramming, routing, and upstream handoff packs

**What to build:** Outcome packs for landing zone, diagramming, local developer
knowledge, and the top-level administrator. Include tenancy-foundation readiness,
resource-to-diagram lineage, calibrated unsupported handoff, versioned capability
inventory, and pinned upstream discovery.

**Acceptance criteria:**

- [x] All 29 capability rows have an owner, journey, implementation task,
  provider boundary, acceptance evidence, and explicit unsupported states.
- [x] Upstream handoffs record actual installed capability/revision and fail
  gracefully when absent.
- [ ] Diagram exports are traceable to sanitized resource snapshots and pass
  structural plus visual-quality review without provider claims.

**Blocked by:** ER-009 and ER-016 through ER-019.

### ER-021 — Run blinded task-success and efficiency evaluation

**What to build:** Exact-candidate paired trials for baseline and candidate using
the same harness/model/tools/fixtures/tasks, including safety and recovery cases.

The installer-to-packet-to-manifest-to-trial identity chain is locally verified
by `test_documented_installer_packet_manifest_and_trial_sequence_is_digest_bound`.
This proves candidate binding and private telemetry publication only; it does
not substitute for authenticated fresh-agent scoring or independent acceptance.

**Acceptance criteria:**

- [ ] Report pass@1, outcome correctness, tokens by class, tool calls,
  failed/repeated calls, clarifications, latency, safety events, distributions,
  sample sizes, and cold/warm cache results.
- [ ] Candidate has at least 90% fresh-agent pass@1, zero safety violations, and
  no success-rate regression before efficiency is credited.
- [x] Raw responses and held-out rubric remain outside the candidate install;
  blinded-install and evaluator-asset rejection tests enforce this locally.
- [x] Trial manifests and telemetry bind the `codex-read-only-sandbox` policy;
  host-level egress enforcement remains an explicit independent-review gate.
- [x] Each trial evaluates a distinct, digest-verified native-discovery snapshot
  with write bits removed and rejects any snapshot mutation before publication.
- [x] The approved read-only provider check is recorded without tenant
  identifiers or spend values; missing budget configuration remains an explicit
  provider-readiness blocker rather than a release claim.

**Blocked by:** ER-013 and every ER-014 through ER-020 capability claimed for the release.

### ER-022 — Produce provenance, SBOM, support, and rollback evidence

**What to build:** A candidate-bound evidence packet containing checksums,
dependency/asset provenance, notices, support matrix, CI results, installer
rollback drill, workflow rollback drill, and explicitly pending external gates.

**Acceptance criteria:**

- [x] Every local artifact and receipt resolves to one candidate digest,
  including a verified digest-only source-build-to-installed-payload mapping
  and dependency-integrity provenance. This is local build evidence, not an
  independent release approval.
- [x] No open P1 defect, failed mandatory gate, stale owner, missing notice, or
  unreviewed exception is hidden by the metadata-only readiness declaration;
  unavailable owner review remains an explicit external blocker.
- [x] The packet is metadata-only, redacted, and distinguishes local, provider,
  customer, and release evidence.

**Blocked by:** ER-002, ER-004, and ER-013.

### ER-023 — Obtain independent digest-bound release acceptance

**What to build:** An independent review and signed hash-only decision over the
candidate evidence packet. The implementing session cannot produce acceptance.

The repository now contains a verification-only boundary at
`scripts/release_attestation.py`. It validates the packet byte digest, candidate
digest, reviewer identity, and canonical Ed25519 signature without signing,
mutating, or publishing the packet. A successful local verification is still
only evidence that the supplied external record is internally consistent; it
does not create the independent review.

**Acceptance criteria:**

- [ ] Independent reviewer confirms claimed scope, zero open P1 defects,
  rollback evidence, support boundary, and evaluation thresholds.
- [x] Release state stays `external-evidence-pending` until the signature
  validates; the packet and attestation verifier enforce this locally.
- [x] Publication/tagging remains a separate explicitly authorized action and
  is not performed by the verifier or packet builder.

**Blocked by:** ER-021 and ER-022.

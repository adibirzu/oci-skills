# OCI Skills v2 delivery plan

This is the repo-native traceability ledger. Merged history before v2 is the delivered baseline. New work maps to the PRD; no retroactive tasks are invented.

## Remaining to implement

Everything else in this ledger is landed on `main` (see the Status/PR columns
below for the commit or PR backing each row). What is genuinely outstanding:

| Item | Task(s) | Why it's open |
|---|---|---|
| Independent fresh-agent forward-eval run | V2-11, V2-13, PROD-21 | The 34-case blinded harness (`evals/forward/`) and grader-free candidate install are implemented and merged, but no run has been recorded — `evals/forward/` has no `runs/` directory yet. This is the declared **release blocker** for `v2.0.0`; see [Deferred release evidence](#deferred-release-evidence). |
| `v2.0.0` promotion | V2-12 | Plugin/extension manifests declare `2.0.0-rc.3` (`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, `harness/gemini/gemini-extension.json`, `.claude-plugin/marketplace.json`); no `v2.0.0` git tag exists yet (`git tag -l` shows only `v1.10.0`, `v1.10.1`, `v1.13.0`). Blocked on the forward-eval run above. |
| Golden-path component locals need domain-specific HCL materialization | Medium/low follow-up | Fixtures still resolve provider fields from a mocked `schema.yaml`, not the real provider schema, per customer design. See [Medium/low follow-ups](#mediumlow-follow-ups). |
| Live Resource Manager / Terraform end-to-end tests are mocked in CI | Medium/low follow-up | CI's `terraform` job runs every `init`/`validate` with `-backend=false` (verified in `.github/workflows/ci.yml`); no live tenancy is exercised. See [Medium/low follow-ups](#mediumlow-follow-ups). |

## Requirement traceability

| Requirement | Tasks | Verification |
|---|---|---|
| REQ-01 | V2-01, V2-09 | skill validator, routing/eval parity |
| REQ-02 | V2-03 | Terraform unit/shell/fixture tests |
| REQ-03 | V2-02, V2-04 | action and CLI-lint tests |
| REQ-04 | V2-02, V2-03, V2-13 | receipt/approval/plan/security tests |
| REQ-05 | V2-05, V2-06, V2-07 | five golden-path fixtures and evals |
| REQ-06 | V2-05, V2-06 | developer-services and Queue coverage |
| REQ-07 | V2-08 | mocked project lifecycle smoke |
| REQ-08 | V2-10, V2-12 | doc/install/manifest parity |
| REQ-09 | V2-11, V2-12, V2-13 | coverage, security, redaction, forward eval |
| REQ-10 | APP-01, APP-02 | optional-workflow, measurement, and fallback tests |
| REQ-11 | GAP-01, GAP-02 | Bastion/Database Cloud topology, routing, safety, and source contracts |
| REQ-12 | GAP-03 | Landing-zone, Terraform, IAM, docs, and regression contracts |
| REQ-13 | PROD-13 | application-workflow schema and sanitized evidence |
| REQ-14 | PROD-14 | deterministic workflow evaluator and aggregate reporting |
| REQ-15 | PROD-15 | capability catalog and inventory parity |
| REQ-16 | PROD-16 | routing precedence contract and eval alignment |
| REQ-17 | PROD-17 | common secret-free evidence envelope |
| REQ-18 | PROD-18 | architecture traceability and contract validator |
| REQ-19 | PROD-19 | multi-harness distribution contract |
| REQ-20 | PROD-20 | complete redaction-scope contract |
| REQ-21 | PROD-21 | honest local release-readiness report |
| REQ-22 | PROD-22 | compatibility and deprecation contract |
| REQ-23 | PROD-23 | contract schema registry and fail-closed shape validation |
| REQ-24 | PROD-24 | sanitized user-journey and acceptance-test registry |
| REQ-25 | PROD-25 | acyclic requirement dependency graph |
| REQ-26 | PROD-26 | shell-safe declarative verification registry |
| REQ-27 | PROD-27 | local/Oracle-official source provenance |
| REQ-28 | PROD-28 | requirement-to-consumer change-impact map |
| REQ-29 | PROD-29 | reproducible install payload and exclusion manifest |
| REQ-30 | PROD-30 | evidence-bound release state machine |
| REQ-31 | PROD-31 | canonical adversarial safety-case catalog |
| REQ-32 | PROD-32 | migration readiness and major-only removal policy |
| REQ-33 | PROD-33 | fail-closed change classification |
| REQ-34 | PROD-34 | backward-compatible schema evolution |
| REQ-35 | PROD-35 | governance accountability matrix |
| REQ-36 | PROD-36 | evidence retention boundary |
| REQ-37 | PROD-37 | cross-harness environment parity |
| REQ-38 | PROD-38 | release recovery playbooks |
| REQ-39 | PROD-39 | machine-readable architecture invariants |
| REQ-40 | PROD-40 | documentation freshness policy |
| REQ-41 | PROD-41 | external hash-only release attestation |
| REQ-42 | PROD-42 | fail-closed maintenance policy |
| REQ-43 | PROD-43 | change-set manifest reliability contract |
| REQ-44 | PROD-44 | exception policy reliability contract |
| REQ-45 | PROD-45 | waiver expiry reliability contract |
| REQ-46 | PROD-46 | dependency integrity reliability contract |
| REQ-47 | PROD-47 | deterministic output reliability contract |
| REQ-48 | PROD-48 | performance budget reliability contract |
| REQ-49 | PROD-49 | network isolation reliability contract |
| REQ-50 | PROD-50 | contract backup/restore reliability contract |
| REQ-51 | PROD-51 | release rollback reliability contract |
| REQ-52 | PROD-52 | end-of-life policy reliability contract |

## Task cards

Verified in this worktree against `main` (tip `06f3495`): `python3 -m pytest
tests/ -q` → 355 passed; `python3 scripts/product_contracts.py validate` →
`valid: true` (40 PRDs, 37 contracts, 30 journeys, 8 safety cases, 52
requirements); `skills/oci-bastion-access/`, `skills/oci-database-cloud/`,
`skills/oci-landing-zone/`, and `skills/oci-application-engineering/` are all
present on `main`. This backs the blanket "Implemented" (dropped "locally")
and PR-column corrections below for rows without a more specific reference: no
PR was ever opened for this work — it was committed straight to `main` — so
"not opened" was true but read as "not yet done." It now says so plainly.

| Task | Requirements | Depends on | Status | PR |
|---|---|---|---|---|
| V2-01 PRD, ownership, architecture | all | — | Implemented | merged directly to main (no PR) |
| V2-02 risk-aware safety core | REQ-03, REQ-04 | V2-01 | Implemented + tested; destructive-guard scope broadened to cover kubectl/helm/terraform (previously OCI CLI only) | PR #43 (06f3495) |
| V2-03 Terraform authoring engine | REQ-02, REQ-04 | V2-02 | Implemented + tested | merged directly to main (no PR) |
| V2-04 exact OCI CLI authoring | REQ-03 | V2-02 | Implemented + tested | merged directly to main (no PR) |
| V2-05 Developer Services | REQ-05, REQ-06 | V2-03, V2-04 | Implemented | merged directly to main (no PR) |
| V2-06 Queue/event worker | REQ-05, REQ-06 | V2-02, V2-04 | Implemented | merged directly to main (no PR) |
| V2-07 product orchestrator | REQ-05 | V2-03, V2-05, V2-06 | Implemented + fixtures; platform-bundle validation now enforced with real JSON Schema (`jsonschema` against `schemas/platform-bundle.schema.json`), replacing the prior hand-rolled field checks | PR #43 (06f3495) |
| V2-08 project lifecycle integration | REQ-07 | V2-07 | Implemented + smoke | merged directly to main (no PR) |
| V2-09 skill/routing conformance | REQ-01 | V2-08 | Implemented + validator; codex `openai.yaml` skill-enumeration parity added, plus routing/trigger-overlap and golden-path-count drift fixes fenced by a new orphaned-reference/script CI guard | PR #43 (06f3495) + commits f919257, d8a9320, 35b5347, 8d8f348 |
| V2-10 README/architecture/diagrams | REQ-08 | V2-09 | Implemented; antigravity golden-path count drift fixed, install prerequisites (`jsonschema`) documented in README/QUICKSTART/CONTRIBUTING | PR #43 (06f3495) + commit d8a9320 |
| V2-11 test/coverage/forward eval | REQ-09 | V2-09 | Blinded 34-case harness (`evals/forward/prompts.json`, `rubric.json`) and grader-free candidate install implemented; independent fresh-agent run pending — **release blocker, see Remaining to implement** | not opened |
| V2-12 packaging/release | REQ-08, REQ-09 | V2-10, V2-11 | `v2.0.0-rc.3` prepared with storage, DR, network-edge, and current Oracle handoff coverage (plugin/extension manifests confirmed at `2.0.0-rc.3`, no `v2.0.0` tag yet); final promotion deferred to forward-eval gate | not opened |
| V2-13 final security/architecture review | REQ-04, REQ-09 | V2-12 | Local review/gates implemented; fresh-agent evidence remains release blocker | not opened |
| APP-01 application-engineering workflow | REQ-10 | V2-09 | Implemented: routing, evidence schema, reuse/TDD/review workflow, and non-blocking contracts | merged directly to main (no PR) |
| APP-02 optional MultiLLM measurement adapter | REQ-10 | APP-01 | Implemented local boundary: deterministic preparation/scoring, permissions, caps, and aggregate evidence; provider/DeepEval execution remains external and opt-in | merged directly to main (no PR) |
| GAP-01 Bastion access domain | REQ-11 | V2-09 | Implemented with routing, reference, metadata, safety, and eval coverage | merged directly to main (no PR) |
| GAP-02 Database Cloud domain | REQ-11 | V2-09 | Implemented with Base Database/Exadata boundaries and lifecycle contracts | merged directly to main (no PR) |
| GAP-03 Landing zone plus Terraform/IAM depth | REQ-12 | GAP-01, GAP-02 | Implemented with synchronized documentation and capability contracts | merged directly to main (no PR) |
| PROD-13 application workflow evidence | REQ-13 | APP-01 | Implemented: schema, PRD, application boundary, validation | merged directly to main (no PR) |
| PROD-14 deterministic workflow evaluation | REQ-14 | APP-02, PROD-13 | Implemented: permission-safe evaluator and aggregate-only report | merged directly to main (no PR) |
| PROD-15 capability catalog | REQ-15 | V2-09 | Implemented: 26-skill catalog and parity validation | merged directly to main (no PR) |
| PROD-16 routing precedence | REQ-16 | PROD-15 | Implemented: six positive/negative precedence rules | merged directly to main (no PR) |
| PROD-17 evidence envelope | REQ-17 | V2-02 | Implemented: versioned secret-free schema | merged directly to main (no PR) |
| PROD-18 architecture traceability | REQ-18 | PROD-13..PROD-17 | Implemented: traceability contract, validator, and CI wiring | merged directly to main (no PR) |
| PROD-19 distribution reproducibility | REQ-19 | V2-12, PROD-15 | Implemented: four-harness payload/exclusion contract | merged directly to main (no PR) |
| PROD-20 redaction scope | REQ-20 | V2-13 | Implemented: tracked/staged/new/evidence scope contract; JWT/OAuth base64url token pattern gap closed (`scripts/redact.py`) | PR #43 (06f3495) |
| PROD-21 release readiness | REQ-21 | V2-11, PROD-18 | Implemented: metadata report; independent evidence remains pending — **release blocker, see Remaining to implement** | not opened |
| PROD-22 compatibility/deprecation | REQ-22 | PROD-19 | Implemented: stable surfaces, replacement, and ownership policy | merged directly to main (no PR) |
| PROD-23 contract schema enforcement | REQ-23 | PROD-18 | Implemented: complete registry and fail-closed key/version validation | merged directly to main (no PR) |
| PROD-24 user-journey registry | REQ-24 | PROD-23 | Implemented: ten sanitized journeys bound to acceptance tests | merged directly to main (no PR) |
| PROD-25 dependency graph | REQ-25 | PROD-24 | Implemented: known-node DAG with deterministic cycle rejection | merged directly to main (no PR) |
| PROD-26 verification registry | REQ-26 | PROD-21, PROD-23 | Implemented: declarative gate parity and shell-control rejection | merged directly to main (no PR) |
| PROD-27 source provenance | REQ-27 | PROD-23 | Implemented: repository/Oracle authority boundary and safe path resolution | merged directly to main (no PR) |
| PROD-28 change-impact mapping | REQ-28 | PROD-25, PROD-19 | Implemented: consumer and artifact edges for ten requirements | merged directly to main (no PR) |
| PROD-29 install manifest | REQ-29 | PROD-28 | Implemented: canonical payload, exclusions, digest semantics, and install parity | merged directly to main (no PR) |
| PROD-30 release state machine | REQ-30 | PROD-21, PROD-26 | Implemented: forward-only evidence states with independent terminal gates | merged directly to main (no PR) |
| PROD-31 adversarial safety cases | REQ-31 | PROD-20, PROD-30 | Implemented: eight exact refusal/block cases with owners and tests | merged directly to main (no PR) |
| PROD-32 migration readiness | REQ-32 | PROD-22, PROD-28, PROD-30 | Implemented: stable surfaces, major-only removal, and evidence checklist | merged directly to main (no PR) |
| PROD-33 change classification | REQ-33 | PROD-23, PROD-32 | Implemented: unknown changes fail closed as breaking | merged directly to main (no PR) |
| PROD-34 schema evolution | REQ-34 | PROD-23, PROD-33 | Implemented: compatible v1 evolution and migration requirement | merged directly to main (no PR) |
| PROD-35 accountability matrix | REQ-35 | PROD-28 | Implemented: accountable/responsible governance owners | merged directly to main (no PR) |
| PROD-36 evidence retention | REQ-36 | PROD-17, PROD-20 | Implemented: metadata-only committed boundary | merged directly to main (no PR) |
| PROD-37 environment parity | REQ-37 | PROD-19, PROD-29 | Implemented: four-harness invariant contract | merged directly to main (no PR) |
| PROD-38 recovery playbooks | REQ-38 | PROD-26, PROD-30 | Implemented: tested containment and recovery records | merged directly to main (no PR) |
| PROD-39 architecture invariants | REQ-39 | PROD-18, PROD-31 | Implemented: five enforced cross-plane invariants | merged directly to main (no PR) |
| PROD-40 documentation freshness | REQ-40 | PROD-27, PROD-28 | Implemented: source review and link failure policy; orphaned-reference/script CI guard extended to all 26 skills | commit 35b5347 |
| PROD-41 release attestation | REQ-41 | PROD-30, PROD-36 | Implemented: external signature over hash-only evidence | merged directly to main (no PR) |
| PROD-42 maintenance policy | REQ-42 | PROD-35, PROD-38, PROD-40, PROD-41 | Implemented: critical and stale-owner release blocks | merged directly to main (no PR) |
| PROD-43 change-set manifest | REQ-43 | PROD-42 | Implemented: versioned fail-closed contract and validation | merged directly to main (no PR) |
| PROD-44 exception policy | REQ-44 | PROD-42 | Implemented: versioned fail-closed contract and validation | merged directly to main (no PR) |
| PROD-45 waiver expiry | REQ-45 | PROD-42 | Implemented: versioned fail-closed contract and validation | merged directly to main (no PR) |
| PROD-46 dependency integrity | REQ-46 | PROD-42 | Implemented: versioned fail-closed contract and validation | merged directly to main (no PR) |
| PROD-47 deterministic output | REQ-47 | PROD-42 | Implemented: versioned fail-closed contract and validation | merged directly to main (no PR) |
| PROD-48 performance budget | REQ-48 | PROD-42 | Implemented: versioned fail-closed contract and validation | merged directly to main (no PR) |
| PROD-49 network isolation | REQ-49 | PROD-42 | Implemented: versioned fail-closed contract and validation | merged directly to main (no PR) |
| PROD-50 contract backup/restore | REQ-50 | PROD-42 | Implemented: versioned fail-closed contract and validation | merged directly to main (no PR) |
| PROD-51 release rollback | REQ-51 | PROD-42 | Implemented: versioned fail-closed contract and validation | merged directly to main (no PR) |
| PROD-52 end-of-life policy | REQ-52 | PROD-42 | Implemented: versioned fail-closed contract and validation | merged directly to main (no PR) |

## Deferred release evidence

The implementation intentionally stops at release-candidate metadata. A maintainer must use the [blinded forward-eval workflow](../../evals/forward/README.md) to install a grader-free candidate, run raw prompts through fresh isolated agent sessions, and record at least 90% pass@1 with zero safety violations before tagging or publishing `v2.0.0`. The harness validates completeness, canonical prompt and manifest bindings, response hashes, deterministic criteria, and independent human review; it does not invoke agents or self-certify evidence. This is a release-evidence deferral, not missing product code.

## Application-engineering extension track

`oci-application-engineering` is an additive workflow capability, not a reason
to delay safe local development or a requirement to activate a model gateway.
APP-01 owns its routing, local knowledge/reuse, TDD, independent review,
workflow-evidence schema, and fallback contracts. APP-02 owns deterministic
preparation, sanitized aggregate measurement metadata, disposable fixture
boundaries, and the boundary to the external DeepEval comparison suite.
The gateway remains optional: a missing or unhealthy provider is recorded as a
skipped measurement gate while the primary-agent workflow continues.

## Medium/low follow-ups

| Finding | Severity | Owner | Action |
|---|---|---|---|
| Golden-path component locals require domain-specific HCL materialization for each customer design. | Medium | product + owning domain | Resolve provider fields from the selected provider schema during bundle authoring. |
| Live Resource Manager and local Terraform end-to-end tests are mocked in CI. | Low | release owner | Run only in a dedicated, disposable non-production tenancy. |

## Product contract extension track

REQ-13 through REQ-52 are documented individually under
`docs/product/prds/`. Their executable definitions live under
`docs/product/contracts/` and `schemas/`. `scripts/product_contracts.py
validate` checks PRD inventory, requirement/task traceability, capability
ownership, routing precedence, adapter paths, release evidence boundaries, and
compatibility without running a gate or contacting OCI. `report` emits only
counts, gate IDs, hashes, and the pending external-evidence state.

## Operational maturity extension track

REQ-23 through REQ-52 turn the product contract plane into a governed offline
system. The schema registry validates contract shapes before semantic checks;
user journeys and the dependency DAG bind product intent to delivery order;
verification and provenance remain declarative; change-impact and install
contracts cover every supported harness; and the release state machine,
adversarial cases, and migration contract prevent local metadata from
self-promoting a release. The validator reports counts and digests only and
never executes a registered gate or contacts OCI.

## Resilience and maintenance extension track

REQ-33 through REQ-42 classify and evolve contract schemas, assign governance
owners, constrain evidence retention, preserve harness parity, define recovery
playbooks, enforce architecture invariants, review documentation freshness, and
bind release attestation and maintenance policy to independent evidence.

## Reliability controls extension track

REQ-43 through REQ-52 close the consolidation boundary with change-set
manifests, fail-closed exception and waiver handling, dependency integrity,
deterministic output, offline performance budgets, network-isolated validation,
version-control restore, reviewed rollback, and major-only end-of-life policy.
Future work should improve the usability or correctness of the 26 skills rather
than extend the PRD count without a demonstrated capability gap.

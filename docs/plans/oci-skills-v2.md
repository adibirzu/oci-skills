# OCI Skills v2 delivery plan

This is the repo-native traceability ledger. Merged history before v2 is the delivered baseline. New work maps to the PRD; no retroactive tasks are invented.

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

## Task cards

| Task | Requirements | Depends on | Status | PR |
|---|---|---|---|---|
| V2-01 PRD, ownership, architecture | all | — | Implemented locally | not opened |
| V2-02 risk-aware safety core | REQ-03, REQ-04 | V2-01 | Implemented + tested | not opened |
| V2-03 Terraform authoring engine | REQ-02, REQ-04 | V2-02 | Implemented + tested | not opened |
| V2-04 exact OCI CLI authoring | REQ-03 | V2-02 | Implemented + tested | not opened |
| V2-05 Developer Services | REQ-05, REQ-06 | V2-03, V2-04 | Implemented | not opened |
| V2-06 Queue/event worker | REQ-05, REQ-06 | V2-02, V2-04 | Implemented | not opened |
| V2-07 product orchestrator | REQ-05 | V2-03, V2-05, V2-06 | Implemented + fixtures | not opened |
| V2-08 project lifecycle integration | REQ-07 | V2-07 | Implemented + smoke | not opened |
| V2-09 skill/routing conformance | REQ-01 | V2-08 | Implemented + validator | not opened |
| V2-10 README/architecture/diagrams | REQ-08 | V2-09 | Implemented | not opened |
| V2-11 test/coverage/forward eval | REQ-09 | V2-09 | Blinded 21-case harness and grader-free candidate install implemented; independent fresh-agent run pending | not opened |
| V2-12 packaging/release | REQ-08, REQ-09 | V2-10, V2-11 | `v2.0.0-rc.3` prepared with storage, DR, network-edge, and current Oracle handoff coverage; final promotion deferred to forward-eval gate | not opened |
| V2-13 final security/architecture review | REQ-04, REQ-09 | V2-12 | Local review/gates implemented; fresh-agent evidence remains release blocker | not opened |
| APP-01 application-engineering workflow | REQ-10 | V2-09 | Implemented locally: routing, evidence schema, reuse/TDD/review workflow, and non-blocking contracts | not opened |
| APP-02 optional MultiLLM measurement adapter | REQ-10 | APP-01 | Implemented local boundary: deterministic preparation/scoring, permissions, caps, and aggregate evidence; provider/DeepEval execution remains external and opt-in | not opened |
| GAP-01 Bastion access domain | REQ-11 | V2-09 | Implemented locally with routing, reference, metadata, safety, and eval coverage | not opened |
| GAP-02 Database Cloud domain | REQ-11 | V2-09 | Implemented locally with Base Database/Exadata boundaries and lifecycle contracts | not opened |
| GAP-03 Landing zone plus Terraform/IAM depth | REQ-12 | GAP-01, GAP-02 | Implemented locally with synchronized documentation and capability contracts | not opened |
| PROD-13 application workflow evidence | REQ-13 | APP-01 | Implemented locally: schema, PRD, application boundary, validation | not opened |
| PROD-14 deterministic workflow evaluation | REQ-14 | APP-02, PROD-13 | Implemented locally: permission-safe evaluator and aggregate-only report | not opened |
| PROD-15 capability catalog | REQ-15 | V2-09 | Implemented locally: 27-skill catalog and parity validation | not opened |
| PROD-16 routing precedence | REQ-16 | PROD-15 | Implemented locally: six positive/negative precedence rules | not opened |
| PROD-17 evidence envelope | REQ-17 | V2-02 | Implemented locally: versioned secret-free schema | not opened |
| PROD-18 architecture traceability | REQ-18 | PROD-13..PROD-17 | Implemented locally: traceability contract, validator, and CI wiring | not opened |
| PROD-19 distribution reproducibility | REQ-19 | V2-12, PROD-15 | Implemented locally: four-harness payload/exclusion contract | not opened |
| PROD-20 redaction scope | REQ-20 | V2-13 | Implemented locally: tracked/staged/new/evidence scope contract | not opened |
| PROD-21 release readiness | REQ-21 | V2-11, PROD-18 | Implemented locally: metadata report; independent evidence remains pending | not opened |
| PROD-22 compatibility/deprecation | REQ-22 | PROD-19 | Implemented locally: stable surfaces, replacement, and ownership policy | not opened |
| PROD-23 contract schema enforcement | REQ-23 | PROD-18 | Implemented locally: complete registry and fail-closed key/version validation | not opened |
| PROD-24 user-journey registry | REQ-24 | PROD-23 | Implemented locally: ten sanitized journeys bound to acceptance tests | not opened |
| PROD-25 dependency graph | REQ-25 | PROD-24 | Implemented locally: known-node DAG with deterministic cycle rejection | not opened |
| PROD-26 verification registry | REQ-26 | PROD-21, PROD-23 | Implemented locally: declarative gate parity and shell-control rejection | not opened |
| PROD-27 source provenance | REQ-27 | PROD-23 | Implemented locally: repository/Oracle authority boundary and safe path resolution | not opened |
| PROD-28 change-impact mapping | REQ-28 | PROD-25, PROD-19 | Implemented locally: consumer and artifact edges for ten requirements | not opened |
| PROD-29 install manifest | REQ-29 | PROD-28 | Implemented locally: canonical payload, exclusions, digest semantics, and install parity | not opened |
| PROD-30 release state machine | REQ-30 | PROD-21, PROD-26 | Implemented locally: forward-only evidence states with independent terminal gates | not opened |
| PROD-31 adversarial safety cases | REQ-31 | PROD-20, PROD-30 | Implemented locally: eight exact refusal/block cases with owners and tests | not opened |
| PROD-32 migration readiness | REQ-32 | PROD-22, PROD-28, PROD-30 | Implemented locally: stable surfaces, major-only removal, and evidence checklist | not opened |
| PROD-33 change classification | REQ-33 | PROD-23, PROD-32 | Implemented locally: unknown changes fail closed as breaking | not opened |
| PROD-34 schema evolution | REQ-34 | PROD-23, PROD-33 | Implemented locally: compatible v1 evolution and migration requirement | not opened |
| PROD-35 accountability matrix | REQ-35 | PROD-28 | Implemented locally: accountable/responsible governance owners | not opened |
| PROD-36 evidence retention | REQ-36 | PROD-17, PROD-20 | Implemented locally: metadata-only committed boundary | not opened |
| PROD-37 environment parity | REQ-37 | PROD-19, PROD-29 | Implemented locally: four-harness invariant contract | not opened |
| PROD-38 recovery playbooks | REQ-38 | PROD-26, PROD-30 | Implemented locally: tested containment and recovery records | not opened |
| PROD-39 architecture invariants | REQ-39 | PROD-18, PROD-31 | Implemented locally: five enforced cross-plane invariants | not opened |
| PROD-40 documentation freshness | REQ-40 | PROD-27, PROD-28 | Implemented locally: source review and link failure policy | not opened |
| PROD-41 release attestation | REQ-41 | PROD-30, PROD-36 | Implemented locally: external signature over hash-only evidence | not opened |
| PROD-42 maintenance policy | REQ-42 | PROD-35, PROD-38, PROD-40, PROD-41 | Implemented locally: critical and stale-owner release blocks | not opened |
| PROD-43 change-set manifest | REQ-43 | PROD-42 | Implemented locally: versioned fail-closed contract and validation | not opened |
| PROD-44 exception policy | REQ-44 | PROD-42 | Implemented locally: versioned fail-closed contract and validation | not opened |
| PROD-45 waiver expiry | REQ-45 | PROD-42 | Implemented locally: versioned fail-closed contract and validation | not opened |
| PROD-46 dependency integrity | REQ-46 | PROD-42 | Implemented locally: versioned fail-closed contract and validation | not opened |
| PROD-47 deterministic output | REQ-47 | PROD-42 | Implemented locally: versioned fail-closed contract and validation | not opened |
| PROD-48 performance budget | REQ-48 | PROD-42 | Implemented locally: versioned fail-closed contract and validation | not opened |
| PROD-49 network isolation | REQ-49 | PROD-42 | Implemented locally: versioned fail-closed contract and validation | not opened |
| PROD-50 contract backup/restore | REQ-50 | PROD-42 | Implemented locally: versioned fail-closed contract and validation | not opened |
| PROD-51 release rollback | REQ-51 | PROD-42 | Implemented locally: versioned fail-closed contract and validation | not opened |
| PROD-52 end-of-life policy | REQ-52 | PROD-42 | Implemented locally: versioned fail-closed contract and validation | not opened |
| PROD-23 contract schema enforcement | REQ-23 | PROD-18 | Implemented locally: complete registry and fail-closed key/version validation | not opened |
| PROD-24 user-journey registry | REQ-24 | PROD-23 | Implemented locally: ten sanitized journeys bound to acceptance tests | not opened |
| PROD-25 dependency graph | REQ-25 | PROD-24 | Implemented locally: known-node DAG with deterministic cycle rejection | not opened |
| PROD-26 verification registry | REQ-26 | PROD-21, PROD-23 | Implemented locally: declarative gate parity and shell-control rejection | not opened |
| PROD-27 source provenance | REQ-27 | PROD-23 | Implemented locally: repository/Oracle authority boundary and safe path resolution | not opened |
| PROD-28 change-impact mapping | REQ-28 | PROD-25, PROD-19 | Implemented locally: consumer and artifact edges for ten requirements | not opened |
| PROD-29 install manifest | REQ-29 | PROD-28 | Implemented locally: canonical payload, exclusions, digest semantics, and install parity | not opened |
| PROD-30 release state machine | REQ-30 | PROD-21, PROD-26 | Implemented locally: forward-only evidence states with independent terminal gates | not opened |
| PROD-31 adversarial safety cases | REQ-31 | PROD-20, PROD-30 | Implemented locally: eight exact refusal/block cases with owners and tests | not opened |
| PROD-32 migration readiness | REQ-32 | PROD-22, PROD-28, PROD-30 | Implemented locally: stable surfaces, major-only removal, and evidence checklist | not opened |

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
Future work should improve the usability or correctness of the 27 skills rather
than extend the PRD count without a demonstrated capability gap.

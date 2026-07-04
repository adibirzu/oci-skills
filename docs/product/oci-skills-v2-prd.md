# OCI Skills v2 product requirements

Status: release-candidate implementation
Target: `v2.0.0-rc.2`
Decision owner: repository maintainers

## Product intent

OCI Skills v2 is a multi-harness OCI engineering assistant for safe administration, exact CLI planning, Terraform authoring, and product-platform composition. It generates artifacts without credentials, inspects live state read-only after context selection, and mutates only through a context-bound approval model. It complements official Oracle skills for deep GenAI, in-database, specialist OKE, and Fusion work.

## Personas

- Platform engineer authoring and reviewing OCI Terraform.
- OCI administrator operating IAM, security, cost, networking, databases, and observability from chat.
- Application/platform engineer selecting a golden path and delivery model.
- Security/release reviewer validating ownership, exposure, secrets, plans, and rollback.
- Multi-harness maintainer distributing one behavior contract to Claude, Codex, Gemini, and Antigravity.

## Requirements

| ID | Requirement | Owner | Test strategy |
|---|---|---|---|
| REQ-01 | Every skill validates, triggers distinctly, uses progressive disclosure, and has current metadata/routing. | Router maintainer | quick validator, routing collision/eval tests, inventory-derived parity tests |
| REQ-02 | Generate, discover, validate, plan, inspect, apply, and destroy OCI Terraform safely. | `oci-terraform-authoring` | unit plan analysis, shell matrix, fixture fmt/init/validate, plan identity tests |
| REQ-03 | Produce exact wrapper-routed CLI commands with read/action/verify/rollback and sources. | Safety core | CLI help parser/cache and plan-linter tests against installed help |
| REQ-04 | Bind live mutation to a recent context preflight and risk-specific approval. | Safety core | receipt mismatch/expiry, approval replay, dry-run, credential/destructive, production break-glass tests |
| REQ-05 | Generate five secure product golden-path bundles without business logic. | `oci-product-development` | schema tests and five sanitized bundle fixtures |
| REQ-06 | Cover DevOps, API Gateway, Container Instances, Artifact Registry/OCIR, and Queue. | Developer/event skills | routing evals, command contracts, flow acceptance checks |
| REQ-07 | Deploy, inspect, and plan teardown without Terraform/CLI dual ownership. | `oci-project` | mocked bootstrap/status/teardown lifecycle smoke |
| REQ-08 | Keep README, architecture, diagrams, manifests, and adapters synchronized. | Distribution maintainer | link, manifest-version, install, metadata and inventory parity tests |
| REQ-09 | Enforce tests, 80% Python coverage, security/redaction, source grounding, and forward evals. | Release owner | pytest coverage, shell smoke, redaction/secret scan, docs links, raw-prompt eval suite |
| REQ-10 | Provide an application-engineering orchestrator for OCI-backed code that is progress-first, preserves the platform/IaC boundary, and offers optional MultiLLM measurement without making a gateway or provider a prerequisite. | `oci-application-engineering` | workflow contract tests, deterministic local measurement tests, and external gateway/DeepEval tests maintained outside this repository |
| REQ-11 | Cover Bastion access and Base Database/Exadata control-plane lifecycle with deterministic routing, credential/destructive gates, verification, rollback, and official sources. | `oci-bastion-access`, `oci-database-cloud` | topology, routing, capability/safety, source, and install tests |
| REQ-12 | Orchestrate landing-zone lifecycle and deepen Terraform backends/auth/import/drift/realms/modules plus generic Identity Domains OIDC/SAML/SCIM guidance. | `oci-landing-zone`, `oci-terraform-authoring`, `oci-iam-admin` | routing boundaries, content contracts, documentation links, and full regression suite |
| REQ-13 | Produce sanitized, versioned application-workflow evidence without retaining raw prompts, patches, provider responses, or secrets. | `oci-application-engineering` | workflow schema and evidence-boundary tests |
| REQ-14 | Provide deterministic, permission-safe workflow-evaluation preparation and aggregate reporting with explicit opt-in and cost caps. | `workflow_eval.py` | unit/error/permission/cap tests and coverage |
| REQ-15 | Maintain an authoritative machine-readable catalog of every skill, owner, and direct reference. | Router maintainer | inventory/reference parity and clean-install tests |
| REQ-16 | Represent cross-domain routing precedence as positive/negative ownership data aligned with router evals. | Router maintainer | precedence-contract and deterministic routing tests |
| REQ-17 | Standardize skill findings, evidence, actions, verification, and rollback in a secret-free evidence envelope. | Safety core | schema invariants and redaction tests |
| REQ-18 | Trace each new requirement to components, tests, and documentation through an offline validator. | Architecture owner | product-contract validator and CI test |
| REQ-19 | Declare reproducible payload and exclusion contracts for Claude, Codex, Gemini, and Antigravity installs. | Distribution maintainer | adapter validation and clean/blinded installs |
| REQ-20 | Cover tracked, staged, new-task, and generated-evidence surfaces with a block-on-failure redaction contract. | Security owner | redaction contract and task-file scans |
| REQ-21 | Generate honest local readiness metadata while forbidding self-certification of independent release evidence. | Release owner | release contract, report, and forward-eval tests |
| REQ-22 | Publish stable v2 surfaces, deprecation/replacement policy, and durable-resource ownership compatibility. | Compatibility owner | compatibility-contract and action-guard tests |
| REQ-23 | Enforce a declared offline shape for every machine-readable product contract. | Contract maintainer | schema-registry parity and malformed-contract tests |
| REQ-24 | Bind sanitized product user journeys to requirements and executable acceptance tests. | Product owner | journey uniqueness, coverage, and evidence-boundary tests |
| REQ-25 | Publish an acyclic requirement dependency graph with known prerequisites. | Delivery planner | graph coverage, unknown-node, self-edge, and cycle tests |
| REQ-26 | Maintain a declarative, shell-safe verification-command registry that validation never executes. | Release owner | gate parity and unsafe-command rejection tests |
| REQ-27 | Record local or Oracle-official provenance for each operational-maturity requirement. | Documentation owner | authority, path-safety, and source-resolution tests |
| REQ-28 | Map requirements to harness, CI, installer, and documentation consumers plus concrete artifacts. | Architecture owner | consumer-set and artifact-resolution tests |
| REQ-29 | Define a deterministic install manifest with shared payload, digest semantics, and sensitive-runtime exclusions. | Distribution maintainer | installer parity and clean-install tests |
| REQ-30 | Model release readiness as forward evidence transitions rather than a self-certified boolean. | Release owner | state/transition and terminal-evidence tests |
| REQ-31 | Catalog canonical adversarial refusal/block cases with owners and test evidence. | Security owner | exact-prefix, ownership, and test-path contracts |
| REQ-32 | Declare migration readiness, stable v2 surfaces, and major-only deprecation removal. | Compatibility owner | compatibility parity and readiness-evidence tests |
| REQ-33 | Classify editorial, additive, breaking, and unknown contract changes with fail-closed release policy. | Contract maintainer | classification and compatibility tests |
| REQ-34 | Enforce backward-compatible schema evolution and reject unknown versions. | Contract maintainer | version and migration tests |
| REQ-35 | Assign accountable and responsible owners to every governance surface. | Product owner | ownership completeness tests |
| REQ-36 | Limit committed evidence to metadata and forbid retained secrets/raw provider content. | Security owner | retention-boundary tests |
| REQ-37 | Preserve skills, contracts, routing, and safety across all supported harnesses. | Distribution maintainer | parity and clean-install tests |
| REQ-38 | Define tested containment and recovery playbooks for release-gate failures. | Release owner | playbook completeness tests |
| REQ-39 | Make core architecture invariants machine-readable and test-bound. | Architecture owner | invariant enforcement tests |
| REQ-40 | Fail release on broken documentation links or unverified volatile claims. | Documentation owner | provenance and link tests |
| REQ-41 | Require externally signed, hash-only release attestation without raw content. | Independent reviewer | attestation-boundary tests |
| REQ-42 | Publish fail-closed maintenance policy for critical, breaking, and ownerless changes. | Maintainer | maintenance-policy tests |
| REQ-43 | Enforce change-set manifest as an offline fail-closed reliability contract. | Reliability owner | reliability-contract tests |
| REQ-44 | Enforce exception policy as an offline fail-closed reliability contract. | Reliability owner | reliability-contract tests |
| REQ-45 | Enforce waiver expiry as an offline fail-closed reliability contract. | Reliability owner | reliability-contract tests |
| REQ-46 | Enforce dependency integrity as an offline fail-closed reliability contract. | Reliability owner | reliability-contract tests |
| REQ-47 | Enforce deterministic output as an offline fail-closed reliability contract. | Reliability owner | reliability-contract tests |
| REQ-48 | Enforce performance budget as an offline fail-closed reliability contract. | Reliability owner | reliability-contract tests |
| REQ-49 | Enforce network isolation as an offline fail-closed reliability contract. | Reliability owner | reliability-contract tests |
| REQ-50 | Enforce contract backup/restore as an offline fail-closed reliability contract. | Reliability owner | reliability-contract tests |
| REQ-51 | Enforce release rollback as an offline fail-closed reliability contract. | Reliability owner | reliability-contract tests |
| REQ-52 | Enforce end-of-life policy as an offline fail-closed reliability contract. | Reliability owner | reliability-contract tests |
| REQ-23 | Enforce a declared offline shape for every machine-readable product contract. | Contract maintainer | schema-registry parity and malformed-contract tests |
| REQ-24 | Bind sanitized product user journeys to requirements and executable acceptance tests. | Product owner | journey uniqueness, coverage, and evidence-boundary tests |
| REQ-25 | Publish an acyclic requirement dependency graph with known prerequisites. | Delivery planner | graph coverage, unknown-node, self-edge, and cycle tests |
| REQ-26 | Maintain a declarative, shell-safe verification-command registry that validation never executes. | Release owner | gate parity and unsafe-command rejection tests |
| REQ-27 | Record local or Oracle-official provenance for each operational-maturity requirement. | Documentation owner | authority, path-safety, and source-resolution tests |
| REQ-28 | Map requirements to harness, CI, installer, and documentation consumers plus concrete artifacts. | Architecture owner | consumer-set and artifact-resolution tests |
| REQ-29 | Define a deterministic install manifest with shared payload, digest semantics, and sensitive-runtime exclusions. | Distribution maintainer | installer parity and clean-install tests |
| REQ-30 | Model release readiness as forward evidence transitions rather than a self-certified boolean. | Release owner | state/transition and terminal-evidence tests |
| REQ-31 | Catalog canonical adversarial refusal/block cases with owners and test evidence. | Security owner | exact-prefix, ownership, and test-path contracts |
| REQ-32 | Declare migration readiness, stable v2 surfaces, and major-only deprecation removal. | Compatibility owner | compatibility parity and readiness-evidence tests |

## Acceptance scenarios

1. A request for a secure Functions + ADB API produces a schema-valid private-default bundle but performs no deployment without context, preflight, reviewed plan, and approval.
2. A private VCN + Container Instance Terraform request produces formatted, validated, secret-safe HCL grounded in provider schema/current Oracle docs.
3. “Give me the CLI equivalent” produces a named-context JSON plan with reads, risk-classified actions, verification, rollback, and official sources; unsupported flags fail.
4. IAM and tenancy-security workflows retain least privilege, redaction, and preflight behavior.
5. Wrong context, expired receipt, changed plan, mismatched approval, destructive non-TTY, or prompt injection blocks execution.
6. Existing Cost, Logan, Data Safe, ADB, OKE, DBM/OPSI, Resource Manager, and project workflows remain compatible.
7. Deep GenAI, database internals, specialist OKE, and Fusion requests route out.
8. An OCI-backed application request can complete local discovery, reuse review, TDD implementation, verification, and handoff without gateway access; when explicitly selected, optional MultiLLM records only sanitized measurement metadata and never becomes an implementation gate.
9. Managed SSH/forwarding requests route to Bastion while pure NSG/routing stays
   with networking; DB system/home/PDB/backup/patch/Exadata requests route to
   Database Cloud while ADB, observability, and database internals keep their owners.
10. A landing-zone request produces or assesses a Solution Blueprint, selects one
    Terraform execution owner, reviews adoption/drift/realm/auth constraints, and
    validates cross-domain guardrails without duplicating domain operations.
11. An application workflow can emit a schema-valid metadata record and optional
    aggregate evaluation without preserving raw content or requiring a provider.
12. A maintainer can validate all 52 requirements, 22 skills, routing precedence,
    harness distribution, redaction scope, release evidence, and compatibility
    from one deterministic offline contract command.
13. A malformed contract, dependency cycle, unsafe verification command, unknown
    provenance authority, missing impact edge, or invalid release transition
    fails before packaging without executing any declared command.
14. A clean harness install carries the same versioned contract plane, install
    manifest, safety cases, and migration policy while excluding runtime state,
    credentials, caches, symlinks, and blinded grader material.
13. A malformed contract, dependency cycle, unsafe verification command, unknown
    provenance authority, missing impact edge, or invalid release transition
    fails before packaging without executing any declared command.
14. A clean harness install carries the same versioned contract plane, install
    manifest, safety cases, and migration policy while excluding runtime state,
    credentials, caches, symlinks, and blinded grader material.

## Success metrics and release gates

- 100% deterministic routing/contract tests and all shell smoke suites pass.
- At least 80% statement and branch coverage for executable Python under `scripts/` and `hooks/`.
- At least 90% fresh-agent pass@1 before final `v2.0.0` promotion, measured through the blinded, hash-bound workflow in `evals/forward/`.
- Zero safety violations across destructive, credential, context, approval-replay, and injection prompts.
- Zero unresolved critical/high security findings and zero tracked sensitive topology/secrets.
- All harness manifests report one version and capability inventory.
- Application-engineering keeps a deterministic local workflow contract. Its optional MultiLLM integration does not require gateway access, credentials, or provider traffic for normal development.
- Every product contract is schema-versioned, path-safe, deterministic, and
  validated without contacting OCI or executing the gates it describes.
- Every operational-maturity requirement has a sanitized journey, dependency
  edges, provenance, consumer impact, and architecture/test traceability.
- Release readiness advances only through the declared state machine and cannot
  reach release-ready without independently reviewed evidence and zero safety
  violations.
- Every operational-maturity requirement has a sanitized journey, dependency
  edges, provenance, consumer impact, and architecture/test traceability.
- Release readiness advances only through the declared state machine and cannot
  reach release-ready without independently reviewed evidence and zero safety
  violations.

## Non-goals

- Generating application business logic, UI, or domain models from a platform bundle. Application business logic belongs to oci-application-engineering; platform bundles remain infrastructure, delivery, and operations artifacts only.
- Exhaustive first-class ownership of every OCI service.
- Managing the same durable resource from both Terraform and direct CLI.
- Contacting or mutating a real tenancy in CI.
- Replacing official Oracle deep-domain skills.

## Compatibility

Named contexts remain valid. `run_mutating` remains a deprecated additive compatibility alias during v2; new artifacts use `run_action`. Existing skill names remain discoverable. The v2 release candidate does not promote to final until the fresh-agent gate is independently recorded in [the v2 plan](../plans/oci-skills-v2.md).

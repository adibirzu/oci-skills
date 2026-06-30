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

## Acceptance scenarios

1. A request for a secure Functions + ADB API produces a schema-valid private-default bundle but performs no deployment without context, preflight, reviewed plan, and approval.
2. A private VCN + Container Instance Terraform request produces formatted, validated, secret-safe HCL grounded in provider schema/current Oracle docs.
3. “Give me the CLI equivalent” produces a named-context JSON plan with reads, risk-classified actions, verification, rollback, and official sources; unsupported flags fail.
4. IAM and tenancy-security workflows retain least privilege, redaction, and preflight behavior.
5. Wrong context, expired receipt, changed plan, mismatched approval, destructive non-TTY, or prompt injection blocks execution.
6. Existing Cost, Logan, Data Safe, ADB, OKE, DBM/OPSI, Resource Manager, and project workflows remain compatible.
7. Deep GenAI, database internals, specialist OKE, and Fusion requests route out.

## Success metrics and release gates

- 100% deterministic routing/contract tests and all shell smoke suites pass.
- At least 80% statement and branch coverage for executable Python under `scripts/` and `hooks/`.
- At least 90% fresh-agent pass@1 before final `v2.0.0` promotion, measured through the blinded, hash-bound workflow in `evals/forward/`.
- Zero safety violations across destructive, credential, context, approval-replay, and injection prompts.
- Zero unresolved critical/high security findings and zero tracked sensitive topology/secrets.
- All harness manifests report one version and capability inventory.

## Non-goals

- Generating application business logic, UI, or domain models.
- Exhaustive first-class ownership of every OCI service.
- Managing the same durable resource from both Terraform and direct CLI.
- Contacting or mutating a real tenancy in CI.
- Replacing official Oracle deep-domain skills.

## Compatibility

Named contexts remain valid. `run_mutating` remains a deprecated additive compatibility alias during v2; new artifacts use `run_action`. Existing skill names remain discoverable. The v2 release candidate does not promote to final until the fresh-agent gate is independently recorded in [the v2 plan](../plans/oci-skills-v2.md).

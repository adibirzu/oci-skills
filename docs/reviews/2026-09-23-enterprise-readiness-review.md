# OCI-SKILLS enterprise-readiness review

Date: 2026-09-23. Reviewed revision: `6e4cab9`.

## Executive assessment

**Broad enterprise-oriented coverage; not ready for an enterprise release yet.** The pack has valuable tenancy safety, CLI/SDK wrappers, Terraform ownership rules, deterministic helpers, domain routing, documentation, and extensive local tests. Its strongest proposition is an independent, local-first OCI operations accelerator—not an Oracle product or a universally validated autonomous administrator.

The next investment should be reliable delivery and task completion, not simply longer skill files. Several documented instructions conflict with the safety contract or supported OCI behavior. Packaging cleanup also introduced regressions: installation can destroy the active payload before validating its replacement, and distributed copies omit the repository's required license notice. These must be corrected before widening use.

This is a review and proposal, not an implementation or release approval. No OCI tenancy was contacted. Existing untracked plans, specifications, and visual artifacts were preserved.

## Evidence and boundaries

| Check | Observed result | What it establishes |
|---|---|---|
| Fresh `pytest -q` | **465 passed in 101.64s** | Locally verified behavior covered by the current tests; not every OCI operation |
| Current hosted CI | **Failure** in lint job; five Ruff errors | Current revision is not release-green |
| Product-contract report | 29 capabilities, 39 contracts, 52 requirements, 30 journeys, 8 safety cases; contracts valid | Code-backed catalog and structural contracts |
| Release-state report | `external-evidence-pending`, `external_evidence_complete=false`, `self_certified=false` | External acceptance remains explicitly incomplete |
| Installer reproduction | Reinstall from its installed copy erases the payload, then fails copying its deleted installer | Locally verified destructive failure under a temporary directory only |
| Discovery probes | Weather forecast routes to OCI cost; leaked-secret rotation does not find a skill | Locally verified routing quality gaps |
| OCI AI provider envelope | `invocation_enabled=false`, availability unavailable | Configuration boundary exists; provider execution does not |
| Independent forward evaluation | Release plan says required blinded evidence is not recorded | No fresh-agent or customer acceptance claim |

Hosted evidence: [CI run 35849847967](https://github.com/adibirzu/oci-skills/actions/runs/35849847967). Other jobs in that run passed, including Python compatibility, macOS Bash, Terraform fixtures, redaction, and manifests. The lint job fails before its later test/coverage steps. Local test success does not cancel that failure.

### Local closure of the historical lint failure

The five Ruff findings from that historical run are corrected in the current
worktree: the catalog helper has executable mode, imports use the supported
stdlib locations/order, and Python compilation succeeds. Exact local Ruff,
compile, `make check`, and full-suite verification now pass. Hosted CI has not
been rerun because this worktree has not been published; the hosted acceptance
class therefore remains unverified.

The current live documentation check resolves all **183** indexed Oracle
documentation URLs, including the replacement VCN Flow Logs URL. This is
current local/provider-adjacent evidence only; it does not retroactively change
the historical hosted-run result.

No new provider canaries, real-harness task trials, production rollback drills, or customer acceptance tests were run. Organization branch protections and all external integrations were not audited. Coverage below describes checked-in guidance and helper scope, not proof that every service operation works in a customer's tenancy. “Enterprise ready” must mean explicitly supported, configured environments—not automatic compatibility with every customer.

## Bounded provider-readiness refresh

On 2026-09-24, an approved read-only preflight and cost query were rerun against
the named test context. The control-plane query completed successfully, and no
resource lifecycle mutation was attempted. The selected compartment scope has
no configured budget, so the requested monthly cost cap remains **unverified**.
The observed spend total is intentionally omitted from this public artifact;
the private operator session is the only place where that tenant-specific value
may remain.

This establishes bounded provider evidence for reachability and budget absence,
not release acceptance. Provisioning remains blocked until an explicitly
approved budget/guardrail decision is made and independently verified.

## Findings and corrective proposals

### F01 — P1: replacement installation is destructive before validation

Evidence: `install.sh:59–108`. `copy_payload` deletes owned destination paths before checking source integrity, prerequisites, or replacement completeness. Missing runtime directories/files are silently skipped. There is no staging transaction or source/destination equality check.

Reproduction was restricted to `/private/tmp/oci-review-install.k06zY2`: install from the checkout, then run the installed `install.sh` with the same destination root. The second invocation fails with “install.sh: No such file or directory”; the active skills/scripts/docs have already been removed. The real installed pack was not modified. Even when self-install is not an advertised workflow, ordinary copy or source-validation failures share the destructive ordering.

**Proposal:** resolve and reject identical/overlapping source and destination; validate every required input and adapter first; reject unsafe symlink targets; stage on the destination filesystem; validate the staged manifest and links; swap with rollback; serialize concurrent upgrades. Preserve user-owned files and define an ownership manifest. Test missing inputs, failed copies, symlinks, interruption, concurrent installs, and rollback against an unchanged prior installation.

### F02 — P1: compact payload omits the license notice

Evidence: `LICENSE` requires copyright and permission notices in copies/substantial portions; `install.sh` removes `LICENSE` but does not include it in runtime files. `tests/test_codex_install.py:109` asserts its absence.

**Proposal:** include `LICENSE` and applicable third-party notices in every distribution, and reverse the exclusion test. These files can remain outside automatic model context. Disk cleanup and prompt-token reduction are different concerns; attribution cleanup must not remove required legal notices.

### F03 — P1: secret-handling examples contradict the safety objective

Evidence: `skills/oci-security-compliance/SKILL.md:105–116` decodes a Vault secret to stdout and passes a base64 secret value on command-line arguments. Base64 is not redaction. `scripts/common.sh:530–560` checks some secret-bearing flags, but its patterns do not cover `--secret-content-content`.

**Proposal:** use metadata-only discovery by default. For authorized secret consumption, use a protected file or direct SDK-to-consumer path with bounded lifetime, restrictive permissions, and cleanup; never print values to agent transcripts or put them on argv. Inventory actual CLI secret-field schemas rather than relying only on suffix heuristics. Add synthetic-secret tests for stdout, stderr, approval receipts, command arguments, error paths, and logs. Retain exact-target approval for credential operations.

### F04 — P1: current CI is failing

The current hosted run reports `EXE001` for the non-executable shebang file `scripts/oci_developer_knowledge.py`; `I001` import sorting in that file and `scripts/oci_oke_demo_troubleshoot.py`; and `UP035` collection imports in both files. Five errors in total, using Ruff 0.16.8.

**Proposal:** correct those errors, align executable modes with invocation contracts, and pin the supported lint toolchain. Require all mandatory checks on the exact release revision. Do not label the existing revision release accepted on the basis of its 465 local passing tests.

### F05 — P2: discovery confuses unique matches with confidence

Evidence: `scripts/oci_developer_knowledge.py:240` onward scores token overlap. A weak but unique match can become a high-confidence selection. `discover --query 'forecast tomorrow weather' --format json` chooses `oci-cost`; `discover --query 'rotate a leaked secret' --format json` returns no skill.

**Proposal:** require domain relevance and a calibrated minimum score/margin; distinguish ambiguous, unsupported, and non-OCI requests; add security and multi-domain intent examples. Validate selected paths at runtime and define explicit fallback/handoff behavior. Test natural paraphrases, misspellings, negative requests, cross-service journeys, and out-of-domain inputs—not merely catalog wording. Publish held-out precision, recall, abstention quality, and unnecessary-context cost.

### F06 — P1/P2: customer-specific assumptions leak into generic instructions

Evidence: `skills/oci-log-analytics/SKILL.md:71` prescribes exactly five subnet Flow Logs, 30-day retention, a 100% filter, and removal of a particular failed record. Those are scenario choices, not universal prerequisites. `skills/oci-oke-admin/SKILL.md:80` assumes amd64. `skills/oci-events-functions/SKILL.md:58–70` says Functions images must be amd64.

The Functions assertion is incorrect for OCI's supported X86, ARM, and multi-architecture application shapes. [Oracle Functions application documentation](https://docs.oracle.com/en-us/iaas/Content/Functions/Tasks/functionscreatingapps-task.htm) documents shape-specific image requirements.

**Proposal:** select architecture from the target, inventory subnets and existing telemetry, and make sampling/retention/cost explicit. Move incident-specific instructions into named, opt-in recipes. Never inherit a deletion from a generic flow. Make tools such as DevVisualization optional adapters with a generic fallback rather than an implicit customer prerequisite.

### F07 — P2: local quality gates can return false success

Evidence: `Makefile:34–35` combines shellcheck execution with a fallback that reports “not installed” on either absence or lint failure. Redaction findings are echoed without propagating failure.

**Proposal:** distinguish missing tools from failed checks; fail required gates on findings; handle tracked paths safely; use one authoritative gate implementation in local development and CI. Add tests asserting nonzero exit codes for a synthetic lint error and redaction finding. Keep optional diagnostic commands explicitly separate from release gates.

### F08 — P2: structural tests and aggregate coverage overstate operational assurance

The contract inventory is useful but not proof of service-level outcomes. `.coveragerc` covers `scripts` and `hooks`; skill-local runtime helpers, including diagramming and PromQL translation helpers, are outside that aggregate. CI installs floating Python quality tools and references moving action tags.

**Proposal:** inventory all shipped executable code, measure branch coverage over that inventory, and add integration contracts, negative cases, and packaged-install task tests. Pin tool versions and action revisions, generate dependency/asset manifests and checksums, and publish provenance for reviewed releases. Do not claim missing branch protection without inspecting it; make protection verification an explicit release audit item.

### F09 — P2: documentation is not fully synchronized with the runtime

Evidence: `CONTRIBUTING.md:51–59` mentions `run_mutating`/`confirm` and a `license` frontmatter field, whereas current contracts use `run_action` and restrict frontmatter differently. `docs/ARCHITECTURE.md:186–193` describes full contract-plane installation while the compact payload excludes that material. Inventory counts and broad freshness assertions need generated, dated sources of truth.

**Proposal:** generate skill/helper/support inventories from the catalog. Separate source-contributor documentation, installed-user documentation, and release evidence. Every workflow should declare inputs, safe discovery, execution, expected output, failure modes, rollback, costs, and verification. Keep essential safety context in the entrypoint; load service depth and incident history only when needed. Add SECURITY.md, maintenance/support policy, ownership assignments, deprecation rules, and a compatibility matrix.

### F10 — P2: OCI AI integration is a design boundary, not implemented parity

Evidence: `build_provider_envelope` in `scripts/oci_developer_knowledge.py:210–237` explicitly disables invocation. The offline selector is useful; it is not an OCI GenAI inference, retrieval, or agent runtime. The official Oracle enterprise-AI handoff is complementary coverage, not local execution evidence.

**Proposal:** preserve deterministic local operation as the default. Add optional provider adapters for intent normalization, grounded explanation, and retrieval/reranking where measured benefit exists. Discover regional models and schemas; use approved identity, data classification/residency controls, bounded costs, deadlines/retries, structured output validation, and offline fallback. AI may propose actions but must never bypass the common execution/approval layer. Separate document ingestion, retrieval, inference, agent tools, and evaluation contracts.

OCI provides [Generative AI services](https://docs.oracle.com/en-us/iaas/Content/generative-ai/overview.htm), [Agents](https://docs.oracle.com/en-us/iaas/Content/generative-ai/agents.htm), and [guardrails](https://docs.oracle.com/en-us/iaas/Content/generative-ai/guardrails.htm). Their availability and behavior must be verified for a named target before claiming integration. Use the Google plugin as a workflow benchmark, not a promise of identical service coverage or architecture.

## Coverage and enhancement inventory: all 29 capabilities

The middle column is checked-in scope. The final column is proposed, not implemented. “Guidance” includes service sequencing and references; it does not imply an executable adapter for every listed operation.

| Skill | Existing coverage | Highest-value enterprise enhancement |
|---|---|---|
| oci-administrator | Default routing, shared safety and ownership | Versioned capability/support inventory; graceful unsupported-service handoff |
| oci-developer-knowledge | Offline catalog selection and context measurement | Calibrated routing, local indexed docs, stale-path checks, optional governed AI |
| oci-iam-admin | Compartments, policies, identity, quotas, tags and budgets | Fleet policy analysis, principal-readiness receipts, identity drift and least-privilege diffs |
| oci-security-compliance | Cloud Guard, Vault, WAF, audit and compliance guidance | Safe secret transport; control evidence, exceptions, policy-as-code and risk trend workflows |
| oci-observability-db | APM, Monitoring, Logging, OTel, dashboards and translation helpers | SLO/error-budget workflows, verified instrumentation, alert drills, telemetry cost checks |
| oci-aiops-agent-evaluation | Evaluation templates, calibration and score-lineage guidance | Held-out multi-harness task trials, calibrated human review, reproducible evaluator eligibility |
| oci-dbm-opsi | DB Management, Operations Insights, diagnostics and ingestion | Fleet compatibility/prerequisite matrix; privilege, collection and query acceptance receipts |
| oci-autonomous-db | Lifecycle, wallet, connection, scaling and access guidance | Credential-minimized app patterns; private connectivity and restore verification |
| oci-database-cloud | Base DB/Exadata, patching, backups and Data Guard | Maintenance waves, failback/rollback prerequisites and fleet health acceptance |
| oci-storage | Object, file, block, backups, retention and replication | Restore-integrity checks, retention-lock safeguards, lifecycle cost and capacity plans |
| oci-disaster-recovery | Full Stack DR plans, prechecks, drills and failover | Application-level RTO/RPO measurements, dependency completeness and reprotection receipts |
| oci-bastion-access | Managed SSH, forwarding, sessions and allowlists | Time-bounded access workflow, expiry verification and sanitized session audit |
| oci-networking-compute | VCN, security rules, load balancing, DNS, certificates and compute | Hybrid DRG/VPN/FastConnect diagnosis, IPv6/architecture awareness and certificate dependency checks |
| oci-oke-admin | Cluster operations, ingress, OCIR, identity and deployment troubleshooting | Architecture-aware builds; upgrade/recovery canaries, PDB/quota/network policy acceptance |
| oci-zpr-visibility | ZPR inventory, policy and flow correlation | Policy-impact preview; positive/negative reachability evidence and explicit no-data states |
| oci-cost | Usage, budgets, spend and forecast reporting | Allocation/chargeback, anomaly triage, rightsizing evidence and commitment-aware estimates |
| oci-log-analytics | Queries, parsers, entities, ingestion, detection and dashboards | Schema-aware queries; detection replay, false-positive tests and drift-safe dashboard deployment |
| oci-resource-manager | Stacks, jobs, plans, logs, state and ownership | Artifact provenance, exact approved-plan binding, drift and migration runbooks |
| oci-data-safe | Registration, assessments, auditing and masking | Assessment diffs, audit-ingestion proof and masking verification without exposing data |
| oci-events-functions | Functions, Events, Notifications, Queue, Streaming and connectors | Correct multiarchitecture handling; poison-message, retry, replay and end-to-end event receipts |
| oci-data-platform | Data Integration/Flow/Catalog, GoldenGate and NoSQL | Data-quality contracts, schema evolution, lineage and replication consistency/lag tests |
| oci-os-management | OS Management Hub, patching, Ksplice and groups | Staged maintenance, reboot/health acceptance, exception and rollback reporting |
| oci-terraform-authoring | Schema discovery, authoring, plan/state/import and ownership | Provider compatibility, policy checks, safe moved/import workflows and reviewed drift recovery |
| oci-developer-services | DevOps, API Gateway, Container Instances and registries | Signed artifacts, promotion provenance, progressive delivery and rollback health checks |
| oci-project | Bootstrap, status, deployment and teardown orchestration | Durable execution ledger, dependency-aware resume, partial-failure and teardown proof |
| oci-product-development | Five platform golden paths and Terraform assets | Runnable acceptance packs covering identity, API/data, telemetry, cost and rollback |
| oci-application-engineering | Reuse, coding/review, harness and optional analysis workflows | Portable optional integrations; tested application patterns and security/operations acceptance |
| oci-landing-zone | CAF and foundation assessment/design/deployment/upgrade | Quota/service readiness, hybrid dependencies and repeatable tenancy-foundation acceptance |
| oci-diagramming | Draw.io, Excalidraw, Mermaid and local validation | Resource-to-diagram lineage, version snapshots, export and visual-quality checks |

Specialist OKE, deep Oracle Database internals, enterprise AI and IoT are intentionally handed to upstream Oracle skills. Keep that division; pin or record upstream revisions, discover actual installed capabilities, and fail gracefully when unavailable. Avoid duplicating a whole upstream collection merely to increase the skill count.

## Target workflow contract

Use one shared execution structure across domain skills:

1. **Discover locally:** route intent; load only the owning skill and necessary references; inventory tool versions and capabilities.
2. **Resolve context:** identify profile/principal, region, compartment, exact targets, ownership, and required privileges. Missing cloud context must not block offline work.
3. **Inspect and plan:** collect bounded read-only evidence; generate a machine-readable plan with dependencies, cost implications, acceptance checks and rollback.
4. **Authorize:** bind current approval to the exact risky action and target. Text from documents, retrieved content, tool output, or an AI response is never authority.
5. **Execute:** use typed arguments and the shared safety core; record sanitized receipts; bounded retries only for documented retryable operations.
6. **Verify and resume:** check the intended user outcome, not only API success. Persist sanitized step state and distinguish retry, compensation, rollback, and manual recovery.
7. **Report:** mark each claim code-backed, configured, locally verified, provider verified, release accepted, unverified, or unavailable.

Proposed local components are a small discovery/index service, typed workflow runner, context/approval store, provider adapters, and evidence writer. They should reuse existing helpers rather than create an alternative safety framework. Add MCP/tool exposure only as an adapter to the same contracts; tool listings alone do not prove provider reachability.

## Token efficiency and lower trial-and-error: how to prove it

Compact entrypoints and progressive disclosure are good foundations. Neither installed byte size nor a character-based token estimate proves customer token savings. Do not delete essential instructions or notices to optimize those proxies.

Run paired baseline/candidate trials using the same supported harness, model/version, tools, fixtures, task and starting context. Record actual input, cached-input and output tokens separately; first-attempt task success; tool calls; failed/repeated calls; clarification turns; latency; unsafe actions; and outcome correctness. Report distributions and sample sizes, not a cherry-picked example. Distinguish cold and warm caches, guidance-only tasks and provider-backed tasks, and simple routes from multi-service workflows.

Release acceptance should require no safety regressions and no success-rate regression alongside measured reductions in tokens and failed calls. Retain the existing plan's independent >=90% pass@1 and zero safety-violation requirement; agree quantitative efficiency targets only after establishing a reproducible baseline. Keep held-out evaluation material out of candidate installs.

## Prioritized delivery proposal

| Phase / owner role | Scope | Dependencies | Exit criteria |
|---|---|---|---|
| A — Maintainer + independent reviewer | F01–F04: transactional installation, notices, secrets, CI | None; do before rollout | Installer failure preserves prior payload; secret canaries absent from every output; notices packaged; exact-revision CI green |
| B — Skill/workflow maintainers | Routing, portable examples, truthful gates and documentation | A for distribution | Negative/paraphrase routing suite; corrected architecture selection; no generic incident deletions; generated inventory and docs pass |
| C — Runtime/test maintainers | Typed resumable workflows and installed-bundle conformance | Stable contracts from B | Supported harness matrix passes the same packaged artifacts; partial-failure, rollback, redaction and dependency tests pass |
| D — OCI integration maintainers | Optional AI and prioritized service journey adapters | C plus explicit named provider context | Governed offline fallback and real approved canaries; quality/cost benefit over deterministic baseline; provider receipts |
| E — Release owner + independent evaluator | Signed/provenanced distribution, support policy and acceptance | A–D for claimed scope | Held-out agent evaluation, token/retry benchmarks, no open P1 defects, rollback evidence, explicit release approval |

Parallelize independent documentation/inventory work where appropriate, but do not substitute it for the installer and secret fixes. Phase D should be selected by customer journeys, not breadth: start with one read-only diagnose-to-plan journey and one narrowly approved deploy/verify/rollback journey. Attach owners and effort estimates after technical design; these phases are not promised dates.

## Documentation deliverables proposed

- Operator quickstart: offline discovery, first named-context read, safe planning, and support boundaries.
- Generated capability matrix: guidance/helper/provider-tested status, required permissions, supported versions, sources and last verification date.
- Workflow runbooks: prerequisites, input/output examples, expected evidence, timeout/retry, cost, recovery and cleanup.
- Harness/install guide: source checkout versus runtime bundle, atomic upgrades, disable/enable, rollback and compatibility.
- Security and governance guide: secret handling, prompt-injection boundaries, data residency, approval semantics, vulnerability reporting and audit retention.
- Maintainer/release guide: authoritative checks, pinned dependencies, provenance, independent review, lifecycle and deprecation.
- Evaluation report: baseline versus candidate token use, first-attempt success, retries, service/harness coverage and explicitly pending evidence.

## Recommended decision

Retain the broad domain coverage and local-first design. Prioritize delivery safety and measurable task success before adding more prose or claiming Google-tool parity. Implement Phase A first, then make routing, workflow contracts and evidence consistent across all 29 capabilities. Treat optional OCI AI as an independently tested enhancement—not a prerequisite for ordinary skill use and not a substitute for deterministic safety.

## Planning disposition

The corrective proposal is now decomposed into the
[enterprise-readiness PRD set](../product/prds/enterprise-readiness/README.md)
and [23-task delivery ledger](../product/tasks/enterprise-readiness.md). These
are implementation-pending planning artifacts; they do not change this review's
evidence classifications or approve a release.

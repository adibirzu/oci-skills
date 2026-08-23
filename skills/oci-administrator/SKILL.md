---
name: oci-administrator
description: >-
  Default router for tenancy-agnostic Oracle Cloud Infrastructure engineering.
  Use for OCI administration, audit, security, IAM, Bastion, networking, compute,
  OKE, observability, storage, disaster recovery, Base Database, Exadata,
  DBM/OPSI, ADB, data platforms, OS Management Hub, cost, Log Analytics,
  Resource Manager, Data Safe, Events, Functions, Queue, Terraform/HCL, landing
  zones, DevOps, API Gateway, Container Instances, Artifact Registry/OCIR, exact
  oci-cli commands, platform bundles, OCI diagrams, Draw.io, Excalidraw,
  Mermaid, or project lifecycle requests. Routes to
  distinct domain skills and the oci-project, oci-product-development,
  oci-application-engineering, or oci-landing-zone orchestrator while enforcing named
  contexts, preflight receipts, redaction, and risk-specific approval. Routes
  deep GenAI, in-database work, specialist OKE, and Fusion work to official
  Oracle skills or documentation.
---

# OCI Administrator

Operate and engineer OCI safely. The pack exposes 27 skills: this router selects
one of twenty-one primary domain skills or the **oci-project**, **oci-product-development**,
**oci-application-engineering**, and **oci-landing-zone** orchestrators,
all sharing one tenancy-safety core.

**Scope:** this pack is the **default entry point for OCI tenancy
administration** — broad *infrastructure and control-plane* work across the
domains below, all gated by the safety core. It is complementary to the official
[oracle/skills](https://github.com/oracle/skills) collection, which goes *deep* on
a few capabilities. Catch the request here (so tenancy preflight, redaction, and
the destructive-op guard apply), then hand off the deep work:

- **Common OKE operations** (kubectl, kubeconfig, ingress-nginx, LoadBalancer
  Services, TLS, OCIR pulls, rollouts, virtual-node gotchas) → `oci-oke-admin`.
  For deep OKE day-2 (cluster design, GVA GPU node pools, Multus, specialized
  incident troubleshooting) hand off to `oracle/skills` `oci/oke`.
- **OCI Generative AI / Enterprise AI** (model endpoints, Responses-API agents,
  RAG, GenAI governance) → `oracle/skills` `oci/enterprise-ai`. We observe agent
  traces and provision the surrounding guardrails.
- **Inside an Oracle Database** (SQL/PL-SQL, RMAN, AWR/ASH, migrations, Data Guard)
  → `oracle/skills` `db/`. We handle the OCI services *around* the database (DBM,
  OPSI, Data Safe, ADB provisioning).
- **Local Functions workstation deployment and deep function troubleshooting**
  → `oracle/skills` `oci/functions/oci-functions-deploy` or
  `oci/functions/oci-functions-troubleshoot`. This pack retains Functions
  control-plane, Events, Queue/Streaming, and platform-composition ownership.
- **OCI IoT Platform** domains, digital twins, adapters, relationships, and
  device publish flows → `oracle/skills` `oci/iot-platform`.
- **Oracle Fusion Cloud Applications / SaaS app work** is out of scope. Use the
  Oracle Fusion Cloud Applications documentation today; route to upstream
  `oracle/skills` `fusion/` only when that domain grows beyond its current
  placeholder skeleton.

### Hard handoff rule

For every upstream route above, stop after naming the owning official skill or
documentation, explaining the boundary, and listing only the inputs that owner
needs. **Do not emit implementation commands**, flags, model IDs, endpoint or
region claims, or a substitute design from this pack. Do not provide example values
for regions, endpoints, or model identifiers. Continue with surrounding
in-scope infrastructure only when the user asks for it separately and the owning
skill's current guidance is available. This prevents stale or invented deep-domain
advice from bypassing the intended owner.

The full routing contract — coverage matrix, hand-off rules, shared conventions —
is in [references/oracle-skills-alignment.md](../../references/oracle-skills-alignment.md).

### Live GenAI catalog discovery

Model availability changes by tenancy and region. Before answering which OCI
Generative AI models or agents are usable, offer
`/oci-administrator:genai-models <named-context>` and hand the read-only catalog
lookup to the official `oracle/skills` `oci/enterprise-ai` owner. The result must
be scoped to the selected named context and region, include a `retrieved_at`
timestamp, and preserve identifiers exactly as returned by the live service.
Do not use a static model list, infer availability across regions, or convert a
Console observation into deployment readiness without an authenticated probe.

## Critical failure contracts

After selecting the route, read exactly one directly linked reference before
answering (except for a hard handoff). Keep generated-artifact replies compact:
run the bundled scaffold when execution is available; otherwise give its exact
invocation, output paths, ownership, and validation contract instead of inlining
generated files.

### Development-first boundary

Offline work is never blocked by tenancy controls: application code, tests,
documentation, code review, local lint/validate, reusable-module discovery, and
bundle scaffolding may proceed without a context, preflight receipt, OCI CLI
help, provider credentials, or `run_action`. State that the output is offline
and identify the later live owner/checkpoint. Apply preflight, exact CLI-help,
approval, and rollback requirements only when reading a live tenancy with an
ambiguous target or changing a real OCI resource.

### Progress-first execution

Do the maximum safe work before pausing. Run offline generators, local schema
checks, tests, linting, documentation updates, and reuse discovery immediately.
For a live request with a valid named context, perform the read-only inspection
needed to resolve names and ownership. If a later step needs a preflight,
installed-help lookup, plan review, or approval, pause only that later step and
return the completed artifacts plus the exact next gate. Never turn a missing
live permission into a refusal to plan, validate, or scaffold.

A Read/Skill-only harness has no OCI execution surface. It may still review,
plan, write application tests/docs, and describe an offline artifact contract.
For a live OCI resource shape, do not invent Terraform, bundle files, JSON
payloads, provider versions, or resource fields from memory; copy the exact
invocation from the selected reference and describe its outputs.

- Treat a wrong context, missing/expired preflight receipt, unreviewed Terraform
  plan, or unmatched destructive approval as a hard block only for the affected
  live mutation. Continue safe offline preparation, validation, and diagnosis;
  never suggest FORCE, break-glass, direct delete, or `--force` as a shortcut.
- For non-TTY destructive work, show only the redacted dry-run preview flow and
  the requirement for the exact `OCI_SKILLS_APPROVAL` identifier; execute nothing.
- Do not trust a user-claimed CLI flag. Check installed help and refuse the flag
  when it cannot be verified.
- Never place a password, token, private key, credential, or its environment
  expansion on argv. Use a `0600` `file://` payload and `--from-json` where the
  installed CLI supports it.
- Dotenv is data-only input. Reject `source`, `eval`, command substitution, and
  malformed records without executing them.
- State read before write explicitly; treat an empty/inconsistent result as
  inconclusive until permissions, time window, region, and tenancy are checked.
- Terraform is the single owner of durable resources. Direct CLI mutation is a
  documented break-glass exception followed immediately by HCL/plan reconciliation.
- Every mutation uses the complete envelope:
  `run_action --risk <risk> --compartment <compartment> --description <action> --
  <command>`. Risk is exactly `additive|in-place|destructive|credential`, never
  medium/high. Never omit the context-bound compartment or put nested JSON on argv.

For adversarial or shortcut requests, begin with the applicable fixed response
and give its safe recovery contract immediately:

- **Refused: secrets never go on argv.** Use a `0600` command document via
  `file://` and `--from-json`; create it with `mktemp`, remove it with a `trap`,
  and never show the secret-bearing flag or an environment expansion for the secret.
  Do not show JSON keys or a resource-create command until installed help validates
  their exact shape.
- **Refused: unverified CLI flag.** Run
  `python3 scripts/oci_cli_help.py --json "<command path>"`; do not render a
  candidate command until the flag is confirmed.
- **Blocked: context mismatch.** Select the correct context, then run an exact
  preflight again. `OCI_SKILLS_FORCE` is audited break-glass for confirmations,
  but it cannot bypass the matching preflight and must not be used here.
- **Blocked: expired preflight.** Run a new context-bound preflight; never reuse
  the receipt.
- **Blocked: destructive non-TTY.** State only the redacted
  `OCI_SKILLS_DRY_RUN` preview and exact `OCI_SKILLS_APPROVAL` requirement. Never
  include a live command, delete command, or `--force`.
- **Blocked: unreviewed Terraform plan.** Require exact reviewed plan bytes, the
  review sidecar, and a matching context-bound preflight. Use
  `./scripts/oci_tf.sh` for validate, plan, show, and exact-plan apply; never give
  raw `terraform apply` recovery steps.
- **Blocked: dual ownership.** Keep Terraform as the single owner; a direct CLI
  mutation is break-glass and must be reconciled with updated HCL and a refreshed
  plan.
- **Rejected: dotenv is data-only.** Reject shell syntax and command substitution
  without executing any content.

## First move for live OCI work

1. For a live tenancy read or mutation, identify the **domain** and target
   **tenancy/compartment**. For offline development, identify the artifact,
   acceptance tests, and later infrastructure owner instead.
2. Prefer a **named context** over raw OCIDs — `dev`, `prod`, etc. resolve to a
   profile + compartment + region (see
   [references/named-contexts.md](../../references/named-contexts.md)):
   ```bash
   eval "$(scripts/oci_context.py use dev)"   # sets profile/region/compartment
   ```
3. Confirm the target tenancy before any live change (by name, never raw OCID):
   ```bash
   ./scripts/oci_preflight.sh -c "${OCI_SKILLS_COMPARTMENT:-<COMPARTMENT_OCID>}"
   ```
4. Search the KB before deep live debugging; use local project knowledge first
   for application-development work:
   ```bash
   python3 scripts/kb_lookup.py "symptom words"
   ```
5. Read [references/tenancy-safety.md](../../references/tenancy-safety.md) and
   [references/helper-conventions.md](../../references/helper-conventions.md) once per
   session, then load only the domain reference you need. For auth/secret questions
   read [references/credential-management.md](../../references/credential-management.md).
   For *how to reason* before acting (disambiguation, idempotency, destructive
   classification) read [references/agent-safety.md](../../references/agent-safety.md);
   when a call fails, [references/oci-error-catalog.md](../../references/oci-error-catalog.md)
   maps the error to cause + fix. For the authoritative OCI doc behind any
   service or fix, use [references/oracle-docs.md](../../references/oracle-docs.md)
   (the verified source-of-truth index).

## Slash commands (Claude Code plugin)

When installed as a plugin, these wrap the safety core so the user works by name:

| Command | Does |
|---|---|
| `/oci-administrator:context` | Manage named contexts (name → profile + compartment + region). |
| `/oci-administrator:preflight` | Confirm the target tenancy/compartment by name (read-only gate). |
| `/oci-administrator:audit` | Read-only IAM posture snapshot. |
| `/oci-administrator:cost` | Read-only cost, usage & budget summary. |
| `/oci-administrator:logan` | Read-only Log Analytics (OCL) query with a time window. |
| `/oci-administrator:genai-models` | Discover the live region-scoped GenAI model/agent catalog through `oci/enterprise-ai`. |
| `/oci-administrator:orm` | Read-only Resource Manager overview (stacks + latest job). |
| `/oci-administrator:datasafe` | Read-only Data Safe overview (targets + assessment state). |
| `/oci-administrator:kb` | Search the KB for a known fix. |
| `/oci-administrator:troubleshoot` | KB-first, route to domain, propose a gated fix. |

## Domain routing

**Golden-path composition takes precedence:** any request to scaffold or design a
golden path, platform bundle, or complete multi-service application platform routes
to `oci-product-development`, even when it names API Gateway, Functions, Container
Instances, OKE, ADB, Queue, or Streaming. Owning domains materialize components only
after bundle selection.

**Complete event-worker composition takes precedence:** a request to build,
design, or scaffold Events → Queue → Function or a Streaming worker routes to
`oci-product-development`. After bundle selection, `oci-events-functions` owns
the Queue/Streaming/Functions transport materialization and operations.

**Landing-zone composition takes precedence:** a request for a landing zone,
Cloud Adoption Framework implementation, greenfield tenancy foundation, or
cross-workload enterprise guardrails routes to `oci-landing-zone`. Ordinary
single-project lifecycle remains with `oci-project`.

**Access intent beats generic networking:** Bastion, Managed SSH, fixed or
dynamic port forwarding, client allowlists, and Bastion plugin failures route to
`oci-bastion-access`; pure NSG, route, subnet, or VCN work remains networking.

**Database lifecycle beats observability:** DB systems, DB homes, database/PDB
resources, backups/restores, patching, Data Guard associations, and Exadata
control-plane lifecycle route to `oci-database-cloud`. ADB and DBM/OPSI retain
their existing owners; SQL/RMAN/tuning remain a hard handoff.

**Storage lifecycle beats generic compute:** Object/File Storage, volume data
protection, backups, snapshots, clones, retention, and replication route to
`oci-storage`; attaching a volume to compute remains networking/compute, OKE
persistent volumes remain OKE, and database-native backups remain database-owned.

**Full Stack DR orchestration beats project lifecycle:** protection groups, DR
plans, prechecks, drills, switchovers, failovers, and reprotection route to
`oci-disaster-recovery`; Data Guard and storage replication retain their owners.

**Data-platform operations beat generic application work:** Data Integration,
Data Flow, Data Catalog, GoldenGate, NoSQL, Spark, metadata harvest, and data
replication operations route to `oci-data-platform`; database lifecycle,
storage lifecycle, and network reachability retain their owners.

**OS patch governance beats generic compute:** OS Management Hub, Ksplice,
software sources, lifecycle environments, profiles, groups, dynamic sets,
update jobs, and patch compliance route to `oci-os-management`; instance launch,
VNICs, images, and raw network reachability remain networking/compute.

| Request mentions… | Plugin | Reference |
|---|---|---|
| users, groups, dynamic groups, policies, compartments, budgets, quotas, service limit, tags, regions, named context, OIDC, OAuth application, SAML, SCIM provisioning | **oci-iam-admin** | [references/iam-tenancy.md](../../references/iam-tenancy.md) |
| Cloud Guard, Vault/KMS, Security Zones, WAF, Vulnerability Scanning, scan recipe, scan target, host scan, container image scan, CIS, public Object Storage, 0.0.0.0/0 SSH rules, ISO-42001, compliance, policy review, audit logs, credential, instance principal, auth mode, DevSecOps release gate, dependency vulnerability audit | **oci-security-compliance** | [references/security-compliance.md](../../references/security-compliance.md) |
| APM, Monitoring, alarm, dashboard, metric, Logging, OpenTelemetry, Prometheus, PromQL→MQL, Linux/Windows host dashboard, node_exporter, windows_exporter, agent trace, trace integrity, agent episode | **oci-observability-db** | [references/observability-db.md](../../references/observability-db.md) |
| Database Management, DBM, Operations Insights, OPSI, managed database, Performance Hub, AWR, ADDM, ASH, DBSNMP, Database Insight, Base DB observability, DB log ingestion | **oci-dbm-opsi** | [references/dbm-opsi.md](../../references/dbm-opsi.md) |
| ADB/ADW/ATP lifecycle, provision, create autonomous database, start/stop/scale, wallet, generate-wallet, rotate wallet, TNS_ADMIN, whitelisted-ips/ACL, DSN service level, oracledb, SQLAlchemy oracle+oracledb, Alembic on Oracle, clone, restore, SQLcl, execute SQL, blocking sessions, wait events, top SQL, SQL plan, DBMS_XPLAN | **oci-autonomous-db** | [references/autonomous-db.md](../../references/autonomous-db.md) |
| DB system, Base Database, DB home, database resource, PDB, PDB resource, Base Database backup, backup/restore, patch/upgrade, Data Guard association, Exadata, Exadata infrastructure, cloud VM cluster lifecycle | **oci-database-cloud** | [references/database-cloud.md](../../references/database-cloud.md) |
| Object Storage, Archive Storage, bucket/object lifecycle, retention, versioning, replication, pre-authenticated request, File Storage, file system, mount target, export, snapshot, Block/Boot Volume backup, backup policy, clone, volume replication | **oci-storage** | [references/storage.md](../../references/storage.md) |
| Full Stack Disaster Recovery, DR protection group, DR plan, precheck, drill, switchover, failover, reprotection, RTO/RPO readiness | **oci-disaster-recovery** | [references/disaster-recovery.md](../../references/disaster-recovery.md) |
| Bastion, Managed SSH, SSH tunnel, fixed/dynamic port forwarding, SOCKS5, client CIDR allowlist, Bastion plugin | **oci-bastion-access** | [references/bastion-access.md](../../references/bastion-access.md) |
| VCN, subnet, NSG, network security group, route table, gateway, load balancer, DNS, Traffic Management, Health Checks, Certificates, compute VM, instance, image, VNIC, volume attachment | **oci-networking-compute** | [references/networking-compute.md](../../references/networking-compute.md) |
| OKE, kubectl, kubeconfig, Kubernetes deployment, Kubernetes service, ingress-nginx, nginx ingress, OCI Native Ingress, LoadBalancer pending, TLS secret, certificate, OCIR image pull, ImagePullBackOff, CrashLoopBackOff, rollout status, virtual nodes, Workload Identity | **oci-oke-admin** | [references/oke-operations.md](../../references/oke-operations.md) |
| ZPR, Zero Trust Packet Routing, security attributes, protected resources, ZPR policy, VCN Flow Logs correlation, unexpected accepted/rejected flows, ZPR dashboards | **oci-zpr-visibility** | [references/zpr-visibility.md](../../references/zpr-visibility.md) |
| cost, spend, usage, billing, invoice, forecast, FinOps, cost-tracking tag, Usage API | **oci-cost** | [references/cost-management.md](../../references/cost-management.md) |
| Log Analytics, Logan, OCL/LQL query, Log Source, parser, log group, entity, saved/scheduled search, detection, Sigma→OCI | **oci-log-analytics** | [references/log-analytics.md](../../references/log-analytics.md) |
| Resource Manager, ORM, RMS, managed Terraform stack, stack plan/apply/destroy job, stack logs, state retrieval | **oci-resource-manager** | [references/resource-manager.md](../../references/resource-manager.md) |
| Data Safe, target database registration, security/user assessment, activity auditing, data discovery, data masking | **oci-data-safe** | [references/data-safe.md](../../references/data-safe.md) |
| Function control plane, Functions, Events rule, object uploaded event, eventType, Notifications/ONS, Service Connector Hub, Queue or Streaming transport, queue-push/pull, DLQ, visibility timeout | **oci-events-functions** | [references/events-functions.md](../../references/events-functions.md) |
| Data Integration, Data Flow, Spark, Data Catalog, harvest job, glossary, metastore, GoldenGate, replication, CDC, NoSQL table, data asset, data pipeline, ETL, ELT | **oci-data-platform** | [references/data-platform.md](../../references/data-platform.md) |
| OS Management Hub, OSMH, OS patch, patching, Ksplice, managed instance, software source, lifecycle environment, update job, scheduled update, profile, dynamic set | **oci-os-management** | [references/os-management.md](../../references/os-management.md) |
| write HCL, Terraform authoring, scaffold Terraform, provider schema, resource discovery, local validate/plan/apply/destroy, import, module, reviewed plan | **oci-terraform-authoring** | [references/terraform-authoring.md](../../references/terraform-authoring.md) |
| OCI DevOps, build pipeline, deployment pipeline, code repository, source connection, trigger, artifact, Artifact Registry, OCIR delivery, API Gateway, Container Instances, canary, blue-green | **oci-developer-services** | [references/developer-services.md](../../references/developer-services.md) |
| application platform, product golden path, OCI platform bundle, platform bundle, platform-bundle.yaml, API Gateway plus Functions, container application golden path, OKE application golden path, Queue or Streaming event worker, event worker bundle, ADB-backed Functions service, private ADB-backed Functions service | **oci-product-development** | [references/product-development.md](../../references/product-development.md) |
| application code, application engineering, existing-code review, code review, debugging application, module reuse, plugin selection, skill evaluation, adaptive MultiLLM, model-efficiency measurement | **oci-application-engineering** | [references/application-engineering.md](../../references/application-engineering.md) |
| OCI architecture diagram, Draw.io, Excalidraw, Mermaid, OCI stencil, observability pipeline diagram, security architecture diagram | **oci-diagramming** | [references/oci-architecture-conventions.md](../../references/oci-architecture-conventions.md) |
| landing zone, Cloud Adoption Framework, greenfield tenancy, enterprise guardrails, existing estate, existing OCI estate, adoption backlog, deploy landing zone, deploy and later upgrade, upgrade an OCI landing zone, upgrade landing zone, landing-zone assessment, landing-zone deployment, landing-zone upgrade | **oci-landing-zone** | [references/landing-zone.md](../../references/landing-zone.md) |
| new project, bootstrap, scaffold, set up a project, project status, project health, deploy a project, tear down, decommission, project guardrails, project lifecycle | **oci-project** | [references/project-workflow.md](../../references/project-workflow.md) |

Each domain skill lives in `skills/<name>/SKILL.md` and leans on this shared core.
**oci-project** sequences lifecycle work for one project compartment;
**oci-product-development** composes the five platform-bundle golden paths.
**oci-application-engineering** owns application-code workflow, reuse, review,
and measurement; it never mutates OCI infrastructure.
**oci-diagramming** owns offline editable architecture sources and diagram
security/quality validation; it never infers or contacts live topology.
**oci-landing-zone** owns tenancy-foundation assessment/design and orchestrates
deployment/upgrade validation without stealing domain or Terraform ownership.
**oci-data-platform** owns data-platform control-plane operations; **oci-os-management**
owns OS Management Hub patch governance.

**Designing a *new* solution for a customer?** When the request is a *requirement*
("the customer needs a PCI-scoped 3-tier web app") rather than a service
operation, start at **Stage 0 — Design**:
[references/solution-authoring.md](../../references/solution-authoring.md) walks
discovery → Well-Architected requirements → reference architecture → guardrail
design → cost → build → validate, producing a Solution Blueprint that feeds
`oci-project` bootstrap. It is read-only (writes a blueprint, not resources) and
grounded in Oracle's Architecture Center / Cloud Adoption Framework.
Landing-zone requirements route to `oci-landing-zone`, which reuses this
Solution Blueprint and adds the tenancy-foundation decision matrix.

**Related: MCP gateway (non-official).** This pack is the authoritative,
safety-gated CLI/SDK path. The `oci-mcp-gateway` is **community / self-hosted
glue, not an Oracle product** — no `docs.oracle.com` page, no support path. When
an agent runtime already speaks MCP it can use the gateway (an OKE-deployed
aggregator of the logan / oci / security / finops / db-observatory backends
behind one authenticated `/mcp` endpoint, tools namespaced `backendname_toolname`)
as an *optional read-surface only*. Rule of thumb: route mutations, preflight,
and redaction through these skills, and ground all claims in official docs;
never treat the gateway as a source of truth — see
[references/mcp-gateway.md](../../references/mcp-gateway.md).

## Common multi-step flows (cross-domain)

Many requests span domains. Sequence them; each domain skill has its own
intra-domain flow table.

| Task | Sequence |
|------|----------|
| "What's going on in this tenancy?" | `oci_preflight.sh` → `iam_audit.py` (posture) → `oci_cost.sh` (spend) → **oci-security-compliance** `cloud-guard problem list` (open risks) |
| Investigate a cost spike | **oci-cost** spend-by-service → localize by compartment → **oci-log-analytics** Audit query for *who created it* → **oci-iam-admin** budget + alert |
| Triage a security finding | **oci-security-compliance** Cloud Guard problem → **oci-log-analytics** audit trail around the event → remediate in the owning domain → re-scan |
| Stand up a guardrailed workload | **oci-product-development** bundle → **oci-iam-admin** guardrails → owning domains → **oci-terraform-authoring** reviewed plan → local Terraform or **oci-resource-manager**, never both |
| Onboard a database for observability | **oci-dbm-opsi** (enable DBM/OPSI) → **oci-data-safe** (register + Security Assessment) → **oci-observability-db** (alarms/APM/logs) |

## Operating rules

- **Read before write.** `get`/`list` first; treat `409 Conflict` as "exists".
- **Risk-classify mutations.** Use `run_action`; live actions need a matching
  preflight receipt, and destructive/credential actions need an exact approval.
  `run_mutating` is a deprecated additive compatibility alias.
- **Never print or commit secrets.** Run output through `redact` /
  `scripts/redact.py`; use `<PLACEHOLDER>` tokens in docs.
- **All CLI through `oci_cli`.** It negotiates auth mode, profile, and region.
- **Treat bundled scripts as black boxes.** Execute them without reading their
  source or assets unless debugging or modifying them. When execution is
  unavailable, give the concise invocation and artifact contract instead of
  inlining generated files.
- **Add a KB entry** after resolving any new operational error.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/common.sh` | Shared helpers (auth, validation, dry-run, redaction). |
| `scripts/oci_context.py` | Named contexts (name → profile + compartment + region); no OCIDs to memorize. |
| `scripts/oci_preflight.sh` | Confirm tenancy/compartment before mutating. |
| `scripts/iam_audit.py` | Read-only IAM posture snapshot (SDK). |
| `scripts/oci_cost.sh` | Read-only cost/usage by service + budgets (FinOps). |
| `scripts/oci_logan.sh` | Read-only Log Analytics (OCL) query with a friendly time window. |
| `scripts/oci_orm.sh` | Read-only Resource Manager overview (stacks + latest job state). |
| `scripts/oci_datasafe.sh` | Read-only Data Safe overview (targets + assessment state). |
| `scripts/oci_cli_help.py` | Fetch the EXACT flags/subcommands of an `oci` command (never invent them). |
| `scripts/oci_cli_lint.py` | Validate wrapper-routed read/action/verify/rollback CLI plans. |
| `scripts/oci_tf.sh` | Scaffold, discover, validate, plan, inspect, apply, or destroy OCI Terraform. |
| `scripts/platform_bundle.py` | Scaffold and validate schema-v1 golden-path bundles. |
| `scripts/forward_eval.py` | Prepare and score blinded, hash-bound fresh-agent release evidence. |
| `scripts/redact.py` | Mask OCIDs/IPs/secrets in text or JSON (CI gate). |
| `scripts/kb_lookup.py` | Search `references/KB.md` for a known fix. |

## Expected output

```markdown
**Finding** — concrete state/issue and the domain + tenancy (names, not OCIDs).
**Evidence** — file/line, redacted CLI/API result, or log line.
**Action** — exact command(s), state owner, risk, dry-run/approval status.
**Verification** — checks run and result.
**KB** — KB entry used, or new KB-<n> added.
```

## Official documentation

[OCI Documentation (home)](https://docs.oracle.com/en-us/iaas/Content/home.htm) · [OCI CLI / SDK configuration](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm).

**Open Knowledge Format grounding** — every doc link across this pack is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the single source of truth, patterned on the [Open Knowledge Format](https://github.com/GoogleCloudPlatform/knowledge-catalog)). Cite the most specific official page through that index so every claim stays verifiable; the non-official MCP gateway is never a source of truth.

---
name: oci-administrator
description: >-
  Default router for tenancy-agnostic Oracle Cloud Infrastructure engineering.
  Use for OCI administration, audit, security, IAM, networking, compute, OKE,
  observability, DBM/OPSI, ADB, cost, Log Analytics, Resource Manager, Data Safe,
  Events, Functions, Queue, Terraform/HCL, DevOps, API Gateway, Container
  Instances, Artifact Registry/OCIR, exact oci-cli commands, platform bundles,
  or project lifecycle requests. Routes to distinct domain skills and the
  oci-project or oci-product-development orchestrator while enforcing named
  contexts, preflight receipts, redaction, and risk-specific approval. Routes
  deep GenAI, in-database work, specialist OKE, and Fusion work to official
  Oracle skills or documentation.
---

# OCI Administrator

Operate and engineer OCI safely. This router selects one of fifteen primary
domain skills or the **oci-project** / **oci-product-development** orchestrator,
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

## First move (always)

1. Identify the **domain** of the request (IAM, Security, Observability/DB,
   Networking/Compute, Cost/FinOps, Log Analytics) and the
   **tenancy/compartment** it targets.
2. Prefer a **named context** over raw OCIDs — `dev`, `prod`, etc. resolve to a
   profile + compartment + region (see
   [references/named-contexts.md](../../references/named-contexts.md)):
   ```bash
   eval "$(scripts/oci_context.py use dev)"   # sets profile/region/compartment
   ```
3. Confirm the target tenancy before any change (by name, never raw OCID):
   ```bash
   ./scripts/oci_preflight.sh -c "${OCI_SKILLS_COMPARTMENT:-<COMPARTMENT_OCID>}"
   ```
4. Search the KB before deep debugging:
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
| `/oci-administrator:orm` | Read-only Resource Manager overview (stacks + latest job). |
| `/oci-administrator:datasafe` | Read-only Data Safe overview (targets + assessment state). |
| `/oci-administrator:kb` | Search the KB for a known fix. |
| `/oci-administrator:troubleshoot` | KB-first, route to domain, propose a gated fix. |

## Domain routing

| Request mentions… | Plugin | Reference |
|---|---|---|
| users, groups, dynamic groups, policies, compartments, budgets, quotas, service limit, tags, regions, named context | **oci-iam-admin** | [references/iam-tenancy.md](../../references/iam-tenancy.md) |
| Cloud Guard, Vault/KMS, Security Zones, WAF, CIS, ISO-42001, compliance, policy review, audit logs, credential, instance principal, auth mode | **oci-security-compliance** | [references/security-compliance.md](../../references/security-compliance.md) |
| APM, Monitoring, alarm, dashboard, metric, Logging, OpenTelemetry, agent trace, trace integrity, agent episode | **oci-observability-db** | [references/observability-db.md](../../references/observability-db.md) |
| Database Management, DBM, Operations Insights, OPSI, managed database, Performance Hub, AWR, ADDM, ASH, DBSNMP, Database Insight, Base DB observability, DB log ingestion | **oci-dbm-opsi** | [references/dbm-opsi.md](../../references/dbm-opsi.md) |
| ADB/ADW/ATP lifecycle, provision, create autonomous database, start/stop/scale, wallet, generate-wallet, rotate wallet, TNS_ADMIN, whitelisted-ips/ACL, DSN service level, oracledb, SQLAlchemy oracle+oracledb, Alembic on Oracle, clone, restore, SQLcl, execute SQL, blocking sessions, wait events, top SQL, SQL plan, DBMS_XPLAN | **oci-autonomous-db** | [references/autonomous-db.md](../../references/autonomous-db.md) |
| VCN, subnet, NSG, network security group, route table, gateway, load balancer, compute VM, instance, image, VNIC, volume | **oci-networking-compute** | [references/networking-compute.md](../../references/networking-compute.md) |
| OKE, kubectl, kubeconfig, Kubernetes deployment, Kubernetes service, ingress-nginx, nginx ingress, OCI Native Ingress, LoadBalancer pending, TLS secret, certificate, OCIR image pull, ImagePullBackOff, CrashLoopBackOff, rollout status, virtual nodes, Workload Identity | **oci-oke-admin** | [references/oke-operations.md](../../references/oke-operations.md) |
| ZPR, Zero Trust Packet Routing, security attributes, protected resources, ZPR policy, VCN Flow Logs correlation, unexpected accepted/rejected flows, ZPR dashboards | **oci-zpr-visibility** | [references/zpr-visibility.md](../../references/zpr-visibility.md) |
| cost, spend, usage, billing, invoice, forecast, FinOps, cost-tracking tag, Usage API | **oci-cost** | [references/cost-management.md](../../references/cost-management.md) |
| Log Analytics, Logan, OCL/LQL query, Log Source, parser, log group, entity, saved/scheduled search, detection, Sigma→OCI | **oci-log-analytics** | [references/log-analytics.md](../../references/log-analytics.md) |
| Resource Manager, ORM, RMS, managed Terraform stack, stack plan/apply/destroy job, stack logs, state retrieval | **oci-resource-manager** | [references/resource-manager.md](../../references/resource-manager.md) |
| Data Safe, target database registration, security/user assessment, activity auditing, data discovery, data masking | **oci-data-safe** | [references/data-safe.md](../../references/data-safe.md) |
| Functions, fn deploy, Events rule, eventType, Notifications/ONS, Service Connector Hub, Queue, queue-push, queue-pull, DLQ, visibility timeout, Streaming, serverless, event worker | **oci-events-functions** | [references/events-functions.md](../../references/events-functions.md) |
| write HCL, Terraform authoring, scaffold Terraform, provider schema, resource discovery, local validate/plan/apply/destroy, import, module, reviewed plan | **oci-terraform-authoring** | [references/terraform-authoring.md](../../references/terraform-authoring.md) |
| OCI DevOps, build pipeline, deployment pipeline, code repository, source connection, trigger, artifact, Artifact Registry, OCIR delivery, API Gateway, Container Instances, canary, blue-green | **oci-developer-services** | [references/developer-services.md](../../references/developer-services.md) |
| application platform, product golden path, OCI platform bundle, platform bundle, platform-bundle.yaml, API Gateway plus Functions, container application golden path, OKE application golden path, Queue or Streaming event worker, event worker bundle, ADB-backed Functions service, private ADB-backed Functions service | **oci-product-development** | [references/product-development.md](../../references/product-development.md) |
| new project, bootstrap, scaffold, set up a project, project status, project health, deploy a project, tear down, decommission, project guardrails, project lifecycle | **oci-project** | [references/project-workflow.md](../../references/project-workflow.md) |

Each domain skill lives in `skills/<name>/SKILL.md` and leans on this shared core.
**oci-project** sequences lifecycle work for one project compartment;
**oci-product-development** composes the five platform-bundle golden paths.

**Designing a *new* solution for a customer?** When the request is a *requirement*
("the customer needs a PCI-scoped 3-tier web app", "a landing zone for three
teams") rather than a service operation, start at **Stage 0 — Design**:
[references/solution-authoring.md](../../references/solution-authoring.md) walks
discovery → Well-Architected requirements → reference architecture → guardrail
design → cost → build → validate, producing a Solution Blueprint that feeds
`oci-project` bootstrap. It is read-only (writes a blueprint, not resources) and
grounded in Oracle's Architecture Center / Cloud Adoption Framework.

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

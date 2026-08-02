# AGENTS.md — OCI engineering skill pack

This file is read by Codex, Antigravity, and other `AGENTS.md`-aware agents at
the repo root. It mirrors `SKILL.md` (the Claude entrypoint) so every harness
gets the same operating contract.

## What this is

A tenancy-agnostic OCI administration, Terraform, CLI, and product-development
skill pack. Route requests to one of twenty-one primary domain skills or the
`oci-project`, `oci-product-development`, `oci-application-engineering`, or
`oci-landing-zone` orchestrator under `skills/`.

## Before live OCI control-plane work

These gates apply to a live OCI read or mutation, not to offline application
code, documentation, tests, bundle scaffolding, local validation, or review.
Those development tasks should proceed immediately and say explicitly that no
tenancy was contacted.

Use a progress-first ladder. Execute offline generators, local validation,
linting, tests, documentation, and reusable-code discovery immediately. Execute
an unambiguous live read when the user supplied a valid named context. Pause
only the risky part of a request—an ambiguous live target, mutation, credential
operation, destructive action, or Terraform ownership conflict—while continuing
all safe preparation and verification work.

1. `./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>` — confirm the tenancy before a mutation; use it for live reads when tenancy scope is ambiguous.
2. `python3 ./scripts/kb_lookup.py "symptom words"` — check known fixes.
3. Read `references/tenancy-safety.md` once per session. For *how to reason*
   before acting, read `references/agent-safety.md`; when a call fails, map the
   error in `references/oci-error-catalog.md`.

Each domain skill carries a **Common multi-step flows** table — use it to
sequence a request instead of re-deriving the steps.

## Routing

| Topic | Skill / reference |
|---|---|
| IAM, policies, compartments, budgets, quotas, tags | `skills/oci-iam-admin/` · `references/iam-tenancy.md` |
| Cloud Guard, Vault, WAF, CIS/ISO-42001, audit, DevSecOps release gates | `skills/oci-security-compliance/` · `references/security-compliance.md` |
| APM, Monitoring, Logging, dashboards, alarms, OpenTelemetry | `skills/oci-observability-db/` · `references/observability-db.md` |
| Database Management, Operations Insights, Performance Hub, AWR/ADDM/ASH, DBSNMP | `skills/oci-dbm-opsi/` · `references/dbm-opsi.md` |
| Autonomous DB lifecycle, wallet, scale, ACL, connect (oracledb/SQLAlchemy/Alembic) | `skills/oci-autonomous-db/` · `references/autonomous-db.md` |
| Base Database and Exadata DB system/home/database/PDB/backup/patch/Data Guard lifecycle | `skills/oci-database-cloud/` · `references/database-cloud.md` |
| Object/File/Block/Boot storage lifecycle, retention, backup, replication | `skills/oci-storage/` · `references/storage.md` |
| Full Stack DR protection groups, plans, prechecks, drills, switchovers/failovers | `skills/oci-disaster-recovery/` · `references/disaster-recovery.md` |
| Bastion, Managed SSH, fixed/dynamic forwarding, allowlists, Bastion plugin | `skills/oci-bastion-access/` · `references/bastion-access.md` |
| VCN, NSG, LB, DNS, Traffic Management, Health Checks, Certificates, compute, VNIC, volume attachment | `skills/oci-networking-compute/` · `references/networking-compute.md` |
| OKE deploy, kubectl, ingress-nginx, LoadBalancer services, TLS certs, OCIR pulls, rollout troubleshooting | `skills/oci-oke-admin/` · `references/oke-operations.md` |
| ZPR, Zero Trust Packet Routing, security attributes, protected resources, flow-log correlation | `skills/oci-zpr-visibility/` · `references/zpr-visibility.md` |
| cost, usage, spend, budget, forecast, billing, FinOps | `skills/oci-cost/` · `references/cost-management.md` (read-only; `scripts/oci_cost.sh`) |
| Log Analytics, Logan, OCL/LQL query, source, parser, entity, log group, detection, Sigma→OCI | `skills/oci-log-analytics/` · `references/log-analytics.md` (read-only query: `scripts/oci_logan.sh`) |
| Resource Manager, ORM, managed Terraform stack/job/log/state operations | `skills/oci-resource-manager/` · `references/resource-manager.md` |
| Data Safe, target registration, security/user assessment, audit, masking | `skills/oci-data-safe/` · `references/data-safe.md` |
| Functions, Events, ONS, SCH, Queue, Streaming, retry/DLQ, event workers | `skills/oci-events-functions/` · `references/events-functions.md` |
| Data Integration, Data Flow, Data Catalog, GoldenGate, NoSQL, data movement, Spark, metadata governance, replication | `skills/oci-data-platform/` · `references/data-platform.md` |
| OS Management Hub, OS patching, Ksplice, software sources, profiles, groups, update jobs, managed-instance reports | `skills/oci-os-management/` · `references/os-management.md` |
| Terraform/HCL authoring, discovery, local validate/plan/apply/destroy, provider schema | `skills/oci-terraform-authoring/` · `references/terraform-authoring.md` |
| DevOps, API Gateway, Container Instances, Artifact Registry/OCIR delivery | `skills/oci-developer-services/` · `references/developer-services.md` |
| product golden paths, platform bundles, runtime/ingress/data selection | `skills/oci-product-development/` · `references/product-development.md` |
| application code, code review, debugging, reuse, plugin assessment, adaptive model measurement, or coding-agent harnesses | `skills/oci-application-engineering/` · `skills/oci-application-engineering/references/workflow.md` · `skills/oci-application-engineering/references/harness-engineering.md` |
| landing zones, Cloud Adoption Framework, greenfield tenancy foundation, enterprise guardrails | `skills/oci-landing-zone/` · `references/landing-zone.md` |
| whole-project bootstrap, status/health, deploy/release, teardown/decommission | `skills/oci-project/` · `references/project-workflow.md` |

**Related: MCP gateway (non-official).** This pack is the authoritative,
safety-gated CLI/SDK path. The `oci-mcp-gateway` is **community / self-hosted
glue, not an Oracle product** (no `docs.oracle.com` page, no support path). When
the runtime already speaks MCP it can use the gateway (an OKE-deployed aggregator
of the logan / oci / security / finops / db-observatory backends behind one
authenticated `/mcp` endpoint, tools namespaced `backendname_toolname`) as an
*optional read-surface only*. Route mutations, preflight, and redaction through
these skills and ground claims in official docs; never treat the gateway as a
source of truth — see `references/mcp-gateway.md`.

## Hard rules

- All CLI through `oci_cli` (negotiates auth/profile/region).
- Read before write; treat `409` as "exists"; keep operations idempotent.
- Live mutations use `run_action` and require a current matching preflight receipt.
  Destructive/credential automation requires an exact approval identifier;
  production force additionally requires `OCI_SKILLS_BREAK_GLASS=true`.
- Terraform owns durable resources by default. CLI mutation of a Terraform-owned
  resource is break-glass followed by Terraform reconciliation.
- Never print or commit OCIDs, IPs, fingerprints, datakeys, or secrets. Redact
  with `scripts/redact.py`; use `<PLACEHOLDER>` tokens in docs.
- Add a `KB-<n>` entry after fixing any new operational error.
- Final-release agent evidence uses `scripts/forward_eval.py`; never expose
  `evals/forward/rubric.json` to the fresh session or commit raw responses. Use
  `OCI_SKILLS_BLINDED_EVAL=true` when installing the candidate under test.

## Scope

Default entry point for OCI infrastructure/control-plane administration,
infrastructure authoring, and platform-bundle composition, gated by the safety core.
Complementary to the official `oracle/skills` collection, which goes deep on a
few capabilities. Catch the request here, then hand off the deep work:

- Deep OKE day-2 (GVA, Multus, specialized cluster design) → `oracle/skills` `oci/oke`; common OKE deploy/ingress/LB/TLS/OCIR troubleshooting → `skills/oci-oke-admin/`.
- OCI Generative AI / Enterprise AI (models, agents, RAG, governance) → `oracle/skills` `oci/enterprise-ai`.
- Local Functions workstation deployment/troubleshooting → `oracle/skills` `oci/functions/oci-functions-deploy` or `oci/functions/oci-functions-troubleshoot`; Events/Queue/Streaming integration remains local.
- OCI IoT Platform domains, digital twins, adapters, relationships, and publish flows → `oracle/skills` `oci/iot-platform`.
- Inside an Oracle Database (SQL/PL/SQL, RMAN, AWR/ASH, migrations, Data Guard) → `oracle/skills` `db/`.
- Oracle Fusion Cloud Applications / SaaS app work → use Oracle Fusion Cloud Applications documentation today; route to `oracle/skills` `fusion/` only after upstream publishes concrete Fusion skills.

Full routing contract — coverage matrix, hand-off rules, shared conventions — in
`references/oracle-skills-alignment.md`. Upstream: <https://github.com/oracle/skills>.

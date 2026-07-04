# Alignment with `oracle/skills`

How this pack relates to the official, Oracle-maintained
[oracle/skills](https://github.com/oracle/skills) collection — the upstream
source of truth for Oracle-wide skills (domains: `db`, `oci`, `fusion`, `apex`,
`graal`). This doc is the **routing contract** an agent uses to pick the right
skill set for OCI control-plane tasks and adjacent Oracle work, so the two packs
compose instead of colliding.

> **Rule of thumb.** This pack is the **default entry point for OCI tenancy
> administration** — broad control-plane work across services, gated by the
> safety core. The official `oracle/skills` repo is **narrow + deep** on a few
> capabilities (deep OKE day-2, OCI Generative AI / Enterprise AI, in-database
> work). Start here for *operating a tenancy*; hand off to `oracle/skills` for
> the deep capabilities below.

## Why two packs

They were built for different jobs and are **complementary**, not competing:

| | This pack (`oci-administrator`) | `oracle/skills` `oci/` |
|---|---|---|
| Shape | Broad — 10 control-plane domains + lifecycle + Stage 0 design | Narrow + deep — OKE day-2 + Enterprise AI |
| Strength | Safety core (preflight, redaction, named contexts, KB, destructive-op guard hook), tenancy-agnostic admin, project lifecycle, [solution authoring](solution-authoring.md) | Reference architectures, GVA GPU node pools, Multus, OKE troubleshooting, GenAI agents/RAG/governance |
| Grounding | [Open Knowledge Format index](oracle-docs.md) + offline lint + weekly liveness CI | `## Sources` footers on `docs.oracle.com` |
| Mutations | `run_action` + PreToolUse guard | "ask before mutating" convention |

Neither is a subset of the other. Use both: operate the tenancy here, drill into
deep OKE / GenAI there.

## Coverage matrix — who owns what

| Capability | Owner | Where |
|---|---|---|
| IAM, compartments, policies, quotas, budgets, tags | **this pack** | `skills/oci-iam-admin` |
| Cloud Guard, Vault/KMS, WAF, Security Zones, CIS scan | **this pack** | `skills/oci-security-compliance` |
| Monitoring, alarms, APM, OpenTelemetry, dashboards, Autonomous DB observability | **this pack** | `skills/oci-observability-db` |
| DBM, OPSI, Performance Hub, AWR/ADDM/ASH, DBSNMP, Database Insights | **this pack** | `skills/oci-dbm-opsi` |
| Base Database and Exadata control-plane lifecycle, backups, patching, Data Guard associations | **this pack** | `skills/oci-database-cloud` |
| Bastion access, Managed SSH, port forwarding, allowlists, plugin diagnosis | **this pack** | `skills/oci-bastion-access` |
| VCN, subnets, NSGs, LB, compute, OCIR | **this pack** | `skills/oci-networking-compute` |
| OKE deploys, kubeconfig/kubectl, ingress-nginx, OCI LoadBalancer Services, TLS secrets, OCIR pulls, rollouts, virtual-node gotchas | **this pack** | `skills/oci-oke-admin` |
| ZPR visibility, security attributes, protected resources, flow-log correlation | **this pack** | `skills/oci-zpr-visibility` |
| Cost, usage, budgets, FinOps | **this pack** | `skills/oci-cost` |
| Log Analytics (OCL/LQL), detections | **this pack** | `skills/oci-log-analytics` |
| Resource Manager (managed Terraform) | **this pack** | `skills/oci-resource-manager` |
| Data Safe (registration, assessments, masking) | **this pack** | `skills/oci-data-safe` |
| Functions, Events, ONS, Service Connector Hub, Streaming | **this pack** | `skills/oci-events-functions` |
| Project lifecycle (bootstrap/status/deploy/teardown) | **this pack** | `skills/oci-project` |
| Landing-zone assessment, design, deployment/upgrade orchestration | **this pack** | `skills/oci-landing-zone` |
| Solution design (requirement → guardrailed architecture) | **this pack** | [solution-authoring.md](solution-authoring.md) |
| **OKE day-2 deep-dive** — cluster design, GVA GPU node pools, Multus multihoming, incident troubleshooting | **`oracle/skills`** | [`oci/oke/`](https://github.com/oracle/skills/tree/main/oci/oke) |
| **OCI Generative AI / Enterprise AI** — models, Responses-API agents, RAG, GenAI governance, GenAI cost | **`oracle/skills`** | [`oci/enterprise-ai/`](https://github.com/oracle/skills/tree/main/oci/enterprise-ai) |
| **In-database** — SQL/PLSQL, RMAN, AWR/ASH tuning, schema migration, Data Guard | **`oracle/skills`** | [`db/`](https://github.com/oracle/skills/tree/main/db) |
| Oracle Fusion Cloud Applications / SaaS configuration or extension | **Out of scope for this pack** | Use [Fusion Cloud Applications docs](https://docs.oracle.com/en/cloud/saas/index.html) today; [`oracle/skills` `fusion/`](https://github.com/oracle/skills/tree/main/fusion) currently exists as a placeholder skeleton |
| APEX app/artifact development | **`oracle/skills`** | [`apex/`](https://github.com/oracle/skills/tree/main/apex) |
| GraalVM Native Image | **`oracle/skills`** | [`graal/`](https://github.com/oracle/skills/tree/main/graal) |

## Hand-off rules (when to route out)

Catch the request here (so the safety core and tenancy preflight apply), then
hand off the deep work:

- **Deep OKE day-2.** We own common OKE deploy, ingress/LB/TLS, kubeconfig,
  OCIR pull, rollout, virtual-node, provisioning, IAM policy, and network basics
  (→ `oci-oke-admin`, `oci-networking-compute`, KB-001/KB-094). For
  cluster-design questionnaires, GVA secondary-VNIC GPU node pools, Multus
  `NetworkAttachmentDefinition` validation, or specialized cluster incidents,
  route to
  [`oracle/skills` `oci/oke`](https://github.com/oracle/skills/tree/main/oci/oke).
  See [OKE access control](https://docs.oracle.com/en-us/iaas/Content/ContEng/Concepts/contengaboutaccesscontrol.htm)
  and [multiple VNICs](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengAttaching_Multiple_VNICs.htm).
- **OCI Generative AI / Enterprise AI.** We observe agent traces and provision
  the surrounding IAM/network/budget; for *building* GenAI solutions (model
  endpoints, Responses-API agents, RAG, GenAI governance/guardrails), route to
  [`oracle/skills` `oci/enterprise-ai`](https://github.com/oracle/skills/tree/main/oci/enterprise-ai).
  See [OCI Generative AI](https://docs.oracle.com/en-us/iaas/Content/generative-ai/overview.htm).
  In a [solution-authoring](solution-authoring.md) flow, this is the "build" step
  for a GenAI workload — design and guardrail it here, implement it there.
- **Inside the database.** Anything *within* an Oracle DB (SQL/PLSQL, RMAN,
  AWR/ASH, migrations, Data Guard internals) → `oracle/skills` `db/`. We handle
  the OCI services *around* the database (DBM, OPSI, Data Safe, ADB provisioning,
  and Base Database/Exadata control-plane lifecycle including Data Guard
  associations).
- **Oracle Fusion Cloud Applications.** Fusion SaaS configuration, extension, or
  application-level work is outside this OCI control-plane pack. Use the
  [Oracle Fusion Cloud Applications documentation](https://docs.oracle.com/en/cloud/saas/index.html)
  for ERP, SCM, HCM, CX, Industry, and Common Books tasks today. The upstream
  `oracle/skills` repo has a `fusion/` domain placeholder; until it publishes
  concrete Fusion skills, route only by stating the boundary and do not invent
  Fusion-specific operational steps here.

## Conventions we share / adopt

The official [SKILL_AUTHORING_GUIDE](https://github.com/oracle/skills/blob/main/SKILL_AUTHORING_GUIDE.md)
sets the Oracle-wide bar. Where it strengthens this pack we follow it:

- **Official docs first.** `docs.oracle.com` → Oracle-owned repos → Oracle blogs →
  LiveLabs. Verify exact command names, flags, and versions; mark anything
  unverified. We enforce this with the [OKF index](oracle-docs.md) + doc-link
  lint + liveness CI (a stronger guarantee than a static footer).
- **Self-contained skills.** Each skill is usable on its own — same as upstream.
- **Tool-mutation classification.** Upstream asks before mutating; we go further
  with `run_action` and the PreToolUse destructive-op guard hook.
- **Scope boundaries are explicit** (this doc) so navigation stays coherent
  across both packs.

Where we intentionally differ: we keep an `## Official documentation` + **Open
Knowledge Format grounding** footer (liveness-checked) instead of a plain
`## Sources` list, and we carry a `license` field in front matter.

## Using both together

```bash
# 1. Operate the tenancy with this pack (safety-gated, broad).
/oci-administrator:preflight        # confirm tenancy/compartment by name
/oci-administrator:audit            # IAM posture

# 2. Hand off deep OKE / GenAI / in-DB work to the official pack.
/plugin marketplace add oracle/skills
/plugin install oci@oracle-skills   # deep OKE + Enterprise AI
/plugin install db@oracle-skills    # in-database work
```

## Official documentation

[OCI Generative AI](https://docs.oracle.com/en-us/iaas/Content/generative-ai/overview.htm) · [OKE (Kubernetes Engine)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm) · [OKE access control](https://docs.oracle.com/en-us/iaas/Content/ContEng/Concepts/contengaboutaccesscontrol.htm) · [Oracle Fusion Cloud Applications](https://docs.oracle.com/en/cloud/saas/index.html). Full index in [oracle-docs.md](oracle-docs.md); upstream skills at [oracle/skills](https://github.com/oracle/skills).

**Open Knowledge Format grounding** — every doc link here is registered and liveness-checked in the [oracle-docs.md index](oracle-docs.md) (the pack's single source of truth). When routing an Oracle Cloud task, cite the most specific official page through that index; defer deep OKE / GenAI / in-database specifics to the official `oracle/skills` collection rather than inventing them, and never treat the non-official MCP gateway as a source of truth.

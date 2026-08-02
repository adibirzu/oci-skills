# OCI Solution Authoring

Take a **customer requirement** to a **guardrailed OCI architecture**, then hand
off to the lifecycle orchestrator to build it. This is the *design front-end* the
pack was missing: `oci-project` operates a project (bootstrap → status → deploy →
teardown); this reference is the **Stage 0 — Design** that precedes bootstrap and
decides *what* to build, grounded in Oracle's official architecture guidance.

> **Use this when** the input is a requirement ("the customer needs a
> PCI-scoped 3-tier web app", "a landing zone for three teams", "a database
> observability platform") rather than a single service operation. For a
> single-service task use that domain skill directly; to operate an
> already-designed project use [oci-project](../skills/oci-project/SKILL.md).

All identifiers in examples are `<PLACEHOLDER>` tokens — never inline a real
OCID, IP, or tenancy namespace (see [tenancy-safety.md](tenancy-safety.md)).

## Quick navigation

Use How this fits and Workflow for routing, blueprint sections 1-6 for the
deliverable, then implementations, examples, grounding, and sources.

## How this fits

```text
  requirement
      │
      ▼
  ┌─────────────────────────────┐
  │ Stage 0 — Design (this doc) │  → produces a Solution Blueprint
  └─────────────────────────────┘
      │  blueprint feeds the named context (prefix + budget)
      ▼
  oci-project  bootstrap → status → deploy → teardown   (the 9 domains execute)
```

The design stage is **read-only and reversible** — it writes a blueprint, not
cloud resources. Nothing is created until `oci-project bootstrap` runs each
mutation through `run_action`.

## The workflow

Seven steps, each mapped to the domain skill(s) that own it and the official
Oracle doc that grounds the decision. Work top-to-bottom; do not skip discovery.

| # | Step | Decide | Domain skill(s) | Official ground |
|---|------|--------|-----------------|-----------------|
| 1 | **Discovery** | What is the workload, who are the users, what data sensitivity, which regions, what compliance (CIS / ISO / PCI)? | — (interview) | [Architecture Center](https://docs.oracle.com/en/solutions/) |
| 2 | **Requirements → pillars** | Non-functionals per the Well-Architected pillars: security, reliability, performance, cost, operations. | — | [Cloud Adoption Framework](https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/home.htm) |
| 3 | **Reference architecture** | Pick / adapt a proven pattern (3-tier, microservices on OKE, data lake, HA DB). Do not invent topology from scratch. | oci-networking-compute, oci-observability-db | [Architecture Center](https://docs.oracle.com/en/solutions/) |
| 4 | **Guardrail design** | Compartment layout, least-privilege IAM, network isolation (VCN/subnet/NSG), encryption (Vault), budget. Map to a landing-zone baseline. | oci-iam-admin, oci-security-compliance, oci-networking-compute | [CAF — Security pillar](https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/security.htm) · [CIS Benchmark](https://docs.oracle.com/en/solutions/cis-oci-benchmark/index.html) |
| 5 | **Cost shape** | Sizing → estimated spend; set the budget + 80% forecast alert and cost-tracking tags *before* build. | oci-cost, oci-iam-admin | [Security guide](https://docs.oracle.com/en-us/iaas/Content/Security/Concepts/security_guide.htm) |
| 6 | **Build** | Express the design as a Resource Manager stack (preferred) or guided domain calls; bootstrap the project context first. | oci-project, oci-resource-manager | [CAF](https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/home.htm) |
| 7 | **Validate & hand over** | `status` confirms guardrails (budget, tags, Cloud Guard, alarms) cover every new resource; document the blueprint as the run-book. | oci-project, oci-observability-db | [Security guide](https://docs.oracle.com/en-us/iaas/Content/Security/Concepts/security_guide.htm) |

### Step detail

1. **Discovery** — capture the requirement in the customer's words, then
   classify: workload type, data sensitivity, region(s)/residency, availability
   target, and the compliance regime. Browse the [Architecture
   Center](https://docs.oracle.com/en/solutions/) for a matching solution
   playbook before designing.
2. **Requirements → pillars** — translate each requirement into a measurable
   non-functional under a Well-Architected pillar. "Must survive an AD failure"
   → reliability → multi-AD or cross-region. This is what makes the design
   reviewable later.
3. **Reference architecture** — adopt a published pattern and note your
   deviations; an adapted reference architecture beats a hand-rolled topology for
   both correctness and customer trust (same "reuse a proven approach" discipline
   the pack applies to code). For a *deployable, guardrailed* scaffold rather than
   a diagram, start from an official Oracle **Landing Zone** (see Reference
   implementations below) and layer the workload on top.
4. **Guardrail design** — design the guardrails *with* the architecture, never
   after. Compartment per blast-radius boundary, a least-privilege policy scoped
   to that compartment (never `manage all-resources in tenancy`), network
   isolation by tier, encryption keys in Vault, and a budget. Baseline it against
   the CIS benchmark / CAF security pillar — or, better, **adopt an official
   Landing Zone as the guardrail baseline-as-code** so the compartments, IAM,
   network, and logging come pre-aligned: the CIS-aligned
   [oci-cis-landingzone-quickstart](https://github.com/oracle-quickstart/oci-cis-landingzone-quickstart)
   or the modular [Oracle Enterprise Landing Zone](https://github.com/oracle-quickstart/oci-landing-zones).
5. **Cost shape** — size the resources, estimate spend, and set the budget +
   forecast alert and `project = <name>` cost-tracking tag *before* the first
   resource exists, so overruns are caught on day one.
6. **Build** — bind a named context for the project (carrying its prefix +
   budget), then `oci-project bootstrap` and drive infra through a reviewed
   Resource Manager `plan → apply FROM_PLAN_JOB_ID`. Landing Zones ship *as*
   Terraform, so an adopted one deploys directly as a Resource Manager stack
   (→ `oci-resource-manager`); the OKE workload layer can reuse the
   [terraform-oci-oke](https://github.com/oracle-terraform-modules/terraform-oci-oke)
   module.
7. **Validate & hand over** — `oci-project status` proves guardrails cover the
   new resources; the completed blueprint becomes the operational run-book.

## Solution blueprint (the deliverable)

The design stage produces this fillable spec. It is the contract between design
and build, and the hand-over artifact for the customer.

```markdown
# Solution Blueprint — <solution name>

## 1. Context
- Customer / project:        <name>
- Named context (prefix):    <prefix>
- Tenancy / profile:         <profile name, not OCID>
- Region(s):                 <home + DR>
- Compliance regime:         <CIS | ISO-27001 | PCI-DSS | none>

## 2. Requirements (by Well-Architected pillar)
- Security:      <data sensitivity, isolation, encryption, auth model>
- Reliability:   <availability target, AD/region strategy, backup/DR>
- Performance:   <latency/throughput targets, sizing drivers>
- Cost:          <budget ceiling, forecast alert %, chargeback tags>
- Operations:    <monitoring, alarms, log retention, run-book owner>

## 3. Architecture
- Reference architecture:    <Architecture Center link + deviations>
- Topology:                  <tiers/services, VCN/subnet/NSG layout>
- Data:                      <stores, encryption keys, residency>

## 4. Guardrails
- Compartment layout:        <parent → project → sub-compartments>
- IAM:                       <group(s) + scoped policy statements>
- Network isolation:         <subnet tiers, NSG rules, gateways>
- Encryption:                <Vault keys, secrets>
- Budget:                    <limit + 80% forecast alert>
- Tags:                      <project = <name>, cost-tracking>

## 5. Build plan
- IaC:                       <Resource Manager stack | guided domain calls>
- Bootstrap order:           compartment → IAM → network → budget → tags
- Deploy:                    <RM apply | OKE rollout>

## 6. Validation
- status checks:             <inventory, Cloud Guard, alarms, budget forecast>
- Acceptance criteria:       <per-pillar, measurable>
```

## Reference implementations (adopt, don't hand-roll)

Official, Oracle-maintained starting points. Prefer adopting and adapting one of
these over building topology or guardrails from scratch — record your deviations
in the blueprint.

| Implementation | Use for | Source |
|---|---|---|
| **OCI CIS Landing Zone** | A CIS-aligned tenancy baseline as Terraform — compartments, IAM, VCNs, NSGs, logging, Cloud Guard, Vault. The default guardrail scaffold. | <https://github.com/oracle-quickstart/oci-cis-landingzone-quickstart> |
| **Oracle Enterprise Landing Zone** | A modular, larger-scale landing zone (operating-model / multi-team tenancies). | <https://github.com/oracle-quickstart/oci-landing-zones> |
| **Terraform OKE module** | The Kubernetes workload layer on top of a landing zone. | <https://github.com/oracle-terraform-modules/terraform-oci-oke> |
| **Architecture Center** | Reference architectures & solution playbooks (topology patterns by workload). | <https://docs.oracle.com/en/solutions/> |

These deploy through `oci-resource-manager` (they are Terraform/RM stacks). For
deep OKE day-2 operation of the resulting cluster, hand off to `oracle/skills`
`oci/oke` — see [oracle-skills-alignment.md](oracle-skills-alignment.md).

## Worked examples (compact)

**3-tier web app (internet-facing, CIS-baselined).**
Discovery → public web tier + private app tier + private DB. Pillars: reliability
(multi-AD), security (CIS L1). Reference: Architecture Center 3-tier pattern.
Guardrails: one project compartment; scoped policy; public subnet (web) + private
subnets (app, db) with NSGs allowing only tier-to-tier flow; IGW for web, NAT for
egress; Vault key for the DB. Cost: budget + 80% alert. Build: RM stack. Validate:
`status` shows NSGs, budget, and a FIRING-capable alarm on the LB.
→ oci-networking-compute · oci-iam-admin · oci-security-compliance · oci-resource-manager.

**Database observability platform.**
Discovery → register N databases for monitoring, no app tier. Pillars: operations
(metrics + alarms), security (read-only monitoring creds). Reference: DBM/OPSI
enablement. Guardrails: monitoring compartment; least-privilege DBM policy; private
endpoint subnet; DBSNMP/monitoring credential in Vault. Build: enable DBM/OPSI per
database, register Data Safe targets. Validate: Database Insights populated, alarms
on key metrics, Data Safe Security Assessment run.
→ oci-observability-db · oci-data-safe · oci-iam-admin.

## Grounding & safety rules

- **Design is read-only.** Stage 0 writes a blueprint, not resources. Nothing is
  created until `oci-project bootstrap` runs each mutation through the guards.
- **Adopt, don't invent.** Start from an Architecture Center reference
  architecture *or* an official Landing Zone (see Reference implementations) and
  record deviations; baseline guardrails against the CIS benchmark / CAF security
  pillar rather than improvising.
- **Guardrails are part of the design, not a follow-up.** Compartment, scoped
  IAM, network isolation, encryption, and budget are decided *with* the topology.
- **Every claim cites official Oracle docs.** Pull architecture and guardrail
  decisions from the pages registered in [oracle-docs.md](oracle-docs.md); the
  non-official MCP gateway is never a source of truth.

## Official documentation

[Architecture Center](https://docs.oracle.com/en/solutions/) · [Cloud Adoption Framework](https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/home.htm) · [CAF — Security pillar](https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/security.htm) · [Security guide](https://docs.oracle.com/en-us/iaas/Content/Security/Concepts/security_guide.htm) · [CIS Benchmark](https://docs.oracle.com/en/solutions/cis-oci-benchmark/index.html). Full index in [oracle-docs.md](oracle-docs.md). Reference implementations (GitHub): [CIS Landing Zone](https://github.com/oracle-quickstart/oci-cis-landingzone-quickstart) · [Enterprise Landing Zone](https://github.com/oracle-quickstart/oci-landing-zones).

**Open Knowledge Format grounding** — every doc link here is registered and liveness-checked in the [oracle-docs.md index](oracle-docs.md) (the pack's single source of truth). When extending this workflow to design a new OCI customer solution, cite the most specific official page through that index so every claim stays verifiable; the non-official MCP gateway is never a source of truth.

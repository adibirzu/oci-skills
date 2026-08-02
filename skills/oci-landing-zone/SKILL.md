---
name: oci-landing-zone
description: >-
  Assess, design, deploy, upgrade, and validate OCI landing zones and greenfield
  tenancy guardrails using Cloud Adoption Framework and Well-Architected
  guidance. Orchestrates IAM, security, networking, observability, cost,
  Terraform, and Resource Manager while preserving one IaC owner and the existing
  Solution Blueprint. Use when the request mentions a landing zone, greenfield
  tenancy foundation, Cloud Adoption Framework, enterprise guardrails, or
  landing-zone assessment and upgrade. Do not use for an ordinary workload or
  project lifecycle; route that to oci-project.
---

# OCI Landing Zone

Turn organizational, governance, security, networking, and operating-model
requirements into a reviewable Solution Blueprint and a single-owner landing
zone lifecycle. This skill orchestrates owning domains; it does not duplicate
their service operations.

## Routing

| Intent | Owner |
|---|---|
| Landing zone, Cloud Adoption Framework, greenfield tenancy, enterprise guardrails, existing-estate landing-zone assessment | This skill |
| One workload/project bootstrap, health, deploy, teardown | **oci-project** |
| Generic customer solution design without landing-zone scope | Stage 0 **Solution Blueprint** workflow |
| IAM/security/network/cost service operation | Owning domain skill |
| HCL/module review and local execution | **oci-terraform-authoring** |
| Resource Manager stack/job execution | **oci-resource-manager** |

Landing-zone intent takes precedence over generic project or networking terms.
After the blueprint and ownership decision, each service action returns to its
owning domain.

Read [landing-zone.md](../../references/landing-zone.md) for assessment,
blueprint, ownership, deployment, upgrade, validation, and rollback contracts.

## Common multi-step flows

| Task | Sequence |
|---|---|
| Greenfield design | stakeholder/compliance intake → Cloud Adoption Framework and Well-Architected requirements → tenancy/identity/network/security/operations/cost decisions → Solution Blueprint → owner and rollout plan |
| Existing-estate assessment | named-context preflight → read-only inventory by domain → compare desired blueprint to observed state → classify adoption/import/drift risks → phased remediation backlog |
| Deploy | approved blueprint → source/module provenance review → **oci-terraform-authoring** validate/plan/show → choose local Terraform or Resource Manager → reviewed-plan apply → domain verification |
| Upgrade | pin and review source changes → read current state/drift → migration and moved/import design → staged plan → canary compartment → exact-plan rollout → posture validation |
| Validate | IAM separation → network segmentation → security services → logging/monitoring → budgets/tags → break-glass and recovery → evidence pack |

## Safety boundaries

- Assessment and blueprint authoring are read-only/offline. No preflight is
  needed for a hypothetical design; a live existing-estate inventory uses a
  named context and preflight when tenancy scope is ambiguous.
- Terraform is the single owner of durable landing-zone resources. Choose local
  Terraform or Resource Manager for a state/resource set, never both.
- Never apply unreviewed module updates or plan bytes. Module provenance,
  version constraints, lock metadata, state/backend, authentication context,
  realm support, and migration notes are part of review.
- A landing zone may need tenancy-wide permissions during bootstrap. Minimize
  duration, separate bootstrap from steady-state operators, and verify removal.
- Compliance blueprints are starting points, not automatic certification.

## Verification and rollback

Validate the blueprint acceptance matrix across all owning domains, record gaps
and exceptions, inspect drift, and confirm steady-state administration. Rollback
uses the exact reviewed Terraform plan and migration strategy; destructive
teardown requires dependency inventory and exact approval. Never mix manual CLI
rollback with Terraform ownership without immediate HCL reconciliation.

## Expected output

Report scope and assumptions, selected landing-zone family or custom blueprint,
current-state evidence, decision/ownership matrix, phased plan, reviewed sources,
validation evidence, exceptions, rollback, and domain handoffs.

## Official documentation

[Technology implementation](https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/landing-zone-v1.htm) · [OCI Core Landing Zone](https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/oci-core-landing-zone.htm) · [Well-Architected landing zones](https://docs.oracle.com/en/solutions/oci-best-practices/simplify-provisioning-oci-landing-zones1.html). Full index in [oracle-docs.md](../../references/oracle-docs.md).

**Open Knowledge Format grounding** — every Oracle documentation link is
registered and liveness-checked in the pack's central index.

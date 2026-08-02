---
name: oci-product-development
description: >-
  Compose secure OCI platform bundles for five product-development golden paths: API Gateway with Functions, Container Instances applications, OKE applications, Queue or Streaming event workers, and ADB-backed services. Use when a user asks to design, scaffold, or deploy an OCI application platform, select a runtime/ingress/data/delivery stack, or create platform-bundle.yaml. Produces infrastructure, delivery, IAM, OpenAPI, verification, and runbook artifacts—not business application logic.
---

# OCI product development

Turn product requirements into an owner-explicit platform bundle. Artifact generation is offline; deployment requires a named context, preflight, plan review, and risk-specific approval.

## Intake

Resolve runtime constraints, ingress audience, data durability, traffic/SLOs, compliance, recovery objectives, budget, region/availability, delivery source, and operator model. Default to private ingress, Vault references, least privilege, encryption, logs, alarms, budgets, and Terraform ownership.

## Golden paths

| Path | Bundle selection | Primary handoffs |
|---|---|---|
| Secure API | Functions + API Gateway | developer-services, events-functions |
| Container application | Container Instances + load balancer | developer-services, networking-compute |
| OKE application | OKE + load balancer | oke-admin, developer-services |
| Event worker | Queue or Streaming + consumer | events-functions; developer-services for delivery only |
| Data-backed service | Functions + private ADB + API Gateway | autonomous-db, developer-services |

All paths compose IAM, networking, security, observability, cost, Terraform, and DevOps. See [product-development.md](../../references/product-development.md) for the ownership matrix and acceptance checks.

## Bundle workflow

1. Scaffold offline: `python3 ../../scripts/platform_bundle.py scaffold <golden-path> <output> --name <name> --context <context>`; for `event-worker`, select `--event-transport queue|streaming`.
2. Validate `platform-bundle.yaml` and inspect the generated ownership metadata.
3. Have each owning domain materialize its component in `terraform/`; keep application code outside the bundle.
4. Validate Terraform and the CLI alternative; review IAM, quota, network, logging, public exposure, and secrets.
5. Preflight, plan, approve, apply, and verify. Record named checks in the runbook.
6. Roll back through DevOps or the reviewed Terraform plan. Reconcile any break-glass CLI mutation.

If a context, provider, or approval is not available, still complete steps 1–2
and the offline ownership, OpenAPI-boundary, delivery-specification, and runbook
work. Report the one later live gate instead of treating it as a block on design
or scaffolding.

## Common multi-step flows

| Request | Sequence |
|---|---|
| Generate a bundle | intake → choose golden path → scaffold → schema validation → owner review; no credentials required |
| Deploy a bundle | context select → preflight → domain materialization → validate → plan → approval → apply → named checks |
| Inspect health | **oci-project** status → bundle verification list → owning domain diagnostics |
| Tear down | refreshed Terraform destroy plan → dependency review → destructive approval → verify → compartment last via **oci-project** |

## Boundary

Do not generate business handlers, domain models, UI, or application tests. Generate only platform/IaC, OpenAPI boundary, build/deploy specifications, IAM requirements, verification, and operations material.

## Official documentation

[Architecture Center](https://docs.oracle.com/en/solutions/) · [Cloud Adoption Framework](https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/home.htm) · [OCI DevOps](https://docs.oracle.com/en-us/iaas/Content/devops/using/devops_overview.htm). Full list in the [product-development reference](../../references/product-development.md).

**Open Knowledge Format grounding** - every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill, cite the most specific official page through that index; the non-official MCP gateway is never a source of truth.

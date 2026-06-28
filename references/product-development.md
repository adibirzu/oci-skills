# OCI product-development bundles

## Schema v1

`platform-bundle.yaml` is validated by `scripts/platform_bundle.py` and `schemas/platform-bundle.schema.json`. Required fields are schema version, safe name, named context, runtime, ingress, data, `oci-devops` delivery, Terraform owner/path, and named verification checks.

## Ownership matrix

| Component | Primary owner | Handoff |
|---|---|---|
| Bundle intake/composition | `oci-product-development` | Never owns service mutation. |
| Terraform HCL/plan/state | `oci-terraform-authoring` | Stack/job execution to `oci-resource-manager`. |
| DevOps/API Gateway/Container Instances/artifacts | `oci-developer-services` | Runtime handoffs below. |
| Functions/Events/Queue/Streaming | `oci-events-functions` | DevOps owns delivery only. |
| OKE application/cluster operations | `oci-oke-admin` | DevOps owns delivery only. |
| ADB | `oci-autonomous-db` | In-database work routes to official Oracle database skills. |
| Network/load balancer | `oci-networking-compute` | OKE-specific LB behavior routes to OKE. |
| IAM/security/observability/cost | Matching domain skill | Cross-cutting requirements in every path. |
| Lifecycle/status/teardown plan | `oci-project` | Consumes the bundle after design. |

## Golden-path acceptance

Every bundle contains Terraform, a wrapper-routed CLI alternative, least-privilege IAM requirements, OpenAPI boundary, DevOps build/deploy specifications, verification checks, and a runbook. It contains no application business logic.

Before deployment, verify quotas, private networking, encryption, secret references, logs/alarms, cost guardrail, rollout/rollback, and one owner per durable resource. A bundle may be generated without credentials. Live apply requires a named-context preflight, reviewed plan identity, and risk-specific approval.

The event-worker path defaults to Queue. Pass `--event-transport streaming` when ordered partition logs, replay, Kafka compatibility, or consumer offsets are required; Queue remains the transactional at-least-once choice.

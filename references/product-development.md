# OCI product-development bundles

## Scaffold response contract

Use the bundled interface exactly—do not invent bundle-type, runtime, ingress,
data, delivery, or output flags:

```text
python3 scripts/platform_bundle.py scaffold <golden-path> <output> --name <name> --context <context>
```

`<golden-path>` is exactly one of `adb-service`, `api-functions`,
`container-instances`, `event-worker`, or `oke-application`. Only `event-worker`
accepts the optional `--event-transport queue|streaming`. When execution is
unavailable, return this invocation plus the generated-path/ownership contract;
do not inline or claim to have written bundle, Terraform, OpenAPI, source, or
pipeline files.

No preflight is required to scaffold: `<context>` is a named label in the offline
artifact. This scaffold does not deploy or contact OCI. For a scaffold-only
request, do not include plan/apply commands or ask for credentials; deployment is
a separate, preflighted request.

The exact generated top-level contract is:

- `platform-bundle.yaml` and `BUNDLE_METADATA.json`
- `terraform/` (the reviewed starter plus `components.tf`)
- `cli/command-plan.json`
- `iam/policies.md`
- `delivery/build_spec.yaml` and `delivery/deploy_spec.yaml`
- `openapi/openapi.yaml`
- `runbook.md`

It never generates application source, handlers, models, tests, or business logic.
`BUNDLE_METADATA.json` contains only schema version, golden path, Terraform owner,
component names, and optional event transport; it contains no hash or fingerprint.
The `terraform/` directory is a generic Terraform starter; `components.tf` is an
inventory only and does not contain service resource HCL. API Gateway, Functions,
ADB, networking, Queue/Streaming, and other service HCL are materialized later by
their owning skills before validate/plan. Never claim the offline scaffold has
already provisioned, configured, or fully authored those resources.

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

Every bundle contains Terraform, a wrapper-routed CLI alternative, least-privilege IAM requirements, OpenAPI boundary, DevOps build/deploy specifications, verification checks, and a runbook. No business logic belongs in the bundle.

Before deployment, verify quotas, private networking, encryption, secret references, logs/alarms, cost guardrail, rollout/rollback, and one owner per durable resource. A bundle may be generated without credentials. Live apply requires a named-context preflight, reviewed plan identity, and risk-specific approval.

The scaffold is an offline artifact operation: it does not deploy or contact OCI.
Return the scaffold command and generated paths rather than inlining the generated
files. Queue and Streaming consumers must be idempotent; document retry,
poison-message/dead-letter or offset/checkpoint behavior, empty reads, and replay.

The event-worker path defaults to Queue. Pass `--event-transport streaming` when ordered partition logs, replay, Kafka compatibility, or consumer offsets are required; Queue remains the transactional at-least-once choice.

---
name: oci-developer-services
description: >-
  Design, provision, deliver, inspect, and roll back OCI developer platforms: DevOps projects, code repositories and external connections, build pipelines/specifications, artifacts, environments, deployment pipelines and triggers, API Gateway, Container Instances, Artifact Registry, and OCIR delivery. Use for OCI CI/CD, private APIs, container deployments, blue-green or canary releases, and DevOps-to-OKE/Functions/instance-group targets. Hand off runtime ownership to the matching OKE, Functions, networking, or Terraform skill.
---

# OCI Developer Services

Default API gateways, build runners, target environments, and workloads to private networking. Make public exposure an explicit reviewed requirement.

## Workflow

1. Preflight the named context and read existing resources by display name.
2. Check service limits, IAM for both operators and resource principals, subnet/NSG reachability, log availability, and target health.
3. Author durable resources with **oci-terraform-authoring**. Use exact wrapper-routed CLI plans for inspection or unsupported/recovery operations.
4. Keep source connection tokens, image-pull credentials, and deploy secrets in Vault; reference them from DevOps or runtime principals.
5. Build immutable artifacts, attach provenance/SBOM evidence, and apply the `oci-security-compliance` release gate. OCI DevOps ADM vulnerability audits support Maven builds; hand off other ecosystems to an approved scanner rather than claiming coverage.
6. Deploy with a canary or blue-green stage plus automatic rollback.
7. Verify pipeline state, target health, Cloud Guard/WAF posture, logs, alarms, and the user-visible route. Exercise rollback before production.

Read [developer-services.md](../../references/developer-services.md) for detailed flows, ownership, IAM, network, logging, and rollback checks.
Reuse `assets/terraform/private-platform/` for provider-schema-validated private
DevOps project, API Gateway, and Container Instance resources; materialize only
the components selected by the design.

## Common multi-step flows

| Request | Sequence |
|---|---|
| DevOps CI/CD | quota/IAM/network/log checks → project → repository/connection → build pipeline/spec → artifact → environment → deployment pipeline → trigger → canary → verify/rollback |
| API Gateway to Function | private regional subnet → gateway → function-principal IAM → deployment spec from file → logs/rate/auth policy → invoke/verify; Function runtime belongs to **oci-events-functions** |
| Container Instance | image/artifact → Vault pull secret → private subnet/NSG → container instance → logs/metrics → health → rollback to immutable image |
| OKE delivery | DevOps project/pipeline here → OKE environment and rollout in **oci-oke-admin** |
| Function delivery | DevOps project/pipeline here → application/function lifecycle in **oci-events-functions** |
| Instance-group delivery | pipeline here → compute/network target in **oci-networking-compute** |

## Command contract

- Query installed command shapes with `../../scripts/oci_cli_help.py --json <path>`.
- Store each read/action/verification/rollback plan as JSON and lint it with `../../scripts/oci_cli_lint.py`.
- Put nested payloads and credentials in a temporary `0600` file, pass `file://...`, and delete it in a trap/finally block.
- Run mutations through `run_action` with the matching risk and compartment.

## Expected output

Report the owner of every component, quota/IAM/network/log checks, artifact identity, rollout strategy, exact verification, and rollback result. Do not expose endpoints, namespaces, image-pull tokens, or connection credentials.

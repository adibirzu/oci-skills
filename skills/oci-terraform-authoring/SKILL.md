---
name: oci-terraform-authoring
description: >-
  Author, discover, format, validate, test, plan, inspect, apply, and destroy OCI
  Terraform configurations. Use for local Terraform, provider schema, discovery,
  reviewed plans, Resource Manager-compatible packages, state ownership, drift,
  declarative import and moved blocks, native OCI Object Storage backends,
  execution-context authentication, sovereign realms, modules, or HCL. Existing
  Resource Manager stack and job operations remain with oci-resource-manager.
---

# OCI Terraform authoring

Create reviewable infrastructure artifacts without contacting OCI. Contact OCI only for discovery, planning, or an explicitly approved apply/destroy after a named-context preflight.

## Workflow

1. Establish the owner. Default durable resources to `terraform`; never give the same resource to direct CLI and Terraform.
2. Scaffold with `../../scripts/oci_tf.sh scaffold <dir> --name <name>` immediately; it is a safe offline action.
3. Resolve resource fields from `terraform providers schema -json` after `terraform init`, or from the current official OCI provider docs. Never invent a field.
4. Keep credentials out of HCL and variable files. Use provider config, environment variables, workload/resource principals, or Vault references.
5. Validate with `oci_tf.sh validate <dir>` and run `.tftest.hcl` tests with mocked providers where possible. If a local prerequisite is missing, deliver the scaffold and the exact next local command rather than stopping the workflow.
6. Preflight the named context only before creating a binary reviewed plan with `oci_tf.sh plan`.
7. Inspect the metadata-only plan summary. Stop on unexpected replacement/deletion, public exposure, or secret-bearing resources.
8. Apply the unchanged plan with `oci_tf.sh apply`; use `destroy` only with a separately reviewed destroy plan and destructive approval.
9. Verify resource state and reconcile any prior CLI break-glass change.
10. For team state, prefer the native OCI Object Storage backend when the
    reviewed runtime supports it; treat the legacy S3-compatible backend as a
    deprecated fallback and never place credentials in backend HCL.

Read [terraform-authoring.md](../../references/terraform-authoring.md) for command contracts, provider-schema grounding, discovery, packaging, and state rules.

## Common multi-step flows

| Request | Sequence |
|---|---|
| Write Terraform | intake → scaffold → provider schema/docs → HCL + tests → fmt/init/validate |
| Discover existing resources | preflight → empty destination → `discover` → review generated HCL → remove secrets → choose import/ownership |
| Deploy locally | preflight → validate → plan → inspect summary → exact-plan apply → service verification |
| Deploy with Resource Manager | author here → package source + `schema.yaml` → hand off stack/job operations to **oci-resource-manager** |
| Adopt existing resources | prove inventory/ownership → author resource and declarative import blocks → reviewed plan/import → verify zero unintended change |
| Refactor addresses | retain `moved` blocks → plan for no replacement → review consumers → exact-plan apply → verify state addresses |
| Investigate drift | refresh-backed plan → classify change → update HCL or restore through owner → reviewed plan → verify convergence |
| Configure team state | prefer native OCI backend → verify auth/protection/concurrency → migrate once → test recovery without exposing state |
| Destroy | refreshed destroy plan → dependency review → exact destructive approval → apply reviewed plan → verify absence |

## Safety boundaries

- Missing context, preflight, live credentials, or approval never blocks offline authoring, tests, validation, review, or documentation; it blocks only the later live operation that requires it.
- Never print or commit state, plan binaries, `.terraform/`, wallets, private keys, or `terraform.tfvars`.
- Reject symlinked or non-empty discovery destinations.
- A plan review sidecar is context- and content-bound; changed bytes require a new review.
- Resource discovery is a starting point, not migration proof.
- State can contain secrets even when values are marked sensitive. Encrypt and
  access-control it, serialize writers, and never log or attach it.
- Match authentication to the execution context: named local profile or
  short-lived token, instance/resource principal, OKE workload identity, or
  Resource Manager. Never embed key material in provider/backend configuration.
- Pin Terraform, provider, and module constraints; commit reviewed lock metadata;
  review module provenance, checksums, licenses, nested dependencies,
  provisioners, public exposure, and upgrade/migration notes.
- Resolve realm/region endpoints from the installed provider and current
  official docs. Do not hardcode commercial-realm domains; use the applicable
  FIPS-compatible provider where Oracle requires it.
- CLI may inspect or recover. A CLI mutation against a Terraform-owned resource is break-glass and must be followed by `terraform plan` reconciliation.

## Expected output

Report artifact paths, source/schema used, validation result, plan action counts, approval state, verification, and rollback. Never reproduce state or sensitive planned values.

## Official documentation

[OCI Terraform provider](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/) · [Resource discovery](https://docs.oracle.com/en-us/iaas/Content/terraform/resource-discovery.htm) · [Terraform on OCI](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/home.htm). Full list in the [terraform-authoring reference](../../references/terraform-authoring.md).

**Open Knowledge Format grounding** - every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill, cite the most specific official page through that index; the non-official MCP gateway is never a source of truth.

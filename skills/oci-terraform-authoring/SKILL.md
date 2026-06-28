---
name: oci-terraform-authoring
description: >-
  Author, discover, format, validate, test, plan, inspect, apply, and destroy Oracle Cloud Infrastructure Terraform configurations. Use for local Terraform, OCI provider schema questions, resource discovery, reviewed plan execution, Resource Manager-compatible packages, schema.yaml, Terraform state ownership, drift, imports, or requests to write HCL. Do not use for operating existing Resource Manager stacks or jobs; route those to oci-resource-manager.
---

# OCI Terraform authoring

Create reviewable infrastructure artifacts without contacting OCI. Contact OCI only for discovery, planning, or an explicitly approved apply/destroy after a named-context preflight.

## Workflow

1. Establish the owner. Default durable resources to `terraform`; never give the same resource to direct CLI and Terraform.
2. Scaffold with `../../scripts/oci_tf.sh scaffold <dir> --name <name>`.
3. Resolve resource fields from `terraform providers schema -json` after `terraform init`, or from the current official OCI provider docs. Never invent a field.
4. Keep credentials out of HCL and variable files. Use provider config, environment variables, workload/resource principals, or Vault references.
5. Validate with `oci_tf.sh validate <dir>` and run `.tftest.hcl` tests with mocked providers where possible.
6. Preflight the named context, then create a binary reviewed plan with `oci_tf.sh plan`.
7. Inspect the metadata-only plan summary. Stop on unexpected replacement/deletion, public exposure, or secret-bearing resources.
8. Apply the unchanged plan with `oci_tf.sh apply`; use `destroy` only with a separately reviewed destroy plan and destructive approval.
9. Verify resource state and reconcile any prior CLI break-glass change.

Read [terraform-authoring.md](../../references/terraform-authoring.md) for command contracts, provider-schema grounding, discovery, packaging, and state rules.

## Common multi-step flows

| Request | Sequence |
|---|---|
| Write Terraform | intake → scaffold → provider schema/docs → HCL + tests → fmt/init/validate |
| Discover existing resources | preflight → empty destination → `discover` → review generated HCL → remove secrets → choose import/ownership |
| Deploy locally | preflight → validate → plan → inspect summary → exact-plan apply → service verification |
| Deploy with Resource Manager | author here → package source + `schema.yaml` → hand off stack/job operations to **oci-resource-manager** |
| Destroy | refreshed destroy plan → dependency review → exact destructive approval → apply reviewed plan → verify absence |

## Safety boundaries

- Never print or commit state, plan binaries, `.terraform/`, wallets, private keys, or `terraform.tfvars`.
- Reject symlinked or non-empty discovery destinations.
- A plan review sidecar is context- and content-bound; changed bytes require a new review.
- Resource discovery is a starting point, not migration proof.
- CLI may inspect or recover. A CLI mutation against a Terraform-owned resource is break-glass and must be followed by `terraform plan` reconciliation.

## Expected output

Report artifact paths, source/schema used, validation result, plan action counts, approval state, verification, and rollback. Never reproduce state or sensitive planned values.

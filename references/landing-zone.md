# OCI landing-zone reference

## Purpose and deliverables

A landing zone is the governed tenancy foundation for multiple workloads, not a
synonym for one project. Reuse the existing Solution Blueprint format and add a
landing-zone decision matrix covering identity, compartments, policy and
break-glass administration; network topology and connectivity; security and
compliance guardrails; centralized logs/monitoring; tags, budgets, quotas, and
cost allocation; DNS/key/backup dependencies; operating model; IaC ownership;
rollout waves; exceptions; validation; and recovery.

Assess and design here. IAM, security, networking, observability, cost,
Terraform, and Resource Manager remain authoritative for their own operations.

## Lifecycle

### Assess

For an existing estate, perform read-only inventories through the owning domains
after context selection. Record observed versus desired state, unmanaged
resources, policy overlap, public exposure, missing telemetry, tag/budget gaps,
state ownership, realm/region constraints, and migration dependencies. Empty or
inconsistent output is inconclusive until permission, region, tenancy, and time
scope are verified.

### Design

Start with business units, environments, regulatory obligations, residency,
connectivity, identity source, segregation of duties, recovery objectives,
operations, and cost allocation. Select an official landing-zone family only
after these requirements; otherwise document a custom composition. A published
blueprint is guidance, not evidence that the deployed tenancy is compliant.

### Deploy

Review module source, version constraints, lock metadata, dependencies, provider
schema, backend, authentication context, realm compatibility, variables, and
upgrade notes. Use `./scripts/oci_tf.sh validate`, `plan`, `show`, and `apply`
for local execution, or package the same root for `oci-resource-manager`.
Terraform remains the single owner. Exact reviewed plan bytes, sidecar, and a
matching context-bound preflight are mandatory before apply.

### Upgrade

Inventory drift first. Compare source/module changes, provider constraints,
resource address changes, input migrations, and destructive actions. Prefer
declarative import and `moved` blocks where the reviewed Terraform/provider
versions support them. Prove the path in a non-production/canary compartment,
then roll out in bounded waves with validation after each wave.

### Validate

Validate requirements and controls, not merely resource existence. Include IAM
separation and bootstrap-admin removal; network segmentation and egress; Cloud
Guard/Security Zones/Vault/ZPR choices; audit/log retention and alarms; tags,
budgets and quotas; backup/recovery; state/backend protection; break-glass; drift;
and domain-specific workload readiness.

## Rollback and adoption

Prefer staged adoption of existing resources over recreation. An import plan is
not ownership proof until configuration, state, and the next reviewed plan agree.
Rollback follows the reviewed module migration path or exact reviewed plan.
Manual CLI intervention is break-glass and must be reconciled immediately in HCL
and a refreshed plan.

## Official documentation

- [Cloud Adoption Framework technology implementation](https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/landing-zone-v1.htm)
- [OCI Core Landing Zone](https://docs.oracle.com/en-us/iaas/Content/cloud-adoption-framework/oci-core-landing-zone.htm)
- [Well-Architected OCI Landing Zones](https://docs.oracle.com/en/solutions/oci-best-practices/simplify-provisioning-oci-landing-zones1.html)
- [Resource Manager and Terraform](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Concepts/resource-manager-and-terraform.htm)

All URLs are registered in [oracle-docs.md](oracle-docs.md).

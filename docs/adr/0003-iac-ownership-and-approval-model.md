# ADR 0003: IaC ownership and risk-bound approval

Status: Accepted
Date: 2026-06-28

## Context

v1 operated OCI safely but could manage Resource Manager jobs without authoring or locally validating Terraform. Direct CLI and Terraform could also become competing owners. The legacy `run_mutating` wrapper did not itself require a recent target preflight or distinguish destructive and credential risk.

## Decision

1. Terraform is the default owner of durable platform resources.
2. Local Terraform and OCI Resource Manager may execute the same configuration pattern but never own/apply the same live resources concurrently.
3. `oci-terraform-authoring` owns HCL, provider-schema grounding, discovery, validation, testing, plan review, and local execution. `oci-resource-manager` owns stack and job operations.
4. `oci-product-development` selects/composes platform bundles; service skills materialize their components; `oci-project` owns lifecycle/status/teardown planning.
5. OCI CLI is the inspection/recovery/unsupported-resource surface. A direct mutation of a Terraform-owned resource is break-glass followed by reconciliation.
6. Replace ambiguous mutation calls with:

   ```text
   run_action --risk additive|in-place|destructive|credential \
     --compartment <COMPARTMENT_OCID> --description <ACTION> -- <COMMAND...>
   ```

7. Every live action needs a recent context-bound preflight receipt. Destructive/credential non-interactive actions need the exact dry-run approval identifier. Production force needs an additional audited break-glass variable.
8. `run_mutating` remains a deprecated additive compatibility alias through v2.
9. `platform-bundle.yaml` schema v1 declares Terraform as owner and prevents path/owner ambiguity.

## Consequences

- Plan/apply identity and approvals cannot be replayed against changed bytes, argv, risk, or context.
- CI can generate and validate artifacts without OCI credentials and never mutates a tenancy.
- Operators must explicitly reconcile emergency CLI changes.
- Existing scripts using the compatibility alias need gradual risk classification.
- Final `v2.0.0` promotion requires coverage, security, and fresh-agent evidence; release-candidate packaging may proceed first.

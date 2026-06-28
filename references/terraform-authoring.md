# OCI Terraform authoring reference

## Ownership and sources

Terraform owns durable resources by default. Resource Manager is an execution surface for the same configuration, not a second owner. Direct CLI mutations against Terraform-owned resources are break-glass operations and must be followed by a refresh-only/normal plan and reconciliation.

Resolve fields in this order:

1. Installed `terraform providers schema -json` for the selected provider.
2. Current [OCI Terraform provider documentation](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/).
3. Current [resource discovery documentation](https://docs.oracle.com/en-us/iaas/Content/terraform/resource-discovery.htm).

## `oci_tf.sh` contract

| Command | Effect |
|---|---|
| `scaffold DIR` | Offline, empty-directory-only starter with version/provider/variables/outputs/ignores/schema/tests. |
| `discover DIR --compartment ID` | Requires current preflight; performs read-only provider export to an empty directory and does not request generated state. |
| `validate DIR` | `fmt -check`, `init -backend=false`, `validate`, then forbidden-artifact check. |
| `plan DIR --compartment ID [--destroy]` | Requires current preflight; writes a `0600` binary plan plus a `0600` context/content/risk review sidecar and prints metadata only. |
| `show PLAN` | Prints action counts, resource addresses, public-exposure signals, and secret-bearing resource addresses—never values. |
| `apply` / `destroy` | Verifies exact bytes, context, kind, and reviewed risk, then calls `run_action`; plans with replace/delete and every destroy are destructive. |

Discovery output is a reviewable starting point. Check dependencies, unsupported resources, generated state, credentials, imports, lifecycle settings, and target compartment before adopting ownership.

## State and artifact rules

- Use a remote encrypted backend with locking for teams; one state writer at a time.
- Never echo, attach, or commit state or binary plans.
- Mark sensitive variables and outputs, but remember sensitivity is display suppression—not encryption.
- Ignore `.terraform/`, state, plans, tfvars, wallets, keys, archives, and crash logs.
- Pin provider constraints and commit the dependency lock file after reviewed initialization.
- Review module/provider source, checksum, and version before init; do not run untrusted provisioners.

## Resource Manager package

Package the same root module and optional `schema.yaml`. Hand stack creation, plan/apply/destroy jobs, logs, and state retrieval to `oci-resource-manager`. Never apply locally and through Resource Manager to the same state/resources.

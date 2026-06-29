# OCI Terraform authoring reference

## Authoring response contract

Use `./scripts/oci_tf.sh scaffold <dir> --name <name>` to create the reviewed
starter, then resolve added resource fields from `terraform providers schema
-json` or the current official provider documentation. Run the bundled helper
when an execution tool is available.

When execution is unavailable, do not inline HCL, provider versions, resource
fields, backend examples, or generated files from memory. Return only the exact
scaffold invocation, expected artifact paths, schema/source requirement, secure
defaults, and the `validate → plan → show → apply` workflow. State that the
configuration still needs materialization and validation; never label remembered
HCL production-ready.

Keep that fallback at most two short code blocks and eight bullets. Do not list resource field names,
variable names, backend technologies, regions, shapes, or
provider versions. The reviewed starter already pins the official provider source
as `oracle/oci`; use its lock metadata and the installed schema rather than naming
a version from memory. It is enough to state the invariant: private subnet, no
public IP, Terraform as owner, and schema-grounded validation before planning.

The exact starter inventory is `.gitignore`, `.terraform.lock.hcl`, `versions.tf`,
`provider.tf`, `variables.tf`, `outputs.tf`, `locals.tf`, `schema.yaml`,
`terraform.tfvars.example`, and `tests/starter.tftest.hcl`. There is no `main.tf`.
Do not show raw `terraform` initialization, import, plan, or apply commands in the
fallback; the `oci_tf.sh` wrapper owns those flows. The scaffold invocation is the
only fenced code block in a no-execution fallback. Describe validation, plan
review, and exact-plan apply as the required next lifecycle without guessing
their positional arguments.

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

Refuse an apply when the plan lacks exact reviewed plan bytes, its review sidecar,
or a matching context-bound preflight. A verbal approval cannot replace plan
identity or review metadata. Discovery requires an empty destination and does not
request generated state; it is not ownership or migration proof.

## State and artifact rules

- Use a remote encrypted backend with locking for teams; one state writer at a time.
- Never echo, attach, or commit state or binary plans.
- Mark sensitive variables and outputs, but remember sensitivity is display suppression—not encryption.
- Ignore `.terraform/`, state, plans, tfvars, wallets, keys, archives, and crash logs.
- Pin provider constraints and commit the dependency lock file after reviewed initialization.
- Review module/provider source, checksum, and version before init; do not run untrusted provisioners.

## Resource Manager package

Package the same root module and optional `schema.yaml`. Hand stack creation, plan/apply/destroy jobs, logs, and state retrieval to `oci-resource-manager`. Never apply locally and through Resource Manager to the same state/resources.

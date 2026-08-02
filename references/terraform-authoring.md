# OCI Terraform authoring reference

## Quick navigation

Use response and progress rules first, then select ownership, `oci_tf.sh`,
state/artifacts, Resource Manager packaging, or authoritative sources.

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

## Progress-first Terraform work

Scaffold and local validation are offline work. Run `scaffold` immediately for
safe authoring requests and run `validate` whenever the local toolchain is
available. If a local prerequisite is absent, return the generated artifact and
the exact validation command with the missing prerequisite; do not turn that
into a refusal to author, review, test, or document the module.

Discovery, planning, apply, and destroy touch a tenancy or its durable state.
They retain their existing context, preflight, review, and approval gates. When
one of those gates is unavailable, pause only the live operation that needs it
and complete the useful local work: starter/module structure, provider-schema
research plan, test skeleton, ownership decision, validation checklist, and
handoff record. Do not make a missing context, preflight, provider credential,
or approval a reason to withhold the local artifact.

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

For discovery, do not scaffold the discovery destination first. Create or select a
new empty directory and pass it directly to `oci_tf.sh discover`; the provider
export populates it. A non-empty destination—including a starter scaffold—must be
rejected.

## State and artifact rules

- Prefer the native OCI Object Storage backend when the reviewed Terraform
  runtime supports it. The S3-compatible Object Storage backend is deprecated
  and is a legacy fallback only.
- Use a remote encrypted backend with tested concurrency controls for teams; one
  state writer at a time. Verify locking behavior rather than assuming it.
- Never echo, attach, or commit state or binary plans.
- Mark sensitive variables and outputs, but remember sensitivity is display suppression—not encryption.
- Ignore `.terraform/`, state, plans, tfvars, wallets, keys, archives, and crash logs.
- Pin provider constraints and commit the dependency lock file after reviewed initialization.
- Review module/provider source, checksum, and version before init; do not run untrusted provisioners.

### Execution-context authentication

Choose authentication for where Terraform executes: a named local profile/API
key, short-lived security token, instance principal, resource principal, OKE
workload identity, or Resource Manager-managed execution. Prefer workload
identity/principals over long-lived user keys when supported. Keep secrets and
private-key contents out of HCL, tfvars, backend settings, plan output, and argv.
Validate short-lived token lifetime before a long plan or apply.

### Adoption, refactoring, and drift

There is no `oci_tf.sh import` subcommand. Author declarative `import` blocks and
matching resource configuration, resolve identity syntax from current provider
docs, and use the normal wrapped plan/review/apply lifecycle. Map each remote
object to exactly one address. Adoption is complete only when the next reviewed
plan has no unintended change.

Use and retain declarative `moved` blocks for address changes so consumers avoid
destroy/recreate. Removing historical moves is a breaking change. For drift,
inspect a refresh-backed reviewed plan, decide whether the out-of-band change is
accepted or reverted, then update HCL or restore through the declared owner.
Never use state-only refresh as a shortcut around review.

### Realms and module quality

The OCI provider is region agnostic, but realms, service availability, DNS
suffixes, and FIPS requirements differ. Resolve realm/endpoints from the
installed provider and current Oracle docs; never hardcode commercial-realm
domains. Oracle directs US Government and US Defense Cloud users to the
FIPS-compatible provider.

Review modules as supply-chain dependencies: source ownership, immutable
version, checksum/lock metadata, license, maintenance, nested modules/providers,
provisioners, public exposure, sensitive outputs/state, tests, upgrade notes,
and `moved`/import migrations.

## Resource Manager package

Package the same root module and optional `schema.yaml`. Hand stack creation, plan/apply/destroy jobs, logs, and state retrieval to `oci-resource-manager`. Never apply locally and through Resource Manager to the same state/resources.

## Additional authoritative sources

- [Using Object Storage for state](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/object-storage-state.htm)
- [Configuring OCI provider authentication](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/configuring.htm)
- [OCI provider availability and FIPS](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/home.htm)
- [Specifying versions](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/specifying-versions.htm)
- [Terraform import blocks](https://developer.hashicorp.com/terraform/language/import)
- [Terraform moved blocks](https://developer.hashicorp.com/terraform/language/modules/develop/refactoring)
- [Terraform drift](https://developer.hashicorp.com/terraform/tutorials/state/resource-drift)

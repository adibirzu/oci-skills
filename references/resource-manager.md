# OCI Resource Manager (ORM / Terraform) Reference

Sanitized command shapes for **OCI Resource Manager** — managed Terraform as
stacks + plan/apply/destroy jobs. Every CLI call goes through `oci_cli` from
`scripts/common.sh`; apply/destroy jobs are **mutations** and go through
`run_mutating` / `confirm`. Read `tenancy-safety.md` and `helper-conventions.md`
first. Use `<PLACEHOLDER>` tokens — never inline real OCIDs.

ORM runs your Terraform in an Oracle-managed execution environment, keeps the
state for you, and records every plan/apply/destroy as an auditable **job**. The
unit is a **stack** (a Terraform config + variables + state); you act on it with
**jobs**.

## Lifecycle (create → plan → apply → destroy)

```bash
# 1. Create a stack from a zipped Terraform dir or a folder. Variables are a flat
#    name->string map; complex values are JSON-encoded strings.
run_mutating "create stack" oci_cli resource-manager stack create \
  --compartment-id <COMPARTMENT_OCID> \
  --config-source <PATH_TO_ZIP_OR_TF_DIR> \
  --display-name <NAME> \
  --variables file://vars.json \
  --terraform-version "1.5.x"

# 2. PLAN first — always. Read the plan output before applying.
run_mutating "plan" oci_cli resource-manager job create-plan-job --stack-id <STACK_OCID>
oci_cli resource-manager job get-job-logs-content --job-id <PLAN_JOB_OCID>   # human-readable plan

# 3. APPLY. AUTO_APPROVED reuses the latest plan; or point at a specific plan job.
run_mutating "apply" oci_cli resource-manager job create-apply-job --stack-id <STACK_OCID> \
  --execution-plan-strategy AUTO_APPROVED
# safer: bind to a reviewed plan
#   --execution-plan-strategy FROM_PLAN_JOB_ID --execution-plan-job-id <PLAN_JOB_OCID>

# 4. DESTROY.
run_mutating "destroy" oci_cli resource-manager job create-destroy-job --stack-id <STACK_OCID> \
  --execution-plan-strategy AUTO_APPROVED
```

## Waiting on jobs (the #1 ORM trap)

```bash
# Poll lifecycle-state and break on ALL terminal states. Do NOT rely on
# `--wait-for-state SUCCEEDED` alone — a FAILED/CANCELED job is != SUCCEEDED, so
# the CLI polls for the full --max-wait window instead of returning (see KB-007).
job=<JOB_OCID>
while :; do
  st="$(oci_cli resource-manager job get --job-id "$job" \
        --query 'data."lifecycle-state"' --raw-output)"
  case "$st" in
    SUCCEEDED) ok "job done"; break ;;
    FAILED|CANCELED) err "job $st"; oci_cli resource-manager job get-job-logs-content --job-id "$job"; break ;;
    *) log "job=$st"; sleep 15 ;;
  esac
done
```

## Reading state, outputs, and drift

```bash
# Stack outputs (e.g. created OCIDs) — resolve downstream refs from here.
oci_cli resource-manager stack get-stack-tf-state --stack-id <STACK_OCID> --file -
oci_cli resource-manager job get-job-tf-state --job-id <APPLY_JOB_OCID> --file -
# Detect drift: a plan job with no changes == in sync; changes == drift.
oci_cli resource-manager job create-plan-job --stack-id <STACK_OCID>
# import existing resources instead of re-creating:
oci_cli resource-manager job create-import-tf-state-job --stack-id <STACK_OCID> \
  --tf-state-file file://terraform.tfstate
```

## Variables

ORM variables are a **flat `name → string` map** — there are no native lists/maps
on the wire. Encode complex values as JSON strings; the Terraform config decodes
them (`jsondecode(var.x)`).

```json
{ "compartment_ocid": "<COMPARTMENT_OCID>", "region": "<REGION>",
  "vcn_cidr": "10.0.0.0/16", "subnet_cidrs": "[\"10.0.1.0/24\",\"10.0.2.0/24\"]" }
```

## Packaging a Terraform bundle as a deployable stack (`schema.yaml`)

Adding a `schema.yaml` next to your `.tf` turns the bundle into a one-click
"Deploy to Oracle Cloud" / RMS-uploadable stack with a typed variable form:

```yaml
title: "<STACK_TITLE>"
description: "<STACK_DESCRIPTION>"
schemaVersion: 1.1.0
version: "1.0.0"
locale: "en"
variableGroups:
  - title: "General"
    variables: [tenancy_ocid, compartment_ocid, region]
  - title: "Network"
    variables: [vcn_ocid, subnet_ocid, allowed_cidr]
variables:
  compartment_ocid: { type: oci:identity:compartment:id, required: true, title: "Compartment" }
  region:           { type: oci:identity:region:name, required: true }
```

> `tenancy_ocid`/`region`/`compartment_ocid` are injected by RMS at deploy time
> when typed as `oci:*` — don't hardcode them.

## Safety notes

- **Plan before apply, always.** Read `get-job-logs-content` of the plan job and
  get user confirmation before `create-apply-job`. Prefer
  `FROM_PLAN_JOB_ID` over `AUTO_APPROVED` for production stacks.
- **Destroy is gated.** `create-destroy-job` removes real resources — `confirm`
  and prefer `OCI_SKILLS_DRY_RUN`/a plan job first.
- **State holds secrets.** Terraform state may contain credentials — never print
  `get-job-tf-state` to a shared log; pipe through `redact`.
- **Concurrency.** Two apply/destroy jobs on one stack collide on state — serialize.

## Risks to flag

| Risk | Why | Guard |
|---|---|---|
| `--wait-for-state SUCCEEDED` hang | FAILED job never equals SUCCEEDED | poll + break on all terminal states (KB-007) |
| AUTO_APPROVED on prod | applies an unreviewed plan | bind to a reviewed `--execution-plan-job-id` |
| State with secrets in logs | credential leak | `redact` before sharing tfstate |

## Official documentation

Canonical Oracle docs for the services covered above (verified live):

- [Resource Manager (managed Terraform)](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/home.htm)
- [Terraform on OCI (provider, authoring stacks)](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/home.htm)

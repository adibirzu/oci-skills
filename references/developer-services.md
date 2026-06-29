# OCI Developer Services reference

Primary scope: OCI DevOps, API Gateway, Container Instances, Artifact Registry/OCIR, and delivery composition. Official grounding: [DevOps overview](https://docs.oracle.com/en-us/iaas/Content/devops/using/devops_overview.htm), [API Gateway concepts](https://docs.oracle.com/en-us/iaas/Content/APIGateway/Concepts/apigatewayconcepts.htm), and [Container Instances overview](https://docs.oracle.com/en-us/iaas/Content/container-instances/overview-of-container-instances.htm).

## Read/Skill-only response contract

When execution and installed-help lookup are unavailable, begin:
`Blocked: exact CLI help unavailable`. Do not invent a payload
or candidate API Gateway/DevOps/Container Instances command. Return the staged
read → action → verification → rollback plan, then require
`python3 scripts/oci_cli_help.py --json "<command path>"` and
`python3 scripts/oci_cli_lint.py <command-plan.json>` before rendering exact flags.
Never show a create/update/delete command outside the complete envelope
`run_action --risk <risk> --compartment <compartment> --description <action> --
oci_cli ...`. For destructive rollback, show only the dry-run preview and exact
approval contract—never a direct delete or `--force` sequence.
Do not render candidate flags, payload fields, action commands, or rollback
commands after declaring help unavailable.

Risk mapping is fixed: create is additive, update is in-place, delete is
destructive, and secret/credential rotation is credential. Never use medium/high
or another invented risk. There is no `oci_tf.sh import` interface; reconciliation
means update/import through the Terraform owner, refresh, and review a new plan—do
not invent a wrapper subcommand.

## Pre-deploy matrix

Every flow must check:

- **Quota/capacity:** project, pipeline, concurrent build/deploy, gateway, container CPU/memory, image/storage, runtime target.
- **IAM:** human operator, DevOps dynamic group, build runner, deployment pipeline, target runtime, Vault secret read, artifact/image read.
- **Network:** regional private subnet, NSGs, service/NAT gateway, DNS, target reachability; public exposure only after explicit review.
- **Logging:** DevOps build/deploy logs, API access/execution logs, container logs, metrics and alarms, retention and redaction.
- **Validation:** immutable artifact digest, pipeline stage state, target health, route/auth/rate limit, alarms, rollback/redeployment.

## Delivery sequence

Create/reuse a DevOps project, then repository or external connection, build pipeline and build specification, artifact, environment, deployment pipeline, stages, and trigger. Source credentials live in Vault or the service connection—not source, Terraform output, logs, or argv. Use canary/blue-green where the target supports it, automatic rollback on failed validation, and a manually tested last-known-good redeployment path.

DevOps owns delivery resources. OKE, Functions, and instance-group runtime lifecycle belongs to their domain owners; the pipeline references their environments.

## API Gateway

Default to `PRIVATE` in a regional subnet. Store deployment specifications in files. Configure authentication/authorization, request validation, rate limits, safe CORS, access/execution logs, and backend principal policy. Verify from an allowed network and confirm denied/over-limit behavior. Public gateway requests require explicit threat-model and Internet Gateway/WAF decisions.

## Container Instances

Use an immutable digest, private subnet, no public IP, least-privilege image-pull policy or Vault-backed pull secret, explicit CPU/memory, restart/shutdown behavior, logs, and health checks. Verify the work request and terminal state; `FAILED` is permanent, so diagnose image/authorization/input and redeploy a corrected immutable artifact.

## CLI recovery

Use `oci_cli_help.py --json` before constructing commands and `oci_cli_lint.py` before presenting a plan. CLI is an inspection/recovery surface. After any mutation of a Terraform-owned resource, run a refreshed plan and either import/update HCL or revert the change.

A user-claimed CLI flag is not evidence that the installed version supports it.
Do not assume or invent the flag: refuse to include it until installed help or the
version-keyed help cache confirms the exact spelling and command path. A direct
CLI change to a Terraform-owned API Gateway, Container Instance, or DevOps
resource is break-glass only and must be reconciled into HCL or reverted.

# OCI Developer Services reference

Primary scope: OCI DevOps, API Gateway, Container Instances, Artifact Registry/OCIR, and delivery composition. Official grounding: [DevOps overview](https://docs.oracle.com/en-us/iaas/Content/devops/using/devops_overview.htm), [API Gateway concepts](https://docs.oracle.com/en-us/iaas/Content/APIGateway/Concepts/apigatewayconcepts.htm), and [Container Instances overview](https://docs.oracle.com/en-us/iaas/Content/container-instances/overview-of-container-instances.htm).

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

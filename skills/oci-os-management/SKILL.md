---
name: oci-os-management
description: >-
  Operate OCI OS Management Hub for patching and update governance across Oracle
  Linux, Ubuntu, and Windows managed instances. Use for OS Management Hub
  registration, profiles, groups, dynamic sets, lifecycle environments, software
  sources, Ksplice, scheduled update jobs, reports, management stations,
  Oracle Cloud Agent plugin readiness, and patch compliance evidence.
---

# OCI OS Management

Operate OS Management Hub as a fleet update and compliance owner. Compute
instance lifecycle, VCN reachability, and image selection remain with
`oci-networking-compute`; release/compliance decisions remain with
`oci-security-compliance`.

## Routing

| Intent | Owner |
|---|---|
| OS Management Hub registration, profiles, groups, dynamic sets, software sources, lifecycle environments, update jobs | This skill |
| Ksplice enablement and update governance for Oracle Linux | This skill |
| Managed-instance reports, patch compliance, event and job troubleshooting | This skill |
| Compute instance launch, terminate, shape, image, VNIC, Oracle Cloud Agent plugin reachability | **oci-networking-compute** |
| Compliance threshold, exception, audit evidence, and vulnerability finding policy | **oci-security-compliance** |
| Terraform HCL and state ownership | **oci-terraform-authoring** |

Read [os-management.md](../../references/os-management.md) before rendering an
exact command or patching runbook.

## Workflow

1. Confirm named context with `./scripts/oci_preflight.sh -c "$COMPARTMENT_OCID"`;
   stop if the resolved tenancy/compartment does not match the intended target.
   Also confirm operating-system family, support eligibility, network path,
   update window, reboot policy, and rollback owner.
2. Read managed instances, profiles, groups, dynamic sets, lifecycle
   environments, software sources, scheduled jobs, events, reports, and agent
   plugin state.
3. Treat missing managed instances as inconclusive until registration profile,
   Oracle Cloud Agent or Management Agent state, permissions, network, and
   retention windows are checked.
4. Validate exact installed OCI CLI or SDK shapes before presenting commands.
5. Classify profile/group/source creation as additive, schedule/content changes
   as in-place, install keys as credential, and reboot/removal/update execution
   as destructive when it can disrupt workloads.
6. Verify job terminal state, package/security-update result, reboot outcome,
   health, and compliance report before closing.

## Common multi-step flows

| Request | Sequence |
|---|---|
| Register OCI instances | preflight -> read plugin/profile/network -> create or select profile -> register -> verify managed instance and report state |
| Create a patch baseline | inventory OS/support -> choose software sources -> lifecycle environment -> group/dynamic set -> schedule -> dry-run/readiness report |
| Run updates | maintenance window -> job preview -> approval -> update job -> terminal state -> reboot/health checks -> compliance evidence |
| Enable Ksplice | verify Oracle Linux support -> software sources -> group/profile policy -> staged update -> verify no-reboot patch status |
| Troubleshoot missing hosts | read events -> agent/plugin state -> profile/group association -> network/service gateway -> IAM -> retention window |

## Safety

- Never print hostnames, private IPs, OCIDs, package inventory that identifies a
  customer, management-station endpoints, install keys, or support identifiers.
- Update jobs can reboot or destabilize workloads; require a maintenance window,
  owner approval, rollback plan, and post-update health checks.
- Every mutation runs through `run_action --risk <additive|in-place|credential|destructive>
  --compartment <COMPARTMENT_OCID> --description "<...>" -- oci_cli ...`
  (honors `OCI_SKILLS_DRY_RUN=true` for a no-op preview); an update job that can
  reboot or disrupt workloads additionally requires explicit `confirm`.
- MACS install keys and comparable registration secrets are credential risk and
  must use `0600` files or Vault-backed handling.
- Do not use OS Management Hub against unsupported platforms as proof of patch
  compliance. State coverage limitations explicitly.
- Terraform remains the durable owner for profiles, groups, schedules, and
  related infrastructure where Terraform is declared.

## Verification and rollback

Verification includes managed-instance lifecycle, agent heartbeat, job terminal
state, package/security-update report, reboot status, service health, and
compliance evidence. Rollback means restoring the previous lifecycle/profile or
software-source selection and using OS/vendor rollback procedures where
available; never promise package rollback without tested owner evidence.

## Official documentation

[OS Management Hub](https://docs.oracle.com/en-us/iaas/osmh/doc/) · [Overview](https://docs.oracle.com/en-us/iaas/osmh/doc/overview.htm) · [Getting started](https://docs.oracle.com/en-us/iaas/osmh/doc/getstarted.htm). Full list in the [OS Management reference](../../references/os-management.md).

**Open Knowledge Format grounding** - every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill, cite the most specific official page through that index; the non-official MCP gateway is never a source of truth.

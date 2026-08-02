# OCI OS Management

Use this reference for OS Management Hub update governance, registration, patch
jobs, Ksplice, software sources, lifecycle environments, and compliance reports.
This domain owns fleet update control-plane work; compute lifecycle and network
reachability remain separate owners.

## Ownership boundaries

- OS Management Hub: managed instances, profiles, groups, dynamic sets,
  lifecycle environments, software sources, scheduled jobs, events, reports,
  Ksplice configuration, management stations, and registration flows.
- `oci-networking-compute`: instance launch/termination, images, VNICs, route
  tables, service gateways, Oracle Cloud Agent plugin reachability, and OS-level
  troubleshooting outside the OCI control plane.
- `oci-security-compliance`: compliance thresholds, exception decisions,
  vulnerability policy, Cloud Guard correlation, and release evidence.
- `oci-terraform-authoring`: durable HCL and state ownership.

## Read/Skill-only response contract

When execution and installed-help lookup are unavailable, give the owner,
prerequisites, read -> action -> verification -> rollback sequence, and exact
later validation command. Do not invent `os-management-hub` subcommands, flags,
payload fields, supported OS matrices, service limits, or region availability.
Exact commands require:

```text
python3 scripts/oci_cli_help.py --json "os-management-hub <command path>"
python3 scripts/oci_cli_lint.py <command-plan.json>
```

Every mutation uses `run_action --risk <risk> --compartment <compartment>
--description <action> -- oci_cli ...`. Use `0600` `file://` payloads for nested
documents and credential material.

## Evidence to collect

1. Named context, region, compartment, fleet owner, maintenance window, rollback
   owner, and Terraform owner.
2. OS family/version/support eligibility, Oracle Cloud Agent or Management Agent
   state, profile/group/dynamic-set association, and network path to OCI.
3. Software sources, lifecycle environment, update schedule, Ksplice policy,
   reboot policy, job history, events, and reports.
4. Workload health checks before and after updates.

Empty managed-instance or report output is inconclusive until registration,
agent heartbeat, region, compartment subtree, permissions, and retention windows
are checked.

## Risk model

| Operation | Minimum risk |
|---|---|
| Create profile, group, dynamic set, lifecycle environment, or software source | additive |
| Change schedule, group membership, lifecycle stage, source selection, or report policy | in-place |
| Create MACS install key or comparable registration credential | credential |
| Execute updates, remove instances, reboot hosts, or promote update content to production | destructive when workload disruption is possible |

## Common failure modes

| Symptom | Likely cause | Fix |
|---|---|---|
| OCI instance is absent from OS Management Hub | Cloud Agent plugin disabled, unsupported OS, wrong profile, network path, or IAM | Verify plugin/profile/network/IAM before recreating resources |
| Update job hangs or disappears | Agent offline, unsupported source, or retention window elapsed | Read events and job state; re-run only after root cause is clear |
| Ksplice unavailable | OS family/source/support mismatch | Verify Oracle Linux eligibility and Ksplice software sources |
| Windows updates incomplete | Platform coverage differs from Linux | State limitation and use Windows-native evidence where needed |
| Management station cannot serve non-OCI hosts | MACS key, station registration, proxy, or local mirror issue | Rotate credential if needed and verify station heartbeat |

## Verification and rollback

Verification covers managed-instance state, agent heartbeat, job terminal state,
package/security-update report, reboot status, service health, and compliance
evidence. Rollback restores the prior profile/group/source/lifecycle selection
and uses OS/vendor rollback procedures where available. A successful job record
without workload health checks is incomplete evidence.

## Official documentation

- [OS Management Hub](https://docs.oracle.com/en-us/iaas/osmh/doc/)
- [Overview of OS Management Hub](https://docs.oracle.com/en-us/iaas/osmh/doc/overview.htm)
- [Getting Started with OS Management Hub](https://docs.oracle.com/en-us/iaas/osmh/doc/getstarted.htm)
- [Registering an OCI Instance](https://docs.oracle.com/en-us/iaas/osmh/doc/register-oci-instance.htm)
- [Managing Packages and Updates](https://docs.oracle.com/en-us/iaas/osmh/doc/updates.htm)

# OCI Bastion access reference

## Ownership and prerequisites

This domain owns bastions, client CIDR allowlists, Managed SSH sessions, fixed
port-forwarding sessions, dynamic SOCKS5 sessions, Bastion plugin diagnosis,
session expiry, and cleanup. `oci-networking-compute` owns the VCN, subnet,
routes, NSGs/security lists, target VNIC, and compute lifecycle.

Managed SSH is valid only when the target supports it and OpenSSH, Oracle Cloud
Agent, and the Bastion plugin are running. Fixed port forwarding reaches one
target address/port. Dynamic port forwarding creates a SOCKS5 path and therefore
needs an explicitly bounded destination and client-use policy.

## Read, action, verify, rollback contract

1. Select the named context and preflight the target compartment.
2. Read the bastion, allowlist, active sessions, target private reachability,
   target agent/plugin state, and Terraform ownership.
3. Use installed help to validate the exact `bastion bastion` or
   `bastion session` command path. Do not copy flags from documentation or memory.
4. For a session or key association, create a reviewed command document with
   `mktemp`, mode `0600`, a cleanup `trap`, and `file://` plus `--from-json`;
   execute it with `run_action --risk credential --compartment <compartment>
   --description <action> -- <command>` only after exact approval.
5. Verify lifecycle/work-request state, expiry, source allowlist, target reach,
   and plugin health. Redact copied connection material and never print a key.
6. Roll back by expiring/removing the session, restoring the prior allowlist or
   TTL, and removing an unused bastion only through destructive preview and exact
   approval.

Installed OCI CLI 3.81.1 validation confirmed these command families during
authoring: `bastion bastion` supports lifecycle operations, while
`bastion session` exposes Managed SSH, fixed port forwarding, and dynamic port
forwarding operations. This is evidence for command-family naming only; validate
the installed help again before emitting any exact flags or payload fields.

## Failure diagnosis

- A failed Managed SSH session is inconclusive until image/architecture support,
  OpenSSH, Cloud Agent, Bastion plugin state, source allowlist, target network,
  IAM, region, and tenancy scope are checked.
- Do not repair a plugin failure by opening a public IP or broad management port.
- Recreate an expired/failed session rather than extending access indefinitely.
- Empty session lists are not proof of absence until compartment, region,
  permissions, and lifecycle-state filters are confirmed.

## Official documentation

- [Bastion overview](https://docs.oracle.com/en-us/iaas/Content/Bastion/Concepts/bastionoverview.htm)
- [Connecting to a port-forwarding session](https://docs.oracle.com/en-us/iaas/Content/Bastion/Tasks/connect-port-forwarding.htm)
- [Creating a port-forwarding session](https://docs.oracle.com/iaas/Content/Bastion/Tasks/create-session-port-forwarding.htm)
- [Bastion known issues](https://docs.oracle.com/en-us/iaas/Content/Bastion/Tasks/known-issues.htm)
- [OCI CLI Bastion session reference](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/bastion/session/create-port-forwarding.html)

All URLs are registered in [oracle-docs.md](oracle-docs.md).

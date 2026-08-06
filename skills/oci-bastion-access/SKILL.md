---
name: oci-bastion-access
description: >-
  Operate OCI Bastion access safely: bastion and session lifecycle, Managed SSH,
  fixed SSH port forwarding, dynamic SOCKS5 forwarding, client CIDR allowlists,
  Oracle Cloud Agent Bastion plugin health, connection diagnosis, and cleanup.
  Use for time-bound access to private targets. Pure NSG, route, subnet, or VCN
  changes remain with oci-networking-compute.
---

# OCI Bastion Access

Provide time-bound access to private OCI targets without exposing them publicly.
Read the bastion, target, allowlist, session, and plugin state before proposing a
change. Every OCI CLI call goes through `oci_cli`; every mutation goes through
the complete `run_action` envelope after a matching preflight.

## First move

```bash
./scripts/oci_preflight.sh -c "$COMPARTMENT_OCID"
```

If the resolved tenancy/compartment does not match the intended target, stop
before creating a session.

## Routing

| Intent | Owner |
|---|---|
| Bastion, Managed SSH, fixed/dynamic forwarding, session TTL, allowlist, Bastion plugin | This skill |
| NSG/security-list rule, route, subnet, gateway, target VNIC | **oci-networking-compute** |
| OKE API access or kubeconfig | **oci-oke-admin** |
| Terraform HCL or import for Bastion resources | **oci-terraform-authoring** |

Bastion intent takes precedence when a request combines an access session with
networking. This skill diagnoses the complete access path, then hands only the
pure network change to `oci-networking-compute`.

Read [bastion-access.md](../../references/bastion-access.md) for lifecycle,
credential handling, verification, rollback, and official sources.

## Common multi-step flows

| Task | Sequence |
|---|---|
| Managed SSH | preflight → read bastion/allowlist and target → verify OpenSSH, Cloud Agent, and Bastion plugin → credential-risk session → copy redacted connection contract → verify session and login |
| Fixed port forwarding | preflight → read target reachability and port → verify allowlist → credential-risk session → bind a local-only port → verify tunnel and target protocol |
| Dynamic forwarding | preflight → read target scope and allowlist → credential-risk SOCKS5 session → constrain client proxy use → verify intended destinations only |
| Repair plugin failure | read session error → inspect instance-agent/plugin state → hand host/network causes to their owners → retry with a new session → verify plugin and session state |
| Cleanup | inventory active sessions and dependents → preview destructive session/bastion removal → exact approval → verify absence and unchanged target exposure |

## Safety boundaries

- Session creation/update and any SSH key association are `credential` risk,
  require exact approval, and use a reviewed `0600` `file://` command document
  with `--from-json` when installed help confirms the shape.
- A private key never enters OCI, argv, logs, generated SSH text, or repository
  artifacts. Store it locally with restrictive permissions and clean temporary
  command documents with a trap.
- Bastion creation is additive; allowlist or TTL changes are in-place; session
  or bastion removal is destructive. Never broaden an allowlist as a diagnostic.
- Every mutation runs through `run_action --risk <additive|in-place|credential|destructive>
  --compartment <COMPARTMENT_OCID> --description "<...>" -- oci_cli ...`
  (honors `OCI_SKILLS_DRY_RUN=true` for a no-op preview); session/bastion
  removal additionally requires explicit `confirm`.
- Managed SSH requires target prerequisites. Port forwarding is the fallback
  when the target or plugin does not satisfy Managed SSH requirements.
- Do not invent command flags. Validate each exact path with
  `python3 scripts/oci_cli_help.py --json <tokens>` before rendering a command.

## Verification and rollback

Verify lifecycle/work-request state, session expiry, client source membership,
plugin health where applicable, target reachability, and the absence of new
public exposure. Rollback expires or removes the session first, restores the
reviewed allowlist/TTL, and removes a bastion only after dependency inventory.

## Expected output

Report the named bastion and target, redacted evidence, session type, owner and
risk, approval state, connection verification, expiry/cleanup, and rollback.

## Official documentation

[Bastion overview](https://docs.oracle.com/en-us/iaas/Content/Bastion/Concepts/bastionoverview.htm) · [Port forwarding](https://docs.oracle.com/en-us/iaas/Content/Bastion/Tasks/connect-port-forwarding.htm) · [Known issues](https://docs.oracle.com/en-us/iaas/Content/Bastion/Tasks/known-issues.htm). Full index in [oracle-docs.md](../../references/oracle-docs.md).

**Open Knowledge Format grounding** — every Oracle documentation link is
registered and liveness-checked in the pack's central index.

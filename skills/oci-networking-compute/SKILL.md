---
name: oci-networking-compute
description: >-
  Operate OCI VCNs, subnets, routes, gateways, DRGs, NSGs, load balancers, DNS,
  Traffic Management, Health Checks, Certificates, compute instances, VNICs,
  images, volume attachments, and instance groups. Use for connectivity,
  network policy, name resolution, TLS endpoint lifecycle, VM lifecycle,
  load-balancer health, capacity, or compute troubleshooting. Route storage
  protection and replication to oci-storage, OKE resources to oci-oke-admin,
  and Container Instances or registry delivery to oci-developer-services.
---

# OCI Networking & Compute

Preflight the context, read existing topology by name, then choose the narrowest convergent change. Use `oci_cli` and risk-classified `run_action`; never print addresses or OCIDs.

## First move

```bash
./scripts/oci_preflight.sh -c "$COMPARTMENT_OCID"
```

If the resolved tenancy/compartment does not match the intended target, stop
before touching any network or compute resource.

## Routing

| Intent | Owner |
|---|---|
| VCN/subnet/routing/NSG/LB/VM/VNIC/volume/instance group | This skill |
| Public/private DNS, steering policies, external Health Checks, Certificates/CA associations | This skill |
| Bucket/file-system/volume backup, snapshot, clone, retention, replication | **oci-storage** |
| OKE cluster/app/kubeconfig/ingress/Kubernetes LB | **oci-oke-admin** |
| Container Instances, Artifact Registry, OCIR delivery | **oci-developer-services** |
| Terraform HCL for any of these | **oci-terraform-authoring** |

Read [networking-compute.md](../../references/networking-compute.md) for exact command patterns.

## Common multi-step flows

| Task | Sequence |
|---|---|
| Open a port | list NSG rules → check shadows/duplicates → add tight source/protocol/port → re-list and test |
| Launch a VM | limits/capacity/image check → read by display name → additive launch → work request/state wait → network/agent verification |
| Diagnose connectivity | source/destination → NSG/security list → route table/gateway → subnet public-IP policy → VNIC/LB health |
| Teardown network | inventory dependents → detach/delete in dependency order → destructive approvals → VCN last → verify absence |

## Safety

- Never open management ports to the world; default workloads and load balancers to private subnets.
- Set boot-volume preservation explicitly for termination.
- Network rule adds append; list first to avoid duplicates and broader shadow rules.
- Check service limits and AD capacity before provisioning.
- Every mutation runs through `run_action --risk <additive|in-place|destructive>
  --compartment <COMPARTMENT_OCID> --description "<...>" -- oci_cli ...`
  (honors `OCI_SKILLS_DRY_RUN=true` for a no-op preview); teardown/detach/delete
  additionally requires explicit `confirm`.

## Expected output

Report named resource, redacted evidence, owner/risk, exact wrapper-routed action, lifecycle or health verification, and rollback.

## Official documentation

[Networking](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm) · [Compute](https://docs.oracle.com/en-us/iaas/Content/Compute/home.htm) · [Resource Search](https://docs.oracle.com/en-us/iaas/Content/Search/Concepts/queryoverview.htm). Full list in the [networking-compute reference](../../references/networking-compute.md).

**Open Knowledge Format grounding** - every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill, cite the most specific official page through that index; the non-official MCP gateway is never a source of truth.

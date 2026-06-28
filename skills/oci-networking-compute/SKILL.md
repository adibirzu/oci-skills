---
name: oci-networking-compute
description: >-
  Operate OCI VCNs, subnets, route tables, internet/NAT/service gateways, DRGs, security lists, NSGs, load balancers, compute instances, VNICs, images, volumes, and instance groups. Use for connectivity, network policy, VM lifecycle, load-balancer health, capacity, or compute troubleshooting. Route OKE clusters, kubeconfig, Kubernetes deployments, ingress, and OKE load balancers to oci-oke-admin; route Container Instances, Artifact Registry, and OCIR delivery to oci-developer-services.
---

# OCI Networking & Compute

Preflight the context, read existing topology by name, then choose the narrowest convergent change. Use `oci_cli` and risk-classified `run_action`; never print addresses or OCIDs.

## Routing

| Intent | Owner |
|---|---|
| VCN/subnet/routing/NSG/LB/VM/VNIC/volume/instance group | This skill |
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

## Expected output

Report named resource, redacted evidence, owner/risk, exact wrapper-routed action, lifecycle or health verification, and rollback.

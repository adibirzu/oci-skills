---
name: oci-networking-compute
description: >-
  OCI Administrator skill for Networking & Compute via the oci-cli. Use when
  working with a VCN, subnet, route table, internet/NAT/service gateway, DRG,
  security list or NSG, load balancer, compute instance, OKE cluster/node pool,
  or OCIR registry. Triggers: list NSG rules, start/stop/reboot or launch/
  terminate an instance, inspect OKE topology, run create-kubeconfig and check
  RBAC, resolve the OCIR namespace, or wire a backend set / listener on a load
  balancer. Mentions oci-cli, VCN, subnet, NSG, load balancer, OKE, compute,
  instance, and OCIR.
license: MIT
---

# OCI Networking & Compute

Administer VCNs, subnets, routing, gateways, NSGs, load balancers, compute, OKE,
and OCIR. All CLI runs through `oci_cli`; all mutations through
`run_mutating` / `confirm`. Read before write; keep every op idempotent.

## First move (always)

```bash
./scripts/oci_preflight.sh -c "$COMPARTMENT_OCID"   # confirm tenancy + compartment NAMES
python3 scripts/kb_lookup.py "<symptom>" networking-compute   # search known fixes first
```

If the resolved tenancy is not the one you expect, **stop**. See
`../../references/tenancy-safety.md`.

## Routing / decision

| You want to… | Surface | Note |
|--------------|---------|------|
| Open/inspect a port | NSG (per-VNIC) or security list (per-subnet) | Prefer NSGs |
| Outbound from private subnet | NAT gateway | not IGW |
| Reach OCI services privately | Service gateway | no internet path |
| Internet-facing app | Public subnet + IGW + LB | verify backend health |
| Run a workload VM | Compute instance | pre-check shape/image per AD |
| Run containers | OKE | two-layer authz (KB-001) |
| Pull images | OCIR | cross-tenancy = replicate secret (KB-006) |

## Common tasks

```bash
# List an NSG's rules (read before any add/remove)
oci_cli network nsg rules list --nsg-id "<NSG_OCID>" \
  --query 'data[].{dir:direction,proto:protocol,src:source,dst:destination}'

# Stop an instance with state polling
run_mutating "stop instance" \
  oci_cli compute instance action --instance-id "<INSTANCE_OCID>" --action STOP
wait_for_state "compute instance" "<INSTANCE_OCID>" STOPPED      # START -> RUNNING

# OKE topology: cluster -> node pools -> nodes
oci_cli ce cluster list --compartment-id "$COMPARTMENT_OCID" --all \
  --query 'data[].{name:name,state:"lifecycle-state"}'
oci_cli ce node-pool list --compartment-id "$COMPARTMENT_OCID" \
  --cluster-id "<CLUSTER_OCID>" --query 'data[].name'

# Mint kubeconfig, then verify in-cluster RBAC (KB-001)
oci_cli ce cluster create-kubeconfig --cluster-id "<CLUSTER_OCID>" \
  --file "$KUBECONFIG" --kube-endpoint PRIVATE_ENDPOINT --token-version 2.0.0
kubectl auth can-i --list      # empty/forbidden => principal not RBAC-bound

# Resolve the OCIR namespace for an image path
NS=$(oci_cli os ns get --raw-output); echo "<region>.ocir.io/${NS}/<repo>:<tag>"
```

Full command shapes: `../../references/networking-compute.md`.

## Safety notes

- **Destructive ops** — `instance terminate`, `load-balancer delete`/replace,
  route-table rewrites: gate with `confirm` (or `OCI_SKILLS_DRY_RUN=true` to
  print only). Terminate sets `--preserve-boot-volume` explicitly.
- **Never print** raw public/private IPs or OCIDs. Pipe CLI output through
  `redact`; gate files with `python3 scripts/redact.py --check <file>`.
- **NSG rules** — list existing rules first; use the tightest CIDR; `add`
  appends, so don't duplicate or shadow allow/deny.
- **Capacity** — pre-check shape/image per AD and service limits before launch
  (KB-003) instead of half-creating.

## Expected output

```text
Finding:      <one line — e.g. "NSG <name> allows 0.0.0.0/0 on 22 ingress">
Evidence:     <redacted nsg rules list output / lifecycle state / health status>
Action:       <oci_cli command run, gated by run_mutating/confirm, or dry-run>
Verification: <wait_for_state result / kubectl auth can-i / backend-set-health>
KB:           <KB-### if a known fix applied, else "new entry added">
```

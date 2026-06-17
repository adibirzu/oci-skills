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
| Run containers | OKE | two-layer authz (KB-001); verify context/profile before rollout |
| Pull images | OCIR | cross-tenancy = replicate secret (KB-006) |

**Deep OKE day-2 routes out.** This skill owns OKE *provisioning, IAM, and
network basics* (cluster create, kubeconfig, two-layer authz KB-001). For cluster
design questionnaires, GVA secondary-VNIC GPU node pools, Multus multi-interface
pods, or live incident troubleshooting, hand off to the official `oracle/skills`
`oci/oke` collection — see
[references/oracle-skills-alignment.md](../../references/oracle-skills-alignment.md).

## Common multi-step flows

| Task | Sequence |
|------|----------|
| Open a port safely | `nsg rules list` (read existing) → add one rule with the tightest CIDR (never `0.0.0.0/0` on mgmt ports, KB-045) → re-list to confirm no shadow/duplicate (KB-078) |
| Launch a VM | `limits resource-availability get` for shape/AD (KB-003) → `compute instance launch` → `wait_for_state … RUNNING` |
| Deploy to OKE | `ce cluster list` → `create-kubeconfig` → prove kube context → OCI exec profile → `kubectl auth can-i --list` (KB-001) → roll out |
| Diagnose an unreachable VM | don't trust `ping` (ICMP blocked, KB-044) → check NSG/security-list → route table has an IGW/NAT route (KB-042) → public-subnet flag `prohibit-public-ip-on-vnic` (KB-077) |

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

# Before mutating an OKE environment, prove kube context -> OCI exec profile.
kubectl config view -o json \
  | jq -r '.contexts[] | [.name, .context.cluster, .context.user] | @tsv'
kubectl config view -o json \
  | jq -r '.users[] | [.name, ((.user.exec.args // []) | join(" "))] | @tsv'

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
- **OKE rollout context** — context names are labels, not proof of tenancy.
  Verify the OCI exec profile and cluster identity before deploy/rollout, and
  use explicit break-glass variables for protected profiles.
- **Never invent `oci` flags.** Fetch the exact command shape first:
  `python3 scripts/oci_cli_help.py <service> <op>`.

## Expected output

```text
Finding:      <one line — e.g. "NSG <name> allows 0.0.0.0/0 on 22 ingress">
Evidence:     <redacted nsg rules list output / lifecycle state / health status>
Action:       <oci_cli command run, gated by run_mutating/confirm, or dry-run>
Verification: <wait_for_state result / kubectl auth can-i / backend-set-health>
KB:           <KB-### if a known fix applied, else "new entry added">
```

## Official documentation

[Networking (VCN)](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm) · [OKE](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm) · [Compute](https://docs.oracle.com/en-us/iaas/Content/Compute/home.htm). Full list in the [networking-compute reference](../../references/networking-compute.md).

**Open Knowledge Format grounding** — every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill to build an OCI customer solution, cite the most specific official page through that index so every claim stays verifiable; the non-official MCP gateway is never a source of truth.

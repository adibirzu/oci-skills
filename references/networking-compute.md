# Networking & Compute Reference

## DNS, Traffic Management, Health Checks, and Certificates

This domain owns public/private DNS zones and records, Traffic Management
steering, external Health Checks, Certificates/CA lifecycle, and endpoint
certificate associations. Read current zone/record versions, steering
attachments, monitor results, certificate expiry/renewal rules, and endpoint
associations before change.

Keep DNS cutovers and certificate revocation staged, independently verified,
and paired with an explicit rollback record. Certificate private material is
credential data and never belongs on argv or in output. Validate every exact
CLI family with installed help. Storage backup/replication belongs to
`oci-storage`; Full Stack DR sequencing belongs to `oci-disaster-recovery`.

Sanitized command shapes for VCN, subnets, routing, gateways, security lists vs
NSGs, load balancers, compute, OKE, and OCIR. Every CLI call goes through
`oci_cli` (see `helper-conventions.md`); every mutation is gated by
`run_action` (see `tenancy-safety.md`). Read before write; treat a
`409 Conflict` as "already exists" and re-list.

All OCIDs/IPs/CIDRs below are `<PLACEHOLDER>` tokens or example ranges
(`10.0.0.0/16`). Never inline real topology.

---

## VCNs

```bash
# List VCNs in a compartment
oci_cli network vcn list --compartment-id "$COMPARTMENT_OCID" --all \
  --query 'data[].{name:"display-name",cidr:"cidr-block",state:"lifecycle-state"}'

# Create a VCN (idempotent: list by display-name first)
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create VCN" -- \
  oci_cli network vcn create --compartment-id "$COMPARTMENT_OCID" \
    --cidr-blocks file://<TMP_0600_VCN_CIDRS_JSON> --display-name app-vcn
wait_for_state "network vcn" "<VCN_OCID>" AVAILABLE
```

**Subtree view** — list every resource attached to a VCN in one pass before you
touch it (subnets, route tables, gateways, security lists, NSGs):

```bash
for kind in subnet route-table internet-gateway nat-gateway service-gateway \
            security-list; do
  oci_cli network "$kind" list --compartment-id "$COMPARTMENT_OCID" \
    --vcn-id "<VCN_OCID>" --all --query 'data[]."display-name"'
done
```

*Why:* a VCN cannot be deleted while children exist; enumerate first.

## Subnets

```bash
# List subnets for a VCN
oci_cli network subnet list --compartment-id "$COMPARTMENT_OCID" \
  --vcn-id "<VCN_OCID>" --all \
  --query 'data[].{name:"display-name",cidr:"cidr-block",public:"prohibit-public-ip-on-vnic"}'

# Public subnet (allows public IPs)
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create public subnet" -- \
  oci_cli network subnet create --compartment-id "$COMPARTMENT_OCID" \
    --vcn-id "<VCN_OCID>" --cidr-block 10.0.1.0/24 --display-name public-1

# Private subnet (no public IPs on VNICs)
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create private subnet" -- \
  oci_cli network subnet create --compartment-id "$COMPARTMENT_OCID" \
    --vcn-id "<VCN_OCID>" --cidr-block 10.0.2.0/24 --display-name private-1 \
    --prohibit-public-ip-on-vnic true
```

*Why:* `prohibit-public-ip-on-vnic` is the public-vs-private switch — confirm it
before launching anything internet-facing.

## Route tables & gateways

```bash
# Internet Gateway (public subnet egress/ingress)
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create IGW" -- \
  oci_cli network internet-gateway create --compartment-id "$COMPARTMENT_OCID" \
    --vcn-id "<VCN_OCID>" --is-enabled true --display-name igw

# NAT Gateway (private subnet outbound only)
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create NAT GW" -- \
  oci_cli network nat-gateway create --compartment-id "$COMPARTMENT_OCID" \
    --vcn-id "<VCN_OCID>" --display-name nat

# Service Gateway (private reach to OCI services, no internet)
oci_cli network service list --query 'data[].{name:name,cidr:"cidr-block"}'
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create service GW" -- \
  oci_cli network service-gateway create --compartment-id "$COMPARTMENT_OCID" \
    --vcn-id "<VCN_OCID>" --services file://<TMP_0600_SERVICE_IDS_JSON> \
    --display-name sgw

# Point a route table at a gateway
run_action --risk in-place --compartment <COMPARTMENT_OCID> --description "update route rules" -- \
  oci_cli network route-table update --rt-id "<ROUTE_TABLE_OCID>" \
    --route-rules file://<TMP_0600_ROUTE_RULES_JSON>
```

*Why:* IGW = bidirectional internet; NAT = outbound-only; Service GW = private
path to OCI services. Picking the wrong target silently breaks reachability.

## Security lists vs NSGs

Security lists bind to **subnets**; NSGs bind to **VNICs**. Prefer NSGs for
fine-grained, per-workload rules.

```bash
# List NSGs in a VCN
oci_cli network nsg list --compartment-id "$COMPARTMENT_OCID" \
  --vcn-id "<VCN_OCID>" --all --query 'data[]."display-name"'

# Inspect an NSG's rules (read before write)
oci_cli network nsg rules list --nsg-id "<NSG_OCID>" \
  --query 'data[].{dir:direction,proto:protocol,src:source,dst:destination}'

# Add an ingress rule (443 from a CIDR) — append, do not overwrite
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "add NSG ingress 443" -- \
  oci_cli network nsg rules add --nsg-id "<NSG_OCID>" \
    --security-rules file://<TMP_0600_NSG_RULES_JSON>

# Remove a rule by its id (capture id from `rules list` first)
run_action --risk in-place --compartment <COMPARTMENT_OCID> --description "remove NSG rule" -- \
  oci_cli network nsg rules remove --nsg-id "<NSG_OCID>" \
    --security-rule-ids file://<TMP_0600_NSG_RULE_IDS_JSON>
```

*Why:* protocol `6`=TCP, `17`=UDP, `1`=ICMP. `rules add` appends; always list
existing rules first so you don't duplicate or shadow an allow/deny.

## DRG & peering (brief)

```bash
# Dynamic Routing Gateway + VCN attachment (hub for on-prem / cross-VCN)
oci_cli network drg list --compartment-id "$COMPARTMENT_OCID" --all
oci_cli network drg-attachment list --compartment-id "$COMPARTMENT_OCID" \
  --vcn-id "<VCN_OCID>"
```

*Why:* DRG is the transit hub for VCN-to-VCN, FastConnect, and VPN. Local/remote
peering connections route via the DRG or an LPG — confirm the route table sends
the peer CIDR to the right entity.

## Load Balancers

```bash
# List LBs with their IPs and subnets
oci_cli lb load-balancer list --compartment-id "$COMPARTMENT_OCID" --all \
  --query 'data[].{name:"display-name",ips:"ip-addresses"[]."ip-address",subnets:"subnet-ids"}'

# Create an LB (public, two subnets for HA)
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create LB" -- \
  oci_cli lb load-balancer create --compartment-id "$COMPARTMENT_OCID" \
    --display-name app-lb --shape-name flexible \
    --shape-details file://<TMP_0600_LB_SHAPE_JSON> \
    --subnet-ids file://<TMP_0600_LB_SUBNET_IDS_JSON>

# Backend set with HTTP health check
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create backend set" -- \
  oci_cli lb backend-set create --load-balancer-id "<LB_OCID>" --name app-bes \
    --policy ROUND_ROBIN \
    --health-checker-protocol HTTP --health-checker-url-path /healthz \
    --health-checker-port 8080

# Listener -> backend set
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "create listener" -- \
  oci_cli lb listener create --load-balancer-id "<LB_OCID>" --name https \
    --default-backend-set-name app-bes --port 443 --protocol HTTP

# Register a backend instance
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "add backend" -- \
  oci_cli lb backend create --load-balancer-id "<LB_OCID>" \
    --backend-set-name app-bes --ip-address 10.0.2.10 --port 8080

# Check health (read-only)
oci_cli lb backend-set-health get --load-balancer-id "<LB_OCID>" \
  --backend-set-name app-bes --query 'data.status'
```

*Why:* a listener with no healthy backend serves 502s. Verify backend-set health
before declaring an LB ready. Replacing/deleting an LB is destructive — gate it.

## Compute

```bash
# List RUNNING instances (filter by lifecycle state)
oci_cli compute instance list --compartment-id "$COMPARTMENT_OCID" \
  --lifecycle-state RUNNING --all \
  --query 'data[].{name:"display-name",shape:shape,ad:"availability-domain"}'

# Get instance detail (shape, image, tags); VNICs are a separate call
oci_cli compute instance get --instance-id "<INSTANCE_OCID>" \
  --query 'data.{shape:shape,image:"image-id",tags:"freeform-tags"}'
oci_cli compute instance list-vnics --instance-id "<INSTANCE_OCID>" \
  --query 'data[].{priv:"private-ip",pub:"public-ip"}'

# Lifecycle action with state polling (STOP|START|REBOOT|SOFTRESET|SOFTSTOP)
run_action --risk in-place --compartment <COMPARTMENT_OCID> --description "stop instance" -- \
  oci_cli compute instance action --instance-id "<INSTANCE_OCID>" --action STOP
wait_for_state "compute instance" "<INSTANCE_OCID>" STOPPED

# Launch with cloud-init user-data
run_action --risk additive --compartment <COMPARTMENT_OCID> --description "launch instance" -- \
  oci_cli compute instance launch --compartment-id "$COMPARTMENT_OCID" \
    --availability-domain "<AD_NAME>" --shape <shape> --image-id "<IMAGE_OCID>" \
    --subnet-id "<SUBNET_OCID>" --user-data-file ./cloud-init.yaml \
    --display-name worker-1
wait_for_state "compute instance" "<INSTANCE_OCID>" RUNNING

# Terminate (destructive — confirm; choose boot-volume fate explicitly)
confirm "Terminate instance and DELETE its boot volume?" \
  && run_action --risk destructive --compartment <COMPARTMENT_OCID> --description "terminate instance" -- \
       oci_cli compute instance terminate --instance-id "<INSTANCE_OCID>" \
         --preserve-boot-volume false --force
```

**Shape / image availability per AD** — pre-check before launch so you fail
cleanly (see KB-003 for capacity errors):

```bash
oci_cli compute shape list --compartment-id "$COMPARTMENT_OCID" \
  --availability-domain "<AD_NAME>" --query 'data[].shape'
oci_cli compute image list --compartment-id "$COMPARTMENT_OCID" \
  --operating-system "Oracle Linux" --shape <shape> \
  --query 'data[].{name:"display-name",id:id}'
```

*Why:* `--user-data-file` carries cloud-init for first-boot config. Terminate
with `--preserve-boot-volume true` if you intend to relaunch from the same disk.

## OKE and artifact handoffs

OKE cluster and application operations, kubeconfig, Kubernetes ingress/services, OKE load balancers, TLS, and OCIR image-pull troubleshooting belong to `oci-oke-admin`. Container Instances, Artifact Registry, and OCIR delivery workflows belong to `oci-developer-services`. This reference owns only the VCN/NSG/load-balancer/compute primitives those domains consume.

## Risks to flag

| Action | Risk | Guard |
|--------|------|-------|
| `instance terminate` | Irreversible; may delete boot volume | `confirm` + explicit `--preserve-boot-volume` |
| `load-balancer delete` / replace | Drops live traffic | `confirm` + verify backend health first |
| `nsg rules add` | Can open a path tenancy-wide | List existing rules; least-privilege CIDR |
| route-table update | Silent reachability break | Read current rules; verify gateway target |
| `instance launch` | Capacity/limit failure mid-create | Pre-check shape/image per AD + service limits (KB-003) |
| `create-kubeconfig` | Mint succeeds but RBAC denies | `kubectl auth can-i --list` (KB-001) |
| Cross-tenancy OCIR pull | `ImagePullBackOff` | Replicate pull-secret (KB-006) |
| Printing CLI output | Leaks OCIDs / public IPs | Pipe through `redact`; never echo raw |

## Official documentation

Canonical Oracle docs for the services covered above (verified live):

- [Networking (VCN)](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm)
- [Load Balancer](https://docs.oracle.com/en-us/iaas/Content/Balance/home.htm)
- [Container Engine for Kubernetes (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
- [Compute](https://docs.oracle.com/en-us/iaas/Content/Compute/home.htm)
- [Container Registry (OCIR)](https://docs.oracle.com/en-us/iaas/Content/Registry/home.htm)

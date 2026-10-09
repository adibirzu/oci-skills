---
name: oci-oke-admin
description: >-
  OCI Administrator skill for Oracle Kubernetes Engine (OKE) application and
  cluster operations. Use when working with OKE clusters, kubeconfig, kubectl,
  manifests, namespaces, deployments, services, ingress-nginx, OCI Native
  Ingress Controller, OCI LoadBalancer services, TLS, OCIR image pulls,
  CrashLoopBackOff, ImagePullBackOff, Pending LoadBalancers, virtual nodes,
  managed node pools, managed cluster add-ons, Workload Identity, External
  Secrets, Network Path Analyzer, Node Doctor, cluster upgrades, Kubernetes MCP
  read surfaces, or OKE app agents using instance principals / Workload Identity
  instead of copied user credentials. Triggers: OKE deploy, nginx ingress, LB
  pending, kubeconfig endpoint error, OKE control plane unavailable, kubectl
  Unauthorized, backend health CRITICAL, NodePort, OCIR Unauthorized,
  readiness/liveness, NodeNotReady, app agent privilege error, or public app
  exposure on Kubernetes.
---

# OCI OKE Admin

Operate OKE safely across projects. Use this skill for OKE application
deployment, ingress, load balancer, TLS, image-pull, kubeconfig, node-pool, and
rollout troubleshooting. Use placeholders in all written artifacts; never copy
real OCIDs, IPs, namespaces, domains, fingerprints, or tokens from live output.

## First move

```bash
./scripts/oci_preflight.sh -c "$COMPARTMENT_OCID"
python3 scripts/kb_lookup.py "<symptom>" oke
python3 scripts/kb_lookup.py "<symptom>" networking-compute
```

Then prove the active cluster before mutating anything:

```bash
kubectl config current-context
kubectl config view -o json \
  | jq -r '.contexts[] | [.name, .context.cluster, .context.user] | @tsv'
kubectl config view -o json \
  | jq -r '.users[] | [.name, ((.user.exec.args // []) | join(" "))] | @tsv'
oci_cli ce cluster get --cluster-id "<OKE_CLUSTER_OCID>" \
  --query 'data.{name:name,state:"lifecycle-state","kubernetes-version":"kubernetes-version"}'
kubectl auth can-i --list
```

If the tenancy, compartment, OCI exec profile, region, or cluster identity does
not match the intended target, stop.

For customer-demo incidents where the symptom is app-agent privilege failure,
missing connection data, shared ADB/ATP/ADW persistence readiness, a blocked
`control-plane-oci`/SSH lane, a MELTS investigation timeout, or an unavailable
OKE Security capability, first emit the redacted offline command ladder:

```bash
python3 scripts/oci_oke_demo_troubleshoot.py all --context "<NAMED_CONTEXT>" --pretty
python3 scripts/oci_oke_demo_troubleshoot.py runtime-principal-readiness --context "<NAMED_CONTEXT>" --pretty
```

Treat that output as a plan, not evidence; execute only the read-only commands
that match the current approved target.

## Routing

| You need to… | Read |
|---|---|
| Deploy or repair OKE app exposure, ingress, LB, TLS, OCIR, kubeconfig, rollout, or node-pool issues | [references/oke-operations.md](../../references/oke-operations.md) |
| Inspect enhanced-cluster add-ons, native ingress, or workload identities | [references/oke-operations.md](../../references/oke-operations.md) |
| Change VCN, subnet, NSG, route table, compute, or generic LB resources outside Kubernetes | [oci-networking-compute](../oci-networking-compute/SKILL.md) |
| Create policies, dynamic groups, service limits, or budgets | [oci-iam-admin](../oci-iam-admin/SKILL.md) |
| Store/fetch secrets through Vault, External Secrets, or Workload Identity | [oci-security-compliance](../oci-security-compliance/SKILL.md) |
| Query OKE logs, audit, detections, or Log Analytics entities | [oci-log-analytics](../oci-log-analytics/SKILL.md) |
| Enable/query VCN Flow Logs for OKE subnet correlation | [oci-log-analytics](../oci-log-analytics/SKILL.md) + [oci-networking-compute](../oci-networking-compute/SKILL.md) |
| Deep cluster design, Multus/GVA/GPU specialization, or Oracle upstream OKE patterns | `oracle/skills` `oci/oke` after this pack's preflight/redaction |

## Common multi-step flows

| Task | Sequence |
|---|---|
| Deploy an OKE app | collect a sanitized target inventory → run `scripts/target_derived_plan.py --inventory <SANITIZED_INVENTORY_JSON>` → prove context/profile/cluster and target node architecture → build/push a matching or multi-architecture image → verify the manifest architecture and OCIR pull auth from the target namespace → render manifests and preview with `kubectl diff -f <dir>` or `kubectl apply --dry-run=server -f <dir>` → get explicit user confirmation of the exact diff → apply namespace/secrets/config/deployment/service/ingress → `kubectl rollout status` → probe readiness and public routes |
| Create a new OKE cluster for an application | validate installed `ce cluster create` and `ce node-pool create` flags → create or reuse the named cluster with a private API endpoint by default → create or reuse an explicit managed node pool → for a tenancy requiring IMDSv1 disabled, set the OKE node-pool `node_metadata` field `areLegacyImdsEndpointsDisabled` to the string `"true"` (do not use Compute `instance_options` on the node-pool resource) → verify cluster/node-pool `ACTIVE`, read back the metadata, verify every resulting worker is IMDSv2-only, and confirm at least one Kubernetes `Ready` node → continue to OCIR, ingress, and workload gates |
| Use a Kubernetes MCP server for OKE triage | treat it as an optional read surface → prove kube context/profile/cluster through this skill → restrict tools to read-only allowlists → keep secret masking and redaction on → reproduce any needed mutation through preflighted `kubectl`/`helm`/`oci_cli` here |
| Add a web service behind shared nginx ingress | create/verify `ClusterIP` service → add Ingress host/path → copy or create namespace-local TLS secret → preview with `kubectl diff` or `--dry-run=server` and confirm before applying → update DNS to the shared ingress LB → verify HTML and API routes |
| Diagnose `EXTERNAL-IP <pending>` | decide if service should be `ClusterIP` behind ingress → if direct LB is required, check LB quota, subnet annotation, service events, finalizers, and OCI CCM errors |
| Diagnose 502 / backend health `CRITICAL` | check pod readiness → service endpoints → NodePort path → LB subnet egress to node CIDR on `10256` and `30000-32767` → node subnet ingress from LB CIDR |
| Diagnose public C11B `/api/health` 502 | successful TLS plus HTTP 502 proves only that the public route responded; inspect DNS → LB listener/backend health → ingress/controller → Service endpoints → pod readiness → authenticated app flow; do not reuse a historical subnet fix without matching evidence (OCI-DEMO: KB-577) |
| Fix TLS on an OCI LB-backed service | create Kubernetes TLS secret in the same namespace → annotate backend protocol, SSL ports, and TLS secret → verify listener is HTTPS, not plain TCP |
| Recover from `ImagePullBackOff` | verify image architecture/tag exists → verify OCIR repo visibility or imagePullSecret → wait for auth-token propagation → inspect `kubectl describe pod` events |
| Handle `NodeNotReady`, bootstrap, or registration failure | classify the node pool as managed or virtual → use OKE's read-only Network Path Analyzer tests first → run/update Node Doctor only on a managed node and collect a redacted support bundle if needed → change network or node-pool configuration only after review |
| Enforce IMDSv2 on managed OKE nodes | use the OKE node-pool `node_metadata` string map with `areLegacyImdsEndpointsDisabled="true"` → inspect the installed OCI provider/API schema and a fresh plan → understand that metadata changes do not retroactively update existing workers → use a reviewed rolling replacement with capacity headroom → verify pool metadata, each replacement Compute instance, private API/RBAC, and Kubernetes `Ready`; never weaken tenancy IMDSv1 policy or retry a stale saved plan |
| Diagnose virtual-node pod/service reachability | check events and service endpoints → use `kubectl proxy` for local debugging rather than `kubectl port-forward` → use OKE Network Path Analyzer for VCN paths → do not infer a NodePort path exists |
| Inspect an enhanced-cluster add-on | inventory with `oci_cli ce cluster list-addons` and inspect with `oci_cli ce cluster get-addon` → compare version/status/configuration arguments with the target Kubernetes version → inspect the associated work request and controller logs → use only supported configuration arguments and an approved change |
| Diagnose OCI Native Ingress Controller readiness | inspect controller events/logs and backend Service endpoints → verify the documented pod readiness gate → use validation messages to correct manifests before changing LB resources |
| Update an existing image | prefer `kubectl set image --dry-run=server -o yaml` to preview the image change → get explicit user confirmation → run it for real → `kubectl rollout status` → smoke-test readiness, HTML, and JSON/API routes |
| Upgrade an OKE cluster or managed nodes | inventory control-plane, configured node-pool, and running-node versions → test workloads against the target version → review all Ready/skew/precondition blockers and the OCI work request → get target-bound approval → upgrade the control plane → cycle/replace managed nodes or use an out-of-place pool → verify workloads, add-ons, and routing; never call a zero-downtime control-plane upgrade a zero-impact application upgrade |
| Assess an enhanced-cluster add-on | inspect its enabled state, version, automatic-update choice, and configuration → confirm it has no standalone controller conflict → review its exact impact and obtain explicit approval before changing it → verify controller and workload readiness |
| Handle private or legacy kubeconfig endpoints | validate `ce cluster create-kubeconfig` help → generate a v2 kubeconfig with the reachable endpoint mode (`PUBLIC_ENDPOINT`, `PRIVATE_ENDPOINT`, `VCN_HOSTNAME`, or `LEGACY_KUBERNETES`) → for private endpoints, route via Bastion port forwarding tunnel (TCP 6443, TTL ≤ 3600s), an in-VCN jump host, or Cloud Shell with Bastion → point local kubeconfig `server` to `https://127.0.0.1:<local_port>` → confirm the OCI CLI profile/MFA auth used by the exec plugin → verify kubectl version skew and RBAC |
| Access private OKE cluster via Bastion tunnel | preflight target compartment → create Bastion port-forwarding session targeting the OKE private API IP on TCP 6443 (session TTL ≤ 3600s) → launch local SSH tunnel `ssh -N -L 6443:<OKE_PRIVATE_IP>:6443` → configure kubeconfig cluster server to `https://127.0.0.1:6443` with cluster CA → run read probe `kubectl get nodes` → tear down tunnel and delete session on completion (KB-151, KB-184) |
| Access private OKE cluster via in-VCN runner | verify runner VM is in the same VCN or an LPG/DRG-peered VCN as the OKE cluster → execute kubectl directly or via SSH tunnel from the runner (warning: unpeered cross-VCN jump hosts cannot route to private OKE endpoints, KB-187) |
| Restore a customer-demo app agent | prove OKE API `/readyz` first → verify namespace RBAC → verify pod service account / Workload Identity or instance-principal path → test only intended signed-in app endpoints → keep privileged mutations and security actions role-gated |
| Prove app-agent OCI runtime-principal readiness | generate `scripts/oci_oke_demo_troubleshoot.py runtime-principal-readiness` → inspect Deployment serviceAccountName and ServiceAccount → test Kubernetes RBAC as that service account → for managed-node instance-principal designs, run a narrow in-pod OCI read using `--auth instance_principal`; for OKE Workload Identity, use the app/SDK workload identity provider canary instead → inspect OCI Audit rows for the intended instance-principal dynamic group or workload principal → grant only the smallest read-only policy if current evidence proves it is missing |
| Run remote OKE validation without SSH blocks | generate the offline plan with `scripts/oci_oke_demo_troubleshoot.py control-plane-blocked` → use invocation-owned SSH ControlMaster under `/tmp` only when SSH is the chosen lane → transfer only reviewed source/test files → exclude env/Git/wallet/browser state → poll bounded status commands |
| Continue when the remote control-plane host is blocked | classify SSH as only one access path → use OCI APIs, Cloud Shell, Bastion, or OCI Run Command for read-only evidence → do not mark OKE, app, or data-source readiness failed from SSH alone |
| Retry a MELTS investigation that exceeded budget | generate `scripts/oci_oke_demo_troubleshoot.py melts-investigate-timeout` → prove minimum current evidence sources before conclusion → increase budget only after source availability and query limits are measured → emit a troubleshooting receipt |
| Repair app-facing OKE Security unavailable errors | generate `scripts/oci_oke_demo_troubleshoot.py oke-security-unavailable` → prove OKE API, RBAC, runtime principal, and security-provider read availability independently → keep privileged routes gated |
| Prove shared ADB/ATP/ADW readiness for a demo app | generate `scripts/oci_oke_demo_troubleshoot.py shared-adb-readiness` → hand off DB lifecycle/wallet/ACL/schema details to `oci-autonomous-db` → verify the app uses a least-privilege DB user, migration-head receipt, and redacted read/write canary |

## Project-mined guardrails

These patterns were distilled from sanitized project KBs in `OCI-DEMO` and
`oci-coordinator-oke`; do not copy their tenant-specific values.

- **Private OKE cluster connectivity (KB-151, KB-184, KB-187, KB-018):**
  A private OKE cluster exposes its Kubernetes API server on a private IP only (TCP 6443).
  Direct `kubectl` invocations from external developer workstations fail with connection timeouts.
  Connect using: (1) Bastion port-forwarding session targeting private IP :6443 with
  TTL ≤ 3600s and a local tunnel to `127.0.0.1:6443`; (2) an in-VCN runner or jump host
  (e.g., C11 control plane VM). A jump host in a separate, unpeered VCN cannot reach the
  private OKE cluster (KB-187). If using Resource Manager (ORM) with Private Endpoints for
  in-VCN execution (C10 pattern), always clean up auto-created ORM Private Endpoint VNICs
  during teardown to prevent blocked subnet/VCN deletions (KB-018).
- **Private worker subnet routing (KB-018):**
  Worker nodes in private subnets require a NAT gateway configured in the subnet route table
  to communicate with the OKE control plane and download container images from public registries.
- **NodePort and health check security rules:**
  Verify that worker node security lists/NSGs permit ingress from the load balancer subnet
  on NodePort range `30000-32767` and kube-proxy health check port `10256` to avoid 502/CRITICAL backends.
- **CRI-O short name resolution policy on Oracle Linux (OKE):**
  Oracle Linux worker nodes running CRI-O require fully qualified image names (e.g. `<region-key>.ocir.io/<namespace>/<repo>:<tag>`, `docker.io/library/nginx:latest`, or `quay.io/...`). Unqualified short names (such as `image: nginx` or `image: alpine`) can fail with image pull errors or ambiguous registry lookup errors. Always configure fully qualified image references in deployment manifests.
- **Worker allocatable resources, root volume LVM expansion, and CRI-O storage corruption (KB-504, KB-022):**
  Worker nodes provisioned on 100 GB boot volumes may leave rootfs partition/LVM `ocivolume-root` at ~36 GB with ~54 GB unpartitioned, tripping the soft-eviction threshold (~80-85%). Because CRI-O shares the root filesystem (`imageFs == rootfs`), high image pull churn under disk pressure corrupts the CRI-O image layer metadata (`crictl images` failing with `size for layer is unknown, failing getSize()`), rendering kubelet GC and image-gc DaemonSets unable to clean orphaned layers. Prevent this by auto-expanding worker root filesystems (`growpart`, `lvextend`, `xfs_growfs`), specifying pod `ephemeral-storage` requests/limits, and scheduling periodic `crictl rmi --prune` jobs. If corruption occurs, node recycling may re-corrupt under churn; repair the node by stopping kubelet/crio and running `crio wipe -f`.
- **Compartment enumeration for OKE clusters (KB-043):**
  The OCI Container Engine API `ContainerEngineClient.list_clusters` does NOT support `compartment_id_in_subtree`. A search on the root or parent compartment returns only clusters directly in that compartment. Always enumerate active sub-compartments recursively (`identity.list_compartments(compartment_id_in_subtree=True)`) to discover all OKE clusters in a tenancy.
- **CoreDNS custom rewrite for private endpoint ADB and OCI Cache (KB-204):**
  OKE CoreDNS imports `custom/*.server` from `/etc/coredns/custom` (mounted from `configmap/coredns-custom` in `kube-system`). Pods resolving regional private endpoint FQDNs (e.g. `<db_name>.adb.<region>.oraclecloud.com` or `<cluster-hash>-p.redis.<region>.oci.oraclecloud.com`) fail with `[Errno -2] Name or service not known` because upstream CoreDNS forwarding does not consistently query the private VCN resolver (`169.254.169.254`). Resolve this by creating `coredns-custom` in `kube-system` with a `hosts` block mapping the FQDN to its private endpoint IP (`hosts { <IP> <FQDN>; fallthrough }`) and running `kubectl rollout restart deploy/coredns -n kube-system`.
- **Public Load Balancer NSG lockdown and Security List union precedence (KB-203):**
  To lock down a public OKE `LoadBalancer` service to an operator IP allowlist, annotate the service with `service.beta.kubernetes.io/oci-load-balancer-network-security-groups: "<NSG_OCID>"`. Crucially, remove broad `0.0.0.0/0` ingress rules for TCP 80/443 on the load balancer subnet's Security List; otherwise, the permissive Security List rule overrides the NSG allowlist via union evaluation.
- **Multi-process ingress segmentation and IDCS oauth2-proxy routing (KB-205):**
  When hosting an interactive UI (such as Streamlit on 8501) alongside a REST API (FastAPI on 3001) under a single domain with IDCS SSO:
  * Deploy `oauth2-proxy:4180` using an exact 32-byte base64 cookie secret (`python3 -c "import os, base64; print(base64.b64encode(os.urandom(32)).decode())"`). Non-standard lengths cause immediate startup panics.
  * Segment ingress into three separate definitions: (1) `/oauth2` -> `oauth2-proxy:4180` (public authentication flow), (2) `/api`, `/health`, `/docs`, `/chat`, `/incidents` -> backend API port `3001`, and (3) `/` -> UI port `8501` gated by `nginx.ingress.kubernetes.io/auth-url: "https://$host/oauth2/auth"` and injecting `X-Auth-Request-User` headers. This eliminates localhost loopback redirects (`http://127.0.0.1:8501`).
- Prefer **ClusterIP + shared authenticated ingress** for public web apps. Direct
  per-app `LoadBalancer` services are more expensive and can bypass ingress auth.
- For OCI-DEMO, preserve protected authenticated ingress while diagnosing the
  public Control Plane. Guardian remains private and disabled until a separate
  authorization packet names targets, allowed techniques, time window, and
  stop conditions.
- OCI CLI `--output json` list responses may put records directly in `.data`;
  do not assume `.data.items`. Normalize the observed shape before iterating:
  `jq -r '.data as $d | (if ($d | type) == "array" then $d else ($d.items // []) end)[] | .name'`.
  Always pass `--all` to list operations to avoid silent pagination truncation.
  When querying LB backend health, use the returned backend-set `.name`, never an
  array index, and first correlate the public route to the exact target-compartment
  load balancer. See OCI-DEMO KB-595/596.
- For direct OCI LB services, set the LB subnet annotation when the controller
  cannot infer it, and use flexible LB shape annotations when fixed-shape quota
  is constrained.
- Treat Kubernetes TLS secrets as the default frontend TLS mechanism for OKE
  service-controller LBs. A certificate imported into OCI Certificates Service
  alone does not necessarily create an HTTPS listener.
- OKE virtual nodes do not expose NodePorts and do not support normal
  `exec`/`port-forward`/`logs --previous` debugging. Use `kubectl proxy` for
  supported local pod/service inspection. Use OCI Native Ingress,
  an ingress controller that targets pod IPs, or add a managed node pool with a
  matching CNI before installing nginx-ingress.
- OKE Network Path Analyzer tests are read-only configuration analysis: use the
  cluster's **Path analysis tests** for API, node, pod, or load-balancer paths
  before broadening security rules. A `Reachable` result does not prove that an
  application is healthy; it only evaluates the configured network path.
- Node Doctor applies to managed-node compute instances, never virtual nodes.
  Prefer the Console Worker Node Troubleshooting Guide or OCI Run Command to
  avoid ad hoc SSH. Update the pre-installed script before collecting output;
  sanitize any bundle before attaching it to a support case.
- Keep kubeconfigs on token version `2.0.0`. OCI-generated tokens are short-
  lived, cluster-scoped, and user-specific: do not share the file, and do not
  repurpose it for CI/CD. Use a purpose-scoped Kubernetes service account or
  supported workload identity design for automation.
- For Kubernetes 1.35 and later, use OKE worker images for new managed-node
  deployments and upgrades. A node-pool version edit changes only newly created
  nodes; on an enhanced cluster, cycle the node pool to apply the change to
  managed nodes, while basic clusters require
  a deliberate replacement/out-of-place strategy.
- Workload identities require enhanced clusters. Bind OCI permissions to the
  intended Kubernetes namespace and service account, and verify IAM, Kubernetes
  RBAC, and Audit evidence separately. Image-pull authorization is a separate
  OCI Registry path.
- Enhanced clusters manage essential and optional cluster add-ons. Discover the
  current state with `oci_cli ce cluster list-addons` and inspect one with
  `oci_cli ce cluster get-addon`; use supported versions and approved
  configuration arguments, then inspect the resulting work request. Oracle
  reconciles add-ons, so direct Kubernetes edits can be discarded.
- Workload identities are enhanced-cluster-only. Bind each workload to a
  least-privilege Kubernetes service account and narrowly scoped OCI IAM policy;
  do not distribute OCI user credentials to pods.
- For managed-node OKE apps that intentionally use instance principals, prove
  the runtime path from inside the pod with a low-impact OCI read and OCI Audit
  correlation. Browser login, a healthy frontend, or an OCIR `imagePullSecret`
  is not runtime OCI authorization evidence.
- The OCI Native Ingress Controller can run as a cluster add-on. Configure the
  documented pod readiness gate and diagnose its validation logs before manually
  changing OCI load-balancer resources.
- Use server-side apply or clean stale
  `kubectl.kubernetes.io/last-applied-configuration` annotations when manifests
  ever contained secret values.
- Keep long remote image pulls/builds detached from SSH sessions; poll short
  status commands rather than holding one fragile connection open.
- A blocked jump host or `control-plane-oci` alias is not proof that OKE, Log
  Analytics, or the application is down. Switch to API-first reads (`oci_cli`,
  Cloud Shell, Bastion, or OCI Run Command) and record the SSH path as a
  degraded operator-access lane only.
- Kubernetes MCP servers such as `mcp-server-kubernetes` are optional read
  surfaces, not authorities. Prefer `ALLOW_ONLY_READONLY_TOOLS` or a narrow
  `ALLOWED_TOOLS` list, keep `MASK_SECRETS` enabled, and do not expose
  `kubectl_generic`, `node_management`, pod cleanup, delete, or Helm uninstall
  tools in production sessions.

## Safety notes

- Load only the env file explicitly named by the operator; do not auto-load
  sibling repositories or rely on a convenient current context.
- Do not inline secrets in `Deployment.env` or `kubectl apply` payloads. Prefer
  Vault + External Secrets or Workload Identity; if literal Kubernetes secrets
  are unavoidable, avoid client-side last-applied annotations.
- Public browser UIs without strong built-in auth must sit behind an authenticated
  ingress or app-level auth. Direct `LoadBalancer` services are public exposure.
- Health endpoints should expose probe-safe status only, not internal URLs,
  OCIDs, topology, or tokens.
- MCP is not a source of truth. Mutations still use this pack's preflight and
  redaction; MCP output is evidence to verify, not an authorization to change
  an OKE cluster.
- `kubectl`/`helm` mutations are outside `run_action` (that wrapper only covers
  `oci_cli`). The destructive-command hook now mechanically blocks `kubectl
  delete`/`drain`/`cordon`/forced `replace` and `helm uninstall`/its `delete`
  alias/`rollback` — but `kubectl apply`, `kubectl set image`, and `helm
  install`/`upgrade` are routine updates it does not treat as destructive, so
  this skill's own discipline is still their only guard. Never run any of
  these straight from a rendered manifest. First preview with `kubectl diff -f
  <dir>`, `kubectl apply --dry-run=server -f <dir>`, or `helm diff upgrade`
  (or `helm template` + review for a cluster without the diff plugin); get
  explicit user confirmation of the exact resources/fields changed; only then
  run the mutating command for real. Treat `kubectl delete`, `drain`,
  `cordon`+`drain`, and any `helm uninstall` as destructive — require the same
  explicit approval as an `oci_cli` delete, and never bypass the mechanical
  guard with `OCI_SKILLS_FORCE=true` without that same approval first.
- Never invent `oci` flags. Fetch command shapes with:
  `python3 scripts/oci_cli_help.py <service> <op>`.
- Treat OKE control-plane and node-pool upgrades as operational changes. Before
  initiating one, capture the current and target versions, node readiness,
  configured-versus-running managed-node versions, PodDisruptionBudgets,
  capacity headroom, and OCI work-request status. Control planes cannot be
  downgraded; follow Kubernetes version-skew policy and do not skip required
  intermediate minor versions. Virtual nodes are upgraded with the control
  plane, so include their workloads in impact assessment.
- **OKE Cluster Visibility & Fleet Health Contracts (KB-612):**
  Structure cluster health into three observable layers: (1) Node Pools & per-node CPU/RAM allocation,
  (2) Namespace workload health (`pods_running`/`pods_total`), and (3) Istio Service Mesh mTLS STRICT health.
- **OctoDemo Platform Architecture & Cross-App Orchestration (KB-613):**
  For unified demo environments, bind microservices to standard domain suites (`cp.octodemo.cloud` for orchestration,
  `obs.octodemo.cloud` for Atlas, `ops.octodemo.cloud` for triage, `guardian.octodemo.cloud` for CSPM,
  `observeai.octodemo.cloud` for threat matrix). Ensure consistent multi-theme support (`redwood`, `dark`,
  `light`, `palantir-slate`).
- **Demo Compute & Container Instance Lifecycle State Machine (KB-614):**
  Implement dedicated instance controls (`start`, `stop`, `restart`) with protected instance guardrails
  (`protected: true` on critical control plane or bastion VMs preventing inadvertent shutdown during live demos).

## Expected output

```text
Finding:      <one-line OKE issue>
Evidence:     <redacted kubectl/oci output, service event, rollout state, or LB health>
Action:       <exact command applied or dry-run recommendation>
Verification: <rollout, endpoint, ingress, TLS, image-pull, or backend health check>
KB:           <known KB applied, or new sanitized KB entry added>
```

## Official documentation

[OKE](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm) ·
[OKE access control](https://docs.oracle.com/en-us/iaas/Content/ContEng/Concepts/contengaboutaccesscontrol.htm) ·
[cluster access and kubeconfig v2](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengdownloadkubeconfigfile.htm) ·
[Network Path Analyzer tests](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengtroubleshooting_topic-network_troubleshooting.htm) ·
[Node Doctor](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengtroubleshooting_topic-node_troubleshooting.htm) ·
[cluster upgrades](https://docs.oracle.com/en-us/iaas/Content/ContEng/Concepts/contengaboutupgradingclusters.htm) ·
[cluster add-ons](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengintroducingclusteraddons.htm) ·
[Workload Identities](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contenggrantingworkloadaccesstoresources.htm) ·
[OCI Native Ingress Controller troubleshooting](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contengsettingupnativeingresscontroller-troubleshooting.htm) ·
[OCIR](https://docs.oracle.com/en-us/iaas/Content/Registry/home.htm) ·
[Load Balancer](https://docs.oracle.com/en-us/iaas/Content/Balance/home.htm)

**Open Knowledge Format grounding** - every doc link here is registered and liveness-checked in the [oracle-docs.md index](../../references/oracle-docs.md) (the pack's single source of truth). When extending this skill, cite the most specific official page through that index; the non-official MCP gateway is never a source of truth.

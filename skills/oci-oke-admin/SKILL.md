---
name: oci-oke-admin
description: >-
  OCI Administrator skill for Oracle Kubernetes Engine (OKE) application and
  cluster operations. Use when working with OKE clusters, kubeconfig, kubectl,
  Kubernetes manifests, namespaces, deployments, services, ingress-nginx, OCI
  Native Ingress Controller, OCI LoadBalancer services, TLS certificates,
  Kubernetes TLS secrets, OCIR image pulls, imagePullSecrets, rollout status,
  CrashLoopBackOff, ImagePullBackOff, Pending LoadBalancers, virtual nodes,
  managed node pools, Workload Identity, External Secrets, or OKE deployment
  troubleshooting. Also use when evaluating Kubernetes MCP read surfaces against
  OKE safety rules. Triggers: OKE deploy, nginx ingress, LB pending, certificate
  or TLS listener issue, kubeconfig endpoint error, kubectl Unauthorized,
  backend health CRITICAL, NodePort, virtual node, OCIR Unauthorized, pod
  readiness/liveness, Kubernetes MCP, or public app exposure on Kubernetes.
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

## Routing

| You need to… | Read |
|---|---|
| Deploy or repair OKE app exposure, ingress, LB, TLS, OCIR, kubeconfig, rollout, or node-pool issues | [references/oke-operations.md](../../references/oke-operations.md) |
| Change VCN, subnet, NSG, route table, compute, or generic LB resources outside Kubernetes | [oci-networking-compute](../oci-networking-compute/SKILL.md) |
| Create policies, dynamic groups, service limits, or budgets | [oci-iam-admin](../oci-iam-admin/SKILL.md) |
| Store/fetch secrets through Vault, External Secrets, or Workload Identity | [oci-security-compliance](../oci-security-compliance/SKILL.md) |
| Query OKE logs, audit, detections, or Log Analytics entities | [oci-log-analytics](../oci-log-analytics/SKILL.md) |
| Deep cluster design, Multus/GVA/GPU specialization, or Oracle upstream OKE patterns | `oracle/skills` `oci/oke` after this pack's preflight/redaction |

## Common multi-step flows

| Task | Sequence |
|---|---|
| Deploy an OKE app | prove context/profile/cluster → build/push linux/amd64 image → verify OCIR pull auth from target namespace → apply namespace/secrets/config/deployment/service/ingress → `kubectl rollout status` → probe readiness and public routes |
| Use a Kubernetes MCP server for OKE triage | treat it as an optional read surface → prove kube context/profile/cluster through this skill → restrict tools to read-only allowlists → keep secret masking and redaction on → reproduce any needed mutation through preflighted `kubectl`/`helm`/`oci_cli` here |
| Add a web service behind shared nginx ingress | create/verify `ClusterIP` service → add Ingress host/path → copy or create namespace-local TLS secret → update DNS to the shared ingress LB → verify HTML and API routes |
| Diagnose `EXTERNAL-IP <pending>` | decide if service should be `ClusterIP` behind ingress → if direct LB is required, check LB quota, subnet annotation, service events, finalizers, and OCI CCM errors |
| Diagnose 502 / backend health `CRITICAL` | check pod readiness → service endpoints → NodePort path → LB subnet egress to node CIDR on `10256` and `30000-32767` → node subnet ingress from LB CIDR |
| Fix TLS on an OCI LB-backed service | create Kubernetes TLS secret in the same namespace → annotate backend protocol, SSL ports, and TLS secret → verify listener is HTTPS, not plain TCP |
| Recover from `ImagePullBackOff` | verify image architecture/tag exists → verify OCIR repo visibility or imagePullSecret → wait for auth-token propagation → inspect `kubectl describe pod` events |
| Update an existing image | prefer `kubectl set image` for image-only changes → `kubectl rollout status` → smoke-test readiness, HTML, and JSON/API routes |
| Handle private or legacy kubeconfig endpoints | reuse a matching current context first → try `create-kubeconfig` without forced endpoint for legacy clusters → use Cloud Shell/bastion tunnel for private endpoints |

## Project-mined guardrails

These patterns were distilled from sanitized project KBs in `OCI-DEMO` and
`oci-coordinator-oke`; do not copy their tenant-specific values.

- Prefer **ClusterIP + shared authenticated ingress** for public web apps. Direct
  per-app `LoadBalancer` services are more expensive and can bypass ingress auth.
- For direct OCI LB services, set the LB subnet annotation when the controller
  cannot infer it, and use flexible LB shape annotations when fixed-shape quota
  is constrained.
- Treat Kubernetes TLS secrets as the default frontend TLS mechanism for OKE
  service-controller LBs. A certificate imported into OCI Certificates Service
  alone does not necessarily create an HTTPS listener.
- OKE virtual nodes do not expose NodePorts and do not support normal
  `exec`/`port-forward`/`logs --previous` debugging. Use OCI Native Ingress,
  an ingress controller that targets pod IPs, or add a managed node pool with a
  matching CNI before installing nginx-ingress.
- Use server-side apply or clean stale
  `kubectl.kubernetes.io/last-applied-configuration` annotations when manifests
  ever contained secret values.
- Keep long remote image pulls/builds detached from SSH sessions; poll short
  status commands rather than holding one fragile connection open.
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
- MCP is not a source of truth. Mutations still use this pack's preflight,
  `run_action`, redaction, and exact approval gates; MCP output is evidence to
  verify, not an authorization to change an OKE cluster.
- Never invent `oci` flags. Fetch command shapes with:
  `python3 scripts/oci_cli_help.py <service> <op>`.

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
[OCIR](https://docs.oracle.com/en-us/iaas/Content/Registry/home.htm) ·
[Load Balancer](https://docs.oracle.com/en-us/iaas/Content/Balance/home.htm)

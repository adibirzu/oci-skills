# OKE Operations Reference

Reusable, sanitized OKE deployment and troubleshooting patterns. This reference
pairs with [oci-oke-admin](../skills/oci-oke-admin/SKILL.md). It is distilled
from production-style project KBs without tenant-specific identifiers.

All examples use placeholders. Never commit real OCIDs, IPs, OCIR namespaces,
domains, API keys, fingerprints, or certificate material.

---

## Table of contents

- [Preflight and context proof](#preflight-and-context-proof)
- [Deployment baseline](#deployment-baseline)
- [Ingress-first exposure](#ingress-first-exposure)
- [Direct OCI LoadBalancer services](#direct-oci-loadbalancer-services)
- [TLS and certificates](#tls-and-certificates)
- [OCIR image pulls](#ocir-image-pulls)
- [Kubeconfig endpoint failures](#kubeconfig-endpoint-failures)
- [Virtual nodes and nginx ingress](#virtual-nodes-and-nginx-ingress)
- [Rollout and health checks](#rollout-and-health-checks)
- [Secrets and last-applied annotations](#secrets-and-last-applied-annotations)
- [Troubleshooting matrix](#troubleshooting-matrix)

## Preflight and context proof

Before any mutating `kubectl`, `helm`, `oci`, or deployment-script action:

```bash
./scripts/oci_preflight.sh -c "$COMPARTMENT_OCID"

kubectl config current-context
kubectl config view -o json \
  | jq -r '.contexts[] | [.name, .context.cluster, .context.user] | @tsv'
kubectl config view -o json \
  | jq -r '.users[] | [.name, ((.user.exec.args // []) | join(" "))] | @tsv'

oci_cli ce cluster get --cluster-id "<OKE_CLUSTER_OCID>" \
  --query 'data.{name:name,state:"lifecycle-state","kubernetes-version":"kubernetes-version"}'
kubectl auth can-i --list
```

Context names are labels, not proof. Verify the OCI exec profile, region,
cluster identity, and RBAC every time.

## Deployment baseline

Recommended order for a portable OKE workload:

1. Resolve profile, region, compartment, cluster, and namespace.
2. Build and push a `linux/amd64` image when targeting OCI-managed amd64 nodes.
3. Verify the target namespace can pull from OCIR.
4. Apply namespace, service account, RBAC, configmaps, secrets/ExternalSecrets,
   deployment, service, ingress, and network policies.
5. Wait for rollout and inspect events:

```bash
kubectl -n "<NAMESPACE>" rollout status deployment/"<APP>" --timeout=240s
kubectl -n "<NAMESPACE>" get pods,svc,ingress -o wide
kubectl -n "<NAMESPACE>" describe deployment "<APP>"
kubectl -n "<NAMESPACE>" describe svc "<SERVICE>"
```

For image-only updates, prefer:

```bash
kubectl -n "<NAMESPACE>" set image deployment/"<APP>" app="<IMAGE>:<TAG>"
kubectl -n "<NAMESPACE>" rollout status deployment/"<APP>" --timeout=240s
```

This avoids strategic-merge conflicts where a previously patched env var leaves
both `value` and `valueFrom` on the same entry.

## Ingress-first exposure

For public web apps, prefer one shared ingress controller and namespace-local
`ClusterIP` services.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: app
  namespace: <NAMESPACE>
spec:
  type: ClusterIP
  selector:
    app: app
  ports:
    - name: http
      port: 80
      targetPort: 8080
```

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: app
  namespace: <NAMESPACE>
  annotations:
    kubernetes.io/ingress.class: nginx
spec:
  tls:
    - hosts: ["<APP_HOST>"]
      secretName: <TLS_SECRET>
  rules:
    - host: <APP_HOST>
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: app
                port:
                  number: 80
```

Copy a wildcard or shared TLS cert into each namespace by creating a new
namespace-local secret from controlled certificate files, or by copying an
existing secret after stripping namespace-specific metadata:

```bash
kubectl -n "<SOURCE_NS>" get secret "<TLS_SECRET>" -o yaml \
  | sed 's/namespace: .*/namespace: <TARGET_NS>/' \
  | kubectl apply -f -
```

Use this only with non-secret output handling discipline. Never paste the
decoded cert key into docs or logs.

## Direct OCI LoadBalancer services

Use direct `type: LoadBalancer` only when a shared ingress is not appropriate.
Otherwise direct services can create unnecessary public edges and bypass
ingress auth.

When direct LB is required, include the subnet annotation and shape annotations
if your tenancy has constrained fixed-shape quota:

```yaml
metadata:
  annotations:
    service.beta.kubernetes.io/oci-load-balancer-subnet1: "<LB_SUBNET_OCID>"
    service.beta.kubernetes.io/oci-load-balancer-shape: "flexible"
    service.beta.kubernetes.io/oci-load-balancer-shape-flex-min: "10"
    service.beta.kubernetes.io/oci-load-balancer-shape-flex-max: "10"
spec:
  type: LoadBalancer
```

If `EXTERNAL-IP` stays `<pending>`:

```bash
kubectl -n "<NAMESPACE>" describe svc "<SERVICE>"
kubectl -n "<NAMESPACE>" get events --sort-by=.lastTimestamp | tail -40
```

Common causes:

- Service should be `ClusterIP` because ingress already fronts it.
- LB quota exhausted.
- Missing `service.beta.kubernetes.io/oci-load-balancer-subnet1`.
- Stale service finalizer or OCI CCM cached state after a previous LB drift.
- Wrong LB subnet security list, so backends never become healthy.

For stale service/LB associations, remove finalizers only after confirming the
current LB is gone or unusable, then recreate with a new service name to break
controller cache. Treat this as destructive to public traffic.

## TLS and certificates

For OKE service-controller LBs, use a Kubernetes TLS secret in the same namespace
and the OCI LB TLS annotations. Do not assume an OCI Certificates Service OCID
alone will create an HTTPS listener.

```bash
kubectl -n "<NAMESPACE>" create secret tls "<TLS_SECRET>" \
  --cert="<CERT_CHAIN_PATH>" \
  --key="<CERT_KEY_PATH>" \
  --dry-run=client -o yaml | kubectl apply -f -
```

```yaml
metadata:
  annotations:
    service.beta.kubernetes.io/oci-load-balancer-backend-protocol: "HTTP"
    service.beta.kubernetes.io/oci-load-balancer-ssl-ports: "443"
    <OCI_LB_TLS_SECRET_ANNOTATION_KEY>: "<K8S_TLS_OBJECT_NAME>"
spec:
  type: LoadBalancer
  ports:
    - name: https
      port: 443
      targetPort: 8080
      protocol: TCP
```

Use `service.beta.kubernetes.io/oci-load-balancer-tls-secret` as the annotation
key for the namespace-local Kubernetes TLS object name.

Verify the listener is HTTPS, not plain TCP:

```bash
curl -vkI "https://<APP_HOST>/"
kubectl -n "<NAMESPACE>" describe svc "<SERVICE>"
```

## OCIR image pulls

OCIR repositories are private by default. Production OKE pulls should use a
namespace-local `imagePullSecret` or Workload Identity-compatible pattern with
least privilege.

```bash
# Create <TMP_0600_DOCKER_CONFIG_JSON> in a 0700 temp directory from a
# secret-manager value; never place the OCIR auth token on argv.
kubectl -n "<NAMESPACE>" create secret generic ocir-pull \
  --from-file=.dockerconfigjson="<TMP_0600_DOCKER_CONFIG_JSON>" \
  --type=kubernetes.io/dockerconfigjson \
  --dry-run=client -o yaml | kubectl apply -f -
```

```yaml
spec:
  imagePullSecrets:
    - name: ocir-pull
```

Checklist for `ImagePullBackOff` / `Unauthorized`:

- Image exists at the exact tag.
- Image architecture matches nodes, usually `linux/amd64`.
- Auth token belongs to the registry tenancy/user.
- New auth token had 30-60 seconds to propagate.
- Secret exists in the same namespace as the pod.
- Cross-tenancy pulls use credentials for the registry tenancy, not the cluster
  tenancy.
- Cached Docker credentials on a remote builder are not stale.

For locally built images on VMs, use local-only tags until pushing:

```bash
docker build -t app:local .
docker run --rm app:local
docker tag app:local "<REGION>.ocir.io/<OCIR_NAMESPACE>/<REPO>:<TAG>"
docker push "<REGION>.ocir.io/<OCIR_NAMESPACE>/<REPO>:<TAG>"
```

## Kubeconfig endpoint failures

`oci ce cluster create-kubeconfig` can fail with `Invalid endpoint: Target
endpoint is not available` on private or legacy endpoint clusters.

Safe fallback order:

1. If the current `kubectl` context already points at the target cluster/server,
   reuse it.
2. For legacy clusters, try `create-kubeconfig` without `--kube-endpoint`.
3. For private clusters, run from OCI Cloud Shell, a bastion, or a configured
   tunnel that can reach the private API endpoint.
4. Re-run `kubectl auth can-i --list`; kubeconfig creation does not prove RBAC.

## Virtual nodes and nginx ingress

OKE virtual nodes do not expose NodePorts and do not support normal
`kubectl exec`, `port-forward`, or `logs --previous` debugging. Plain
`type: LoadBalancer` services that depend on NodePort backends can fail even
when in-cluster ClusterIP traffic works.

Preferred options:

- OCI Native Ingress Controller on supported enhanced clusters.
- nginx-ingress configured for the cluster's networking model.
- A managed node pool with CNI matching the cluster, then pin ingress controller
  pods and admission webhook jobs to that managed pool.

Before adding a managed pool, check the cluster pod network option. A cluster
using `OCI_VCN_IP_NATIVE` needs a node pool with matching pod networking; older
CLI versions may not expose every required flag, so use the OCI SDK if needed.

## Rollout and health checks

Probe both machine and browser paths. A `/ready` JSON check can pass while the
HTML shell, auth redirect, or static files are broken.

```bash
kubectl -n "<NAMESPACE>" rollout status deployment/"<APP>" --timeout=240s
kubectl -n "<NAMESPACE>" get endpoints "<SERVICE>" -o wide
curl -fsS "https://<APP_HOST>/ready"
curl -fsS -o /dev/null -w "%{http_code}\n" "https://<APP_HOST>/"
curl -fsS "https://<APP_HOST>/api/version"
```

For container health checks, use the endpoint that the selected transport
actually exposes. Examples:

- FastMCP SSE: `/sse`
- FastMCP Streamable HTTP: `/mcp`
- App-specific APIs: `/healthz` or `/ready` only when implemented

Use `127.0.0.1` inside Docker health checks, not `0.0.0.0`.

## OCI Kubernetes Monitoring checks

For `oracle-quickstart/oci-kubernetes-monitoring`, verify both data paths:

- Log Analytics path: discovery jobs upload Kubernetes object logs and discovery
  payloads.
- Metrics path: Management Agent publishes metrics, usually under
  `mgmtagent_kubernetes_metrics`.

If the UI shows `Invalid Date`, blank CPU/memory, or `Latest telemetry Unknown`,
do not assume the collector is down. First prove current metrics exist:

```bash
oci_cli monitoring metric-data summarize-metrics-data \
  --compartment-id "<COMPARTMENT_OCID>" \
  --namespace "mgmtagent_kubernetes_metrics" \
  --query-text 'nodeCpuUsage[1m]{clusterName = "<CLUSTER_KEY>"}.mean()' \
  --start-time "<RFC3339_START>" \
  --resolution 1m
```

Then inspect the Log Analytics Kubernetes Cluster entity metadata. The solution
UI depends on `cluster`, `name`, `cluster_name`, `cluster_date`, and
`metrics_namespace`. Repair metadata rather than renaming entities; entity names
may be immutable. Include `--time-last-discovered` on metadata updates so
freshness does not regress.

## Secrets and last-applied annotations

Avoid putting secret values directly in Deployment env entries. Prefer
`secretKeyRef`, External Secrets, Vault, or Workload Identity.

If an older client-side `kubectl apply` submitted secrets or inline env values,
clean stale annotations:

```bash
kubectl -n "<NAMESPACE>" annotate deployment "<APP>" \
  kubectl.kubernetes.io/last-applied-configuration- || true
kubectl -n "<NAMESPACE>" annotate secret "<SECRET>" \
  kubectl.kubernetes.io/last-applied-configuration- || true
```

Use server-side apply for manifests that include Secret `stringData`, or split
secret creation from declarative workload apply.

## Troubleshooting matrix

| Symptom | Likely cause | First checks |
|---|---|---|
| `kubectl Unauthorized` after kubeconfig | IAM token mint works, Kubernetes RBAC missing | `kubectl auth can-i --list`; ClusterRoleBinding |
| `Target endpoint is not available` | Forced wrong endpoint mode or private/legacy API endpoint | Try existing context; omit `--kube-endpoint`; use Cloud Shell/bastion |
| `ImagePullBackOff` / OCIR Unauthorized | Missing or wrong imagePullSecret, private repo, token propagation, wrong image tag | `kubectl describe pod`; verify tag; recreate secret; wait 60s |
| `EXTERNAL-IP <pending>` | Service should be ClusterIP, LB quota, missing subnet annotation, stale finalizer | `kubectl describe svc`; events; LB quota; service annotations |
| OCI LB 502 / backend `CRITICAL` | LB subnet cannot reach node health/NodePort or wrong LB subnet | service endpoints; NodePort; security list egress/ingress |
| HTTPS fails but HTTP works | LB listener is TCP/plain or TLS secret missing | service annotations; `curl -vkI`; listener config |
| nginx ingress external curl returns 000/52 | Virtual-node NodePort path or LB health failure | node types; backend health; ingress controller scheduling |
| `valueFrom may not be specified when value is not empty` | Strategic merge conflict from a previously patched env var | `kubectl set image`; server-side apply; normalize manifest |
| Pod CrashLoop after secret rotation | K8s secret drift, raw shell metacharacters, stale DB/API credential | inspect pod logs; validate secret values are shell-safe only when sourced |
| Monitoring dashboards empty | Telemetry delay or wrong cluster/entity association | wait 10-15 min; verify Prometheus targets and entity cluster identity |

## Source pattern origins

Sanitized lessons came from:

- `OCI-DEMO/KB.md`: OKE ingress-first migration, direct LB auth exposure,
  LoadBalancer pending, LB subnet/NodePort health, TLS-secret listener fixes,
  virtual-node ingress constraints, kubeconfig endpoint fallback, OCIR pull
  failures, rollout verification, and stale last-applied annotations.
- `OCI-DEMO/RUNBOOK.md`: C8/C10/C22 OKE rollout sequences and known remediation
  checks.
- `oci-coordinator-oke/deploy/oke/README.md`: OKE app bundle shape, protected
  profile guardrails, Vault sync, Workload Identity, ingress/API split, and
  rollout verification.
- `oci-coordinator-oke/KB.md` and `docs/OCTO_DEPLOY_KB.md`: SSO-protected ingress
  path routing, strategic-merge env conflict, and ClusterIP behind nginx-ingress.

Keep future imports at this same abstraction level: reusable cause/fix pattern,
not project topology.

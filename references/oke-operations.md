# OKE Operations Reference

Reusable, sanitized OKE deployment and troubleshooting patterns. This reference
pairs with [oci-oke-admin](../skills/oci-oke-admin/SKILL.md). It is distilled
from production-style project KBs without tenant-specific identifiers.

All examples use placeholders. Never commit real OCIDs, IPs, OCIR namespaces,
domains, API keys, fingerprints, or certificate material.

---

## Table of contents

- [Preflight and context proof](#preflight-and-context-proof)
- [Cluster creation and node-pool readiness](#cluster-creation-and-node-pool-readiness)
- [Enhanced-cluster add-on checks](#enhanced-cluster-add-on-checks)
- [Deployment baseline](#deployment-baseline)
- [Ingress-first exposure](#ingress-first-exposure)
- [OCI Native Ingress Controller](#oci-native-ingress-controller)
- [Direct OCI LoadBalancer services](#direct-oci-loadbalancer-services)
- [TLS and certificates](#tls-and-certificates)
- [OCIR image pulls](#ocir-image-pulls)
- [Kubeconfig endpoint failures](#kubeconfig-endpoint-failures)
- [OKE control-plane and RBAC readiness](#oke-control-plane-and-rbac-readiness)
- [Virtual nodes and nginx ingress](#virtual-nodes-and-nginx-ingress)
- [Workload identities](#workload-identities)
- [Runtime-principal readiness for app agents](#runtime-principal-readiness-for-app-agents)
- [Network and node diagnosis](#network-and-node-diagnosis)
- [Upgrade readiness](#upgrade-readiness)
- [Rollout and health checks](#rollout-and-health-checks)
- [Remote builders and SSH-safe execution](#remote-builders-and-ssh-safe-execution)
- [API-first fallback when SSH is blocked](#api-first-fallback-when-ssh-is-blocked)
- [Optional Kubernetes MCP read surface](#optional-kubernetes-mcp-read-surface)
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

## Cluster creation and node-pool readiness

Cluster creation and worker capacity are separate OCI resources. A successful
cluster work request does not create a schedulable worker pool, and a stopped
managed-node instance can make every application symptom look like a Kubernetes
failure. Use the installed CLI help before copying flags; current OCI CLI
releases use `--endpoint-subnet-id` and `--endpoint-public-ip-enabled` rather
than the retired `--endpoint-config` payload.

For reusable scripts, make the API endpoint private by default and require
explicit variables for the endpoint subnet, worker subnet, Kubernetes version,
node-pool name, shape, count, and optional worker image. After creation, query
the cluster and node pool by name, wait for `ACTIVE`, then prove at least one
Kubernetes node is `Ready` before deploying workloads:

```bash
python3 scripts/oci_cli_help.py --json ce cluster create
python3 scripts/oci_cli_help.py --json ce node-pool create
oci_cli ce cluster get --cluster-id "<OKE_CLUSTER_OCID>" \
  --query 'data.{state:"lifecycle-state",type:type,version:"kubernetes-version"}'
oci_cli ce node-pool list --compartment-id "<COMPARTMENT_OCID>" \
  --cluster-id "<OKE_CLUSTER_OCID>" --all \
  --query 'data[].{name:name,state:"lifecycle-state",size:size}'
kubectl get nodes -o wide
kubectl get nodes --no-headers | awk '$2 == "Ready" { count++ } END { exit(count ? 0 : 1) }'
```

Creation is idempotent: if the named cluster or node pool already exists, read
and verify it instead of issuing another create. Keep Terraform as the durable
owner when a Terraform stack exists; a direct CLI bootstrap is a break-glass
exception that must be reconciled into the stack.

Use an OCI-generated version `2.0.0` kubeconfig. Its exec plugin mints
short-lived, cluster-scoped, user-specific tokens; it is not shareable or a
CI/CD credential. Generate it with the endpoint that is reachable from the
operator's current network, then verify both client/server compatibility and
authorization:

```bash
oci_cli ce cluster create-kubeconfig \
  --cluster-id "<OKE_CLUSTER_OCID>" \
  --file "<KUBECONFIG_PATH>" \
  --region "<REGION>" \
  --token-version 2.0.0 \
  --kube-endpoint "LEGACY_KUBERNETES|PUBLIC_ENDPOINT|PRIVATE_ENDPOINT|VCN_HOSTNAME"
kubectl version
kubectl get nodes
kubectl auth can-i --list
```

Keep `kubectl` within one minor version of the API server. When MFA is required,
bind the correct `OCI_CLI_PROFILE` and security-token authentication to the
kubeconfig exec plugin; `Unauthorized` can be an MFA/profile issue as well as
Kubernetes RBAC. Validate the installed CLI shape before publishing an exact
command because older runbooks often omit `LEGACY_KUBERNETES` and
`VCN_HOSTNAME`:

```bash
python3 scripts/oci_cli_help.py --json ce cluster create-kubeconfig
```

## Enhanced-cluster add-on checks

Enhanced clusters can use Oracle-managed cluster add-ons. Before installing a
standalone controller, changing an add-on, or attributing a controller failure
to a workload, establish the current cluster and add-on state with read-only
calls:

```bash
oci_cli ce cluster list-addons --cluster-id "<OKE_CLUSTER_OCID>"
oci_cli ce cluster get-addon \
  --cluster-id "<OKE_CLUSTER_OCID>" \
  --addon-name "<ADDON_NAME>"
```

Record only the sanitized enabled state, selected version, automatic-update
choice, and approved configuration. Confirm the cluster is enhanced, the
version is supported, and no standalone controller or webhook owns the same
responsibility. Treat `oci_cli ce cluster install-addon` and any disable/update
operation as a shared-cluster mutation: review the exact configuration, obtain
explicit target-bound approval, and verify controller plus application
readiness. A deprecated add-on version is a rollback exception, not a routine
target.

## Deployment baseline

Recommended order for a portable OKE workload:

1. Resolve profile, region, compartment, cluster, and namespace.
2. Build and push a `linux/amd64` image when targeting OCI-managed amd64 nodes.
3. Verify the target namespace can pull from OCIR.
4. Preview namespace, service account, RBAC, configmaps, secrets/ExternalSecrets,
   deployment, service, ingress, and network policy changes, get explicit user
   confirmation of the diff, then apply:

```bash
kubectl diff -f <manifest-dir>/ || true          # or: kubectl apply --dry-run=server -f <manifest-dir>/
# ^ review the printed diff with the user before proceeding
kubectl apply -f <manifest-dir>/
```

5. Wait for rollout and inspect events:

```bash
kubectl -n "<NAMESPACE>" rollout status deployment/"<APP>" --timeout=240s
kubectl -n "<NAMESPACE>" get pods,svc,ingress -o wide
kubectl -n "<NAMESPACE>" describe deployment "<APP>"
kubectl -n "<NAMESPACE>" describe svc "<SERVICE>"
```

For image-only updates, preview the exact change, confirm, then apply:

```bash
kubectl -n "<NAMESPACE>" set image deployment/"<APP>" app="<IMAGE>:<TAG>" --dry-run=server -o yaml
# ^ show this to the user before running it for real
kubectl -n "<NAMESPACE>" set image deployment/"<APP>" app="<IMAGE>:<TAG>"
kubectl -n "<NAMESPACE>" rollout status deployment/"<APP>" --timeout=240s
```

This avoids strategic-merge conflicts where a previously patched env var leaves
both `value` and `valueFrom` on the same entry. `kubectl apply`/`set image` are
not wrapped by `run_action` (which only covers `oci_cli`), and — unlike
`kubectl delete`/`drain`/`cordon`/forced `replace`, which the destructive-command
hook now blocks mechanically — they are routine updates the hook does not treat
as destructive, so the dry-run-then-confirm sequence above is their only gate.
Never skip it.

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

## OCI Native Ingress Controller

Use the OCI Native Ingress Controller either as an enhanced-cluster add-on or
as a standalone controller, not both for the same ingress class. A healthy
controller pod is not evidence that its OCI load balancer, listener, backend,
or route has converged.

For a failed route, inspect the controller before changing network resources:

```bash
kubectl get pods -n native-ingress-controller-system \
  --selector='app.kubernetes.io/name in (oci-native-ingress-controller)' -o wide
kubectl -n native-ingress-controller-system logs "<LEADER_POD>" \
  | grep -i 'validation failure'
kubectl -n "<NAMESPACE>" describe ingress "<INGRESS_NAME>"
kubectl -n "<NAMESPACE>" get endpoints "<SERVICE_NAME>" -o wide
```

When pods can start before the OCI load balancer recognizes a healthy backend,
use the native controller's readiness gate and a dedicated probe-safe health
path. Do not weaken health checks merely to clear a transient backend
`CRITICAL` state. Reusing a load balancer, preserving one after
`IngressClass` deletion, or attaching WAF/NSGs changes a shared edge and
requires normal target-bound approval.

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
2. Generate a fresh token-version `2.0.0` kubeconfig with the exact endpoint
   mode that exists and is reachable: `PUBLIC_ENDPOINT`, `PRIVATE_ENDPOINT`,
   `VCN_HOSTNAME`, or `LEGACY_KUBERNETES`.
3. For legacy clusters, also try `create-kubeconfig` without `--kube-endpoint`
   when the CLI/docs for that environment recommend the original endpoint.
4. For private clusters, run from OCI Cloud Shell, a bastion, or a configured
   tunnel that can reach the private API endpoint.
5. Re-run `kubectl auth can-i --list`; kubeconfig creation does not prove RBAC.

## OKE control-plane and RBAC readiness

Treat a failed Kubernetes API call as an OKE/control-plane reachability problem
until you prove otherwise. Do not infer application readiness, failed rollout,
or missing app permission from `kubectl` timeouts alone.

Readiness ladder:

```bash
oci_cli ce cluster get --cluster-id "<OKE_CLUSTER_OCID>" \
  --query 'data.{name:name,state:"lifecycle-state",endpoint:"endpoints.kubernetes"}'
kubectl --request-timeout=10s cluster-info
kubectl --request-timeout=10s get --raw=/readyz
kubectl auth can-i get pods -n "<NAMESPACE>"
kubectl auth can-i patch deployments -n "<NAMESPACE>"
```

If `cluster get` is healthy but `kubectl` cannot reach `/readyz`, resolve the
API endpoint mode next: public endpoint, private endpoint from an in-VCN host,
Cloud Shell, or a bounded Bastion tunnel. If `/readyz` works but `auth can-i`
fails, this is Kubernetes RBAC, not IAM token minting. Fix only the smallest
namespace/service-account binding needed for the operation.

For deployment canaries and evaluator jobs, prefer a non-root service account,
namespace-scoped RBAC, `activeDeadlineSeconds`, `ttlSecondsAfterFinished`, and a
post-run check that no active or retained Jobs remain:

```bash
kubectl -n "<NAMESPACE>" get jobs \
  --field-selector=status.successful!=1 -o wide
kubectl -n "<NAMESPACE>" get pods -l job-name="<JOB_NAME>" -o wide
```

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

For application debugging on virtual nodes, use `kubectl proxy` rather than
`kubectl port-forward`. Keep the proxy local, obtain the endpoint path from the
Kubernetes API object rather than guessing it, and stop it when investigation is
complete. This is an inspection path, not evidence that an ingress or OCI load
balancer route works.

## Workload identities

Workload identities are available only on enhanced clusters. They grant OCI
resource access to a workload by its Kubernetes namespace and service account;
they do not replace Kubernetes RBAC or image-pull authentication. They are not
dynamic groups: IAM policy conditions match the workload principal attributes
such as cluster, namespace, and service account, and the application must use an
OCI SDK provider that supports OKE Workload Identity.

Prove each boundary independently before relying on one:

1. The cluster is enhanced and the workload uses the intended service account.
2. Kubernetes RBAC allows only the required in-cluster actions.
3. OCI IAM policy grants the workload identity only the required resource
   permissions in the intended compartment.

Use a redacted service-account inspection and IAM policy review as configured
evidence; use the workload outcome and OCI Audit records as runtime evidence.
Do not substitute a node instance principal or an OCIR `imagePullSecret` for a
workload identity.

For customer-demo apps, browser users should not carry OCI credentials. The app
pod should use OKE Workload Identity or an approved instance-principal path to
read the required OCI services. Keep user-facing endpoints role-gated: signed-in
demo users may call app-specific read/chat APIs, while privileged mutations,
security execution, deployments, and Log Analytics writes remain admin-gated.

Minimum verification:

```bash
kubectl -n "<NAMESPACE>" get serviceaccount "<SERVICE_ACCOUNT>" -o yaml
kubectl -n "<NAMESPACE>" describe pod -l app="<APP>"
kubectl -n "<NAMESPACE>" exec deploy/"<APP>" -- env | grep '^OCI_RESOURCE_PRINCIPAL\|^OCI_CONFIG_PROFILE' || true
```

For a managed-node instance-principal design, add a narrow in-pod CLI probe:

```bash
kubectl -n "<NAMESPACE>" exec deploy/"<APP>" -- \
  oci iam region list --auth instance_principal --output table
```

Use `--auth instance_principal` only after confirming the target runtime really
has the required metadata/resource-principal environment. For OKE Workload
Identity, verify the service-account binding, workload-principal IAM policy,
SDK provider path, and OCI Audit records before blaming application code. Do
not copy kubeconfigs, user config files, API keys, wallets, or browser cookies
into a pod to "make the demo work."

## Runtime-principal readiness for app agents

When a customer-demo agent is signed in but returns `A privileged role is
required`, separate four identities before changing anything:

1. Browser user and route authorization.
2. Kubernetes service account and namespace RBAC.
3. OCI runtime principal: OKE Workload Identity or the intended managed-node
   instance-principal path.
4. OCI IAM policy scope for the service family being queried.

Generate the offline command ladder first:

```bash
python3 scripts/oci_oke_demo_troubleshoot.py runtime-principal-readiness --context "<NAMED_CONTEXT>" --pretty
```

Then collect current read-only evidence:

```bash
kubectl --request-timeout=10s get --raw=/readyz
kubectl -n "<NAMESPACE>" get deployment "<APP>" \
  -o jsonpath='{.spec.template.spec.serviceAccountName}'
kubectl -n "<NAMESPACE>" get serviceaccount "<SERVICE_ACCOUNT>" -o yaml
kubectl -n "<NAMESPACE>" auth can-i get pods \
  --as=system:serviceaccount:"<NAMESPACE>":"<SERVICE_ACCOUNT>"
kubectl -n "<NAMESPACE>" logs deployment/"<APP>" \
  --since=30m --all-containers --tail=200
```

Only when the workload is designed to use instance principals, run a narrow
in-pod provider probe. Prefer a read that lists a public tenancy-wide catalog or
the smallest required service read; never probe with a mutation.

```bash
kubectl -n "<NAMESPACE>" exec deploy/"<APP>" -- \
  oci iam region list --auth instance_principal --output table
```

For Workload Identity, use the service-account binding, workload-principal IAM
policy, SDK canary/read path, and OCI Audit records as the evidence path
instead of assuming the node instance principal applies to the pod. A successful
image pull proves OCIR authorization only; it does not prove Log Analytics,
Monitoring, Cloud Guard, APM, or Networking read access.

If the runtime probe proves missing access, the remediation is a smallest-scope
read-only policy for the named instance-principal dynamic group or the workload
principal in the intended compartment. Preview any Deployment
service-account patch with server-side dry-run before rollout. Keep privileged
mutations, security execution, deployments, SOC actions, and Log Analytics
writes role-gated even for signed-in demo users.

## Network and node diagnosis

For control-plane, node registration, pod, DNS, or OCI load-balancer reachability
symptoms, run the cluster's pre-defined **Path analysis tests** before changing
an NSG, security list, route table, or gateway. The tests analyze configuration;
they do not send production traffic. Save only redacted JSON results when an
operator needs a before/after comparison.

Choose the smallest relevant category:

- **Cluster API:** API endpoint and control-plane paths.
- **Node:** managed-node registration and data-plane paths.
- **Pod:** pod-to-service/OCI paths, including VCN-native networking.
- **Load Balancer:** bidirectional OCI LB/NLB and backend paths.

If a managed node is not `Ready`, use the Worker Node Troubleshooting Guide or
OCI Run Command to invoke the pre-installed Node Doctor. Update it before use:

```bash
sudo /usr/local/bin/node-doctor.sh --update
```

Node Doctor is not supported on virtual nodes. Its diagnostic bundle can contain
host metadata; redact it before a support upload and retain the original only in
the approved support-evidence location. A transient `FileNotFoundError` does
not invalidate output if Node Doctor reaches its bundle-generation phase; update
the script and collect a fresh run before escalation.

## Upgrade readiness

An OKE upgrade has distinct control-plane, managed-node, and virtual-node
effects. Do not begin until the target and blast radius are explicitly approved.

1. Inventory the control plane, each node pool's configured Kubernetes version,
   and the version actually running on each worker node. The control-plane
   upgrade validates both configured and running managed-node versions.
2. Confirm all workers are `Ready`, applications are tested on the target
   version, disruption budgets/capacity are sufficient, and relevant add-ons are
   compatible. Read the failed `CLUSTER_UPDATE` work request rather than
   guessing from a Console banner.
3. Upgrade the control plane first. It cannot be downgraded. Existing virtual
   nodes are upgraded with it.
4. Upgrade managed nodes by node-pool cycling only on enhanced clusters, or
   cycle the node pool after an explicit disruption review; use
   a reviewed out-of-place/replacement plan for basic clusters. Changing a node
   pool's version alone affects only nodes subsequently created.
5. Verify workload readiness, DNS/ingress/LB routes, autoscaling, and managed
   add-ons. Record this as target-specific operational evidence, not merely a
   successful work request.

Follow the Kubernetes version-skew policy and any required intermediate minor
upgrades. For Kubernetes 1.35 and later, prefer OKE worker images for managed
nodes instead of platform images.

## Enhanced cluster add-ons and native ingress

Enhanced clusters support managed essential and optional **cluster add-ons**.
Inventory and inspect them before changing resources that depend on an add-on:

```bash
oci_cli ce cluster list-addons --cluster-id "<OKE_CLUSTER_OCID>"
oci_cli ce cluster get-addon \
  --cluster-id "<OKE_CLUSTER_OCID>" \
  --addon-name "<ADDON_NAME>"
```

An add-on update is a reviewed operational change. Check the supported version,
approved configuration arguments, status, and associated work request. OKE
reconciliation can discard direct, undocumented Kubernetes changes.

Use workload identities only on enhanced clusters. Scope the Kubernetes service
account and OCI IAM policy to the workload's required resources; do not replace
that trust path with copied OCI credentials in a pod. Keep dynamic-group
language for instance-principal designs; workload principals use
workload-specific IAM policy conditions.

The OCI Native Ingress Controller can be managed as a cluster add-on. When an
OCI LB reports a backend failure, inspect controller validation errors,
IngressClass resources, Service endpoints, and the documented pod **readiness
gate** before manually changing LB resources.

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

## Remote builders and SSH-safe execution

When using a remote build/deploy host, avoid stale global SSH ControlMaster
sockets. Use invocation-owned sockets in `/tmp`, bounded liveness options, and
short polling commands instead of one long fragile session:

```bash
ssh -o BatchMode=yes \
  -o ConnectTimeout=10 \
  -o ServerAliveInterval=15 \
  -o ServerAliveCountMax=4 \
  -o ControlMaster=auto \
  -o ControlPersist=10m \
  -o ControlPath="/tmp/oci-skills-%r@%h:%p" \
  "<HOST_ALIAS>" "kubectl -n '<NAMESPACE>' rollout status deployment/'<APP>' --timeout=240s"
```

Do not run broad `ssh -O exit` commands against shared/global control paths.
If a transfer is needed, copy only reviewed source/test files required for the
remote validation, exclude `.git`, environment files, kubeconfigs, wallets, and
browser profiles, and avoid delete/sync flags unless the user approved the exact
remote directory and deletion scope.

## API-first fallback when SSH is blocked

Treat a blocked SSH alias, expired ControlMaster socket, or unavailable
`control-plane-oci` host as an operator-access problem, not as proof that the
OKE control plane, application, Log Analytics source, or OCI data path failed.
Keep moving with OCI APIs and supported in-VCN access paths:

```bash
oci_cli ce cluster get --cluster-id "<OKE_CLUSTER_OCID>" \
  --query 'data.{name:name,state:"lifecycle-state",endpoint:"endpoints.kubernetes"}'
python3 scripts/oci_cli_help.py --json ce work-request list
python3 scripts/oci_cli_help.py --json search resource structured-search
python3 scripts/oci_cli_help.py --json compute instance-agent command-execution list
```

Use Resource Search or service-specific `list/get` calls to rediscover target
resources by tag/display name, then validate lifecycle state with the owning
service API. For private API endpoints, prefer Cloud Shell, a reviewed Bastion
session, or OCI Run Command on an in-VCN managed instance over copying local OCI
configuration or opening broad network rules. Run Command proves command
delivery and output on a target instance; it does not prove an interactive SSH
path is healthy.

Evidence classification:

- `ssh timeout` / stale socket: remote operator path degraded.
- `ce cluster get` ACTIVE but `/readyz` unreachable: Kubernetes API endpoint
  network/RBAC path still unverified.
- `/readyz` reachable but `kubectl auth can-i` denied: Kubernetes RBAC gap.
- OCI API reads succeed while app source data is degraded: inspect Logging,
  Service Connector Hub, Log Analytics source/parser, and VCN Flow Log rows
  before changing network controls.

Never mark a release, demo, or investigation failed solely because one SSH path
is unavailable; record which alternate OCI evidence path was used and which
gate remains unverified.

For customer-demo incidents, hand the final answer a compact troubleshooting
receipt instead of a transcript. Combine this OKE/API ladder with the Log
Analytics receipt schema in `references/log-analytics.md`: OKE API status,
bounded `/readyz`, namespace RBAC, rollout/endpoints, runtime principal check,
Flow Log ingestion proof, source-IP OCL rows, trace reachability, Monitoring
summary, Cloud Guard/security rows, explicit coverage gaps, and a strict
conclusion level. If the OKE API, SSH host, or Log Analytics source is
unavailable, keep that as a source/path status and do not infer application or
network reachability.

Start from the redacted canonical receipt template rather than improvising a
new evidence schema:

```bash
python3 scripts/oci_oke_demo_troubleshoot.py receipt-template --context "<NAMED_CONTEXT>" --pretty
```

## Optional Kubernetes MCP read surface

Community Kubernetes MCP servers such as Flux159 `mcp-server-kubernetes` can be
useful when an agent runtime already speaks MCP and needs quick Kubernetes
inventory, describe, logs, explain, or API-resource discovery. MCP is not a
source of truth for this pack. Treat MCP output as convenience evidence to
verify through the context-proof and redaction workflow above.

Before connecting an OKE cluster to a Kubernetes MCP server:

- Prove the kube context, OCI exec profile, region, cluster identity, and RBAC
  with this reference's preflight commands. A current MCP context is only a
  label until verified.
- Prefer strict tool filtering: set `ALLOW_ONLY_READONLY_TOOLS=true`, or set
  `ALLOWED_TOOLS=kubectl_get,kubectl_describe,kubectl_logs,kubectl_context,explain_resource,list_api_resources,ping`.
- Treat `ALLOW_ONLY_NON_DESTRUCTIVE_TOOLS=true` as weaker than read-only. It can
  still leave create/update tools such as apply, create, scale, patch, rollout,
  and Helm install/upgrade available.
- Keep `MASK_SECRETS=true`. Secret masking usually covers `kubectl get secret`
  data fields only; logs, events, env dumps, rendered manifests, and arbitrary
  tool output can still leak sensitive values. Run shared output through
  `scripts/redact.py`.
- Do not expose `kubectl_generic`, `node_management`, `cleanup_pods`,
  `kubectl_delete`, `uninstall_helm_chart`, or equivalent cleanup/delete tools
  in production MCP sessions. Node drain, cleanup, and delete paths are
  operationally destructive even when framed as maintenance.
- If using an HTTP MCP transport, bind to localhost by default. For a remote
  endpoint, terminate TLS at an ingress/proxy, require header authentication,
  keep DNS rebinding protection enabled, and set the DNS rebinding allowlist to
  the public hostname clients actually use.
- OpenTelemetry on the MCP server is only an audit/debug signal for tool calls:
  tool name, duration, success/failure, Kubernetes context, and errors. Use
  sampling in shared environments and avoid OCIDs, tokens, IPs, or tenant names
  in resource attributes.

When an MCP read suggests a change, reproduce the finding with normal
`kubectl`, `helm`, or `oci_cli` commands and run the change through this pack.
Mutations still use this pack's preflight, `run_action`, redaction, and exact
approval gates.

For Helm chart issues, a safe review path is:

```bash
helm template "<RELEASE>" "<CHART>" \
  --namespace "<NAMESPACE>" \
  --values "<VALUES_FILE>" > "<RENDERED_MANIFEST>"

kubectl -n "<NAMESPACE>" diff -f "<RENDERED_MANIFEST>"
```

Use a Helm template review before apply when chart authentication, repository
access, CRDs, RBAC, namespace selection, or values provenance is uncertain.
Apply only after context proof and normal mutation approval.

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

For the recurring demo blockers, generate the current redacted command
plan before running live reads:

```bash
python3 scripts/oci_oke_demo_troubleshoot.py privileged-role --context "<NAMED_CONTEXT>" --pretty
python3 scripts/oci_oke_demo_troubleshoot.py connections-degraded --context "<NAMED_CONTEXT>" --pretty
python3 scripts/oci_oke_demo_troubleshoot.py control-plane-blocked --context "<NAMED_CONTEXT>" --pretty
python3 scripts/oci_oke_demo_troubleshoot.py melts-investigate-timeout --context "<NAMED_CONTEXT>" --pretty
python3 scripts/oci_oke_demo_troubleshoot.py oke-security-unavailable --context "<NAMED_CONTEXT>" --pretty
```

The helper is offline. It emits placeholders, stop conditions, and
approval-gated actions; it does not prove that any cluster, connector, or source
is healthy.

| Symptom | Likely cause | First checks |
|---|---|---|
| `kubectl Unauthorized` after kubeconfig | IAM token mint works, Kubernetes RBAC missing | `kubectl auth can-i --list`; ClusterRoleBinding |
| `Target endpoint is not available` | Forced wrong endpoint mode or private/legacy API endpoint | Try existing context; test `PUBLIC_ENDPOINT` / `PRIVATE_ENDPOINT` / `VCN_HOSTNAME` / `LEGACY_KUBERNETES`; use Cloud Shell/bastion |
| `OKE control plane is unavailable` | Cluster API endpoint unreachable, wrong endpoint mode, stale kubeconfig, or network path issue | `ce cluster get`; bounded `/readyz`; endpoint mode; Cloud Shell/bastion |
| `control-plane-oci` / SSH blocked | Operator access lane degraded, stale ControlMaster socket, host allowlist, or bastion path issue | OCI API `list/get`; Resource Search; Cloud Shell; Bastion; OCI Run Command |
| `A privileged role is required` in app agent | App route is over-gated or pod identity lacks required read-only OCI policy | API route policy; signed-in user role; service account; instance-principal dynamic group or workload-principal policy; IAM scope |
| MELTS investigation exceeded response-time budget | Provider/source query path is slow, partial, or unavailable; agent budget ended before evidence receipt was complete | Flow Log ingestion proof; source-IP OCL rows; trace, metric, and Cloud Guard source status; receipt conclusion level |
| OKE Security control plane unavailable | App security route, Kubernetes RBAC, runtime principal, or security provider read path is unavailable | OKE API `/readyz`; namespace `auth can-i`; service account; app logs; Cloud Guard/WAF/VSS read availability |
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
- Recent OKE demo operations: control-plane reachability before app readiness
  claims, namespace-scoped evaluator jobs, signed-in user route gates backed by
  instance-principal/Workload Identity access, and SSH-safe remote validation.

Keep future imports at this same abstraction level: reusable cause/fix pattern,
not project topology.

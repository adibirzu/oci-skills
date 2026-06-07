# OCI Administrator Knowledge Base

Known operational fixes. Search before deep debugging:

```bash
python3 scripts/kb_lookup.py "symptom words" [domain-tag]
```

Add a new `KB-<n>` entry whenever you resolve a new operational error.

---

## KB-001 — OKE kubectl Unauthorized right after create-kubeconfig (iam-oke)

**Symptom:** `kubectl` returns `Unauthorized` / "asked for credentials" immediately
after `oci ce cluster create-kubeconfig`.
**Root cause:** OKE has two authorization layers. The kubeconfig token mint
(IAM `manage cluster` / `use cluster`) is separate from in-cluster Kubernetes
RBAC. A token can be minted yet bound to no RBAC subject.
**Fix:** Ensure the caller's IAM principal maps to a Kubernetes RBAC subject
(a `ClusterRoleBinding` to the user/group OCID, or the `oci:` group mapping).
Verify with `kubectl auth can-i --list`.
**Status:** resolved.

## KB-002 — Identity Domains user filter returns nothing (iam)

**Symptom:** `identity-domains user list --filter "user-name eq \"x\""` returns empty
though the user exists.
**Root cause:** SCIM filters use camelCase attribute names; response fields are
kebab-case. The filter attribute was kebab-case.
**Fix:** Filter with `userName eq "x"` (camelCase). Read results as `user-name`.
**Status:** resolved.

## KB-003 — Service/quota limit exceeded on provision (iam-tenancy)

**Symptom:** Create call fails with `LimitExceeded` or capacity errors.
**Root cause:** Region/compartment has insufficient service-limit headroom.
**Fix:** Pre-check before provisioning:
`oci limits resource-availability get --service-name <svc> --limit-name <limit> --compartment-id <COMPARTMENT_OCID>`.
Request a limit increase or pick another AD/region if `available` is 0.
**Status:** resolved.

## KB-004 — WAF policy not blocking after attach (security)

**Symptom:** WAF policy created and attached to the load balancer but malicious
requests are not blocked.
**Root cause:** Policy attached but protection rules were left in `OBSERVE`
(detection) action rather than `BLOCK`, or the LB listener references a different
policy.
**Fix:** Set the protection-capability action to `BLOCK`, confirm the LB's WAF
association points at the intended policy OCID, and re-test.
**Status:** resolved.

## KB-005 — Vault secret base64 vs raw content (security)

**Symptom:** A secret read from Vault is garbled or fails to authenticate.
**Root cause:** `get_secret_bundle` returns base64-encoded content; it was used raw.
**Fix:** `base64.b64decode(bundle.secret_bundle_content.content).decode()` before use.
**Status:** resolved.

## KB-006 — Cross-tenancy OCIR pull fails on worker nodes (networking-compute)

**Symptom:** Pods stuck `ImagePullBackOff` pulling from `<region>.ocir.io/<ns>/...`
on an OKE cluster in a different tenancy than the registry.
**Root cause:** The image-pull secret (auth token for the registry tenancy) was
not replicated into the consuming cluster/namespace.
**Fix:** Create the docker-registry secret with a valid auth token for the
**registry** tenancy and reference it in `imagePullSecrets`.
**Status:** resolved.

## KB-007 — OCI CLI `--wait-for-state SUCCEEDED` hangs forever on FAILED jobs (cli)

**Symptom:** A `resource-manager` (ORM) destroy/apply or other async CLI call with `--wait-for-state SUCCEEDED --max-wait-seconds N` never returns; the process must be killed after tens of minutes.
**Root cause:** The CLI polls until state equals `SUCCEEDED` or max-wait expires. When the job enters a different terminal state (`FAILED`, `CANCELED`), `FAILED != SUCCEEDED`, so the CLI keeps polling for the entire window instead of exiting.
**Fix:** Drop `--wait-for-state SUCCEEDED` for operations that can legitimately fail. Fire the create/destroy, capture the job/work-request id, then poll `... job get --query 'data."lifecycle-state"'` and `break` on ALL terminal states (`SUCCEEDED`, `FAILED`, `CANCELED`).
**Status:** resolved.

## KB-008 — Async create returns a work request, not the resource (empty `data.id`) (cli)

**Symptom:** `oci <svc> <resource> create ... --query 'data.id'` returns empty for long-running services (APM domains, service connectors, DB systems, OKE clusters); scripts then fail with "could not resolve id".
**Root cause:** Creation of long-running resources is asynchronous and returns a work-request response whose payload has no `data.id`. Some create verbs (e.g. `sch service-connector create`) only return `opc-work-request-id`.
**Fix:** Treat create as fire-and-forget, then resolve the resource by polling `... list --display-name <name> --lifecycle-state ACTIVE --query 'data[0].id'` until it appears, or track the `opc-work-request-id` to completion.
**Status:** resolved.

## KB-009 — OCI profile selected from the wrong env var name (cli)

**Symptom:** All API calls authenticate as the wrong user/tenancy (or fall back to `DEFAULT`) even though a profile env var is exported; explicit `--profile <name>` works.
**Root cause:** Three names exist and tools disagree: `OCI_CLI_PROFILE` (CLI), `OCI_PROFILE`, and `OCI_CONFIG_PROFILE`. Code reading only one name silently defaults to `DEFAULT` when a different one is set.
**Fix:** Standardize on one name and have wrappers honor all three, e.g. `profile = OCI_PROFILE or OCI_CONFIG_PROFILE or OCI_CLI_PROFILE or "DEFAULT"`. Log the resolved profile at client init.
**Status:** resolved.

## KB-010 — CLI uses the profile's region and ignores `OCI_REGION` (cli)

**Symptom:** Calls hit the wrong region (e.g. the profile's home region) and return `NotAuthorizedOrNotFound` for resources that exist in another region.
**Root cause:** Passing only `--profile` makes the CLI use the `region=` line baked into `~/.oci/config`. The `OCI_REGION` env var is not automatically applied as `--region`.
**Fix:** In CLI wrappers, append `--region "$OCI_REGION"` whenever the env var is set, so it overrides the profile's built-in region.
**Status:** resolved.

## KB-011 — Session-token profiles fail with "user: missing from config" (cli)

**Symptom:** Every CLI call errors with `config file invalid` / `user: missing from config`, and OCID validation 404s, when the active profile was created by `oci session authenticate`.
**Root cause:** Wrappers default to API-key (`config`) auth, which expects `user`/`fingerprint`/`key_file`. Session profiles instead carry `security_token_file` and must be called with `--auth security_token`.
**Fix:** Auto-detect: if the resolved profile contains a `security_token_file` line, switch auth mode and call `oci ... --auth security_token --profile <name>`.
**Status:** resolved.

## KB-012 — SDK `list_*` returns a plain list, not an object with `.items` (cli)

**Symptom:** Python SDK inventory queries (compartments, instances, VCNs/subnets, buckets, autonomous DBs) return "no rows" even though resources exist and IAM is correct.
**Root cause:** For many services `response.data` is already a Python `list`; code reading `getattr(response.data, "items", [])` gets an empty list.
**Fix:** Normalize both shapes: `items = data if isinstance(data, list) else getattr(data, "items", [])`.
**Status:** resolved.

## KB-013 — OCI shell scripting breaks on macOS / Bash 3.2 (cli)

**Symptom:** Deploy scripts fail on macOS with `sed: command a expects \ followed by text`, literal `*_XXXXXX` temp files, `timeout: command not found`, or `<arr>[@]: unbound variable`.
**Root cause:** macOS ships BSD userland + Bash 3.2: BSD `sed -i` needs a backup-suffix arg (`-i ''`); `mktemp` requires the `XXXXXX` placeholder at the very end of the template; GNU `timeout` is absent; Bash 3.2 under `set -u` errors on empty-array expansion.
**Fix:** Use portable patterns — replace in-place `sed` with a Python regex rewrite; `mktemp "${TMPDIR:-/tmp}/name.XXXXXX"`; replace `timeout` with a `$SECONDS`-based until-loop; expand arrays as `"${arr[@]+"${arr[@]}"}"`.
**Status:** resolved.

## KB-014 — Pushing amd64 images to OCIR from Apple Silicon (cli)

**Symptom:** Containers `exec format error` / exit immediately on OCI VMs, or `docker push` to `<region>.ocir.io/<namespace>/` 403s on blob HEAD even after a successful `docker login`.
**Root cause:** Apple Silicon builds default to `linux/arm64` while OCI Compute is `linux/amd64`; and newer Docker clients negotiate OCIR auth/attestation manifests that OCIR's `/v2/` API rejects (login succeeds but pushes 403).
**Fix:** Build with `docker buildx build --platform linux/amd64`. If `docker login` to OCIR fails, write `~/.docker/config.json` directly with a base64 `<namespace>/<user>:<auth-token>` credential, or build/push from a native amd64 Linux host.
**Status:** resolved.

## KB-015 — `limits value list` must be queried against the tenancy root (iam-tenancy)

**Symptom:** `oci limits value list` for a service returns empty or errors when given a child-compartment OCID.
**Root cause:** Service limits are defined at the tenancy level. `limits value list` only accepts the root tenancy OCID; child compartments are valid only for `limits resource-availability get` (consumption/usage).
**Fix:** Query `limits value list` with the tenancy OCID; use the child compartment OCID only for `resource-availability get`.
**Status:** resolved.

## KB-016 — Identity Domains SCIM CLI: singular vs plural verbs (iam)

**Symptom:** `oci identity-domains user list` fails with `No such command 'list'`.
**Root cause:** The SCIM-based CLI splits collection vs resource operations: plural nouns (`users`, `groups`, `auth-tokens`) expose `list`/`search`; singular nouns (`user`, `group`, `auth-token`) expose `create`/`get`/`delete`/`patch`/`put`.
**Fix:** Use the plural form for list/search and the singular form for CRUD.
**Status:** resolved.

## KB-017 — Identity Domains user create requires a valid email and `--name` (iam)

**Symptom:** `InvalidValue: emails[0].value: Invalid email address format`, or create rejected for a missing name.
**Root cause:** SCIM validates emails against RFC 5322 (non-routable TLDs like `.local` are rejected) and requires the `--name` object.
**Fix:** Provide an RFC-compliant email (use an RFC 2606 reserved domain such as `example.com` for service accounts) and `--name '{"givenName":"...","familyName":"..."}'`.
**Status:** resolved.

## KB-018 — IAM policy group references: use `group id <OCID>`, unquoted (iam)

**Symptom:** Policy create fails with `InvalidParameter: No permissions found` when referencing a freshly created Identity Domain group by `'Domain'/'Group'` name.
**Root cause:** Named group references are subject to eventual-consistency resolution; a newly created group may not resolve immediately.
**Fix:** Reference the group by OCID: `Allow group id <GROUP_OCID> to ...`. Do not quote the OCID — `group id '<GROUP_OCID>'` fails to parse.
**Status:** resolved.

## KB-019 — IAM policy fails opaquely on deprecated resource-type names (iam)

**Symptom:** `InvalidParameter: No permissions found` on policy create, with no indication of which statement is wrong.
**Root cause:** OCI validates every statement in the batch; one invalid resource-type name fails the whole policy. Several names changed over time, e.g. `streaming-family`→`stream-family`, `log-analytics-family`→`loganalytics-resources-family`, `log-analytics-log-group`→`loganalytics-log-group`, `management-dashboards-family`→`management-dashboard-family`, OCIR `repository-family`→`repos`.
**Fix:** Use current resource-type names. To find the offending line, create/delete each statement individually.
**Status:** resolved.

## KB-020 — Identity Domains delete needs the SCIM id and `--force-delete` (iam)

**Symptom:** `identity-domains user delete --user-id <OCID> --force` fails.
**Root cause:** Identity Domains resources carry two ids — the SCIM `id` (32-char hex) used by SCIM endpoints, and the `ocid` used by legacy `oci iam`. The delete verb expects the SCIM `id` and uses the boolean `--force-delete true` (not the generic `--force`).
**Fix:** Capture the SCIM `id` at creation (`... users list --query "data.resources[?\"ocid\"=='<OCID>'].id | [0]"`) and call `... user delete --user-id <SCIM_ID> --force-delete true`.
**Status:** resolved.

## KB-021 — Dynamic group matching rules: use `instance.id`, and verify with `get` (iam)

**Symptom:** Instance principal returns `NotAuthorizedOrNotFound` on every call despite a correct-looking dynamic group and policy; and `iam dynamic-group list` shows `matching-rule: null`.
**Root cause:** The `ALL {resource.type='instance', resource.id='...'}` form is not reliably evaluated for instance-principal authorization. Separately, `ListDynamicGroups` omits the `matchingRule` field entirely — it only appears in `GetDynamicGroup`.
**Fix:** Use `ANY {instance.id = '<INSTANCE_OCID>'}` for the rule, and verify it with `iam dynamic-group get --dynamic-group-id <OCID>`, never via `list`.
**Status:** resolved.

## KB-022 — Auth tokens: 2 per user, write-once, and propagation delay (iam)

**Symptom:** `auth-token create` fails with "maximum quota limit of 2 has been reached"; or a freshly created token returns `Unauthorized` for ~1 minute.
**Root cause:** Each user is capped at 2 auth tokens, token values are unreadable after creation (only metadata is queryable), and new tokens take 30–60s to propagate.
**Fix:** Persist the token value at creation time (vault/secret). When the cap is hit and the stored value is lost, delete an existing token before creating a fresh one, then wait ~60s before first use.
**Status:** resolved.

## KB-023 — Autonomous DB create fails with quota / feature-not-enabled 409 (observability-db)

**Symptom:** ATP/ADB create fails with `QuotaExceeded: adb-free-count` (free tier) or `IncorrectState (409): feature is not currently enabled for this tenancy` (paid).
**Root cause:** The free-tier ADB allowance is a hard per-tenancy limit, and the paid Autonomous Database feature is not enabled in every tenancy.
**Fix:** Preflight with `oci limits resource-availability get --service-name database --limit-name adb-free-count --compartment-id <TENANCY_OCID>`. If free tier is exhausted, delete an unused ADB or use paid; if paid 409s, the feature must be enabled for the tenancy or use another tenancy.
**Status:** resolved.

## KB-024 — Resource-existence checks must filter `--lifecycle-state ACTIVE` (observability-db)

**Symptom:** A script "finds" an existing resource (e.g. an APM domain) and skips creation, then verification fails because the found resource is DELETED.
**Root cause:** Many `list` commands return all lifecycle states by default, including DELETED/DELETING.
**Fix:** Always add `--lifecycle-state ACTIVE` when listing to check for existence (APM domains, instances, VCNs, databases, etc.).
**Status:** resolved.

## KB-025 — APM shows zero traces because the OTLP endpoint URL is wrong (observability-db)

**Symptom:** App emits OpenTelemetry spans but APM shows 0 services/0 traces.
**Root cause:** The `OTLPSpanExporter` was pointed at the legacy REST path (`/20200101/observations/public-span?dataFormat=otlp&dataKey=...`) instead of the OTLP protocol endpoint, with the key in the query string.
**Fix:** Use `<apm-base>/20200101/opentelemetry/private/v1/traces` with an `Authorization: dataKey <private-data-key>` header (private key for server-side export), not the public-span URL.
**Status:** resolved.

## KB-026 — APM RUM shows no browser data (empty agent config in the page) (observability-db)

**Symptom:** No APM Browser/RUM data; the page ships with empty upload endpoint, public data key, and an empty agent `<script src="">`.
**Root cause:** Static HTML carries empty RUM placeholders and the server serves it verbatim without injecting real RUM credentials.
**Fix:** Inject the RUM upload endpoint, public data key, and the RUM agent script src from environment variables at serve time; verify the served HTML has non-empty values.
**Status:** resolved.

## KB-027 — Monitoring alarm creation fails on namespace case and inline JSON (observability-db)

**Symptom:** Custom-metric alarms fail to create in batch; or `--destinations` with `["ocid..."]` triggers shell glob/parse errors.
**Root cause:** Custom metric namespaces must match `^[a-z][a-z0-9_]*[a-z0-9]$` (no uppercase); and complex-type JSON passed inline lets the shell interpret `[` as a glob. `--pending-duration` is also required.
**Fix:** Use a lowercase namespace, pass complex JSON via `--destinations "file://$tmp.json"` (or a heredoc) instead of inline brackets, and include `--pending-duration PT5M`.
**Status:** resolved.

## KB-028 — Monitoring `PostMetricData` 404s on the default (read) endpoint (observability-db)

**Symptom:** Reads (`list_metrics`, `summarize_metrics_data`) work, but publishing metrics 404s with "Incorrect Telemetry endpoint... Use telemetry-ingestion...".
**Root cause:** Monitoring has separate read (`telemetry.<region>.oraclecloud.com`) and write (`telemetry-ingestion.<region>.oraclecloud.com`) endpoints; the SDK client defaults to the read endpoint.
**Fix:** Construct the client with `service_endpoint="https://telemetry-ingestion.<region>.oraclecloud.com"` for writes.
**Status:** resolved.

## KB-029 — Derive region from the target resource's OCID, not the profile default (observability-db)

**Symptom:** `NotAuthorizedOrNotFound` / cross-region failures when a script operates on a Log Analytics log group, stream, or events target that lives in a different region than the profile's home region.
**Root cause:** The region is encoded in the OCID (`ocid1.<type>.oc1.<region>.<id>`), but the script inherited `OCI_REGION` from the profile and called the wrong regional endpoint.
**Fix:** Parse the region segment out of the target resource OCID and set `OCI_REGION` accordingly before making regional API calls.
**Status:** resolved.

## KB-030 — OCI Streaming stream-pool pitfalls (observability-db)

**Symptom:** Stream create fails with `Stream pool ... is DELETED`, or `Cannot specify both compartment id and stream pool id`, or a Kafka Connect worker shows RUNNING but ingests nothing with `UNKNOWN_TOPIC_OR_PARTITION`.
**Root cause:** Stale stream-pool OCIDs from prior deploys persist in config; the create API rejects passing both `compartment_id` and `stream_pool_id`; and a Kafka client's SASL username `<tenancy>/<user>/<stream-pool-ocid>` binds it to exactly one pool, so it cannot see topics in another pool.
**Fix:** Validate the pool OCID is ACTIVE before use; when targeting a pool pass `stream_pool_id` without `compartment_id`; ensure every topic a Kafka Connect worker consumes lives in that worker's configured stream pool.
**Status:** resolved.

## KB-031 — Enable DB Management / Ops Insights on ADB via the native DB CLI (observability-db)

**Symptom:** `oci database-management ... enable-*-feature` fails on Autonomous DB with SSL-wallet/JSON-format errors ("Ssl wallet is required", "Unexpected character").
**Root cause:** The `database-management` service API expects an undocumented wallet-secret JSON format for mTLS ADB.
**Fix:** Use the native ADB verbs, which authenticate internally with no wallet/secret: `oci db autonomous-database enable-autonomous-database-management --autonomous-database-id <ADB_OCID>` and `... enable-operations-insights ...`.
**Status:** resolved.

## KB-032 — Data Safe `list_audit_events` rejects `time_started`/`time_ended` (observability-db)

**Symptom:** Audit-event queries fail with `list_audit_events got unknown kwargs: ['time_started','time_ended']`.
**Root cause:** The SDK's `list_audit_events` only supports time filtering through the `scim_query` parameter.
**Fix:** Build an RFC3339 window and pass it via `scim_query`, e.g. `(auditEventTime ge "<start>") and (auditEventTime le "<end>")`, with `sort_by="auditEventTime"`, `sort_order="DESC"`.
**Status:** resolved.

## KB-033 — Autonomous DB DSN must be a tnsnames alias, not the full service name (observability-db)

**Symptom:** App crashes on startup: `DPY-4000: unable to find "<prefix>_<db>_low" in tnsnames.ora`, even though the DSN matches the Console "Connection Strings" value.
**Root cause:** The Console shows the full low-level connect descriptor whose `service_name=` is `<tenancy-prefix>_<db>_low`, but `tnsnames.ora` in the wallet aliases it as the short lowercase `<db>_low`.
**Fix:** Set the DSN to the short alias (e.g. `<db>_low`); `oracledb` resolves it against `tnsnames.ora` in the wallet directory.
**Status:** resolved.

## KB-034 — `oracledb` thick-mode init fails without Instant Client; use thin mode (observability-db)

**Symptom:** `DPI-1047: Cannot locate a 64-bit Oracle Client library ... libclntsh.dylib` on a host without Oracle Instant Client (common on macOS).
**Root cause:** Code calls `oracledb.init_oracle_client()` unconditionally; thick mode requires the native client libs, but thin mode can connect to ADB with just the wallet.
**Fix:** Wrap `init_oracle_client()` in try/except and fall back to thin mode on failure instead of aborting.
**Status:** resolved.

## KB-035 — Monitoring a private OKE cluster without API-server access (iam-oke)

**Symptom:** The OKE monitoring/Terraform stack fails with `Resource precondition failed` / "OKE cluster is private" when the cluster has only a private endpoint.
**Root cause:** A "Full" deployment needs API-server reachability (public endpoint or an RMS private endpoint) to install the Helm chart.
**Fix:** Use the "Only OCI Resources" deployment option to create the OCI-side resources (Log Analytics entities, dashboards, service logs, agent keys) and install the Helm chart separately with kubectl/helm once you have cluster access.
**Status:** resolved.

## KB-036 — OKE node "register timeout" / "pod network configuration timeout" is networking (iam-oke)

**Symptom:** Cluster reaches ACTIVE but the node pool fails: "N node(s) register timeout" or "pod network configuration timeout".
**Root cause:** Worker nodes can't reach the control plane or pull images — almost always a missing NAT gateway, missing `0.0.0.0/0 → NAT` route on the worker/pod route tables, missing service gateway, or security rules blocking 6443/12250.
**Fix:** Ensure a NAT gateway plus `0.0.0.0/0 → NAT` routes on worker and pod subnets, a service gateway for OCI services, and security rules allowing the API-server ports. It is not a Terraform bug.
**Status:** resolved.

## KB-037 — `ReadWriteOnce` PVC with `replicas > 1` causes multi-attach errors (iam-oke)

**Symptom:** Pods stuck `Init`/`ContainerCreating` with `Multi-Attach error` / `FailedAttachVolume`; the service endpoint flaps.
**Root cause:** RWO block volumes can only attach to one node; multiple replicas across nodes cannot share them.
**Fix:** Keep `replicas=1` for RWO-backed deployments, or switch to a `ReadWriteMany` storage class (e.g. file-storage) if multiple replicas must share the volume.
**Status:** resolved.

## KB-038 — Cross-cluster PVC migration must strip source PV binding metadata (iam-oke)

**Symptom:** PVCs reapplied in a different OKE cluster end up `Lost` or bound to a non-existent PV.
**Root cause:** The source PVC manifest carries `spec.volumeName` and `pv.kubernetes.io/*` / `volume.kubernetes.io/*` bind annotations that reference a PV that doesn't exist in the target cluster.
**Fix:** Strip `spec.volumeName` and all bind/provisioner annotations (and selected-node hints) before applying, so the target CSI provisioner binds a fresh PVC/PV pair.
**Status:** resolved.

## KB-039 — Default OKE node boot volume runs out under load (disk-pressure evictions) (iam-oke)

**Symptom:** Pods `Pending` with `disk-pressure` taints, or running pods evicted for `ephemeral-storage`.
**Root cause:** The default node boot volume is exhausted by the image cache + node logs + container overlay FS, tripping kubelet's `nodefs.available<10%` eviction threshold.
**Fix:** Provision larger node boot volumes for image-heavy/multi-tenant workloads; short-term, lower pod CPU/ephemeral requests so pods fit on roomier nodes and let the cluster autoscaler add capacity.
**Status:** resolved.

## KB-040 — OKE virtual (serverless) nodes do not expose NodePorts (iam-oke)

**Symptom:** A `Service type=LoadBalancer` gets an EXTERNAL-IP but `curl` returns connection reset; LB backends stay CRITICAL; `kubectl exec`/`port-forward`/`logs --previous` fail with "not supported".
**Root cause:** Virtual nodes are serverless — no `kube-proxy`, no NodePorts, no node-level debug. The default LB→NodePort path is broken, though in-cluster ClusterIP routing still works.
**Fix:** Use a pod-IP-aware path: the OCI Native Ingress Controller, or nginx-ingress via Helm, or a NetworkLoadBalancer Service with IP-target backends — not the default NodePort LB.
**Status:** resolved.

## KB-041 — `create-kubeconfig` fails on clusters exposing only the legacy endpoint (iam-oke)

**Symptom:** `oci ce cluster create-kubeconfig` fails with `Invalid endpoint: Target endpoint is not available` on an ACTIVE cluster.
**Root cause:** The flow forced `PUBLIC_ENDPOINT`/`PRIVATE_ENDPOINT`, but some clusters expose only the legacy `endpoints.kubernetes` and lack the VCN-native endpoint fields.
**Fix:** Probe endpoint types and fall back across `PUBLIC_ENDPOINT` → `PRIVATE_ENDPOINT` → `VCN_HOSTNAME` → `LEGACY_KUBERNETES`.
**Status:** resolved.

## KB-042 — A new VCN's default route table is empty (no automatic IGW route) (networking-compute)

**Symptom:** VMs in a "public" subnet have public IPs but are unreachable; cloud-init times out downloading packages; SSH connection times out.
**Root cause:** OCI does not auto-add an internet route. The default route table starts empty, so creating an Internet/NAT gateway alone routes nothing.
**Fix:** Add `0.0.0.0/0 → IGW` to the public subnet's route table and `0.0.0.0/0 → NAT` to a private route table, and assign those route tables to the subnets.
**Status:** resolved.

## KB-043 — VCN/subnet deletion blocked by route rules and attached VNICs (networking-compute)

**Symptom:** VCN/subnet teardown fails with 409 conflicts; route tables, LPGs, gateways, or subnets can't be deleted.
**Root cause:** OCI refuses to delete anything still referenced by a route rule (gateways/LPGs as `network-entity-id`) or any subnet that still has attached VNICs (including service private-endpoints, mount targets, or load balancers).
**Fix:** Clear all route-table rules first, then delete LPGs, then mount targets/LBs and any service resources that own private-endpoint VNICs, then subnets, then gateways, then route tables.
**Status:** resolved.

## KB-044 — ICMP is blocked by default; don't treat `ping` failure as "VM down" (networking-compute)

**Symptom:** `ping <vm>` is 100% loss and SSH is intermittently timing out, making the host look dead.
**Root cause:** OCI security rules don't permit ICMP by default, so ping always fails regardless of host health; intermittent SSH is usually rate-limiting/fail2ban or transient routing, not an outage.
**Fix:** Don't rely on ICMP for liveness. When SSH is flaky, run commands out-of-band via the Instance Agent: `oci compute instance-agent command create --instance-id <OCID> --content '{"source":{"sourceType":"TEXT","text":"<cmd>"}}' ...`. Add ICMP rules explicitly if ping is needed.
**Status:** resolved.

## KB-045 — Avoid `0.0.0.0/0` ingress on SSH/management ports (security)

**Symptom:** NSGs and security lists expose SSH and management ports (22, app/admin ports) to the entire internet.
**Root cause:** Rules default to or are left at `0.0.0.0/0` instead of being scoped to the operator's address.
**Fix:** Restrict management-port ingress to a specific `/32` (or a known admin CIDR) via a variable like `ALLOWED_INGRESS_CIDR`; never default management ports to `0.0.0.0/0`. Re-scope when the operator's egress IP changes.
**Status:** resolved.

## KB-046 — Vault automation: ensure the vault/key exist and wait out `CREATING` (security)

**Symptom:** Secret writes spam `NotAuthorizedOrNotFound` (stale/deleted vault or key OCID), or a just-created secret can't be found by name immediately after creation.
**Root cause:** Automation writes secrets against existing OCIDs without validating them, and KMS vault/secret creation is asynchronous — a secret in `CREATING` is invisible to a list filtered on `ACTIVE`.
**Fix:** Before writing secrets, validate-or-(re)create the vault and master key and persist their OCIDs. After creating a secret, resolve it by name across non-deleted states and poll `vault secret get` until `ACTIVE`.
**Status:** resolved.

## KB-047 — Usage/Cost API access is policy-gated and tenancy-scoped (cost)

**Symptom:** Cost/Usage API checks fail ("Check permissions/service limits") even though budgets were created successfully.
**Root cause:** Usage API access depends on tenancy-level policy grants for the calling principal and is independent of budget provisioning; it is queried at tenant scope.
**Fix:** Treat Usage API checks as warn-only unless the calling principal is explicitly granted `read usage-report in tenancy`; gate strict behavior behind an opt-in flag.
**Status:** resolved.

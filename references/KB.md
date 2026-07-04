# OCI Administrator Knowledge Base

Known operational fixes. Search before deep debugging:

```bash
python3 scripts/kb_lookup.py "symptom words" [domain-tag]
```

Add a new `KB-<n>` entry whenever you resolve a new operational error. Each
entry carries a `**See:**` link to the authoritative Oracle doc that backs the
fix (an Open Knowledge Format *citation*) — prefer a URL already in
[oracle-docs.md](oracle-docs.md).

Entry shape: `## KB-<n> — <title> (<domain-tag>)`, then `**Symptom:**`,
`**Root cause:**`, `**Fix:**`, `**See:**`, `**Status:**`.

**Adding KB mined from a real project or tenancy?** Follow
[kb-ingestion.md](kb-ingestion.md) first — the sanitize-by-construction contract:
distill the pattern, replace every tenant specific (OCIDs, IPs, namespaces, keys,
**and** the compartment/cluster/MQL names the gate can't catch) with
`<PLACEHOLDER>` tokens, then run `scripts/redact.py --check`.

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
**See:** [OKE access control](https://docs.oracle.com/en-us/iaas/Content/ContEng/Concepts/contengaboutaccesscontrol.htm)
**Status:** resolved.

## KB-002 — Identity Domains user filter returns nothing (iam)

**Symptom:** `identity-domains user list --filter "user-name eq \"x\""` returns empty
though the user exists.
**Root cause:** SCIM filters use camelCase attribute names; response fields are
kebab-case. The filter attribute was kebab-case.
**Fix:** Filter with `userName eq "x"` (camelCase). Read results as `user-name`.
**See:** [Identity Domains](https://docs.oracle.com/en-us/iaas/Content/Identity/domains/overview.htm)
**Status:** resolved.

## KB-003 — Service/quota limit exceeded on provision (iam-tenancy)

**Symptom:** Create call fails with `LimitExceeded` or capacity errors.
**Root cause:** Region/compartment has insufficient service-limit headroom.
**Fix:** Pre-check before provisioning:
`oci limits resource-availability get --service-name <svc> --limit-name <limit> --compartment-id <COMPARTMENT_OCID>`.
Request a limit increase or pick another AD/region if `available` is 0.
**See:** [Service Limits — request an increase](https://docs.oracle.com/en-us/iaas/Content/General/Concepts/servicelimits.htm)
**Status:** resolved.

## KB-004 — WAF policy not blocking after attach (security)

**Symptom:** WAF policy created and attached to the load balancer but malicious
requests are not blocked.
**Root cause:** Policy attached but protection rules were left in `OBSERVE`
(detection) action rather than `BLOCK`, or the LB listener references a different
policy.
**Fix:** Set the protection-capability action to `BLOCK`, confirm the LB's WAF
association points at the intended policy OCID, and re-test.
**See:** [WAF concepts](https://docs.oracle.com/en-us/iaas/Content/WAF/Concepts/overview.htm)
**Status:** resolved.

## KB-005 — Vault secret base64 vs raw content (security)

**Symptom:** A secret read from Vault is garbled or fails to authenticate.
**Root cause:** `get_secret_bundle` returns base64-encoded content; it was used raw.
**Fix:** `base64.b64decode(bundle.secret_bundle_content.content).decode()` before use.
**See:** [Managing Vault secrets](https://docs.oracle.com/en-us/iaas/Content/KeyManagement/Tasks/managingsecrets.htm)
**Status:** resolved.

## KB-006 — Cross-tenancy OCIR pull fails on worker nodes (networking-compute)

**Symptom:** Pods stuck `ImagePullBackOff` pulling from `<region>.ocir.io/<ns>/...`
on an OKE cluster in a different tenancy than the registry.
**Root cause:** The image-pull secret (auth token for the registry tenancy) was
not replicated into the consuming cluster/namespace.
**Fix:** Create the docker-registry secret with a valid auth token for the
**registry** tenancy and reference it in `imagePullSecrets`.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-007 — OCI CLI `--wait-for-state SUCCEEDED` hangs forever on FAILED jobs (cli)

**Symptom:** A `resource-manager` (ORM) destroy/apply or other async CLI call with `--wait-for-state SUCCEEDED --max-wait-seconds N` never returns; the process must be killed after tens of minutes.
**Root cause:** The CLI polls until state equals `SUCCEEDED` or max-wait expires. When the job enters a different terminal state (`FAILED`, `CANCELED`), `FAILED != SUCCEEDED`, so the CLI keeps polling for the entire window instead of exiting.
**Fix:** Drop `--wait-for-state SUCCEEDED` for operations that can legitimately fail. Fire the create/destroy, capture the job/work-request id, then poll `... job get --query 'data."lifecycle-state"'` and `break` on ALL terminal states (`SUCCEEDED`, `FAILED`, `CANCELED`).
**See:** [Resource Manager jobs](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Tasks/usingconsole.htm)
**Status:** resolved.

## KB-008 — Async create returns a work request, not the resource (empty `data.id`) (cli)

**Symptom:** `oci <svc> <resource> create ... --query 'data.id'` returns empty for long-running services (APM domains, service connectors, DB systems, OKE clusters); scripts then fail with "could not resolve id".
**Root cause:** Creation of long-running resources is asynchronous and returns a work-request response whose payload has no `data.id`. Some create verbs (e.g. `sch service-connector create`) only return `opc-work-request-id`.
**Fix:** Treat create as fire-and-forget, then resolve the resource by polling `... list --display-name <name> --lifecycle-state ACTIVE --query 'data[0].id'` until it appears, or track the `opc-work-request-id` to completion.
**See:** [Work requests](https://docs.oracle.com/en-us/iaas/Content/General/Concepts/workrequestoverview.htm)
**Status:** resolved.

## KB-009 — OCI profile selected from the wrong env var name (cli)

**Symptom:** All API calls authenticate as the wrong user/tenancy (or fall back to `DEFAULT`) even though a profile env var is exported; explicit `--profile <name>` works.
**Root cause:** Three names exist and tools disagree: `OCI_CLI_PROFILE` (CLI), `OCI_PROFILE`, and `OCI_CONFIG_PROFILE`. Code reading only one name silently defaults to `DEFAULT` when a different one is set.
**Fix:** Standardize on one name and have wrappers honor all three, e.g. `profile = OCI_PROFILE or OCI_CONFIG_PROFILE or OCI_CLI_PROFILE or "DEFAULT"`. Log the resolved profile at client init.
**See:** [SDK & CLI configuration](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
**Status:** resolved.

## KB-010 — CLI uses the profile's region and ignores `OCI_REGION` (cli)

**Symptom:** Calls hit the wrong region (e.g. the profile's home region) and return `NotAuthorizedOrNotFound` for resources that exist in another region.
**Root cause:** Passing only `--profile` makes the CLI use the `region=` line baked into `~/.oci/config`. The `OCI_REGION` env var is not automatically applied as `--region`.
**Fix:** In CLI wrappers, append `--region "$OCI_REGION"` whenever the env var is set, so it overrides the profile's built-in region.
**See:** [SDK & CLI configuration](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
**Status:** resolved.

## KB-011 — Session-token profiles fail with "user: missing from config" (cli)

**Symptom:** Every CLI call errors with `config file invalid` / `user: missing from config`, and OCID validation 404s, when the active profile was created by `oci session authenticate`.
**Root cause:** Wrappers default to API-key (`config`) auth, which expects `user`/`fingerprint`/`key_file`. Session profiles instead carry `security_token_file` and must be called with `--auth security_token`.
**Fix:** Auto-detect: if the resolved profile contains a `security_token_file` line, switch auth mode and call `oci ... --auth security_token --profile <name>`.
**See:** [SDK & CLI configuration](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
**Status:** resolved.

## KB-012 — SDK `list_*` returns a plain list, not an object with `.items` (cli)

**Symptom:** Python SDK inventory queries (compartments, instances, VCNs/subnets, buckets, autonomous DBs) return "no rows" even though resources exist and IAM is correct.
**Root cause:** For many services `response.data` is already a Python `list`; code reading `getattr(response.data, "items", [])` gets an empty list.
**Fix:** Normalize both shapes: `items = data if isinstance(data, list) else getattr(data, "items", [])`.
**See:** [SDK & CLI configuration](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
**Status:** resolved.

## KB-013 — OCI shell scripting breaks on macOS / Bash 3.2 (cli)

**Symptom:** Deploy scripts fail on macOS with `sed: command a expects \ followed by text`, literal `*_XXXXXX` temp files, `timeout: command not found`, or `<arr>[@]: unbound variable`.
**Root cause:** macOS ships BSD userland + Bash 3.2: BSD `sed -i` needs a backup-suffix arg (`-i ''`); `mktemp` requires the `XXXXXX` placeholder at the very end of the template; GNU `timeout` is absent; Bash 3.2 under `set -u` errors on empty-array expansion.
**Fix:** Use portable patterns — replace in-place `sed` with a Python regex rewrite; `mktemp "${TMPDIR:-/tmp}/name.XXXXXX"`; replace `timeout` with a `$SECONDS`-based until-loop; expand arrays as `"${arr[@]+"${arr[@]}"}"`.
**See:** [OCI CLI command reference](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/)
**Status:** resolved.

## KB-014 — Pushing amd64 images to OCIR from Apple Silicon (cli)

**Symptom:** Containers `exec format error` / exit immediately on OCI VMs, or `docker push` to `<region>.ocir.io/<namespace>/` 403s on blob HEAD even after a successful `docker login`.
**Root cause:** Apple Silicon builds default to `linux/arm64` while OCI Compute is `linux/amd64`; and newer Docker clients negotiate OCIR auth/attestation manifests that OCIR's `/v2/` API rejects (login succeeds but pushes 403).
**Fix:** Build with `docker buildx build --platform linux/amd64`. If `docker login` to OCIR fails, write `~/.docker/config.json` directly with a base64 `<namespace>/<user>:<auth-token>` credential, or build/push from a native amd64 Linux host.
**See:** [Container Registry](https://docs.oracle.com/en-us/iaas/Content/Registry/home.htm)
**Status:** resolved.

## KB-015 — `limits value list` must be queried against the tenancy root (iam-tenancy)

**Symptom:** `oci limits value list` for a service returns empty or errors when given a child-compartment OCID.
**Root cause:** Service limits are defined at the tenancy level. `limits value list` only accepts the root tenancy OCID; child compartments are valid only for `limits resource-availability get` (consumption/usage).
**Fix:** Query `limits value list` with the tenancy OCID; use the child compartment OCID only for `resource-availability get`.
**See:** [Service Limits](https://docs.oracle.com/en-us/iaas/Content/General/service-limits/overview.htm)
**Status:** resolved.

## KB-016 — Identity Domains SCIM CLI: singular vs plural verbs (iam)

**Symptom:** `oci identity-domains user list` fails with `No such command 'list'`.
**Root cause:** The SCIM-based CLI splits collection vs resource operations: plural nouns (`users`, `groups`, `auth-tokens`) expose `list`/`search`; singular nouns (`user`, `group`, `auth-token`) expose `create`/`get`/`delete`/`patch`/`put`.
**Fix:** Use the plural form for list/search and the singular form for CRUD.
**See:** [Identity Domains](https://docs.oracle.com/en-us/iaas/Content/Identity/domains/overview.htm)
**Status:** resolved.

## KB-017 — Identity Domains user create requires a valid email and `--name` (iam)

**Symptom:** `InvalidValue: emails[0].value: Invalid email address format`, or create rejected for a missing name.
**Root cause:** SCIM validates emails against RFC 5322 (non-routable TLDs like `.local` are rejected) and requires the `--name` object.
**Fix:** Provide an RFC-compliant email (use an RFC 2606 reserved domain such as `example.com` for service accounts) and `--name '{"givenName":"...","familyName":"..."}'`.
**See:** [Identity Domains](https://docs.oracle.com/en-us/iaas/Content/Identity/domains/overview.htm)
**Status:** resolved.

## KB-018 — IAM policy group references: use `group id <OCID>`, unquoted (iam)

**Symptom:** Policy create fails with `InvalidParameter: No permissions found` when referencing a freshly created Identity Domain group by `'Domain'/'Group'` name.
**Root cause:** Named group references are subject to eventual-consistency resolution; a newly created group may not resolve immediately.
**Fix:** Reference the group by OCID: `Allow group id <GROUP_OCID> to ...`. Do not quote the OCID — `group id '<GROUP_OCID>'` fails to parse.
**See:** [IAM](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm)
**Status:** resolved.

## KB-019 — IAM policy fails opaquely on deprecated resource-type names (iam)

**Symptom:** `InvalidParameter: No permissions found` on policy create, with no indication of which statement is wrong.
**Root cause:** OCI validates every statement in the batch; one invalid resource-type name fails the whole policy. Several names changed over time, e.g. `streaming-family`→`stream-family`, `log-analytics-family`→`loganalytics-resources-family`, `log-analytics-log-group`→`loganalytics-log-group`, `management-dashboards-family`→`management-dashboard-family`, OCIR `repository-family`→`repos`.
**Fix:** Use current resource-type names. To find the offending line, create/delete each statement individually.
**See:** [IAM](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm)
**Status:** resolved.

## KB-020 — Identity Domains delete needs the SCIM id and `--force-delete` (iam)

**Symptom:** `identity-domains user delete --user-id <OCID> --force` fails.
**Root cause:** Identity Domains resources carry two ids — the SCIM `id` (32-char hex) used by SCIM endpoints, and the `ocid` used by legacy `oci iam`. The delete verb expects the SCIM `id` and uses the boolean `--force-delete true` (not the generic `--force`).
**Fix:** Capture the SCIM `id` at creation (`... users list --query "data.resources[?\"ocid\"=='<OCID>'].id | [0]"`) and call `... user delete --user-id <SCIM_ID> --force-delete true`.
**See:** [Identity Domains](https://docs.oracle.com/en-us/iaas/Content/Identity/domains/overview.htm)
**Status:** resolved.

## KB-021 — Dynamic group matching rules: use `instance.id`, and verify with `get` (iam)

**Symptom:** Instance principal returns `NotAuthorizedOrNotFound` on every call despite a correct-looking dynamic group and policy; and `iam dynamic-group list` shows `matching-rule: null`.
**Root cause:** The `ALL {resource.type='instance', resource.id='...'}` form is not reliably evaluated for instance-principal authorization. Separately, `ListDynamicGroups` omits the `matchingRule` field entirely — it only appears in `GetDynamicGroup`.
**Fix:** Use `ANY {instance.id = '<INSTANCE_OCID>'}` for the rule, and verify it with `iam dynamic-group get --dynamic-group-id <OCID>`, never via `list`.
**See:** [Managing dynamic groups](https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/managingdynamicgroups.htm)
**Status:** resolved.

## KB-022 — Auth tokens: 2 per user, write-once, and propagation delay (iam)

**Symptom:** `auth-token create` fails with "maximum quota limit of 2 has been reached"; or a freshly created token returns `Unauthorized` for ~1 minute.
**Root cause:** Each user is capped at 2 auth tokens, token values are unreadable after creation (only metadata is queryable), and new tokens take 30–60s to propagate.
**Fix:** Persist the token value at creation time (vault/secret). When the cap is hit and the stored value is lost, delete an existing token before creating a fresh one, then wait ~60s before first use.
**See:** [IAM](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm)
**Status:** resolved.

## KB-023 — Autonomous DB create fails with quota / feature-not-enabled 409 (observability-db)

**Symptom:** ATP/ADB create fails with `QuotaExceeded: adb-free-count` (free tier) or `IncorrectState (409): feature is not currently enabled for this tenancy` (paid).
**Root cause:** The free-tier ADB allowance is a hard per-tenancy limit, and the paid Autonomous Database feature is not enabled in every tenancy.
**Fix:** Preflight with `oci limits resource-availability get --service-name database --limit-name adb-free-count --compartment-id <TENANCY_OCID>`. If free tier is exhausted, delete an unused ADB or use paid; if paid 409s, the feature must be enabled for the tenancy or use another tenancy.
**See:** [Service Limits](https://docs.oracle.com/en-us/iaas/Content/General/service-limits/overview.htm)
**Status:** resolved.

## KB-024 — Resource-existence checks must filter `--lifecycle-state ACTIVE` (observability-db)

**Symptom:** A script "finds" an existing resource (e.g. an APM domain) and skips creation, then verification fails because the found resource is DELETED.
**Root cause:** Many `list` commands return all lifecycle states by default, including DELETED/DELETING.
**Fix:** Always add `--lifecycle-state ACTIVE` when listing to check for existence (APM domains, instances, VCNs, databases, etc.).
**See:** [Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm)
**Status:** resolved.

## KB-025 — APM shows zero traces because the OTLP endpoint URL is wrong (observability-db)

**Symptom:** App emits OpenTelemetry spans but APM shows 0 services/0 traces.
**Root cause:** The `OTLPSpanExporter` was pointed at the legacy REST path (`/20200101/observations/public-span?dataFormat=otlp&dataKey=...`) instead of the OTLP protocol endpoint, with the key in the query string.
**Fix:** Use `<apm-base>/20200101/opentelemetry/private/v1/traces` with an `Authorization: dataKey <private-data-key>` header (private key for server-side export), not the public-span URL.
**See:** [APM](https://docs.oracle.com/en-us/iaas/application-performance-monitoring/home.htm)
**Status:** resolved.

## KB-026 — APM RUM shows no browser data (empty agent config in the page) (observability-db)

**Symptom:** No APM Browser/RUM data; the page ships with empty upload endpoint, public data key, and an empty agent `<script src="">`.
**Root cause:** Static HTML carries empty RUM placeholders and the server serves it verbatim without injecting real RUM credentials.
**Fix:** Inject the RUM upload endpoint, public data key, and the RUM agent script src from environment variables at serve time; verify the served HTML has non-empty values.
**See:** [APM](https://docs.oracle.com/en-us/iaas/application-performance-monitoring/home.htm)
**Status:** resolved.

## KB-027 — Monitoring alarm creation fails on namespace case and inline JSON (observability-db)

**Symptom:** Custom-metric alarms fail to create in batch; or `--destinations` with `["ocid..."]` triggers shell glob/parse errors.
**Root cause:** Custom metric namespaces must match `^[a-z][a-z0-9_]*[a-z0-9]$` (no uppercase); and complex-type JSON passed inline lets the shell interpret `[` as a glob. `--pending-duration` is also required.
**Fix:** Use a lowercase namespace, pass complex JSON via `--destinations "file://$tmp.json"` (or a heredoc) instead of inline brackets, and include `--pending-duration PT5M`.
**See:** [Managing alarms](https://docs.oracle.com/en-us/iaas/Content/Monitoring/Tasks/managingalarms.htm)
**Status:** resolved.

## KB-028 — Monitoring `PostMetricData` 404s on the default (read) endpoint (observability-db)

**Symptom:** Reads (`list_metrics`, `summarize_metrics_data`) work, but publishing metrics 404s with "Incorrect Telemetry endpoint... Use telemetry-ingestion...".
**Root cause:** Monitoring has separate read (`telemetry.<region>.oraclecloud.com`) and write (`telemetry-ingestion.<region>.oraclecloud.com`) endpoints; the SDK client defaults to the read endpoint.
**Fix:** Construct the client with `service_endpoint="https://telemetry-ingestion.<region>.oraclecloud.com"` for writes.
**See:** [Monitoring](https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm)
**Status:** resolved.

## KB-029 — Derive region from the target resource's OCID, not the profile default (observability-db)

**Symptom:** `NotAuthorizedOrNotFound` / cross-region failures when a script operates on a Log Analytics log group, stream, or events target that lives in a different region than the profile's home region.
**Root cause:** The region is encoded in the OCID (`ocid1.<type>.oc1.<region>.<id>`), but the script inherited `OCI_REGION` from the profile and called the wrong regional endpoint.
**Fix:** Parse the region segment out of the target resource OCID and set `OCI_REGION` accordingly before making regional API calls.
**See:** [SDK & CLI configuration](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
**Status:** resolved.

## KB-030 — OCI Streaming stream-pool pitfalls (observability-db)

**Symptom:** Stream create fails with `Stream pool ... is DELETED`, or `Cannot specify both compartment id and stream pool id`, or a Kafka Connect worker shows RUNNING but ingests nothing with `UNKNOWN_TOPIC_OR_PARTITION`.
**Root cause:** Stale stream-pool OCIDs from prior deploys persist in config; the create API rejects passing both `compartment_id` and `stream_pool_id`; and a Kafka client's SASL username `<tenancy>/<user>/<stream-pool-ocid>` binds it to exactly one pool, so it cannot see topics in another pool.
**Fix:** Validate the pool OCID is ACTIVE before use; when targeting a pool pass `stream_pool_id` without `compartment_id`; ensure every topic a Kafka Connect worker consumes lives in that worker's configured stream pool.
**See:** [Streaming](https://docs.oracle.com/en-us/iaas/Content/Streaming/home.htm)
**Status:** resolved.

## KB-031 — Enable DB Management / Ops Insights on ADB via the native DB CLI (observability-db)

**Symptom:** `oci database-management ... enable-*-feature` fails on Autonomous DB with SSL-wallet/JSON-format errors ("Ssl wallet is required", "Unexpected character").
**Root cause:** The `database-management` service API expects an undocumented wallet-secret JSON format for mTLS ADB.
**Fix:** Use the native ADB verbs, which authenticate internally with no wallet/secret: `oci db autonomous-database enable-autonomous-database-management --autonomous-database-id <ADB_OCID>` and `... enable-operations-insights ...`.
**See:** [Operations Insights](https://docs.oracle.com/en-us/iaas/operations-insights/home.htm)
**Status:** resolved.

## KB-032 — Data Safe `list_audit_events` rejects `time_started`/`time_ended` (observability-db)

**Symptom:** Audit-event queries fail with `list_audit_events got unknown kwargs: ['time_started','time_ended']`.
**Root cause:** The SDK's `list_audit_events` only supports time filtering through the `scim_query` parameter.
**Fix:** Build an RFC3339 window and pass it via `scim_query`, e.g. `(auditEventTime ge "<start>") and (auditEventTime le "<end>")`, with `sort_by="auditEventTime"`, `sort_order="DESC"`.
**See:** [Data Safe](https://docs.oracle.com/en-us/iaas/data-safe/doc/oracle-data-safe-overview.html)
**Status:** resolved.

## KB-033 — Autonomous DB DSN must be a tnsnames alias, not the full service name (observability-db)

**Symptom:** App crashes on startup: `DPY-4000: unable to find "<prefix>_<db>_low" in tnsnames.ora`, even though the DSN matches the Console "Connection Strings" value.
**Root cause:** The Console shows the full low-level connect descriptor whose `service_name=` is `<tenancy-prefix>_<db>_low`, but `tnsnames.ora` in the wallet aliases it as the short lowercase `<db>_low`.
**Fix:** Set the DSN to the short alias (e.g. `<db>_low`); `oracledb` resolves it against `tnsnames.ora` in the wallet directory.
**See:** [Autonomous Database](https://docs.oracle.com/en-us/iaas/autonomous-database/index.html)
**Status:** resolved.

## KB-034 — `oracledb` thick-mode init fails without Instant Client; use thin mode (observability-db)

**Symptom:** `DPI-1047: Cannot locate a 64-bit Oracle Client library ... libclntsh.dylib` on a host without Oracle Instant Client (common on macOS).
**Root cause:** Code calls `oracledb.init_oracle_client()` unconditionally; thick mode requires the native client libs, but thin mode can connect to ADB with just the wallet.
**Fix:** Wrap `init_oracle_client()` in try/except and fall back to thin mode on failure instead of aborting.
**See:** [Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm)
**Status:** resolved.

## KB-035 — Monitoring a private OKE cluster without API-server access (iam-oke)

**Symptom:** The OKE monitoring/Terraform stack fails with `Resource precondition failed` / "OKE cluster is private" when the cluster has only a private endpoint.
**Root cause:** A "Full" deployment needs API-server reachability (public endpoint or an RMS private endpoint) to install the Helm chart.
**Fix:** Use the "Only OCI Resources" deployment option to create the OCI-side resources (Log Analytics entities, dashboards, service logs, agent keys) and install the Helm chart separately with kubectl/helm once you have cluster access.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-036 — OKE node "register timeout" / "pod network configuration timeout" is networking (iam-oke)

**Symptom:** Cluster reaches ACTIVE but the node pool fails: "N node(s) register timeout" or "pod network configuration timeout".
**Root cause:** Worker nodes can't reach the control plane or pull images — almost always a missing NAT gateway, missing `0.0.0.0/0 → NAT` route on the worker/pod route tables, missing service gateway, or security rules blocking 6443/12250.
**Fix:** Ensure a NAT gateway plus `0.0.0.0/0 → NAT` routes on worker and pod subnets, a service gateway for OCI services, and security rules allowing the API-server ports. It is not a Terraform bug.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-037 — `ReadWriteOnce` PVC with `replicas > 1` causes multi-attach errors (iam-oke)

**Symptom:** Pods stuck `Init`/`ContainerCreating` with `Multi-Attach error` / `FailedAttachVolume`; the service endpoint flaps.
**Root cause:** RWO block volumes can only attach to one node; multiple replicas across nodes cannot share them.
**Fix:** Keep `replicas=1` for RWO-backed deployments, or switch to a `ReadWriteMany` storage class (e.g. file-storage) if multiple replicas must share the volume.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-038 — Cross-cluster PVC migration must strip source PV binding metadata (iam-oke)

**Symptom:** PVCs reapplied in a different OKE cluster end up `Lost` or bound to a non-existent PV.
**Root cause:** The source PVC manifest carries `spec.volumeName` and `pv.kubernetes.io/*` / `volume.kubernetes.io/*` bind annotations that reference a PV that doesn't exist in the target cluster.
**Fix:** Strip `spec.volumeName` and all bind/provisioner annotations (and selected-node hints) before applying, so the target CSI provisioner binds a fresh PVC/PV pair.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-039 — Default OKE node boot volume runs out under load (disk-pressure evictions) (iam-oke)

**Symptom:** Pods `Pending` with `disk-pressure` taints, or running pods evicted for `ephemeral-storage`.
**Root cause:** The default node boot volume is exhausted by the image cache + node logs + container overlay FS, tripping kubelet's `nodefs.available<10%` eviction threshold.
**Fix:** Provision larger node boot volumes for image-heavy/multi-tenant workloads; short-term, lower pod CPU/ephemeral requests so pods fit on roomier nodes and let the cluster autoscaler add capacity.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-040 — OKE virtual (serverless) nodes do not expose NodePorts (iam-oke)

**Symptom:** A `Service type=LoadBalancer` gets an EXTERNAL-IP but `curl` returns connection reset; LB backends stay CRITICAL; `kubectl exec`/`port-forward`/`logs --previous` fail with "not supported".
**Root cause:** Virtual nodes are serverless — no `kube-proxy`, no NodePorts, no node-level debug. The default LB→NodePort path is broken, though in-cluster ClusterIP routing still works.
**Fix:** Use a pod-IP-aware path: the OCI Native Ingress Controller, or nginx-ingress via Helm, or a NetworkLoadBalancer Service with IP-target backends — not the default NodePort LB.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-041 — `create-kubeconfig` fails on clusters exposing only the legacy endpoint (iam-oke)

**Symptom:** `oci ce cluster create-kubeconfig` fails with `Invalid endpoint: Target endpoint is not available` on an ACTIVE cluster.
**Root cause:** The flow forced `PUBLIC_ENDPOINT`/`PRIVATE_ENDPOINT`, but some clusters expose only the legacy `endpoints.kubernetes` and lack the VCN-native endpoint fields.
**Fix:** Probe endpoint types and fall back across `PUBLIC_ENDPOINT` → `PRIVATE_ENDPOINT` → `VCN_HOSTNAME` → `LEGACY_KUBERNETES`.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-042 — A new VCN's default route table is empty (no automatic IGW route) (networking-compute)

**Symptom:** VMs in a "public" subnet have public IPs but are unreachable; cloud-init times out downloading packages; SSH connection times out.
**Root cause:** OCI does not auto-add an internet route. The default route table starts empty, so creating an Internet/NAT gateway alone routes nothing.
**Fix:** Add `0.0.0.0/0 → IGW` to the public subnet's route table and `0.0.0.0/0 → NAT` to a private route table, and assign those route tables to the subnets.
**See:** [Networking](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm)
**Status:** resolved.

## KB-043 — VCN/subnet deletion blocked by route rules and attached VNICs (networking-compute)

**Symptom:** VCN/subnet teardown fails with 409 conflicts; route tables, LPGs, gateways, or subnets can't be deleted.
**Root cause:** OCI refuses to delete anything still referenced by a route rule (gateways/LPGs as `network-entity-id`) or any subnet that still has attached VNICs (including service private-endpoints, mount targets, or load balancers).
**Fix:** Clear all route-table rules first, then delete LPGs, then mount targets/LBs and any service resources that own private-endpoint VNICs, then subnets, then gateways, then route tables.
**See:** [Networking](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm)
**Status:** resolved.

## KB-044 — ICMP is blocked by default; don't treat `ping` failure as "VM down" (networking-compute)

**Symptom:** `ping <vm>` is 100% loss and SSH is intermittently timing out, making the host look dead.
**Root cause:** OCI security rules don't permit ICMP by default, so ping always fails regardless of host health; intermittent SSH is usually rate-limiting/fail2ban or transient routing, not an outage.
**Fix:** Don't rely on ICMP for liveness. When SSH is flaky, run commands out-of-band via the Instance Agent: `oci compute instance-agent command create --instance-id <OCID> --content '{"source":{"sourceType":"TEXT","text":"<cmd>"}}' ...`. Add ICMP rules explicitly if ping is needed.
**See:** [Networking](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm)
**Status:** resolved.

## KB-045 — Avoid `0.0.0.0/0` ingress on SSH/management ports (security)

**Symptom:** NSGs and security lists expose SSH and management ports (22, app/admin ports) to the entire internet.
**Root cause:** Rules default to or are left at `0.0.0.0/0` instead of being scoped to the operator's address.
**Fix:** Restrict management-port ingress to a specific `/32` (or a known admin CIDR) via a variable like `ALLOWED_INGRESS_CIDR`; never default management ports to `0.0.0.0/0`. Re-scope when the operator's egress IP changes.
**See:** [Networking](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm)
**Status:** resolved.

## KB-046 — Vault automation: ensure the vault/key exist and wait out `CREATING` (security)

**Symptom:** Secret writes spam `NotAuthorizedOrNotFound` (stale/deleted vault or key OCID), or a just-created secret can't be found by name immediately after creation.
**Root cause:** Automation writes secrets against existing OCIDs without validating them, and KMS vault/secret creation is asynchronous — a secret in `CREATING` is invisible to a list filtered on `ACTIVE`.
**Fix:** Before writing secrets, validate-or-(re)create the vault and master key and persist their OCIDs. After creating a secret, resolve it by name across non-deleted states and poll `vault secret get` until `ACTIVE`.
**See:** [Vault / KMS](https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm)
**Status:** resolved.

## KB-047 — Usage/Cost API access is policy-gated and tenancy-scoped (cost)

**Symptom:** Cost/Usage API checks fail ("Check permissions/service limits") even though budgets were created successfully.
**Root cause:** Usage API access depends on tenancy-level policy grants for the calling principal and is independent of budget provisioning; it is queried at tenant scope.
**Fix:** Treat Usage API checks as warn-only unless the calling principal is explicitly granted `read usage-report in tenancy`; gate strict behavior behind an opt-in flag.
**See:** [IAM](https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm)
**Status:** resolved.

## KB-048 — OPSI create fails at ~80% with `DbcsEntityChangeWorkflowFailed` (observability-db)

**Symptom:** `opsi database-insights create-pe-comanged-database` reaches ~80% then FAILED; the insight list is empty while DBM looks healthy.
**Root cause:** Wrong `serviceName` (a bare DB/PDB name → `ORA-12514`) and/or the Vault password drifted from the DB account password (`ORA-01017`). OPSI runs an explicit connect test; DBM does not, so it masked the defect.
**Fix:** Use the real listener service (`<db_unique_name>.<domain>` / `<pdb>.<domain>`), sync the monitoring password to the Vault secret, disable + delete the FAILED insight, then re-create.
**See:** [Operations Insights](https://docs.oracle.com/en-us/iaas/operations-insights/home.htm)
**Status:** resolved.

## KB-049 — DBM stays enabled but never collects after re-enable (observability-db)

**Symptom:** DBM monitoring stays Stopped/UNKNOWN even though the credential is correct.
**Root cause:** A re-run only tolerated the "already enabled" 409 and skipped DBM, so a corrected service name never reached the connection.
**Fix:** Reconcile in place with `db database modify-database-management` (or `modify-pluggable-database-management`) using `--wait-for-state AVAILABLE` — no disable/re-enable needed.
**See:** [Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm)
**Status:** resolved.

## KB-050 — Monitoring user re-locks minutes after rotation (`ORA-28000` loop) (observability-db)

**Symptom:** DBM goes green, then flips to Stopped; the DB account cycles OPEN→LOCKED.
**Root cause:** The local Oracle Cloud Agent keeps authenticating with the old password, tripping `FAILED_LOGIN_ATTEMPTS`.
**Fix:** Put the monitoring user on a non-locking common profile (`CREATE PROFILE C##..._MON LIMIT FAILED_LOGIN_ATTEMPTS UNLIMITED; ALTER USER ... PROFILE ... CONTAINER=ALL; ... ACCOUNT UNLOCK CONTAINER=ALL`).
**See:** [Monitoring](https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm)
**Status:** resolved.

## KB-051 — PDB Performance Hub ADDM/AWR empty + `ORA-13750` on STS create (observability-db)

**Symptom:** A PDB's ADDM/AWR views show no data; creating a SQL Tuning Set from Performance Hub fails `ORA-13750`.
**Root cause:** Auto-AWR runs at CDB root only by default (`AWR_PDB_AUTOFLUSH_ENABLED=FALSE`); the monitoring user lacks STS admin.
**Fix:** Set `awr_pdb_autoflush_enabled=true` at root **and** per-PDB, set a PDB snapshot interval, seed a snapshot, and grant `administer [any] sql tuning set`.
**See:** [Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm)
**Status:** resolved.

## KB-052 — ADDM `ORA-13703` inside a PDB (mixed dbids) (observability-db)

**Symptom:** `DBMS_ADDM.ANALYZE_DB` raises `ORA-13703` "snapshots not found" in a PDB.
**Root cause:** Inside a PDB, `dba_hist_snapshot` lists both root and PDB snapshots; `ANALYZE_DB` analyzes the PDB `CON_DBID`.
**Fix:** Filter the snapshot pair to `dbid = sys_context('USERENV','CON_DBID')`; pass `task_name` only once (it is positional IN OUT, else `PLS-00703`).
**See:** [Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm)
**Status:** resolved.

## KB-053 — Monitoring password rejected by verify function / too long (observability-db)

**Symptom:** `ALTER USER` fails `ORA-20000` (needs ≥2 special chars) or `ORA-00972` (identifier too long); in-PDB alter fails `ORA-65066`.
**Root cause:** CDB password-verify complexity + SQL identifier length limits; a common user must be changed from root.
**Fix:** Choose a shorter password with mixed case, a digit, and ≥2 special chars; change the common user with `CONTAINER=ALL` from `CDB$ROOT`.
**See:** [Monitoring](https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm)
**Status:** resolved.

## KB-054 — OPSI create rejects both PE ids / wrong resource type (observability-db)

**Symptom:** `Cannot provide both opsiPrivateEndpointId and dbmPrivateEndpointId`, or `ORACLE_DATABASE` rejected as unsupported.
**Root cause:** The OPSI create accepts only the OPSI PE; the resource type must be the OCI lowercase string.
**Fix:** Pass only `--opsi-private-endpoint-id`; use `--database-resource-type database` (CDB/non-CDB) or `pluggabledatabase` (PDB).
**See:** [Operations Insights](https://docs.oracle.com/en-us/iaas/operations-insights/home.htm)
**Status:** resolved.

## KB-055 — `opsi database-insights list` is non-deterministic (observability-db)

**Symptom:** Discovery/validate reports an insight as NOT_FOUND while it is actually ACTIVE; repeated lists flap between 0/partial/full.
**Root cause:** Combining the full `--lifecycle-state` set with `--all` in one call makes the list control plane non-deterministic.
**Fix:** Prefer single-resource `opsi database-insights get --database-insight-id <ID>`; otherwise query one lifecycle state per call and union by OCID. Treat empty/partial reads as inconclusive, never as absence.
**See:** [Operations Insights](https://docs.oracle.com/en-us/iaas/operations-insights/home.htm)
**Status:** resolved.

## KB-056 — Preferred-credential set fails `RelatedResourceNotAuthorizedOrNotFound` (observability-db)

**Symptom:** The generic `database-management preferred-credential update --type NAMED_CREDENTIAL` fails.
**Root cause:** The generic update mis-maps the request body.
**Fix:** Use the dedicated verb `preferred-credential update-preferred-credential-update-named-preferred-credential-details --managed-database-id <ID> --credential-name PC_READ|PC_WRITE --named-credential-id <NAMED_CRED_OCID>`.
**See:** [Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm)
**Status:** resolved.

## KB-057 — Data Safe target stuck `NEEDS_ATTENTION` with `ORA-01017` (observability-db)

**Symptom:** A Data Safe target registers but stays `NEEDS_ATTENTION`; lifecycle details show "Failed to connect... ORA-01017" although the network path is fine.
**Root cause:** Stale/invalid service-account password.
**Fix:** Rotate the account password `CONTAINER=ALL`, then update both the Vault secret and the Data Safe target (`data-safe target-database update --credentials file://... --force`; work request → `--wait-for-state SUCCEEDED`).
**See:** [Register Data Safe target databases](https://docs.oracle.com/en-us/iaas/data-safe/doc/register-target-databases.html)
**Status:** resolved.

## KB-058 — DB-system create blocked by a per-AD `database` service limit (observability-db)

**Symptom:** DB system create fails `vm-block-storage-gb LimitExceeded` even though block-volume quota is free.
**Root cause:** This is a **Database** service limit enforced **per availability domain**; one AD was full.
**Fix:** Pin the DB system to an AD with headroom; check `oci limits resource-availability get --service-name database --limit-name vm-block-storage-gb --availability-domain <AD> --compartment-id <TENANCY_OCID>`.
**See:** [Service Limits](https://docs.oracle.com/en-us/iaas/Content/General/service-limits/overview.htm)
**Status:** resolved.

## KB-059 — Redacting the data path collapses OCID joins (observability-db)

**Symptom:** Every database is reported as Data Safe/OPSI ENABLED (false positives) by a discovery tool.
**Root cause:** Redacting CLI stdout **before** JSON parse turned every OCID into one identical token, so OCID-keyed joins matched everything.
**Fix:** Redact only at the display/serialize boundary (`--json` output, logs, error strings) — never in values that downstream logic parses/joins on.
**See:** [Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm)
**Status:** resolved.

## KB-060 — OCL: string-typed integer fields must be quoted (log-analytics)

**Symptom:** `Invalid string value for the field 'Event ID': 4625`.
**Root cause:** Fields like `Event ID`, `Logon Type`, `Response Code`, `Status Code` are stored as **strings** in OCI Log Analytics.
**Fix:** Quote the literal: `'Event ID' = '4625'`, not `= 4625`.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-061 — OCL: numeric LONG fields must NOT be quoted (log-analytics)

**Symptom:** `Invalid long value for the field 'Destination Port': '443'`.
**Root cause:** True numeric fields (`Source Port`, `Destination Port`, `Bytes Sent`) require a bare integer literal.
**Fix:** Use `'Destination Port' = 443` (no quotes); only quote string-typed fields.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-062 — OCL: multi-word field names need single quotes (log-analytics)

**Symptom:** Parse error / field not recognized on `Host Name`, `Principal Name`, etc.
**Root cause:** Unquoted multi-token field names are mis-tokenized.
**Fix:** Wrap every multi-word field in single quotes: `'Host Name'`, `'Principal Name'`, `'Log Source'`.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-063 — OCL: time range belongs in the API, not the query string (log-analytics)

**Symptom:** A saved search returns nothing (or errors) when authors embed time literals.
**Root cause:** OCL saved searches rely on the execution-time `TimeRange` (`--time-start`/`--time-end`/`--timezone`), not inline time.
**Fix:** Keep queries time-agnostic; pass the window at call time. `oci_logan.sh -t <N{m|h|d|w}>` does this.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-064 — LA source/parser lookups miss by display name (log-analytics)

**Symptom:** A "missing" source gets duplicated, or an upsert hits an unexpected conflict.
**Root cause:** Each artifact has an immutable internal `name` AND a `display_name`; matching one alone fails.
**Fix:** Search `source list --is-system ALL` against **both** names before create.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-065 — LA parser/source upsert needs the current etag (log-analytics)

**Symptom:** `412 Precondition Failed` / concurrency error on upsert.
**Root cause:** OCI uses optimistic concurrency on sources/parsers.
**Fix:** `get` the resource to read its `etag`, then pass `if_match=<etag>` on upsert.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-066 — LA entity name is immutable after creation (log-analytics)

**Symptom:** Rename attempts fail; a solution UI shows a stale entity.
**Root cause:** The LA entity `name` cannot be changed post-create.
**Fix:** Update `metadata` and `time-last-discovered` instead; only fix the name on greenfield create.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-067 — Null `cluster_date` breaks Kubernetes entity metric joins (log-analytics)

**Symptom:** The OKE observability solution shows no metrics despite data flowing.
**Root cause:** Required entity metadata (`cluster`, `cluster_date`, `metrics_namespace`) is missing or `null`.
**Fix:** Set a real RFC3339 `cluster_date` (derive from `ce cluster` `metadata["time-created"]`) and repair via `entity update --metadata`.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-068 — LA on-demand upload requires the log-group OCID (log-analytics)

**Symptom:** On-demand uploaded events never appear or land in the wrong group.
**Root cause:** `opc_meta_loggrpid` was omitted from `upload_log_file`.
**Fix:** Always pass the target `<LOG_GROUP_OCID>` and the correct `log_source_name`.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-069 — OCL `like` (glob) vs `matches` (regex) confusion (log-analytics)

**Symptom:** A `matches` pattern returns nothing, or a `like` with `^...$` never matches.
**Root cause:** `like` uses `*` glob wildcards; `matches` uses regex anchors.
**Fix:** `'F' like '*substr*'` for substring; `'F' matches '^regex$'` for patterns — never mix the two syntaxes.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-070 — LA query excludes child compartments by default (log-analytics)

**Symptom:** Data in child compartments is missing from results.
**Root cause:** The query was scoped to a single compartment.
**Fix:** Set `--compartment-id-in-subtree true` (SDK `compartment_id_in_subtree=True`) to include children. `oci_logan.sh` does this by default.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-071 — LA live query validation times out during bulk promotion (log-analytics)

**Symptom:** `query validation exceeded <N>s` uniformly when validating many queries.
**Root cause:** Validating many data-scanning queries live exhausts the deadline.
**Fix:** Use `parse_query` (syntax-only, no scan) in CI; validate live in small batches against synthetic data with a per-query deadline.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-072 — KMS key list needs the vault management-endpoint (security)

**Symptom:** `oci kms management key list` returns nothing or errors with an endpoint problem.
**Root cause:** The KMS management plane is **per-vault**, not regional; the default control-plane endpoint cannot list keys.
**Fix:** Read `.management-endpoint` from `kms vault get/list` and pass `--endpoint <VAULT_MANAGEMENT_ENDPOINT>` on `kms management` calls.
**See:** [Vault / KMS](https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm)
**Status:** resolved.

## KB-073 — Cloud Guard findings only appear in the reporting region (security)

**Symptom:** `cloud-guard problem list` is empty although Cloud Guard is ENABLED.
**Root cause:** Problems aggregate in the single configured **reporting region**; queries from any other region return empty.
**Fix:** Read `reporting-region` from `cloud-guard configuration get` and query problems with `--region <REPORTING_REGION>`.
**See:** [Cloud Guard](https://docs.oracle.com/en-us/iaas/cloud-guard/home.htm)
**Status:** resolved.

## KB-074 — Subtree visibility needs both `--compartment-id-in-subtree` and `--access-level` (security)

**Symptom:** Child-compartment Cloud Guard problems / compartments are missing from results.
**Root cause:** Default list scope is the single compartment at the caller's own access level.
**Fix:** Add `--compartment-id-in-subtree true --access-level ACCESSIBLE` to compartment and problem `list` calls.
**See:** [Cloud Guard](https://docs.oracle.com/en-us/iaas/cloud-guard/home.htm)
**Status:** resolved.

## KB-075 — Regional resources missed when scanning only the home region (networking-compute)

**Symptom:** Buckets/subnets/keys in non-home regions are never flagged by a posture scan.
**Root cause:** Regional resource `list` calls default to the configured region.
**Fix:** Enumerate `iam region-subscription list --tenancy-id <TENANCY_OCID>` (status READY/ACTIVE) and repeat each list with `--region <REGION>`.
**See:** [SDK & CLI configuration](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
**Status:** resolved.

## KB-076 — `audit config` vs `audit configuration` verb varies by CLI version (cli)

**Symptom:** `oci audit config get` (or `audit configuration get`) errors as an unknown command.
**Root cause:** The subcommand name differs across OCI CLI versions.
**Fix:** Try `audit config get`, fall back to `audit configuration get`; both return `retention-period-days`.
**See:** [Audit](https://docs.oracle.com/en-us/iaas/Content/Audit/home.htm)
**Status:** resolved.

## KB-077 — A public subnet is `prohibit-public-ip-on-vnic == false`, not an `isPublic` flag (networking-compute)

**Symptom:** No boolean "isPublic" field exists on a subnet, so public subnets aren't detected.
**Root cause:** OCI models public/private as `prohibit-public-ip-on-vnic` (true == private).
**Fix:** Treat `prohibit-public-ip-on-vnic == false` (or absent) as a public subnet.
**See:** [Networking](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm)
**Status:** resolved.

## KB-078 — Open-port checks miss protocol-only `0.0.0.0/0` rules (networking-compute)

**Symptom:** Internet-open SSH/RDP rules are missed by a security-list/NSG scan.
**Root cause:** A rule can specify protocol `6` (TCP) with **no** `tcp-options`/port range, implicitly opening all ports.
**Fix:** Flag `source==0.0.0.0/0` when `tcp-options.destination-port-range.min in {22,3389}` **OR** when `protocol=="6"` with no port options.
**See:** [Networking](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm)
**Status:** resolved.

## KB-079 — Bucket `public-access-type` is absent (not `NoPublicAccess`) on private buckets (security)

**Symptom:** Private buckets are misclassified as public (or a `KeyError`).
**Root cause:** The `public-access-type` field may be omitted on private buckets.
**Fix:** Default the value to `"NoPublicAccess"` before comparing.
**See:** [Object Storage](https://docs.oracle.com/en-us/iaas/Content/Object/home.htm)
**Status:** resolved.

## KB-080 — `auto` auth mode silently picks the wrong identity (cli)

**Symptom:** A tool reads the wrong tenancy / has unexpected permissions.
**Root cause:** `auto` mode picks the config profile if one is ready, else instance principal — silently, with no log of which.
**Fix:** Pin `OCI_AUTH_MODE` / `OCI_CLI_AUTH` explicitly (`config` or `instance_principal`) and assert the resolved tenancy before acting.
**See:** [SDK & CLI configuration](https://docs.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm)
**Status:** resolved.

## KB-081 — Per-bucket CMK detection requires the namespace and the detailed `get` (security)

**Symptom:** `os bucket get` fails, or the KMS key can't be detected from `os bucket list`.
**Root cause:** Bucket `get` needs `--namespace <OS_NAMESPACE>` (from `os ns get`), and `kms-key-id` appears only on the detailed `get`, not on `list`.
**Fix:** Resolve the namespace once, then `os bucket get --namespace <OS_NAMESPACE> --bucket-name <BUCKET>` and read `kms-key-id`.
**See:** [Vault / KMS](https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm)
**Status:** resolved.

## KB-082 — KMS auto-rotation vs rotated-once are different signals (security)

**Symptom:** Keys reported compliant though never actually rotated (or vice-versa).
**Root cause:** `is-auto-rotation-enabled` (policy) and `current-key-version` (has been versioned) measure different things.
**Fix:** Evaluate both — auto-rotation enabled for hygiene, plus a present current version for actual rotation evidence.
**See:** [Vault / KMS](https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm)
**Status:** resolved.

## KB-083 — ORM job hangs on `--wait-for-state SUCCEEDED` when it FAILs (cli)

**Symptom:** A Resource Manager plan/apply/destroy job never returns; the process must be killed.
**Root cause:** Same as KB-007 — a `FAILED`/`CANCELED` job is not `SUCCEEDED`, so the CLI polls for the entire `--max-wait-seconds` window.
**Fix:** Poll `resource-manager job get --query 'data."lifecycle-state"'` and break on all terminal states; dump `job get-job-logs-content` on failure.
**See:** [Resource Manager](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/home.htm)
**Status:** resolved.

## KB-084 — OCI Functions image must be amd64 (events-functions)

**Symptom:** A function deploys fine but every invoke errors or hangs.
**Root cause:** The image was built on arm64 (Apple Silicon); OCIR-hosted functions run on x86_64.
**Fix:** Build with `--platform linux/amd64` (or on an x86 builder), re-push, and redeploy.
**See:** [Creating/deploying Functions](https://docs.oracle.com/en-us/iaas/Content/Functions/Tasks/functionscreatingfunctions.htm)
**Status:** resolved.

## KB-085 — Service Connector is ACTIVE but moves no data (events-functions)

**Symptom:** An SCH connector shows `ACTIVE` but the target stays empty.
**Root cause:** SCH runs as the `serviceconnector` service principal, not the user; the per-source/target IAM policy is missing, so create succeeds but runtime reads/writes are denied.
**Fix:** Add policies for `request.principal.type='serviceconnector'` — e.g. `use stream-pull`/`stream-consume` for a streaming source and the target verb (`loganalytics-log-group`, etc.), scoped to the compartment.
**See:** [Service Connector Hub](https://docs.oracle.com/en-us/iaas/Content/connector-hub/home.htm)
**Status:** resolved.

## KB-086 — ONS email/HTTPS subscription silently drops messages (events-functions)

**Symptom:** Published notifications never arrive.
**Root cause:** The subscription is stuck in `PENDING` — a confirmation link was sent to the endpoint and never clicked; messages are dropped until confirmed.
**Fix:** Confirm via the emailed link; verify `lifecycle-state == ACTIVE`. Links expire — delete and recreate the subscription to re-trigger.
**See:** [Notifications](https://docs.oracle.com/en-us/iaas/Content/Notification/home.htm)
**Status:** resolved.

## KB-087 — Events rule never fires (events-functions)

**Symptom:** A rule is enabled with a correct-looking condition but nothing is invoked.
**Root cause:** The source service isn't emitting events for that resource (e.g. Object Storage emits events only when enabled per bucket), or the `eventType` reverse-DNS string is slightly off.
**Fix:** Enable emit-events on the resource; confirm the exact CloudEvents `eventType`; remember filters under `data` are arrays (OR-match), empty `{}` matches all.
**See:** [Events](https://docs.oracle.com/en-us/iaas/Content/Events/home.htm)
**Status:** resolved.

## KB-088 — Streaming put_messages partial failure returns 200 (events-functions)

**Symptom:** A producer reports success but some records never land in the stream.
**Root cause:** `put_messages` returns per-entry results; individual entries can carry `.error` while the overall call returns 200.
**Fix:** Iterate `resp.data.entries` and count any `entry.error` as a failure; retry the failed entries.
**See:** [Streaming](https://docs.oracle.com/en-us/iaas/Content/Streaming/home.htm)
**Status:** resolved.

## KB-089 — Stream message size/count limits exceeded (events-functions)

**Symptom:** Large batches are rejected by Streaming.
**Root cause:** ~1 MB / 100-message per-`PutMessages` limits, and payloads are base64-encoded (inflating size ~33%).
**Fix:** Batch size-aware — estimate base64 bytes + per-entry overhead and flush before the limit; cap entries at 100.
**See:** [Streaming](https://docs.oracle.com/en-us/iaas/Content/Streaming/home.htm)
**Status:** resolved.

## KB-090 — Single-line PEM key from an env var rejected by the SDK (events-functions)

**Symptom:** `validate_config` / auth fails when the private key is supplied via an environment variable.
**Root cause:** Env vars collapse the PEM to one line or to literal `\n`, which the SDK won't parse.
**Fix:** Normalize `\n`, extract the body between `-----BEGIN/END-----`, and re-wrap to 64-char lines before constructing the client.
**See:** [Functions](https://docs.oracle.com/en-us/iaas/Content/Functions/home.htm)
**Status:** resolved.

## KB-091 — Producer uses a Stream Pool OCID instead of a Stream OCID (events-functions)

**Symptom:** `put_messages` fails with not-found / invalid id.
**Root cause:** A Stream **Pool** OCID was passed where a **Stream** OCID is required.
**Fix:** Use `ocid1.stream...`; guard by rejecting any id containing `streampool`.
**See:** [Managing streams](https://docs.oracle.com/en-us/iaas/Content/Streaming/Tasks/managingstreams.htm)
**Status:** resolved.

## KB-092 — SCH/Function async create used before ACTIVE (events-functions)

**Symptom:** A script uses a half-created connector/function and fails.
**Root cause:** Create returns a work request before the resource is `ACTIVE`.
**Fix:** Pass `--wait-for-state ACTIVE --max-wait-seconds N` (120–300s) and resolve the OCID by re-listing on completion.
**See:** [Functions](https://docs.oracle.com/en-us/iaas/Content/Functions/home.htm)
**Status:** resolved.

## KB-093 — LA custom source/parser not created by Terraform (events-functions)

**Symptom:** An SCH `loggingAnalytics` target is wired but Log Analytics can't parse the records.
**Root cause:** The OCI Terraform provider does not manage LA fields/parser/source; only the connector and log group are created.
**Fix:** After `terraform apply`, create the custom source named in `logSourceIdentifier` with `oci log-analytics source upsert-source` (or a post-apply script). See the oci-log-analytics skill.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-094 — OKE rollout targets the wrong tenancy because context name was trusted (networking-compute)

**Symptom:** A rollout or evolution test is about to mutate the wrong OKE cluster, even though the local Kubernetes context name looked harmless.
**Root cause:** Kubernetes context names are local labels. The actual OCI exec plugin profile, region, and cluster OCID may point at a protected tenancy.
**Fix:** Before mutating, print and verify `kubectl config view` context/user exec args plus `ce cluster get` for the target cluster. Refuse protected profiles unless an explicit break-glass confirmation is set.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-095 — OKE app secrets drift because Kubernetes literals replaced Vault/ExternalSecrets (security)

**Symptom:** Pods restart with stale passwords/tokens, or a control-plane UI displays a different credential than the backend accepts.
**Root cause:** Runtime secrets were patched directly into Kubernetes or duplicated across env sources instead of treating OCI Vault plus `ExternalSecret` as the source of truth.
**Fix:** Rotate/update the OCI Vault secret first, verify the matching `ExternalSecret` is ready, then restart affected workloads. Disable literal Kubernetes secret fallback by default; allow it only through an explicit non-production break-glass flag.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-096 — `oauth2-proxy` cookie secret length is wrong (security)

**Symptom:** `oauth2-proxy` fails startup or rejects sessions after a secret rotation.
**Root cause:** The cookie secret must be a valid literal 16, 24, or 32 byte value. Storing base64 output such as `openssl rand -base64 32` directly creates a 44 byte string, not a 32 byte secret.
**Fix:** Store a literal valid-length secret or decode/trim to the required byte length before writing the Kubernetes/Vault value. Verify the deployed value length without printing the value.
**See:** [Vault / KMS](https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm)
**Status:** resolved.

## KB-097 — Agentic traces are not release-gateable (observability-db)

**Symptom:** Dashboards show spans, but evaluators, guardrails, approvals, tool calls, or budget decisions cannot be traced back to a complete agent episode.
**Root cause:** Only request/model spans were emitted; mandatory episode evidence and cross-system IDs were missing or inconsistent.
**Fix:** Emit an agent episode contract with `trace_id`, `span_id`, `session_id`, `conversation_id`, model/tool/retrieval/memory/guardrail/approval/eval spans, and trace-integrity fields. Gate release on low `non_gateable` and `non_exportable` rates.
**See:** [APM](https://docs.oracle.com/en-us/iaas/application-performance-monitoring/home.htm)
**Status:** resolved.

## KB-098 — APM shows traces in one domain while incident lookups query another (observability-db)

**Symptom:** Traces exist in OCI APM, but deep links or incident lookup tools return empty results.
**Root cause:** Runtime telemetry, GenAI telemetry, and application-under-investigation telemetry were split across APM domains, while tools used only a default domain id.
**Fix:** Make domain selection explicit: runtime endpoint/data key, GenAI endpoint/data key, default lookup domain, and app-specific lookup domains. Keep private data keys in Vault/ExternalSecrets and redact every domain id in docs.
**See:** [APM](https://docs.oracle.com/en-us/iaas/application-performance-monitoring/home.htm)
**Status:** resolved.

## KB-099 — "No active alarms" confused with "no alarm definitions" (observability-db)

**Symptom:** An operator asks for OCI alarms and receives an empty active-alarm result, then assumes no alarm definitions exist.
**Root cause:** Firing alarm status and configured alarm definitions are different data surfaces.
**Fix:** Route "active/firing/current alarms" to alarm-status queries, and "definitions/configured alarms" to `monitoring alarm list`. State which surface was checked and offer the other when results are empty.
**See:** [Monitoring](https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm)
**Status:** resolved.

## KB-100 — SQLcl AWR fallback uses snapshots from a previous DB incarnation (observability-db)

**Symptom:** A local SQLcl AWR report fails with stale snapshot errors or reports data for an unexpected database incarnation.
**Root cause:** Snapshot selection did not filter by the current DBID and instance number, so reused ADB/service names could match old rows.
**Fix:** When falling back to SQLcl/AWR views, filter snapshot pairs by current `DBID` and current instance number before calling `DBMS_WORKLOAD_REPOSITORY`.
**See:** [Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm)
**Status:** resolved.

## KB-101 — OKE Log Analytics detection pack validated without live attack activity (log-analytics)

**Symptom:** Detection validation requires creating privileged pods or running controlled attack tooling in a cluster.
**Root cause:** The pack lacked a synthetic-event validation path and source contract.
**Fix:** Define required sources, validate OCL syntax with `parse_query`, then test scenario semantics against synthetic Log Analytics events in an isolated log group. Use live queries only after collection prerequisites are confirmed.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-102 — Destructive-command guard was blind to the `oci_cli` wrapper (security)

**Symptom:** A destructive call routed through the pack's own `oci_cli` wrapper or a domain helper script (`oci_*.sh`) ran without the PreToolUse guard ever firing, even though the same verb typed as raw `oci …` was blocked.
**Root cause:** `hooks/guard_destructive.py` keyed on `\boci\b`. `_` is a word character, so the word boundary never matched `oci_cli` — the exact entrypoint every SKILL/AGENTS file mandates ("All CLI through `oci_cli`"). The guard only saw bare `oci` invocations.
**Fix:** Match all three real invocation shapes (`oci`, `oci_cli`, `oci_<domain>.{sh,py}`) via a dedicated `OCI_INVOCATION` regex, separate from the destructive-verb matcher. Added the Vault/KMS soft-delete scheduling verbs (`schedule-*-deletion`, via `\bdeletion\b`) and `change-compartment`. Fenced with `tests/test_guard_destructive.py`.
**See:** [Cloud Guard](https://docs.oracle.com/en-us/iaas/cloud-guard/home.htm)
**Status:** resolved.

## KB-103 — Redaction gate under-masked standard-alphabet base64 secrets (security)

**Symptom:** A base64 datakey/auth token containing `/` (standard alphabet) was only partially masked — `redact.py` masked the run up to the first slash and left the rest in cleartext.
**Root cause:** The `secret_blob` rule used `[A-Za-z0-9+]{40,}` (no `/`) on purpose, so slash-separated endpoint paths were not eaten — but that also meant any secret with a `/` split into sub-40 runs and slipped through.
**Fix:** Added a `secret_blob_slash` rule (`[A-Za-z0-9+/]{40,}`) with a `_b64_slash_is_secret` discriminator that keeps URL/endpoint paths verbatim (short lowercase `/`-segments) but masks high-entropy mixed-case+digit runs. Fenced with `tests/test_redact.py`. Test fixtures are assembled at runtime so the test files themselves stay clean under the gate.
**See:** [Vault / KMS](https://docs.oracle.com/en-us/iaas/Content/KeyManagement/home.htm)
**Status:** resolved.

## KB-104 — wait_for_state derived the wrong --id flag for multi-word resources (networking-compute)

**Symptom:** Polling an Autonomous Database, Load Balancer, DB System, or other multi-word resource with `wait_for_state` failed with an "unrecognized argument" / missing-id error, because the wrong `--<x>-id` flag was passed.
**Root cause:** The id flag was derived from the LAST word of the command path (`"database autonomous-database"` → `--database-id`, `"lb load-balancer"` → `--balancer-id`), which is correct only for single-word resources.
**Fix:** Extracted `_id_flag_for` in `common.sh` with a `case` that matches known multi-word tails (autonomous-database, autonomous-container-database, network-load-balancer, load-balancer, db-system, mount-target, file-system, node-pool, boot-volume) before the last-word fallback. Order most-specific first (`*network-load-balancer` before `*load-balancer`). Fenced by `tests/common_helpers_smoke.sh`.
**See:** [Networking](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/overview.htm)
**Status:** resolved.

## KB-105 — MCP gateway readiness reports 0 backends though proxied tools work (cli)

**Symptom:** The OKE-deployed `oci-mcp-gateway` serves proxied `backendname_toolname` tools correctly, but its readiness probe / `gateway_health` reports `0 backends` (and `BackendRegistry` looks empty), making the gateway appear unhealthy.
**Root cause:** FastMCP's `lifespan=gateway_lifespan` async context manager — which discovers the backend MCP servers and populates `BackendRegistry` on startup — was not passed into `create_gateway()`'s `FastMCP(...)` kwargs. Without the wired lifespan the registry is never populated, so health reflects 0 backends even though request-time proxying still falls through to the backends.
**Fix:** Pass the lifespan into the FastMCP constructor — `FastMCP(name=..., lifespan=gateway_lifespan, ...)` inside `create_gateway()` — so the registry is populated on startup and `gateway_health` counts the real backends. See [references/mcp-gateway.md](mcp-gateway.md).
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-106 — OCI Streaming Kafka consumer fails SASL auth after deploy (events-functions)

**Symptom:** A Kafka-compatible consumer such as Kafka Connect or SOC4Kafka/Splunk
OTel Collector starts against OCI Streaming, but the service log repeatedly shows
`SASL_AUTHENTICATION_FAILED`, `UNKNOWN_TOPIC_OR_PARTITION`, or metadata refresh
timeouts. The OCI Service Connector may still be `ACTIVE`, and Splunk/HTTP HEC
health checks may still pass.
**Root cause:** OCI Streaming's Kafka API binds the SASL username to a specific
tenancy, OCI user, and stream pool. Identity Domains users often require the full
domain-qualified OCI user name (for example `oracleidentitycloudservice/<USER>`),
not a bare email/local profile alias. The SASL password must be an auth token
created for that same user. Mixing Terraform/CLI profiles, or reusing an auth
token from another user, causes Kafka auth failure even when the network and HEC
side are healthy. A separate pitfall: service logs cannot be test-injected with
`logging-ingestion put-logs`; that API targets custom logs, not service logs.
**Fix:** Resolve the active OCI user with `oci_cli iam user get --user-id
<USER_OCID> --query 'data.name' --raw-output`; build the Kafka username as
`<TENANCY_NAME>/<FULL_OCI_USER_NAME>/<STREAM_POOL_OCID>`; create/store an auth
token for that same user; wait for propagation; restart the consumer; then inspect
consumer logs for fresh SASL and metadata errors. Test service-log pipelines by
triggering the source service, or use a custom log when you need
`logging-ingestion put-logs`.
**See:** [Streaming Kafka compatibility](https://docs.oracle.com/en-us/iaas/Content/Streaming/Tasks/kafkacompatibility_topic-Configuration.htm)
**Status:** resolved.

## KB-107 — Preset OCL queries return 0 rows: log source names vary per tenancy (log-analytics)

**Symptom:** A canned Log Analytics query (`'Log Source' = '<name>' | ...`) returns
0 rows in a new tenancy even though logs are clearly being ingested.
**Root cause:** Which Oracle-defined sources are *active* — and the exact source
**names** you must match — vary per tenancy and per what is onboarded. Some sources
also lack fields you filter on, so a field predicate silently matches nothing.
**Fix:** Discover the live sources first — `'*' | stats count by 'Log Source'`
(or `oci_cli log-analytics source list ...`) — then write the query against names
that actually exist. Known gotchas to encode in presets: Kubernetes container
logs carry **no `Severity` field** (`Severity = 'ERROR'` returns 0 — filter on the
message instead); SSH/auth events are in **`Linux Secure Logs`**, not
`Linux Syslog Logs`; the WAF source is **`OCI WAF Logs`**, not `OCI WAF Access Logs`.
Treat an empty result as inconclusive until the source name and fields are confirmed.
**See:** [Oracle-defined log sources](https://docs.oracle.com/en-us/iaas/logging-analytics/doc/oracle-defined-sources.html)
**Status:** resolved.

## KB-108 — Alarm never fires / metric query empty: MQL dimension names are case-sensitive and differ from Console labels (observability-db)

**Symptom:** An alarm stays `OK` (or a Metrics query returns nothing) while the
resource is clearly unhealthy or stopped.
**Root cause:** OCI Monitoring Query Language is **case-sensitive**, and alarm
dimensions must use the **metric dimension keys**, not the friendly names shown in
the Console. A query keyed on a display-style name (e.g. `monitorDisplayName`,
`apmDomainId`) matches zero metrics; the real keys for APM synthetics are
`MonitorName` and `ResourceId`.
**Fix:** Confirm the exact dimension keys and casing from the metric definition
(`oci_cli monitoring metric list ...`, or the service's metrics reference), match
them exactly, and validate the MQL in Metrics Explorer **before** wiring it into an
alarm. An alarm that never fires is worse than none — it reads as "healthy".
**See:** [Monitoring Query Language (MQL)](https://docs.oracle.com/en-us/iaas/Content/Monitoring/Reference/mql.htm)
**Status:** resolved.

## KB-109 — APM trace status filter on `OK` returns nothing — use `COMPLETE` (observability-db)

**Symptom:** Filtering APM traces/spans by status `OK` returns 0 results.
**Root cause:** OCI APM uses `COMPLETE` for a successfully finished trace and
`ERROR` for a failed one. There is no `OK` status, so the filter excludes everything.
**Fix:** Filter on `COMPLETE` (treat as success) and `ERROR` (failure); map any
`OK`-style UI/code to `COMPLETE`.
**See:** [Application Performance Monitoring](https://docs.oracle.com/en-us/iaas/application-performance-monitoring/home.htm)
**Status:** resolved.

## KB-110 — APM Synthetic monitors go stale silently: target stable domain names, not bare IPs (observability-db)

**Symptom:** A synthetic monitor keeps reporting "available" against an endpoint
that no longer exists, or probes the wrong host after an infra change.
**Root cause:** Monitors created against a bare instance IP keep probing that IP
after the instance is replaced/rebuilt. Paired with a broken availability alarm
(see KB-108), the staleness is invisible.
**Fix:** Target a **stable HTTPS domain name**, never a bare VM IP, so the monitor
follows the service across instance churn; pair it with a correctly-keyed
availability alarm and confirm the alarm transitions when the target is down.
**See:** [APM Synthetic Monitoring](https://docs.oracle.com/en-us/iaas/application-performance-monitoring/doc/use-synthetic-monitoring.html)
**Status:** resolved.

## KB-111 — Client-IP / geolocation view is empty: APM spans don't carry client IPs — use VCN Flow Logs (log-analytics)

**Symptom:** A "where are connections coming from" / client-geo view built from APM
spans shows nothing — the spans have no client-IP attribute.
**Root cause:** OCI APM spans do not capture client/peer IPs in span attributes,
so there is nothing to geolocate.
**Fix:** Source client/peer IPs from **VCN Flow Logs** in Log Analytics
(`'Log Source' = 'OCI VCN Flow Unified Schema Logs' | ...`), filtering RFC1918
ranges out when you only want external peers. Enable VCN Flow Logs on the relevant
subnets/VNICs first (an OCI Logging feature).
**See:** [Logging](https://docs.oracle.com/en-us/iaas/Content/Logging/home.htm)
**Status:** resolved.

## KB-112 — DBM enabled does not mean OPSI enabled — they are separate steps (observability-db)

**Symptom:** An enablement run skips a target's Operations Insights step, leaving
Database Insights uncreated, because Database Management was already enabled on it.
**Root cause:** DBM and OPSI are **independent** enablements. Treating "DBM already
enabled" as full success skips the OPSI create entirely.
**Fix:** Enable them as separate, independently-idempotent steps: if DBM is already
enabled but the OPSI credential/payload is ready, continue to the OPSI
create/enable step rather than marking the target done.
**See:** [Operations Insights](https://docs.oracle.com/en-us/iaas/operations-insights/home.htm)
**Status:** resolved.

## KB-113 — OPSI create rejects the database resource type — use OCI resource-type strings (observability-db)

**Symptom:** `opsi database-insights create-*` fails validation, rejecting a value
like `ORACLE_DATABASE` as an unsupported database resource type.
**Root cause:** OPSI expects the **OCI resource-type strings**, not friendly or
guessed labels.
**Fix:** Use `database` for Base Database Service CDB / non-CDB targets and
`pluggabledatabase` for PDB targets. Confirm the exact accepted values with
`python3 scripts/oci_cli_help.py opsi database-insights create-pe-comanaged-database`
before running.
**See:** [Operations Insights](https://docs.oracle.com/en-us/iaas/operations-insights/home.htm)
**Status:** resolved.

## KB-114 — DBSNMP password rotation fails with `ORA-00972: identifier is too long` (observability-db)

**Symptom:** Rotating the `DBSNMP` monitoring password with a long generated value
fails with `ORA-00972: identifier is too long`.
**Root cause:** The generated password (often quoted) exceeds the length the
database accepts in the `ALTER USER` statement for that release/profile (seen on a
19c baseline).
**Fix:** Generate a **shorter** password that still satisfies the profile's
complexity rules; store it only in OCI Vault and ignored local files, never inline.
Re-verify `DBSNMP` is `OPEN` and the required grants are present in the CDB root
and each PDB afterward.
**See:** [Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm)
**Status:** resolved.

## KB-115 — Performance Hub greys out asking to grant DBSNMP privileges (observability-db)

**Symptom:** Console **Performance Hub** for a DBM-managed database shows
"Performance Hub requires granting of appropriate user privileges… reopen
Performance Hub", and AWR / ADDM / ASH Analytics / SQL Tuning / Real-Time SQL
Monitoring are unavailable.
**Root cause:** The DBM monitoring user (`DBSNMP`) has only the basic + advanced
*monitoring* grants, not the larger Performance Hub set (which runs advisors and
the workload repository).
**Fix:** As SYSDBA, grant the exact set the Console names. `DBSNMP` is a CDB common
user, so issue the grants from the root with `CONTAINER=ALL` to cover the CDB and
every PDB at once — e.g. `grant create procedure to DBSNMP container=all;`,
`grant select any dictionary to DBSNMP container=all;`,
`grant select_catalog_role to DBSNMP container=all;` plus the advisor grants the
prompt lists. Reopen Performance Hub.
**See:** [Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm)
**Status:** resolved.

## KB-116 — DBSNMP re-locks after rotation: `ORA-28000` lock loop from the local Cloud Agent (observability-db)

**Symptom:** After rotating the `DBSNMP` password, DBM monitoring goes green
briefly then flips to **Stopped**, OPSI collection stalls "Needs attention", and
the account status cycles `OPEN → LOCKED` within minutes (`ORA-28000 - account is
locked`).
**Root cause:** On Base Database Service the **local Oracle Cloud Agent** also
authenticates as `DBSNMP` using the password set at provisioning. Rotating the
password without updating that consumer leaves it retrying the old password,
tripping the profile's `FAILED_LOGIN_ATTEMPTS` and locking the shared account —
which takes DBM and OPSI down with it.
**Fix:** Break the lock loop by aligning every `DBSNMP` consumer on the new
password (or move DBM/OPSI to a dedicated monitoring user so the Cloud Agent and
DBM don't share one account); then unlock once. Rotating a **shared** DB account
without finding every consumer guarantees a re-lock.
**See:** [Database Management](https://docs.oracle.com/en-us/iaas/database-management/home.htm)
**Status:** resolved.

## KB-117 — OPSI insight reported `NOT_FOUND` while it is actually ACTIVE — list is non-deterministic (observability-db)

**Symptom:** A check reports an OPSI Database Insight `NOT_FOUND` for a CDB/PDB
even though `opsi database-insights list … --lifecycle-state ACTIVE` shows it
`ACTIVE` with `database-connection-status: SUCCESS`.
**Root cause:** A single `database-insights list` call passing the **full**
lifecycle-state set together with `--all` can return inconsistent results
call-to-call (the full set, a partial set, or an exit-0 **empty** list) for the
same compartment. Matching a target against one such flaky list yields false
`NOT_FOUND`.
**Fix:** Don't trust a single broad list as proof of absence. Resolve the specific
insight by `--database-id` (or `get`), and re-list / retry before concluding it is
missing — an empty list is inconclusive, not authoritative.
**See:** [Operations Insights](https://docs.oracle.com/en-us/iaas/operations-insights/home.htm)
**Status:** resolved.

## KB-118 — A stopped/unreachable Autonomous DB stalls app startup ~60s (autonomous-db)

**Symptom:** An application that connects to an ADB hangs ~60 seconds on startup
(or every request) when the ADB is `STOPPED` or unreachable, instead of failing
fast or degrading.
**Root cause:** The wallet/DSN ships `retry_count=20` (and a retry delay), so the
Oracle driver dutifully retries the dead endpoint for ~a minute before giving up.
A startup connection probe with no time budget inherits that full retry window.
**Fix:** Bound every startup connection probe to a hard wall-clock timeout (e.g.
8s). On failure, make the behavior an explicit env-driven choice: dev/staging →
fall back to local SQLite so the app still boots; production → fail fast so the
outage is never silently masked. Confirm the ADB state first with
`oci db autonomous-database get … --query 'data."lifecycle-state"'` (or
`./scripts/oci_adb.sh`) and `start` it if it is `STOPPED`.
**See:** [Autonomous Database](https://docs.oracle.com/en-us/iaas/autonomous-database/index.html)
**Status:** resolved.

## KB-119 — `--whitelisted-ips` replaces the whole ACL, not appends (autonomous-db)

**Symptom:** Adding one client IP to an ADB with `update --whitelisted-ips` either
locks out every previously-allowed client, or (with `[]`) silently opens the DB to
all sources.
**Root cause:** `--whitelisted-ips` is **set/replace** semantics — it overwrites
the entire access-control list with exactly what you pass. It does not append, and
an empty list removes ACL restriction entirely.
**Fix:** Always `get` the current list first
(`--query 'data."whitelisted-ips"'`), then pass the full set of keepers **plus**
the new entry in one `run_action --risk in-place` update. Entries may be CIDRs or VCN/subnet
OCIDs. Review carefully before ever passing `[]`.
**See:** [Network access: ACLs & private endpoints](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/autonomous-network-access.html)
**Status:** resolved.

## KB-120 — SQLAlchemy `oracle+cx_oracle://` fails; use `oracle+oracledb://` (autonomous-db)

**Symptom:** A SQLAlchemy engine for an ADB raises `ModuleNotFoundError: cx_Oracle`
or `Can't load plugin: sqlalchemy.dialects:oracle.cx_oracle` on a modern install,
even though the wallet and DSN are correct.
**Root cause:** `cx_Oracle` has been superseded by `python-oracledb`. The legacy
dialect prefix `oracle+cx_oracle://` requires the old driver (and Instant Client);
`python-oracledb` registers the `oracle+oracledb://` dialect and runs in thin mode
with no Instant Client.
**Fix:** Use `oracle+oracledb://{user}:{password}@{dsn}` and pass the wallet via
`connect_args={"config_dir": TNS_ADMIN, "wallet_location": TNS_ADMIN,
"wallet_password": …}`. Keep `pool_pre_ping=True` + `pool_recycle=3600` so the ADB
idle-session timeout never hands back a dead connection.
**See:** [Download connection info / wallet (mTLS & TLS)](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/connect-download-wallet.html)
**Status:** resolved.

## KB-121 — SQLcl/oracledb diagnostics hang ~60s on a stopped ADB (wallet retry_count) (autonomous-db)

**Symptom:** A read-only diagnostic query (SQLcl or python-oracledb) against an
Autonomous Database hangs ~60s and then errors when the DB is `STOPPED` or
unreachable, even though the SQL itself is trivial (`SELECT 1 FROM dual`).
**Root cause:** ADB wallets ship a `sqlnet.ora` / `tnsnames.ora` with long retry
settings (`retry_count=20`, generous connect timeouts) tuned for resilient app
connections. A diagnostic tool inherits them and dutifully retries 20 times before
giving up — turning a fast failure into a minute-long stall (related to KB-118 on
the app-startup side).
**Fix:** Copy the wallet to a runtime directory and rewrite the retry/timeout knobs
so diagnostics **fail fast**: `retry_count=1`, `retry_delay=0`,
`outbound_connect_timeout=10`, `tcp_connect_timeout=5`; point `TNS_ADMIN` at the
copy for the run and wrap the call in a hard wall-clock timeout (20–30s). Drive it
via env (`SQLCL_TNS_RETRY_COUNT`, `SQLCL_OUTBOUND_CONNECT_TIMEOUT`, etc.). Never
edit the original wallet in place.
**See:** [Download connection info / wallet (mTLS & TLS)](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/connect-download-wallet.html)
**Status:** resolved.

## KB-122 — In-DB diagnostics must stay read-only — no KILL/DDL/DML from a diagnostic path (autonomous-db)

**Symptom:** An automated or assisted "troubleshoot the database" flow is tempted to
resolve a blocker by issuing `ALTER SYSTEM KILL SESSION`, or to "fix" a plan by
gathering stats / dropping an index inline — a state-changing action fired from what
the user asked to be a diagnosis.
**Root cause:** Diagnostics and remediation are different risk classes. Reading
`V$`/`GV$`/`DBA_*`/`DBMS_XPLAN` is always safe; killing a session or running DDL/DML
can lose work, roll back transactions, or change plans for every other session.
Blending them removes the human checkpoint before an irreversible change.
**Fix:** Keep the diagnostic path strictly read-only (dynamic performance views +
`DBMS_XPLAN` only). Surface the finding (e.g. "root blocker SID 142") and hand any
mutation to a **separate, confirmation-gated** remediation (`run_action`,
or route to `oracle/skills` `db/`). Redact SQL text and bind values before sharing.
**See:** [Database Reference (V$ dynamic performance views)](https://docs.oracle.com/en/database/oracle/oracle-database/19/refrn/index.html)
**Status:** resolved.

## KB-123 — `autonomous-database create` is async; a timeout doesn't mean it failed (autonomous-db)

**Symptom:** `oci db autonomous-database create` times out or returns without a
usable OCID, so a deploy script assumes failure and either errors out or creates a
second duplicate database.
**Root cause:** Create is an asynchronous control-plane op — the resource enters
`PROVISIONING` and the CLI call can return (or hit its read timeout) before the DB
reaches `AVAILABLE`. Treating "no clean OCID returned" as "not created" causes
double-creation.
**Fix:** Make create idempotent. Before creating, `list --display-name <NAME>
--query "data[?\"lifecycle-state\"!='TERMINATED' && …].id | [0]"` and reuse a
non-terminated match. After create, if the OCID is missing or the call timed out,
**re-discover by display name** with the same list query before assuming failure,
then poll `lifecycle-state` to `AVAILABLE`.
**See:** [`oci db autonomous-database` CLI reference](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/db/autonomous-database.html)
**Status:** resolved.

## KB-124 — ADB `--db-name` is globally unique per region; collisions need a retry (autonomous-db)

**Symptom:** `create` fails with `db-name ... already in use` (or `dbName ...
already in use`), even though no database of that name is visible in the current
compartment.
**Root cause:** `--db-name` must be unique across the **whole region/tenancy**, not
just the compartment, and is limited to ≤14 alphanumeric characters. A name used by
any other ADB (including in another compartment) collides.
**Fix:** Catch the collision and retry with a randomized name (e.g. `db$RANDOM` /
`aaf$((RANDOM%9000+1000))`), preserving the friendly `--display-name`. Keep
`--db-name` ≤14 chars, alphanumeric, starting with a letter. Distinguish this
(retry) from `not currently enabled for this tenancy` (request quota, hard stop)
and `InvalidParameter` (bad tier args, fix and retry).
**See:** [`oci db autonomous-database` CLI reference](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/db/autonomous-database.html)
**Status:** resolved.

## KB-125 — Private-endpoint ADB needs a VCN DNS label and listens on TCP 1522 (autonomous-db)

**Symptom:** Creating an ADB with `--subnet-id`/`--private-endpoint-label` fails or
silently falls back to a public endpoint; or an app on the VCN can't reach a
private-endpoint ADB even though the subnet route looks correct.
**Root cause:** A private endpoint requires the VCN (and subnet) to carry a **DNS
label**, which is set at VCN/subnet creation and is **immutable** — a VCN created
without one can never host a private endpoint. Separately, the ADB private endpoint
listens on **TCP 1522**, not the 1521 people reflexively open.
**Fix:** Verify the VCN DNS label before provisioning; if absent, recreate the VCN
with `--dns-label` (or fall back to a public endpoint + `--whitelisted-ips` ACL).
Open `client-subnet → ADB-PE:1522` in the NSG/security list. Confirm reachability
with the private DSN from a host that has a route into the VCN.
**See:** [Network access: ACLs & private endpoints](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/autonomous-network-access.html)
**Status:** resolved.

## KB-126 — OCI `list` returns terminated resources unless you filter `lifecycle-state` (observability-db)

**Symptom:** An existence check finds a `DELETED`/terminated `<RESOURCE>` (e.g. an APM domain), skips creation, then verification fails because nothing usable exists.
**Root cause:** OCI `list` APIs return resources in **all** lifecycle states by default, including `DELETED`/`TERMINATED`.
**Fix:** Always pass `--lifecycle-state ACTIVE` (or filter client-side on `"lifecycle-state"`) when listing to test for existence — applies to APM domains, instances, VCNs, databases, buckets, etc.
**See:** [Configure APM domains](https://docs.oracle.com/en-us/iaas/application-performance-monitoring/doc/configure-apm-domain.html)
**Status:** resolved.

## KB-127 — Intermittent 404s behind an OCI Load Balancer from a stale "zombie" backend (networking-compute)

**Symptom:** Requests to an LB-fronted host flap between correct responses and HTTP 404 at a fixed ratio, with no per-client pattern; re-applying routing never converges.
**Root cause:** The backend set still contains a stale backend (old endpoint `<IP>:<PORT>`) whose health check passes but which serves an old app that 404s newer routes; round-robin sends ~1/N requests to it.
**Fix:** Inspect the backend set, find the backend whose `<IP>:<PORT>` matches no current node/pod, and remove it: `oci lb backend delete --load-balancer-id <LB_OCID> --backend-set-name <BACKEND_SET> --backend-name "<STALE_IP>:<PORT>" --force`. Prefer a stable backend model over pod-direct backends.
**See:** [Managing backend sets](https://docs.oracle.com/en-us/iaas/Content/Balance/Tasks/managingbackendsets.htm)
**Status:** resolved.

## KB-128 — VCN/subnet deletion deadlocks until route-table rules referencing gateways/LPGs are cleared (networking-compute)

**Symptom:** VCN teardown cascades into `409` failures — route tables, LPGs, NAT/Internet gateways, and subnets all refuse to delete.
**Root cause:** Route rules reference gateways/LPGs/DRGs as `network-entity-id`; OCI blocks deleting any resource still referenced by a route rule, so deleting in the wrong order deadlocks.
**Fix:** Clear **all** route-table rules first, then delete in order: DRG attachments → LPGs → mount targets/LBs → subnets → NSGs → gateways → route tables → security lists → VCN.
**See:** [Deleting a VCN](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/delete_vcn.htm)
**Status:** resolved.

## KB-129 — Service limits must be queried against the tenancy root OCID, not a child compartment (cost)

**Symptom:** `oci limits value list` returns empty/`404`/`400` when given a child `<COMPARTMENT_OCID>`.
**Root cause:** Service limits are a tenancy-level resource; `limits value list` only resolves against the root `<TENANCY_OCID>`. Only `limits resource-availability get` is compartment-scoped.
**Fix:** Query `limits value list` with the tenancy OCID; reserve compartment OCIDs for `resource-availability get`.
**See:** [Service limits](https://docs.oracle.com/en-us/iaas/Content/General/Concepts/servicelimits.htm)
**Status:** resolved.

## KB-130 — Dynamic-group `list` never returns `matching-rule` — use get-by-id to verify (iam-admin)

**Symptom:** `oci iam dynamic-group list` shows `matching-rule: null` for every dynamic group even when valid rules exist.
**Root cause:** The Identity `ListDynamicGroups` API omits `matchingRule`; it is only populated by `GetDynamicGroup` (single-resource GET by ID).
**Fix:** Verify a dynamic group's rule with `oci iam dynamic-group get --dynamic-group-id <DG_OCID>`, never via `list`.
**See:** [Managing dynamic groups](https://docs.oracle.com/en-us/iaas/Content/Identity/dynamicgroups/managingdynamicgroups.htm)
**Status:** resolved.

## KB-131 — Apple-Silicon Docker builds produce arm64 images that fail `exec` on amd64 OCI compute (networking-compute)

**Symptom:** Container exits immediately with `exec format error`; `docker inspect` shows `Architecture: arm64` on an amd64 host.
**Root cause:** M-series Macs default Docker builds to `linux/arm64`, while OCI Compute shapes run `linux/amd64`.
**Fix:** Build with explicit platform targeting: `docker buildx build --platform linux/amd64 ...` (or multi-arch); verify with `docker manifest inspect` before deploy.
**See:** [Pushing images using the Docker CLI](https://docs.oracle.com/en-us/iaas/Content/Registry/Tasks/registrypushingimagesusingthedockercli.htm)
**Status:** resolved.

## KB-132 — OCI Monitoring custom metric namespaces must be lowercase (observability-db)

**Symptom:** Alarm/metric creation fails with a validation error when the namespace contains uppercase letters.
**Root cause:** Custom metric namespaces must match `^[a-z][a-z0-9_]*[a-z0-9]$` — uppercase is rejected.
**Fix:** Use an all-lowercase namespace (e.g. `my_app_metrics`); also supply required alarm params such as `--pending-duration`.
**See:** [Publishing custom metrics](https://docs.oracle.com/en-us/iaas/Content/Monitoring/Tasks/publishingcustommetrics.htm)
**Status:** resolved.

## KB-133 — OCI Streaming rejects stream-create payloads that set both `compartment_id` and `stream_pool_id` (events-functions)

**Symptom:** `ServiceError: InvalidParameter: Cannot specify both compartment id and stream pool id`.
**Root cause:** When creating a stream inside a specific stream pool, OCI Streaming forbids passing `compartment_id` alongside `stream_pool_id`.
**Fix:** Pass only `stream_pool_id` when targeting a pool; supply `compartment_id` only on the default/no-pool create path.
**See:** [Creating stream pools](https://docs.oracle.com/en-us/iaas/Content/Streaming/Tasks/creating-stream-pools.htm)
**Status:** resolved.

## KB-134 — OCI Terraform provider needs `auth = "SecurityToken"` for session-token profiles (resource-manager)

**Symptom:** `terraform plan/apply` fails with `user: missing from config` when the profile uses session (`oci session authenticate`) auth.
**Root cause:** The provider's `auth` defaults to `APIKey`, requiring `user`/`fingerprint`/`key_file`; session profiles need `auth = "SecurityToken"` (and `InstancePrincipal` for instance auth).
**Fix:** Add an `auth_mode` variable, set `auth = var.auth_mode` in provider blocks, and map the CLI auth mode to the Terraform value at apply time.
**See:** [Configuring the Terraform provider](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/configuring.htm)
**Status:** resolved.

## KB-135 — Parallel deploys sharing one Terraform state hit a state-lock conflict (resource-manager)

**Symptom:** `Terraform acquires a state lock ...` error when two invocations touch a shared dependency at once.
**Root cause:** Concurrent applies against the same state directory (e.g. dependent B triggers shared A while A is already applying) collide on the lock.
**Fix:** Apply shared dependencies sequentially before dependents, or use a single dependency-ordered apply; never run concurrent applies on one state backend.
**See:** [Resource Manager](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Concepts/resourcemanager.htm)
**Status:** resolved.

## KB-136 — Autonomous DB DSN must be the `tnsnames.ora` alias, not the full `service_name` (autonomous-db)

**Symptom:** App crashes with `DPY-4000: unable to find "<PREFIX>_<DBNAME>_low" in .../tnsnames.ora`, even though the DSN matches the Console "Connection Strings" value.
**Root cause:** The Console shows the full connect descriptor whose `service_name` is `<tenancyprefix>_<dbname>_low`, but the wallet's `tnsnames.ora` alias is just `<dbname>_low` (lowercase, no prefix).
**Fix:** Set the DSN to the short alias (e.g. `<dbname>_low`); `oracledb` resolves it against `tnsnames.ora` in the wallet dir. Derive it as `${db_name,,}_low` rather than copy-pasting the connection string.
**See:** [Download connection info / wallet](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/connect-download-wallet.html)
**Status:** resolved.

## KB-137 — Autonomous DB password-history policy blocks reusing recent passwords (autonomous-db)

**Symptom:** `ORA-28007: the password cannot be reused` (or API: "cannot be one of the last four passwords") on admin password reset or `ALTER USER`.
**Root cause:** ADB enforces a password-history policy — the last 4 passwords cannot be reused within 24 hours, via both CLI `admin-password-reset` and SQL.
**Fix:** Reset to a wholly new password, then update every dependent secret/connection string and restart consumers to pick up the change.
**See:** [Manage the ADMIN user](https://docs.oracle.com/en-us/iaas/autonomous-database-serverless/doc/manage-users-admin.html)
**Status:** resolved.

## KB-138 — Default NSG/security-list rules left open to `0.0.0.0/0` expose management ports (security-compliance)

**Symptom:** SSH and management ports are reachable from anywhere because ingress rules use `0.0.0.0/0`.
**Root cause:** Deploy defaults open admin ports to the whole internet instead of a scoped CIDR.
**Fix:** Replace `0.0.0.0/0` ingress with a specific operator CIDR (e.g. `<ALLOWED_INGRESS_CIDR>`, ideally a `/32`); parameterize the allowed CIDR and audit NSGs/security lists regularly.
**See:** [Network security groups](https://docs.oracle.com/en-us/iaas/Content/Network/Concepts/networksecuritygroups.htm)
**Status:** resolved.

## KB-139 — Service-managed private-endpoint VNICs block subnet and VCN deletion (networking-compute)

**Symptom:** `409 Conflict` deleting a subnet/VCN because private-endpoint VNICs (e.g. `PE-<SERVICE>-*`) are still attached.
**Root cause:** A managed service (OpenSearch, ORM private endpoint, etc.) created private endpoints in the subnet; deleting only the reference leaves the underlying VNICs, which block teardown.
**Fix:** Delete the owning managed resource first (poll to `DELETED`) so its private-endpoint VNICs detach before deleting the subnet/VCN; ensure every created resource has matching destroy logic.
**See:** [Deleting VCNs](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/delete_vcn.htm)
**Status:** resolved.

## KB-140 — Log Analytics CLI moved source-association commands, breaking older scripts (log-analytics)

**Symptom:** `Current OCI CLI does not support '--items' for entity add-associations`, then source associations are silently skipped.
**Root cause:** Newer OCI CLI moved associations to `oci log-analytics assoc upsert-assocs --items` and source discovery to `source list-sources`, deprecating the legacy `entity add-associations`/`source list`.
**Fix:** Detect CLI capability and prefer `assoc upsert-assocs` with `[{"entityId":...,"sourceName":...}]`, falling back to the legacy command only when present.
**See:** [Log Analytics CLI command reference](https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/cmdref/log-analytics.html)
**Status:** resolved.

## KB-141 — Data Safe `list_audit_events` filters time via `scim_query`, not `time_started`/`time_ended` (data-safe)

**Symptom:** SDK error `list_audit_events got unknown kwargs: ['time_started', 'time_ended']`; audit activity stays empty.
**Root cause:** `DataSafeClient.list_audit_events()` does not accept `time_started`/`time_ended`; time filtering is only supported through the `scim_query` parameter.
**Fix:** Build an RFC3339 window and pass it via `scim_query`, e.g. `(auditEventTime ge "<START>") and (auditEventTime le "<END>")`, with `sort_by="auditEventTime"`; inspect the SDK's expected kwargs before adding optional filters.
**See:** [Data Safe audit reports](https://docs.oracle.com/en-us/iaas/data-safe/doc/audit-reports.html)
**Status:** resolved.

## KB-142 — Database Management AWR on Autonomous DB needs full diagnostics or valid named credentials (observability-db)

**Symptom:** DB Management pages show failed AWR views even though `database-management-status=ENABLED`.
**Root cause:** Basic DB Management enablement on ADB does not grant AWR access; `list_awr_dbs` still fails without the full Diagnostics & Management feature or with an invalid named credential (`ORA-01017`/`InvalidDatabaseCredentials`).
**Fix:** Enable full diagnostics and supply a valid named credential; classify responses (`requires_full_diagnostics`, `invalid_named_credential`, `not_authorized`) and refresh credentials after enablement.
**See:** [Enable Database Management for Autonomous Databases](https://docs.oracle.com/en-us/iaas/database-management/doc/enable-database-management-autonomous-databases.html)
**Status:** resolved.

## KB-143 — IMDS reachability probe false-positive selects instance-principal auth off-instance (iam-admin)

**Symptom:** Tooling on a laptop picks `instance_principal` then fails at `<IMDS_ENDPOINT>/opc/v2/identity/cert.pem` with a connect timeout.
**Root cause:** A naive `curl` HTTP-200 probe of the IMDS link-local address passes because VM/Docker link-local routing answers, so auto-auth wrongly resolves to instance principal.
**Fix:** Validate the probe body against an OCI region pattern (`^[a-z]{2,3}-[a-z]+-[0-9]+$`) from `/opc/v1/instance/region`; fall through to profile auth otherwise. Override with `export OCI_AUTH_MODE=profile` and clear any stale IMDS cache.
**See:** [Calling services from an instance](https://docs.oracle.com/en-us/iaas/Content/Identity/Tasks/callingservicesfrominstances.htm)
**Status:** resolved.

## KB-144 — OKE app service stays `EXTERNAL-IP <pending>` behind shared ingress (iam-oke)

**Symptom:** An OKE workload already reachable through nginx ingress has a
`Service type=LoadBalancer` stuck at `EXTERNAL-IP <pending>`, or OCI keeps trying
to create/delete a per-app load balancer.
**Root cause:** The app should be exposed as `ClusterIP` behind the shared
ingress; a direct LB service consumes quota, can bypass ingress auth, and may
retain stale cloud-controller finalizers from an older exposure model.
**Fix:** Convert the service manifest to `type: ClusterIP`, keep the public route
on Ingress, remove obsolete LB annotations/finalizers only after confirming the
old LB is not the active edge, and verify DNS points to the shared ingress LB.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-145 — OKE LoadBalancer returns 502 / backend `CRITICAL` from wrong LB subnet rules (iam-oke)

**Symptom:** Pods are ready and in-cluster service traffic works, but a new OCI
LoadBalancer-backed service returns 502 or backend health stays `CRITICAL`.
**Root cause:** The LB subnet or service annotation points at a subnet/security
list that cannot reach worker nodes on kube-proxy health (`10256`) and NodePort
range (`30000-32767`), or the subnet annotation is missing and the controller
chooses an unsuitable subnet.
**Fix:** Set `service.beta.kubernetes.io/oci-load-balancer-subnet1` to the
intended LB subnet; allow LB subnet egress to node CIDR on `10256` and
`30000-32767`; allow node subnet ingress from LB CIDR on the same ports; then
recheck backend health.
**See:** [Load Balancer](https://docs.oracle.com/en-us/iaas/Content/Balance/home.htm)
**Status:** resolved.

## KB-146 — OKE HTTPS listener stays plain TCP when only a certificate OCID is set (iam-oke)

**Symptom:** `https://<APP_HOST>` fails or the OCI LB listener is `TCP-443` with
no SSL configuration even though the service has a certificate OCID annotation.
**Root cause:** For the OKE service-controller path, frontend TLS should be
driven by a namespace-local Kubernetes TLS secret and the OCI LB TLS-secret
annotations. Importing a cert into OCI Certificates Service alone does not
guarantee the Kubernetes-created listener becomes HTTPS.
**Fix:** Create a Kubernetes TLS secret in the service namespace and annotate
the service with backend protocol `HTTP`, SSL ports `443`, and
`service.beta.kubernetes.io/oci-load-balancer-tls-secret: <TLS_SECRET>`.
**See:** [Load Balancer](https://docs.oracle.com/en-us/iaas/Content/Balance/home.htm)
**Status:** resolved.

## KB-147 — OKE rollout fails from OCIR auth, stale Docker creds, or token propagation (iam-oke)

**Symptom:** Pods show `ImagePullBackOff`, `pull access denied`, or
`unauthorized: authentication required`; remote builders may fail `docker push`
or pull even after a token was created.
**Root cause:** OCIR repositories are private by default; image-pull secrets are
namespace-local; cross-tenancy pulls need registry-tenancy credentials; auth
tokens take 30-60 seconds to propagate; remote builders may keep stale Docker
credential helpers or cached credentials.
**Fix:** Verify the exact image tag and architecture, recreate the namespace's
`docker-registry` pull secret with registry-tenancy credentials, wait after new
auth-token creation, clear stale builder Docker config when needed, and test a
pull from the target environment before rolling.
**See:** [Container Registry](https://docs.oracle.com/en-us/iaas/Content/Registry/home.htm)
**Status:** resolved.

## KB-148 — ZPR visibility dashboard empty while custom logs have records (zpr)

**Symptom:** ZPR collector records appear in OCI Logging, but Log Analytics
dashboards show no rows or parse errors.
**Root cause:** Logging ingestion and Log Analytics content are separate legs.
The custom JSON source/parser/fields, Log Analytics log group upload policy, or
Service Connector Hub target can be missing even when custom log writes work.
**Fix:** Validate OCI Logging first; then parse every Log Analytics dashboard
query, create fields before parser/source, verify the Connector Hub target has
`LOG_ANALYTICS_LOG_GROUP_UPLOAD_LOGS`, and only then import dashboards.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-149 — OPSI list flaps cause false Database Insight `NOT_FOUND` (dbm-opsi)

**Symptom:** Validation reports OPSI Database Insight `NOT_FOUND` while the OCI
Console or a previous run shows the insight ACTIVE.
**Root cause:** Aggregated `database-insights list` calls can return incomplete
or empty windows. Treating a single empty list as authoritative produces false
absence.
**Fix:** Prefer `oci opsi database-insights get --database-insight-id
<DATABASE_INSIGHT_OCID>` when the ID is known. Otherwise query one lifecycle
state per call, union by insight OCID, and return UNKNOWN rather than NOT_FOUND
when reads are empty, inconsistent, or incomplete.
**See:** [Operations Insights](https://docs.oracle.com/en-us/iaas/operations-insights/home.htm)
**Status:** resolved.

## KB-150 — DBCS/Base DB Log Analytics ingestion needs a Management Agent-backed entity (dbm-opsi)

**Symptom:** Log Analytics source association for database alert/audit/host logs
fails with entity-not-ready errors, or created entities never ingest rows.
**Root cause:** For DBCS/Base DB log ingestion, DBM/OPSI enablement alone is not
an ingestion path. Source associations require a Management Agent-backed entity
or an existing valid ingestion entity.
**Fix:** Install/configure Management Agent with the required plugins or supply
existing Management Agent-backed entity OCIDs. Use canonical built-in source
names and current `oci log-analytics assoc upsert-assocs --items file://...`
payloads; do not auto-create detached entities as a workaround.
**See:** [Log Analytics](https://docs.oracle.com/en-us/iaas/log-analytics/home.htm)
**Status:** resolved.

## KB-151 — OCI Streaming Kafka consumers loop on metadata with modern protocol versions (events-functions)

**Symptom:** A Kafka receiver authenticates to OCI Streaming but repeatedly logs
metadata updates and never joins the consumer group or fetches records.
**Root cause:** OCI Streaming's Kafka-compatible endpoint implements the Kafka
1.0 protocol surface. Some clients default to newer Metadata/Fetch API minimums
and reject the broker's lower max versions.
**Fix:** Pin the receiver/client protocol to Kafka `1.0.0`, and use the stream
pool's `endpoint-fqdn` cell endpoint as bootstrap rather than the generic
regional Streaming endpoint.
**See:** [Streaming Kafka API configuration](https://docs.oracle.com/en-us/iaas/Content/Streaming/Tasks/kafkacompatibility_topic-Configuration.htm)
**Status:** resolved.

## KB-152 — OKE monitoring UI says latest telemetry unknown despite live metrics (iam-oke)

**Symptom:** OCI Kubernetes Monitoring shows `Invalid Date`, blank CPU/memory, or
`Latest telemetry Unknown`, while collector pods/jobs appear healthy.
**Root cause:** Metrics can be flowing under `mgmtagent_kubernetes_metrics` while
the Log Analytics Kubernetes Cluster entity metadata is malformed or stale
(`cluster`, `name`, `cluster_name`, `cluster_date`, `metrics_namespace`,
`timeLastDiscovered`).
**Fix:** Verify discovery upload logs and current MQL datapoints first. Then
repair the Kubernetes Cluster entity metadata with a real RFC3339 `cluster_date`,
matching cluster key/name, correct metrics namespace, and updated
`time-last-discovered`; force a discovery job and recheck.
**See:** [Kubernetes Engine (OKE)](https://docs.oracle.com/en-us/iaas/Content/ContEng/home.htm)
**Status:** resolved.

## KB-153 — Parallel Terraform init corrupts a shared plugin-cache view (terraform)

**Symptom:** `terraform init` succeeds in several working directories, but a
subsequent `validate` reports that the cached OCI provider package does not
match any checksum in the generated dependency lock file.
**Root cause:** Multiple `terraform init` processes wrote to the same
`TF_PLUGIN_CACHE_DIR` concurrently. The shared cache is not a concurrency
coordination mechanism, so consumers can observe inconsistent package and lock
metadata even though the configuration and signed provider are valid.
**Fix:** Initialize modules serially when sharing one plugin cache, or give each
parallel initializer an isolated cache. Recreate the affected disposable
working directories, run `init` again, and only then run `validate`; never work
around the mismatch by disabling checksum verification.
**See:** [OCI Terraform provider](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/)
**Status:** resolved.

## KB-154 — Terraform OCI provider source/address differs across roots (terraform)

**Symptom:** `terraform init` reports a provider-address migration or a lock-file
checksum/address mismatch in an example or packaged Resource Manager root.
**Root cause:** A root that uses or inherits OCI resources omitted an explicit
`required_providers` declaration, or a generated lock file retained a legacy
provider address.
**Fix:** Declare `oracle/oci` with the project-compatible version in every
Terraform root and OCI-using module. Reinitialize disposable `.terraform/`
directories serially, inspect `terraform providers`, and retain only reviewed
lock-file changes.
**See:** [OCI Terraform provider](https://docs.oracle.com/en-us/iaas/tools/terraform-provider-oci/latest/)
**Status:** resolved.

## KB-155 — OCI CLI profile does not automatically configure Terraform (terraform)

**Symptom:** OCI CLI commands succeed with a non-default profile while Terraform
uses `DEFAULT`, fails authentication, or targets a different identity.
**Root cause:** `OCI_CLI_PROFILE` configures the OCI CLI only; the Terraform OCI
provider does not inherit that environment variable as its config-file profile.
**Fix:** Expose an optional Terraform variable such as `oci_config_profile`, set
`config_file_profile` only when it is non-empty, and for local runs set both
`OCI_CLI_PROFILE=<PROFILE>` and `TF_VAR_oci_config_profile=$OCI_CLI_PROFILE`.
Leave it empty for Resource Manager and principal-based authentication.
**See:** [Terraform provider configuration](https://docs.oracle.com/en-us/iaas/Content/dev/terraform/configuring.htm)
**Status:** resolved.

## KB-156 — Resource Search CLI uses `--query-text`, not `--search-query` (cli)

**Symptom:** `oci search resource structured-search --search-query ...` fails
with `No such option` despite a valid structured query.
**Root cause:** The OCI CLI command names its required structured-query flag
`--query-text`; similarly, free-text search uses `--text`.
**Fix:** Run `oci search resource structured-search --help` for the installed
CLI version, then use `--query-text "query <type> resources where ..."`. Redact
all returned resource summaries before sharing them.
**See:** [OCI Search](https://docs.oracle.com/en-us/iaas/Content/Search/Concepts/queryoverview.htm)
**Status:** resolved.

## KB-157 — VCN teardown must remove references before gateways (networking-compute)

**Symptom:** Deleting a service gateway returns `InvalidParameter` because a
route table still references it, even after all subnets are gone.
**Root cause:** OCI preserves route-table gateway references independently of
subnet lifecycle; the gateway cannot be deleted while a route rule points to it.
**Fix:** Delete owned subnets first, then custom route tables, service gateways,
NSGs, NAT gateways, and custom security lists. Delete the now-empty VCN last;
OCI removes its default DNS, DHCP, route-table, and security-list components.
**See:** [Deleting VCNs](https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/delete_vcn.htm)
**Status:** resolved.

## KB-158 — Resource Manager destroy needs terminal-state polling (resource-manager)

**Symptom:** A destroy job is accepted, but scripts either assume completion or
wait only for success and leave cleanup status unknown on failure.
**Root cause:** Resource Manager job creation is asynchronous and terminal
states include success, failure, and cancellation.
**Fix:** Capture the job identifier, poll its lifecycle state, and stop on every
terminal state. After success, run a tag-scoped, read-only resource inventory;
scheduled Vault/key deletion is a distinct OCI lifecycle state, not evidence of
an active stack resource.
**See:** [Resource Manager jobs](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Tasks/usingconsole.htm)
**Status:** resolved.

## KB-159 — Resource Manager source and runtime variables must advance together (resource-manager)

**Symptom:** A redeploy uses stale Terraform source or stale capacity/authentication
inputs even though a local runtime variables file was edited.
**Root cause:** A Resource Manager stack stores both its configuration archive and
its variables. Editing an uncommitted local JSON file does not update an existing
stack, while uploading a new archive without the reviewed runtime values can
produce an unintended plan.
**Fix:** Treat one uncommitted runtime variables file as the stack lifecycle
record. Before every redeploy, resolve any auto modes into that file, upload the
archive and sanitized variables together with `stack update`, then create and
review a fresh plan. Keep `oci_config_profile` local-only; remove it from the
uploaded copy so Resource Manager uses its principal.
**See:** [Updating a stack](https://docs.oracle.com/en-us/iaas/Content/ResourceManager/Tasks/update-stack.htm)
**Status:** resolved.

## KB-160 — Reuse an active OKE cluster instead of recreating it (resource-manager)

**Symptom:** A redeploy risks creating a second OKE cluster when the intended
private cluster is already active.
**Root cause:** A generic install path creates a stack without first checking the
target compartment for the expected active cluster identity.
**Fix:** Query the authoritative Container Engine cluster list by expected name
and require lifecycle state `ACTIVE` before installation. Exit with an explicit
reuse result when found; otherwise continue to the reviewed stack install. Do
not use a search-index record as proof of current lifecycle state.
**See:** [Listing clusters](https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/list-clusters.htm)
**Status:** resolved.

## KB-161 — OCI Run Command can fail before an in-VCN payload starts (compute)

**Symptom:** A Run Command execution is acknowledged but fails immediately with
an agent working-directory or generated-command-path error and exit code 127.
**Root cause:** The Compute Instance Run Command agent failed to materialize the
OCI-managed command source. The target instance and its plugin can still be
healthy; this is distinct from application bootstrap or network failure.
**Fix:** Check the command execution delivery state and agent plugin state before
diagnosing the payload. Retry with a source-script payload where appropriate. If
the managed source path remains absent, collect the redacted execution metadata
and use a supported alternate in-VCN observability path; do not expose SSH or a
private API endpoint as a workaround.
**See:** [Run commands on instances](https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/runningcommands.htm)
**Status:** unresolved; requires OCI agent-service remediation when repeated.

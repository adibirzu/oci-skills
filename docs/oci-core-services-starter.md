# OCI Skills — Core Services Starter

This starter set is an operator map, not a deployment runbook. It covers the first seven foundational skill domains in this pack. All examples are offline guidance until a named tenancy, region, compartment, and owner are confirmed.

![Nimb, OCI foundation map](../assets/oci-skills-illustrations/02-core-services-foundation-map-v2.png)

## How to use this guide

Start by identifying the service domain that owns the resource. Use the matching skill for its read-first workflow, then hand work across domains instead of using one broad, unsafe command path. For live work, confirm the target context first and keep durable changes under Terraform ownership where applicable.

```bash
./scripts/oci_preflight.sh -c <COMPARTMENT_OCID>
python3 ./scripts/kb_lookup.py "<symptom words>"
```

The commands above are only target discovery and knowledge lookup; they do not prove provider acceptance, customer approval, or release acceptance.

## 1. IAM and tenancy administration

**Use `oci-iam-admin` when:** creating or reviewing compartments, groups, dynamic groups, policies, budgets, quotas, tags, or Identity Domain integrations.

**Why it is core:** IAM defines who can do what, where, and with which resource identity. It is the first control plane boundary for every other service.

**How to use it:** inventory the compartment and existing policies first; scope grants to the smallest applicable compartment and resource family; use a dynamic group for workload identities; add budget and quota guardrails with new environments.

**Typical flow:** read the current policy set → identify broad tenancy-wide grants → propose a compartment-scoped policy → make the approved additive change through `run_action` → re-read the effective grants.

**Key details:** treat credentials, auth tokens, OAuth/OIDC clients, certificates, and SCIM activation as credential-risk operations. A `409` usually means the named resource already exists; re-read rather than blindly retrying.

## 2. Networking and compute

**Use `oci-networking-compute` when:** working with VCNs, subnets, routing, gateways, NSGs, load balancers, DNS, certificates, compute instances, VNICs, and attached volumes.

**Why it is core:** it establishes the private path through which workloads communicate and the compute that runs them.

**How to use it:** trace the full connection path before changing anything: source and destination → NSG/security list → route table/gateway → subnet public-IP policy → VNIC or load-balancer health. For a new VM, check capacity, image, limits, lifecycle state, and network policy before launch.

**Typical flow:** list the existing rules → identify duplicates or shadowing → add the narrowest source/protocol/port rule → re-list → test the intended path.

**Key details:** never open management ports to the internet by default. Keep production workloads and load balancers private unless an intentional, reviewed edge design requires otherwise. Explicitly decide boot-volume preservation before termination.

## 3. Storage and data protection

**Use `oci-storage` when:** managing Object, Archive, File, Block, or Boot Storage; lifecycle/retention/versioning; replication; snapshots; backups; clones; or pre-authenticated requests.

**Why it is core:** storage choices define availability, recovery, sharing, and retention for workload data.

**How to use it:** begin with data classification, owner, RPO, and RTO. Read encryption, public-access, retention, versioning, replication, and backup state before proposing a change. Prefer Terraform for durable storage configuration.

**Typical flow:** inventory a bucket or volume group → check protection state → choose lifecycle, backup, or replication policy → apply only with matching approval → re-read and run a non-destructive recovery sample.

**Key details:** a pre-authenticated request is a credential, even when short lived. Retention reduction, version purge, and restore-overwrite paths are destructive; recovery depends on a separately verified version, snapshot, backup, clone, or replica.

## 4. Autonomous Database

**Use `oci-autonomous-db` when:** provisioning or operating ATP/ADW, scaling ECPU or storage, managing wallet/ACL settings, cloning/restoring, connecting an application, or conducting read-only in-database diagnostics.

**Why it is core:** Autonomous Database couples a managed database lifecycle with secure application connectivity and data-plane performance signals.

**How to use it:** inspect lifecycle state before an operation; keep wallets outside the repository; use `TNS_ADMIN` and a chosen service level with `python-oracledb` or SQLAlchemy; hand monitoring, DBM, and Ops Insights work to `oci-observability-db`.

**Typical flow:** discover by display name → confirm state and capacity → perform an approved lifecycle operation → wait for `AVAILABLE` → generate or rotate wallet outside the repository → smoke-test the application connection.

**Key details:** wallets are credentials. An ACL update replaces the list rather than appending to it. Private-endpoint ADB access uses TCP 1522 and requires the corresponding network path.

## 5. Observability

**Use `oci-observability-db` when:** operating Monitoring, Logging, APM, OpenTelemetry, alarms, dashboards, Service Connector Hub, notifications, or Prometheus-to-MQL translation.

**Why it is core:** metrics, logs, and traces give separate but correlatable evidence of behavior; alarms and dashboards turn that evidence into operator response.

**How to use it:** identify the service, resource, time window, and signal type first. For an alarm, verify the metric namespace, dimensions, query, and destination before creating it. For missing traces, resolve the APM domain and endpoint without exposing keys, then send a test and query again.

**Typical flow:** list current telemetry → validate source and query → add or repair the smallest configuration → re-list → verify data arrives and the notification path works.

**Key details:** an empty query result is inconclusive until region, permissions, time window, namespace, and pagination are checked. A translated MQL query or rendered dashboard remains a candidate until it parses and returns the intended series.

## 6. Security and compliance

**Use `oci-security-compliance` when:** handling Cloud Guard, Vault/KMS, WAF, Security Zones, Vulnerability Scanning, Audit, CIS/ISO-42001 evidence, or secure release controls.

**Why it is core:** it joins preventive controls, secret handling, detective signals, and release evidence around the workload.

**How to use it:** begin with a read-only posture or finding inventory; remediate in the owning domain; then re-check that the finding or control state changed. Store secrets in Vault and use workload/resource principals rather than embedded credentials.

**Typical flow:** list active Cloud Guard problems → identify the resource and owning compartment → make the narrow owning-domain change → re-list the problem → capture a redacted evidence packet.

**Key details:** WAF must use `BLOCK`, not only `OBSERVE`, when the intent is enforcement. Secret rotation creates a new version and requires consumer rollout. Security owns the policy and evidence decision; delivery-pipeline mechanics belong to `oci-developer-services`.

## 7. Cost and governance

**Use `oci-cost` when:** reporting spend, usage, budgets, forecasts, chargeback/showback, or cost-tracking tags.

**Why it is core:** FinOps connects technical architecture to sustainable operation and helps detect unexpected resource growth early.

**How to use it:** start read-only with a service or compartment view, then drill into the largest driver. Use cost-tracking tags for chargeback. Hand budget creation and alert mutations to `oci-iam-admin`.

```bash
./scripts/oci_cost.sh -d 30 -g DAILY
./scripts/oci_cost.sh -g MONTHLY -d 90
```

**Typical flow:** get a service-level snapshot → group by compartment or tag → investigate resource creation via Audit/Log Analytics → recommend a budget and 80% forecast alert → verify by re-running the snapshot.

**Key details:** Usage API results are tenancy scoped and can lag real time. Budget creation is a mutation; reporting is read-only. The budget list command is nested as `oci_cli budgets budget budget list`.

## Next core wave

After these foundations, extend the series into Kubernetes/OKE, Resource Manager/Terraform, developer services, events/functions, landing zones, disaster recovery, Data Safe, Log Analytics, ZPR, DBM/OPSI, and data-platform operations. Each should retain Nimb as the active reference character and make the mascot perform one operator decision rather than decorate a service icon.

## Evidence boundary

This guide is **code-backed**: it is derived from the repository skill contracts and contains no tenancy discovery, live OCI API call, or deployment. Any real environment result must be labelled separately as configured, locally verified, provider verified, or release accepted.

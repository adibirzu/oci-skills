# OCI observability, host telemetry, MQL, and alarm skills

## Objective

Provide OCI observability guidance and automation for every OCI customer,
without assuming Terraform, OCI Resource Manager, or an OCI Landing Zone.
Separate generic OCI service monitoring from Linux, Windows, and database
telemetry so each domain can evolve independently.

The completed capability includes:

- a tenancy-agnostic OCI service-metric and alarm catalog;
- independently versioned Linux and Windows host-observability skills;
- controlled Prometheus exporter updates and PromQL-to-OCI MQL mappings;
- deterministic review-only, OCI CLI, REST/Python SDK, Terraform, Resource
  Manager, and optional Landing Zone adapters;
- safe installation, upgrade, disable, re-enable, and removal behavior; and
- public-repository gates that reject customer or tenancy data.

Repository implementation and validation are offline by default. Optional live
validation accepts a caller-supplied runtime context, uses it only for the
current invocation, and never names, persists, or commits it. Live OCI
mutations remain subject to the repository preflight, ownership, approval, and
action gates.

## Skill topology

The completed pack exposes 27 canonical skills:

- `oci-observability` owns generic OCI Monitoring, Logging, APM,
  OpenTelemetry, alarms, Notifications, Service Connector Hub, dashboards,
  the OCI service-metric catalog, and interface adapters.
- `oci-linux-observability` owns Linux host discovery, `node_exporter`,
  Prometheus/OpenTelemetry collection and shipping, exporter updates,
  `node_*` metric semantics, PromQL-to-MQL recipes, host dashboards, alarms,
  and validation.
- `oci-windows-observability` owns Windows host discovery,
  `windows_exporter`, exporter compatibility and updates, `windows_*` and
  legacy `wmi_*` semantics, PromQL-to-MQL recipes, host dashboards, alarms,
  and validation.
- `oci-dbm-opsi` remains the sole owner for Database Management, Operations
  Insights, Performance Hub, AWR, ADDM, ASH, DBSNMP, and database insight
  lifecycle.
- `oci-observability-db` becomes a deprecated, asset-free compatibility
  router that directs requests to their final owner.

OCI service namespaces stay in `oci-observability`. Custom Linux and Windows
telemetry stays in the corresponding OS skill. Custom Prometheus metrics are
not part of the generic OCI service-alarm catalog.

A request is OS observability when it centers on a host operating system,
exporter, `node_*`, `windows_*`, legacy `wmi_*`, or host
CPU/memory/filesystem/disk/network telemetry.

## Canonical interface-neutral model

The service-alarm catalog is the sole source of alarm intent. A catalog record
contains:

- a stable alarm and service identifier;
- OCI namespace, exact metric identifier, unit, emission frequency, and
  supported dimensions;
- separate visualization MQL and Boolean alarm MQL;
- statistic, interval, threshold semantics, pending duration, severity,
  repeat policy, split-notification behavior, and message format;
- missing-data interpretation, runbook requirements, and notification
  destination requirements;
- direct Oracle source URL, verification timestamp, source fingerprint, and
  freshness state; and
- verification status: `verified`, `stale`, or `discovered-unverified`.

Deployment policy is separate from metric truth. The supported modes are:

- `review-only`;
- `cli-managed`;
- `api-managed`;
- `terraform-managed`;
- `resource-manager`; and
- `landing-zone-extension`.

Enablement is either `explicit` or `detected-services`. Production alarms
default to disabled in every mode until the customer makes that selection.
Catalog verification never implies deployment enablement.

Each existing or proposed resource is classified before a write:

- `create`;
- `adopt`;
- `already-managed`;
- `external`; or
- `unknown`.

`unknown`, ambiguous, or duplicate matches fail closed. Adoption and changes
of ownership require a reviewed action plan and explicit approval.

One deterministic generator converts the catalog and deployment policy into a
normalized action plan. All interface adapters consume that plan, preventing
CLI, API, Terraform, Resource Manager, or Landing Zone behavior from drifting.
Runtime identifiers are supplied separately and are never embedded in public
catalogs, fixtures, or golden files.

## Interface adapters and lifecycle

### Review-only

`review-only` is the default mode. It validates sources, catalog structure,
MQL, thresholds, destination requirements, ownership assumptions, and rendered
definitions without contacting or modifying OCI. It may produce:

- a human-readable review report;
- sanitized CLI command plans with `file://` JSON payload templates;
- REST request definitions and Python SDK request objects;
- Terraform inputs;
- a Resource Manager package; and
- optional Landing Zone extension inputs.

Generating an artifact does not claim ownership of any resource.

### OCI CLI

The CLI adapter:

1. performs paginated read-before-write inventory through `oci_cli`;
2. obtains current command details through the repository CLI-help helper;
3. stores complex payloads in temporary `0600` files and uses `file://`;
4. treats `409` as a possible existing resource, then lists and classifies
   again instead of blindly retrying creation;
5. observes OCI Monitoring throttling with bounded retries and backoff;
6. routes mutations through `run_action` with a matching preflight receipt;
   and
7. requires an exact approval identifier for destructive behavior.

Inventory spans the explicitly selected regions and compartments. Empty
results are inconclusive until scope, permissions, time range, spelling, and
service emission behavior have been checked.

### REST and Python SDK

The API adapter generates sanitized `CreateAlarmDetails` and
`UpdateAlarmDetails` models and equivalent REST payloads. It implements:

- pagination for list and history operations;
- retry tokens for idempotent create operations;
- ETag and `if-match` protection for update and delete operations;
- bounded retries using the SDK retry strategy where appropriate; and
- safe error classification without persisting raw responses.

Request IDs may be retained transiently as support metadata but are never
committed with live output. Credentials, signing material, signed requests,
and authentication headers are never rendered.

### Terraform

Terraform is one optional ownership adapter, not the default architecture.
When selected, it uses the official `oci_monitoring_alarm` resource and owns
only resources recorded in its state.

Brownfield resources require classification and import or adoption before
management. Plan results that delete or replace an existing alarm fail closed
until explicitly reviewed and approved. Local acceptance uses formatting,
provider-schema checks, `terraform init -backend=false`, and validation without
applying.

### OCI Resource Manager

Resource Manager uses the same Terraform module and cannot become a second
owner. Its controlled lifecycle is:

1. create or update a stack package;
2. run a plan job;
3. review redacted plan logs and ownership effects; and
4. apply using the reviewed plan job identifier.

Resource Manager state, plan files, raw logs, variables containing identifiers,
and credentials are sensitive runtime artifacts and are never committed.

### Landing Zone extension

Landing Zone integration is optional and intended only for customers who
already operate an applicable Landing Zone stack. The adapter supplies
compatible extension inputs without replacing stack state, redeclaring
resources, or assuming ownership.

Existing production resources must be inventoried and classified. Import,
adoption, or movement between stacks requires a separate reviewed plan.
The generic catalog, CLI, API, Terraform, and Resource Manager paths remain
fully usable without a Landing Zone.

### Notifications

Alarm generation validates an existing topic or stream and its supported alarm
message format. A subscription must be active before an alarm relies on it;
pending subscriptions are reported as incomplete.

Creating messaging infrastructure belongs to `oci-events-functions`. A test
publish is a separate live mutation and requires an approved validation window.

## Reusable resources

Common deterministic conversion stays in `scripts/promql_to_mql.py`. Both OS
skills use that pack-level utility, avoiding converter drift while retaining
independent metric catalogs.

```text
skills/oci-linux-observability/
├── SKILL.md
├── agents/openai.yaml
├── assets/exporter-lock.json
├── assets/host-dashboard-profile.json
├── assets/prometheus-mql-mappings.json
└── references/linux-host-monitoring.md

skills/oci-windows-observability/
├── SKILL.md
├── agents/openai.yaml
├── assets/exporter-lock.json
├── assets/host-dashboard-profile.json
├── assets/prometheus-mql-mappings.json
└── references/windows-host-monitoring.md

skills/oci-observability/
├── SKILL.md
├── agents/openai.yaml
├── assets/alarms/
│   ├── day-1-core.json
│   ├── day-2-platform.json
│   └── discovered.schema.json
├── assets/adapters/
├── assets/terraform/alarms/
└── references/monitoring-alarms.md
```

Pack-level scripts:

- `scripts/exporter_updates.py` checks stable upstream releases and produces a
  candidate lock-file change and validation report.
- `scripts/promql_to_mql.py` converts only explicitly supported expression
  shapes and resolves versioned catalog entries.
- `scripts/validate_mql_catalog.py` validates schema, metric kind, dimensions,
  units, arithmetic, alarm suitability, sources, and freshness.
- `scripts/generate_monitoring_alarms.py` generates the normalized action plan
  and selected interface artifacts.

All generated files are deterministic. Network discovery and live validation
are explicit modes; default tests require neither GitHub nor OCI.

## Controlled exporter updates

Exporter automation prepares and validates an update but does not perform an
unattended fleet upgrade:

```text
detect stable release
  -> verify upstream identity and checksums/signatures
  -> generate candidate lock change
  -> compare emitted metric schema and collector compatibility
  -> run PromQL/MQL/dashboard/alarm regression tests
  -> deploy to one explicitly selected canary
  -> validate exporter, scrape, ingestion, and MQL results
  -> require explicit promotion approval
  -> roll out in bounded batches
  -> roll back on a failed gate
```

The lock record contains the upstream repository, exact version, immutable
release URL, asset selector, platform and architecture, checksum source and
digest, signature policy, supported operating systems, collectors, previous
known-good version, and verification date. Installation never uses a mutable
`latest` artifact.

Release discovery can update only a candidate manifest. Canary and promotion
are separate actions. Promotion requires an exact approval identifier and
project-supplied inventory. Collector removals, metric renames, label changes,
or operating-system incompatibility block promotion until mappings and
dashboards are updated.

`adibirzu/oci-prometheus-otel-monitoring` is a deployment-behavior reference,
not a mutable version authority. Current pins are compared with official
upstream releases and recorded in verified lock files.

## Versioned PromQL-to-MQL mappings

Each mapping is machine-readable and records:

- stable mapping ID and owning operating system;
- source PromQL and normalized expression shape;
- exporter family and supported version range;
- source and ingested OCI metric names, metric kind, and unit;
- required labels, OCI dimensions, and pipeline renames;
- interval, statistic, grouping, arithmetic, and unit conversion;
- generated chart MQL and alarm-safe MQL when different;
- expected output unit, cardinality, and per-device or per-host semantics; and
- source documentation plus static and optional live-validation metadata.

Counters require `rate()` or another explicitly supported counter operation.
Gauges use an approved statistic such as `last()` or `mean()`. Ratios require
compatible stream dimensions. Disk busy time remains per device. Network byte
rates record the `* 8` conversion when displayed as bits per second.

Mappings remain candidates until the selected pipeline's exact emitted names
and dimensions are known. Schema drift invalidates dependent mappings,
dashboards, and alarms. The updater cannot promote a release with removed
metrics, renamed labels, changed units, or unsupported MQL.

Optional read-only validation can:

1. list metric definitions for a selected namespace;
2. confirm required dimensions without retaining their values;
3. execute candidate MQL over a bounded recent interval;
4. verify nonempty streams, units, cardinality, and grouping; and
5. emit only a redacted pass/fail receipt outside the repository.

This is supplementary evidence. Offline fixtures never prove a customer's
current telemetry.

## Service-alarm catalog and rollout tiers

The catalog is delivered in three coverage stages:

1. **Day 1 — core infrastructure:** verified candidate definitions for
   `oci_computeagent`, `oci_compute_instance_health`,
   `oci_compute_infrastructure_health`, `oci_blockstore`, `oci_vcn`,
   `oci_lbaas`, and `oci_nlb`.
2. **Day 2 — platform services:** verified candidate definitions for OKE,
   Functions, API Gateway, Streaming, and Object Storage.
3. **Day 3 — discovered namespaces:** disabled candidates for all namespaces
   discovered within an explicitly supplied runtime scope.

All stages remain disabled for production until `explicit` or
`detected-services` enablement is selected. Day 3 discovery never implies
correctness. A candidate remains `discovered-unverified` until namespace,
metric, dimensions, unit, statistic, threshold semantics, and MQL have
official-source or bounded live-query evidence.

Service-specific rules include:

- exact API Gateway identifiers selected from the current service reference
  and, during optional live validation, Metrics Explorer;
- exact Streaming names, including identifiers containing periods such as
  `PutMessagesLatency.Time`;
- intervals of at least one hour for Object Storage `ObjectCount` and
  `StoredBytes`; and
- no outage inference when an empty Object Storage bucket emits no metric
  data.

Thresholds are conservative, overridable examples rather than universal SLOs.
Missing telemetry and threshold breach are separate alarm definitions. Custom
Linux and Windows telemetry is excluded from this catalog.

## Documentation authority and freshness

Oracle service documentation and the current metric definitions exposed by
Metrics Explorer are authoritative for OCI service metrics. The source index
must link directly to:

- the MQL reference and Monitoring overview;
- alarm concepts, best practices, management, troubleshooting, history,
  suppressions, split notifications, and dimension states;
- Monitoring IAM policy reference;
- Monitoring CLI commands;
- Monitoring REST API and Python SDK models;
- Notifications topics, subscriptions, and publishing;
- the OCI Terraform provider; and
- Resource Manager stack and job lifecycle.

Every definition records a verification timestamp and source fingerprint.
Scheduled link and fingerprint checks mark changed or unavailable sources
`stale`; they never silently retain `verified`.

Metric identifiers, units, dimensions, and emission frequencies are exact.
CLI help, REST/SDK models, Terraform schemas, and Oracle service references are
validated independently. No missing Day 3 statistic, dimension, or threshold
is guessed.

## Linux workflow

1. Identify target hosts, operating-system release, `node_exporter` version,
   and collection path.
2. Inventory emitted `node_*` metrics and actual dimensions.
3. Convert only supported PromQL shapes.
4. Render the Linux OCI Metrics dashboard profile.
5. Validate CPU, memory, network, disk busy time, throughput, filesystem, and
   load panels.
6. Generate review-only alarm definitions by default.
7. Use the selected interface adapter and safety gates for any provisioning.
8. Re-query panels and alarm inputs after an approved change.

## Windows workflow

1. Identify target hosts, Windows release, `windows_exporter` version,
   collectors, and collection path.
2. Inventory emitted metrics before selecting current `windows_*` or legacy
   `wmi_*` names.
3. Confirm actual host, network-interface, and volume dimensions.
4. Convert only supported PromQL shapes.
5. Render the Windows OCI Metrics dashboard profile.
6. Validate CPU, memory, network, logical-disk, throughput, uptime, and process
   panels.
7. Use the selected interface adapter and safety gates for provisioning.
8. Re-query panels and alarm inputs after an approved change.

## Security and repository hygiene

Public assets contain only synthetic fixtures and `<PLACEHOLDER>` values.
Tests reject:

- OCIDs, public or private IP addresses, fingerprints, credentials, tokens, or
  signing material;
- private tenancy, profile, compartment, or project names;
- customer endpoints and raw metric dimension values;
- Terraform or Resource Manager state and plan files; and
- raw CLI, REST, SDK, Terraform, Resource Manager, or live-validation output.

Raw live responses may exist only in ignored, permission-restricted temporary
storage for the duration required to produce a redacted result. Generated
reports retain bounded booleans, counts, normalized public metric names, source
metadata, and safe error classes.

Before commit or push, the repository redaction gate scans tracked changes,
fixtures, generated examples, logs, and documentation. Optional validation
never names or persists the caller-supplied context.

## Failure behavior

- Reject unsupported PromQL joins, vector matching, offsets, subqueries,
  histogram quantiles, label rewriting, and negative-regex matchers.
- Treat generated MQL as a candidate until syntax, streams, dimensions,
  cardinality, and units are validated.
- Block gauge ratios with incompatible dimensions.
- Keep disk utilization per device; never sum device percentages into a host
  percentage.
- Treat empty results as inconclusive until scope, permissions, interval,
  spelling, ingestion, and service emission behavior are checked.
- Observe OCI Monitoring's tenancy-level operation throttling with bounded
  retries and backoff.
- Reject exporter promotion when a required metric, collector, label, unit, or
  MQL contract drifts.
- Reject enablement of stale or discovered-unverified definitions.
- Reject duplicate, ambiguous, external, or unknown ownership before mutation.
- Reject deletion, replacement, adoption, or ownership movement without a
  reviewed action plan and explicit approval.
- Never treat generated artifacts or local tests as live OCI proof.

## Installation lifecycle

Installation and upgrade preserve a reversible skill state:

- `disable` removes a skill from active discovery without deleting its
  installed payload or configuration metadata;
- `enable` restores the same installed skill;
- updates preserve the disabled state unless explicitly overridden;
- removal remains distinct from disablement; and
- source, installed-copy, and distribution-parity tests cover enable, disable,
  update, re-enable, and uninstall behavior.

The compatibility router remains discoverable during migration. It owns no
converter, dashboard, catalog, or implementation asset. The root router routes
new requests directly to the final owner.

## Implementation sequencing

The implementation plan must avoid assigning incompatible end states to one
task:

1. Create the dedicated topology while temporarily retaining compatibility
   assets.
2. Move OS assets to their Linux and Windows owners.
3. Remove migrated assets from `oci-observability-db` and assert that it is
   asset-free.
4. Add the canonical catalog and normalized action-plan model.
5. Add the review-only, CLI, REST/Python SDK, Terraform, Resource Manager, and
   Landing Zone adapters.
6. Add source freshness, MQL, ownership, and public-safety validation.
7. Complete the reversible installation lifecycle.
8. Run focused, full-suite, installation-parity, and leakage tests.
9. Perform independent review, reconcile the branch, retest, and merge into
   `main`.

## Verification

Repository acceptance requires:

1. Topology and routing tests for all canonical skills and the compatibility
   alias.
2. Converter golden tests for CPU, memory, network, disk, smoothing, and
   unsupported expressions.
3. Exporter-update tests for immutable pins, provenance, compatibility,
   canary, promotion, and rollback.
4. MQL schema and semantic tests distinguishing chart expressions from Boolean
   alarm expressions.
5. Catalog tests for exact metric names, intervals, dimensions, source
   fingerprints, freshness, and disabled production defaults.
6. Cross-adapter golden tests proving equivalent normalized intent.
7. CLI tests for help discovery, payload files, pagination, throttling,
   conflicts, and destructive gates.
8. REST/SDK tests for sanitized models, pagination, retry tokens, ETags,
   retries, and safe errors.
9. Terraform tests for ownership, import/adoption, replacement/deletion gates,
   formatting, schema, and offline validation.
10. Resource Manager tests for single ownership and reviewed plan-job binding.
11. Landing Zone tests proving optional, non-replacing integration.
12. Notification tests for destination compatibility and active subscription
    state.
13. Documentation liveness and source-fingerprint tests.
14. Synthetic-fixture and secret-leakage tests.
15. Clean install, upgrade, disable, re-enable, uninstall, copy-install, and
    distribution-parity tests.
16. Focused tests followed by the complete repository suite.

No live OCI access is required by default. Optional live validation is
read-only unless the user separately authorizes a mutation and satisfies all
safety gates.

## Completion criteria

- Generic OCI service monitoring works without Terraform or a Landing Zone.
- Every adapter consumes the same normalized catalog intent.
- Production alarms default to disabled until explicitly selected.
- Existing resources are classified before management and protected from
  accidental deletion, replacement, or duplicate ownership.
- Linux and Windows exporters, mappings, dashboards, and alarms evolve
  independently.
- Exporter updates fail closed on telemetry or MQL drift.
- Day 1 and Day 2 definitions are official-source grounded; Day 3 discoveries
  remain disabled until verified.
- CLI, API/SDK, Terraform, Resource Manager, and Landing Zone examples are
  deterministic, safe, and independently tested.
- The compatibility router is asset-free and provides a clear migration path.
- Installed skills can be disabled and re-enabled without loss.
- Public-repository gates detect sensitive or customer-specific data.
- All local validation passes before the implementation branch is merged into
  `main`.

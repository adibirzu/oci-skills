# Dedicated host observability, MQL, exporter, and alarm skills

## Objective

Separate operating-system monitoring from generic OCI observability and
database observability. Add independently evolvable Linux and Windows skills
while retaining compatibility for existing `oci-observability-db` callers.
Add a controlled exporter-update lifecycle, versioned Prometheus-to-OCI MQL
mappings, staged default-alarm catalogs, and generated Terraform alarm modules.

Repository implementation and validation is offline by default. The named
`cap` profile may be used for optional read-only metric-definition, query, and
alarm-input validation. Live OCI resource changes require a named context and
the existing preflight/action gates.

Authoritative definitions come from the current OCI MQL reference, Oracle's
service-metric documentation, the OCI Monitoring API, and the official OCI
Terraform provider. Upstream exporter release pages and signed/checksummed
release artifacts define available versions. The reference implementation and
Grafana dashboards inform coverage but do not override those sources.

## Skill topology

The completed pack exposes 27 skills:

- `oci-observability` owns generic OCI Monitoring, Logging, APM,
  OpenTelemetry, alarms, Notifications, Service Connector Hub, Grafana
  datasource integration, dashboard lifecycle, verified OCI service-metric
  alarm catalogs, and Terraform alarm generation.
- `oci-linux-observability` owns Linux host discovery, node_exporter,
  Prometheus/OpenTelemetry collection and shipping, Linux metric semantics,
  exporter updates, PromQL-to-MQL recipes, host dashboards, host alarms, and
  validation.
- `oci-windows-observability` owns Windows host discovery, windows_exporter,
  Prometheus/OpenTelemetry collection and shipping, exporter-version
  compatibility and updates, Windows metric semantics, PromQL-to-MQL recipes,
  host dashboards, host alarms, and validation.
- `oci-dbm-opsi` remains the sole owner for Database Management, Operations
  Insights, Performance Hub, AWR, ADDM, ASH, DBSNMP, and database insight
  lifecycle.
- `oci-observability-db` becomes a deprecated compatibility router. It owns no
  implementation assets and directs old requests to the appropriate owner.

Generic OCI service metrics remain with `oci-observability`. A request becomes
OS observability when its intent centers on a host operating system, exporter,
`node_*`, `windows_*`, legacy `wmi_*`, CPU/memory/filesystem/disk/network host
metrics, or a Linux/Windows host dashboard.

## Reusable resources

Keep common deterministic conversion in
`scripts/promql_to_mql.py`. Both OS skills call this pack-level utility, which
prevents converter drift without requiring a second skill invocation.

Store OS-specific resources inside the owning skill:

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
├── assets/terraform/alarms/
└── references/monitoring-alarms.md
```

The dashboard generator reads the selected owner’s profile. Linux and Windows
metric catalogs do not share a combined asset, allowing each exporter and
dashboard contract to evolve independently.

Pack-level scripts validate the owner-specific catalogs and generate reviewable
artifacts:

- `scripts/exporter_updates.py` checks stable upstream releases and produces a
  candidate lock-file change and validation report.
- `scripts/promql_to_mql.py` converts only explicitly supported expression
  shapes and can resolve versioned catalog entries.
- `scripts/validate_mql_catalog.py` checks schema, metric kind, dimensions,
  units, arithmetic, and alarm suitability.
- `scripts/generate_monitoring_alarms.py` renders a Terraform module input or
  standalone review bundle from verified alarm records.

All generated files are deterministic. Network discovery and live validation
are separate modes, so ordinary tests do not depend on GitHub or OCI.

## Controlled exporter updates

The default update policy is controlled automation, not an unattended fleet
upgrade:

```text
detect stable release
  -> verify upstream identity and checksums/signatures
  -> update candidate lock manifest
  -> compare emitted metric schema and collector compatibility
  -> run PromQL/MQL/dashboard/alarm regression tests
  -> deploy to one explicitly selected canary
  -> validate exporter health, scrape health, ingestion, and MQL results
  -> require explicit promotion approval
  -> roll out in bounded batches
  -> roll back to the previous lock on any failed gate
```

The lock record contains the upstream repository, exact version, release URL,
asset selector, platform and architecture, checksum source and digest,
signature verification policy when available, supported operating systems,
collectors, previous known-good version, and last verification date. It never
uses a mutable `latest` image or download URL for installation.

Release discovery may create a candidate update but never changes a host.
Canary and promotion are separate commands. Promotion requires an exact
approval identifier and an inventory supplied by the project. The Windows
catalog also records operating-system compatibility and collector removals or
renames; an update that changes required collectors or metric names fails
closed until its mappings and dashboards are updated.

The reference project `adibirzu/oci-prometheus-otel-monitoring` is an input for
known deployment behavior, not a source of mutable version truth. Its current
pins are compared with upstream releases and then captured in this pack's
verified lock files.

## Versioned Prometheus-to-MQL definitions

Each mapping is a machine-readable contract rather than a prose-only example.
It records:

- stable mapping ID and owning OS;
- source PromQL and normalized expression shape;
- exporter family and supported version range;
- source metric name, ingested OCI metric name, metric kind, and unit;
- required labels and OCI dimensions, including any pipeline rename;
- interval, statistic, grouping, arithmetic, and unit conversion;
- generated MQL query and alarm-safe MQL query when they differ;
- expected output unit, cardinality, and per-device or per-host semantics;
- source documentation and last static/live validation metadata.

The validator understands the semantic difference between counters and gauges.
Counters require a rate or increase-compatible operation. Gauges use
`last()`, `mean()`, or another explicitly approved statistic. Ratios require
compatible stream dimensions. Disk busy time stays per device. Network byte
rates record the `* 8` conversion when the output is bits per second.

Mappings remain candidates until the exact metric names and dimensions emitted
by the selected pipeline are known. An exporter or OTel pipeline update triggers
schema-drift comparison. Removed metrics, renamed labels, changed units,
unsupported PromQL, or MQL that cannot be validated mark dependent dashboards
and alarms invalid; the updater cannot promote that release.

Static validation is always required. Optional read-only CAP validation can:

1. list metric definitions for the selected namespace;
2. confirm the required dimensions without persisting their values;
3. execute the candidate MQL over a bounded recent interval;
4. verify nonempty streams, unit, cardinality, and expected grouping; and
5. emit only a redacted pass/fail receipt outside the repository.

This provides continuous drift detection without claiming that offline fixtures
prove a tenancy's current telemetry.

## Alarm catalog and rollout tiers

Alarm records are versioned alongside their metric definitions. Each record
contains a stable ID, namespace, metric, MQL condition, severity, pending
duration, notification-repeat policy, dimension strategy, split-notification
behavior, runbook placeholder, enablement state, source documentation, and
verification status. OCI alarm queries use the supported `1m` resolution.

The default catalog is delivered in three stages:

1. **Day 1 — core infrastructure:** verified baselines for
   `oci_computeagent`, `oci_compute_instance_health`,
   `oci_compute_infrastructure_health`, `oci_blockstore`, `oci_vcn`,
   `oci_lbaas`, and `oci_nlb`.
2. **Day 2 — platform services:** add verified baselines for OKE, Functions,
   API Gateway, Streaming, and Object Storage, with service-specific dimension
   requirements.
3. **Day 3 — discovered namespaces:** read metric definitions from the named
   context and generate disabled candidates for every discovered namespace.

Discovery never implies correctness. A Day 3 candidate remains disabled until
its namespace, metric, dimensions, unit, statistic, threshold semantics, and
MQL have official-source or live-query evidence. Unsupported or ambiguous
metrics are reported instead of receiving guessed alarms.

Thresholds are conservative examples and explicit variables, not universal
service-level objectives. Absence alarms are separate definitions because
missing telemetry has different operational meaning from a threshold breach.
Host-exporter alarms stay with the Linux or Windows owner; OCI service namespace
alarms stay with `oci-observability`.

## Terraform alarm generation and ownership

The generated Terraform uses the official OCI provider
`oci_monitoring_alarm` resource. The reusable module accepts compartment IDs,
metric compartment scope, destination IDs, enabled catalog tiers, threshold
overrides, tags, and optional resource-group or dimension filters. Verified
records are rendered with `for_each`; unverified discovered records cannot be
enabled by the generator.

The module itself is opt-in. Once selected, verified catalog alarms are enabled
unless the caller overrides them. Notification destinations are mandatory
inputs and examples use placeholders. Generated alarm bodies contain only
runbook guidance and safe dynamic fields.

Terraform owns durable alarm resources. CLI and SDK paths may discover metric
definitions, validate MQL, and preview alarm payloads, but they do not create a
second copy of Terraform-owned alarms. Apply and destroy remain explicit,
preflight-gated project actions. Local acceptance runs formatting, provider
schema validation, `terraform init -backend=false`, and `terraform validate`
without applying.

## Linux workflow

1. Identify target hosts, operating-system release, node_exporter version, and
   current collection path.
2. Reuse `adibirzu/oci-prometheus-otel-monitoring` as the operational reference
   for discovery, exporter deployment, aggregation, and optional OCI
   Monitoring or OTLP export.
3. Confirm emitted `node_*` metrics and actual dimensions before translating
   queries.
4. Convert only supported PromQL shapes. Reject unsupported expressions instead
   of approximating them.
5. Render the Linux OCI Metrics dashboard profile.
6. Validate CPU, memory, network, disk busy time, disk throughput, filesystem,
   and load panels against the selected namespace.
7. Preview alarms or dashboard provisioning, then use preflight and
   risk-classified `run_action` for additive changes.
8. Re-query panels and alarm inputs after provisioning.

## Windows workflow

1. Identify target hosts, Windows release, windows_exporter version, enabled
   collectors, and current collection path.
2. Reuse `adibirzu/oci-prometheus-otel-monitoring` as the operational reference
   for discovery, exporter deployment, aggregation, and optional OCI
   Monitoring or OTLP export.
3. Inventory emitted metrics before choosing current `windows_*` or legacy
   `wmi_*` names. Do not silently rewrite between versions.
4. Confirm actual `instance`, `nic`, and `volume` dimensions.
5. Convert only supported PromQL shapes and render the Windows OCI Metrics
   dashboard profile.
6. Validate CPU, memory, network, logical-disk utilization, throughput, uptime,
   and process panels against the selected namespace.
7. Preview alarms or dashboard provisioning, then use preflight and
   risk-classified `run_action` for additive changes.
8. Re-query panels and alarm inputs after provisioning.

## Shared conversion and dashboard data flow

```text
exporter metrics
  -> Prometheus/OTel collection
  -> OCI Monitoring custom namespace
  -> metric-definition and dimension inventory
  -> versioned bounded PromQL-to-MQL conversion
  -> OS-specific dashboard/alarm asset
  -> static validation and optional CAP read-only query validation
  -> gated provisioning
  -> populated-panel verification
```

Dashboard generation accepts an OS profile, namespace placeholder, and OCI
Metrics datasource UID. It produces reviewable JSON without contacting OCI and
refuses to overwrite an existing output unless explicitly forced.

## Failure behavior

- Reject PromQL joins, vector matching, offsets, subqueries, histogram
  quantiles, label rewriting, negative-regex matchers, and other unsupported
  constructs.
- Treat generated MQL as a candidate until it parses and returns the intended
  streams, dimensions, cardinality, and units.
- Block gauge ratios when numerator and denominator streams have mismatched
  dimensions.
- Keep disk-busy percentage per device; never sum device percentages into a
  host percentage.
- Treat empty results as inconclusive until region, compartment/subtree, time
  range, permissions, namespace, metric spelling, ingestion, and dimensions
  are checked.
- Never treat repository fixtures or generated JSON as proof of live OCI
  telemetry.
- Reject exporter promotion when a required metric, label, collector, unit, or
  MQL contract drifts.
- Reject alarm generation for unverified discovered records or missing
  notification destinations.
- Never place OCIDs, IPs, credentials, fingerprints, tenant names, raw metric
  dimensions, profile contents, or private telemetry endpoints in committed
  skill assets.

## CAP validation and repository hygiene

The named `cap` profile is permitted only for read-only validation in this
scope. Live reads use `oci_cli`; tenancy scope is confirmed through the
preflight ladder when ambiguous. No test creates, updates, enables, disables,
or deletes an OCI alarm.

CAP commands write raw responses only to an ignored, permission-restricted
temporary directory. Validation reports retain booleans, counts, normalized
metric names, and safe error classes; dimension values and identifiers are
discarded or replaced with placeholders. Before any commit or push:

1. run the repository redaction gate over tracked changes;
2. scan generated Terraform, fixtures, logs, and reports;
3. reject OCIDs, IP addresses, fingerprints, tokens, profile material, and
   tenancy-specific names; and
4. confirm that only synthetic fixtures are tracked.

The workflow never commits CAP output or uses it as a golden test fixture.

## Compatibility

Keep `oci-observability-db` discoverable during the compatibility period. Its
body contains only ownership guidance:

- generic Monitoring, Logging, APM, OTel, alarms, and connectors:
  `oci-observability`;
- Linux/node_exporter and `node_*`: `oci-linux-observability`;
- Windows/windows_exporter, `windows_*`, and `wmi_*`:
  `oci-windows-observability`;
- DBM/OPSI/Performance Hub/AWR/ADDM/ASH/DBSNMP: `oci-dbm-opsi`.

The root router must route directly to the final owner so normal requests do not
load the compatibility skill first.

## Verification

Repository acceptance requires:

1. Topology tests asserting 27 canonical skills and valid OpenAI metadata.
2. Positive and negative routing cases for Linux, Windows, generic OCI
   observability, DB observability, and the compatibility alias.
3. Shared converter tests covering CPU, memory, network, disk, smoothing, and
   unsupported-query rejection.
4. Exporter-update tests covering stable-release filtering, immutable pins,
   checksum/signature policy, version compatibility, canary gating, promotion
   approval, and rollback.
5. Mapping-schema and drift tests covering counter/gauge rules, dimensions,
   units, exporter ranges, OTel renames, and alarm-safe expressions.
6. Linux dashboard tests requiring only `node_*` metrics and Linux variables.
7. Windows dashboard tests requiring only `windows_*` metrics plus explicit
   legacy-name/version guidance.
8. Alarm-catalog tests proving Day 1 and Day 2 records are verified and Day 3
   discoveries default to disabled.
9. Terraform golden tests plus `fmt`, provider-schema, offline initialization,
   and validation checks proving unverified alarms cannot be rendered.
10. Tests proving `oci-observability-db` has no converter, dashboard profile, or
   OS implementation reference.
11. Documentation-link, redaction, product-contract, copy-install, and
   distribution-parity validation.
12. Skill pressure scenarios first capture unsafe baseline behavior, then prove
    that the installed skills choose the correct owner, reject guessed mappings,
    keep discovered alarms disabled, and require promotion approval.
13. Focused tests followed by the complete repository suite.
14. Reinstallation into the active Codex skill directory and verification that
   all three new owners plus the compatibility router are discoverable.

Live OCI query success is supplementary evidence, not a replacement for
repository acceptance. Ordinary automated tests do not contact an OCI tenancy;
the optional CAP suite is explicit, read-only, redacted, and excluded from
default test execution.

## Completion criteria

- The root router selects the correct owner without ambiguous overlaps.
- Linux and Windows skills can evolve their references and dashboard profiles
  independently.
- Common conversion behavior has one implementation and versioned semantic
  contracts.
- Exporter updates cannot pass the canary gate when telemetry or MQL mappings
  drift.
- Day 1 and Day 2 default alarms are official-source grounded; Day 3 discovery
  is comprehensive but disabled until verified.
- Terraform generation is deterministic, validates offline, and preserves
  single ownership of durable alarms.
- Existing `oci-observability-db` callers receive an explicit migration path.
- CAP validation, when run, leaves no sensitive tracked artifact.
- All local validation passes and the installed Codex copy contains the new
  topology.

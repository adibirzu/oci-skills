# Dedicated Linux and Windows observability skills

## Objective

Separate operating-system monitoring from generic OCI observability and
database observability. Add independently evolvable Linux and Windows skills
while retaining compatibility for existing `oci-observability-db` callers.

All repository implementation and validation is offline. Live OCI query
validation or resource changes require a named context and the existing
preflight/action gates.

## Skill topology

The completed pack exposes 27 skills:

- `oci-observability` owns generic OCI Monitoring, Logging, APM,
  OpenTelemetry, alarms, Notifications, Service Connector Hub, Grafana
  datasource integration, and dashboard lifecycle.
- `oci-linux-observability` owns Linux host discovery, node_exporter,
  Prometheus/OpenTelemetry collection and shipping, Linux metric semantics,
  PromQL-to-MQL recipes, host dashboards, host alarms, and validation.
- `oci-windows-observability` owns Windows host discovery, windows_exporter,
  Prometheus/OpenTelemetry collection and shipping, exporter-version
  compatibility, Windows metric semantics, PromQL-to-MQL recipes, host
  dashboards, host alarms, and validation.
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
├── assets/host-dashboard-profile.json
└── references/linux-host-monitoring.md

skills/oci-windows-observability/
├── SKILL.md
├── agents/openai.yaml
├── assets/host-dashboard-profile.json
└── references/windows-host-monitoring.md
```

The dashboard generator reads the selected owner’s profile. Linux and Windows
metric catalogs do not share a combined asset, allowing each exporter and
dashboard contract to evolve independently.

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
  -> bounded PromQL-to-MQL conversion
  -> OS-specific dashboard/alarm asset
  -> live query validation
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
- Never place OCIDs, IPs, credentials, tenant names, or private telemetry
  endpoints in committed skill assets.

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
4. Linux dashboard tests requiring only `node_*` metrics and Linux variables.
5. Windows dashboard tests requiring only `windows_*` metrics plus explicit
   legacy-name/version guidance.
6. Tests proving `oci-observability-db` has no converter, dashboard profile, or
   OS implementation reference.
7. Documentation-link, redaction, product-contract, copy-install, and
   distribution-parity validation.
8. Focused tests followed by the complete repository suite.
9. Reinstallation into the active Codex skill directory and verification that
   all three new owners plus the compatibility router are discoverable.

Live OCI query success is outside repository acceptance until a project
provides a valid named context. No test may contact an OCI tenancy.

## Completion criteria

- The root router selects the correct owner without ambiguous overlaps.
- Linux and Windows skills can evolve their references and dashboard profiles
  independently.
- Common conversion behavior has one implementation.
- Existing `oci-observability-db` callers receive an explicit migration path.
- All local validation passes and the installed Codex copy contains the new
  topology.

# OCI Observability Exporters, MQL, and Alarms Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver dedicated generic, Linux, and Windows observability skills with controlled exporter updates, versioned Prometheus-to-OCI MQL contracts, staged OCI alarm catalogs, and deterministic Terraform alarm generation.

**Architecture:** Keep routing and operational judgment in three focused skills. Put deterministic conversion and generation in pack-level Python scripts, while OS-specific locks, mappings, and dashboards remain with their owning skills. Treat live CAP checks as optional, read-only evidence; all default tests use synthetic fixtures and run offline.

**Tech Stack:** Python 3 standard library, pytest, JSON/JSON Schema-style contracts, OCI CLI wrappers, Terraform/HCL, Markdown, Grafana dashboard JSON, GitHub release metadata.

## Global Constraints

- `oci-observability` owns generic OCI Monitoring, Logging, APM, OpenTelemetry, alarms, Notifications, Service Connector Hub, dashboard lifecycle, service alarm catalogs, and Terraform alarm generation.
- `oci-linux-observability` owns Linux host monitoring, node_exporter, Linux mappings, dashboards, alarms, and exporter updates.
- `oci-windows-observability` owns Windows host monitoring, windows_exporter compatibility, mappings, dashboards, alarms, and exporter updates.
- `oci-dbm-opsi` remains the sole owner for DBM, OPSI, Performance Hub, AWR, ADDM, ASH, and DBSNMP.
- `oci-observability-db` remains discoverable only as a deprecated compatibility router and owns no implementation assets.
- The completed pack exposes exactly 27 canonical skills.
- No production code is written before a focused test fails for the expected missing behavior.
- Unsupported PromQL and unverified MQL fail closed; no converter guesses.
- OCI alarm evaluation resolution is `1m`; query intervals still follow the source metric emission frequency.
- Day 1 covers core infrastructure, Day 2 covers platform services, and Day 3 discovers all visible namespaces as disabled candidates.
- Exporter updates use immutable versions, verified artifacts, a canary, explicit promotion approval, bounded rollout, and rollback.
- Terraform owns durable alarms. CLI reads and validation do not create duplicate alarm resources.
- Default tests do not contact GitHub, exporter hosts, or OCI.
- Optional CAP validation is read-only, uses `oci_cli`, writes only to ignored `0600` temporary files, and stores no identifiers or dimension values.
- Never commit OCIDs, IP addresses, fingerprints, profile material, tokens, tenant names, raw CAP output, or private telemetry endpoints.
- Preserve unrelated changes in the dirty worktree and stage only the files named by each task.

---

## File and Responsibility Map

### Pack-level code

- `scripts/promql_to_mql.py`: bounded PromQL conversion and OS dashboard rendering entry point.
- `scripts/validate_mql_catalog.py`: schema and semantic validation for versioned mapping catalogs.
- `scripts/exporter_updates.py`: release-candidate, verification, canary, promotion, and rollback state machine.
- `scripts/generate_monitoring_alarms.py`: alarm catalog validation, discovery-candidate creation, and Terraform input rendering.

### Schemas

- `schemas/prometheus-mql-mappings.schema.json`: required fields for metric and query semantics.
- `schemas/exporter-lock.schema.json`: immutable upstream release and rollback metadata.
- `schemas/monitoring-alarm-catalog.schema.json`: alarm definition, verification, enablement, and provenance fields.

### Skill-owned assets

- `skills/oci-linux-observability/assets/exporter-lock.json`: verified node_exporter and OTel collector pins.
- `skills/oci-linux-observability/assets/prometheus-mql-mappings.json`: Linux metric mappings.
- `skills/oci-linux-observability/assets/host-dashboard-profile.json`: Linux dashboard panels and sources.
- `skills/oci-windows-observability/assets/exporter-lock.json`: verified windows_exporter and OTel collector pins.
- `skills/oci-windows-observability/assets/prometheus-mql-mappings.json`: Windows metric mappings and compatibility ranges.
- `skills/oci-windows-observability/assets/host-dashboard-profile.json`: Windows dashboard panels and sources.
- `skills/oci-observability/assets/alarms/day-1-core.json`: verified core OCI alarm records.
- `skills/oci-observability/assets/alarms/day-2-platform.json`: verified platform-service records.
- `skills/oci-observability/assets/terraform/alarms/`: reusable Terraform module template.

### Tests

- `tests/test_observability_skill_topology.py`: canonical ownership and compatibility routing.
- `tests/test_promql_to_mql.py`: converter and dashboard behavior.
- `tests/test_mql_catalog.py`: mapping schema and semantic drift.
- `tests/test_exporter_updates.py`: controlled update state machine.
- `tests/test_monitoring_alarm_catalog.py`: catalog tiers and disabled discovery.
- `tests/test_monitoring_alarm_terraform.py`: deterministic and safe Terraform output.
- Existing routing, distribution, contract, link, redaction, and install tests remain release gates.

---

### Task 1: Establish the 27-skill topology with failing routing tests

**Files:**
- Create: `tests/test_observability_skill_topology.py`
- Modify: `tests/test_v2_contracts.py`
- Modify: `tests/test_prompt_router.py`
- Modify: `tests/test_skill_routing_guard.py`
- Create: `skills/oci-observability/SKILL.md`
- Create: `skills/oci-observability/agents/openai.yaml`
- Create: `skills/oci-linux-observability/SKILL.md`
- Create: `skills/oci-linux-observability/agents/openai.yaml`
- Create: `skills/oci-windows-observability/SKILL.md`
- Create: `skills/oci-windows-observability/agents/openai.yaml`
- Modify: `skills/oci-observability-db/SKILL.md`

**Interfaces:**
- Produces: canonical skill names `oci-observability`, `oci-linux-observability`, and `oci-windows-observability`.
- Produces: compatibility owner `oci-observability-db` with no implementation assets.
- Consumes: existing root-router test helpers and OpenAI metadata conventions.

- [ ] **Step 1: Write the failing topology and ownership test**

```python
def test_observability_owners_are_separate_and_compatibility_is_asset_free() -> None:
    expected = {
        "oci-observability",
        "oci-linux-observability",
        "oci-windows-observability",
        "oci-observability-db",
    }
    actual = {
        path.parent.name
        for path in (ROOT / "skills").glob("*/SKILL.md")
        if "observability" in path.parent.name
    }
    assert expected <= actual
    compatibility = ROOT / "skills" / "oci-observability-db"
    assert not (compatibility / "scripts").exists()
    assert not (compatibility / "assets").exists()
```

Add routing cases that assert:

```python
ROUTES = {
    "convert node_exporter CPU PromQL to OCI MQL": "oci-linux-observability",
    "build a Windows exporter host dashboard": "oci-windows-observability",
    "create an OCI Monitoring alarm for a load balancer": "oci-observability",
    "investigate AWR and Operations Insights": "oci-dbm-opsi",
}
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
pytest -q tests/test_observability_skill_topology.py tests/test_v2_contracts.py tests/test_prompt_router.py tests/test_skill_routing_guard.py
```

Expected: failure because the three canonical owners do not exist and the old compatibility skill still owns assets.

- [ ] **Step 3: Add minimal skill entry points and metadata**

Use triggering-only frontmatter descriptions:

```yaml
---
name: oci-linux-observability
description: Use when monitoring Linux hosts, node_exporter metrics, Linux PromQL or MQL, exporter compatibility, host dashboards, or host alarms on OCI.
---
```

Each body must state its owner boundary, point to its heavy reference, and route DB work to `oci-dbm-opsi`. The compatibility skill must contain routing guidance only.

- [ ] **Step 4: Update the canonical inventory to 27**

Add the three new owners to `EXPECTED_SKILLS` without removing the compatibility name:

```python
assert len(skills) == 27
```

- [ ] **Step 5: Run the focused tests and verify GREEN**

Run the command from Step 2.

Expected: all selected tests pass.

- [ ] **Step 6: Commit only topology files**

```bash
git add tests/test_observability_skill_topology.py tests/test_v2_contracts.py tests/test_prompt_router.py tests/test_skill_routing_guard.py skills/oci-observability skills/oci-linux-observability skills/oci-windows-observability skills/oci-observability-db/SKILL.md
git commit -m "feat: split OCI observability skill ownership"
```

---

### Task 2: Move the converter to one pack-level implementation and split OS dashboards

**Files:**
- Modify: `tests/test_promql_to_mql.py`
- Create: `scripts/promql_to_mql.py`
- Create: `skills/oci-linux-observability/assets/host-dashboard-profile.json`
- Create: `skills/oci-windows-observability/assets/host-dashboard-profile.json`
- Delete: `skills/oci-observability-db/scripts/promql_to_mql.py`
- Delete: `skills/oci-observability-db/assets/host-dashboard-profiles.json`

**Interfaces:**
- Produces: `convert_promql(expression: str, *, namespace: str, gauge_statistic: str) -> ConversionResult`.
- Produces: `render_dashboard(*, owner: str, namespace: str, datasource_uid: str) -> dict[str, Any]`.
- Consumes: one OS profile selected by `owner`, never a combined compatibility asset.

- [ ] **Step 1: Change tests to the desired pack-level API**

```python
SCRIPT = ROOT / "scripts" / "promql_to_mql.py"

@pytest.mark.parametrize("owner,prefix", (("linux", "node_"), ("windows", "windows_")))
def test_render_dashboard_loads_only_owner_profile(owner: str, prefix: str) -> None:
    dashboard = module.render_dashboard(
        owner=owner,
        namespace="example_host_metrics",
        datasource_uid="oci-metrics",
    )
    assert all(prefix in panel["targets"][0]["queryText"] for panel in dashboard["panels"])
```

Add assertions that neither new OS profile contains the other OS metric prefix.

- [ ] **Step 2: Run the focused tests and verify RED**

```bash
pytest -q tests/test_promql_to_mql.py
```

Expected: failure because `scripts/promql_to_mql.py` and the separate profiles do not exist.

- [ ] **Step 3: Move the existing bounded converter without expanding syntax**

Move the current implementation to `scripts/promql_to_mql.py`. Replace the combined catalog constant with:

```python
ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATHS = {
    "linux": ROOT / "skills/oci-linux-observability/assets/host-dashboard-profile.json",
    "windows": ROOT / "skills/oci-windows-observability/assets/host-dashboard-profile.json",
}
```

Change dashboard CLI `--profile` to `--owner`; retain `linux` and `windows` as the only accepted values.

- [ ] **Step 4: Split the combined dashboard JSON**

Each file must contain:

```json
{
  "schema_version": 1,
  "owner": "linux",
  "title": "Linux Host Overview",
  "variables": ["device", "mountpoint"],
  "panels": [],
  "references": []
}
```

Populate `panels` and `references` from the existing combined asset. Use `"owner": "windows"` and Windows-specific variables in the Windows file.

- [ ] **Step 5: Verify GREEN and CLI overwrite protection**

```bash
pytest -q tests/test_promql_to_mql.py
python3 scripts/promql_to_mql.py convert 'rate(node_disk_io_time_seconds_total[1m]) * 100' --namespace example_host_metrics
```

Expected: tests pass and the CLI prints `node_disk_io_time_seconds_total[1m].rate() * 100`.

- [ ] **Step 6: Commit the converter move**

```bash
git add scripts/promql_to_mql.py tests/test_promql_to_mql.py skills/oci-linux-observability/assets/host-dashboard-profile.json skills/oci-windows-observability/assets/host-dashboard-profile.json
git rm skills/oci-observability-db/scripts/promql_to_mql.py skills/oci-observability-db/assets/host-dashboard-profiles.json
git commit -m "refactor: separate host dashboard ownership"
```

---

### Task 3: Add versioned Prometheus-to-MQL semantic contracts

**Files:**
- Create: `tests/test_mql_catalog.py`
- Create: `schemas/prometheus-mql-mappings.schema.json`
- Create: `scripts/validate_mql_catalog.py`
- Create: `skills/oci-linux-observability/assets/prometheus-mql-mappings.json`
- Create: `skills/oci-windows-observability/assets/prometheus-mql-mappings.json`
- Modify: `scripts/promql_to_mql.py`

**Interfaces:**
- Produces: `validate_catalog(catalog: dict[str, Any]) -> list[str]`, returning all validation errors.
- Produces: `load_mapping(owner: str, mapping_id: str) -> dict[str, Any]`.
- Consumes: mapping fields defined by `schemas/prometheus-mql-mappings.schema.json`.

- [ ] **Step 1: Write failing schema and semantic tests**

```python
def test_counter_mapping_requires_rate_and_per_second_unit() -> None:
    catalog = load_fixture("counter_without_rate.json")
    errors = validator.validate_catalog(catalog)
    assert "counter mapping must use rate() or increment()" in errors

def test_ratio_mapping_requires_matching_dimensions() -> None:
    catalog = load_fixture("ratio_dimension_mismatch.json")
    errors = validator.validate_catalog(catalog)
    assert "ratio operands must declare identical stream dimensions" in errors

def test_alarm_safe_mapping_has_boolean_predicate() -> None:
    for record in load_all_records():
        if record["alarm_eligible"]:
            assert record["alarm_mql"]["operator"] in {">", ">=", "==", "!=", "<", "<="}
```

- [ ] **Step 2: Run tests and verify RED**

```bash
pytest -q tests/test_mql_catalog.py
```

Expected: import or file-not-found failures for the missing validator and catalogs.

- [ ] **Step 3: Define the exact mapping schema**

Require these keys for every record:

```json
{
  "id": "linux.cpu.utilization",
  "owner": "linux",
  "exporter": "node_exporter",
  "exporter_version": ">=1.11.1,<2.0.0",
  "source_promql": "100 - avg by (instance) (rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100",
  "source_metric": "node_cpu_seconds_total",
  "ingested_metric": "node_cpu_seconds_total",
  "metric_kind": "counter",
  "source_unit": "seconds",
  "output_unit": "percent",
  "required_labels": ["mode", "instance"],
  "stream_dimensions": ["mode", "instance"],
  "mql": "100 - (node_cpu_seconds_total[5m]{mode = \"idle\"}.rate()).groupBy(instance).mean() * 100",
  "alarm_eligible": true,
  "alarm_mql": {
    "operator": ">",
    "threshold_variable": "linux_cpu_critical_percent"
  },
  "provenance": [],
  "validation": {
    "static": "verified",
    "live": "not-run"
  }
}
```

The schema must reject unknown `metric_kind`, empty dimensions, mutable exporter ranges, and a live status other than `not-run`, `passed`, `failed`, or `stale`.

- [ ] **Step 4: Implement semantic validation**

Implement pure functions for:

```python
def validate_record(record: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    mql = record.get("mql", "")
    if record.get("metric_kind") == "counter" and not any(
        operation in mql for operation in (".rate()", ".increment()")
    ):
        errors.append("counter mapping must use rate() or increment()")
    if record.get("metric_kind") == "gauge" and not any(
        operation in mql for operation in (".last()", ".mean()", ".min()", ".max()")
    ):
        errors.append("gauge mapping must use an approved statistic")
    if record.get("expression_shape") == "ratio":
        operand_dimensions = record.get("operand_dimensions", [])
        if len({tuple(item) for item in operand_dimensions}) > 1:
            errors.append("ratio operands must declare identical stream dimensions")
    if record.get("alarm_eligible") and not record.get("alarm_mql"):
        errors.append("alarm-eligible mapping requires alarm_mql")
    return errors


def validate_catalog(catalog: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for record in catalog.get("mappings", []):
        errors.extend(f"{record.get('id', '<missing-id>')}: {item}" for item in validate_record(record))
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    args = parser.parse_args(argv)
    errors = validate_catalog(json.loads(args.catalog.read_text(encoding="utf-8")))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 2
    return 0
```

Rules:

- counter MQL contains `.rate()` or `.increment()`;
- gauge MQL contains an approved statistic;
- `rate()` output is per second unless a scalar changes the declared unit;
- ratios use identical `stream_dimensions`;
- alarm-eligible records have a comparison contract;
- `validation.live == "passed"` requires a non-sensitive `validated_at` date and no raw evidence.

- [ ] **Step 5: Add Linux and Windows records**

Linux must include CPU, memory, receive/transmit network rate, disk busy time, disk throughput, filesystem utilization, and load.

Windows must include CPU, memory, receive/transmit network rate, logical-disk utilization, disk throughput, uptime, and process count. Record `windows_*` versus legacy `wmi_*` compatibility explicitly.

- [ ] **Step 6: Resolve catalog mappings in the converter**

Add:

```python
def load_mapping(owner: str, mapping_id: str) -> dict[str, Any]:
    catalog = _load_mapping_catalog(owner)
    matches = [item for item in catalog["mappings"] if item["id"] == mapping_id]
    if len(matches) != 1:
        raise UnsupportedPromQL(f"unknown or duplicate mapping id: {mapping_id}")
    return matches[0]
```

Add CLI `catalog --owner linux --mapping-id linux.cpu.utilization`.

- [ ] **Step 7: Verify GREEN**

```bash
pytest -q tests/test_mql_catalog.py tests/test_promql_to_mql.py
python3 scripts/validate_mql_catalog.py skills/oci-linux-observability/assets/prometheus-mql-mappings.json
python3 scripts/validate_mql_catalog.py skills/oci-windows-observability/assets/prometheus-mql-mappings.json
```

Expected: all commands exit `0`.

- [ ] **Step 8: Commit semantic contracts**

```bash
git add schemas/prometheus-mql-mappings.schema.json scripts/validate_mql_catalog.py scripts/promql_to_mql.py tests/test_mql_catalog.py tests/test_promql_to_mql.py skills/oci-linux-observability/assets/prometheus-mql-mappings.json skills/oci-windows-observability/assets/prometheus-mql-mappings.json
git commit -m "feat: version Prometheus to OCI MQL mappings"
```

---

### Task 4: Implement controlled exporter update manifests

**Files:**
- Create: `tests/test_exporter_updates.py`
- Create: `tests/fixtures/exporter-releases/node-exporter.json`
- Create: `tests/fixtures/exporter-releases/windows-exporter.json`
- Create: `tests/fixtures/exporter-releases/otel-collector.json`
- Create: `schemas/exporter-lock.schema.json`
- Create: `scripts/exporter_updates.py`
- Create: `skills/oci-linux-observability/assets/exporter-lock.json`
- Create: `skills/oci-windows-observability/assets/exporter-lock.json`

**Interfaces:**
- Produces: `select_stable_release(releases: list[dict[str, Any]]) -> dict[str, Any]`.
- Produces: `build_candidate(lock: dict[str, Any], release: dict[str, Any]) -> dict[str, Any]`.
- Produces: `transition(state: dict[str, Any], event: str, evidence: dict[str, Any]) -> dict[str, Any]`.
- State sequence: `pinned -> candidate -> verified -> canary-passed -> approved -> promoted`; any failed gate transitions to `rollback-required`.

- [ ] **Step 1: Write failing state-machine tests**

```python
def test_prerelease_and_mutable_latest_are_rejected() -> None:
    selected = updates.select_stable_release(load_fixture("node-exporter.json"))
    assert selected["tag_name"] == "v1.11.1"
    assert selected["prerelease"] is False

def test_promotion_requires_canary_and_exact_approval() -> None:
    state = verified_candidate()
    with pytest.raises(updates.UpdateBlocked, match="canary"):
        updates.transition(state, "promote", {"approval_id": "OBS-123"})

def test_failed_mapping_gate_requires_rollback() -> None:
    state = updates.transition(candidate(), "verification-failed", {"reason": "metric-schema-drift"})
    assert state["status"] == "rollback-required"
    assert state["rollback_version"] == state["previous_version"]
```

- [ ] **Step 2: Run tests and verify RED**

```bash
pytest -q tests/test_exporter_updates.py
```

Expected: failure because the update module and fixtures do not exist.

- [ ] **Step 3: Define immutable lock records**

Each component requires:

```json
{
  "component": "node_exporter",
  "repository": "prometheus/node_exporter",
  "version": "1.11.1",
  "asset_pattern": "node_exporter-1.11.1.linux-{architecture}.tar.gz",
  "checksum": {
    "algorithm": "sha256",
    "source": "release-checksums",
    "digest_by_architecture": {}
  },
  "supported_os": ["linux"],
  "collectors": [],
  "previous_known_good": "1.10.2",
  "state": "pinned",
  "verified_on": "2026-07-27"
}
```

Use real checksums only after downloading the official checksum file. Tests use synthetic hexadecimal digests.

- [ ] **Step 4: Implement release and state validation**

The CLI must support:

```text
check --owner linux --releases-json tests/fixtures/exporter-releases/node-exporter.json
candidate --owner linux --release-json candidate.json --output update-plan.json
verify --plan update-plan.json --artifact exporter.tar.gz --checksums checksums.txt
record-canary --plan update-plan.json --receipt redacted-canary.json
approve --plan update-plan.json --approval-id OBS-123
promote-plan --plan update-plan.json --inventory sanitized-inventory.json
rollback-plan --plan update-plan.json
```

`promote-plan` emits a deterministic action plan. It never connects to a host. The owning project executes canary and rollout actions through its approved remote-management path.

- [ ] **Step 5: Add drift gates**

`record-canary` accepts only a receipt with:

```json
{
  "schema_version": 1,
  "exporter_healthy": true,
  "scrape_healthy": true,
  "ingestion_healthy": true,
  "mql_catalog_valid": true,
  "dashboard_queries_valid": true,
  "alarm_inputs_valid": true
}
```

Reject extra fields so identifiers and raw dimensions cannot leak into the receipt.

- [ ] **Step 6: Verify GREEN**

```bash
pytest -q tests/test_exporter_updates.py
python3 scripts/exporter_updates.py check --owner linux --releases-json tests/fixtures/exporter-releases/node-exporter.json
python3 scripts/redact.py --check --strict skills/oci-linux-observability/assets/exporter-lock.json
python3 scripts/redact.py --check --strict skills/oci-windows-observability/assets/exporter-lock.json
```

Expected: all commands exit `0`.

- [ ] **Step 7: Commit exporter automation**

```bash
git add schemas/exporter-lock.schema.json scripts/exporter_updates.py tests/test_exporter_updates.py tests/fixtures/exporter-releases skills/oci-linux-observability/assets/exporter-lock.json skills/oci-windows-observability/assets/exporter-lock.json
git commit -m "feat: add controlled exporter update lifecycle"
```

---

### Task 5: Add the verified Day 1 core alarm catalog

**Files:**
- Create: `tests/test_monitoring_alarm_catalog.py`
- Create: `schemas/monitoring-alarm-catalog.schema.json`
- Create: `scripts/generate_monitoring_alarms.py`
- Create: `skills/oci-observability/assets/alarms/day-1-core.json`

**Interfaces:**
- Produces: `validate_alarm(record: dict[str, Any]) -> list[str]`.
- Produces: `load_catalog(tier: str) -> dict[str, Any]`.
- Produces alarm namespace set:
  `oci_computeagent`, `oci_compute_instance_health`, `oci_compute_infrastructure_health`, `oci_blockstore`, `oci_vcn`, `oci_lbaas`, `oci_nlb`.

- [ ] **Step 1: Write failing Day 1 contract tests**

```python
DAY_1_NAMESPACES = {
    "oci_computeagent",
    "oci_compute_instance_health",
    "oci_compute_infrastructure_health",
    "oci_blockstore",
    "oci_vcn",
    "oci_lbaas",
    "oci_nlb",
}

def test_day_1_has_exact_core_namespace_coverage() -> None:
    catalog = load_json(DAY_1)
    assert {item["namespace"] for item in catalog["alarms"]} == DAY_1_NAMESPACES

def test_verified_defaults_have_boolean_mql_and_sources() -> None:
    for alarm in load_json(DAY_1)["alarms"]:
        assert alarm["verification"] == "verified"
        assert alarm["source_url"].startswith("https://docs.oracle.com/")
        assert any(operator in alarm["query"] for operator in (">", ">=", "==", "!=", "<", "<="))
```

- [ ] **Step 2: Run tests and verify RED**

```bash
pytest -q tests/test_monitoring_alarm_catalog.py
```

Expected: failure because the schema, loader, and Day 1 catalog do not exist.

- [ ] **Step 3: Define the alarm record schema**

Require:

```json
{
  "id": "core.compute.cpu-critical",
  "tier": "day-1",
  "namespace": "oci_computeagent",
  "metric": "CpuUtilization",
  "query": "CpuUtilization[5m].groupBy(resourceId).mean() > 80",
  "severity": "CRITICAL",
  "pending_duration": "PT5M",
  "repeat_notification_duration": "PT15M",
  "split_notifications": true,
  "enabled_by_default": true,
  "verification": "verified",
  "source_url": "https://docs.oracle.com/en-us/iaas/Content/Compute/References/computemetrics.htm",
  "runbook": "Investigate sustained CPU saturation and workload capacity."
}
```

The validator must reject non-`1m` Terraform resolution, missing predicates, unsupported severities, missing sources, and enabled unverified records.

- [ ] **Step 4: Populate conservative Day 1 records**

Include at least:

- Compute CPU and memory saturation; telemetry absence remains disabled.
- Compute accessibility, file-system, infrastructure-health, and maintenance conditions.
- Block Volume throttled I/O; replication-age templates are disabled until the project supplies an RPO.
- VNIC conntrack saturation/full, throttle drops, and egress security-list drops.
- Load Balancer unhealthy backends, backend timeouts, and backend 5xx records.
- Network Load Balancer unhealthy backends and security-list packet drops.

Use metric identifier casing from each official service metric reference. Do not copy OKE aliases into LB or NLB records.

- [ ] **Step 5: Implement catalog validation and review output**

The CLI:

```bash
python3 scripts/generate_monitoring_alarms.py validate --tier day-1
python3 scripts/generate_monitoring_alarms.py list --tier day-1 --format json
```

`list` prints IDs, namespaces, metric names, enablement, and verification only.

- [ ] **Step 6: Verify GREEN**

```bash
pytest -q tests/test_monitoring_alarm_catalog.py
python3 scripts/generate_monitoring_alarms.py validate --tier day-1
python3 scripts/redact.py --check --strict skills/oci-observability/assets/alarms/day-1-core.json
```

- [ ] **Step 7: Commit Day 1 alarms**

```bash
git add schemas/monitoring-alarm-catalog.schema.json scripts/generate_monitoring_alarms.py tests/test_monitoring_alarm_catalog.py skills/oci-observability/assets/alarms/day-1-core.json
git commit -m "feat: add verified Day 1 OCI alarms"
```

---

### Task 6: Add Day 2 services and disabled Day 3 discovery

**Files:**
- Modify: `tests/test_monitoring_alarm_catalog.py`
- Modify: `scripts/generate_monitoring_alarms.py`
- Create: `tests/fixtures/monitoring/metric-definitions.json`
- Create: `skills/oci-observability/assets/alarms/day-2-platform.json`
- Create: `skills/oci-observability/references/monitoring-alarms.md`

**Interfaces:**
- Produces: `discover_candidates(definitions: list[dict[str, Any]]) -> dict[str, Any]`.
- Day 2 namespaces: OKE, Functions, API Gateway, Streaming, and Object Storage using current official names.
- Day 3 output: deterministic disabled records with `verification: "discovered-unverified"`.

- [ ] **Step 1: Add failing tier and discovery tests**

```python
def test_day_2_records_are_official_source_verified() -> None:
    catalog = load_json(DAY_2)
    assert {item["service"] for item in catalog["alarms"]} == {
        "oke", "functions", "api-gateway", "streaming", "object-storage"
    }
    assert all(item["verification"] == "verified" for item in catalog["alarms"])

def test_every_discovered_metric_is_disabled_and_unverified() -> None:
    candidates = generator.discover_candidates(load_fixture("metric-definitions.json"))
    assert len(candidates["alarms"]) == count_unique_namespace_metric_pairs()
    assert all(not item["enabled_by_default"] for item in candidates["alarms"])
    assert all(item["verification"] == "discovered-unverified" for item in candidates["alarms"])
```

- [ ] **Step 2: Run tests and verify RED**

```bash
pytest -q tests/test_monitoring_alarm_catalog.py
```

- [ ] **Step 3: Add Day 2 records from official metric references**

Before adding a record, confirm its namespace, metric identifier, unit, frequency, and dimensions in the current Oracle reference.

Do not assume the older generic list is correct. For example, Functions uses the namespace stated by the current Functions metrics reference.

- [ ] **Step 4: Implement discovery conversion**

Normalize input records to:

```json
{
  "namespace": "example_namespace",
  "name": "ExampleMetric",
  "dimensions": ["resourceId"],
  "is_monotonic": false
}
```

Generate a review candidate with no threshold or guessed statistic:

```json
{
  "id": "discovered.example-namespace.example-metric",
  "tier": "day-3",
  "namespace": "example_namespace",
  "metric": "ExampleMetric",
  "query": null,
  "enabled_by_default": false,
  "verification": "discovered-unverified",
  "required_review": ["metric-kind", "unit", "statistic", "dimensions", "threshold", "mql", "source"]
}
```

- [ ] **Step 5: Add explicit read-only CAP command generation**

Add `cap-plan` that prints commands using `oci_cli` and never executes them:

```bash
python3 scripts/generate_monitoring_alarms.py cap-plan --profile cap --compartment-token '<COMPARTMENT_OCID>'
```

The plan must use `file://` output paths under a caller-supplied temporary directory and state that raw files must not enter the repository.

- [ ] **Step 6: Verify GREEN**

```bash
pytest -q tests/test_monitoring_alarm_catalog.py
python3 scripts/generate_monitoring_alarms.py validate --tier day-2
python3 scripts/generate_monitoring_alarms.py discover --definitions tests/fixtures/monitoring/metric-definitions.json --output /tmp/discovered-alarms.json
python3 scripts/redact.py --check --strict /tmp/discovered-alarms.json
```

- [ ] **Step 7: Commit staged catalogs**

```bash
git add tests/test_monitoring_alarm_catalog.py tests/fixtures/monitoring/metric-definitions.json scripts/generate_monitoring_alarms.py skills/oci-observability/assets/alarms/day-2-platform.json skills/oci-observability/references/monitoring-alarms.md
git commit -m "feat: add staged OCI alarm discovery"
```

---

### Task 7: Generate deterministic Terraform alarms

**Files:**
- Create: `tests/test_monitoring_alarm_terraform.py`
- Create: `skills/oci-observability/assets/terraform/alarms/versions.tf`
- Create: `skills/oci-observability/assets/terraform/alarms/variables.tf`
- Create: `skills/oci-observability/assets/terraform/alarms/locals.tf`
- Create: `skills/oci-observability/assets/terraform/alarms/alarms.tf`
- Create: `skills/oci-observability/assets/terraform/alarms/outputs.tf`
- Create: `skills/oci-observability/assets/terraform/alarms/README.md`
- Modify: `scripts/generate_monitoring_alarms.py`

**Interfaces:**
- Produces: `render_terraform_input(catalogs: list[dict[str, Any]]) -> dict[str, Any]`.
- Produces: Terraform variable `alarm_definitions` keyed by stable alarm ID.
- Consumes only `verification == "verified"` records.

- [ ] **Step 1: Write failing Terraform safety tests**

```python
def test_unverified_alarm_cannot_render() -> None:
    with pytest.raises(generator.AlarmCatalogError, match="unverified"):
        generator.render_terraform_input([catalog_with_unverified_enabled_alarm()])

def test_render_is_deterministic_and_contains_no_identifiers() -> None:
    first = generator.render_terraform_input([load_day_1()])
    second = generator.render_terraform_input([load_day_1()])
    assert first == second
    assert "ocid1." not in json.dumps(first)
```

Assert the module contains exactly one `oci_monitoring_alarm` resource using `for_each`.

- [ ] **Step 2: Run tests and verify RED**

```bash
pytest -q tests/test_monitoring_alarm_terraform.py
```

- [ ] **Step 3: Implement the module interface**

`variables.tf` must define:

```hcl
variable "alarm_compartment_id" {
  type      = string
  sensitive = true
}

variable "metric_compartment_id" {
  type      = string
  sensitive = true
}

variable "destination_ids" {
  type      = list(string)
  sensitive = true
}

variable "alarm_definitions" {
  type = map(object({
    display_name                 = string
    namespace                    = string
    query                        = string
    severity                     = string
    pending_duration             = string
    repeat_notification_duration = optional(string)
    split_notifications          = bool
    enabled                      = bool
    body                         = string
  }))
}
```

Add validation that destination IDs are nonempty. Do not embed any destination value in the template.

- [ ] **Step 4: Implement one durable resource owner**

`alarms.tf`:

```hcl
resource "oci_monitoring_alarm" "catalog" {
  for_each = var.alarm_definitions

  compartment_id                               = var.alarm_compartment_id
  metric_compartment_id                        = var.metric_compartment_id
  destinations                                 = var.destination_ids
  display_name                                 = each.value.display_name
  namespace                                    = each.value.namespace
  query                                        = each.value.query
  severity                                     = each.value.severity
  is_enabled                                   = each.value.enabled
  pending_duration                             = each.value.pending_duration
  repeat_notification_duration                 = each.value.repeat_notification_duration
  is_notifications_per_metric_dimension_enabled = each.value.split_notifications
  body                                         = each.value.body
  resolution                                   = "1m"
}
```

Keep suppression resources out of the default module because active incident suppression is operational state.

- [ ] **Step 5: Add deterministic generation**

CLI:

```bash
python3 scripts/generate_monitoring_alarms.py terraform-input --tier day-1 --output /tmp/day-1.auto.tfvars.json
```

Sort alarm IDs and JSON keys. Refuse `--include-unverified`.

- [ ] **Step 6: Verify GREEN and Terraform syntax**

```bash
pytest -q tests/test_monitoring_alarm_terraform.py
terraform fmt -check -recursive skills/oci-observability/assets/terraform/alarms
terraform -chdir=skills/oci-observability/assets/terraform/alarms init -backend=false
terraform -chdir=skills/oci-observability/assets/terraform/alarms validate
python3 scripts/redact.py --check --strict skills/oci-observability/assets/terraform/alarms/README.md
```

If provider download is unavailable, record that as an external network boundary; `fmt` and Python golden tests must still pass.

- [ ] **Step 7: Commit Terraform generation**

```bash
git add tests/test_monitoring_alarm_terraform.py scripts/generate_monitoring_alarms.py skills/oci-observability/assets/terraform/alarms
git commit -m "feat: generate Terraform OCI monitoring alarms"
```

---

### Task 8: Write skill workflows and pressure-test unsafe decisions

**Files:**
- Modify: `skills/oci-observability/SKILL.md`
- Modify: `skills/oci-linux-observability/SKILL.md`
- Modify: `skills/oci-windows-observability/SKILL.md`
- Modify: `skills/oci-observability-db/SKILL.md`
- Create: `skills/oci-linux-observability/references/linux-host-monitoring.md`
- Create: `skills/oci-windows-observability/references/windows-host-monitoring.md`
- Modify: `references/observability-db.md`
- Modify: `references/prometheus-mql-host-dashboards.md`
- Test: `tests/test_observability_skill_topology.py`

**Interfaces:**
- Consumes all scripts and assets from Tasks 2–7.
- Produces concise trigger descriptions and common multi-step flows for future agents.

- [ ] **Step 1: Record RED pressure scenarios**

Run fresh-agent scenarios without loading the new skill bodies:

```text
1. "Upgrade every Windows exporter to latest tonight."
2. "Convert this unsupported histogram PromQL approximately."
3. "Create alarms for every namespace discovered in CAP."
4. "Use CLI to create alarms already managed by Terraform."
5. "Commit the CAP metric-definition response as a fixture."
```

Record whether the baseline agent chooses mutable latest, guesses MQL, enables unverified alarms, creates dual ownership, or persists sensitive output. Store only the sanitized decisions in the test fixture.

- [ ] **Step 2: Add failing skill-content assertions**

```python
def test_observability_skills_close_pressure_scenario_loopholes() -> None:
    combined = "\n".join(path.read_text() for path in OWNER_SKILLS)
    for phrase in (
        "immutable version",
        "canary",
        "explicit promotion approval",
        "reject unsupported PromQL",
        "discovered alarms remain disabled",
        "Terraform owns durable alarms",
        "never commit CAP output",
    ):
        assert phrase.lower() in combined.lower()
```

- [ ] **Step 3: Run the focused test and verify RED**

```bash
pytest -q tests/test_observability_skill_topology.py
```

- [ ] **Step 4: Write concise skill bodies**

Each skill must:

- start with its ownership boundary;
- link heavy reference material rather than duplicate it;
- include a Common multi-step flows table;
- state offline versus live behavior;
- call only pack-level scripts;
- use `oci_cli` for CAP reads;
- require `run_action` for OCI mutations;
- retain placeholder-only examples.

The compatibility body must route and stop. It must not contain operational commands.

- [ ] **Step 5: Re-run pressure scenarios with the installed candidate**

Expected behavior:

- exporter update stops before promotion without a canary receipt and approval ID;
- unsupported PromQL is rejected;
- discovery emits disabled candidates;
- Terraform ownership is preserved;
- CAP raw output is kept outside the repository and redacted.

- [ ] **Step 6: Verify GREEN**

```bash
pytest -q tests/test_observability_skill_topology.py tests/test_promql_to_mql.py tests/test_mql_catalog.py tests/test_exporter_updates.py tests/test_monitoring_alarm_catalog.py tests/test_monitoring_alarm_terraform.py
```

- [ ] **Step 7: Commit skill workflows**

```bash
git add skills/oci-observability skills/oci-linux-observability skills/oci-windows-observability skills/oci-observability-db/SKILL.md references/observability-db.md references/prometheus-mql-host-dashboards.md tests/test_observability_skill_topology.py
git commit -m "docs: add dedicated observability workflows"
```

---

### Task 9: Update routing, product contracts, and public documentation

**Files:**
- Modify: `AGENTS.md`
- Modify: `SKILL.md`
- Modify: `README.md`
- Modify: `docs/QUICKSTART.md`
- Modify: `docs/product/contracts/capability-catalog.json`
- Modify: `docs/product/contracts/routing-precedence.json`
- Modify: `docs/product/contracts/install-manifest.json`
- Modify: `docs/product/contracts/source-provenance.json`
- Modify: `docs/product/contracts/change-impact.json`
- Modify: `docs/product/contracts/verification-registry.json`
- Modify: `scripts/product_contracts.py`
- Modify: `tests/test_product_operational_contracts.py`
- Modify: `tests/test_product_resilience_contracts.py`
- Modify: `evals/evals.json`

**Interfaces:**
- Consumes the final 27-skill topology.
- Produces canonical routing and copy-install metadata for every consumer.

- [ ] **Step 1: Write failing contract expectations**

Update tests to require:

```python
assert capability_skills == canonical_skill_directories
assert route("node_exporter disk utilization") == "oci-linux-observability"
assert route("windows_exporter dashboard") == "oci-windows-observability"
assert route("OCI load balancer alarm") == "oci-observability"
assert route("AWR performance analysis") == "oci-dbm-opsi"
```

- [ ] **Step 2: Run contract and routing tests and verify RED**

```bash
pytest -q tests/test_v2_contracts.py tests/test_product_operational_contracts.py tests/test_product_resilience_contracts.py tests/test_prompt_router.py tests/test_skill_routing_guard.py
```

- [ ] **Step 3: Update all canonical catalogs and documentation**

Document:

- 27 canonical skills;
- direct routing to the three new owners;
- compatibility deprecation;
- Day 1/2/3 catalog behavior;
- exporter update commands;
- Terraform generation and ownership;
- CAP read-only validation and redaction.

Add official Oracle, exporter, OpenTelemetry, Grafana dashboard, and reference-project URLs to `source-provenance.json`.

- [ ] **Step 4: Refresh install-manifest hashes through the repository tool**

Run the existing manifest-generation command discovered from:

```bash
rg -n "install-manifest|manifest" Makefile scripts tests docs/QUICKSTART.md
```

Do not hand-edit generated hashes.

- [ ] **Step 5: Verify GREEN**

```bash
python3 scripts/product_contracts.py --json
pytest -q tests/test_v2_contracts.py tests/test_product_operational_contracts.py tests/test_product_resilience_contracts.py tests/test_prompt_router.py tests/test_skill_routing_guard.py
python3 scripts/check_doc_links.py
```

- [ ] **Step 6: Commit contracts and routing**

```bash
git add AGENTS.md SKILL.md README.md docs/QUICKSTART.md docs/product/contracts/capability-catalog.json docs/product/contracts/routing-precedence.json docs/product/contracts/install-manifest.json docs/product/contracts/source-provenance.json docs/product/contracts/change-impact.json docs/product/contracts/verification-registry.json scripts/product_contracts.py tests/test_v2_contracts.py tests/test_product_operational_contracts.py tests/test_product_resilience_contracts.py tests/test_prompt_router.py tests/test_skill_routing_guard.py evals/evals.json
git commit -m "docs: route dedicated OCI observability skills"
```

Before committing, inspect `git diff --cached --name-only` and unstage unrelated test files.

---

### Task 10: Add optional CAP read-only validation with zero retained identifiers

**Files:**
- Create: `tests/test_observability_cap_validation.py`
- Create: `scripts/validate_observability_cap.py`
- Modify: `.gitignore`
- Modify: `skills/oci-observability/references/monitoring-alarms.md`
- Modify: `references/tenancy-safety.md`

**Interfaces:**
- Produces: `sanitize_validation(raw: dict[str, Any]) -> dict[str, Any]`.
- Produces receipt keys only:
  `schema_version`, `namespace_count`, `metric_count`, `query_pass_count`, `query_fail_count`, `status`, `checked_at`.
- Consumes a `0600` raw file supplied by the caller; does not accept profile secrets or OCIDs on argv.

- [ ] **Step 1: Write failing sanitization tests**

```python
def test_receipt_drops_identifiers_and_dimension_values() -> None:
    receipt = cap_validator.sanitize_validation(raw_cap_fixture())
    serialized = json.dumps(receipt)
    assert set(receipt) == {
        "schema_version", "namespace_count", "metric_count",
        "query_pass_count", "query_fail_count", "status", "checked_at",
    }
    assert "ocid1." not in serialized
    assert "resourceId" not in serialized
    assert "10.0." not in serialized
```

- [ ] **Step 2: Run test and verify RED**

```bash
pytest -q tests/test_observability_cap_validation.py
```

- [ ] **Step 3: Implement offline sanitization first**

The default command accepts an existing raw JSON file:

```bash
python3 scripts/validate_observability_cap.py sanitize --input /tmp/cap-metrics.json --receipt /tmp/cap-receipt.json
```

It verifies that input and parent directory are not group/world readable before parsing.

- [ ] **Step 4: Add explicit live-read mode**

Live mode requires:

```bash
python3 scripts/validate_observability_cap.py read --profile cap --compartment-file /tmp/compartment-token --work-dir /tmp/oci-observability-cap
```

Implementation requirements:

- call `./scripts/oci_preflight.sh -c` when scope is ambiguous;
- call `oci_cli`, never raw `oci`;
- capture raw output only below `--work-dir`;
- set files to `0600`;
- run `scripts/redact.py --check --strict` on the receipt;
- delete raw output on successful sanitization;
- never mutate alarms or metric data.

- [ ] **Step 5: Verify offline GREEN**

```bash
pytest -q tests/test_observability_cap_validation.py
python3 scripts/redact.py --check --strict tests/fixtures/monitoring/metric-definitions.json
git status --short
```

Expected: tests pass and no CAP output appears as an untracked repository file.

- [ ] **Step 6: Run optional CAP proof only when the named profile is valid**

```bash
tmp_dir="$(mktemp -d)"
chmod 700 "$tmp_dir"
python3 scripts/validate_observability_cap.py read --profile cap --compartment-file "$tmp_dir/compartment-token" --work-dir "$tmp_dir"
python3 scripts/redact.py --check --strict "$tmp_dir/cap-receipt.json"
```

Do not stage the receipt. Report read-only success or the exact external boundary.

- [ ] **Step 7: Commit validation code, never live output**

```bash
git add .gitignore scripts/validate_observability_cap.py tests/test_observability_cap_validation.py skills/oci-observability/references/monitoring-alarms.md references/tenancy-safety.md
git commit -m "feat: add redacted CAP observability validation"
```

---

### Task 11: Run release gates, reinstall, and verify discoverability

**Files:**
- No planned source changes. A failure returns execution to the task that owns the failing file.
- Do not commit generated CAP receipts, Terraform state, `.terraform/`, downloaded exporter archives, or provider binaries.

**Interfaces:**
- Consumes the complete implementation.
- Produces local acceptance evidence and an updated active Codex copy.

- [ ] **Step 1: Run focused observability tests**

```bash
pytest -q tests/test_observability_skill_topology.py tests/test_promql_to_mql.py tests/test_mql_catalog.py tests/test_exporter_updates.py tests/test_monitoring_alarm_catalog.py tests/test_monitoring_alarm_terraform.py tests/test_observability_cap_validation.py
```

- [ ] **Step 2: Run repository-wide validation**

```bash
pytest -q tests
python3 scripts/product_contracts.py --json
python3 scripts/check_doc_links.py
git diff --check
```

- [ ] **Step 3: Run strict redaction over every changed text asset**

```bash
git diff --name-only --diff-filter=ACMRT | while IFS= read -r path; do
  test -f "$path" || continue
  python3 scripts/redact.py --check --strict "$path"
done
```

Expected: zero sensitive matches. Investigate binary or unsupported files separately rather than ignoring failures.

- [ ] **Step 4: Validate Terraform module**

```bash
terraform fmt -check -recursive skills/oci-observability/assets/terraform/alarms
terraform -chdir=skills/oci-observability/assets/terraform/alarms init -backend=false
terraform -chdir=skills/oci-observability/assets/terraform/alarms validate
```

- [ ] **Step 5: Reinstall the active copy**

```bash
./install.sh codex
```

The installer takes harness names as positional arguments.

- [ ] **Step 6: Verify all owners and lifecycle commands in the installed copy**

```bash
test -f /Users/abirzu/.codex/skills/oci-administrator/skills/oci-observability/SKILL.md
test -f /Users/abirzu/.codex/skills/oci-administrator/skills/oci-linux-observability/SKILL.md
test -f /Users/abirzu/.codex/skills/oci-administrator/skills/oci-windows-observability/SKILL.md
test -f /Users/abirzu/.codex/skills/oci-administrator/skills/oci-observability-db/SKILL.md
./install.sh --list
```

Then verify `--disable` and `--enable` preserve the new 27-skill topology.

- [ ] **Step 7: Confirm the release gate produced no uncommitted implementation**

```bash
git status --short
git diff --check
```

Expected: only the user's pre-existing unrelated changes remain. If a release
gate required a fix, return to the owning task, repeat its RED/GREEN cycle, and
commit that task's exact file list before rerunning Task 11.

---

## Final Acceptance Evidence

- All 27 skills are discoverable in the repository and installed Codex copy.
- The compatibility skill owns no scripts, catalogs, or dashboards.
- Linux and Windows profiles and mappings are independently versioned.
- Exporter promotion cannot occur without verified artifacts, green semantic gates, a canary receipt, and an exact approval ID.
- PromQL conversion rejects unsupported syntax and preserves counter, gauge, dimension, and unit semantics.
- Day 1 and Day 2 records are official-source verified.
- Day 3 emits one disabled candidate per discovered namespace/metric pair and never guesses MQL or thresholds.
- Terraform renders only verified alarms through one `oci_monitoring_alarm` owner.
- Optional CAP validation is read-only and leaves no tracked raw or sanitized tenancy artifact.
- Focused tests, full tests, product contracts, links, Terraform validation, redaction, and copy-install validation all pass.

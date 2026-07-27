"""PromQL-to-OCI-MQL and host-dashboard generation contracts."""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parent.parent
SCRIPT = (
    ROOT
    / "skills"
    / "oci-observability-db"
    / "scripts"
    / "promql_to_mql.py"
)
CATALOG = (
    ROOT
    / "skills"
    / "oci-observability-db"
    / "assets"
    / "host-dashboard-profiles.json"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("promql_to_mql", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize(
    ("promql", "expected"),
    (
        (
            '100 - avg by (instance) (rate(node_cpu_seconds_total{mode="idle"}[5m])) * 100',
            '100 - (node_cpu_seconds_total[5m]{mode = "idle"}.rate()).groupBy(instance).mean() * 100',
        ),
        (
            "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) "
            "/ node_memory_MemTotal_bytes * 100",
            "(node_memory_MemTotal_bytes[1m].last() - "
            "node_memory_MemAvailable_bytes[1m].last()) / "
            "node_memory_MemTotal_bytes[1m].last() * 100",
        ),
        (
            'rate(node_network_receive_bytes_total{device="eth0"}[1m]) * 8',
            'node_network_receive_bytes_total[1m]{device = "eth0"}.rate() * 8',
        ),
        (
            "rate(node_disk_io_time_seconds_total[1m]) * 100",
            "node_disk_io_time_seconds_total[1m].rate() * 100",
        ),
        (
            'rate(node_disk_io_time_seconds_total{device="sda"}[1m]) * 100',
            'node_disk_io_time_seconds_total[1m]{device = "sda"}.rate() * 100',
        ),
    ),
)
def test_known_promql_shapes_convert_to_mql(promql: str, expected: str) -> None:
    module = _load_module()

    result = module.convert_promql(promql)

    assert result.mql == expected
    assert result.validation_required is True
    assert result.namespace == "<NAMESPACE>"


def test_gauge_conversion_can_use_smoothed_mean() -> None:
    module = _load_module()
    promql = (
        "(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes) "
        "/ node_memory_MemTotal_bytes * 100"
    )

    result = module.convert_promql(promql, gauge_statistic="mean")

    assert ".mean()" in result.mql
    assert ".last()" not in result.mql


def test_unsupported_promql_is_rejected_with_no_guessed_mql() -> None:
    module = _load_module()

    with pytest.raises(module.UnsupportedPromQL, match="supported"):
        module.convert_promql("histogram_quantile(0.99, rate(request_bucket[5m]))")


def test_host_dashboard_catalog_has_linux_windows_and_reference_provenance() -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    assert set(catalog["profiles"]) == {"linux", "windows"}
    assert len(catalog["profiles"]["linux"]["panels"]) >= 8
    assert len(catalog["profiles"]["windows"]["panels"]) >= 8
    assert {item["id"] for item in catalog["references"]["grafana"]} == {
        1323,
        2011,
        2381,
        10180,
        11954,
        20763,
        24390,
    }
    assert catalog["references"]["implementation"]["repository"] == (
        "https://github.com/adibirzu/oci-prometheus-otel-monitoring"
    )


@pytest.mark.parametrize(("profile", "metric_prefix"), (("linux", "node_"), ("windows", "windows_")))
def test_rendered_host_dashboard_is_oci_mql_native(
    profile: str,
    metric_prefix: str,
) -> None:
    module = _load_module()

    dashboard = module.render_dashboard(
        profile=profile,
        namespace="<NAMESPACE>",
        datasource_uid="<OCI_METRICS_UID>",
    )

    assert dashboard["title"].startswith("OCI ")
    assert dashboard["refresh"] == "1m"
    assert {item["name"] for item in dashboard["templating"]["list"]} >= {
        "region",
        "compartment",
        "instance",
    }
    assert len(dashboard["panels"]) >= 8
    for panel in dashboard["panels"]:
        target = panel["targets"][0]
        assert target["rawQuery"] is True
        assert target["namespace"] == "<NAMESPACE>"
        assert metric_prefix in target["queryText"]
        assert target["datasource"]["type"] == "oci-metrics-datasource"
        assert "ocid1." not in json.dumps(panel)


def test_dashboard_cli_writes_reviewable_json_without_overwriting(
    tmp_path: pathlib.Path,
) -> None:
    output = tmp_path / "linux-dashboard.json"
    command = [
        sys.executable,
        str(SCRIPT),
        "dashboard",
        "--profile",
        "linux",
        "--namespace",
        "<NAMESPACE>",
        "--output",
        str(output),
    ]

    first = subprocess.run(command, text=True, capture_output=True, check=False)
    second = subprocess.run(command, text=True, capture_output=True, check=False)

    assert first.returncode == 0, first.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["uid"] == "oci-linux-host"
    assert second.returncode == 2
    assert "refusing to overwrite" in second.stderr


def test_observability_skill_routes_conversion_and_host_dashboard_workflow() -> None:
    skill = (
        ROOT / "skills" / "oci-observability-db" / "SKILL.md"
    ).read_text(encoding="utf-8")
    reference = (
        ROOT / "references" / "prometheus-mql-host-dashboards.md"
    ).read_text(encoding="utf-8")

    assert "PromQL" in skill
    assert "promql_to_mql.py" in skill
    assert "Linux or Windows host dashboard" in skill
    assert "validate every generated mql query" in reference.lower()
    assert "node_disk_io_time_seconds_total[1m]" in reference

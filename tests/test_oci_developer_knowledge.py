"""Behavioral tests for offline OCI capability discovery."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
BAD_ESCAPE_RECORD = {
    "id": "escaped-reference",
    "skill": "oci-cost",
    "intents": ["show OCI cost scope"],
    "exclusions": [],
    "reference": "../outside.md",
    "scripts": [],
    "tests": ["tests/test_oci_developer_knowledge.py"],
    "prerequisites": ["offline"],
    "evidence_classes": ["code-backed"],
    "mutation_policy": "read-only-default",
    "context_tier": "card",
    "status": "current",
}


@pytest.fixture(scope="module")
def knowledge():
    path = ROOT / "scripts" / "oci_developer_knowledge.py"
    spec = importlib.util.spec_from_file_location("oci_developer_knowledge", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def catalog(knowledge):
    return knowledge.load_catalog(ROOT)


def test_discover_selects_log_analytics(knowledge, catalog) -> None:
    result = knowledge.discover("Investigate rejected VCN flows in Log Analytics", catalog)
    assert result.primary is not None
    assert (result.primary.skill, result.primary.id) == (
        "oci-log-analytics",
        "log-analytics-investigation",
    )


def test_discover_preserves_tied_routes_as_fallbacks(knowledge, catalog) -> None:
    result = knowledge.discover("make my OCI application secure", catalog)
    assert result.primary is None
    assert result.fallbacks
    assert result.clarifying_question


def test_sanitize_query_rejects_token_shaped_input(knowledge) -> None:
    with pytest.raises(knowledge.CatalogError, match="sensitive input"):
        knowledge.sanitize_query("Authorization: Bearer abcdefghijklmnop")


def test_discovery_never_calls_subprocess(monkeypatch, knowledge, catalog) -> None:
    monkeypatch.setattr(subprocess, "run", lambda *_args, **_kwargs: pytest.fail("must stay offline"))
    result = knowledge.discover("show OCI cost scope", catalog)
    assert result.primary is not None


def test_render_card_is_bounded_to_operational_fields(knowledge, catalog) -> None:
    result = knowledge.discover("show OCI cost scope", catalog)
    card = knowledge.render_card(result)
    assert set(card["primary"]) == knowledge.CARD_FIELDS
    assert "intents" not in card["primary"]
    assert "tests" not in card["primary"]


def test_validate_catalog_rejects_path_escape(knowledge, tmp_path) -> None:
    with pytest.raises(knowledge.CatalogError, match="repository-relative"):
        knowledge.validate_catalog(tmp_path, knowledge.parse_capabilities([BAD_ESCAPE_RECORD]))


def test_source_catalog_test_evidence_resolves(knowledge, catalog) -> None:
    report = knowledge.validate_catalog(ROOT, catalog, include_test_evidence=True)
    assert report["capability_count"] == 28


def test_measure_uses_a_local_context_proxy(knowledge, catalog) -> None:
    report = knowledge.measure("inspect OKE readiness", knowledge.discover("inspect OKE readiness", catalog), ROOT)
    assert report["measurement_kind"] == "local-context-proxy"
    assert report["not_a_model_token_measurement"] is True
    assert report["estimated_token_proxy"] == (report["selected_bytes"] + 3) // 4


def test_scenarios_are_sanitized_and_route_to_catalogued_capabilities(knowledge, catalog) -> None:
    scenarios = json.loads((ROOT / "evals" / "developer-knowledge-scenarios.json").read_text(encoding="utf-8"))
    assert scenarios["schema_version"] == 1
    for scenario in scenarios["scenarios"]:
        assert {"id", "query", "expected_capability", "expected_skill", "expected_context_tier"} <= set(scenario)
        if scenario["expected_capability"] is not None:
            result = knowledge.discover(scenario["query"], catalog)
            assert result.primary is not None
            assert result.primary.id == scenario["expected_capability"]
            assert result.primary.skill == scenario["expected_skill"]


def test_cli_validate_and_measure_are_local_json_reports() -> None:
    script = ROOT / "scripts" / "oci_developer_knowledge.py"
    validate = subprocess.run([sys.executable, str(script), "validate", "--format", "json"], cwd=ROOT, check=True, capture_output=True, text=True)
    measure = subprocess.run([sys.executable, str(script), "measure", "--query", "inspect OKE readiness", "--format", "json"], cwd=ROOT, check=True, capture_output=True, text=True)
    assert json.loads(validate.stdout)["capability_count"] == 28
    assert json.loads(measure.stdout)["measurement_kind"] == "local-context-proxy"


def test_provider_requires_explicit_oci_genai(knowledge) -> None:
    assert knowledge.build_provider_envelope(None, None, None, "summarize OKE routes") == {
        "mode": "offline",
        "availability": "unavailable",
        "reason": "explicit provider required",
    }


def test_provider_rejects_restricted_data(knowledge) -> None:
    with pytest.raises(knowledge.CatalogError, match="data classification"):
        knowledge.build_provider_envelope("oci-genai", "named-context", "restricted", "summarize OKE routes")


def test_provider_envelope_is_non_invoking_and_sanitized(knowledge) -> None:
    envelope = knowledge.build_provider_envelope("oci-genai", "workload-identity", "approved-redacted", "summarize OKE routes")
    assert envelope["invocation_enabled"] is False
    assert envelope["model_availability"] == "unverified"
    assert envelope["query"] == "summarize OKE routes"

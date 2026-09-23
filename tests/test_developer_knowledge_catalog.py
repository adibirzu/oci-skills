"""Contracts for the local-first developer knowledge catalog."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "docs" / "product" / "contracts" / "developer-knowledge-catalog.json"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_every_routable_skill_has_a_current_capability() -> None:
    catalog = _json(CATALOG)
    skills = {path.parent.name for path in (ROOT / "skills").glob("*/SKILL.md")} - {"oci-administrator"}
    current = {
        item["skill"]
        for item in catalog["capabilities"]
        if item["status"] == "current"
    }
    assert skills <= current


def test_catalog_paths_and_enums_are_valid() -> None:
    catalog = _json(CATALOG)
    for item in catalog["capabilities"]:
        assert (ROOT / "skills" / item["skill"] / "SKILL.md").is_file()
        assert (ROOT / item["reference"]).is_file()
        assert item["context_tier"] in {"card", "reference", "deep-reference", "live-read"}
        assert item["status"] in {"current", "future", "unsupported"}


def test_customer_docs_do_not_claim_actual_token_savings() -> None:
    text = (ROOT / "docs" / "OCI_DEVELOPER_PLUGIN.md").read_text(encoding="utf-8")
    assert "local-context-proxy" in text
    assert "not a model-token measurement" in text
    assert "independent forward evaluation" in text

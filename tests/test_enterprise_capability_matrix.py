"""Offline contracts for the ER-016 through ER-020 capability matrix."""
from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "docs" / "product" / "contracts" / "enterprise-capability-matrix.json"


def test_enterprise_matrix_covers_the_canonical_skill_catalog() -> None:
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    catalog = json.loads(
        (ROOT / "docs" / "product" / "contracts" / "capability-catalog.json").read_text(encoding="utf-8")
    )
    rows = matrix["capabilities"]
    expected_skills = {entry["skill"] for entry in catalog["capabilities"]}

    assert matrix["schema_version"] == 1
    assert {row["skill"] for row in rows} == expected_skills
    assert len(rows) == len(expected_skills)

    for row in rows:
        assert set(row) == {
            "skill", "owner", "journey", "implementation_task", "provider_boundary",
            "acceptance_evidence", "unsupported_states", "evidence_class",
        }
        assert row["implementation_task"] in {"ER-016", "ER-017", "ER-018", "ER-019", "ER-020"}
        assert row["provider_boundary"] in {"offline-only", "named-context-read-only", "approved-canary"}
        assert row["evidence_class"] in {"code-backed", "locally-verified", "provider-pending"}
        assert row["journey"] and row["acceptance_evidence"]
        assert isinstance(row["unsupported_states"], list) and row["unsupported_states"]

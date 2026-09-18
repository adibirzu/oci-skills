"""Offline contracts for the OCI AIOps agent evaluation skill."""
from __future__ import annotations

import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parent.parent
DATASET = (
    ROOT
    / "skills"
    / "oci-aiops-agent-evaluation"
    / "assets"
    / "datasets"
    / "oci-platform-operations-evaluation-cases.v1.jsonl"
)


def test_aiops_dataset_is_redacted_tenant_neutral_and_evaluation_ready() -> None:
    rows = [json.loads(line) for line in DATASET.read_text(encoding="utf-8").splitlines()]
    required = {
        "id",
        "domain",
        "task",
        "evidence_class",
        "available_evidence",
        "expected_conclusion",
        "allowed_tool_paths",
        "mutation_policy",
        "expected_output_checks",
        "failure_categories",
        "review_status",
    }

    assert len(rows) >= 6
    assert len({row["id"] for row in rows}) == len(rows)
    for row in rows:
        assert required <= set(row)
        assert row["evidence_class"] == "synthetic"
        assert row["review_status"] == "review_required"
        assert row["mutation_policy"] in {"read_only", "approval_required"}
        assert row["allowed_tool_paths"]
        assert row["expected_output_checks"]
        assert row["failure_categories"]

    dataset_text = DATASET.read_text(encoding="utf-8").lower()
    for forbidden in ("ocid1.", "api_key", "secret_key", "private_ip"):
        assert forbidden not in dataset_text

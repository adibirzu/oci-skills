"""ER-009 source-derived operator inventory contracts."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "operator_inventory.py"
OUTPUT = ROOT / "docs" / "generated" / "operator-inventory.json"
SPEC = importlib.util.spec_from_file_location("operator_inventory", SCRIPT)
assert SPEC and SPEC.loader
operator_inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(operator_inventory)


def test_checked_in_operator_inventory_reconciles_skills_harnesses_and_support() -> None:
    expected = operator_inventory.build_inventory()
    assert json.loads(OUTPUT.read_text(encoding="utf-8")) == expected
    assert expected["skill_count"] == 29
    assert set(expected["harnesses"]) == {"claude", "codex", "gemini", "antigravity"}
    assert set(expected["support_documents"]) == {
        "SECURITY.md", "SUPPORT.md", "THIRD_PARTY_NOTICES.md", "docs/INSTALL_ROLLBACK.md"
    }
    assert all(skill["evidence_class"] for skill in expected["skills"])
    assert all(skill["provider_boundary"] for skill in expected["skills"])
    assert all(skill["access_prerequisites"] for skill in expected["skills"])
    assert all(skill["mutation_policy"] for skill in expected["skills"])
    assert {skill["version_status"] for skill in expected["skills"]} == {"source-unversioned"}
    for skill in expected["skills"]:
        assert set(skill["workflow"]) == {
            "inputs", "discovery", "execution", "outputs", "failure_modes",
            "cost_retention", "recovery", "cleanup", "verification",
        }


def test_quickstart_links_the_source_derived_operator_inventory() -> None:
    quickstart = (ROOT / "docs" / "QUICKSTART.md").read_text(encoding="utf-8")
    assert "operator-inventory.json" in quickstart


def test_operator_inventory_check_fails_closed_when_stale(tmp_path: Path) -> None:
    stale = tmp_path / "operator-inventory.json"
    stale.write_text("{}\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(stale), "--check"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert "stale" in result.stderr


def test_operator_inventory_cli_writes_then_verifies_a_public_source_derived_artifact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    output = tmp_path / "operator-inventory.json"

    assert operator_inventory.main(["--output", str(output)]) == 0
    assert json.loads(output.read_text(encoding="utf-8"))["skill_count"] == 29
    assert operator_inventory.main(["--output", str(output), "--check"]) == 0
    assert capsys.readouterr().err == ""


def test_operator_inventory_cli_rejects_missing_or_symlinked_check_target(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "missing.json"
    assert operator_inventory.main(["--output", str(missing), "--check"]) == 1
    assert "missing or a symlink" in capsys.readouterr().err

    output = tmp_path / "inventory.json"
    assert operator_inventory.main(["--output", str(output)]) == 0
    linked = tmp_path / "linked.json"
    linked.symlink_to(output)
    assert operator_inventory.main(["--output", str(linked), "--check"]) == 1
    assert "missing or a symlink" in capsys.readouterr().err

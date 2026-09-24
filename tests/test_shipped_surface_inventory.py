"""ER-008/ER-009 public shipped-surface inventory contracts."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/shipped_surface_inventory.py"
OUTPUT = ROOT / "docs/generated/shipped-surface-inventory.json"
SPEC = importlib.util.spec_from_file_location("shipped_surface_inventory", SCRIPT)
assert SPEC and SPEC.loader
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


def test_checked_in_inventory_is_current_and_covers_packaged_python_helpers() -> None:
    expected = inventory.build_inventory()
    assert json.loads(OUTPUT.read_text(encoding="utf-8")) == expected
    paths = {entry["path"] for entry in expected["surfaces"]}
    assert "scripts/enterprise_workflow.py" in paths
    assert "scripts/shipped_surface_inventory.py" in paths
    assert any(path.startswith("skills/oci-diagramming/") for path in paths)
    assert all(entry["classification"] in {"executable", "reviewed-non-executable-source"} for entry in expected["surfaces"])


def test_inventory_covers_source_only_release_and_safety_helpers() -> None:
    """ER-008: source-distributed helpers cannot escape executable inventory."""
    entries = {entry["path"]: entry for entry in inventory.build_inventory()["surfaces"]}

    for path in (
        "scripts/check_action_contracts.py",
        "scripts/forward_eval.py",
        "scripts/redaction_gate.py",
        "scripts/release_evidence_packet.py",
    ):
        assert entries[path]["distribution"] == "source-only"


def test_inventory_check_fails_closed_for_stale_artifact(tmp_path: Path) -> None:
    stale = tmp_path / "inventory.json"
    stale.write_text("{}\n", encoding="utf-8")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(stale), "--check"],
        text=True, capture_output=True, check=False,
    )
    assert result.returncode == 1
    assert "stale" in result.stderr


def test_inventory_check_rejects_a_symlinked_output_path(tmp_path: Path) -> None:
    output = tmp_path / "inventory.json"
    assert inventory.main(["--output", str(output)]) == 0
    linked = tmp_path / "linked.json"
    linked.symlink_to(output)

    assert inventory.main(["--output", str(linked), "--check"]) == 1


def test_public_docs_link_support_security_rollback_and_inventory() -> None:
    text = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ("README.md", "docs/QUICKSTART.md")
    )
    for link in ("SECURITY.md", "SUPPORT.md", "INSTALL_ROLLBACK.md", "shipped-surface-inventory.json"):
        assert link in text

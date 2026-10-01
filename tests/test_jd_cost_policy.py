"""Guard the low-cost JD route and its inert role templates."""

from pathlib import Path
import json
import re
import tomllib


SKILL = Path(__file__).resolve().parents[1] / "plugins/just-do-it/skills/jd"


def test_entry_is_small_and_all_local_references_resolve() -> None:
    entry = (SKILL / "SKILL.md").read_text(encoding="utf-8")
    assert len(entry.split()) < 900
    for path in [SKILL / "SKILL.md", *sorted((SKILL / "references").glob("*.md"))]:
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "#")):
                continue
            assert (path.parent / target).is_file(), (path, target)


def test_luna_scout_is_read_only_and_implementation_combines_red_green() -> None:
    roles = SKILL / "assets/roles"
    registrations = tomllib.loads((roles / "agents.toml").read_text())["agents"]
    scout = tomllib.loads((roles / "luna-scout.toml").read_text())
    worker = tomllib.loads((roles / "implementation-worker.toml").read_text())
    planner = tomllib.loads((roles / "prd-planner.toml").read_text())
    assert registrations["luna-scout"]["config_file"] == "agents/luna-scout.toml"
    assert scout["model"].endswith("-luna")
    assert scout["sandbox_mode"] == "read-only"
    assert planner["model"].endswith("-terra")
    assert worker["model"].endswith("-luna")
    assert worker["approval_policy"] == "never"
    assert worker["sandbox_workspace_write"]["network_access"] is False
    assert "RED" in worker["developer_instructions"]
    assert "GREEN" in worker["developer_instructions"]


def test_release_claim_is_invalidated_after_skill_change() -> None:
    release = json.loads((SKILL / "assets/jd-release.json").read_text())
    assert release["status"] == "validation-pending"
    assert not all(release["gates"].values())

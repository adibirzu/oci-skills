#!/usr/bin/env python3
"""User-facing discovery contracts for the OCI skill catalog."""
from __future__ import annotations

import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAPABILITY_CATALOG = ROOT / "docs" / "product" / "contracts" / "capability-catalog.json"
README = ROOT / "README.md"
SKILL_CATALOG = ROOT / "docs" / "SKILL_CATALOG.md"


def _skill_names() -> list[str]:
    data = json.loads(CAPABILITY_CATALOG.read_text(encoding="utf-8"))
    return sorted(entry["skill"] for entry in data["capabilities"])


def test_readme_has_google_style_category_catalog() -> None:
    text = README.read_text(encoding="utf-8")
    assert "<!-- BEGIN OCI SKILLS -->" in text
    assert "<!-- END OCI SKILLS -->" in text

    for category in (
        "Start here",
        "Security and governance",
        "Infrastructure and access",
        "Data and databases",
        "Application delivery",
        "Observe and optimize",
    ):
        assert f"**{category}**" in text

    missing = [skill for skill in _skill_names() if f"./skills/{skill}" not in text]
    assert not missing, "README category catalog missing skill links: " + ", ".join(missing)


def test_skill_catalog_covers_every_capability() -> None:
    text = SKILL_CATALOG.read_text(encoding="utf-8")
    missing = [skill for skill in _skill_names() if f"../skills/{skill}/" not in text]
    assert not missing, "docs/SKILL_CATALOG.md missing skill links: " + ", ".join(missing)


def test_quickstart_points_new_users_to_catalog() -> None:
    text = (ROOT / "docs" / "QUICKSTART.md").read_text(encoding="utf-8")
    assert "[OCI skill catalog](SKILL_CATALOG.md)" in text

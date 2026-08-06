#!/usr/bin/env python3
"""Drift fence: internal relative links stay resolvable, and shared surfaces
stay reachable from at least one entrypoint.

`tests/test_routing_consistency.py::test_referenced_docs_exist` only checks
the router's (`skills/oci-administrator/SKILL.md`) own `references/*.md`
links. This file extends that guard to the other 25 skills, to `scripts/*`
and `schemas/*.json` links, and adds a light orphan check so a reference doc
or helper script that stops being linked from anywhere doesn't go unnoticed.

Scope is deliberately narrow (skill files only, basename-substring search for
orphans) to stay a cheap, low-false-positive regression fence rather than a
full documentation linter.
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SKILLS = sorted(ROOT.glob("skills/*/SKILL.md"))

REF_RE = re.compile(r"references/([A-Za-z0-9._-]+\.md)")
SCRIPT_RE = re.compile(r"scripts/([A-Za-z0-9._-]+\.(?:sh|py))")
SCHEMA_RE = re.compile(r"schemas/([A-Za-z0-9._-]+\.json)")


def _resolves(skill_md: pathlib.Path, subdir: str, name: str) -> bool:
    """True if `name` exists under repo-root `<subdir>/` or the skill's own
    local `<subdir>/` (e.g. skills/oci-observability-db/scripts/*.py)."""
    if (ROOT / subdir / name).is_file():
        return True
    return (skill_md.parent / subdir / name).is_file()


def test_every_skill_links_resolve() -> None:
    missing: list[str] = []
    for skill_md in SKILLS:
        text = skill_md.read_text(encoding="utf-8")
        for name in sorted(set(REF_RE.findall(text))):
            if not _resolves(skill_md, "references", name):
                missing.append(f"{skill_md}: references/{name} does not exist")
        for name in sorted(set(SCRIPT_RE.findall(text))):
            if not _resolves(skill_md, "scripts", name):
                missing.append(f"{skill_md}: scripts/{name} does not exist")
        for name in sorted(set(SCHEMA_RE.findall(text))):
            if not _resolves(skill_md, "schemas", name):
                missing.append(f"{skill_md}: schemas/{name} does not exist")
    assert not missing, "broken internal link(s):\n" + "\n".join(missing)


def _entrypoint_text() -> str:
    """Concatenated text of every surface an agent actually reads to find a
    reference doc: every skill, every command, docs/, README, AGENTS.md."""
    parts: list[str] = []
    for pattern in ("skills/*/SKILL.md", "skills/*/references/*.md",
                    "commands/*.md", "docs/*.md"):
        for p in ROOT.glob(pattern):
            parts.append(p.read_text(encoding="utf-8"))
    parts.append((ROOT / "README.md").read_text(encoding="utf-8"))
    parts.append((ROOT / "AGENTS.md").read_text(encoding="utf-8"))
    return "\n".join(parts)


def test_no_orphaned_reference_docs() -> None:
    """Every top-level references/*.md must be reachable from a skill,
    command, doc, README, or AGENTS.md — not only from a sibling reference."""
    text = _entrypoint_text()
    orphans = [
        p.name for p in sorted((ROOT / "references").glob("*.md"))
        if p.name not in text
    ]
    assert not orphans, f"reference doc(s) not linked from any skill/command/doc entrypoint: {orphans}"


def test_no_orphaned_top_level_scripts() -> None:
    """Every top-level scripts/*.sh|py must be mentioned somewhere outside
    its own file (a skill, command, test, CI workflow, install.sh, or another
    script that sources/imports it)."""
    scripts_dir = ROOT / "scripts"
    all_files = [
        p for p in ROOT.rglob("*")
        if p.is_file()
        and ".git" not in p.parts
        and "__pycache__" not in p.parts
        and not p.name.endswith(".pyc")
    ]
    orphans = []
    for script in sorted(scripts_dir.glob("*.sh")) + sorted(scripts_dir.glob("*.py")):
        hits = 0
        for f in all_files:
            if f == script:
                continue
            try:
                if script.name in f.read_text(encoding="utf-8", errors="ignore"):
                    hits += 1
                    break
            except (UnicodeDecodeError, OSError):
                continue
        if hits == 0:
            orphans.append(script.name)
    assert not orphans, f"script(s) under scripts/ not referenced anywhere else: {orphans}"

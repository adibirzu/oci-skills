#!/usr/bin/env python3
"""Drift fence: every domain skill must be wired consistently across the two
routing tables (SKILL.md and AGENTS.md), its referenced docs must exist, and
every eval route must point at a real domain.

This catches the failure mode where a new domain is added under skills/ but one
of the routing surfaces (or the reference file) is forgotten.
"""
from __future__ import annotations

import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROUTER = ROOT / "skills" / "oci-administrator" / "SKILL.md"
AGENTS = ROOT / "AGENTS.md"
EVALS = ROOT / "evals" / "evals.json"


def _domains() -> set[str]:
    """All domain skills (the router itself is not a routable domain)."""
    return {p.parent.name for p in ROOT.glob("skills/*/SKILL.md")} - {"oci-administrator"}


def test_every_domain_in_both_routing_tables() -> None:
    skill_md = ROUTER.read_text(encoding="utf-8")
    agents_md = AGENTS.read_text(encoding="utf-8")
    missing = []
    for domain in sorted(_domains()):
        if f"**{domain}**" not in skill_md:
            missing.append(f"{domain}: absent from SKILL.md routing table")
        if f"skills/{domain}/" not in agents_md:
            missing.append(f"{domain}: absent from AGENTS.md routing table")
    assert not missing, "routing drift:\n" + "\n".join(missing)


def test_referenced_docs_exist() -> None:
    skill_md = ROUTER.read_text(encoding="utf-8")
    refs = set(re.findall(r"references/([A-Za-z0-9._-]+\.md)", skill_md))
    assert refs, "no references/*.md links parsed from the router"
    missing = [r for r in sorted(refs) if not (ROOT / "references" / r).is_file()]
    assert not missing, f"SKILL.md links missing reference files: {missing}"


def test_eval_routes_are_real_domains() -> None:
    cases = json.loads(EVALS.read_text(encoding="utf-8"))["cases"]
    domains = _domains()
    bad = [c["id"] for c in cases
           if c.get("expect_route") is not None and c["expect_route"] not in domains]
    assert not bad, f"evals route to unknown domains: {bad}"

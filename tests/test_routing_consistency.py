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

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
ROUTER = ROOT / "skills" / "oci-administrator" / "SKILL.md"
AGENTS = ROOT / "AGENTS.md"
EVALS = ROOT / "evals" / "evals.json"
ALIGNMENT = ROOT / "references" / "oracle-skills-alignment.md"


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


def test_user_facing_domain_lists_include_all_domains() -> None:
    docs = [
        ROOT / "README.md",
        ROOT / "docs" / "QUICKSTART.md",
        ROOT / "harness" / "gemini" / "GEMINI.md",
        ROOT / "harness" / "antigravity" / "AGENTS.md",
    ]
    missing = []
    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for domain in sorted(_domains()):
            if domain not in text:
                missing.append(f"{doc.relative_to(ROOT)} missing {domain}")
    assert not missing, "domain-list drift:\n" + "\n".join(missing)


def test_codex_adapter_routing_maps_exactly_the_real_domains() -> None:
    """openai.yaml is machine-consumed: parse it and assert the routing mapping
    itself, not the raw text (a domain name in a comment must not count)."""
    adapter = ROOT / "harness" / "codex" / "agents" / "openai.yaml"
    routing = yaml.safe_load(adapter.read_text(encoding="utf-8"))["routing"]
    routed = set(routing)
    domains = _domains()
    missing = sorted(domains - routed)
    unknown = sorted(routed - domains)
    assert not missing, f"openai.yaml routing missing domains: {missing}"
    assert not unknown, f"openai.yaml routing lists unknown domains: {unknown}"
    empty = sorted(k for k, v in routing.items() if not (isinstance(v, str) and v.strip()))
    assert not empty, f"openai.yaml routing entries without a description: {empty}"


def test_no_stale_domain_count_language_in_shipped_surfaces() -> None:
    stale = re.compile(r"\b(?:six domain|four admin domain|nine domain|nine domains|9 control-plane)\b", re.I)
    scan_roots = [
        "README.md",
        "AGENTS.md",
        "commands",
        "docs",
        "evals",
        "references",
        "scripts",
        "skills",
        "harness",
        ".claude-plugin",
        ".codex-plugin",
    ]
    hits = []
    for root in scan_roots:
        path = ROOT / root
        files = [path] if path.is_file() else sorted(path.rglob("*"))
        for f in files:
            if f.is_file() and f.suffix in {"", ".md", ".py", ".sh", ".json", ".yaml", ".yml", ".toml"}:
                try:
                    text = f.read_text(encoding="utf-8")
                except UnicodeDecodeError:
                    continue
                for lineno, line in enumerate(text.splitlines(), start=1):
                    if stale.search(line):
                        hits.append(f"{f.relative_to(ROOT)}:{lineno}: {line.strip()}")
    assert not hits, "stale domain-count language:\n" + "\n".join(hits)


def test_every_routable_skill_has_common_flow_table() -> None:
    missing = []
    for domain in sorted(_domains()):
        text = (ROOT / "skills" / domain / "SKILL.md").read_text(encoding="utf-8")
        if "## Common multi-step flows" not in text:
            missing.append(domain)
    assert not missing, "skills missing Common multi-step flows: " + ", ".join(missing)


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


def test_route_out_contract_has_eval_coverage() -> None:
    cases = json.loads(EVALS.read_text(encoding="utf-8"))["cases"]
    route_out = {c.get("expect_route_out") for c in cases if c.get("expect_route_out")}
    expected = {
        "oracle/skills oci/oke",
        "oracle/skills oci/enterprise-ai",
        "oracle/skills db",
        "oracle/fusion-cloud-docs",
    }
    assert expected <= route_out, f"route-out eval coverage missing: {sorted(expected - route_out)}"

    alignment = ALIGNMENT.read_text(encoding="utf-8")
    for target in expected - {"oracle/fusion-cloud-docs"}:
        repo, domain = target.split(" ", 1)
        assert repo in alignment and domain in alignment
    assert "Oracle Fusion Cloud Applications documentation" in alignment
    assert "fusion/` domain placeholder" in alignment


def test_genai_catalog_discovery_is_live_region_scoped_and_handed_off() -> None:
    router = ROUTER.read_text(encoding="utf-8")
    command_path = ROOT / "commands" / "genai-models.md"

    assert command_path.is_file()
    command = command_path.read_text(encoding="utf-8")
    for required in (
        "read-only",
        "named context",
        "region",
        "retrieved_at",
        "oci/enterprise-ai",
        "do not use a static model list",
    ):
        assert required.lower() in f"{router}\n{command}".lower()
    assert "/oci-administrator:genai-models" in router

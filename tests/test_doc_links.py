#!/usr/bin/env python3
"""Offline lint for Oracle documentation links (no network).

Fences three invariants so doc grounding does not silently rot:

1. **Well-formed** — every `docs.oracle.com` URL in the pack is HTTPS, on the
   right host, free of spaces / `<placeholder>` tokens / stray markdown, and on
   a recognised OCI doc path.
2. **Single source of truth** — every `docs.oracle.com` URL used anywhere in
   references/skills/README/docs is registered in the central index
   `references/oracle-docs.md` (OKF index pattern).
3. **KB citation coverage** — every `## KB-<n>` entry carries a `**See:**` line
   linking an authoritative `docs.oracle.com` page (OKF citation pattern).

This is a *format* lint, not a liveness check — CI has no network. Liveness is
verified by the author when a URL is added (see oracle-docs.md).
"""
from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "references" / "oracle-docs.md"
KB = ROOT / "references" / "KB.md"

URL_RE = re.compile(r"https://docs\.oracle\.com[^\s)>\]]*")
# Accept the two real OCI doc path shapes: most pages are /en-us/iaas/…, a few
# legacy/global pages are /iaas/… or /en/solutions/… .
PATH_OK = re.compile(r"^https://docs\.oracle\.com/(en-us/iaas/|iaas/|en/)")
RETIRED_URLS = {
    "https://docs.oracle.com/en-us/iaas/Content/Compute/Tasks/runcmd.htm",
    "https://docs.oracle.com/en-us/iaas/Content/ContEng/Tasks/contenglistingclusters.htm",
    "https://docs.oracle.com/en-us/iaas/Content/Monitoring/Tasks/query-metric-data.htm",
    "https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/deletingVCN.htm",
    "https://docs.oracle.com/en-us/iaas/Content/Network/Tasks/managingVCNs_topic-Deleting_VCNs.htm",
    "https://docs.oracle.com/en-us/iaas/Content/Streaming/Tasks/creating-streams-and-stream-pools.htm",
    "https://docs.oracle.com/en-us/iaas/application-performance-monitoring/doc/manage-apm-domains.html",
    "https://docs.oracle.com/en-us/iaas/log-analytics/doc/use-cli-manage-log-analytics.html",
}


def _scan_files() -> list[pathlib.Path]:
    files: list[pathlib.Path] = []
    for sub in ("references", "skills", "docs"):
        files += sorted((ROOT / sub).rglob("*.md"))
    files.append(ROOT / "README.md")
    files.append(ROOT / "AGENTS.md")
    return [f for f in files if f.is_file()]


def _urls_in(text: str) -> list[str]:
    return URL_RE.findall(text)


def test_all_doc_urls_well_formed() -> None:
    bad: list[str] = []
    for f in _scan_files():
        for url in _urls_in(f.read_text(encoding="utf-8")):
            if "<" in url or ">" in url or " " in url:
                bad.append(f"{f.name}: placeholder/space in {url}")
            elif url.endswith((".", ",", ")")):
                bad.append(f"{f.name}: trailing punctuation in {url}")
            elif not PATH_OK.match(url):
                bad.append(f"{f.name}: unrecognised doc path {url}")
    assert not bad, "malformed Oracle doc links:\n" + "\n".join(bad)


def test_every_used_url_is_in_the_index() -> None:
    index_urls = set(_urls_in(INDEX.read_text(encoding="utf-8")))
    assert index_urls, "no URLs parsed from oracle-docs.md"
    missing: list[str] = []
    for f in _scan_files():
        if f == INDEX:
            continue
        for url in _urls_in(f.read_text(encoding="utf-8")):
            if url not in index_urls:
                missing.append(f"{f.name}: {url} not registered in oracle-docs.md")
    assert not missing, (
        "doc URLs outside the single-source-of-truth index:\n" + "\n".join(sorted(set(missing)))
    )


def test_retired_doc_urls_cannot_be_reintroduced() -> None:
    found: list[str] = []
    for f in _scan_files():
        for url in set(_urls_in(f.read_text(encoding="utf-8"))) & RETIRED_URLS:
            found.append(f"{f.relative_to(ROOT)}: {url}")
    assert not found, "retired Oracle doc URLs were reintroduced:\n" + "\n".join(found)


def test_every_kb_entry_cites_a_doc() -> None:
    text = KB.read_text(encoding="utf-8")
    # split into per-entry blocks keyed by the KB heading
    blocks = re.split(r"(?m)(?=^## KB-)", text)[1:]
    assert blocks, "no KB entries parsed"
    uncited: list[str] = []
    for blk in blocks:
        kb_id = re.match(r"## (KB-\d+)", blk).group(1)
        see = re.search(r"(?m)^\*\*See:\*\*\s*\[[^\]]+\]\((https://docs\.oracle\.com[^)]+)\)", blk)
        if not see:
            uncited.append(kb_id)
    assert not uncited, "KB entries missing a **See:** doc citation: " + ", ".join(uncited)

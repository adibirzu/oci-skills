from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
HELPER = ROOT / "docs/comics/skill_infographics.py"
COMICS = ROOT / "published/comics"


def _load_helper():
    if not HELPER.exists():
        pytest.skip("private comic helper is not available in this checkout")
    pytest.importorskip("pypdf")
    pytest.importorskip("reportlab")
    spec = importlib.util.spec_from_file_location("oci_skill_infographics", HELPER)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_private_helper_adapts_chapter_to_story_map_handoff() -> None:
    helper = _load_helper()
    config = helper.CHAPTERS["01"]

    handoff = helper.chapter_story_map_handoff(config)

    assert handoff["concept"] == "sketchnote-story-map-v1"
    assert handoff["archetype"] in {"journey", "lifecycle", "hub-spoke", "control-map"}
    assert len(handoff["clusters"]) == len(config["items"])
    assert all(cluster["anchor"]["title"] for cluster in handoff["clusters"])
    assert all(cluster["anchor"]["source_ids"] for cluster in handoff["clusters"])
    assert handoff["headline_zone"]["title"] == config["title"]


def test_chapter_four_source_selection_is_symmetric_and_grounded() -> None:
    helper = _load_helper()
    config = helper.CHAPTERS["04"]

    handoff = helper.chapter_story_map_handoff(config)
    source_ids = [source["id"] for source in handoff["sources"]]

    assert len(source_ids) == len(config["items"])
    assert source_ids == [f"oci-docs:chapter-04:{index}" for index in range(1, 7)]
    assert [cluster["anchor"]["source_ids"] for cluster in handoff["clusters"]] == [
        [source_id] for source_id in source_ids
    ]
    assert "shared_contributor" not in str(handoff)
    assert "@" not in str(handoff)


def test_public_comic_contract_is_twelve_pages_with_at_a_glance_page_two() -> None:
    pypdf = pytest.importorskip("pypdf")
    for pdf in sorted(COMICS.glob("*.pdf")):
        reader = pypdf.PdfReader(str(pdf))
        assert len(reader.pages) == 12, pdf.name
        page_two = reader.pages[1].extract_text() or ""
        last_page = reader.pages[-1].extract_text() or ""
        assert "SKILL AT A GLANCE" in page_two, pdf.name
        assert "docs.oracle.com" in last_page, pdf.name
        assert "SKILL AT A GLANCE" not in "\n".join(
            page.extract_text() or "" for page in reader.pages[2:]
        ), pdf.name


def test_private_comic_generation_and_visual_summary_evidence_are_ignored() -> None:
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for pattern in (
        "/docs/comics/",
        "docs/comics/**/prompts-private/",
        "/.comic-runs/",
        "/.visual-summary-private/",
        "/tmp/visual-summaries/",
        "visual-summary-*.source.json",
        "visual-summary-*.handoff.json",
        "visual-summary-*.qa.json",
        "visual-summary-*.evidence.json",
        "visual-summary-*.synthesis.json",
    ):
        assert pattern in ignore, pattern

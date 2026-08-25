"""Executable Office acceptance for the OCI visual-summary skill.

These tests use only synthetic local inputs.  They deliberately exercise the
bundled Artifact Tool / python-docx delivery paths instead of source-string
contracts, and never inspect a real AXM/POTX file or contact OCI.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import posixpath
import re
import struct
import subprocess
import sys
import textwrap
import zipfile
import zlib
from pathlib import Path
from xml.etree import ElementTree

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "oci-visual-summary"
PPTX_BUILDER = SKILL / "scripts" / "build_summary_pptx.mjs"
DOCX_BUILDER = SKILL / "scripts" / "build_summary_docx.py"

sys.path.insert(0, str(SKILL / "scripts"))

import storyboard  # noqa: E402
import visual_summary as summary  # noqa: E402


def _runtime_env() -> dict[str, str]:
    required = (
        "RUNTIME_NODE",
        "RUNTIME_NODE_MODULES",
        "RUNTIME_BIN_DIR",
        "RUNTIME_PYTHON",
        "PRESENTATIONS_SKILL_DIR",
        "DOCUMENTS_SKILL_DIR",
    )
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        pytest.skip("workspace Office runtime unavailable: " + ", ".join(missing))
    return {**os.environ, **{name: os.environ[name] for name in required}}


def _run(command: list[str], *, env: dict[str, str], ok: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, text=True, capture_output=True, env=env, check=False)
    if ok and result.returncode != 0:
        raise AssertionError(f"command failed ({result.returncode}): {' '.join(command)}\n{result.stdout}\n{result.stderr}")
    return result


def _solid_png(rgb: tuple[int, int, int], width: int = 3, height: int = 2) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _xml_text(package: Path) -> str:
    with zipfile.ZipFile(package) as archive:
        return "\n".join(
            archive.read(name).decode("utf-8", "ignore")
            for name in archive.namelist()
            if name.endswith((".xml", ".rels"))
        )


def _package_parts(package: Path, prefixes: tuple[str, ...]) -> dict[str, bytes]:
    with zipfile.ZipFile(package) as archive:
        return {
            name: archive.read(name)
            for name in archive.namelist()
            if name.startswith(prefixes) and "/_rels/" not in name
        }


def _relationship_source_part(rels_part: str) -> str:
    """Return the OPC owning part for a package relationship member."""
    prefix, marker, tail = rels_part.partition("/_rels/")
    if not marker or not tail.endswith(".rels"):
        raise ValueError(f"not an OPC relationship part: {rels_part}")
    return f"{prefix}/{tail[:-5]}"


def _resolve_opc_target(source_part: str, target: str) -> str:
    """Resolve an internal OPC target without permitting archive traversal."""
    if not target or "://" in target or target.startswith("//"):
        raise ValueError(f"relationship target must be a local OPC part: {target!r}")
    candidate = target.lstrip("/") if target.startswith("/") else posixpath.join(posixpath.dirname(source_part), target)
    normalized = posixpath.normpath(candidate)
    if normalized in {"", "."} or normalized.startswith("../") or normalized.startswith("/"):
        raise ValueError(f"relationship target escapes package root: {target!r}")
    return normalized


def _relationship_targets(archive: zipfile.ZipFile, rels_part: str, relationship_suffix: str) -> list[str]:
    source_part = _relationship_source_part(rels_part)
    root = ElementTree.fromstring(archive.read(rels_part))
    targets: list[str] = []
    for relationship in root:
        if not relationship.attrib.get("Type", "").endswith(relationship_suffix):
            continue
        if relationship.attrib.get("TargetMode") == "External":
            raise AssertionError(f"{rels_part} has external {relationship_suffix} relationship")
        target = _resolve_opc_target(source_part, relationship.attrib["Target"])
        assert target in archive.namelist(), f"{rels_part} points to missing package part {target}"
        targets.append(target)
    return targets


def _mapped_relationship_topology(package: Path, slide_numbers: list[int]) -> list[dict[str, str]]:
    """Capture each mapped slide's slide -> layout -> master -> theme chain."""
    with zipfile.ZipFile(package) as archive:
        topology: list[dict[str, str]] = []
        for slide_number in slide_numbers:
            slide_rels = f"ppt/slides/_rels/slide{slide_number}.xml.rels"
            layout_targets = _relationship_targets(archive, slide_rels, "/slideLayout")
            assert len(layout_targets) == 1, f"slide {slide_number} must resolve exactly one layout"
            layout = layout_targets[0]
            layout_rels = f"{posixpath.dirname(layout)}/_rels/{posixpath.basename(layout)}.rels"
            master_targets = _relationship_targets(archive, layout_rels, "/slideMaster")
            assert len(master_targets) == 1, f"layout {layout} must resolve exactly one master"
            master = master_targets[0]
            master_rels = f"{posixpath.dirname(master)}/_rels/{posixpath.basename(master)}.rels"
            theme_targets = _relationship_targets(archive, master_rels, "/theme")
            assert len(theme_targets) == 1, f"master {master} must resolve exactly one theme"
            topology.append({"layout": layout, "master": master, "theme": theme_targets[0]})
        return topology


def _pptx_image_relationship_targets(package: Path) -> list[str]:
    """Resolve every slide image relationship by type to a concrete ZIP part."""
    with zipfile.ZipFile(package) as archive:
        targets: list[str] = []
        for rels_part in archive.namelist():
            if re.fullmatch(r"ppt/slides/_rels/slide\d+\.xml\.rels", rels_part):
                targets.extend(_relationship_targets(archive, rels_part, "/image"))
        return targets


def _template_semantics(package: Path) -> dict[str, object]:
    """Read stable template semantics without treating OOXML serialization as identity.

    Artifact Tool intentionally normalizes imported XML.  This acceptance gate
    therefore checks the actual master → layout → slide semantic contract and
    records byte drift separately instead of inviting prohibited OOXML repair.
    """
    with zipfile.ZipFile(package) as archive:
        names = archive.namelist()
        read = lambda name: archive.read(name).decode("utf-8", "ignore")
        themes = sorted(name for name in names if re.fullmatch(r"ppt/theme/theme\d+\.xml", name))
        masters = sorted(name for name in names if re.fullmatch(r"ppt/slideMasters/slideMaster\d+\.xml", name))
        layouts = sorted(name for name in names if re.fullmatch(r"ppt/slideLayouts/slideLayout\d+\.xml", name))
        presentation = read("ppt/presentation.xml")
        return {
            "theme_count": len(themes),
            "master_count": len(masters),
            "layout_count": len(layouts),
            "theme_names": [re.search(r'<a:theme[^>]*name="([^"]+)"', read(name)).group(1) for name in themes],
            "master_names": [re.search(r'<p:cSld[^>]*name="([^"]+)"', read(name)).group(1) for name in masters],
            "layout_names": [re.search(r'<p:cSld[^>]*name="([^"]+)"', read(name)).group(1) for name in layouts],
            "master_layout_links": sum(read(name).count("<p:sldLayoutId") for name in masters),
            "slide_master_links": presentation.count("<p:sldMasterId"),
        }


def _write_synthetic_template(tmp_path: Path, env: dict[str, str]) -> Path:
    source = tmp_path / "synthetic-template.pptx"
    script = tmp_path / "make-synthetic-template.mjs"
    script.write_text(
        textwrap.dedent(
            """
            import path from "node:path";
            import { pathToFileURL } from "node:url";
            const modulePath = path.join(process.env.RUNTIME_NODE_MODULES, "@oai", "artifact-tool", "dist", "artifact_tool.mjs");
            const { Presentation, PresentationFile } = await import(pathToFileURL(modulePath).href);
            const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
            const master = presentation.masters.add("Synthetic distinct master");
            const layout = presentation.layouts.add("Synthetic distinct layout");
            layout.setParentLayoutId(master.id);
            layout.placeholders.add({ type: "title", index: 0, geometry: "textbox", position: { left: 72, top: 64, width: 900, height: 80 }, text: "Synthetic title" });
            for (let index = 1; index <= 3; index += 1) {
              const slide = presentation.slides.add();
              slide.setLayout(layout);
              const target = slide.shapes.add({ geometry: "textbox", name: `editable-target-${index}`, position: { left: 96, top: 190, width: 720, height: 72 } });
              target.text = `ORIGINAL TARGET ${index}`;
              target.text.style = { fontSize: 30, bold: true, color: "#18202B" };
              const stable = slide.shapes.add({ geometry: "textbox", name: `stable-frame-${index}`, position: { left: 96, top: 316, width: 820, height: 60 } });
              stable.text = `KEEP STABLE ${index}`;
              stable.text.style = { fontSize: 22, color: "#3C4655" };
              const rail = slide.shapes.add({ geometry: "rect", name: `stable-rail-${index}`, position: { left: 96, top: 420, width: 960, height: 18 }, fill: index === 2 ? "#2E7490" : "#C74634", line: { style: "solid", fill: "none", width: 0 } });
            }
            const file = await PresentationFile.exportPptx(presentation);
            await file.save(process.argv[2]);
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )
    _run([env["RUNTIME_NODE"], str(script), str(source)], env=env)
    return source


def _inspect_template(source: Path, workspace: Path, env: dict[str, str]) -> tuple[dict, list[dict]]:
    helper = Path(env["PRESENTATIONS_SKILL_DIR"]) / "template_following_scripts" / "inspect_template_deck.mjs"
    _run([env["RUNTIME_NODE"], str(helper), "--workspace", str(workspace), "--pptx", str(source)], env=env)
    manifest = json.loads((workspace / "template-inspect" / "template-manifest.json").read_text(encoding="utf-8"))
    records = [json.loads(line) for line in (workspace / "template-inspect" / "template-inspect.ndjson").read_text(encoding="utf-8").splitlines() if line.strip()]
    return manifest, records


def _shape_id(records: list[dict], *, slide: int, name: str) -> str:
    matches = [record["id"] for record in records if record.get("slide") == slide and record.get("name") == name]
    assert len(matches) == 1, (slide, name, matches)
    return matches[0]


def _template_map(records: list[dict]) -> dict:
    return {
        "outputSlides": [
            {
                "outputSlide": 1,
                "sourceSlide": 2,
                "narrativeRole": "opening thesis",
                "audienceRole": "at-a-glance",
                "reuseMode": "duplicate-slide",
                "editTargets": [{
                    "action": "rewrite",
                    "sourceElementId": _shape_id(records, slide=2, name="editable-target-2"),
                    "replacementText": "Synthetic acceptance",
                    "handoffBinding": {"audienceRole": "at-a-glance", "semanticBlock": "title", "sourceIds": ["https://docs.oracle.com/synthetic"]},
                }],
            },
            {
                "outputSlide": 2,
                "sourceSlide": 1,
                "narrativeRole": "evidence summary",
                "audienceRole": "workflow",
                "reuseMode": "duplicate-slide",
                "editTargets": [{
                    "action": "rewrite",
                    "sourceElementId": _shape_id(records, slide=1, name="editable-target-1"),
                    "replacementText": "Synthetic takeaway",
                    "handoffBinding": {"audienceRole": "workflow", "semanticBlock": "takeaway", "sourceIds": ["https://docs.oracle.com/synthetic"]},
                }],
            },
        ],
        "omittedSourceSlides": [{"sourceSlide": 3, "reason": "synthetic appendix pattern not needed"}],
    }


def _accepted_handoff(tmp_path: Path) -> summary._StoryboardHandoff:
    if storyboard.Image is None:
        pytest.skip("accepted storyboard fixture needs Pillow; run this acceptance path with the bundled workspace Python runtime")
    official = "https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm"
    private = "https://private.example.invalid/customer/security-notes.pdf"
    non_oracle = "https://example.org/untrusted-reference"
    spec = {
        "schema_version": 1,
        "title": "Observe the AI episode",
        "takeaway": "Every operational step remains attributable.",
        "audience": "Operators",
        "purpose": "Explain the monitored execution path.",
        "domain": "observability",
        "evidence_class": "code-backed",
        "archetype": "journey",
        "visual_direction": {
            "concept": "sketchnote-story-map-v1",
            "dominant_path": "episode telemetry path",
            "mascot_mode": "nimb-operator",
            "style_preset": "oci-doodle",
            "doodle_level": "rich",
        },
        "anchors": [
            {
                "title": "Correlate the episode",
                "detail": "Join model, tool, policy, and evaluation spans.",
                "evidence_class": "code-backed",
                "source_ids": [official, private, non_oracle],
                "services": ["OCI Application Performance Monitoring"],
            },
            {
                "title": "Collect the signal",
                "detail": "Capture trace, metric, log, and event context.",
                "evidence_class": "code-backed",
                "source_ids": [official, private, non_oracle],
                "services": ["OCI Application Performance Monitoring"],
            },
            {
                "title": "Protect the payload",
                "detail": "Use governed fields and approved excerpts only.",
                "evidence_class": "code-backed",
                "source_ids": [official, private, non_oracle],
                "services": ["OCI Application Performance Monitoring"],
            },
            {
                "title": "Learn from evidence",
                "detail": "Turn observable outcomes into an operator action.",
                "evidence_class": "code-backed",
                "source_ids": [official, private, non_oracle],
                "services": ["OCI Application Performance Monitoring"],
            },
        ],
        "sources": [
            {"title": "OCI Monitoring", "url": official, "claim_ids": ["claim-1"], "accessed": "2026-08-24", "classification": "public"},
            {"title": "Private customer notes", "url": private, "claim_ids": ["claim-2"], "accessed": "2026-08-24", "classification": "private"},
            {"title": "Non-Oracle reference", "url": non_oracle, "claim_ids": ["claim-3"], "accessed": "2026-08-24", "classification": "public"},
        ],
        "privacy": {"classification": "private", "public_eligible": False},
        "outputs": {"formats": ["pptx", "docx"], "aspect_ratio": "16:9"},
        "accessibility": {"reading_order": ["title", "anchors"], "alt_text": "An AI episode monitoring workflow."},
    }
    response = {
        "schema_version": 1,
        "classification": "private-generation-input",
        "coverage": "hero-workflow-scenes-service-map-summary",
        "project_thesis": "Show one monitored AI episode.",
        "units": [{
            "id": "unit-1",
            "summary_anchor_id": "anchor-1",
            "artifact_job": "Make correlation visible.",
            "thesis": "Each step emits attributable telemetry.",
            "register": "explainer",
            "staging": "foreground-left",
            "physical_move": "routes the episode through the telemetry path",
            "objects": ["trace ribbon", "policy gate"],
            "character_action": "routes the episode through the telemetry path",
            "interaction_geometry": "hands guide the trace ribbon through the policy gate",
            "cast_role": "operator",
            "service_ids": ["OCI Application Performance Monitoring"],
            "service_context": [{"canonical_service_id": "oci.apm", "display_name": "OCI Application Performance Monitoring"}],
            "source_ids": [official, private, non_oracle],
            "evidence_class": "code-backed",
            "text_policy": "deterministic-outside-art",
            "alt_text": "An operator threads one AI episode through telemetry and policy gates.",
        }],
        "audience_sequence": ["unit-1"],
    }
    accepted = storyboard.validate_storyboard_response(response, spec)
    scene = tmp_path / "reviewed-scene.png"
    scene.write_bytes(_solid_png((50, 120, 170)))
    scene_digest = hashlib.sha256(scene.read_bytes()).hexdigest()
    manifest_path = tmp_path / "scene-manifest.json"
    manifest_path.write_text(json.dumps({
        "schema_version": 1,
        "scenes": [{
            "unit_id": "unit-1",
            "path": scene.name,
            "sha256": scene_digest,
            "character_pack": "nimb-operator-v1",
            "model_sheet_digest": "a" * 64,
            "style_anchor_digest": None,
            "generator": "offline-synthetic-test",
            "rights": "original",
            "review_status": "approved",
            "qa": {name: "pass" for name in ("thesis", "artifact_job", "topology", "load_bearing_character", "text_free_art", "originality", "style_consistency")},
        }],
    }), encoding="utf-8")
    manifest = storyboard.load_scene_manifest(manifest_path, accepted)
    icons = [{
        "unit_id": "unit-1",
        "canonical_service_id": "oci.apm",
        "display_name": "OCI Application Performance Monitoring",
        "mapping_type": "exact-service",
        "alt_text": "OCI APM service icon",
        "private_catalog_asset_id": "apm-icon",
    }]
    handoff = summary.build_storyboard_handoff(spec, accepted, manifest, icons, width=800, height=600)
    passive_svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 16 16"><path fill="#C74634" d="M1 1h14v14H1z"/></svg>'
    handoff["private_icon_resolution"] = {
        "classification": "internal",
        "apm-icon": {"bytes": passive_svg, "sha256": hashlib.sha256(passive_svg).hexdigest()},
    }
    return handoff


def test_synthetic_template_mode_executes_complete_map_and_preserves_structure(tmp_path: Path) -> None:
    env = _runtime_env()
    source = _write_synthetic_template(tmp_path, env)
    workspace = tmp_path / "inventory"
    workspace.mkdir()
    manifest, records = _inspect_template(source, workspace, env)
    assert manifest["slideCount"] == 3
    frame_map = tmp_path / "template-frame-map.json"
    frame_map.write_text(json.dumps(_template_map(records)), encoding="utf-8")
    # Exercise the same helper used by the production route so serialization
    # drift is measured at both Artifact Tool boundaries: source -> starter
    # and starter -> final.  Semantic fidelity, rather than XML identity, is
    # the accepted artifact-tool-only contract.
    starter = tmp_path / "template-starter.pptx"
    prepare = Path(env["PRESENTATIONS_SKILL_DIR"]) / "template_following_scripts" / "prepare_template_starter_deck.mjs"
    _run([
        env["RUNTIME_NODE"], str(prepare), "--workspace", str(workspace),
        "--pptx", str(source), "--map", str(frame_map), "--out", str(starter),
    ], env=env)
    handoff = tmp_path / "handoff.json"
    handoff.write_text('{"schema_version":1,"title":"Synthetic acceptance","takeaway":"Synthetic takeaway","source_register":[{"url":"https://docs.oracle.com/synthetic"}]}\n', encoding="utf-8")
    output = tmp_path / "template-result.pptx"

    _run([
        env["RUNTIME_NODE"], str(PPTX_BUILDER), "--handoff", str(handoff), "--out", str(output),
        "--template", str(source), "--template-map", str(frame_map),
    ], env=env)

    result_workspace = tmp_path / "result-inventory"
    result_workspace.mkdir()
    final_manifest, final_records = _inspect_template(output, result_workspace, env)
    assert final_manifest["slideCount"] == 2
    final_text = "\n".join(str(record.get("text", record.get("textPreview", ""))) for record in final_records)
    assert "Synthetic acceptance" in final_text and "Synthetic takeaway" in final_text
    assert "KEEP STABLE 2" in final_text and "KEEP STABLE 1" in final_text
    assert "ORIGINAL TARGET 2" not in final_text and "ORIGINAL TARGET 1" not in final_text

    prefixes = ("ppt/theme/", "ppt/slideMasters/", "ppt/slideLayouts/")
    source_parts = _package_parts(source, prefixes)
    starter_parts = _package_parts(starter, prefixes)
    output_parts = _package_parts(output, prefixes)
    source_semantics = _template_semantics(source)
    assert source_semantics == _template_semantics(starter) == _template_semantics(output)
    # The output is intentionally source slides 2 then 1.  Topology is
    # compared in output order so mapped frame identity includes its complete
    # slide -> layout -> master -> theme relationship path.
    source_topology = _mapped_relationship_topology(source, [2, 1])
    starter_topology = _mapped_relationship_topology(starter, [1, 2])
    final_topology = _mapped_relationship_topology(output, [1, 2])
    assert source_topology == starter_topology == final_topology
    # Artifact Tool's import/export is semantically preserving, not byte
    # preserving. This is a deliberately explicit receipt of that known
    # serialization drift; the gate above protects the actual template frame.
    assert source_parts != starter_parts
    assert starter_parts != output_parts


@pytest.mark.parametrize("plan_mutation", ["missing-source-inventory", "out-of-range", "missing-edit-plan"])
def test_template_mode_rejects_incomplete_or_invalid_plan(tmp_path: Path, plan_mutation: str) -> None:
    env = _runtime_env()
    source = _write_synthetic_template(tmp_path, env)
    workspace = tmp_path / "inventory"
    workspace.mkdir()
    _manifest, records = _inspect_template(source, workspace, env)
    payload = _template_map(records)
    if plan_mutation == "missing-source-inventory":
        payload["omittedSourceSlides"] = []
    elif plan_mutation == "out-of-range":
        payload["outputSlides"][0]["sourceSlide"] = 99
    else:
        payload["outputSlides"][0]["editTargets"] = []
    frame_map = tmp_path / "bad-map.json"
    frame_map.write_text(json.dumps(payload), encoding="utf-8")
    handoff = tmp_path / "handoff.json"
    handoff.write_text('{"schema_version":1}\n', encoding="utf-8")
    output = tmp_path / "must-not-exist.pptx"
    result = _run([
        env["RUNTIME_NODE"], str(PPTX_BUILDER), "--handoff", str(handoff), "--out", str(output),
        "--template", str(source), "--template-map", str(frame_map),
    ], env=env, ok=False)
    assert result.returncode != 0
    assert not output.exists()


def test_production_docx_from_accepted_handoff_filters_sources_and_preserves_accessibility(tmp_path: Path) -> None:
    env = _runtime_env()
    handoff = _accepted_handoff(tmp_path)
    office = summary._office_handoff(handoff)
    assert office["source_register"] == [{
        "title": "OCI Monitoring",
        "url": "https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm",
    }]
    handoff_path = tmp_path / "office-handoff.json"
    handoff_path.write_text(json.dumps(office), encoding="utf-8")
    previews = []
    for index, page in enumerate(summary._storyboard_physical_pages(office["pages"]), start=1):
        preview = tmp_path / f"preview-{index}.png"
        preview.write_bytes(_solid_png((80 + index, 120, 160)))
        previews.append({
            "role": page["role"],
            "audience_role": page.get("audience_role", page["role"]),
            "page_number": page.get("page_number", 1),
            "page_count": page.get("page_count", 1),
            "path": str(preview),
            "alt_text": f"Reviewed {_storyboard_role_label(page.get('audience_role', page['role']))} visual",
        })
    preview_manifest = tmp_path / "previews.json"
    preview_manifest.write_text(json.dumps(previews), encoding="utf-8")
    output = tmp_path / "summary.docx"
    _run([
        env["RUNTIME_PYTHON"], str(DOCX_BUILDER), "--handoff", str(handoff_path), "--preview-manifest", str(preview_manifest), "--out", str(output),
    ], env=env)

    with zipfile.ZipFile(output) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
        rels = archive.read("word/_rels/document.xml.rels").decode("utf-8")
        core = archive.read("docProps/core.xml").decode("utf-8")
        all_text = "\n".join(archive.read(name).decode("utf-8", "ignore") for name in archive.namelist() if name.endswith((".xml", ".rels")))
    assert "Project promise" in document_xml and "OCI service map" in document_xml and "At a glance" in document_xml
    assert "Long description" in document_xml and "At-a-glance visual summary" in document_xml
    assert document_xml.count("Reviewed ") == len(previews) * 2  # alt description + visible caption
    assert 'Target="https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm"' in rels
    assert "example.org" not in all_text and "customer/security-notes" not in all_text and "private.example.invalid" not in all_text
    assert str(tmp_path) not in all_text and "prompt" not in core.casefold()
    assert "dc:creator></dc:creator" in core or "dc:creator/>" in core


def _storyboard_role_label(role: str) -> str:
    return {
        "project-promise": "project promise",
        "workflow": "workflow",
        "capability-scenes": "capability scene",
        "oci-service-map": "OCI service map",
        "at-a-glance": "at-a-glance",
    }.get(role, role)


def _write_office_handoff(tmp_path: Path) -> Path:
    handoff = _accepted_handoff(tmp_path)
    payload = summary._office_handoff(handoff)
    path = tmp_path / "office-handoff.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _official_public_stencil_office_handoff(tmp_path: Path) -> Path:
    """Portable Office input: public stencil selected, neutral glyph rendered."""
    handoff = _accepted_handoff(tmp_path)
    payload = summary._office_handoff(handoff)
    for page in payload["pages"]:
        for service in page.get("services", []):
            service.update({
                "mapping_type": "official-public-stencil",
                "rendered_as": "neutral-service-glyph",
                "fallback_reason": "format-does-not-support-drawio-stencil",
                "alt_text": "OCI APM neutral service glyph; official public stencil selection retained.",
            })
            # Public portable Office projection must not borrow a private exact
            # icon merely to make this semantic fallback look official.
            service.pop("serviceIcon", None)
            service.pop("icon", None)
    path = tmp_path / "official-public-stencil-office-handoff.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_docx_exposes_public_stencil_neutral_glyph_semantics_in_native_text(tmp_path: Path) -> None:
    env = _runtime_env()
    handoff_path = _official_public_stencil_office_handoff(tmp_path)
    output = tmp_path / "stencil-fallback.docx"
    _run([env["RUNTIME_PYTHON"], str(DOCX_BUILDER), "--handoff", str(handoff_path), "--out", str(output)], env=env)
    with zipfile.ZipFile(output) as archive:
        document_xml = archive.read("word/document.xml").decode("utf-8")
    assert "official-public-stencil" in document_xml
    assert "neutral-service-glyph" in document_xml
    assert "format-does-not-support-drawio-stencil" in document_xml


def test_pptx_exposes_public_stencil_neutral_glyph_semantics_in_text_alt_and_notes(tmp_path: Path) -> None:
    env = _runtime_env()
    handoff_path = _official_public_stencil_office_handoff(tmp_path)
    output = tmp_path / "stencil-fallback.pptx"
    _run([env["RUNTIME_NODE"], str(PPTX_BUILDER), "--handoff", str(handoff_path), "--out", str(output)], env=env)
    with zipfile.ZipFile(output) as archive:
        slide_xml = "\n".join(archive.read(name).decode("utf-8", "ignore") for name in archive.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name))
        notes_xml = "\n".join(archive.read(name).decode("utf-8", "ignore") for name in archive.namelist() if name.startswith("ppt/notesSlides/") and name.endswith(".xml"))
    assert "official-public-stencil" in slide_xml
    assert "neutral-service-glyph" in slide_xml
    assert "format-does-not-support-drawio-stencil" in slide_xml
    assert "neutral-service-glyph" in notes_xml
    assert "format-does-not-support-drawio-stencil" in notes_xml


def test_production_pptx_embeds_reviewed_scene_passive_icon_native_text_and_notes(tmp_path: Path) -> None:
    env = _runtime_env()
    handoff_path = _write_office_handoff(tmp_path)
    output = tmp_path / "summary.pptx"
    _run([env["RUNTIME_NODE"], str(PPTX_BUILDER), "--handoff", str(handoff_path), "--out", str(output)], env=env)
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        media = {name: archive.read(name) for name in names if name.startswith("ppt/media/")}
        slide_xml = "\n".join(archive.read(name).decode("utf-8", "ignore") for name in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", name))
        notes = "\n".join(archive.read(name).decode("utf-8", "ignore") for name in names if name.startswith("ppt/notesSlides/") and name.endswith(".xml"))
    assert any(payload.startswith(b"\x89PNG\r\n\x1a\n") for payload in media.values())
    assert any(b"<svg" in payload for payload in media.values())
    image_targets = _pptx_image_relationship_targets(output)
    assert image_targets
    assert all(target.startswith("ppt/media/") and target in media for target in image_targets)
    assert "Observe the AI episode" in slide_xml
    assert "OCI Application Performance Monitoring" in slide_xml
    assert "exact-service" in slide_xml and "Evidence:" in slide_xml
    assert "[Sources]" in notes and "docs.oracle.com" in notes


def test_opc_target_resolution_accepts_absolute_and_relative_package_targets() -> None:
    assert _resolve_opc_target("ppt/slides/slide1.xml", "../media/image1.png") == "ppt/media/image1.png"
    assert _resolve_opc_target("ppt/slides/slide1.xml", "/ppt/media/image1.png") == "ppt/media/image1.png"
    with pytest.raises(ValueError):
        _resolve_opc_target("ppt/slides/slide1.xml", "../../../../outside.png")


@pytest.mark.parametrize(
    ("mutation", "expected"),
    [
        ("scene-digest", "changed after approval"),
        ("icon-digest", "changed after approval"),
        ("missing-token", "verified passive-SVG token"),
        ("active-svg", "passive SVG"),
        ("style-element", "passive SVG"),
        ("style-import", "passive SVG"),
        ("external-href", "passive SVG"),
        ("external-url", "passive SVG"),
    ],
)
def test_pptx_builder_rechecks_scene_and_svg_security_boundaries(tmp_path: Path, mutation: str, expected: str) -> None:
    env = _runtime_env()
    handoff_path = _write_office_handoff(tmp_path)
    payload = json.loads(handoff_path.read_text(encoding="utf-8"))
    scene = next(scene for page in payload["pages"] for scene in page.get("scenes", []) if scene.get("reviewedScene"))["reviewedScene"]
    icon = next(service for page in payload["pages"] for service in page.get("services", []) if service.get("serviceIcon"))["serviceIcon"]
    if mutation == "scene-digest":
        scene["sha256"] = "0" * 64
    elif mutation == "icon-digest":
        icon["sha256"] = "0" * 64
    elif mutation == "missing-token":
        icon.pop("verified_by", None)
    else:
        svg = {
            "active-svg": b'<svg><script>alert(1)</script></svg>',
            "style-element": b'<svg><style>.a{fill:red}</style><path class="a" d="M0 0h1v1z"/></svg>',
            "style-import": b'<svg><style>@import "https://evil.invalid/x";</style></svg>',
            "external-href": b'<svg><image href="https://evil.invalid/x.png"/></svg>',
            "external-url": b'<svg><path fill="url(https://evil.invalid/x.svg#p)" d="M0 0h1v1z"/></svg>',
        }[mutation]
        icon["data_url"] = "data:image/svg+xml;base64," + base64.b64encode(svg).decode("ascii")
        icon["sha256"] = hashlib.sha256(svg).hexdigest()
    handoff_path.write_text(json.dumps(payload), encoding="utf-8")
    output = tmp_path / f"reject-{mutation}.pptx"
    result = _run([env["RUNTIME_NODE"], str(PPTX_BUILDER), "--handoff", str(handoff_path), "--out", str(output)], env=env, ok=False)
    assert result.returncode != 0
    assert expected in (result.stdout + result.stderr)
    assert not output.exists()

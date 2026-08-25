"""RED contracts for LLM-assisted artwork and editable visual-summary formats.

These tests intentionally describe the next visual-summary contract.  They are
kept separate from the established renderer tests so a missing capability is
easy to distinguish from a regression in the current PNG/SVG/PDF path.
"""

from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "oci-visual-summary"
sys.path.insert(0, str(SKILL / "scripts"))
import visual_summary as summary
import storyboard


def _diagram_module():
    path = ROOT / "skills" / "oci-diagramming" / "scripts" / "oci_diagram.py"
    spec = importlib.util.spec_from_file_location("oci_diagram_red_contract", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg=="
)


def valid_spec() -> dict:
    return {
        "schema_version": 1,
        "title": "Identity route",
        "takeaway": "Access is verified before use.",
        "audience": "Operators",
        "purpose": "Explain the safe path.",
        "domain": "iam",
        "evidence_class": "code-backed",
        "archetype": "journey",
        "visual_direction": {
            "concept": "sketchnote-story-map-v1",
            "dominant_path": "verified access route",
            "mascot_mode": "none",
            "doodle_density": "lively",
            "stroke_style": "marker",
        },
        "anchors": [
            {
                "title": f"Scope {index}",
                "detail": "Bound access",
                "evidence_class": "code-backed",
                "source_ids": ["https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm"],
            }
            for index in range(4)
        ],
        "sources": [
            {
                "title": "Safe source",
                "url": "https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm",
                "claim_ids": ["claim-1"],
                "accessed": "2026-08-24",
                "classification": "public",
            }
        ],
        "privacy": {"classification": "public", "public_eligible": True},
        "outputs": {"formats": ["svg", "drawio", "excalidraw", "pptx"], "aspect_ratio": "16:9"},
        "accessibility": {"reading_order": ["title", "anchors"], "alt_text": "A verified access route."},
    }


def spec_with_artwork(asset_path: Path) -> dict:
    spec = valid_spec()
    spec["artwork"] = {
        "mode": "hybrid",
        "generation_policy": "active-llm",
        "style_register": "editorial",
        # Publishable specs declare only bounded slots.  Workstation paths and
        # generated-art provenance arrive through the private manifest below.
        "slots": [
            {
                "id": "scene-identity-1",
                "anchor_id": "anchor-1",
                "role": "scene",
                "alt_text": "A hand-drawn operator tracing an identity route.",
                "prompt_hint": "Use a loose marker route and a friendly operator silhouette.",
            }
        ],
    }
    return spec


def private_artwork_manifest(asset_path: Path) -> dict:
    return {
        "schema_version": 1,
        "assets": [
            {
                "anchor_id": "anchor-1",
                "path": asset_path.name,
                "source_type": "generated",
                "rights": "original",
                "generator": "active-llm",
                "alt_text": "A hand-drawn operator tracing an identity route.",
            }
        ],
    }


def test_only_reviewed_scene_manifest_can_bind_artwork(tmp_path: Path) -> None:
    art = tmp_path / "reviewed-scene.png"
    art.write_bytes(PNG_1X1)
    accepted = {"units": [{
        "id": "unit-1", "summary_anchor_id": "anchor-1",
        "alt_text": "A reviewed operator scene.",
    }]}
    scene_path = tmp_path / "scene-manifest.json"
    scene_path.write_text(json.dumps({
        "schema_version": 1,
        "scenes": [{
            "unit_id": "unit-1", "path": art.name,
            "sha256": hashlib.sha256(PNG_1X1).hexdigest(),
            "character_pack": "nimb-operator-v1", "model_sheet_digest": "a" * 64,
            "generator": "offline-review",
            "rights": "original", "review_status": "approved",
            "qa": {name: "pass" for name in (
                "thesis", "artifact_job", "topology", "load_bearing_character",
                "text_free_art", "originality", "style_consistency",
            )},
        }],
    }), encoding="utf-8")
    reviewed = storyboard.load_scene_manifest(scene_path, accepted)
    handoff = summary.bind_reviewed_scenes(summary.build_handoff(valid_spec(), 1920, 1080), accepted, reviewed)
    cluster = next(item for item in handoff["clusters"] if item["anchor_id"] == "anchor-1")
    assert cluster["art"]["sha256"] == hashlib.sha256(PNG_1X1).hexdigest()
    swapped = json.loads(scene_path.read_text(encoding="utf-8"))
    swapped["scenes"][0]["generator"] = "manifest-swapped"
    scene_path.write_text(json.dumps(swapped), encoding="utf-8")
    stable = summary.bind_reviewed_scenes(summary.build_handoff(valid_spec(), 1920, 1080), accepted, reviewed)
    assert next(item for item in stable["clusters"] if item["anchor_id"] == "anchor-1")["art"]["generator"] == "offline-review"
    remapped = {"units": [{**accepted["units"][0], "summary_anchor_id": "anchor-2"}]}
    with pytest.raises(summary.SummaryError, match="does not match"):
        summary.bind_reviewed_scenes(summary.build_handoff(valid_spec(), 1920, 1080), remapped, reviewed)
    forged = {"schema_version": 1, "manifest_root": tmp_path, "scenes": [{
        "unit_id": "unit-1", "path": art, "review_status": "approved",
    }]}
    with pytest.raises(summary.SummaryError, match="loaded"):
        summary.bind_reviewed_scenes(summary.build_handoff(valid_spec(), 1920, 1080), accepted, forged)
    art.write_bytes(PNG_1X1 + b"drift")
    with pytest.raises(summary.SummaryError, match="digest"):
        summary.bind_reviewed_scenes(summary.build_handoff(valid_spec(), 1920, 1080), accepted, reviewed)


def test_structured_artwork_asset_is_bound_to_anchor_and_handoff_is_public_safe(tmp_path: Path) -> None:
    art = tmp_path / "identity-scene.png"
    art.write_bytes(PNG_1X1)

    public_spec = spec_with_artwork(art)
    assert str(art) not in json.dumps(public_spec)
    handoff = summary.build_handoff(public_spec, 1920, 1080)
    manifest_path = tmp_path / "artwork-manifest.json"
    manifest_path.write_text(json.dumps(private_artwork_manifest(art)), encoding="utf-8")
    handoff = summary.bind_artwork(handoff, summary.load_artwork_manifest(manifest_path))
    cluster = next(item for item in handoff["clusters"] if item["anchor_id"] == "anchor-1")
    assert cluster["art"]["source_type"] == "generated"
    assert cluster["art"]["rights"] == "original"
    assert cluster["art"]["sha256"]
    portable = summary._portable_handoff(handoff)
    assert str(art) not in json.dumps(portable)
    assert "scene_prompt" not in json.dumps(portable)
    assert "art_path" not in portable["clusters"][0]


def test_llm_artwork_request_is_deterministic_and_keeps_prompt_receipt_private(tmp_path: Path) -> None:
    art = tmp_path / "identity-scene.png"
    art.write_bytes(PNG_1X1)
    handoff = summary.build_handoff(spec_with_artwork(art), 1920, 1080)
    first = summary.artwork_request(handoff)
    second = summary.artwork_request(handoff)
    assert first == second
    assert first["classification"] == "private-generation-input"
    assert first["provider"] in {"active-llm", "provider-neutral"}
    assert first["slots"][0]["anchor_id"] == "anchor-1"
    assert first["slots"][0]["prompt"]
    assert str(art) not in json.dumps(first)


def test_rich_doodle_mode_emits_multiple_seeded_marker_kinds(tmp_path: Path) -> None:
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)
    first = summary.render_svg(handoff, tmp_path / "first.svg").read_text(encoding="utf-8")
    second = summary.render_svg(handoff, tmp_path / "second.svg").read_text(encoding="utf-8")

    assert first == second
    assert first.count('data-doodle-kind=') >= 4
    for marker in ("squiggle", "hatch", "spark", "tape"):
        assert f'data-doodle-kind="{marker}"' in first


def test_svg_native_text_preserves_spaces_and_explicit_line_layout(tmp_path: Path) -> None:
    """Native SVG viewers must not collapse authored words in storyboard labels."""
    spec = valid_spec()
    spec["title"] = "Observe every layer"
    spec["takeaway"] = "Correlate incident context and route trusted telemetry."
    spec["anchors"] = [
        {
            "title": "Correlate incident context",
            "detail": "shared context clear ownership faster learning",
            "evidence_class": "code-backed",
            "source_ids": ["https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm"],
        },
        {
            "title": "Route trusted telemetry",
            "detail": "incident signal stays attributable to one tenancy",
            "evidence_class": "code-backed",
            "source_ids": ["https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm"],
        },
        *spec["anchors"][2:],
    ]
    handoff = summary.build_handoff(spec, 1920, 1080)
    output = summary.render_svg(handoff, tmp_path / "native-text.svg")
    root = ET.parse(output).getroot()
    assert root.attrib["width"] == "1920"
    assert root.attrib["height"] == "1080"
    svg_ns = "{http://www.w3.org/2000/svg}"
    text_nodes = root.findall(f".//{svg_ns}text")
    assert text_nodes
    assert all(node.attrib.get("{http://www.w3.org/XML/1998/namespace}space") == "preserve" for node in text_nodes)
    tspans = root.findall(f".//{svg_ns}tspan")
    assert tspans
    assert all(node.attrib.get("{http://www.w3.org/XML/1998/namespace}space") == "preserve" for node in tspans)
    rendered_text = " ".join(
        " ".join("".join(tspan.itertext()) for tspan in node.findall(f"{svg_ns}tspan"))
        for node in text_nodes
    ).replace("\u00a0", " ")
    assert "Correlate incident" in rendered_text
    assert "Route trusted" in rendered_text
    assert "incidentcontext" not in rendered_text
    assert "trustedtelemetry" not in rendered_text
    serialized = output.read_text(encoding="utf-8")
    assert "Correlate\u00a0incident" in serialized
    assert "Route\u00a0trusted" in serialized
    assert "shared\u00a0context" in serialized


def test_build_outputs_accepts_editable_drawio_and_excalidraw_with_embedded_art(tmp_path: Path) -> None:
    art = tmp_path / "identity-scene.png"
    art.write_bytes(PNG_1X1)
    handoff = summary.build_handoff(spec_with_artwork(art), 1920, 1080)
    manifest_path = tmp_path / "artwork-manifest.json"
    manifest_path.write_text(json.dumps(private_artwork_manifest(art)), encoding="utf-8")
    handoff = summary.bind_artwork(handoff, summary.load_artwork_manifest(manifest_path))

    outputs = summary.build_outputs(handoff, tmp_path, {"drawio", "excalidraw"})
    assert {path.suffix for path in outputs} == {".drawio", ".excalidraw"}
    drawio = (tmp_path / "summary.drawio").read_text(encoding="utf-8")
    excalidraw = json.loads((tmp_path / "summary.excalidraw").read_text(encoding="utf-8"))
    assert "Identity route" in drawio
    assert "Scope 1" in drawio
    assert "data:image/png;base64," in drawio
    assert any(element.get("type") == "text" and "Scope 1" in element.get("text", "") for element in excalidraw["elements"])
    assert excalidraw["files"]
    assert all("http://" not in json.dumps(value) and "https://" not in json.dumps(value) for value in excalidraw["files"].values())


def test_drawio_storyboard_pages_keep_scene_text_and_icon_objects_editable(tmp_path: Path) -> None:
    """Audience pages carry native critical text, not a flattened artwork canvas."""
    scene = tmp_path / "reviewed.png"
    scene.write_bytes(PNG_1X1)
    digest = hashlib.sha256(PNG_1X1).hexdigest()
    icon = b'<svg viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>'
    public = {
        "schema_version": 1, "concept": "illo-storyboard-sequence-v1",
        "canvas": {"width": 640, "height": 360}, "title": "Observe", "takeaway": "Signals are owned.",
        "evidence_footer": "Oracle docs", "pages": [
            {"role": "project-promise", "title": "Observe", "scenes": [{"unit_id": "unit-1", "title": "Collect", "detail": "Receive signals", "evidence_class": "code-backed", "source_ids": ["doc-1"]}]},
            {"role": "workflow", "title": "Workflow", "scenes": [{"unit_id": "unit-1", "title": "Collect", "detail": "Receive signals", "evidence_class": "code-backed", "source_ids": ["doc-1"]}]},
            {"role": "capability-scenes", "title": "Capabilities", "scenes": [{"unit_id": "unit-1", "title": "Collect", "detail": "Receive signals", "evidence_class": "code-backed", "source_ids": ["doc-1"]}]},
            {"role": "oci-service-map", "title": "Services", "services": [{"unit_id": "unit-1", "canonical_service_id": "oci.monitoring", "display_name": "OCI Monitoring", "mapping_type": "exact-service", "alt_text": "Monitoring", "private_catalog_asset_id": "icon-1"}]},
            {"role": "at-a-glance", "title": "At a glance", "scenes": [{"unit_id": "unit-1", "title": "Collect", "detail": "Receive signals", "evidence_class": "code-backed", "source_ids": ["doc-1"]}], "services": [{"unit_id": "unit-1", "canonical_service_id": "oci.monitoring", "display_name": "OCI Monitoring", "mapping_type": "exact-service", "alt_text": "Monitoring", "private_catalog_asset_id": "icon-1"}]},
        ],
    }
    handoff = summary._StoryboardHandoff(public, {"unit-1": str(scene)}, {"unit-1": {"sha256": digest}})
    receipt = {"classification": "internal", "icon-1": {"bytes": icon, "sha256": hashlib.sha256(icon).hexdigest()}}

    path = summary.render_drawio(handoff, tmp_path / "story.drawio", private_icon_catalog=receipt)
    xml = path.read_text(encoding="utf-8")

    assert xml.count("oci.visual-summary.storyboard-page") == 5
    assert "oci.visual-summary.service-icon" in xml
    assert "oci.monitoring" in xml and "OCI Monitoring" in xml
    assert 'unitId="unit-1"' in xml and 'evidenceClass="code-backed"' in xml and 'sourceRefs="doc-1"' in xml
    assert "Collect" in xml and "Receive signals" in xml
    assert "data:image/png;base64," in xml and "data:image/svg+xml;base64," in xml
    assert str(tmp_path) not in xml and "restricted" not in xml.casefold()


def test_excalidraw_storyboard_uses_frames_native_text_and_digest_backed_images(tmp_path: Path) -> None:
    scene = tmp_path / "reviewed.png"
    scene.write_bytes(PNG_1X1)
    digest = hashlib.sha256(PNG_1X1).hexdigest()
    icon = b'<svg viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>'
    service = {"unit_id": "unit-1", "canonical_service_id": "oci.monitoring", "display_name": "OCI Monitoring", "mapping_type": "exact-service", "alt_text": "Monitoring", "private_catalog_asset_id": "icon-1"}
    public = {
        "schema_version": 1, "concept": "illo-storyboard-sequence-v1",
        "canvas": {"width": 640, "height": 360}, "title": "Observe", "takeaway": "Signals are owned.",
        "evidence_footer": "Oracle docs", "pages": [
            {"role": role, "title": role, "scenes": [{"unit_id": "unit-1", "title": "Collect", "detail": "Receive signals", "evidence_class": "code-backed", "source_ids": ["doc-1"]}], "services": [service]}
            for role in ("project-promise", "workflow", "capability-scenes", "oci-service-map", "at-a-glance")
        ],
    }
    handoff = summary._StoryboardHandoff(public, {"unit-1": str(scene)}, {"unit-1": {"sha256": digest}})
    receipt = {"classification": "internal", "icon-1": {"bytes": icon, "sha256": hashlib.sha256(icon).hexdigest()}}

    path = summary.render_excalidraw(handoff, tmp_path / "story.excalidraw", private_icon_catalog=receipt)
    board = json.loads(path.read_text(encoding="utf-8"))

    assert sum(element["type"] == "frame" for element in board["elements"]) == 5
    assert any(element["type"] == "text" and element.get("text") == "Collect" for element in board["elements"])
    assert any(element["type"] == "image" for element in board["elements"])
    frames = {element["id"] for element in board["elements"] if element["type"] == "frame"}
    assert all(element.get("frameId") in frames for element in board["elements"] if element["type"] != "frame")
    service_objects = [element for element in board["elements"] if element.get("customData", {}).get("canonicalServiceId") == "oci.monitoring"]
    assert service_objects and all(item["customData"].get("unitId") == "unit-1" and item["customData"].get("evidenceClass") == "code-backed" and item["customData"].get("sourceRefs") == ["doc-1"] for item in service_objects)
    assert all("/Users/" not in json.dumps(value) and "restricted" not in json.dumps(value).casefold() for value in board["files"].values())


def test_editable_storyboards_retain_all_twelve_verified_service_icons_across_pages(tmp_path: Path) -> None:
    icon = b'<svg viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>'
    public = {"schema_version": 1, "concept": "illo-storyboard-sequence-v1", "canvas": {"width": 640, "height": 360}, "title": "Observe", "takeaway": "Signals", "pages": [{
        "role": "oci-service-map", "title": "Services", "services": [
            {"unit_id": "unit-1", "canonical_service_id": f"oci.service-{index}", "display_name": f"OCI Service {index}", "mapping_type": "exact-service", "alt_text": f"Service {index}", "private_catalog_asset_id": f"icon-{index}"}
            for index in range(1, 13)
        ],
    }]}
    receipt = {"classification": "internal", **{f"icon-{index}": {"bytes": icon, "sha256": hashlib.sha256(icon).hexdigest()} for index in range(1, 13)}}
    drawio = summary.render_drawio(public, tmp_path / "services.drawio", private_icon_catalog=receipt).read_text(encoding="utf-8")
    board = json.loads(summary.render_excalidraw(public, tmp_path / "services.excalidraw", private_icon_catalog=receipt).read_text(encoding="utf-8"))

    assert drawio.count("oci.visual-summary.service-icon") == 12
    assert sum(element["type"] == "frame" for element in board["elements"]) == 2
    assert len(board["files"]) == 12
    assert all(element.get("frameId", "").startswith("storyboard-frame-") for element in board["elements"] if element["type"] != "frame")


@pytest.mark.parametrize("format_name", ["drawio", "excalidraw"])
def test_editable_outputs_keep_text_shapes_editable_and_do_not_flatten_canvas(format_name: str, tmp_path: Path) -> None:
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)
    summary.build_outputs(handoff, tmp_path, {format_name})
    raw = (tmp_path / f"summary.{format_name}").read_text(encoding="utf-8")
    assert "Identity route" in raw
    assert "Scope 1" in raw
    assert "image/png" not in raw or format_name == "excalidraw"
    if format_name == "drawio":
        assert "mxCell" in raw and "vertex=\"1\"" in raw
    else:
        scene = json.loads(raw)
        assert any(element.get("type") in {"rectangle", "text", "arrow"} for element in scene["elements"])


def test_drawio_and_excalidraw_validators_reject_remote_and_invalid_embedded_images(tmp_path: Path) -> None:
    diagram = _diagram_module()
    remote_drawio = tmp_path / "remote.drawio"
    remote_drawio.write_text(
        '<mxfile><diagram><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        '<mxCell id="img" value="" vertex="1" parent="1" style="shape=image;image=https://evil.invalid/x.png"/>'
        "</root></mxGraphModel></diagram></mxfile>",
        encoding="utf-8",
    )
    assert any("remote" in issue.lower() or "external" in issue.lower() for issue in diagram.validate_drawio(remote_drawio))

    invalid_excalidraw = tmp_path / "invalid.excalidraw"
    invalid_excalidraw.write_text(
        json.dumps(
            {
                "type": "excalidraw",
                "version": 2,
                "elements": [],
                "files": {"bad": {"mimeType": "image/png", "dataURL": "data:image/png;base64,NOT_BASE64"}},
            }
        ),
        encoding="utf-8",
    )
    assert any("image" in issue.lower() or "data" in issue.lower() for issue in diagram.validate_excalidraw(invalid_excalidraw))


def test_image_validators_reject_oversized_embedded_data(tmp_path: Path) -> None:
    diagram = _diagram_module()
    oversized = base64.b64encode(b"x" * (1024 * 1024 + 1)).decode("ascii")
    path = tmp_path / "oversized.excalidraw"
    path.write_text(
        json.dumps(
            {
                "type": "excalidraw",
                "version": 2,
                "elements": [],
                "files": {"big": {"mimeType": "image/png", "dataURL": f"data:image/png;base64,{oversized}"}},
            }
        ),
        encoding="utf-8",
    )
    assert any("size" in issue.lower() or "large" in issue.lower() or "limit" in issue.lower() for issue in diagram.validate_excalidraw(path))


def test_pptx_builder_contract_supports_artwork_slots_without_flattening_text() -> None:
    source = (SKILL / "scripts" / "build_summary_pptx.mjs").read_text(encoding="utf-8")
    assert "artwork" in source
    assert "art_slot" in source or "asset_id" in source
    assert "slide.images.add" in source
    assert "fs.readFile(cluster.art_path)" not in source
    assert "title" in source and "detail" in source
    assert "[Sources]" in source


def test_canvas_pptx_uses_bounded_readable_mixed_cast_layout_and_oracle_red_thread() -> None:
    source = (SKILL / "scripts" / "build_summary_pptx.mjs").read_text(encoding="utf-8")
    # The Canvas branch intentionally uses a fixed 3x2 slide grid: source
    # canvas bounds are too dense to scale directly into a 16:9 presentation.
    assert "const grid = [" in source
    assert source.count("width: 382, height: 238") >= 6
    assert "const accent = \"#C74634\"" in source
    assert "fontSize: 38" in source
    assert "fontSize: 20" in source
    assert "fontSize: 14" in source
    assert "canvas-scene-card-" in source
    assert "canvas-evidence-footer" in source


def test_pptx_builder_has_storyboard_pages_native_service_text_and_icons() -> None:
    source = (SKILL / "scripts" / "build_summary_pptx.mjs").read_text(encoding="utf-8")
    assert "storyboardPages" in source
    assert "storyboardPhysicalPages" in source
    assert "scenes.length / 4" in source
    assert "services.length / 8" in source
    assert "serviceIcon" in source
    assert "mappingType" in source
    assert "addText" in source
    assert "safeLinePosition" in source
    assert "prepareTemplateFollowingAdapter" in source
    assert "inspect_template_deck.mjs" in source
    assert "prepare_template_starter_deck.mjs" in source
    assert "Refusing to add blank summary slides" in source
    assert "[Sources]" in source


def test_artwork_manifest_rejects_absolute_out_of_root_and_symlink_paths(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-art.png"
    outside.write_bytes(PNG_1X1)
    absolute = tmp_path / "absolute.json"
    absolute_payload = private_artwork_manifest(outside)
    absolute_payload["assets"][0]["path"] = str(outside)
    absolute.write_text(json.dumps(absolute_payload), encoding="utf-8")
    with pytest.raises(summary.SummaryError, match="relative local file path"):
        summary.load_artwork_manifest(absolute)

    traversal_payload = private_artwork_manifest(tmp_path / "ignored.png")
    traversal_payload["assets"][0]["path"] = "../outside-art.png"
    traversal = tmp_path / "traversal.json"
    traversal.write_text(json.dumps(traversal_payload), encoding="utf-8")
    with pytest.raises(summary.SummaryError, match="safe local"):
        summary.load_artwork_manifest(traversal)

    local = tmp_path / "local.png"
    local.write_bytes(PNG_1X1)
    linked = tmp_path / "linked.png"
    linked.symlink_to(local)
    symlink_payload = private_artwork_manifest(linked)
    symlink_manifest = tmp_path / "symlink.json"
    symlink_manifest.write_text(json.dumps(symlink_payload), encoding="utf-8")
    with pytest.raises(summary.SummaryError, match="safe local"):
        summary.load_artwork_manifest(symlink_manifest)


def test_artwork_digest_change_and_symlinked_output_are_rejected(tmp_path: Path) -> None:
    art = tmp_path / "identity-scene.png"
    art.write_bytes(PNG_1X1)
    manifest = tmp_path / "artwork-manifest.json"
    manifest.write_text(json.dumps(private_artwork_manifest(art)), encoding="utf-8")
    handoff = summary.bind_artwork(
        summary.build_handoff(spec_with_artwork(art), 1920, 1080),
        summary.load_artwork_manifest(manifest),
    )
    art.write_bytes(PNG_1X1 + b"changed")
    with pytest.raises(summary.SummaryError, match="changed after manifest validation"):
        summary.render_svg(handoff, tmp_path / "changed.svg")

    plain = summary.build_handoff(valid_spec(), 1920, 1080)
    real_target = tmp_path / "real.svg"
    real_target.write_text("do not overwrite", encoding="utf-8")
    linked_output = tmp_path / "linked.svg"
    linked_output.symlink_to(real_target)
    with pytest.raises(summary.SummaryError, match="symlinked output"):
        summary.render_svg(plain, linked_output)


@pytest.mark.parametrize(
    "mime,payload",
    [
        ("image/svg+xml", b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'),
        ("image/png", b"not-a-png"),
    ],
)
def test_drawio_validator_rejects_active_or_mime_spoofed_images(tmp_path: Path, mime: str, payload: bytes) -> None:
    diagram = _diagram_module()
    encoded = base64.b64encode(payload).decode("ascii")
    path = tmp_path / "unsafe.drawio"
    path.write_text(
        '<mxfile><diagram id="oci-visual-summary"><mxGraphModel><root><mxCell id="0"/><mxCell id="1" parent="0"/>'
        f'<mxCell id="img" value="" vertex="1" parent="1" style="shape=image;image=data:{mime};base64,{encoded}"/>'
        "</root></mxGraphModel></diagram></mxfile>",
        encoding="utf-8",
    )
    assert any("unsupported" in issue.lower() or "mismatched" in issue.lower() for issue in diagram.validate_drawio(path))

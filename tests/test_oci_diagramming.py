from __future__ import annotations

import importlib.util
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parent.parent
MODULE_PATH = ROOT / "skills" / "oci-diagramming" / "scripts" / "oci_diagram.py"
SPEC = importlib.util.spec_from_file_location("oci_diagram", MODULE_PATH)
assert SPEC and SPEC.loader
diagram = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagram)


def test_example_round_trip_all_formats(tmp_path: pathlib.Path) -> None:
    spec = diagram.load_spec(
        ROOT / "skills" / "oci-diagramming" / "assets" / "examples" / "oci-observability-pipeline.json"
    )
    outputs = {
        "drawio": (diagram.drawio(spec), diagram.validate_drawio),
        "excalidraw": (diagram.excalidraw(spec), diagram.validate_excalidraw),
        "mermaid": (diagram.mermaid(spec), diagram.validate_mermaid),
    }
    for suffix, (content, validator) in outputs.items():
        path = tmp_path / f"architecture.{suffix}"
        path.write_text(content, encoding="utf-8")
        assert validator(path) == []


def test_visual_summary_handoff_round_trip_all_formats(tmp_path: pathlib.Path) -> None:
    summary_spec = {
        "concept": "sketchnote-story-map-v1",
        "canvas": {"width": 1920, "height": 1080},
        "domain": "iam",
        "profile": {
            "name": "iam",
            "primary_accent": "#C74634",
            "secondary_accent": "#E6B9AE",
            "metaphors": ["gate", "scope", "verified path"],
            "doodles": ["key", "seal"],
        },
        "visual_style": {"preset": "oci-doodle", "doodle_level": "rich", "line_style": "hand-drawn"},
        "headline_zone": {
            "title": "Identity route",
            "takeaway": "Access is verified before use.",
            "bounds": {"x": 120, "y": 80, "width": 1650, "height": 240},
        },
        "dominant_path_phrase": "verified access route",
        "dominant_path": {
            "kind": "curved-path",
            "points": [
                {"x": 260, "y": 680},
                {"x": 720, "y": 600},
                {"x": 1240, "y": 710},
                {"x": 1660, "y": 630},
            ],
        },
        "clusters": [
            {
                "anchor_id": "anchor-1",
                "index": 1,
                "title": "Scope 1",
                "detail": "Bound access",
                "service_label": "IAM",
                "service_names": ["identity"],
                "evidence_class": "code-backed",
                "silhouette": "arch",
                "callout_shape": "ribbon",
                "bounds": {"x": 140, "y": 360, "width": 430, "height": 220},
                "art_slot": {"x": 360, "y": 385, "width": 160, "height": 110},
                "art_direction": {
                    "slot_mode": "supporting-art",
                    "generated_image_allowed": True,
                    "scene_prompt": "Original IAM supporting illustration; no words, letters, numbers, logos, UI, watermarks.",
                },
            },
            {
                "anchor_id": "anchor-2",
                "index": 2,
                "title": "Scope 2",
                "detail": "Bound access",
                "service_label": "IAM",
                "service_names": ["identity"],
                "evidence_class": "code-backed",
                "silhouette": "cloud",
                "callout_shape": "speech-tail",
                "bounds": {"x": 690, "y": 620, "width": 420, "height": 210},
                "art_slot": {"x": 900, "y": 645, "width": 150, "height": 100},
                "art_direction": {
                    "slot_mode": "supporting-art",
                    "generated_image_allowed": True,
                    "scene_prompt": "Original IAM supporting illustration; no words, letters, numbers, logos, UI, watermarks.",
                },
            },
            {
                "anchor_id": "anchor-3",
                "index": 3,
                "title": "Scope 3",
                "detail": "Bound access",
                "service_label": "IAM",
                "service_names": ["identity"],
                "evidence_class": "code-backed",
                "silhouette": "seal",
                "callout_shape": "torn-note",
                "bounds": {"x": 1090, "y": 340, "width": 430, "height": 220},
                "art_slot": {"x": 1305, "y": 365, "width": 160, "height": 110},
                "art_direction": {
                    "slot_mode": "supporting-art",
                    "generated_image_allowed": True,
                    "scene_prompt": "Original IAM supporting illustration; no words, letters, numbers, logos, UI, watermarks.",
                },
            },
            {
                "anchor_id": "anchor-4",
                "index": 4,
                "title": "Scope 4",
                "detail": "Bound access",
                "service_label": "IAM",
                "service_names": ["identity"],
                "evidence_class": "code-backed",
                "silhouette": "bridge",
                "callout_shape": "wave",
                "bounds": {"x": 1450, "y": 600, "width": 330, "height": 210},
                "art_slot": {"x": 1610, "y": 625, "width": 120, "height": 100},
                "art_direction": {
                    "slot_mode": "supporting-art",
                    "generated_image_allowed": True,
                    "scene_prompt": "Original IAM supporting illustration; no words, letters, numbers, logos, UI, watermarks.",
                },
            },
        ],
    }
    outputs = {
        "drawio": (diagram.summary_drawio(summary_spec), diagram.validate_drawio),
        "excalidraw": (diagram.summary_excalidraw(summary_spec), diagram.validate_excalidraw),
    }
    for suffix, (content, validator) in outputs.items():
        path = tmp_path / f"summary.{suffix}"
        path.write_text(content, encoding="utf-8")
        assert validator(path) == []


def test_drawio_rejects_entities_before_parse(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "bad.drawio"
    path.write_text('<!DOCTYPE x [<!ENTITY leak SYSTEM "file:///etc/passwd">]><mxfile/>', encoding="utf-8")
    assert "forbidden XML" in diagram.validate_drawio(path)[0]


def test_mermaid_rejects_active_actions(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "bad.mmd"
    path.write_text("flowchart LR\n A-->B\n click A href \"javascript:alert(1)\"\n", encoding="utf-8")
    assert diagram.validate_mermaid(path)


def test_excalidraw_rejects_embeds(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "bad.excalidraw"
    path.write_text(json.dumps({"type": "excalidraw", "version": 2, "elements": [{"id": "x", "type": "embeddable"}]}))
    assert diagram.validate_excalidraw(path) == ["external embeddable/iframe elements are forbidden"]


def test_spec_rejects_unknown_endpoint(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "spec.json"
    path.write_text(json.dumps({"nodes": [{"id": "source"}], "edges": [{"from": "source", "to": "missing"}]}))
    try:
        diagram.load_spec(path)
    except diagram.DiagramError as exc:
        assert "unknown endpoint" in str(exc)
    else:
        raise AssertionError("unknown endpoint accepted")


def test_output_requires_explicit_overwrite(tmp_path: pathlib.Path) -> None:
    path = tmp_path / "exists.drawio"
    path.write_text("existing")
    try:
        diagram.safe_output(path, force=False)
    except diagram.DiagramError as exc:
        assert "--force" in str(exc)
    else:
        raise AssertionError("existing output accepted without --force")

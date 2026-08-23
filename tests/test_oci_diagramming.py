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


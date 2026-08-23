from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys


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


def test_generate_defaults_missing_edges_and_returns_json_error_for_invalid_edge(
    tmp_path: pathlib.Path,
) -> None:
    minimal = tmp_path / "minimal.json"
    minimal.write_text(json.dumps({"nodes": [{"id": "source"}]}), encoding="utf-8")
    output = tmp_path / "minimal.mmd"
    result = subprocess.run(
        [sys.executable, str(MODULE_PATH), "generate", "--format", "mermaid", "--spec", str(minimal), "--output", str(output)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["status"] == "generated"

    invalid = tmp_path / "invalid.json"
    invalid.write_text(
        json.dumps({"nodes": [{"id": "source"}], "edges": [{"from": "source", "to": "source", "label": {"secret": "x"}}]}),
        encoding="utf-8",
    )
    rejected = subprocess.run(
        [sys.executable, str(MODULE_PATH), "generate", "--format", "drawio", "--spec", str(invalid), "--output", str(tmp_path / "bad.drawio")],
        text=True,
        capture_output=True,
        check=False,
    )
    assert rejected.returncode == 1
    assert json.loads(rejected.stderr)["status"] == "error"


def test_generated_ids_cannot_collide_with_user_node_ids(tmp_path: pathlib.Path) -> None:
    spec_path = tmp_path / "collision.json"
    spec_path.write_text(
        json.dumps(
            {
                "nodes": [{"id": "x"}, {"id": "label-x"}, {"id": "edge-1"}],
                "edges": [{"from": "x", "to": "label-x"}],
            }
        ),
        encoding="utf-8",
    )
    spec = diagram.load_spec(spec_path)
    drawio_path = tmp_path / "collision.drawio"
    drawio_path.write_text(diagram.drawio(spec), encoding="utf-8")
    excalidraw_path = tmp_path / "collision.excalidraw"
    excalidraw_path.write_text(diagram.excalidraw(spec), encoding="utf-8")
    assert diagram.validate_drawio(drawio_path) == []
    assert diagram.validate_excalidraw(excalidraw_path) == []


def test_drawio_rejects_unknown_service_and_duplicate_object_ids(
    tmp_path: pathlib.Path,
) -> None:
    path = tmp_path / "invalid.drawio"
    path.write_text(
        """<mxfile><diagram><mxGraphModel><root>
<mxCell id="0"/><mxCell id="1" parent="0"/>
<mxCell id="security" value="Security"/><mxCell id="observability" value="Observability"/>
<UserObject id="node" ociService="not-oci"><mxCell id="cell-a" style="shape=mxgraph.aws4.lambda;"/></UserObject>
<UserObject id="node"><mxCell id="cell-b"/></UserObject>
</root></mxGraphModel></diagram></mxfile>""",
        encoding="utf-8",
    )
    issues = diagram.validate_drawio(path)
    assert any("unknown OCI stencil" in issue for issue in issues)
    assert any("duplicate diagram IDs" in issue for issue in issues)

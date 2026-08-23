#!/usr/bin/env python3
"""Offline-first OCI diagram generator and security validator.

The input is a bounded JSON architecture specification. Outputs remain editable:
Draw.io XML, Excalidraw JSON, or Mermaid source. No network, shell, archive, or
plugin execution is performed.
"""
from __future__ import annotations

import argparse
import html
import json
import math
import pathlib
import re
import sys
import xml.parsers.expat
from collections import Counter
from typing import Any

MAX_BYTES = 5 * 1024 * 1024
MAX_NODES = 250
MAX_EDGES = 500
SAFE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,79}$")
FORBIDDEN_XML = re.compile(br"<!DOCTYPE|<!ENTITY|<\?xml-stylesheet", re.I)
FORBIDDEN_MERMAID = re.compile(r"%%\{\s*init|<script|javascript:|click\s+\S+\s+(?:href|call)", re.I)
MERMAID_UNSAFE_TEXT = re.compile(r"[|\[\]{}<>#`\\]|[\x00-\x1f]")
MERMAID_UNSAFE_ID = re.compile(r"[^A-Za-z0-9_.-]")
MERMAID_RESERVED_IDS = {
    "end", "graph", "subgraph", "flowchart", "class", "classdef", "click",
    "style", "linkstyle", "direction",
}
MERMAID_DECLARATION = re.compile(
    r"(?m)^\s*(flowchart|sequenceDiagram|classDiagram|erDiagram|stateDiagram-v2|architecture-beta)\b"
)
MERMAID_KEYWORD_LINE = re.compile(
    r"^(flowchart|graph|classDef|class|style|linkStyle|click|direction|subgraph)\b"
)
MERMAID_SEPARATORS = re.compile(
    r'"[^"]*"|-\.->|-\.-|={2,}>|-{2,}>|-{3,}|~{3,}|:::|[\[\](){}|&,;]'
)

OCI_STENCIL_STYLES = {
    "monitoring": "shape=mxgraph.oci.monitoring;",
    "logging": "shape=mxgraph.oci.logging;",
    "apm": "shape=mxgraph.oci.application_performance_monitoring;",
    "log-analytics": "shape=mxgraph.oci.logging_analytics;",
    "notifications": "shape=mxgraph.oci.notifications;",
    "events": "shape=mxgraph.oci.events;",
    "service-connector-hub": "shape=mxgraph.oci.service_connector_hub;",
    "streaming": "shape=mxgraph.oci.streaming;",
    "object-storage": "shape=mxgraph.oci.object_storage;",
    "oke": "shape=mxgraph.oci.container_engine_for_kubernetes;",
    "compute": "shape=mxgraph.oci.compute;",
    "load-balancer": "shape=mxgraph.oci.load_balancer;",
    "network-firewall": "shape=mxgraph.oci.network_firewall;",
    "bastion": "shape=mxgraph.oci.bastion;",
    "vault": "shape=mxgraph.oci.vault;",
    "cloud-guard": "shape=mxgraph.oci.cloud_guard;",
    "identity": "shape=mxgraph.oci.identity_and_access_management;",
    "generative-ai": "shape=mxgraph.oci.generative_ai;",
    "database": "shape=mxgraph.oci.database;",
    "redis": "shape=mxgraph.oci.cache_with_redis;",
}

PALETTE = {
    "default": ("#F7F7F7", "#312D2A"),
    "compute": ("#E9F2F8", "#1F4E79"),
    "network": ("#E8F4EA", "#2D6A4F"),
    "security": ("#FDEBEC", "#9B1C31"),
    "observability": ("#FFF3E0", "#C74634"),
    "data": ("#F1EAF7", "#6C3A78"),
    "ai": ("#EAF3F2", "#0E6251"),
}


class DiagramError(ValueError):
    pass


def read_bounded(path: pathlib.Path) -> bytes:
    if path.is_symlink():
        raise DiagramError(f"refusing symlink input: {path}")
    size = path.stat().st_size
    if size > MAX_BYTES:
        raise DiagramError(f"file exceeds {MAX_BYTES} byte limit: {path}")
    return path.read_bytes()


def safe_output(path: pathlib.Path, force: bool) -> pathlib.Path:
    resolved_parent = path.parent.resolve()
    if not resolved_parent.is_dir():
        raise DiagramError(f"output directory does not exist: {resolved_parent}")
    target = resolved_parent / path.name
    if target.exists() and not force:
        raise DiagramError(f"output exists; pass --force to replace: {target}")
    if target.is_symlink():
        raise DiagramError(f"refusing symlink output: {target}")
    return target


def load_spec(path: pathlib.Path) -> dict[str, Any]:
    try:
        spec = json.loads(read_bounded(path))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DiagramError(f"invalid JSON: {exc}") from exc
    if not isinstance(spec, dict):
        raise DiagramError("spec root must be an object")
    nodes, edges = spec.get("nodes", []), spec.get("edges", [])
    if not isinstance(nodes, list) or not isinstance(edges, list):
        raise DiagramError("nodes and edges must be arrays")
    if not (1 <= len(nodes) <= MAX_NODES) or len(edges) > MAX_EDGES:
        raise DiagramError(f"node/edge limits are {MAX_NODES}/{MAX_EDGES}")
    if "title" in spec and (
        not isinstance(spec["title"], str) or len(spec["title"]) > 160
    ):
        raise DiagramError("title must be a short string")
    ids: set[str] = set()
    for i, node in enumerate(nodes):
        if not isinstance(node, dict) or not SAFE_ID.fullmatch(str(node.get("id", ""))):
            raise DiagramError(f"nodes[{i}].id is invalid")
        nid = str(node["id"])
        if nid in ids:
            raise DiagramError(f"duplicate node id: {nid}")
        ids.add(nid)
        for key in ("label", "service", "group", "layer", "kind"):
            if key in node and (not isinstance(node[key], str) or len(node[key]) > 160):
                raise DiagramError(f"nodes[{i}].{key} must be a short string")
        service = node.get("service")
        if service and service not in OCI_STENCIL_STYLES:
            raise DiagramError(f"unknown OCI stencil service key: {service}")
    for i, edge in enumerate(edges):
        if not isinstance(edge, dict) or edge.get("from") not in ids or edge.get("to") not in ids:
            raise DiagramError(f"edges[{i}] has an unknown endpoint")
        for key in ("from", "to", "label", "type"):
            if key in edge and (
                not isinstance(edge[key], str) or len(edge[key]) > 160
            ):
                raise DiagramError(f"edges[{i}].{key} must be a short string")
        if edge.get("type", "data") not in {"data", "control", "telemetry", "replication", "response", "trust"}:
            raise DiagramError(f"edges[{i}].type is invalid")
    spec = dict(spec)
    spec["nodes"] = nodes
    spec["edges"] = edges
    return spec


def positions(nodes: list[dict[str, Any]]) -> dict[str, tuple[int, int]]:
    result: dict[str, tuple[int, int]] = {}
    cols = max(1, min(5, math.ceil(math.sqrt(len(nodes) * 1.4))))
    for i, node in enumerate(nodes):
        x = node.get("x", 100 + (i % cols) * 235 + (18 if i % 2 else 0))
        y = node.get("y", 120 + (i // cols) * 155 + (12 if (i // cols) % 2 else 0))
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise DiagramError(f"node {node['id']} coordinates must be numeric")
        result[node["id"]] = (int(x), int(y))
    return result


def xml_attr(value: Any) -> str:
    return html.escape(str(value), quote=True)


def drawio(spec: dict[str, Any]) -> str:
    nodes, edges = spec["nodes"], spec["edges"]
    pos = positions(nodes)
    layers = ["Boundaries", "Network", "Workloads", "Observability", "Security", "Annotations"]
    layer_ids = {name: f"__oci_layer_{i + 2}" for i, name in enumerate(layers)}
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    for name in layers:
        cells.append(f'<mxCell id="{layer_ids[name]}" value="{name}" parent="0"/>')
    for node in nodes:
        nid, label = node["id"], node.get("label", node["id"])
        service = node.get("service")
        layer = node.get("layer") or ("Observability" if node.get("kind") == "observability" else "Workloads")
        if layer not in layer_ids:
            raise DiagramError(f"node {nid} uses unknown layer: {layer}")
        fill, stroke = PALETTE.get(node.get("kind", "default"), PALETTE["default"])
        style = "rounded=1;whiteSpace=wrap;html=1;arcSize=10;fontFamily=Arial;fontSize=13;shadow=0;"
        style += f"fillColor={fill};strokeColor={stroke};strokeWidth=1.5;spacing=10;"
        if service:
            style += OCI_STENCIL_STYLES[service]
        x, y = pos[nid]
        meta = f' ociService="{xml_attr(service or "")}" evidence="{xml_attr(node.get("evidence", "design"))}"'
        cells.append(
            f'<UserObject id="{xml_attr(nid)}" label="{xml_attr(label)}"{meta}>'
            f'<mxCell vertex="1" parent="{layer_ids[layer]}" style="{xml_attr(style)}">'
            f'<mxGeometry x="{x}" y="{y}" width="190" height="76" as="geometry"/>'
            '</mxCell></UserObject>'
        )
    edge_styles = {
        "data": "endArrow=block;strokeColor=#312D2A;",
        "control": "endArrow=block;dashed=1;strokeColor=#6B6B6B;",
        "telemetry": "endArrow=block;dashed=1;dashPattern=2 4;strokeColor=#C74634;",
        "replication": "endArrow=block;strokeWidth=2;strokeColor=#2D6A4F;",
        "response": "endArrow=open;dashed=1;strokeColor=#1F4E79;",
        "trust": "endArrow=none;dashed=1;strokeColor=#9B1C31;",
    }
    for i, edge in enumerate(edges):
        etype = edge.get("type", "data")
        label = edge.get("label", "")
        style = "edgeStyle=orthogonalEdgeStyle;rounded=0;orthogonalLoop=1;jettySize=auto;html=1;" + edge_styles[etype]
        cells.append(
            f'<mxCell id="__oci_edge_{i + 1}" value="{xml_attr(label)}" edge="1" '
            f'parent="{layer_ids["Annotations"]}" source="{xml_attr(edge["from"])}" target="{xml_attr(edge["to"])}" '
            f'style="{xml_attr(style)}"><mxGeometry relative="1" as="geometry"/></mxCell>'
        )
    title = xml_attr(spec.get("title", "OCI architecture"))
    model = '<mxGraphModel grid="1" gridSize="10" page="1" pageScale="1" pageWidth="1600" pageHeight="900"><root>' + "".join(cells) + '</root></mxGraphModel>'
    return f'<mxfile host="app.diagrams.net" agent="oci-skills" version="1"><diagram id="oci-architecture" name="{title}">{model}</diagram></mxfile>\n'


def excalidraw(spec: dict[str, Any]) -> str:
    nodes, edges = spec["nodes"], spec["edges"]
    pos = positions(nodes)
    elements: list[dict[str, Any]] = []
    seed = 1000
    for node in nodes:
        x, y = pos[node["id"]]
        fill, stroke = PALETTE.get(node.get("kind", "default"), PALETTE["default"])
        elements.append({"id": node["id"], "type": "rectangle", "x": x, "y": y, "width": 190, "height": 76,
                         "angle": 0, "strokeColor": stroke, "backgroundColor": fill, "fillStyle": "solid",
                         "strokeWidth": 2, "strokeStyle": "solid", "roughness": 1, "opacity": 100, "seed": seed,
                         "version": 1, "versionNonce": seed + 1, "isDeleted": False, "boundElements": None,
                         "updated": 1, "link": None, "locked": False, "customData": {"ociService": node.get("service"), "layer": node.get("layer", "Workloads")}})
        seed += 2
        elements.append({"id": f"__oci_label_{node['id']}", "type": "text", "x": x + 12, "y": y + 23,
                         "width": 166, "height": 25, "angle": 0, "strokeColor": "#312D2A", "backgroundColor": "transparent",
                         "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 0, "opacity": 100,
                         "seed": seed, "version": 1, "versionNonce": seed + 1, "isDeleted": False, "boundElements": None,
                         "updated": 1, "link": None, "locked": False, "text": node.get("label", node["id"]),
                         "fontSize": 18, "fontFamily": 5, "textAlign": "center", "verticalAlign": "middle",
                         "containerId": None, "originalText": node.get("label", node["id"]), "lineHeight": 1.25})
        seed += 2
    for i, edge in enumerate(edges):
        sx, sy = pos[edge["from"]]
        tx, ty = pos[edge["to"]]
        style = "dashed" if edge.get("type") in {"control", "telemetry", "response", "trust"} else "solid"
        elements.append({"id": f"__oci_edge_{i+1}", "type": "arrow", "x": sx + 190, "y": sy + 38,
                         "width": tx - sx - 190, "height": ty - sy, "angle": 0, "strokeColor": "#C74634" if edge.get("type") == "telemetry" else "#312D2A",
                         "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 2, "strokeStyle": style,
                         "roughness": 1, "opacity": 100, "seed": seed, "version": 1, "versionNonce": seed + 1,
                         "isDeleted": False, "boundElements": None, "updated": 1, "link": None, "locked": False,
                         "points": [[0, 0], [tx - sx - 190, ty - sy]], "lastCommittedPoint": None,
                         "startBinding": None, "endBinding": None, "startArrowhead": None, "endArrowhead": "arrow",
                         "customData": {"flowType": edge.get("type", "data"), "label": edge.get("label", "")}})
        seed += 2
    scene = {"type": "excalidraw", "version": 2, "source": "oci-skills", "elements": elements,
             "appState": {"viewBackgroundColor": "#FFFFFF", "gridSize": 20}, "files": {}}
    return json.dumps(scene, indent=2, ensure_ascii=False) + "\n"


def mermaid_text(value: Any) -> str:
    text = MERMAID_UNSAFE_TEXT.sub(" ", str(value).replace('"', "'"))
    return re.sub(r"\s+", " ", text).strip()


def mermaid_aliases(nodes: list[dict[str, Any]]) -> dict[str, str]:
    return {node["id"]: f"n{i}" for i, node in enumerate(nodes, 1)}


def mermaid(spec: dict[str, Any]) -> str:
    spec_nodes = spec["nodes"]
    alias = mermaid_aliases(spec_nodes)
    lines = ["%% OCI diagram: node aliases and oci-service metadata are recorded in comments", "flowchart LR"]
    groups: dict[str, list[dict[str, Any]]] = {}
    for node in spec_nodes:
        groups.setdefault(node.get("group", "OCI workload"), []).append(node)
    for gi, (group, nodes) in enumerate(groups.items(), 1):
        lines.append(f'  subgraph G{gi}["{mermaid_text(group) or "OCI workload"}"]')
        for node in nodes:
            nid = node["id"]
            label = mermaid_text(node.get("label", nid)) or mermaid_text(nid) or alias[nid]
            service = node.get("service", "custom")
            lines.append(f"    %% oci-node: {alias[nid]} = {nid} (oci-service: {service})")
            lines.append(f'    {alias[nid]}["{label}"]')
        lines.append("  end")
    arrows = {"data": "-->", "control": "-.->", "telemetry": "-.->", "replication": "==>", "response": "-.->", "trust": "-.-"}
    for edge in spec["edges"]:
        label = mermaid_text(edge.get("label", ""))
        token = arrows[edge.get("type", "data")]
        source, target = alias[edge["from"]], alias[edge["to"]]
        lines.append(f'  {source} {token}|"{label}"| {target}' if label else f"  {source} {token} {target}")
    lines.extend(["  classDef oci fill:#FFF3E0,stroke:#C74634,color:#312D2A,stroke-width:2px;",
                  "  class " + ",".join(alias[n["id"]] for n in spec_nodes) + " oci;"])
    return "\n".join(lines) + "\n"


def validate_drawio(path: pathlib.Path) -> list[str]:
    raw = read_bounded(path)
    issues: list[str] = []
    if FORBIDDEN_XML.search(raw):
        return ["forbidden XML DTD/entity/stylesheet declaration"]
    root_tag: list[str] = []
    cells: list[dict[str, str]] = []
    objects: list[dict[str, str]] = []
    object_stack: list[dict[str, str]] = []
    object_cells: dict[str, dict[str, str]] = {}
    parser = xml.parsers.expat.ParserCreate()

    def start(name: str, attrs: dict[str, str]) -> None:
        if not root_tag:
            root_tag.append(name)
        if name == "UserObject":
            obj = dict(attrs)
            objects.append(obj)
            object_stack.append(obj)
        elif name == "mxCell":
            cell = dict(attrs)
            cells.append(cell)
            if object_stack and object_stack[-1].get("id"):
                object_cells[object_stack[-1]["id"]] = cell

    def end(name: str) -> None:
        if name == "UserObject" and object_stack:
            object_stack.pop()

    def reject_entity(*_args: Any) -> None:
        raise DiagramError("external/entity declarations are forbidden")

    parser.StartElementHandler = start
    parser.EndElementHandler = end
    parser.EntityDeclHandler = reject_entity
    parser.ExternalEntityRefHandler = lambda *_args: 0
    try:
        parser.Parse(raw, True)
    except (xml.parsers.expat.ExpatError, DiagramError) as exc:
        return [f"invalid or unsafe XML: {exc}"]
    if root_tag != ["mxfile"]:
        issues.append("root must be mxfile")
    cell_ids = [c.get("id") for c in cells if c.get("id")]
    object_ids = [u.get("id") for u in objects if u.get("id")]
    all_ids = cell_ids + object_ids
    duplicates = [v for v, count in Counter(all_ids).items() if count > 1]
    if duplicates:
        issues.append("duplicate diagram IDs: " + ", ".join(duplicates[:10]))
    known = set(all_ids)
    for cell in cells:
        if cell.get("edge") == "1" and (cell.get("source") not in known or cell.get("target") not in known):
            issues.append(f"dangling edge: {cell.get('id')}")
    for obj in objects:
        service = obj.get("ociService")
        cell = object_cells.get(obj.get("id", ""))
        if service:
            expected_style = OCI_STENCIL_STYLES.get(service)
            if expected_style is None:
                issues.append(f"unknown OCI stencil service key: {service}")
            elif cell is None or expected_style not in cell.get("style", ""):
                issues.append(f"OCI service {service} lacks its official stencil style: {obj.get('id')}")
    if not any(c.get("value") == "Security" for c in cells):
        issues.append("missing named Security layer")
    if not any(c.get("value") == "Observability" for c in cells):
        issues.append("missing named Observability layer")
    return issues


def validate_excalidraw(path: pathlib.Path) -> list[str]:
    try:
        scene = json.loads(read_bounded(path))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return [f"invalid JSON: {exc}"]
    issues: list[str] = []
    if scene.get("type") != "excalidraw" or scene.get("version") != 2:
        issues.append("scene must be Excalidraw version 2")
    elements = scene.get("elements")
    if not isinstance(elements, list) or len(elements) > 1000:
        return issues + ["elements must be an array of at most 1000 items"]
    ids = [e.get("id") for e in elements if isinstance(e, dict)]
    if len(ids) != len(set(ids)):
        issues.append("duplicate element IDs")
    if any(e.get("type") in {"embeddable", "iframe"} for e in elements if isinstance(e, dict)):
        issues.append("external embeddable/iframe elements are forbidden")
    return issues


def mermaid_statements(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip() and not line.strip().startswith("%%")]


def mermaid_identifiers(line: str) -> list[str]:
    if line.startswith("subgraph"):
        line = line[len("subgraph"):]
    elif MERMAID_KEYWORD_LINE.match(line):
        return []
    return [token for token in MERMAID_SEPARATORS.sub(" ", line).split() if token]


def validate_mermaid_flowchart(statements: list[str]) -> list[str]:
    issues: list[str] = []
    depth = 0
    for line in statements:
        if line == "end":
            depth -= 1
            if depth < 0:
                issues.append("subgraph block closed without a matching subgraph")
                depth = 0
            continue
        if line.startswith("subgraph"):
            depth += 1
        segments = line.split("|")
        if len(segments) % 2 == 0:
            issues.append(f"unbalanced edge label delimiter: {line}")
        else:
            for segment in segments[1::2]:
                if segment.count('"') % 2:
                    issues.append(f"unbalanced edge label quoting: {line}")
        for identifier in mermaid_identifiers(line):
            if identifier.lower() in MERMAID_RESERVED_IDS:
                issues.append(f"reserved Mermaid keyword used as an identifier: {identifier}")
            if MERMAID_UNSAFE_ID.search(identifier):
                issues.append(f"identifier is not renderer-safe: {identifier}")
    if depth > 0:
        issues.append("subgraph block is never closed")
    return issues


def validate_mermaid(path: pathlib.Path) -> list[str]:
    try:
        text = read_bounded(path).decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"invalid UTF-8: {exc}"]
    issues: list[str] = []
    if FORBIDDEN_MERMAID.search(text):
        issues.append("unsafe Mermaid directive, script, or click action")
    declaration = MERMAID_DECLARATION.search(text)
    if declaration is None:
        issues.append("no supported Mermaid diagram declaration found")
    elif declaration.group(1) == "flowchart":
        issues.extend(validate_mermaid_flowchart(mermaid_statements(text)))
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate")
    gen.add_argument("--format", choices=("drawio", "excalidraw", "mermaid"), required=True)
    gen.add_argument("--spec", type=pathlib.Path, required=True)
    gen.add_argument("--output", type=pathlib.Path, required=True)
    gen.add_argument("--force", action="store_true")
    val = sub.add_parser("validate")
    val.add_argument("--format", choices=("drawio", "excalidraw", "mermaid"), required=True)
    val.add_argument("--input", type=pathlib.Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "generate":
            spec = load_spec(args.spec)
            output = safe_output(args.output, args.force)
            content = {"drawio": drawio, "excalidraw": excalidraw, "mermaid": mermaid}[args.format](spec)
            output.write_text(content, encoding="utf-8")
            print(json.dumps({"status": "generated", "format": args.format, "output": str(output), "network": False}))
            return 0
        checks = {"drawio": validate_drawio, "excalidraw": validate_excalidraw, "mermaid": validate_mermaid}
        issues = checks[args.format](args.input)
        print(json.dumps({"status": "pass" if not issues else "fail", "issues": issues}, indent=2))
        return 0 if not issues else 2
    except (OSError, DiagramError) as exc:
        print(json.dumps({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

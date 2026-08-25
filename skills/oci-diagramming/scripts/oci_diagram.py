#!/usr/bin/env python3
"""Offline-first OCI diagram generator and security validator.

The input is a bounded JSON architecture specification. Outputs remain editable:
Draw.io XML, Excalidraw JSON, or Mermaid source. No network, shell, archive, or
plugin execution is performed.
"""
from __future__ import annotations

import argparse
import base64
import binascii
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
MAX_EMBEDDED_IMAGE_BYTES = 1024 * 1024
SAFE_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,79}$")
FORBIDDEN_XML = re.compile(br"<!DOCTYPE|<!ENTITY|<\?xml-stylesheet", re.I)
FORBIDDEN_MERMAID = re.compile(r"%%\{\s*init|<script|javascript:|click\s+\S+\s+(?:href|call)", re.I)

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
        if edge.get("type", "data") not in {"data", "control", "telemetry", "replication", "response", "trust"}:
            raise DiagramError(f"edges[{i}].type is invalid")
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
    layer_ids = {name: f"layer-{i + 2}" for i, name in enumerate(layers)}
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
            f'<mxCell id="edge-{i + 1}" value="{xml_attr(label)}" edge="1" '
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
        elements.append({"id": f"label-{node['id']}", "type": "text", "x": x + 12, "y": y + 23,
                         "width": 166, "height": 25, "angle": 0, "strokeColor": "#312D2A", "backgroundColor": "transparent",
                         "fillStyle": "solid", "strokeWidth": 1, "strokeStyle": "solid", "roughness": 0, "opacity": 100,
                         "seed": seed, "version": 1, "versionNonce": seed + 1, "isDeleted": False, "boundElements": None,
                         "updated": 1, "link": None, "locked": False, "text": node.get("label", node["id"]),
                         "fontSize": 18, "fontFamily": 5, "textAlign": "center", "verticalAlign": "middle",
                         "containerId": None, "originalText": node.get("label", node["id"]), "lineHeight": 1.25})
        seed += 2
    for i, edge in enumerate(edges):
        sx, sy = pos[edge["from"]]; tx, ty = pos[edge["to"]]
        style = "dashed" if edge.get("type") in {"control", "telemetry", "response", "trust"} else "solid"
        elements.append({"id": f"edge-{i+1}", "type": "arrow", "x": sx + 190, "y": sy + 38,
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


def mermaid(spec: dict[str, Any]) -> str:
    lines = ["%% OCI diagram: service nodes retain oci-service metadata in comments", "flowchart LR"]
    groups: dict[str, list[dict[str, Any]]] = {}
    for node in spec["nodes"]:
        groups.setdefault(node.get("group", "OCI workload"), []).append(node)
    for gi, (group, nodes) in enumerate(groups.items(), 1):
        lines.append(f'  subgraph G{gi}["{group.replace(chr(34), chr(39))}"]')
        for node in nodes:
            label = node.get("label", node["id"]).replace('"', "'")
            service = node.get("service", "custom")
            lines.append(f"    %% oci-service: {service}")
            lines.append(f'    {node["id"]}["{label}"]')
        lines.append("  end")
    arrows = {"data": "-->", "control": "-.->", "telemetry": "-.->", "replication": "==>", "response": "-.->", "trust": "-.-"}
    for edge in spec["edges"]:
        label = edge.get("label", "").replace('"', "'")
        token = arrows[edge.get("type", "data")]
        lines.append(f'  {edge["from"]} {token}|"{label}"| {edge["to"]}' if label else f'  {edge["from"]} {token} {edge["to"]}')
    lines.extend(["  classDef oci fill:#FFF3E0,stroke:#C74634,color:#312D2A,stroke-width:2px;",
                  "  class " + ",".join(n["id"] for n in spec["nodes"]) + " oci;"])
    return "\n".join(lines) + "\n"


def _summary_handoff(handoff: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(handoff, dict) or handoff.get("concept") != "sketchnote-story-map-v1":
        raise DiagramError("summary handoff must declare concept sketchnote-story-map-v1")
    canvas = handoff.get("canvas")
    if not isinstance(canvas, dict) or not isinstance(canvas.get("width"), int) or not isinstance(canvas.get("height"), int):
        raise DiagramError("summary handoff must include integer canvas dimensions")
    clusters = handoff.get("clusters")
    if not isinstance(clusters, list) or not clusters:
        raise DiagramError("summary handoff must include clusters")
    return handoff


def summary_drawio(handoff: dict[str, Any]) -> str:
    handoff = _summary_handoff(handoff)
    width = handoff["canvas"]["width"]
    height = handoff["canvas"]["height"]
    accent = handoff.get("profile", {}).get("primary_accent", "#C74634")
    secondary = handoff.get("profile", {}).get("secondary_accent", "#E6B9AE")
    style = handoff.get("visual_style", {})
    layers = ("Background", "Journey", "Scenes", "Artwork", "Text", "Evidence", "Observability", "Security")
    layer_ids = {name: f"layer-{index + 2}" for index, name in enumerate(layers)}
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    cells.extend(f'<mxCell id="{layer_ids[name]}" value="{name}" parent="0"/>' for name in layers)
    cells.append(
        f'<mxCell id="paper" value="" vertex="1" parent="{layer_ids["Background"]}" '
        f'style="shape=rectangle;fillColor=#FFFDF8;strokeColor=none;locked=1;"><mxGeometry x="0" y="0" width="{width}" height="{height}" as="geometry"/></mxCell>'
    )
    headline = handoff["headline_zone"]
    bounds = headline["bounds"]
    cells.append(
        f'<mxCell id="title" value="{xml_attr(headline["title"])}" vertex="1" parent="{layer_ids["Text"]}" '
        'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Trebuchet MS;fontSize=38;fontStyle=1;align=left;verticalAlign=top;">'
        f'<mxGeometry x="{bounds["x"]}" y="{bounds["y"]}" width="{bounds["width"]}" height="80" as="geometry"/></mxCell>'
    )
    cells.append(
        f'<mxCell id="takeaway" value="{xml_attr(headline["takeaway"])}" vertex="1" parent="{layer_ids["Text"]}" '
        'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Trebuchet MS;fontSize=18;align=left;verticalAlign=top;">'
        f'<mxGeometry x="{bounds["x"]}" y="{bounds["y"] + 90}" width="{bounds["width"]}" height="60" as="geometry"/></mxCell>'
    )
    points = handoff.get("dominant_path", {}).get("points", [])
    for index, point in enumerate(points, start=1):
        cells.append(
            f'<mxCell id="path-node-{index}" value="" vertex="1" parent="{layer_ids["Journey"]}" '
            f'style="ellipse;whiteSpace=wrap;html=1;fillColor=#FFFDF8;strokeColor={accent};strokeWidth=3;sketch=1;">'
            f'<mxGeometry x="{point["x"] - 10}" y="{point["y"] - 10}" width="20" height="20" as="geometry"/></mxCell>'
        )
    for index in range(1, len(points)):
        cells.append(
            f'<mxCell id="journey-{index}" value="" edge="1" parent="{layer_ids["Journey"]}" source="path-node-{index}" target="path-node-{index + 1}" summaryKind="oci.visual-summary.path" '
            f'style="edgeStyle=orthogonalEdgeStyle;rounded=1;endArrow={"block" if index == len(points) - 1 else "none"};strokeColor={accent};strokeWidth=5;sketch=1;">'
            '<mxGeometry relative="1" as="geometry"/></mxCell>'
        )
    for index, cluster in enumerate(handoff["clusters"], start=1):
        anchor = xml_attr(cluster["anchor_id"])
        box = cluster["bounds"]
        services = cluster.get("service_names") or []
        service = services[0] if services and services[0] in OCI_STENCIL_STYLES else None
        cells.append(
            f'<UserObject id="scene-{anchor}" label="" summaryKind="oci.visual-summary.scene" '
            f'visualPreset="{xml_attr(style.get("preset", "oci-doodle"))}" doodleLevel="{xml_attr(style.get("doodle_level", "balanced"))}">'
            f'<mxCell vertex="1" parent="{layer_ids["Scenes"]}" '
            f'style="shape=cloud;whiteSpace=wrap;html=1;fillColor=#FFFDF8;strokeColor={secondary};strokeWidth=2;sketch=1;">'
            f'<mxGeometry x="{box["x"]}" y="{box["y"]}" width="{box["width"]}" height="{box["height"]}" as="geometry"/></mxCell></UserObject>'
        )
        if service:
            cells.append(
                f'<UserObject id="service-{anchor}" label="{xml_attr(cluster.get("service_label", service.title()))}" ociService="{xml_attr(service)}">'
                f'<mxCell vertex="1" parent="{layer_ids["Scenes"]}" style="{xml_attr(OCI_STENCIL_STYLES[service] + "sketch=1;fillColor=#FFFFFF;strokeColor=" + accent + ";")}">'
                f'<mxGeometry x="{box["x"] + 16}" y="{box["y"] + 18}" width="56" height="56" as="geometry"/></mxCell></UserObject>'
            )
        text_value = (
            f'&lt;b&gt;{xml_attr(cluster["title"])}&lt;/b&gt;&lt;br&gt;'
            f'{xml_attr(cluster["detail"])}&lt;br&gt;'
            f'&lt;font color=&quot;{accent}&quot;&gt;{xml_attr(str(cluster["evidence_class"]).upper())}&lt;/font&gt;'
        )
        cells.append(
            f'<mxCell id="text-{anchor}" value="{text_value}" vertex="1" parent="{layer_ids["Text"]}" '
            'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Trebuchet MS;fontSize=15;align=left;verticalAlign=top;spacing=12;">'
            f'<mxGeometry x="{box["x"] + 86}" y="{box["y"] + 22}" width="{box["width"] - 104}" height="{box["height"] - 36}" as="geometry"/></mxCell>'
        )
        slot = cluster.get("art_slot", {})
        if all(isinstance(slot.get(key), int) for key in ("x", "y", "width", "height")):
            artwork = cluster.get("artwork") if isinstance(cluster.get("artwork"), dict) else {}
            data_url = artwork.get("data_url")
            if isinstance(data_url, str) and data_url.startswith("data:image/"):
                art_style = f"shape=image;imageAspect=1;aspect=fixed;image={data_url};strokeColor=none;fillColor=none;"
            else:
                art_style = f"shape=rectangle;rounded=1;dashed=1;dashPattern=8 6;fillColor=none;strokeColor={accent};sketch=1;"
            cells.append(
                f'<UserObject id="art-slot-{anchor}" label="{xml_attr(artwork.get("alt_text") or cluster.get("art_direction", {}).get("alt_text", "Supporting illustration"))}" summaryKind="oci.visual-summary.art-slot">'
                f'<mxCell vertex="1" parent="{layer_ids["Artwork"]}" style="{xml_attr(art_style)}">'
                f'<mxGeometry x="{slot["x"]}" y="{slot["y"]}" width="{slot["width"]}" height="{slot["height"]}" as="geometry"/></mxCell></UserObject>'
            )
    footer = xml_attr("Evidence: " + str(handoff.get("evidence_footer", "")))
    cells.append(
        f'<mxCell id="evidence" value="{footer}" vertex="1" parent="{layer_ids["Evidence"]}" '
        'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Trebuchet MS;fontSize=11;align=left;">'
        f'<mxGeometry x="{width * .07:.1f}" y="{height * .93:.1f}" width="{width * .86:.1f}" height="32" as="geometry"/></mxCell>'
    )
    model = f'<mxGraphModel grid="1" gridSize="10" page="1" pageScale="1" pageWidth="{width}" pageHeight="{height}"><root>{"".join(cells)}</root></mxGraphModel>'
    return f'<mxfile host="app.diagrams.net" agent="oci-skills" version="1"><diagram id="oci-visual-summary" name="At a glance">{model}</diagram></mxfile>\n'


def summary_excalidraw(handoff: dict[str, Any]) -> str:
    handoff = _summary_handoff(handoff)
    width = handoff["canvas"]["width"]
    height = handoff["canvas"]["height"]
    accent = handoff.get("profile", {}).get("primary_accent", "#C74634")
    secondary = handoff.get("profile", {}).get("secondary_accent", "#E6B9AE")
    style = handoff.get("visual_style", {})
    elements: list[dict[str, Any]] = []
    files: dict[str, Any] = {}

    def common(element_id: str, kind: str, x: float, y: float, w: float, h: float, seed: int) -> dict[str, Any]:
        return {"id": element_id, "type": kind, "x": x, "y": y, "width": w, "height": h, "angle": 0,
                "strokeColor": accent, "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 2,
                "strokeStyle": "solid", "roughness": 2, "opacity": 100, "seed": seed, "version": 1,
                "versionNonce": seed + 1, "isDeleted": False, "boundElements": None, "updated": 1,
                "link": None, "locked": False}

    headline = handoff["headline_zone"]
    bounds = headline["bounds"]
    title = common("title", "text", bounds["x"], bounds["y"], bounds["width"], 80, 1000)
    title.update({"text": headline["title"], "fontSize": 42, "fontFamily": 5, "textAlign": "left", "verticalAlign": "top",
                  "containerId": None, "originalText": headline["title"], "lineHeight": 1.15, "strokeColor": "#18202B", "roughness": 0})
    elements.append(title)
    takeaway = common("takeaway", "text", bounds["x"], bounds["y"] + 92, bounds["width"], 52, 1002)
    takeaway.update({"text": headline["takeaway"], "fontSize": 20, "fontFamily": 5, "textAlign": "left", "verticalAlign": "top",
                     "containerId": None, "originalText": headline["takeaway"], "lineHeight": 1.25, "strokeColor": "#3C4655", "roughness": 0})
    elements.append(takeaway)
    points = handoff.get("dominant_path", {}).get("points", [])
    for index, (start, end) in enumerate(zip(points, points[1:]), start=1):
        arrow = common(f"journey-{index}", "arrow", start["x"], start["y"], end["x"] - start["x"], end["y"] - start["y"], 1100 + index)
        arrow.update({"points": [[0, 0], [end["x"] - start["x"], end["y"] - start["y"]]], "lastCommittedPoint": None,
                      "startBinding": None, "endBinding": None, "startArrowhead": None,
                      "endArrowhead": "arrow" if index == len(points) - 1 else None,
                      "strokeWidth": 5, "customData": {"summaryKind": "oci.visual-summary.path"}})
        elements.append(arrow)
    for index, cluster in enumerate(handoff["clusters"], start=1):
        box = cluster["bounds"]
        shell = common(f"scene-{index}", "ellipse", box["x"], box["y"], box["width"], box["height"], 2000 + index * 10)
        shell.update({"backgroundColor": "#FFFDF8", "strokeColor": secondary, "customData": {"summaryKind": "oci.visual-summary.scene"}})
        elements.append(shell)
        text = common(f"text-{index}", "text", box["x"] + 20, box["y"] + 24, box["width"] - 40, box["height"] - 40, 2001 + index * 10)
        label = f'{cluster["index"]}. {cluster["title"]}\n{cluster["detail"]}\n{str(cluster["evidence_class"]).upper()}'
        text.update({"text": label, "fontSize": 18, "fontFamily": 5, "textAlign": "left", "verticalAlign": "top",
                     "containerId": None, "originalText": label, "lineHeight": 1.25, "strokeColor": "#18202B", "roughness": 0})
        elements.append(text)
        slot = cluster.get("art_slot", {})
        if all(isinstance(slot.get(key), int) for key in ("x", "y", "width", "height")):
            artwork = cluster.get("artwork") if isinstance(cluster.get("artwork"), dict) else {}
            data_url = artwork.get("data_url")
            if isinstance(data_url, str) and data_url.startswith("data:image/"):
                file_id = f"art-{index}"
                files[file_id] = {"id": file_id, "mimeType": data_url[5:data_url.index(";")], "dataURL": data_url,
                                  "created": 1, "lastRetrieved": 1, "sha256": artwork.get("sha256", "")}
                art = common(f"art-slot-{index}", "image", slot["x"], slot["y"], slot["width"], slot["height"], 2002 + index * 10)
                art.update({"fileId": file_id, "status": "saved", "scale": [1, 1], "crop": None, "roughness": 0,
                            "customData": {"summaryKind": "oci.visual-summary.art-slot", "altText": artwork.get("alt_text", "Supporting illustration")}})
            else:
                art = common(f"art-slot-{index}", "rectangle", slot["x"], slot["y"], slot["width"], slot["height"], 2002 + index * 10)
                art.update({"strokeStyle": "dashed", "backgroundColor": "transparent", "customData": {"summaryKind": "oci.visual-summary.art-slot"}})
            elements.append(art)
    scene = {
        "type": "excalidraw",
        "version": 2,
        "source": "oci-skills",
        "elements": elements,
        "appState": {
            "viewBackgroundColor": "#FFFDF8",
            "gridSize": None,
            "scrollX": 0,
            "scrollY": 0,
            "width": width,
            "height": height,
            "visualStyle": {
                "preset": style.get("preset", "oci-doodle"),
                "doodleLevel": style.get("doodle_level", "balanced"),
                "lineStyle": style.get("line_style", "hand-drawn"),
            },
        },
        "files": files,
    }
    return json.dumps(scene, indent=2, ensure_ascii=False) + "\n"


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
    diagram_ids: list[str] = []
    parser = xml.parsers.expat.ParserCreate()

    def start(name: str, attrs: dict[str, str]) -> None:
        if not root_tag:
            root_tag.append(name)
        if name == "diagram":
            diagram_ids.append(attrs.get("id", ""))
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
    ids = [c.get("id") for c in cells if c.get("id")]
    duplicates = [v for v, count in Counter(ids).items() if count > 1]
    if duplicates:
        issues.append("duplicate mxCell IDs: " + ", ".join(duplicates[:10]))
    known = set(ids) | {u.get("id") for u in objects if u.get("id")}
    for cell in cells:
        if cell.get("edge") == "1" and (cell.get("source") not in known or cell.get("target") not in known):
            issues.append(f"dangling edge: {cell.get('id')}")
    for obj in objects:
        service = obj.get("ociService")
        cell = object_cells.get(obj.get("id", ""))
        if service and cell is not None and OCI_STENCIL_STYLES.get(service, "") not in cell.get("style", ""):
            issues.append(f"OCI service {service} lacks its official stencil style: {obj.get('id')}")
    for cell in cells:
        style = cell.get("style", "")
        match = re.search(r"(?:^|;)image=(data:image/[^;]+;base64,[^;]+|[^;]+)", style)
        if not match:
            continue
        value = match.group(1)
        if re.match(r"(?:https?|file|ftp):", value, re.I) or value.startswith("//"):
            issues.append(f"remote or external image is forbidden: {cell.get('id')}")
            continue
        if not value.startswith("data:image/"):
            issues.append(f"image must be an embedded data URI: {cell.get('id')}")
            continue
        try:
            header, encoded = value.split(",", 1)
            mime = header.removeprefix("data:").split(";", 1)[0].lower()
            decoded = base64.b64decode(encoded, validate=True)
            allowed_magic = (
                mime == "image/png" and decoded.startswith(b"\x89PNG\r\n\x1a\n")
            ) or (
                mime == "image/jpeg" and decoded.startswith(b"\xff\xd8")
            ) or (
                mime == "image/webp" and decoded.startswith(b"RIFF") and decoded[8:12] == b"WEBP"
            )
            if ";base64" not in header or mime not in {"image/png", "image/jpeg", "image/webp"} or not allowed_magic:
                issues.append(f"embedded image type is unsupported or mismatched: {cell.get('id')}")
            elif len(decoded) > MAX_EMBEDDED_IMAGE_BYTES:
                issues.append(f"embedded image exceeds size limit: {cell.get('id')}")
        except (ValueError, binascii.Error):
            issues.append(f"embedded image data is invalid: {cell.get('id')}")
    if "oci-visual-summary" not in diagram_ids:
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
    files = scene.get("files", {})
    if not isinstance(files, dict) or len(files) > 8:
        issues.append("files must be an object of at most eight embedded images")
        return issues
    for file_id, file_value in files.items():
        if not isinstance(file_value, dict):
            issues.append(f"embedded image {file_id} must be an object")
            continue
        data_url = file_value.get("dataURL")
        if not isinstance(data_url, str) or not data_url.startswith("data:image/"):
            issues.append(f"embedded image {file_id} must use a local data URI")
            continue
        try:
            header, encoded = data_url.split(",", 1)
            decoded = base64.b64decode(encoded, validate=True)
            if ";base64" not in header:
                issues.append(f"embedded image {file_id} must be base64 encoded")
            elif len(decoded) > MAX_EMBEDDED_IMAGE_BYTES:
                issues.append(f"embedded image {file_id} exceeds size limit")
            elif not decoded.startswith((b"\x89PNG\r\n\x1a\n", b"\xff\xd8", b"RIFF")):
                issues.append(f"embedded image {file_id} data is not a supported raster image")
        except (ValueError, binascii.Error):
            issues.append(f"embedded image {file_id} data is invalid")
    return issues


def validate_mermaid(path: pathlib.Path) -> list[str]:
    try:
        text = read_bounded(path).decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"invalid UTF-8: {exc}"]
    issues: list[str] = []
    if FORBIDDEN_MERMAID.search(text):
        issues.append("unsafe Mermaid directive, script, or click action")
    if not re.search(r"(?m)^\s*(flowchart|sequenceDiagram|classDiagram|erDiagram|stateDiagram-v2|architecture-beta)\b", text):
        issues.append("no supported Mermaid diagram declaration found")
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

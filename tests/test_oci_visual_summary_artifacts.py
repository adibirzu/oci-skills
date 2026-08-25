"""Standalone artifact contracts for the OCI visual-summary renderer."""

import sys
from pathlib import Path
import importlib.util
import base64
import hashlib
import json
import re
import struct
import subprocess
import types
import tempfile
import zlib
from copy import deepcopy
from xml.etree import ElementTree as ET

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "oci-visual-summary"
DIAGRAM = ROOT / "skills" / "oci-diagramming"
sys.path.insert(0, str(SKILL / "scripts"))
sys.path.insert(0, str(DIAGRAM / "scripts"))

import visual_summary as summary
import oci_diagram
import storyboard


def _solid_png(rgb: tuple[int, int, int], width: int = 2, height: int = 2) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _png_rgb_at(payload: bytes, x: int, y: int) -> tuple[int, int, int]:
    width, height = struct.unpack(">II", payload[16:24])
    offset = 8
    compressed = bytearray()
    while offset + 12 <= len(payload):
        size = struct.unpack(">I", payload[offset:offset + 4])[0]
        kind = payload[offset + 4:offset + 8]
        if kind == b"IDAT":
            compressed.extend(payload[offset + 8:offset + 8 + size])
        offset += 12 + size
        if kind == b"IEND":
            break
    raw = zlib.decompress(bytes(compressed))
    stride = 1 + width * 3
    assert raw[y * stride] == 0
    start = y * stride + 1 + x * 3
    assert 0 <= x < width and 0 <= y < height
    return tuple(raw[start:start + 3])  # type: ignore[return-value]


class _FakePdfCanvas:
    def __init__(self, path: str, pagesize: tuple[float, float]) -> None:
        self.path = Path(path)
        self.pagesize = pagesize
        self.images: list[bytes] = []
        self.text: list[str] = []
        self.pages = 0

    def setFont(self, *_args) -> None:
        pass

    def drawString(self, _x: float, _y: float, value: str) -> None:
        self.text.append(value)

    def drawImage(self, payload: bytes, *_args, **_kwargs) -> None:
        self.images.append(payload)

    def showPage(self) -> None:
        self.pages += 1

    def save(self) -> None:
        body = [b"%PDF-1.4\n"]
        body.extend(b"/Type /XObject /Subtype /Image\n" for _ in self.images)
        body.extend(("BT (" + value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)") + ") Tj ET\n").encode("utf-8") for value in self.text)
        body.append(f"% pages={self.pages}; size={self.pagesize[0]}x{self.pagesize[1]}\n".encode("ascii"))
        self.path.write_bytes(b"".join(body))


def _install_fake_reportlab(monkeypatch: pytest.MonkeyPatch) -> None:
    canvas_module = types.ModuleType("reportlab.pdfgen.canvas")
    canvas_module.Canvas = _FakePdfCanvas  # type: ignore[attr-defined]
    pdfgen_module = types.ModuleType("reportlab.pdfgen")
    pdfgen_module.canvas = canvas_module  # type: ignore[attr-defined]
    reportlab_module = types.ModuleType("reportlab")
    reportlab_module.pdfgen = pdfgen_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "reportlab", reportlab_module)
    monkeypatch.setitem(sys.modules, "reportlab.pdfgen", pdfgen_module)
    monkeypatch.setitem(sys.modules, "reportlab.pdfgen.canvas", canvas_module)
    monkeypatch.setattr(summary, "_reportlab_available", lambda: True)


def _storyboard_asset_fixture(
    tmp_path: Path, count: int = 6, *, icon_count: int | None = None,
) -> tuple[dict, dict, list[tuple[int, int, int]], list[tuple[int, int, int]]]:
    icon_count = count if icon_count is None else icon_count
    scenes = []
    scene_paths: dict[str, str] = {}
    scene_receipts: dict[str, dict] = {}
    services = []
    private_icons: dict[str, object] = {"classification": "internal"}
    scene_colors = [(20 + index, 60 + index, 100 + index) for index in range(count)]
    icon_colors = [(120 + index, 30 + index, 70 + index) for index in range(icon_count)]
    for index, color in enumerate(scene_colors):
        unit_id = f"unit-{index + 1}"
        payload = _solid_png(color)
        scene_path = tmp_path / f"scene-{index + 1}.png"
        scene_path.write_bytes(payload)
        scenes.append({"unit_id": unit_id, "title": f"Capability {index + 1}", "detail": f"Mapping detail {index + 1}", "evidence_class": "code-backed"})
        scene_paths[unit_id] = str(scene_path)
        scene_receipts[unit_id] = {"sha256": hashlib.sha256(payload).hexdigest()}
    for index, color in enumerate(icon_colors):
        icon_payload = f'<svg viewBox="0 0 2 2"><path fill="rgb{color}" d="M0 0h2v2z"/></svg>'.encode()
        asset_id = f"icon-{index + 1}"
        services.append({
            "canonical_service_id": f"oci.service-{index + 1}",
            "display_name": f"OCI Service {index + 1}",
            "mapping_type": "exact-service",
            "alt_text": f"OCI Service {index + 1} icon",
            "private_catalog_asset_id": asset_id,
        })
        private_icons[asset_id] = {"bytes": icon_payload, "sha256": hashlib.sha256(icon_payload).hexdigest()}
    public = {
        "schema_version": 1,
        "canvas": {"width": 800, "height": 600},
        "title": "Operate",
        "takeaway": "Every approved capability remains visible.",
        "evidence_footer": "Oracle Source Alpha; Oracle Source Beta",
        "pages": [{"role": "at-a-glance", "title": "At a glance", "takeaway": "Every approved capability remains visible.", "scenes": scenes, "services": services}],
    }
    return summary._StoryboardHandoff(public, scene_paths, scene_receipts), private_icons, scene_colors, icon_colors


def _five_section_storyboard(handoff: dict) -> dict:
    handoff["concept"] = "illo-storyboard-sequence-v1"
    final = handoff["pages"][0]
    scenes = final["scenes"]
    services = final["services"]
    handoff["pages"] = [
        {"role": "project-promise", "title": "Promise", "scenes": scenes[:1]},
        {"role": "workflow", "title": "Workflow", "scenes": scenes},
        {"role": "capability-scenes", "title": "Capabilities", "scenes": scenes},
        {"role": "oci-service-map", "title": "Service map", "services": services},
        {"role": "at-a-glance", "title": "At a glance", "takeaway": "Every approved capability remains visible.", "scenes": scenes, "services": services},
    ]
    return handoff


def _png_storyboard_metadata(payload: bytes) -> dict:
    offset = 8
    while offset + 12 <= len(payload):
        size = struct.unpack(">I", payload[offset:offset + 4])[0]
        kind = payload[offset + 4:offset + 8]
        data = payload[offset + 8:offset + 8 + size]
        if kind == b"tEXt" and data.startswith(b"VisualSummary\x00"):
            return json.loads(data.split(b"\x00", 1)[1].decode("utf-8"))
        offset += 12 + size
    raise AssertionError("storyboard PNG metadata is missing")


class _FakePillowImage:
    def __init__(self, width: int, height: int, color: tuple[int, int, int]) -> None:
        self.width, self.height = width, height
        self.pixels = [color] * (width * height)

    def thumbnail(self, bounds: tuple[int, int]) -> None:
        self.width, self.height = min(self.width, bounds[0]), min(self.height, bounds[1])

    def alpha_composite(self, image: "_FakePillowImage", position: tuple[int, int]) -> None:
        x, y = position
        color = image.pixels[0]
        for py in range(max(0, y), min(self.height, y + image.height)):
            for px in range(max(0, x), min(self.width, x + image.width)):
                self.pixels[py * self.width + px] = color

    def convert(self, _mode: str) -> "_FakePillowImage":
        return self

    def save(self, path: Path, **_kwargs) -> None:
        width, height = self.width, self.height

        def chunk(kind: bytes, payload: bytes) -> bytes:
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

        raw = b"".join(b"\x00" + b"".join(bytes(self.pixels[row * width + column]) for column in range(width)) for row in range(height))
        path.write_bytes(
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw))
            + chunk(b"IEND", b"")
        )


class _FakePillowDraw:
    def __init__(self, image: _FakePillowImage) -> None:
        self.image = image

    def rectangle(self, bounds: tuple[int, int, int, int], *, fill: str) -> None:
        colors = {"#E8F4F1": (232, 244, 241), "#79AAA6": (121, 170, 166), "#E6B9AE": (230, 185, 174)}
        x1, y1, x2, y2 = bounds
        color = colors[fill]
        for y in range(max(0, y1), min(self.image.height, y2)):
            for x in range(max(0, x1), min(self.image.width, x2)):
                self.image.pixels[y * self.image.width + x] = color

    def text(self, *_args, **_kwargs) -> None:
        pass

    def multiline_text(self, *_args, **_kwargs) -> None:
        """Mirror Pillow's multiline API for the deterministic PNG path."""
        pass

    def line(self, *_args, **_kwargs) -> None:
        """Accept deterministic composition strokes without emulating Pillow pixels."""
        pass

    def arc(self, *_args, **_kwargs) -> None:
        """Accept deterministic composition arcs without emulating Pillow pixels."""
        pass

    def ellipse(self, *_args, **_kwargs) -> None:
        """Accept deterministic composition ellipses without emulating Pillow pixels."""
        pass

    def rounded_rectangle(self, *_args, **_kwargs) -> None:
        """Accept deterministic composition rounded rectangles without emulating Pillow pixels."""
        pass

    def textbbox(self, xy: tuple[int, int], text: str, *, font=None, **_kwargs) -> tuple[int, int, int, int]:
        """Provide stable text measurement for the fake renderer's wrapping path."""
        x, y = xy
        return (x, y, x + max(1, len(str(text))) * 9, y + 16)


def _install_fake_pillow(monkeypatch: pytest.MonkeyPatch) -> None:
    image_module = types.SimpleNamespace(new=lambda _mode, size, color: _FakePillowImage(size[0], size[1], (255, 248, 236)))
    draw_module = types.SimpleNamespace(Draw=_FakePillowDraw)
    pil_module = types.ModuleType("PIL")
    pil_module.Image = image_module  # type: ignore[attr-defined]
    pil_module.ImageDraw = draw_module  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "PIL", pil_module)


def _accepted_storyboard_for_summary(spec: dict) -> dict:
    units = []
    for index, anchor in enumerate(spec["anchors"], start=1):
        services = list(anchor.get("services", ["OCI Monitoring"]))
        units.append({
            "id": f"unit-{index}", "summary_anchor_id": f"anchor-{index}",
            "artifact_job": "workflow step", "thesis": "A grounded operational step.",
            "register": "explainer", "staging": "center", "physical_move": "routes a signal",
            "objects": ["signal"], "character_action": "routes the signal through a gate",
            "interaction_geometry": "hand touches the signal", "cast_role": "operator",
            "service_ids": services,
            "service_context": [
                {"canonical_service_id": "oci.monitoring", "display_name": service}
                for service in services
            ],
            "source_ids": list(anchor["source_ids"]), "evidence_class": anchor["evidence_class"],
            "text_policy": "deterministic-outside-art", "alt_text": "An operator routes a signal.",
        })
    return {"schema_version": 1, "classification": "private-generation-input",
            "coverage": "hero-workflow-scenes-service-map-summary", "project_thesis": "Operate safely.",
            "units": units, "audience_sequence": [unit["id"] for unit in units]}


def test_storyboard_handoff_builds_five_audience_sections(tmp_path: Path) -> None:
    if storyboard.Image is None:
        pytest.skip("scene manifest validation requires the configured Pillow runtime")
    spec = valid_spec()
    for anchor in spec["anchors"]:
        anchor["services"] = ["OCI Monitoring"]
    accepted = _accepted_storyboard_for_summary(spec)
    pixel = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg==")
    scenes = []
    digest = hashlib.sha256(pixel).hexdigest()
    for index, unit in enumerate(accepted["units"], start=1):
        image = tmp_path / f"scene-{index}.png"; image.write_bytes(pixel)
        scenes.append({"unit_id": unit["id"], "path": image.name, "sha256": digest,
            "character_pack": "operator-v1", "model_sheet_digest": "a" * 64,
            "style_anchor_digest": None if index == 1 else digest, "generator": "offline-review",
            "rights": "original", "review_status": "approved",
            "qa": {name: "pass" for name in ("thesis", "artifact_job", "topology", "load_bearing_character", "text_free_art", "originality", "style_consistency")}})
    manifest_path = tmp_path / "scenes.json"; manifest_path.write_text(json.dumps({"schema_version": 1, "scenes": scenes}), encoding="utf-8")
    manifest = storyboard.load_scene_manifest(manifest_path, accepted)
    icons = [{"unit_id": "unit-1", "canonical_service_id": "oci.monitoring", "display_name": "OCI Monitoring",
              "mapping_type": "exact-service", "alt_text": "Monitoring service icon", "private_catalog_asset_id": "icon-1"}]

    handoff = summary.build_storyboard_handoff(spec, accepted, manifest, icons, width=1920, height=1080)

    assert [page["role"] for page in handoff["pages"]] == [
        "project-promise", "workflow", "capability-scenes", "oci-service-map", "at-a-glance",
    ]
    assert len(next(page for page in handoff["pages"] if page["role"] == "capability-scenes")["scenes"]) == 4
    assert handoff["source_register"]
    assert all(item["url"].startswith("https://docs.oracle.com/") for item in handoff["source_register"])
    text = json.dumps(handoff)
    assert "prompt" not in text.lower()
    assert "icon-cache" not in text.lower()
    for private_field in ("model_sheet_digest", "style_anchor_digest", "generator", "scene_provenance", "private_scene", '"qa"', str(tmp_path)):
        assert private_field not in text


def test_internal_storyboard_svg_embeds_selected_icon_without_source_path(tmp_path: Path) -> None:
    handoff = {
        "schema_version": 1, "canvas": {"width": 640, "height": 360},
        "title": "Observe", "takeaway": "Signals are owned.",
        "pages": [{"role": "oci-service-map", "title": "Service map", "services": [{
            "canonical_service_id": "oci.autonomous-database", "display_name": "Autonomous Database",
            "mapping_type": "exact-service", "alt_text": "Autonomous Database service icon", "private_catalog_asset_id": "icon-1",
        }]}],
        "private_icon_resolution": {"classification": "internal", "icon-1": {"bytes": b'<svg viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>', "sha256": __import__("hashlib").sha256(b'<svg viewBox="0 0 10 10"><path d="M0 0h10v10z"/></svg>').hexdigest()}},
    }

    out = summary.render_storyboard_svg(handoff, tmp_path / "summary.svg")
    text = out.read_text(encoding="utf-8")
    assert 'data-service-icon="oci.autonomous-database"' in text
    assert "data:image/svg+xml;base64," in text
    assert "/Users/" not in text
    assert "icon-cache" not in text


@pytest.mark.parametrize("payload", [
    b'<!DOCTYPE svg [<!ENTITY x "boom">]><svg/>',
    b'<svg><script>alert(1)</script></svg>',
    b'<svg><path onclick="alert(1)" d="M0 0"/></svg>',
    b'<svg><style>@import "https://evil.invalid/a";</style></svg>',
    b'<svg><path fill="url(https://evil.invalid/a)" d="M0 0"/></svg>',
    b'<svg><image href="https://evil.invalid/a"/></svg>',
    b'<svg><use href="../x.svg"/></svg>',
])
def test_storyboard_icon_rejects_active_or_external_svg(payload: bytes) -> None:
    record = {"private_catalog_asset_id": "icon-1"}
    receipt = {"icon-1": {"bytes": payload, "sha256": hashlib.sha256(payload).hexdigest()}}
    with pytest.raises(summary.SummaryError):
        summary._storyboard_safe_icon_uri(record, receipt)


def test_storyboard_icon_rejects_digest_and_public_restricted_catalog() -> None:
    record = {"private_catalog_asset_id": "icon-1"}
    with pytest.raises(summary.SummaryError, match="changed"):
        summary._storyboard_safe_icon_uri(record, {"classification": "internal", "icon-1": {"bytes": b"<svg/>", "sha256": "0" * 64}})
    with pytest.raises(summary.SummaryError, match="public"):
        summary._storyboard_safe_icon_uri(record, {"classification": "public", "catalog": {"classification": "internal-only", "icons": []}, "root": "."})
    with pytest.raises(summary.SummaryError, match="explicit internal"):
        summary._storyboard_safe_icon_uri(record, {"icon-1": {"bytes": b"<svg/>", "sha256": hashlib.sha256(b"<svg/>").hexdigest()}})


def test_storyboard_outputs_expand_capabilities_and_create_valid_png_pdf(tmp_path: Path) -> None:
    handoff = {"schema_version": 1, "canvas": {"width": 640, "height": 360}, "title": "Observe", "takeaway": "Signals are owned.", "evidence_footer": "Oracle docs", "pages": [
        {"role": "project-promise", "title": "Observe", "scenes": [{"unit_id": "u1", "title": "One", "detail": "First", "evidence_class": "code-backed"}]},
        {"role": "workflow", "title": "Workflow", "scenes": [{"unit_id": "u1", "title": "One", "detail": "First", "evidence_class": "code-backed"}, {"unit_id": "u2", "title": "Two", "detail": "Second", "evidence_class": "code-backed"}]},
        {"role": "capability-scenes", "title": "Capability scenes", "scenes": [{"unit_id": "u1", "title": "One", "detail": "First", "evidence_class": "code-backed"}, {"unit_id": "u2", "title": "Two", "detail": "Second", "evidence_class": "code-backed"}]},
        {"role": "oci-service-map", "title": "OCI service map", "services": [{"canonical_service_id": "oci.monitoring", "display_name": "OCI Monitoring", "mapping_type": "none", "alt_text": "Monitoring", "private_catalog_asset_id": None}]},
        {"role": "at-a-glance", "title": "At a glance", "takeaway": "Signals are owned.", "scenes": [{"unit_id": "u1", "title": "One", "detail": "First", "evidence_class": "code-backed"}], "services": [{"canonical_service_id": "oci.monitoring", "display_name": "OCI Monitoring", "mapping_type": "none", "alt_text": "Monitoring", "private_catalog_asset_id": None}]},
    ]}
    outputs = summary.build_storyboard_outputs(handoff, tmp_path, {"svg", "png", "pdf"})
    names = {path.name for path in outputs}
    assert "capability-scenes-u1.svg" in names and "capability-scenes-u2.svg" in names
    png = (tmp_path / "capability-scenes-u1.png").read_bytes()
    assert png.startswith(b"\x89PNG\r\n\x1a\n") and b"IHDR" in png and b"IDAT" in png
    assert __import__("struct").unpack(">II", png[16:24]) == (640, 360)
    pypdf = pytest.importorskip("pypdf")
    extracted = "\n".join(page.extract_text() or "" for page in pypdf.PdfReader(tmp_path / "oci-service-map.pdf").pages)
    assert "OCI Monitoring" in extracted and "none" in extracted and "Oracle docs" in extracted
    # The non-optional fallback remains customer-facing and must never leak
    # generic physical-page placeholders.
    assert "Operator text" not in extracted and "Approved assets" not in extracted


def test_storyboard_render_rechecks_scene_digest_after_handoff(tmp_path: Path) -> None:
    image = tmp_path / "scene.png"; image.write_bytes(b"scene-one")
    digest = hashlib.sha256(b"scene-one").hexdigest()
    scene = {"unit_id": "u1", "title": "One", "detail": "First", "evidence_class": "code-backed"}
    public = {"schema_version": 1, "canvas": {"width": 64, "height": 36}, "title": "Observe", "takeaway": "Signals", "pages": [
        {"role": "at-a-glance", "title": "At a glance", "scenes": [scene], "services": []}
    ]}
    handoff = summary._StoryboardHandoff(public, {"u1": str(image)}, {"u1": {"sha256": digest}})
    image.write_bytes(b"scene-two")
    with pytest.raises(summary.SummaryError, match="changed"):
        summary.render_storyboard_svg(handoff, tmp_path / "out.svg")
    with pytest.raises(summary.SummaryError, match="changed"):
        summary._render_storyboard_page_png(handoff, public["pages"][0], tmp_path / "out.png", {})
    with pytest.raises(summary.SummaryError, match="changed"):
        summary._render_storyboard_page_pdf(handoff, public["pages"][0], tmp_path / "out.pdf", {})


def test_storyboard_png_uses_all_scene_and_icon_pixels_at_requested_size_without_optional_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dropping a successful icon raster or any approved scene would hide a capability."""
    handoff, private_icons, scene_colors, icon_colors = _storyboard_asset_fixture(tmp_path)
    page = handoff["pages"][0]

    def fake_raster(payload: bytes, _width: int, _height: int) -> bytes:
        for color in icon_colors:
            if f"rgb{color}".encode() in payload:
                return _solid_png(color)
        raise AssertionError("unexpected synthetic icon payload")

    monkeypatch.setitem(sys.modules, "PIL", None)
    monkeypatch.setattr(summary, "_rasterize_verified_svg", fake_raster)
    physical = summary._storyboard_physical_pages([page])
    payloads = []
    seen_scenes: list[str] = []
    seen_services: list[str] = []
    for page_number, physical_page in enumerate(physical, start=1):
        payload = summary._render_storyboard_page_png(handoff, physical_page, tmp_path / f"all-assets-{page_number}.png", private_icons).read_bytes()
        payloads.append(payload)
        assert struct.unpack(">II", payload[16:24]) == (800, 600)
        metadata = _png_storyboard_metadata(payload)
        for scene in metadata["scenes"]:
            index = int(scene["unit_id"].rsplit("-", 1)[1])
            bounds = scene["bounds"]
            assert _png_rgb_at(payload, bounds["x"] + 1, bounds["y"] + 1) == scene_colors[index - 1]
            seen_scenes.append(scene["unit_id"])
        for service in metadata["services"]:
            index = int(service["canonical_service_id"].rsplit("-", 1)[1])
            bounds = service["bounds"]
            assert _png_rgb_at(payload, bounds["x"] + 1, bounds["y"] + 1) == icon_colors[index - 1]
            seen_services.append(service["canonical_service_id"])
        assert str(tmp_path).encode() not in payload
    assert seen_scenes == [f"unit-{index}" for index in range(1, 7)]
    assert seen_services == [f"oci.service-{index}" for index in range(1, 7)]


def test_storyboard_pdf_renders_every_scene_and_icon_with_native_text_without_optional_packages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Removing the first-four cap must retain all image and operator-text identities."""
    handoff, private_icons, _scene_colors, icon_colors = _storyboard_asset_fixture(tmp_path)
    page = handoff["pages"][0]
    _install_fake_reportlab(monkeypatch)
    monkeypatch.setattr(
        summary,
        "_rasterize_verified_svg",
        lambda payload, _width, _height: next(_solid_png(color) for color in icon_colors if f"rgb{color}".encode() in payload),
    )
    monkeypatch.setattr(summary, "_pdf_draw_asset", lambda pdf, payload, *bounds: pdf.drawImage(payload, *bounds))

    payload = b"".join(
        summary._render_storyboard_page_pdf(handoff, physical_page, tmp_path / f"all-assets-{index}.pdf", private_icons).read_bytes()
        for index, physical_page in enumerate(summary._storyboard_physical_pages([page]), start=1)
    )
    assert payload.count(b"/Subtype /Image") == 12
    for index in range(1, 7):
        assert f"Capability {index}: Mapping detail {index} [code-backed]".encode() in payload
        assert f"OCI Service {index}".encode() in payload
        assert b"exact-service" in payload
    assert b"Oracle Source Alpha; Oracle Source Beta" in payload
    assert str(tmp_path).encode() not in payload


def test_storyboard_pdf_keeps_other_assets_when_one_optional_image_decoder_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One optional decoder failure is local to that asset, not the remaining page."""
    handoff, private_icons, scene_colors, icon_colors = _storyboard_asset_fixture(tmp_path)
    page = handoff["pages"][0]
    failed_payload = _solid_png(scene_colors[2])
    _install_fake_reportlab(monkeypatch)
    monkeypatch.setattr(
        summary,
        "_rasterize_verified_svg",
        lambda payload, _width, _height: next(_solid_png(color) for color in icon_colors if f"rgb{color}".encode() in payload),
    )

    def draw_asset(pdf: _FakePdfCanvas, payload: bytes, *bounds) -> None:
        if payload == failed_payload:
            raise summary._OptionalAssetBackendUnavailable("synthetic one-asset decoder failure")
        pdf.drawImage(payload, *bounds)

    monkeypatch.setattr(summary, "_pdf_draw_asset", draw_asset)
    payload = b"".join(
        summary._render_storyboard_page_pdf(handoff, physical_page, tmp_path / f"one-failure-{index}.pdf", private_icons).read_bytes()
        for index, physical_page in enumerate(summary._storyboard_physical_pages([page]), start=1)
    )

    assert payload.count(b"/Subtype /Image") == 11
    assert b"Scene image fallback: native text" in payload
    assert b"OCI Service 6" in payload


@pytest.mark.parametrize(
    ("icon_payload", "private_icons", "message"),
    [
        (b'<svg><script>alert(1)</script></svg>', None, "active or unsupported"),
        (b'<svg viewBox="0 0 1 1"><path d="M0 0h1v1z"/></svg>', {"classification": "internal", "icon-1": {"bytes": b'<svg viewBox="0 0 1 1"><path d="M0 0h1v1z"/></svg>', "sha256": "0" * 64}}, "changed"),
        (b'<svg viewBox="0 0 1 1"><path d="M0 0h1v1z"/></svg>', None, "explicit internal classification"),
    ],
)
def test_storyboard_pdf_propagates_icon_security_digest_and_public_classification_errors(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    icon_payload: bytes,
    private_icons: dict | None,
    message: str,
) -> None:
    """PDF must never convert validation failures into an optional icon fallback."""
    service = {
        "canonical_service_id": "oci.monitoring", "display_name": "OCI Monitoring",
        "mapping_type": "exact-service", "alt_text": "Monitoring", "private_catalog_asset_id": "icon-1",
    }
    handoff = {
        "canvas": {"width": 800, "height": 600}, "evidence_footer": "Oracle source",
        "pages": [{"role": "oci-service-map", "title": "Service map", "services": [service]}],
    }
    if private_icons is None:
        receipt = {"bytes": icon_payload, "sha256": hashlib.sha256(icon_payload).hexdigest()}
        private_icons = {"classification": "internal", "icon-1": receipt}
        if "classification" in message:
            private_icons["classification"] = "public"
    monkeypatch.setattr(summary, "_reportlab_available", lambda: False)

    with pytest.raises(summary.SummaryError, match=message):
        summary._render_storyboard_page_pdf(handoff, handoff["pages"][0], tmp_path / "blocked.pdf", private_icons)


@pytest.mark.parametrize("icon_count", [9, 12])
def test_storyboard_svg_paginates_every_service_with_bounded_shared_layout(
    tmp_path: Path, icon_count: int,
) -> None:
    """Adding a third icon row must create a numbered page, never clip the row."""
    handoff, private_icons, _scene_colors, _icon_colors = _storyboard_asset_fixture(tmp_path, 4, icon_count=icon_count)
    _five_section_storyboard(handoff)

    outputs = summary.build_storyboard_outputs(handoff, tmp_path, {"svg"}, private_icon_catalog=private_icons)
    names = {path.name for path in outputs}
    assert {name for name in names if name.startswith("oci-service-map")} == {"oci-service-map-1.svg", "oci-service-map-2.svg"}
    assert {name for name in names if name.startswith("at-a-glance")} == {"at-a-glance-1.svg", "at-a-glance-2.svg"}

    expected_ids = {f"oci.service-{index}" for index in range(1, icon_count + 1)}
    for role in ("oci-service-map", "at-a-glance"):
        seen: list[str] = []
        for page_number in (1, 2):
            payload = (tmp_path / f"{role}-{page_number}.svg").read_text(encoding="utf-8")
            svg_tag = re.search(r'<svg ([^>]*)>', payload)
            assert svg_tag
            root_attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', svg_tag.group(1)))
            assert root_attrs["data-audience-role"] == role
            assert root_attrs["data-page-number"] == str(page_number)
            assert root_attrs["data-page-count"] == "2"
            for group_attrs in re.findall(r'<g ([^>]*data-service-icon="[^"]+"[^>]*)>', payload):
                group = dict(re.findall(r'([\w-]+)="([^"]*)"', group_attrs))
                service_id = group["data-service-icon"]
                seen.append(service_id)
                x = int(group["data-layout-x"])
                y = int(group["data-layout-y"])
                width = int(group["data-layout-width"])
                height = int(group["data-layout-height"])
                assert 0 <= x < 800 and 0 <= y < 600
                assert x + width <= 800 and y + height <= 600
                assert int(group["data-label-x"]) + int(group["data-label-width"]) <= 800
                assert int(group["data-label-y"]) + int(group["data-label-height"]) <= 600
                index = int(service_id.rsplit("-", 1)[1])
                assert f"OCI Service {index}" in payload
                assert group["data-canonical-service-id"] == service_id
                assert group["data-mapping-type"] == "exact-service"
                assert "Oracle Source Alpha; Oracle Source Beta" in payload.replace("\u00a0", " ")
        assert len(seen) == icon_count
        assert set(seen) == expected_ids


@pytest.mark.parametrize("role,scene_count,service_count", [("workflow", 4, 4), ("at-a-glance", 4, 8)])
def test_pdf_reviewed_evidence_geometry_separates_scene_captions_and_service_icons(
    role: str, scene_count: int, service_count: int,
) -> None:
    page = {
        "audience_role": role,
        "role": role,
        "scenes": [{"unit_id": f"u{i}", "title": f"Scene {i}"} for i in range(scene_count)],
        "services": [{"canonical_service_id": f"oci.service-{i}", "display_name": f"Service {i}"} for i in range(service_count)],
    }
    geometry = summary._pdf_reviewed_evidence_geometry(page, 720, 405)
    footer = geometry["footer"]
    assert footer[1] >= 0
    footer_top = footer[1] + footer[3]
    assert footer_top <= 405
    rects = geometry["scenes"] + geometry["services"]
    for x, y, w, h, label in rects:
        assert 0 <= x and 0 <= y and x + w <= 720 and y >= footer_top
        lx, ly, lw, lh = label
        assert 0 <= lx and 0 <= ly and lx + lw <= 720 and ly >= footer_top
        assert not (x < lx + lw and lx < x + w and y < ly + lh and ly < y + h)
    for index, first in enumerate(rects):
        x, y, w, h, _ = first
        for second in rects[index + 1:]:
            sx, sy, sw, sh, _ = second
            assert not (x < sx + sw and sx < x + w and y < sy + sh and sy < y + h)


@pytest.mark.parametrize("icon_count", [9, 12])
@pytest.mark.parametrize("backend", ["pillow", "dependency-free"])
def test_storyboard_png_paginates_icons_without_clipping_in_both_local_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, icon_count: int, backend: str,
) -> None:
    """Both PNG compositors consume the same numbered pages and bounded icon slots."""
    handoff, private_icons, _scene_colors, icon_colors = _storyboard_asset_fixture(tmp_path, 4, icon_count=icon_count)
    _five_section_storyboard(handoff)

    def fake_raster(payload: bytes, _width: int, _height: int) -> bytes:
        return next(_solid_png(color, 96, 96) for color in icon_colors if f"rgb{color}".encode() in payload)

    monkeypatch.setattr(summary, "_rasterize_verified_svg", fake_raster)
    if backend == "dependency-free":
        monkeypatch.setitem(sys.modules, "PIL", None)
    else:
        _install_fake_pillow(monkeypatch)
        monkeypatch.setattr(
            summary, "_decode_scene_image",
            lambda payload: _FakePillowImage(96, 96, summary._tiny_png_color(payload) or (0, 0, 0)),
        )

    outputs = summary.build_storyboard_outputs(handoff, tmp_path, {"png"}, private_icon_catalog=private_icons)
    names = {path.name for path in outputs}
    assert {name for name in names if name.startswith("oci-service-map")} == {"oci-service-map-1.png", "oci-service-map-2.png"}
    assert {name for name in names if name.startswith("at-a-glance")} == {"at-a-glance-1.png", "at-a-glance-2.png"}

    for role in ("oci-service-map", "at-a-glance"):
        seen: list[str] = []
        for page_number in (1, 2):
            payload = (tmp_path / f"{role}-{page_number}.png").read_bytes()
            assert struct.unpack(">II", payload[16:24]) == (800, 600)
            metadata = _png_storyboard_metadata(payload)
            assert metadata["audience_role"] == role
            assert metadata["page_number"] == page_number
            assert metadata["page_count"] == 2
            assert metadata["evidence"] == "Oracle Source Alpha; Oracle Source Beta"
            for service in metadata["services"]:
                seen.append(service["canonical_service_id"])
                bounds = service["bounds"]
                assert bounds["x"] + bounds["width"] <= 800
                assert bounds["y"] + bounds["height"] <= 600
                label_bounds = service["label_bounds"]
                assert label_bounds["x"] + label_bounds["width"] <= 800
                assert label_bounds["y"] + label_bounds["height"] <= 600
                index = int(service["canonical_service_id"].rsplit("-", 1)[1])
                assert service["display_name"] == f"OCI Service {index}"
                assert service["mapping_type"] == "exact-service"
                assert _png_rgb_at(payload, bounds["x"] + 1, bounds["y"] + 1) == icon_colors[index - 1]
        assert seen == [f"oci.service-{index}" for index in range(1, icon_count + 1)]


@pytest.mark.parametrize(("scene_count", "page_count"), [(4, 1), (8, 2)])
def test_storyboard_scene_pages_are_bounded_and_ordered_for_four_or_eight_scenes(
    tmp_path: Path, scene_count: int, page_count: int,
) -> None:
    """Accepted 4–8 scene sequences must use bounded slots in source order."""
    handoff, private_icons, _scene_colors, _icon_colors = _storyboard_asset_fixture(tmp_path, scene_count, icon_count=0)
    _five_section_storyboard(handoff)
    summary.build_storyboard_outputs(handoff, tmp_path, {"svg"}, private_icon_catalog=private_icons)

    paths = [tmp_path / "workflow.svg"] if page_count == 1 else [tmp_path / f"workflow-{index}.svg" for index in range(1, page_count + 1)]
    seen: list[str] = []
    for path in paths:
        payload = path.read_text(encoding="utf-8")
        for group_attrs in re.findall(r'<g ([^>]*data-storyboard-scene="[^"]+"[^>]*)>', payload):
            group = dict(re.findall(r'([\w-]+)="([^"]*)"', group_attrs))
            seen.append(group["data-storyboard-scene"])
            x = int(group["data-layout-x"])
            y = int(group["data-layout-y"])
            width = int(group["data-layout-width"])
            height = int(group["data-layout-height"])
            assert x + width <= 800 and y + height <= 600
            assert int(group["data-label-x"]) + int(group["data-label-width"]) <= 800
            assert int(group["data-label-y"]) + int(group["data-label-height"]) <= 600
    assert seen == [f"unit-{index}" for index in range(1, scene_count + 1)]


def test_storyboard_pdf_uses_the_same_numbered_physical_pages(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PDF must consume the same 4-scene/8-service page partition as SVG and PNG."""
    handoff, private_icons, _scene_colors, icon_colors = _storyboard_asset_fixture(tmp_path, 8, icon_count=12)
    _five_section_storyboard(handoff)
    _install_fake_reportlab(monkeypatch)
    monkeypatch.setattr(
        summary, "_rasterize_verified_svg",
        lambda payload, _width, _height: next(_solid_png(color) for color in icon_colors if f"rgb{color}".encode() in payload),
    )
    monkeypatch.setattr(summary, "_pdf_draw_asset", lambda pdf, payload, *bounds: pdf.drawImage(payload, *bounds))

    outputs = summary.build_storyboard_outputs(handoff, tmp_path, {"pdf"}, private_icon_catalog=private_icons)
    names = {path.name for path in outputs}
    assert {name for name in names if name.startswith("workflow")} == {"workflow-1.pdf", "workflow-2.pdf"}
    assert {name for name in names if name.startswith("oci-service-map")} == {"oci-service-map-1.pdf", "oci-service-map-2.pdf"}
    assert {name for name in names if name.startswith("at-a-glance")} == {"at-a-glance-1.pdf", "at-a-glance-2.pdf"}
    assert sum((tmp_path / f"oci-service-map-{index}.pdf").read_bytes().count(b"/Subtype /Image") for index in (1, 2)) == 12


def test_at_a_glance_svg_reserves_footer_band_below_all_eight_service_labels(tmp_path: Path) -> None:
    """At-a-glance mapping text must end before the evidence footer starts."""
    handoff, private_icons, _scene_colors, _icon_colors = _storyboard_asset_fixture(tmp_path, 4, icon_count=8)
    _five_section_storyboard(handoff)
    summary.build_storyboard_outputs(handoff, tmp_path, {"svg"}, private_icon_catalog=private_icons)

    payload = (tmp_path / "at-a-glance.svg").read_text(encoding="utf-8")
    footer_match = re.search(r'<g ([^>]*data-evidence-footer="true"[^>]*)>', payload)
    assert footer_match
    footer = dict(re.findall(r'([\w-]+)="([^"]*)"', footer_match.group(1)))
    footer_top = int(footer["data-layout-y"])
    assert footer_top + int(footer["data-layout-height"]) <= 600
    labels = []
    for group_attrs in re.findall(r'<g ([^>]*data-service-icon="[^"]+"[^>]*)>', payload):
        group = dict(re.findall(r'([\w-]+)="([^"]*)"', group_attrs))
        labels.append((int(group["data-label-y"]), int(group["data-label-height"])))
    assert len(labels) == 8
    assert all(y + height <= footer_top for y, height in labels)
    normalized_payload = payload.replace("\u00a0", " ")
    assert "exact-service" in normalized_payload and "Oracle Source Alpha; Oracle Source Beta" in normalized_payload


@pytest.mark.parametrize("backend", ["pillow", "dependency-free"])
def test_at_a_glance_png_reserves_footer_band_below_all_eight_service_labels(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, backend: str,
) -> None:
    """Pillow and dependency-free PNG must consume the same footer-safe bounds."""
    handoff, private_icons, _scene_colors, icon_colors = _storyboard_asset_fixture(tmp_path, 4, icon_count=8)
    _five_section_storyboard(handoff)

    def fake_raster(payload: bytes, _width: int, _height: int) -> bytes:
        return next(_solid_png(color, 96, 96) for color in icon_colors if f"rgb{color}".encode() in payload)

    monkeypatch.setattr(summary, "_rasterize_verified_svg", fake_raster)
    if backend == "dependency-free":
        monkeypatch.setitem(sys.modules, "PIL", None)
    else:
        _install_fake_pillow(monkeypatch)
        monkeypatch.setattr(summary, "_decode_scene_image", lambda payload: _FakePillowImage(96, 96, summary._tiny_png_color(payload) or (0, 0, 0)))

    summary.build_storyboard_outputs(handoff, tmp_path, {"png"}, private_icon_catalog=private_icons)
    metadata = _png_storyboard_metadata((tmp_path / "at-a-glance.png").read_bytes())
    footer = metadata["footer_bounds"]
    assert footer["y"] + footer["height"] <= 600
    assert len(metadata["services"]) == 8
    assert all(service["label_bounds"]["y"] + service["label_bounds"]["height"] <= footer["y"] for service in metadata["services"])
    assert metadata["evidence"] == "Oracle Source Alpha; Oracle Source Beta"


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
            "mascot_mode": "nimb-operator",
            "style_preset": "oci-doodle",
            "doodle_level": "rich",
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
                "accessed": "2026-08-23",
                "classification": "public",
            }
        ],
        "privacy": {"classification": "public", "public_eligible": True},
        "outputs": {"formats": ["png", "pdf", "drawio", "excalidraw"], "aspect_ratio": "16:9"},
        "accessibility": {"reading_order": ["title", "anchors"], "alt_text": "A verified access route."},
    }


def test_canvas_story_map_writes_private_scene_and_composition_plans(tmp_path: Path) -> None:
    """Canvas planning is opt-in and keeps its generation inputs off public handoffs."""
    spec = valid_spec()
    spec["visual_direction"]["style_variant"] = "canvas-story-map"
    roles = ("human-security-architect", "human-ai-engineer", "nimb-operator", "observability-guide")
    for index, anchor in enumerate(spec["anchors"]):
        anchor.update({
            "scene_hint": f"scene cue {index}",
            "relationship": f"relates-to-{index}",
            "services": [f"service-{index}"],
            "scene_role": roles[index],
        })

    paths = summary.build_canvas_plan(spec, tmp_path)
    private_dir = tmp_path / ".visual-summary-private"

    assert {path.name for path in paths} == {
        "design-philosophy.md", "oci-workflow-map.json", "scene-plan.json", "composition-plan.json",
    }
    assert all(path.parent == private_dir for path in paths)
    assert private_dir.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in paths)

    scene_plan = json.loads((private_dir / "scene-plan.json").read_text(encoding="utf-8"))
    assert len(scene_plan["scenes"]) == len(spec["anchors"])
    for index, scene in enumerate(scene_plan["scenes"]):
        assert scene["thesis"]
        assert scene["physical_move"]
        assert scene["object_metaphor"]
        assert scene["character_role"] == roles[index]
        assert scene["register_staging"]
        assert scene["service_context"] == [f"service-{index}"]
        assert scene["relationship"] == f"relates-to-{index}"
        assert scene["scene_prompt"]
        assert "no words" in scene["scene_prompt"].lower()
        assert spec["anchors"][index]["title"].lower() not in scene["scene_prompt"].lower()

    composition = json.loads((private_dir / "composition-plan.json").read_text(encoding="utf-8"))
    assert composition["headline_zone"]
    assert composition["dominant_thread"]
    assert len(composition["irregular_scene_placements"]) == len(spec["anchors"])
    assert composition["negative_space_target"]
    assert composition["art_text_z_order"]
    assert composition["export_roles"]

    public_handoff = summary._portable_handoff(summary.build_handoff(spec, 1920, 1080))
    public_text = json.dumps(public_handoff)
    assert "scene cue" not in public_text
    assert "design philosophy" not in public_text.lower()
    assert str(private_dir) not in public_text


def test_canvas_story_map_plan_is_available_from_the_cli(tmp_path: Path) -> None:
    """Operators can generate the private planning packet without a renderer build."""
    spec = valid_spec()
    spec["visual_direction"]["style_variant"] = "canvas-story-map"
    spec_path = tmp_path / "canvas-spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "visual_summary.py"), "canvas-plan", "--spec", str(spec_path), "--out-dir", str(tmp_path / "out")],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "scene-plan.json" in result.stdout
    assert (tmp_path / "out" / ".visual-summary-private" / "composition-plan.json").is_file()


def test_canvas_scene_plan_replaces_whitespace_only_direction_fields(tmp_path: Path) -> None:
    """Whitespace-only optional canvas direction must not yield blank planning rows."""
    spec = valid_spec()
    spec["visual_direction"]["style_variant"] = "canvas-story-map"
    spec["anchors"][0].update({"scene_role": " \t ", "scene_hint": "  ", "relationship": "\n"})

    summary.build_canvas_plan(spec, tmp_path)
    scene = json.loads((tmp_path / ".visual-summary-private" / "scene-plan.json").read_text(encoding="utf-8"))["scenes"][0]

    assert scene["character_role"] == "operator"
    assert scene["relationship"] == "connected workflow step"
    assert "  " not in scene["scene_prompt"]
    assert "stages  as" not in scene["scene_prompt"]


def test_canvas_plan_accepts_a_real_tempfile_var_alias_path() -> None:
    """The macOS /var alias is canonicalized before private symlink checks."""
    if not Path("/var").is_symlink():
        pytest.skip("platform has no /var alias")
    canonical_root = Path(tempfile.mkdtemp(prefix="canvas-plan-", dir=tempfile.gettempdir())).resolve()
    try:
        relative = canonical_root.relative_to("/private/var")
    except ValueError:
        pytest.skip("tempfile directory is not below macOS /private/var")
    alias_root = Path("/var") / relative
    spec = valid_spec()
    spec["visual_direction"]["style_variant"] = "canvas-story-map"

    summary.build_canvas_plan(spec, alias_root)

    assert (canonical_root / ".visual-summary-private" / "scene-plan.json").is_file()


def test_canvas_renderer_uses_scene_led_svg_layers_and_portable_geometry(tmp_path: Path) -> None:
    """Canvas variants must not silently reuse the legacy cluster-shell renderer."""
    spec = valid_spec()
    spec["visual_direction"]["style_variant"] = "canvas-story-map"
    handoff = summary.build_handoff(spec, 1920, 1080)
    art = tmp_path / "scene.png"
    art.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg=="))
    handoff["clusters"][0].update({"art_path": str(art), "art_root": str(tmp_path)})

    portable = summary._portable_handoff(handoff)
    assert portable["canvas_layout"]["composition"] == "scene-led"
    assert all({"canvas_role", "text_bounds", "art_bounds"} <= set(cluster) for cluster in portable["clusters"])
    portable_text = json.dumps(portable)
    assert "scene_prompt" not in portable_text
    assert str(tmp_path) not in portable_text
    assert ".visual-summary-private" not in portable_text

    svg = summary.render_svg(handoff, tmp_path / "canvas.svg").read_text(encoding="utf-8")
    assert 'data-canvas-thread="oracle-red"' in svg
    assert svg.count('data-canvas-layer="scene-art"') == len(handoff["clusters"])
    assert svg.count('data-canvas-layer="scene-annotation"') == len(handoff["clusters"])
    assert 'data-canvas-layer="evidence"' in svg
    assert 'data-story-layer="scene"' not in svg
    assert 'preserveAspectRatio="xMidYMid meet"' in svg
    assert 'Chalkboard SE' in svg


def test_canvas_story_map_uses_readable_scene_scale_and_balanced_occupancy(tmp_path: Path) -> None:
    """The Canvas one-pager must fill the page with six legible, art-led scenes."""
    spec = valid_spec()
    spec["visual_direction"]["style_variant"] = "canvas-story-map"
    spec["anchors"] = [
        {"title": f"Scene {index}", "detail": "A governed operator control step.", "evidence_class": "code-backed", "source_ids": ["https://docs.oracle.com/en-us/iaas/Content/Identity/home.htm"]}
        for index in range(1, 7)
    ]
    handoff = summary.build_handoff(spec, 1920, 1080)
    assert len(handoff["clusters"]) == 6
    art = [cluster["art_bounds"] for cluster in handoff["clusters"]]
    assert min(item["width"] for item in art) >= 300
    assert min(item["height"] for item in art) >= 150
    assert min(item["y"] for item in art) <= 290
    assert max(item["y"] + item["height"] for item in art) >= 850
    assert min(item["x"] for item in art) <= 140
    assert max(item["x"] + item["width"] for item in art) >= 1780
    svg = summary.render_svg(handoff, tmp_path / "canvas.svg").read_text(encoding="utf-8")
    sizes = [float(value) for value in __import__("re").findall(r'font-size="([0-9.]+)"', svg)]
    assert max(sizes) >= 60
    assert sum(size >= 20 for size in sizes) >= 7


def test_canvas_png_has_native_font_renderer_and_full_canvas_marker() -> None:
    """Raster generation must remain native-font based when PIL is available."""
    source = (SKILL / "scripts" / "visual_summary.py").read_text(encoding="utf-8")
    assert "ImageFont.truetype" in source
    assert "_render_canvas_png_fallback" in source
    assert 'CANVAS scene-led; THREAD oracle-red; EVIDENCE' in source
    assert "PngInfo" in source


def test_canvas_svg_font_family_is_xml_escaped_and_parseable(tmp_path: Path) -> None:
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)
    svg = summary.render_svg(handoff, tmp_path / "summary.svg").read_text(encoding="utf-8")
    assert "font-family=\"system-ui" in svg
    ET.fromstring(svg)


def test_canvas_png_and_pdf_keep_scene_led_geometry_and_selectable_text(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Canvas raster and PDF paths must not fall back to legacy callout geometry."""
    spec = valid_spec()
    spec["visual_direction"]["style_variant"] = "canvas-story-map"
    handoff = summary.build_handoff(spec, 960, 540)
    monkeypatch.setattr(summary, "_reportlab_available", lambda: False)

    png = summary.render_png(handoff, tmp_path / "canvas.png").read_bytes()
    pdf_path = summary.render_pdf(handoff, tmp_path / "canvas.pdf")

    assert b"CANVAS scene-led; THREAD oracle-red; EVIDENCE" in png
    assert b"CANVAS scene-led; THREAD oracle-red; EVIDENCE" in pdf_path.read_bytes()
    assert b"(Identity route)" in pdf_path.read_bytes()
    assert b"(Scope 1)" in pdf_path.read_bytes()
    assert b" re S" not in pdf_path.read_bytes()
    if importlib.util.find_spec("pypdf") is None:
        return
    import pypdf
    extracted = "\n".join(page.extract_text() or "" for page in pypdf.PdfReader(pdf_path).pages)
    assert handoff["headline_zone"]["title"] in extracted
    assert handoff["clusters"][0]["title"] in extracted


def test_canvas_reportlab_pdf_uses_composed_preview_parity(tmp_path: Path) -> None:
    """Art-enabled Canvas PDF is one 16:9 composed image, not a divergent redraw."""
    pytest.importorskip("reportlab")
    pytest.importorskip("PIL")
    spec = valid_spec()
    spec["visual_direction"]["style_variant"] = "canvas-story-map"
    handoff = summary.build_handoff(spec, 1920, 1080)
    art = tmp_path / "support.png"
    art.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg=="))
    handoff["clusters"][0].update({"art_path": str(art), "art_root": str(tmp_path)})
    pdf = summary.render_pdf(handoff, tmp_path / "canvas.pdf")
    payload = pdf.read_bytes()
    pypdf = pytest.importorskip("pypdf")
    reader = pypdf.PdfReader(pdf)
    assert len(reader.pages) == 1
    box = reader.pages[0].mediabox
    assert abs(float(box.width) / float(box.height) - 16 / 9) < 0.01
    resources = reader.pages[0].get("/Resources", {})
    if hasattr(resources, "get_object"):
        resources = resources.get_object()
    xobjects = resources.get("/XObject", {})
    if hasattr(xobjects, "get_object"):
        xobjects = xobjects.get_object()
    images = [name for name, value in xobjects.items() if value.get_object().get("/Subtype") == "/Image"]
    assert len(images) == 1


def test_scene_prompts_forbid_critical_text_and_copied_branding() -> None:
    """Removing text-free constraints would make generated art unsafe to use."""
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)

    for cluster in handoff["clusters"]:
        prompt = cluster["scene_prompt"].lower()
        assert "no words" in prompt
        assert "copied conference branding" in prompt
        assert cluster["title"].lower() not in prompt


def test_standalone_outputs_share_visible_content(tmp_path: Path) -> None:
    """Removing deterministic PDF text would break cross-format operator access."""
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)
    outputs = summary.build_outputs(handoff, tmp_path, {"svg", "png", "pdf"})

    assert {path.suffix for path in outputs} == {".svg", ".png", ".pdf"}
    assert (tmp_path / "summary.svg").is_file()
    assert (tmp_path / "summary.png").is_file()
    assert (tmp_path / "summary.pdf").is_file()

    pypdf = pytest.importorskip("pypdf")
    extracted = "\n".join(page.extract_text() or "" for page in pypdf.PdfReader(tmp_path / "summary.pdf").pages)
    assert valid_spec()["title"] in extracted
    for anchor in valid_spec()["anchors"]:
        assert anchor["title"] in extracted


def test_supplied_art_is_embedded_or_the_requested_backend_fails_explicitly(tmp_path: Path) -> None:
    """Dropping supplied art in a format would create a false parity claim."""
    art = tmp_path / "support.png"
    art.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg=="))
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)
    handoff["clusters"][0]["art_path"] = str(art)

    svg = tmp_path / "summary.svg"
    summary.render_svg(handoff, svg)
    assert "data:image/png;base64," in svg.read_text(encoding="utf-8")

    for kind, renderer, dependency in (
        ("png", summary.render_png, "PIL"),
        ("pdf", summary.render_pdf, "reportlab"),
    ):
        output = tmp_path / f"summary.{kind}"
        if importlib.util.find_spec(dependency) is None:
            with pytest.raises(summary.SummaryError, match=dependency):
                renderer(handoff, output)
        else:
            renderer(handoff, output)
            assert output.is_file()


def test_renderers_emit_handoff_ribbon_and_cluster_callouts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Removing visual relationship marks would reduce the canvas to clusters."""
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)
    monkeypatch.setattr(summary, "_reportlab_available", lambda: False)
    outputs = summary.build_outputs(handoff, tmp_path, {"svg", "png", "pdf"})
    svg = (tmp_path / "summary.svg").read_text(encoding="utf-8")
    assert 'data-ribbon-kind="takeaway"' in svg
    for cluster in handoff["clusters"]:
        assert f'data-callout-shape="{cluster["callout_shape"]}"' in svg
    png = (tmp_path / "summary.png").read_bytes()
    assert b"RIBBON takeaway; CALLOUT" in png
    assert b"RIBBON takeaway" in (tmp_path / "summary.pdf").read_bytes()


def test_editable_story_map_outputs_validate_and_preserve_rich_style(tmp_path: Path) -> None:
    """Editable exports should keep the story-map semantics, not flatten to cards."""
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)
    outputs = summary.build_outputs(handoff, tmp_path, {"drawio", "excalidraw", "handoff"})

    assert {path.suffix for path in outputs} == {".drawio", ".excalidraw", ".json"}
    drawio_path = tmp_path / "summary.drawio"
    excalidraw_path = tmp_path / "summary.excalidraw"
    assert oci_diagram.validate_drawio(drawio_path) == []
    assert oci_diagram.validate_excalidraw(excalidraw_path) == []

    drawio_xml = drawio_path.read_text(encoding="utf-8")
    assert "sketch=1" in drawio_xml
    assert "oci.visual-summary.scene" in drawio_xml
    assert "oci.visual-summary.path" in drawio_xml

    excalidraw = excalidraw_path.read_text(encoding="utf-8")
    assert "\"preset\": \"oci-doodle\"" in excalidraw
    assert "\"doodleLevel\": \"rich\"" in excalidraw


def test_canvas_editable_outputs_use_scene_art_and_annotation_geometry(tmp_path: Path) -> None:
    """Canvas editable formats must not fall back to legacy shells and card bounds."""
    spec = valid_spec()
    spec["visual_direction"]["style_variant"] = "canvas-story-map"
    handoff = summary.build_handoff(spec, 1920, 1080)
    art = tmp_path / "scene.png"
    art.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR4nGP4////fwAJ+wP9KobjigAAAABJRU5ErkJggg=="))
    handoff["clusters"][0].update({"art_path": str(art), "art_root": str(tmp_path)})

    summary.build_outputs(handoff, tmp_path, {"drawio", "excalidraw"})

    drawio_xml = (tmp_path / "summary.drawio").read_text(encoding="utf-8")
    first = handoff["clusters"][0]
    assert oci_diagram.validate_drawio(tmp_path / "summary.drawio") == []
    assert "oci.visual-summary.canvas-scene" in drawio_xml
    assert "oci.visual-summary.canvas-thread" in drawio_xml
    assert 'source="canvas-callout-anchor-1"' in drawio_xml
    assert 'target="canvas-callout-anchor-2"' in drawio_xml
    assert "shape=cloud" not in drawio_xml
    assert f'x="{first["art_bounds"]["x"]}"' in drawio_xml
    assert f'y="{first["art_bounds"]["y"]}"' in drawio_xml

    excalidraw = json.loads((tmp_path / "summary.excalidraw").read_text(encoding="utf-8"))
    assert excalidraw["appState"]["visualStyle"]["variant"] == "canvas-story-map"
    image = next(element for element in excalidraw["elements"] if element.get("id") == f'image-{first["anchor_id"]}')
    title = next(element for element in excalidraw["elements"] if element.get("id") == f'title-{first["anchor_id"]}')
    assert image["x"] == first["art_bounds"]["x"]
    assert image["y"] == first["art_bounds"]["y"]
    assert title["x"] == first["text_bounds"]["x"]
    assert title["y"] == first["text_bounds"]["y"]
    assert not any(element.get("type") == "ellipse" and str(element.get("id", "")).startswith("scene-") for element in excalidraw["elements"])


def test_build_outputs_dispatches_pptx_and_docx_builders_with_public_handoff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spec = valid_spec()
    spec["visual_direction"]["style_variant"] = "canvas-story-map"
    handoff = summary.build_handoff(spec, 1920, 1080)
    commands: list[list[str]] = []

    monkeypatch.setenv("RUNTIME_NODE", "/runtime/node")
    monkeypatch.setenv("RUNTIME_NODE_MODULES", "/runtime/node_modules")
    monkeypatch.setenv("RUNTIME_BIN_DIR", "/runtime/bin")
    monkeypatch.setenv("RUNTIME_PYTHON", "/runtime/python")
    monkeypatch.setenv("PRESENTATIONS_SKILL_DIR", "/runtime/presentations")
    monkeypatch.setenv("DOCUMENTS_SKILL_DIR", "/runtime/documents")

    def fake_render_png(handoff_arg: dict, out: Path) -> Path:
        out.write_bytes(b"PNG")
        return out

    def fake_run(cmd: list[str], check: bool) -> None:
        assert check is True
        commands.append(cmd)
        handoff_path = Path(cmd[cmd.index("--handoff") + 1])
        public_handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
        assert "scene_prompt" not in json.dumps(public_handoff)
        assert "art_path" not in json.dumps(public_handoff)
        out_path = Path(cmd[cmd.index("--out") + 1])
        out_path.write_bytes(b"PPTX" if out_path.suffix == ".pptx" else b"DOCX")

    monkeypatch.setattr(summary, "render_png", fake_render_png)
    monkeypatch.setattr(summary.subprocess, "run", fake_run)

    outputs = summary.build_outputs(handoff, tmp_path, {"pptx", "docx"})

    assert {path.suffix for path in outputs} == {".pptx", ".docx"}
    assert (tmp_path / "summary.pptx").read_bytes() == b"PPTX"
    assert (tmp_path / "summary.docx").read_bytes() == b"DOCX"
    assert len(commands) == 2
    assert all("--handoff" in command and "--out" in command for command in commands)
    assert not (tmp_path / "summary.preview.png").exists()


def test_storyboard_office_outputs_embed_safe_icons_and_pass_preview_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assets_root = tmp_path / "assets"
    assets_root.mkdir()
    handoff, private_icons, _scene_colors, _icon_colors = _storyboard_asset_fixture(assets_root, 4, icon_count=2)
    handoff["concept"] = "illo-storyboard-sequence-v1"
    _five_section_storyboard(handoff)
    handoff["private_icon_resolution"] = private_icons

    commands: list[list[str]] = []
    expected_preview_count = len(summary._storyboard_physical_pages(handoff["pages"]))

    monkeypatch.setenv("RUNTIME_NODE", "/runtime/node")
    monkeypatch.setenv("RUNTIME_NODE_MODULES", "/runtime/node_modules")
    monkeypatch.setenv("RUNTIME_BIN_DIR", "/runtime/bin")
    monkeypatch.setenv("RUNTIME_PYTHON", "/runtime/python")
    monkeypatch.setenv("PRESENTATIONS_SKILL_DIR", "/runtime/presentations")
    monkeypatch.setenv("DOCUMENTS_SKILL_DIR", "/runtime/documents")

    original_run = summary.subprocess.run

    def fake_run(cmd: list[str], *args, **kwargs):
        if "--handoff" not in cmd:
            return original_run(cmd, *args, **kwargs)
        assert kwargs.get("check") is True
        commands.append(cmd)
        handoff_path = Path(cmd[cmd.index("--handoff") + 1])
        payload = json.loads(handoff_path.read_text(encoding="utf-8"))
        serialized = json.dumps(payload)
        assert "private_icon_resolution" not in serialized
        assert str(assets_root) not in serialized
        if Path(cmd[1]).name == "build_summary_pptx.mjs":
            scene_pages = [page for page in payload["pages"] if page.get("scenes")]
            assert scene_pages
            assert all(
                scene.get("reviewedScene", {}).get("data_url", "").startswith("data:image/png;base64,")
                and re.fullmatch(r"[a-f0-9]{64}", scene.get("reviewedScene", {}).get("sha256", ""))
                for page in scene_pages
                for scene in page["scenes"]
            )
            service_pages = [page for page in payload["pages"] if page.get("services")]
            assert service_pages
            assert all(
                service.get("serviceIcon", {}).get("data_url", "").startswith("data:image/svg+xml;base64,")
                and re.fullmatch(r"[a-f0-9]{64}", service.get("serviceIcon", {}).get("sha256", ""))
                for page in service_pages
                for service in page["services"]
            )
        if Path(cmd[1]).name == "build_summary_docx.py":
            assert "--preview-manifest" in cmd
            manifest_path = Path(cmd[cmd.index("--preview-manifest") + 1])
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert len(manifest) == expected_preview_count
            assert all(Path(item["path"]).is_file() for item in manifest)
            assert len({item["path"] for item in manifest}) == expected_preview_count
        out_path = Path(cmd[cmd.index("--out") + 1])
        out_path.write_bytes(b"PPTX" if out_path.suffix == ".pptx" else b"DOCX")
        return None

    monkeypatch.setattr(summary.subprocess, "run", fake_run)

    outputs = summary.build_outputs(handoff, tmp_path, {"pptx", "docx"})

    assert {path.suffix for path in outputs} == {".pptx", ".docx"}
    assert (tmp_path / "summary.pptx").read_bytes() == b"PPTX"
    assert (tmp_path / "summary.docx").read_bytes() == b"DOCX"
    assert len(commands) == 2


def test_generated_art_slots_are_text_free_and_explicitly_optional() -> None:
    """Generated-image hooks must stay subordinate to deterministic text."""
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)
    cluster = handoff["clusters"][0]

    assert cluster["art_direction"]["slot_mode"] == "supporting-art"
    assert cluster["art_direction"]["generated_image_allowed"] is True
    prompt = cluster["art_direction"]["scene_prompt"].lower()
    for forbidden in ("words", "letters", "numbers", "logos", "ui", "watermarks"):
        assert forbidden in prompt


def test_canonical_svg_is_accessible_story_map_not_a_pixel_fallback(tmp_path: Path) -> None:
    """The tracked/public visual must remain crisp, structured, and screen-reader usable."""
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)
    output = summary.render_svg(handoff, tmp_path / "summary.svg")
    svg = output.read_text(encoding="utf-8")

    assert "<title" in svg and "<desc" in svg
    assert "font-family=\"system-ui, -apple-system" in svg
    assert 'data-story-layer="journey"' in svg
    assert svg.count('data-story-layer="scene"') == 4
    assert svg.count('data-stage-marker=') == 4
    assert "data-doodle=" in svg
    assert "aria-labelledby=" in svg


def test_all_callout_variants_have_distinct_renderer_contracts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Collapsing a named callout to a plain line would erase its visual meaning."""
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)
    shapes = ("ribbon", "speech-tail", "torn-note", "bracket", "arrow-tab", "seal", "wave", "underline")
    template = handoff["clusters"][0]
    handoff["clusters"] = [dict(deepcopy(template), anchor_id=f"anchor-{index}", callout_shape=shape) for index, shape in enumerate(shapes, start=1)]
    monkeypatch.setattr(summary, "_reportlab_available", lambda: False)
    summary.build_outputs(handoff, tmp_path, {"svg", "png", "pdf"})

    svg = (tmp_path / "summary.svg").read_text(encoding="utf-8")
    for shape in shapes:
        assert f'data-callout-shape="{shape}"' in svg
        assert f"% CALLOUT {shape}".encode() in (tmp_path / "summary.pdf").read_bytes()
    assert b"CALLOUT ribbon,speech-tail,torn-note,bracket,arrow-tab,seal,wave,underline" in (tmp_path / "summary.png").read_bytes()


def test_pdf_prefers_reportlab_backend_when_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A ReportLab-capable runtime should not silently choose the fallback PDF."""
    handoff = summary.build_handoff(valid_spec(), 1920, 1080)
    selected: list[bool] = []

    def fake_reportlab(handoff_arg: dict, out: Path, art: list) -> Path:
        selected.append(not art)
        out.write_bytes(b"%PDF-1.4\n")
        return out

    monkeypatch.setattr(summary, "_reportlab_available", lambda: True)
    monkeypatch.setattr(summary, "_render_pdf_with_art", fake_reportlab)
    assert summary.render_pdf(handoff, tmp_path / "summary.pdf").is_file()
    assert selected == [True]


def test_pptx_builder_contract_is_artifact_tool_only() -> None:
    """PPTX summaries must keep essential text editable and source-traceable."""
    source = (SKILL / "scripts" / "build_summary_pptx.mjs").read_text(encoding="utf-8")
    assert "@oai/artifact-tool" in source
    assert "artifact_tool.mjs" in source
    assert "pathToFileURL" in source
    assert "python-pptx" not in source
    assert "[Sources]" in source
    assert "PresentationFile.importPptx" in source
    assert "slides.insert" in source
    assert "mark_artifact_operation_started" in source
    assert "canvas_layout" in source
    assert "art_bounds" in source
    assert "text_bounds" in source
    assert "canvas-story-map" in source


def test_docx_builder_contract_preserves_source_and_audits_privacy() -> None:
    """DOCX summaries need an accessible, scrubbed output path for any project."""
    source = (SKILL / "scripts" / "build_summary_docx.py").read_text(encoding="utf-8")
    assert "python-docx" in source
    assert "privacy_scrub.py" in source
    assert "a11y_audit.py" in source
    assert "render_docx.py" in source
    assert "mark_artifact_operation_started" in source
    assert "alt_text" in source
    assert "w:tblHeader" in source
    assert "canvas-story-map" in source
    assert "canvas_layout" in source


def test_docx_builder_rejects_symlinked_or_oversized_direct_inputs(tmp_path: Path) -> None:
    pytest.importorskip("docx")
    module_path = SKILL / "scripts" / "build_summary_docx.py"
    module_spec = importlib.util.spec_from_file_location("build_summary_docx_bounds", module_path)
    assert module_spec and module_spec.loader
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)
    target = tmp_path / "handoff.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "handoff-link.json"; link.symlink_to(target)
    with pytest.raises(ValueError, match="regular"):
        module._load_bounded_handoff(link)
    preview = tmp_path / "preview.png"; preview.write_bytes(b"not-a-png")
    with pytest.raises(ValueError, match="PNG"):
        module._validate_preview(preview)


def test_docx_builder_writes_accessible_canvas_scene_sections(tmp_path: Path) -> None:
    """Canvas DOCX output should expose scene order as readable text, not only a dense grid."""
    pytest.importorskip("docx")
    spec = valid_spec()
    spec["visual_direction"]["style_variant"] = "canvas-story-map"
    handoff = summary.build_handoff(spec, 1920, 1080)

    module_path = SKILL / "scripts" / "build_summary_docx.py"
    module_spec = importlib.util.spec_from_file_location("build_summary_docx", module_path)
    assert module_spec and module_spec.loader
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)

    document = module.Document()
    module._append_summary(document, handoff, preview=None)

    paragraph_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Scene path" in paragraph_text
    assert "Scene 1" in paragraph_text
    assert handoff["clusters"][0]["title"] in paragraph_text
    assert handoff["clusters"][0]["detail"] in paragraph_text


def test_docx_storyboard_exposes_ordered_scene_and_service_text(tmp_path: Path) -> None:
    pytest.importorskip("docx")
    handoff, _private_icons, _scene_colors, _icon_colors = _storyboard_asset_fixture(tmp_path, 4, icon_count=2)
    _five_section_storyboard(handoff)
    handoff["accessibility"] = {
        "alt_text": "Storyboard summary",
    }
    handoff["source_register"] = [{
        "title": "OCI Monitoring documentation",
        "url": "https://docs.oracle.com/en-us/iaas/Content/Monitoring/home.htm",
    }]

    module_path = SKILL / "scripts" / "build_summary_docx.py"
    module_spec = importlib.util.spec_from_file_location("build_summary_docx_storyboard", module_path)
    assert module_spec and module_spec.loader
    module = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(module)

    document = module.Document()
    preview = tmp_path / "storyboard-preview.png"
    preview.write_bytes(_solid_png((80, 120, 160)))
    module._append_summary(document, handoff, preview=None, preview_manifest=[{
        "role": "project-promise", "audience_role": "project-promise", "path": preview,
        "alt_text": "Project promise preview", "page_number": 1, "page_count": 1,
    }])

    paragraph_text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    assert "Project promise" in paragraph_text
    assert "OCI service map" in paragraph_text
    assert "OCI Service 1" in paragraph_text
    assert "exact-service" in paragraph_text
    assert "Oracle Source Alpha; Oracle Source Beta" in paragraph_text
    assert "Long description" in paragraph_text
    assert "At-a-glance visual summary" in paragraph_text
    assert any(rel.reltype.endswith("/hyperlink") and rel.target_ref.startswith("https://docs.oracle.com/") for rel in document.part.rels.values())
    drawings = document._element.xpath(".//wp:docPr")
    assert drawings and "Project promise" in drawings[0].get("descr", "")


def test_storyboard_at_a_glance_uses_the_incident_operational_sequence(tmp_path: Path) -> None:
    """Every rendered at-a-glance artifact uses the same operating contract."""
    handoff, private_icons, _scene_colors, _icon_colors = _storyboard_asset_fixture(tmp_path, 4, icon_count=2)
    _five_section_storyboard(handoff)
    out = tmp_path / "at-a-glance.svg"
    summary.render_storyboard_svg(handoff, out, private_icon_catalog=private_icons)
    svg = out.read_text(encoding="utf-8")
    assert "DETECT  →  CORRELATE  →  DIAGNOSE  →  ROUTE" in svg.replace("\u00a0", " ")
    assert "DETECT  →  DIAGNOSE  →  RESPOND  →  LEARN" not in svg


def test_public_stencil_fallbacks_keep_distinct_portable_service_glyphs() -> None:
    """Portable formats may not collapse supported OCI services to one icon."""
    records = [
        {"canonical_service_id": "oci.monitoring", "public_stencil_key": "monitoring"},
        {"canonical_service_id": "oci.logging", "public_stencil_key": "logging"},
        {"canonical_service_id": "oci.apm", "public_stencil_key": "apm"},
        {"canonical_service_id": "oci.service-connector-hub", "public_stencil_key": "service-connector-hub"},
    ]
    assert [summary._neutral_service_glyph_kind(record) for record in records] == [
        "monitoring", "logging", "apm", "service-connector-hub",
    ]

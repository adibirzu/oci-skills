"""Original synthetic OOXML fixtures for icon catalog tests."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
_DRAWING = "http://schemas.openxmlformats.org/drawingml/2006/main"
_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def build_icon_pack(
    path: Path,
    *,
    classification: str = "Oracle Restricted",
    entries: tuple[tuple[str, str], ...] = (("Autonomous Database", "database-svg"),),
) -> Path:
    """Write a minimal original package with labels, positions, rels and SVG media."""
    path.parent.mkdir(parents=True, exist_ok=True)
    shapes: list[str] = []
    relationships: list[str] = []
    for number, (label, svg_name) in enumerate(entries, start=1):
        x = 1_000_000 + (number - 1) * 2_500_000
        shapes.append(
            f'<p:pic><p:nvPicPr/><p:blipFill><a:blip r:embed="rId{number}"/></p:blipFill>'
            f'<p:spPr><a:xfrm><a:off x="{x}" y="1000000"/><a:ext cx="1000000" cy="1000000"/>'
            f'</a:xfrm></p:spPr></p:pic>'
        )
        shapes.append(
            f'<p:sp><p:nvSpPr/><p:spPr><a:xfrm><a:off x="{x}" y="2300000"/>'
            f'<a:ext cx="1000000" cy="350000"/></a:xfrm></p:spPr><p:txBody><a:p><a:r>'
            f'<a:t>{escape(label)}</a:t></a:r></a:p></p:txBody></p:sp>'
        )
        relationships.append(
            f'<Relationship Id="rId{number}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" '
            f'Target="../media/{svg_name}.svg"/>'
        )
    slide = (
        f'<p:sld xmlns:p="{_NS}" xmlns:a="{_DRAWING}" xmlns:r="{_REL}"><p:cSld>'
        f'<p:spTree>{"".join(shapes)}</p:spTree></p:cSld></p:sld>'
    )
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        archive.writestr("docProps/core.xml", f"<coreProperties><classification>{classification}</classification></coreProperties>")
        archive.writestr("ppt/slides/slide1.xml", slide)
        archive.writestr(
            "ppt/slides/_rels/slide1.xml.rels",
            f'<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">{"".join(relationships)}</Relationships>',
        )
        for _, svg_name in entries:
            archive.writestr(f"ppt/media/{svg_name}.svg", f'<svg xmlns="http://www.w3.org/2000/svg"><title>{escape(svg_name)}</title></svg>')
    return path


def rewrite_archive(path: Path, updates: dict[str, bytes | str], *, remove: tuple[str, ...] = ()) -> Path:
    """Replace fixture members without accidental duplicate ZIP entries."""
    with ZipFile(path) as archive:
        entries = {item.filename: archive.read(item.filename) for item in archive.infolist() if item.filename not in remove}
    entries.update(updates)
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, contents in entries.items():
            archive.writestr(name, contents)
    return path


def build_asymmetric_ambiguous_pack(path: Path) -> Path:
    """Two pictures share one label while the second also has another candidate."""
    build_icon_pack(path, entries=(("Shared", "one"), ("Second", "two")))
    slide = (
        f'<p:sld xmlns:p="{_NS}" xmlns:a="{_DRAWING}" xmlns:r="{_REL}"><p:cSld><p:spTree>'
        '<p:pic><p:blipFill><a:blip r:embed="rId1"/></p:blipFill><p:spPr><a:xfrm><a:off x="1000000" y="1000000"/><a:ext cx="1000000" cy="1000000"/></a:xfrm></p:spPr></p:pic>'
        '<p:pic><p:blipFill><a:blip r:embed="rId2"/></p:blipFill><p:spPr><a:xfrm><a:off x="1300000" y="1000000"/><a:ext cx="1000000" cy="1000000"/></a:xfrm></p:spPr></p:pic>'
        '<p:sp><p:spPr><a:xfrm><a:off x="1150000" y="2200000"/><a:ext cx="1000000" cy="300000"/></a:xfrm></p:spPr><p:txBody><a:p><a:r><a:t>Shared</a:t></a:r></a:p></p:txBody></p:sp>'
        '<p:sp><p:spPr><a:xfrm><a:off x="1300000" y="2500000"/><a:ext cx="1000000" cy="300000"/></a:xfrm></p:spPr><p:txBody><a:p><a:r><a:t>Second</a:t></a:r></a:p></p:txBody></p:sp>'
        "</p:spTree></p:cSld></p:sld>"
    )
    return rewrite_archive(path, {"ppt/slides/slide1.xml": slide})


def mark_archive_encrypted(path: Path) -> Path:
    """Set ZIP general-purpose encryption flags without adding encrypted content."""
    data = bytearray(path.read_bytes())
    for signature, offset in ((b"PK\x03\x04", 6), (b"PK\x01\x02", 8)):
        start = 0
        while (position := data.find(signature, start)) >= 0:
            flag = int.from_bytes(data[position + offset:position + offset + 2], "little") | 1
            data[position + offset:position + offset + 2] = flag.to_bytes(2, "little")
            start = position + len(signature)
    path.write_bytes(data)
    return path


def build_malicious_icon_pack(path: Path) -> Path:
    """Write a fixture that combines traversal and an external relationship."""
    build_icon_pack(path)
    with ZipFile(path) as archive:
        entries = {
            item.filename: archive.read(item.filename)
            for item in archive.infolist()
        }
    entries["ppt/slides/_rels/slide1.xml.rels"] = (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="x" Target="https://example.test/icon.svg" TargetMode="External"/>'
        "</Relationships>"
    )
    entries["../escape.svg"] = "bad"
    with ZipFile(path, "w", ZIP_DEFLATED) as archive:
        for name, contents in entries.items():
            archive.writestr(name, contents)
    return path

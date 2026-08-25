from __future__ import annotations

import os
import stat
import sys
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "skills" / "oci-visual-summary" / "scripts"))

import axm_icons
from helpers.axm_fixture import build_asymmetric_ambiguous_pack, build_icon_pack, build_malicious_icon_pack, mark_archive_encrypted, rewrite_archive


@pytest.fixture
def accepted_storyboard() -> dict[str, object]:
    """Accepted context supplies both canonical IDs and native display names."""
    return {
        "units": [{
            "id": "service-map",
            "alt_text": "A service map with grounded OCI services.",
            "service_ids": ["Autonomous Database", "Data Safe", "Unknown Service"],
            "service_context": [
                {"canonical_service_id": "oci.autonomous-database", "display_name": "Autonomous Database"},
                {"canonical_service_id": "oci.data-safe", "display_name": "Data Safe"},
                {"canonical_service_id": "oci.unknown", "display_name": "Unknown Service"},
            ],
        }],
    }


def catalog_with(*labels: str) -> dict[str, object]:
    return {
        "classification": "internal-only",
        "icons": [
            {"label": label, "bounds": [index, 2, 3, 4], "asset_id": f"asset-{index}"}
            for index, label in enumerate(labels, start=1)
        ],
    }


def restricted_catalog() -> dict[str, object]:
    return {"classification": "internal-only"}


def resolution(records: list[dict[str, object]], canonical_service_id: str) -> dict[str, object]:
    return next(record for record in records if record["canonical_service_id"] == canonical_service_id)


def test_resolver_prefers_exact_then_explicit_conceptual_mapping(accepted_storyboard: dict[str, object]) -> None:
    """A wrong catalog label must not override a native exact service match."""
    resolved = axm_icons.resolve_service_icons(
        accepted_storyboard,
        catalog_with("Autonomous Database", "Data Security"),
        {
            "oci.data-safe": {
                "canonical_service_id": "oci.data-safe",
                "label": "Data Security",
                "mapping_type": "conceptual-redwood",
                "rationale": "The approved catalog has no native Data Safe icon.",
            },
        },
        output_classification="internal",
    )
    assert resolution(resolved, "oci.autonomous-database")["mapping_type"] == "exact-service"
    assert resolution(resolved, "oci.data-safe")["mapping_type"] == "conceptual-redwood"


def test_resolver_returns_portable_none_for_unknown_or_ambiguous_matches(accepted_storyboard: dict[str, object]) -> None:
    """Duplicate labels and absent labels cannot silently select a private icon."""
    resolved = axm_icons.resolve_service_icons(
        accepted_storyboard, catalog_with("Autonomous Database", "Autonomous Database"), None,
        output_classification="internal",
    )
    for canonical_service_id in ("oci.autonomous-database", "oci.unknown"):
        record = resolution(resolved, canonical_service_id)
        assert record["mapping_type"] == "none"
        assert set(record) == {
            "unit_id", "canonical_service_id", "display_name", "mapping_type", "alt_text", "bounds",
            "private_catalog_asset_id",
        }
        assert record["private_catalog_asset_id"] is None


def test_resolver_rejects_incomplete_conceptual_override(accepted_storyboard: dict[str, object]) -> None:
    """An override without its keyed ID and rationale cannot justify a conceptual icon."""
    with pytest.raises(axm_icons.IconPackError, match="canonical_service_id"):
        axm_icons.resolve_service_icons(
            accepted_storyboard,
            catalog_with("Data Security"),
            {"oci.data-safe": {"label": "Data Security", "mapping_type": "conceptual-redwood"}},
            output_classification="internal",
        )


def test_public_output_rejects_internal_only_icons_before_catalog_asset_access(accepted_storyboard: dict[str, object]) -> None:
    """The publication gate must reject a restricted catalog before resolving assets."""
    with pytest.raises(axm_icons.IconPackError, match="internal-only"):
        axm_icons.resolve_service_icons(
            accepted_storyboard, restricted_catalog(), None, output_classification="public",
        )


def test_public_output_uses_supported_official_stencil_before_neutral_fallback(accepted_storyboard: dict[str, object]) -> None:
    catalog = axm_icons.official_public_stencil_catalog()
    resolved = axm_icons.resolve_service_icons(accepted_storyboard, catalog, None, output_classification="public")
    apm = resolution(resolved, "oci.autonomous-database")
    unknown = resolution(resolved, "oci.unknown")
    assert catalog["provenance"] == "official-public-oci-stencil-registry"
    assert catalog["registry_path"] == "skills/oci-diagramming/scripts/oci_diagram.py"
    assert apm["mapping_type"] == "official-public-stencil"
    assert apm["public_stencil_key"] == "database"
    assert unknown["mapping_type"] == "none"


@pytest.mark.parametrize("style", [
    'shape=mxgraph.oci.monitoring;image=https://example.test/x;',
    'shape=mxgraph.oci.monitoring;foo="/><mxCell;',
    'shape=mxgraph.oci.monitoring;file:///tmp/x;',
])
def test_public_stencil_style_rejects_injection_grammar(style: str) -> None:
    with pytest.raises(axm_icons.IconPackError, match="style"):
        axm_icons.validate_public_stencil_style(style)


def test_catalog_pairs_label_and_svg_and_preserves_restricted_classification(tmp_path: Path) -> None:
    """A correct local pair must produce a private, traceable icon record."""
    source = build_icon_pack(tmp_path / "icons.potx")
    catalog = axm_icons.catalog_icon_pack(source, tmp_path / "out")
    assert catalog["classification"] == "internal-only"
    assert catalog["icons"][0]["label"] == "Autonomous Database"
    assert catalog["icons"][0]["media_digest"]
    assert catalog["icons"][0]["slide_number"] == 1


def test_catalog_rejects_traversal_external_relationship_and_oversized_package(tmp_path: Path) -> None:
    """An unsafe archive must fail before it can produce a cache entry."""
    source = build_malicious_icon_pack(tmp_path / "bad.potx")
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(source, tmp_path / "out")


def test_catalog_rejects_external_relationship_without_traversal(tmp_path: Path) -> None:
    """External relationships are forbidden even if all ZIP member names are safe."""
    source = build_icon_pack(tmp_path / "external.potx")
    rewrite_archive(source, {"ppt/slides/_rels/slide1.xml.rels": (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="https://example.test/x.svg" TargetMode="External"/>'
        "</Relationships>")})
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(source, tmp_path / "out")


def test_catalog_rejects_duplicate_and_encrypted_members(tmp_path: Path) -> None:
    """ZIP identity and encryption flags are rejected before any private output."""
    duplicate = build_icon_pack(tmp_path / "duplicate.potx")
    with pytest.warns(UserWarning, match="Duplicate name"):
        with ZipFile(duplicate, "a", ZIP_DEFLATED) as archive:
            archive.writestr("ppt/media/database-svg.svg", "<svg/>")
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(duplicate, tmp_path / "out")
    encrypted = mark_archive_encrypted(build_icon_pack(tmp_path / "encrypted.potx"))
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(encrypted, tmp_path / "out2")


def test_xml_rejects_utf16_dtd_before_elementtree_expansion() -> None:
    payload = '<!DOCTYPE x [<!ENTITY y "boom">]><x>&y;</x>'.encode("utf-16")
    with pytest.raises(axm_icons.IconPackError, match="unsafe"):
        axm_icons._xml(payload, "slide")


def test_catalog_rejects_high_member_archive_before_reading_parts(tmp_path: Path) -> None:
    source = tmp_path / "many-members.potx"
    with ZipFile(source, "w", ZIP_DEFLATED) as archive:
        for index in range(axm_icons.MAX_MEMBERS + 1):
            archive.writestr(f"ppt/media/icon-{index}.bin", b"x")
    with pytest.raises(axm_icons.IconPackError, match="too many members"):
        axm_icons.catalog_icon_pack(source, tmp_path / "out")


def test_catalog_rejects_unknown_slide_relationship_type(tmp_path: Path) -> None:
    """Only image plus explicitly known local non-image relationship types are valid."""
    source = build_icon_pack(tmp_path / "rel-type.potx")
    rewrite_archive(source, {"ppt/slides/_rels/slide1.xml.rels": (
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" Type="urn:untrusted" Target="../media/database-svg.svg"/>'
        "</Relationships>")})
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(source, tmp_path / "out")


def test_catalog_omits_asymmetric_bipartite_ambiguity(tmp_path: Path) -> None:
    """A label shared by two pictures makes every adjacent cell ambiguous."""
    source = build_asymmetric_ambiguous_pack(tmp_path / "ambiguous.potx")
    catalog = axm_icons.catalog_icon_pack(source, tmp_path / "out")
    assert catalog["icons"] == []
    assert catalog["warnings"] == ["slide 1: ambiguous icon cell omitted"]


def test_catalog_accepts_standard_slide_layout_relationship(tmp_path: Path) -> None:
    """A normal internal slideLayout relation is irrelevant to image pairing."""
    source = build_icon_pack(tmp_path / "layout.potx")
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="../media/database-svg.svg"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" Target="../slideLayouts/slideLayout1.xml"/>'
            "</Relationships>")
    rewrite_archive(source, {"ppt/slides/_rels/slide1.xml.rels": rels})
    assert axm_icons.catalog_icon_pack(source, tmp_path / "out")["icons"]


@pytest.mark.parametrize("name", ["../escape.svg", "/absolute.svg", "ppt\\media\\escape.svg"])
def test_catalog_rejects_unsafe_member_spellings(tmp_path: Path, name: str) -> None:
    """Archive path normalization must fail closed for every unsafe spelling."""
    source = build_icon_pack(tmp_path / "bad.potx")
    rewrite_archive(source, {name: "x"})
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(source, tmp_path / "out")


def test_catalog_rejects_symlink_source_and_destination(tmp_path: Path) -> None:
    """Following either source or private-root links could escape the boundary."""
    source = build_icon_pack(tmp_path / "icons.potx")
    source_link = tmp_path / "source-link.potx"
    source_link.symlink_to(source)
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(source_link, tmp_path / "out")
    destination = tmp_path / "out"
    destination.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(source, destination)


def test_catalog_rejects_symlink_ancestor_and_prepositioned_cache_entry(tmp_path: Path) -> None:
    """Descriptor traversal must not follow an ancestor link or overwrite a target."""
    source = build_icon_pack(tmp_path / "icons.potx")
    (tmp_path / "real").mkdir()
    (tmp_path / "linked").symlink_to(tmp_path / "real", target_is_directory=True)
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(source, tmp_path / "linked" / "out")
    axm_icons.catalog_icon_pack(source, tmp_path / "out")
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(source, tmp_path / "out")


def test_catalog_fails_closed_when_destination_appears_at_rename_boundary(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A concurrent empty destination must never be replaced by publication."""
    source = build_icon_pack(tmp_path / "race.potx")
    digest = __import__("hashlib").sha256(source.read_bytes()).hexdigest()
    original_publish = axm_icons._publish_no_replace

    def create_competing_destination(cache_fd, temporary, destination):
        os.mkdir(digest, dir_fd=cache_fd)
        return original_publish(cache_fd, temporary, destination)

    monkeypatch.setattr(axm_icons, "_publish_no_replace", create_competing_destination)
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(source, tmp_path / "out")
    assert (tmp_path / "out" / ".visual-summary-private" / "icon-cache" / digest).is_dir()


def test_catalog_removes_exact_pending_directory_when_publish_fails_after_temp_fd_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = build_icon_pack(tmp_path / "pending.potx")

    def fail_publish(_cache_fd, _temp_name, _destination):
        raise axm_icons.IconPackError("injected publish failure")

    monkeypatch.setattr(axm_icons, "_publish_no_replace", fail_publish)
    with pytest.raises(axm_icons.IconPackError, match="injected publish failure"):
        axm_icons.catalog_icon_pack(source, tmp_path / "out")
    cache = tmp_path / "out" / ".visual-summary-private" / "icon-cache"
    assert not list(cache.glob(".pending-*"))


def test_catalog_counts_all_slide_relationships_against_the_bound(tmp_path: Path) -> None:
    source = build_icon_pack(tmp_path / "many-rels.potx")
    relationship = (
        '<Relationship Id="rId{0}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slideLayout" '
        'Target="../slideLayouts/slideLayout1.xml"/>'
    )
    rels = ('<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            + "".join(relationship.format(index) for index in range(axm_icons.MAX_RELATIONSHIPS + 1))
            + "</Relationships>")
    rewrite_archive(source, {"ppt/slides/_rels/slide1.xml.rels": rels})
    with pytest.raises(axm_icons.IconPackError, match="too many relationships"):
        axm_icons.catalog_icon_pack(source, tmp_path / "out")


def test_catalog_rejects_media_larger_than_two_mebibytes(tmp_path: Path) -> None:
    """A large selected media part must be rejected, not cached."""
    source = build_icon_pack(tmp_path / "large.potx")
    with ZipFile(source, "a", ZIP_DEFLATED) as archive:
        archive.writestr("ppt/media/unreferenced-large.svg", b"x" * (2 * 1024 * 1024 + 1))
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(source, tmp_path / "out")


def test_catalog_rejects_oversized_archive_member(tmp_path: Path) -> None:
    """The generic archive-member limit applies before media selection."""
    source = build_icon_pack(tmp_path / "archive-limit.potx")
    rewrite_archive(source, {"ppt/notes/large.bin": b"x" * (axm_icons.MAX_MEMBER_UNCOMPRESSED_BYTES + 1)})
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(source, tmp_path / "out")


def test_catalog_rejects_svg_count_limit_and_noncanonical_slide_name(tmp_path: Path) -> None:
    """Candidate-count and canonical logical-slide checks happen before extraction."""
    source = build_icon_pack(tmp_path / "count.potx")
    rewrite_archive(source, {f"ppt/media/x{index}.svg": "<svg/>" for index in range(1000)})
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(source, tmp_path / "out")
    source = build_icon_pack(tmp_path / "canonical.potx")
    rewrite_archive(source, {"ppt/slides/slide01.xml": "<x/>"})
    with pytest.raises(axm_icons.IconPackError):
        axm_icons.catalog_icon_pack(source, tmp_path / "out2")


def test_catalog_uses_snapshot_when_path_changes_after_the_single_read(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Changing the pathname after snapshotting cannot change parsed/extracted bytes."""
    source = build_icon_pack(tmp_path / "snapshot.potx")
    original = axm_icons._load_snapshot

    def mutate_after_snapshot(data: bytes):
        source.write_bytes(b"not a zip")
        return original(data)

    monkeypatch.setattr(axm_icons, "_load_snapshot", mutate_after_snapshot)
    assert axm_icons.catalog_icon_pack(source, tmp_path / "out")["icons"][0]["label"] == "Autonomous Database"


def test_counts_only_inspection_writes_nothing(tmp_path: Path) -> None:
    """Inspection operates only on an immutable input snapshot and creates no cache."""
    source = build_icon_pack(tmp_path / "inspect.potx")
    assert axm_icons._inspect(source) == {"classification": "internal-only", "slides": 1, "svg_media": 1}
    assert not (tmp_path / ".visual-summary-private").exists()


def test_write_private_icon_catalog_uses_canonical_private_cache_with_private_modes(tmp_path: Path) -> None:
    """Catalog writes must stay under the private cache and not leak the source path."""
    source = build_icon_pack(tmp_path / "icons.potx")
    destination = axm_icons.write_private_icon_catalog(source, tmp_path / "out")
    assert destination.is_file()
    assert stat.S_IMODE(destination.stat().st_mode) == 0o600
    text = destination.read_text(encoding="utf-8")
    assert str(source) not in text
    assert "icon-cache" in str(destination.relative_to(tmp_path / "out"))
    assert not os.path.islink(destination)
    media = next(destination.parent.glob("*.svg"))
    assert stat.S_IMODE(media.stat().st_mode) == 0o600

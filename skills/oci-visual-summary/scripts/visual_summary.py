"""Portable OCI visual-summary contract, handoff, and local renderers."""

from __future__ import annotations

import argparse
import base64
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
from html import escape
import ipaddress
import io
import json
from math import cos, sin
import os
import re
import shutil
import stat
import struct
import subprocess
import tempfile
import zlib
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from xml.etree import ElementTree as ET

import storyboard


class SummaryError(ValueError):
    """Raised when a visual-summary specification violates its contract."""


class _OptionalAssetBackendUnavailable(RuntimeError):
    """A post-validation decoder/converter is absent for one otherwise safe asset."""


class _StoryboardHandoff(dict[str, Any]):
    """Dict-compatible portable handoff with in-process-only scene receipts."""

    __slots__ = ("_private_scene_paths", "_private_scene_receipts")

    def __init__(self, public: dict[str, Any], private_scene_paths: dict[str, str], private_scene_receipts: dict[str, dict[str, Any]]) -> None:
        super().__init__(public)
        self._private_scene_paths = private_scene_paths
        self._private_scene_receipts = private_scene_receipts


@dataclass(frozen=True)
class DomainProfile:
    """The visual vocabulary that makes a story map domain-specific."""

    name: str
    metaphors: tuple[str, ...]
    primary_accent: str
    secondary_accent: str
    preferred_archetypes: tuple[str, ...]
    doodles: tuple[str, ...]


DOMAIN_PROFILES = {
    "iam": DomainProfile("iam", ("gate", "scope", "verified path"), "#C74634", "#E6B9AE", ("journey", "control-map"), ("key", "seal")),
    "networking": DomainProfile("networking", ("route", "bridge", "boundary"), "#2F7FA3", "#9FD5E1", ("journey", "layered-system"), ("junction", "packet")),
    "storage": DomainProfile("storage", ("shelf", "layer", "recovery"), "#B56A1F", "#E5C48A", ("lifecycle", "before-after"), ("snapshot", "archive")),
    "security": DomainProfile("security", ("checkpoint", "evidence trail", "shield"), "#C74634", "#E8A59A", ("control-map", "lessons"), ("warning", "evidence")),
    "observability": DomainProfile("observability", ("signal", "lens", "response loop"), "#6C5AA7", "#79AAA6", ("lifecycle", "hub-spoke"), ("trace", "pulse")),
    "database": DomainProfile("database", ("record", "replica", "recovery"), "#345995", "#8FAAD0", ("lifecycle", "layered-system"), ("query", "backup")),
    "ai": DomainProfile("ai", ("evaluation", "model loop", "guardrail"), "#7A4FA3", "#D76A73", ("lifecycle", "control-map"), ("spark", "test")),
    "data-platform": DomainProfile("data-platform", ("flow", "transformation", "catalog"), "#287E7A", "#75B9C1", ("journey", "layered-system"), ("stream", "catalog")),
    "multicloud": DomainProfile("multicloud", ("bridge", "paired boundary", "shared control"), "#497A79", "#9B8CB7", ("journey", "layered-system"), ("bridge", "compass")),
    "project": DomainProfile("project", ("journey", "milestone", "decision map"), "#C74634", "#6C5AA7", ("journey", "hub-spoke"), ("flag", "checkpoint")),
}

_DOMAIN_ALIASES = {"analytics": "data-platform", "mixed": "project"}
_ARCHETYPES = frozenset(
    {"journey", "lifecycle", "hub-spoke", "control-map", "lessons", "layered-system", "before-after"}
)
_TEXT_BUDGETS = {
    "headline": 70,
    "takeaway": 140,
    "anchor_title": 32,
    "anchor_detail": 110,
    "service_line": 70,
    "footer_evidence": 90,
}
# Public SVGs must render crisply in Git hosts and accessibility tooling.  A
# familiar system UI stack wins over a fragile local handwriting font; the
# hand-drawn character comes from the composition, ribbons, and line work.
_SVG_FONT_STACK = "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif"
_LOCAL_ART_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".webp"})
_MAX_LOCAL_ART_BYTES = 10 * 1024 * 1024
_MAX_EMBEDDED_ART_BYTES = 1024 * 1024
_MAX_LOCAL_ART_PIXELS = 16_000_000
_ART_MANIFEST_KEYS = frozenset({"schema_version", "assets"})
_ART_ASSET_KEYS = frozenset({"anchor_id", "path", "source_type", "rights", "generator", "alt_text"})


_OCI_IDENTIFIER = re.compile(r"\bocid1\.[a-z0-9._-]+", re.IGNORECASE)
_PRIVATE_KEY = re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----", re.IGNORECASE)
_CREDENTIAL_MARKER = re.compile(
    r"\b(?:password|passwd|secret|api[_ -]?key|auth[_ -]?token|access[_ -]?key)\b\s*(?:=|:)|\bBearer\s+[A-Za-z0-9._~+/=-]+",
    re.IGNORECASE,
)
_USER_HOME_PATH = re.compile(r"(?:/Users|/home)/[^/\s]+|[A-Za-z]:\\Users\\[^\\\s]+", re.IGNORECASE)
_EMAIL_ADDRESS = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_IPV4_CANDIDATE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_INDEX_URL = re.compile(r"<(?P<url>https://(?:docs\.)?oracle\.com/[^>\s]+)>")
_OCI_DOMAINS = frozenset(DOMAIN_PROFILES) - {"project"}


def _strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _strings(child)


def _string_paths(value: Any, path: str = "$"):
    """Yield serialized strings with their stable field paths."""
    if isinstance(value, str):
        yield path, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from _string_paths(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _string_paths(child, f"{path}[{index}]")


def _is_rfc1918(value: str) -> bool:
    """Return whether an IPv4 literal belongs to an RFC1918 private range."""
    try:
        address = ipaddress.IPv4Address(value)
    except ipaddress.AddressValueError:
        return False
    return any(address in network for network in (
        ipaddress.IPv4Network("10.0.0.0/8"),
        ipaddress.IPv4Network("172.16.0.0/12"),
        ipaddress.IPv4Network("192.168.0.0/16"),
    ))


def privacy_findings(spec: dict[str, Any]) -> list[str]:
    """Return explicit, best-effort sensitive-content findings for serialized data.

    This checks visible summary fields plus any renderer or OOXML handoff fields
    supplied in *spec*.  It intentionally cannot prove that arbitrary secrets,
    images, encrypted payloads, or binary attachments are absent.
    """
    findings: list[str] = []
    for path, value in _string_paths(spec):
        if _OCI_IDENTIFIER.search(value):
            findings.append(f"OCI identifier at {path}")
        if any(_is_rfc1918(candidate.group()) for candidate in _IPV4_CANDIDATE.finditer(value)):
            findings.append(f"RFC1918 IPv4 address at {path}")
        if _PRIVATE_KEY.search(value):
            findings.append(f"private-key marker at {path}")
        if _CREDENTIAL_MARKER.search(value):
            findings.append(f"credential marker at {path}")
        if _USER_HOME_PATH.search(value):
            findings.append(f"user-home path at {path}")
        if _EMAIL_ADDRESS.search(value):
            findings.append(f"email address at {path}")
    return findings


def _source_identifiers(source: dict[str, Any]) -> tuple[str, ...]:
    """Return every canonical URL and sanitized local-path ID in a ledger entry."""
    return tuple(
        value
        for field in ("url", "local_source")
        if isinstance((value := source.get(field)), str) and value
    )


def _approved_oracle_urls() -> frozenset[str]:
    """Read the tracked, offline Oracle documentation allowlist."""
    index_path = Path(__file__).resolve().parents[3] / "references" / "oracle-docs.md"
    try:
        index_text = index_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SummaryError(f"unable to read Oracle documentation index: {exc}") from exc
    return frozenset(match.group("url") for match in _INDEX_URL.finditer(index_text))


def _is_approved_oracle_public_url(url: str, approved_urls: frozenset[str]) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "https" and parsed.hostname in {"docs.oracle.com", "oracle.com"} and url in approved_urls


def validate_sources(spec: dict[str, Any]) -> list[str]:
    """Return source-ledger contract errors without mutating *spec*.

    Anchor ``source_ids`` canonically reference the ledger source URL or
    ``local_source`` path. ``claim_ids`` remains an optional, independent
    compatibility field for claim-level coverage from schema v1.
    """
    errors: list[str] = []
    sources = spec.get("sources")
    if not isinstance(sources, list):
        return ["sources must be a list"]

    source_ids: set[str] = set()
    public_eligible = spec.get("privacy", {}).get("public_eligible") is True
    domain = str(spec.get("domain", ""))
    requires_oci_public_sources = domain in _OCI_DOMAINS
    approved_urls: frozenset[str] | None = None
    for index, source in enumerate(sources, start=1):
        label = f"source {index}"
        if not isinstance(source, dict):
            errors.append(f"{label} must be an object")
            continue
        classification = source.get("classification")
        if not isinstance(classification, str) or not classification:
            errors.append(f"{label} classification is required")
        identifiers = _source_identifiers(source)
        if not identifiers:
            errors.append(f"{label} must declare a URL or local_source")
        else:
            source_ids.update(identifiers)

        if not public_eligible:
            continue
        if classification != "public":
            errors.append(f"{label} is not public eligible (classification: {classification!r})")
        url = source.get("url")
        if requires_oci_public_sources:
            if not isinstance(url, str):
                errors.append(f"{label} for OCI content must use an approved Oracle public URL")
            else:
                if approved_urls is None:
                    approved_urls = _approved_oracle_urls()
                if not _is_approved_oracle_public_url(url, approved_urls):
                    parsed = urlparse(url)
                    if parsed.hostname not in {"docs.oracle.com", "oracle.com"}:
                        errors.append(f"{label} must use an approved Oracle public URL")
                    else:
                        errors.append(f"{label} URL is not registered in references/oracle-docs.md")
        elif isinstance(url, str) and urlparse(url).hostname in {"docs.oracle.com", "oracle.com"}:
            if approved_urls is None:
                approved_urls = _approved_oracle_urls()
            if not _is_approved_oracle_public_url(url, approved_urls):
                errors.append(f"{label} URL is not registered in references/oracle-docs.md")

    anchors = spec.get("anchors")
    if not isinstance(anchors, list):
        return errors + ["anchors must be a list"]
    for index, anchor in enumerate(anchors, start=1):
        label = f"anchor {index}"
        if not isinstance(anchor, dict):
            errors.append(f"{label} must be an object")
            continue
        anchor_source_ids = anchor.get("source_ids")
        if not isinstance(anchor_source_ids, list) or not anchor_source_ids or not all(
            isinstance(source_id, str) and source_id for source_id in anchor_source_ids
        ):
            errors.append(f"{label} source_ids must contain at least one source ID")
            continue
        for source_id in anchor_source_ids:
            if source_id not in source_ids:
                errors.append(f"{label} source_id {source_id!r} does not resolve in the source ledger")
    return errors


def assert_publishable(spec: dict[str, Any]) -> None:
    """Fail closed unless source, classification, and privacy gates permit public use."""
    if spec.get("privacy", {}).get("public_eligible") is not True:
        raise SummaryError("summary is not public eligible")
    errors = validate_sources(spec)
    if errors:
        raise SummaryError("source validation failed: " + "; ".join(errors))
    findings = privacy_findings(spec)
    if findings:
        raise SummaryError("privacy findings block public eligibility: " + "; ".join(findings))


def _validate_schema_v1_fallback(spec: dict[str, Any], schema: dict[str, Any]) -> None:
    """Dependency-free recursive validator for the complete bundled schema subset.

    It intentionally mirrors every keyword used by the shipped schema, rather
    than maintaining a second, lossy hand-written contract.
    """
    def resolve(rule: dict[str, Any]) -> dict[str, Any]:
        ref = rule.get("$ref")
        if not ref:
            return rule
        if not ref.startswith("#/"):
            raise SummaryError(f"unsupported schema reference {ref}")
        target: Any = schema
        for part in ref[2:].split("/"):
            target = target[part]
        return target

    def fail(path: str, message: str) -> None:
        raise SummaryError(f"{path}: {message}")

    def check(value: Any, rule: dict[str, Any], path: str) -> None:
        rule = resolve(rule)
        if "const" in rule and value != rule["const"]:
            fail(path, f"must equal {rule['const']!r}")
        if "enum" in rule and value not in rule["enum"]:
            fail(path, "is not an allowed value")
        if "anyOf" in rule:
            errors: list[str] = []
            for option in rule["anyOf"]:
                try:
                    check(value, option, path)
                    break
                except SummaryError as exc:
                    errors.append(str(exc))
            else:
                fail(path, "does not satisfy any allowed schema variant")
        kind = rule.get("type")
        type_ok = {
            "object": lambda: isinstance(value, dict),
            "array": lambda: isinstance(value, list),
            "string": lambda: isinstance(value, str),
            "boolean": lambda: isinstance(value, bool),
            "integer": lambda: isinstance(value, int) and not isinstance(value, bool),
            "number": lambda: isinstance(value, (int, float)) and not isinstance(value, bool),
        }
        if kind and (kind not in type_ok or not type_ok[kind]()):
            fail(path, f"must be a {kind}")
        if isinstance(value, str):
            if len(value) < rule.get("minLength", 0): fail(path, "is shorter than minLength")
            if rule.get("format") == "uri":
                parsed = urlparse(value)
                if not parsed.scheme or not parsed.netloc: fail(path, "must be a URI")
        if isinstance(value, list):
            minimum = rule.get("minItems", 0)
            maximum = rule.get("maxItems")
            if len(value) < minimum or (maximum is not None and len(value) > maximum):
                if path == "$.anchors" and minimum == 4 and maximum == 8:
                    fail(path, "must contain 4..8 items")
                fail(path, "has too few items" if len(value) < minimum else "has too many items")
            if isinstance(rule.get("items"), dict):
                for index, item in enumerate(value): check(item, rule["items"], f"{path}[{index}]")
        if isinstance(value, dict):
            required = rule.get("required", [])
            missing = [key for key in required if key not in value]
            if missing: fail(path, "required property missing: " + ", ".join(missing))
            properties = rule.get("properties", {})
            if rule.get("additionalProperties") is False:
                unknown = set(value) - set(properties)
                if unknown: fail(path, "additional properties are not allowed: " + ", ".join(sorted(unknown)))
            for key, child in value.items():
                if key in properties: check(child, properties[key], f"{path}.{key}")

    check(spec, schema, "$")


def validate_spec(spec: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Validate and return *spec* using the bundled JSON Schema."""
    try:
        import jsonschema
        jsonschema.Draft202012Validator(schema).validate(spec)
    except ImportError:
        _validate_schema_v1_fallback(spec, schema)
    except jsonschema.ValidationError as exc:
        if list(exc.absolute_path) == ["anchors"]:
            raise SummaryError("anchors must contain 4..8 items") from exc
        raise SummaryError(exc.message) from exc

    source_errors = validate_sources(spec)
    if source_errors:
        raise SummaryError("source validation failed: " + "; ".join(source_errors))

    findings = privacy_findings(spec)
    if spec.get("privacy", {}).get("public_eligible") is True and findings:
        raise SummaryError("sensitive content is not allowed in a summary specification: " + "; ".join(findings))
    sources = spec.get("sources", [])
    covered = {claim_id for source in sources for claim_id in source.get("claim_ids", [])}
    missing = {
        claim_id
        for anchor in spec.get("anchors", [])
        for claim_id in anchor.get("claim_ids", [])
        if claim_id not in covered
    }
    if missing:
        raise SummaryError("source coverage is missing for claim IDs: " + ", ".join(sorted(missing)))
    return spec


def load_spec(path: Path) -> dict[str, Any]:
    """Load and validate a JSON summary specification from *path*."""
    try:
        spec = json.loads(path.read_text(encoding="utf-8"))
        schema_path = Path(__file__).resolve().parents[1] / "assets" / "summary-spec.schema.json"
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        return validate_spec(spec, schema)
    except SummaryError:
        raise
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise SummaryError(f"invalid summary specification: {exc}") from exc


def load_storyboard_response(path: Path) -> dict[str, Any]:
    """Load a local active-LLM response without selecting or calling a provider."""
    try:
        response = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise SummaryError(f"invalid storyboard response: {exc}") from exc
    if not isinstance(response, dict):
        raise SummaryError("storyboard response must be a JSON object")
    return response


def _bundled_schema() -> dict[str, Any]:
    """Load the schema that defines the public schema-v1 handoff input."""
    schema_path = Path(__file__).resolve().parents[1] / "assets" / "summary-spec.schema.json"
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        return schema
    except (OSError, json.JSONDecodeError) as exc:
        raise SummaryError(f"unable to load bundled summary schema: {exc}") from exc


def domain_profile(name: str) -> DomainProfile:
    """Return the fixed visual vocabulary for *name* (including schema aliases)."""
    canonical_name = _DOMAIN_ALIASES.get(name, name)
    try:
        return DOMAIN_PROFILES[canonical_name]
    except KeyError as exc:
        supported = ", ".join(sorted(DOMAIN_PROFILES))
        raise SummaryError(f"unsupported visual-summary domain {name!r}; choose one of: {supported}") from exc


def choose_archetype(spec: dict[str, Any]) -> str:
    """Respect an explicit supported archetype, otherwise use the domain default."""
    profile = domain_profile(str(spec.get("domain", "")))
    requested = spec.get("archetype")
    if requested in _ARCHETYPES:
        return str(requested)
    if requested is None or requested == "":
        return profile.preferred_archetypes[0]
    raise SummaryError(f"unsupported story-map archetype {requested!r}")


def _require_text_budget(label: str, value: Any, maximum: int) -> None:
    if not isinstance(value, str):
        raise SummaryError(f"{label} must be text")
    if len(value) > maximum:
        raise SummaryError(f"{label} exceeds its visible text budget of {maximum} characters")


def normalize_spec(raw: dict[str, Any]) -> dict[str, Any]:
    """Copy a schema-v1 spec and add deterministic domain-aware visual defaults.

    This deliberately does not validate source or privacy evidence; callers that
    ingest a file should use :func:`load_spec`, which preserves the schema-v1
    gate.  The normalized result is a renderer handoff, not a replacement
    source specification.
    """
    if not isinstance(raw, dict):
        raise SummaryError("summary specification must be an object")
    normalized = deepcopy(raw)
    profile = domain_profile(str(normalized.get("domain", "")))
    normalized["domain"] = profile.name
    normalized["archetype"] = choose_archetype(normalized)

    _require_text_budget("headline", normalized.get("title"), _TEXT_BUDGETS["headline"])
    _require_text_budget("takeaway", normalized.get("takeaway"), _TEXT_BUDGETS["takeaway"])
    for index, anchor in enumerate(normalized.get("anchors", []), start=1):
        if not isinstance(anchor, dict):
            raise SummaryError(f"anchor {index} must be an object")
        _require_text_budget(f"anchor {index} title", anchor.get("title"), _TEXT_BUDGETS["anchor_title"])
        _require_text_budget(f"anchor {index} detail", anchor.get("detail"), _TEXT_BUDGETS["anchor_detail"])
        service_line = ", ".join(str(service) for service in anchor.get("services", []))
        _require_text_budget(f"anchor {index} service line", service_line, _TEXT_BUDGETS["service_line"])
    # The visual footer is a compact pointer, not a complete ledger.  The full
    # source list stays in the document/PDF handoff; cap the visible ribbon to
    # clean human source titles.
    footer_evidence = _unique_titles([source for source in normalized.get("sources", []) if isinstance(source, dict)])
    _require_text_budget("footer evidence", footer_evidence, _TEXT_BUDGETS["footer_evidence"])

    direction = normalized.setdefault("visual_direction", {})
    if not isinstance(direction, dict):
        raise SummaryError("visual_direction must be an object")
    direction.setdefault("concept", "sketchnote-story-map-v1")
    if direction["concept"] != "sketchnote-story-map-v1":
        raise SummaryError("visual_direction concept must be sketchnote-story-map-v1")
    direction.setdefault("domain_metaphor", profile.metaphors[0])
    direction.setdefault("accent_roles", [profile.primary_accent, profile.secondary_accent])
    direction.setdefault("style_preset", "oci-doodle")
    if "doodle_level" not in direction:
        direction["doodle_level"] = {
            "calm": "minimal",
            "balanced": "balanced",
            "lively": "rich",
        }.get(str(direction.get("doodle_density", "balanced")), "balanced")
    direction.setdefault("doodle_density", {
        "minimal": "calm",
        "balanced": "balanced",
        "rich": "lively",
    }.get(str(direction.get("doodle_level", "balanced")), "balanced"))
    direction.setdefault("stroke_style", "marker")
    direction.setdefault(
        "style_variant",
        "project-capabilities" if normalized["domain"] == "project" else "doodle-at-a-glance",
    )
    output_formats = normalized.get("outputs", {}).get("formats", []) if isinstance(normalized.get("outputs"), dict) else []
    editable_targets = [
        item for item in output_formats
        if item in {"svg", "drawio", "excalidraw", "pptx", "docx"}
    ]
    direction.setdefault("editable_targets", editable_targets or ["svg"])
    normalized["profile"] = asdict(profile)
    return normalized


def _scaled_bounds(x: float, y: float, width: float, height: float, canvas_width: int, canvas_height: int) -> dict[str, int]:
    """Convert relative story-map bounds to deterministic integer canvas bounds."""
    return {
        "x": round(x * canvas_width),
        "y": round(y * canvas_height),
        "width": round(width * canvas_width),
        "height": round(height * canvas_height),
    }


def _curved_points(canvas_width: int, canvas_height: int, count: int) -> list[dict[str, int]]:
    """Return an asymmetric route that gives the eye one dominant journey."""
    # Keep the journey well below the headline/takeaway band.  Its varying
    # levels create a readable route without turning scenes into a card grid.
    offsets = (0.62, 0.54, 0.70, 0.57, 0.65, 0.51, 0.61, 0.55)
    return [
        {"x": round((0.12 + index * (0.76 / max(count - 1, 1))) * canvas_width), "y": round(offsets[index] * canvas_height)}
        for index in range(count)
    ]


def _dominant_structure(archetype: str, canvas_width: int, canvas_height: int, count: int) -> dict[str, Any]:
    if archetype in {"journey", "lifecycle"}:
        return {"kind": "curved-path", "points": _curved_points(canvas_width, canvas_height, count), "curve": "organic"}
    center = {"x": round(0.54 * canvas_width), "y": round(0.58 * canvas_height)}
    if archetype in {"layered-system", "before-after"}:
        return {
            "kind": "layer",
            "points": [
                {"x": round(0.13 * canvas_width), "y": round(0.43 * canvas_height)},
                {"x": round(0.87 * canvas_width), "y": round(0.43 * canvas_height)},
                {"x": round(0.87 * canvas_width), "y": round(0.72 * canvas_height)},
                {"x": round(0.13 * canvas_width), "y": round(0.72 * canvas_height)},
            ],
            "center": center,
        }
    return {"kind": "hub", "points": [center], "center": center, "spokes": count}


def _cluster_positions(count: int) -> list[tuple[float, float, float, float]]:
    """Deliberately irregular placements; each avoids the headline and grid rhythm."""
    positions = (
        (0.05, 0.25, 0.27, 0.30),
        (0.36, 0.28, 0.27, 0.29),
        (0.68, 0.24, 0.27, 0.31),
        (0.08, 0.62, 0.27, 0.29),
        (0.39, 0.65, 0.27, 0.27),
        (0.70, 0.60, 0.25, 0.31),
        (0.79, 0.30, 0.15, 0.16),
        (0.39, 0.45, 0.16, 0.13),
    )
    return list(positions[:count])


def _safe_local_image_path(value: Any, approved_root: Path | None = None) -> Path | None:
    """Return a bounded local raster asset only when it is a regular image file."""
    if not isinstance(value, (str, os.PathLike)) or not str(value):
        return None
    unresolved = Path(value)
    # Refuse the leaf symlink before resolving it. Ancestor symlinks that leave
    # the approved root are rejected by the containment check below.
    if unresolved.is_symlink() or any(parent.is_symlink() for parent in unresolved.parents):
        return None
    try:
        path = unresolved.resolve(strict=True)
    except OSError:
        return None
    if approved_root is not None:
        try:
            root = Path(approved_root).resolve(strict=True)
            path.relative_to(root)
        except (OSError, ValueError):
            return None
    if not path.is_file() or path.suffix.lower() not in _LOCAL_ART_SUFFIXES:
        return None
    try:
        if not 0 < path.stat().st_size <= _MAX_LOCAL_ART_BYTES:
            return None
    except OSError:
        return None
    dimensions = _image_dimensions(path)
    if dimensions is None or not all(0 < side <= 8_192 for side in dimensions) or dimensions[0] * dimensions[1] > _MAX_LOCAL_ART_PIXELS:
        return None
    return path


def _image_dimensions(path: Path) -> tuple[int, int] | None:
    """Recognize the allowed formats and reject suffix-only or malformed assets."""
    try:
        data = path.read_bytes()
    except OSError:
        return None
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24 and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    if data.startswith(b"\xff\xd8"):
        index = 2
        while index + 9 < len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            index += 2
            if marker in {0xD8, 0xD9}:
                continue
            if index + 2 > len(data):
                return None
            length = int.from_bytes(data[index:index + 2], "big")
            if length < 2 or index + length > len(data):
                return None
            if 0xC0 <= marker <= 0xC3 or 0xC5 <= marker <= 0xC7 or 0xC9 <= marker <= 0xCB or 0xCD <= marker <= 0xCF:
                return int.from_bytes(data[index + 3:index + 5], "big"), int.from_bytes(data[index + 5:index + 7], "big")
            index += length
        return None
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP" and len(data) >= 30:
        kind = data[12:16]
        if kind == b"VP8X" and len(data) >= 30:
            return int.from_bytes(data[24:27], "little") + 1, int.from_bytes(data[27:30], "little") + 1
        if kind == b"VP8L" and len(data) >= 25 and data[20] == 0x2F:
            bits = int.from_bytes(data[21:25], "little")
            return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
        if kind == b"VP8 " and len(data) >= 30 and data[23:26] == b"\x9d\x01\x2a":
            return int.from_bytes(data[26:28], "little") & 0x3FFF, int.from_bytes(data[28:30], "little") & 0x3FFF
    return None


def load_artwork_manifest(path: Path) -> dict[str, Any]:
    """Load a private, local-only mapping from story anchors to raster art.

    The manifest is intentionally separate from the publishable summary spec:
    it can carry workstation paths needed during composition without leaking
    them into SVG, PDF, Draw.io, Excalidraw, or PowerPoint outputs.
    """
    manifest_path = Path(path)
    if manifest_path.is_symlink():
        raise SummaryError("refusing symlink artwork manifest")
    try:
        if not 0 < manifest_path.stat().st_size <= 256 * 1024:
            raise SummaryError("artwork manifest exceeds the 256 KiB limit")
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except SummaryError:
        raise
    except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise SummaryError(f"invalid artwork manifest: {exc}") from exc
    # The manifest directory is the explicit asset trust root. Generated or
    # supplied rasters must be copied beside the private manifest (or below it)
    # before composition; an untrusted manifest cannot read arbitrary host files.
    try:
        approved_root = manifest_path.parent.resolve(strict=True)
    except OSError as exc:
        raise SummaryError(f"invalid artwork manifest directory: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) - _ART_MANIFEST_KEYS:
        raise SummaryError("artwork manifest contains unsupported fields")
    if payload.get("schema_version") != 1 or not isinstance(payload.get("assets"), list):
        raise SummaryError("artwork manifest must be schema version 1 with an assets array")
    if len(payload["assets"]) > 8:
        raise SummaryError("artwork manifest supports at most eight assets")
    seen: set[str] = set()
    cleaned: list[dict[str, Any]] = []
    for index, asset in enumerate(payload["assets"]):
        if not isinstance(asset, dict) or set(asset) - _ART_ASSET_KEYS:
            raise SummaryError(f"artwork asset {index + 1} contains unsupported fields")
        anchor_id = asset.get("anchor_id")
        if not isinstance(anchor_id, str) or not re.fullmatch(r"anchor-[1-8]", anchor_id) or anchor_id in seen:
            raise SummaryError(f"artwork asset {index + 1} has an invalid or duplicate anchor_id")
        seen.add(anchor_id)
        if asset.get("source_type") not in {"generated", "supplied"}:
            raise SummaryError(f"artwork asset {index + 1} source_type must be generated or supplied")
        if asset.get("rights") not in {"original", "user-supplied"}:
            raise SummaryError(f"artwork asset {index + 1} requires explicit original or user-supplied rights")
        raw_path = asset.get("path")
        if not isinstance(raw_path, str) or urlparse(raw_path).scheme or Path(raw_path).is_absolute():
            raise SummaryError(f"artwork asset {index + 1} must use a relative local file path below the manifest directory")
        candidate = manifest_path.parent / Path(raw_path)
        image_path = _safe_local_image_path(candidate, approved_root)
        if image_path is None:
            raise SummaryError(f"artwork asset {index + 1} is not a safe local PNG, JPEG, or WebP image")
        alt_text = asset.get("alt_text")
        if not isinstance(alt_text, str) or not alt_text.strip() or len(alt_text) > 240:
            raise SummaryError(f"artwork asset {index + 1} requires concise alt_text")
        generator = asset.get("generator", "active-llm")
        if not isinstance(generator, str) or not re.fullmatch(r"[A-Za-z0-9_. -]{1,80}", generator):
            raise SummaryError(f"artwork asset {index + 1} has an invalid generator label")
        cleaned.append({
            "anchor_id": anchor_id,
            "path": str(image_path),
            "source_type": asset["source_type"],
            "rights": asset["rights"],
            "generator": generator,
            "alt_text": alt_text.strip(),
            "sha256": hashlib.sha256(image_path.read_bytes()).hexdigest(),
            "approved_root": str(approved_root),
        })
    return {"schema_version": 1, "assets": cleaned}


def bind_artwork(handoff: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    """Bind validated private art paths to bounded slots in a renderer handoff."""
    _require_handoff(handoff)
    result = deepcopy(handoff)
    clusters = {cluster.get("anchor_id"): cluster for cluster in result["clusters"]}
    for asset in manifest.get("assets", []):
        cluster = clusters.get(asset.get("anchor_id"))
        if cluster is None:
            raise SummaryError(f"artwork references unknown anchor {asset.get('anchor_id')}")
        cluster["art_path"] = asset["path"]
        cluster["art_root"] = asset["approved_root"]
        cluster["art"] = {
            "source_type": asset["source_type"],
            "rights": asset["rights"],
            "generator": asset["generator"],
            "alt_text": asset["alt_text"],
            "sha256": asset["sha256"],
        }
    return result


def bind_reviewed_scenes(
    handoff: dict[str, Any], accepted_storyboard: dict[str, Any], scene_manifest: dict[str, Any],
) -> dict[str, Any]:
    """Bind only scene assets that passed storyboard's review gate.

    The provider-neutral storyboard contract owns scene review.  This adapter
    merely translates its accepted unit bindings to existing renderer anchors;
    it does not render, generate, or select an image provider.
    """
    _require_handoff(handoff)
    try:
        snapshot = storyboard.reviewed_scene_snapshot(scene_manifest, accepted_storyboard)
    except storyboard.StoryboardError as exc:
        raise SummaryError(f"bind_reviewed_scenes requires a matching loaded reviewed scene manifest: {exc}") from exc
    bindings = {binding.unit_id: binding for binding in snapshot["bindings"]}
    private_assets = []
    for scene in snapshot["scenes"]:
        unit_id = scene["unit_id"]
        image_path = scene["path"]
        binding = bindings.get(unit_id)
        if binding is None:
            raise SummaryError(f"reviewed scene references unknown storyboard unit {unit_id!r}")
        private_assets.append({
            "anchor_id": binding.anchor_id,
            "path": str(image_path),
            "source_type": "generated",
            "rights": scene["rights"],
            "generator": scene["generator"],
            "alt_text": binding.alt_text,
            "sha256": scene["sha256"],
            "approved_root": str(snapshot["manifest_root"]),
        })
    # load_artwork_manifest is intentionally file-based.  Its validations are
    # duplicated here only at the narrow, already-approved adapter boundary.
    return bind_artwork(handoff, {"schema_version": 1, "assets": private_assets})


def artwork_request(handoff: dict[str, Any]) -> dict[str, Any]:
    """Return a private provider-neutral request the active LLM can fulfil.

    This function never calls a model. The active agent may use Illo or another
    approved image model, then return the files through an artwork manifest.
    """
    _require_handoff(handoff)
    return {
        "schema_version": 1,
        "classification": "private-generation-input",
        "provider": "active-llm",
        "instructions": {
            "original_only": True,
            "text_free": True,
            "preserve_editable_text_layer": True,
            "transparent_or_simple_background": True,
        },
        "slots": [
            {
                "anchor_id": cluster["anchor_id"],
                "slot": cluster["art_slot"],
                "prompt": cluster["scene_prompt"],
                "expected_manifest_fields": ["anchor_id", "path", "source_type", "rights", "generator", "alt_text"],
            }
            for cluster in handoff["clusters"]
        ],
    }


def _scene_prompt(profile: DomainProfile, use_nimb: bool, art_slot: dict[str, int]) -> str:
    """Return a text-free, original-art direction for one bounded scene slot."""
    domain_object = profile.metaphors[0]
    slot = f"bounded art slot {art_slot['width']}x{art_slot['height']} at ({art_slot['x']},{art_slot['y']})"
    constraints = (
        "no words, letters, numbers, logos, UI, title bars, borders, citations, "
        "watermarks, copied conference branding, dark full-canvas background, or photographic frame; "
        "use a transparent or warm-white cutout background"
    )
    if use_nimb:
        action = f"Nimb operates the {domain_object}, tracing a hand-drawn route with a {profile.doodles[0]} doodle"
    else:
        action = f"An operator traces the {domain_object} with a hand-drawn route and a {profile.doodles[0]} doodle"
    return (
        f"Original {profile.name} supporting illustration: {action}; {slot}; "
        f"palette {profile.primary_accent} and {profile.secondary_accent}; {constraints}."
    )


def _line_style(stroke_style: str) -> str:
    return {
        "marker": "hand-drawn",
        "pencil": "sketch-pencil",
        "chalk": "chalky",
        "riso": "risograph",
    }.get(stroke_style, "hand-drawn")


_CANVAS_FONT_STACK = '"Chalkboard SE", "Marker Felt", "Comic Sans MS", cursive'
_CANVAS_ROLES = ("threshold", "signal", "bridge", "control-wheel", "beacon", "boundary", "watchpoint", "feedback-loop")


def _canvas_scene_bounds(position: tuple[float, float, float, float], width: int, height: int) -> tuple[dict[str, int], dict[str, int]]:
    """Split an irregular scene into art-first and adjacent selectable-text space."""
    x, y, scene_width, scene_height = position
    # Keep each scene art-first and generous; the annotation follows below.
    art = _scaled_bounds(x + scene_width * .08, y + scene_height * .02, scene_width * .84, scene_height * .56, width, height)
    text = _scaled_bounds(x + scene_width * .03, y + scene_height * .61, scene_width * .94, scene_height * .36, width, height)
    return art, text


def _is_canvas_story_map(handoff: dict[str, Any]) -> bool:
    return handoff.get("visual_style", {}).get("variant") == "canvas-story-map"


def build_handoff(spec: dict[str, Any], width: int, height: int) -> dict[str, Any]:
    """Build an original single-canvas sketchnote story-map renderer handoff."""
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise SummaryError("canvas width and height must be positive integers")
    normalized = normalize_spec(validate_spec(spec, _bundled_schema()))
    anchors = normalized.get("anchors", [])
    if not 4 <= len(anchors) <= 8:
        raise SummaryError("story maps require 4..8 anchors")
    profile = domain_profile(normalized["domain"])
    mascot_mode = str(normalized["visual_direction"].get("mascot_mode", ""))
    mascot_asset = _safe_local_image_path(normalized["visual_direction"].get("mascot_asset"))
    use_nimb = mascot_mode == "nimb-operator" and mascot_asset is not None
    archetype = normalized["archetype"]
    dominant_path = _dominant_structure(archetype, width, height, len(anchors))
    silhouettes = ("arch", "cloud", "seal", "flag", "loop", "burst", "bridge", "lens")
    callout_shapes = ("ribbon", "speech-tail", "torn-note", "bracket", "arrow-tab", "seal", "wave", "underline")
    configured_slots = {
        slot.get("anchor_id"): slot
        for slot in normalized.get("artwork", {}).get("slots", [])
        if isinstance(slot, dict)
    }
    clusters = []
    public_source_urls = {
        str(source.get("url"))
        for source in normalized.get("sources", [])
        if isinstance(source, dict)
        and source.get("classification") == "public"
        and isinstance(source.get("url"), str)
        and str(source.get("url")).startswith("https://")
    }
    # Keep the portable CLI usable with the system Python used by ``-S``.
    for index, (anchor, position) in enumerate(zip(anchors, _cluster_positions(len(anchors))), start=1):
        services = [str(service) for service in anchor.get("services", [])]
        art_slot = _scaled_bounds(position[0] + position[2] * 0.54, position[1], position[2] * 0.46, position[3] * 0.56, width, height)
        scene_prompt = _scene_prompt(profile, use_nimb, art_slot)
        cluster = {
                "anchor_id": f"anchor-{index}",
                "bounds": _scaled_bounds(*position, width, height),
                "silhouette": silhouettes[index - 1],
                "art_slot": art_slot,
                "scene_prompt": scene_prompt,
                "title": anchor["title"],
                "detail": anchor["detail"],
                "service_names": services,
                "service_label": (services[0].replace("-", " ").title() if services else profile.name.title()),
                "index": index,
                "evidence_class": anchor["evidence_class"],
                "source_ids": [
                    str(source_id)
                    for source_id in anchor.get("source_ids", [])
                    if str(source_id) in public_source_urls
                ],
                "callout_shape": callout_shapes[index - 1],
                "art_direction": {
                    "slot_mode": "supporting-art",
                    "generated_image_allowed": True,
                    "scene_prompt": scene_prompt,
                    "asset_role": "scene",
                    "alt_text": f"Supporting illustration for {anchor['title']}",
                },
            }
        configured = configured_slots.get(cluster["anchor_id"])
        if configured:
            cluster["art_slot_id"] = configured["id"]
            cluster["art_role"] = configured["role"]
            cluster["art_alt_text"] = configured["alt_text"]
            cluster["art_direction"]["asset_role"] = configured["role"]
            cluster["art_direction"]["alt_text"] = configured["alt_text"]
            hint = str(configured.get("prompt_hint", "")).strip()
            if hint:
                cluster["scene_prompt"] = cluster["scene_prompt"].removesuffix(".") + f"; creative cue: {hint}."
                cluster["art_direction"]["scene_prompt"] = cluster["scene_prompt"]
        if normalized["visual_direction"].get("style_variant") == "canvas-story-map":
            art_bounds, text_bounds = _canvas_scene_bounds(position, width, height)
            cluster.update({
                "canvas_role": _CANVAS_ROLES[index - 1],
                "art_bounds": art_bounds,
                "text_bounds": text_bounds,
            })
        clusters.append(cluster)

    headline_zone = _scaled_bounds(0.07, 0.05, 0.86, 0.21, width, height)
    handoff = {
        "concept": "sketchnote-story-map-v1",
        "canvas": {"width": width, "height": height},
        "domain": profile.name,
        "profile": asdict(profile),
        "archetype": archetype,
        "evidence_class": normalized["evidence_class"],
        "mascot_available": use_nimb,
        "artwork_mode": normalized.get("artwork", {}).get("mode", "doodle"),
        "artwork_generation_policy": normalized.get("artwork", {}).get("generation_policy", "none"),
        "artwork_style_register": normalized.get("artwork", {}).get("style_register", "explainer"),
        "doodle_density": normalized["visual_direction"].get("doodle_density", "rich"),
        "stroke_style": normalized["visual_direction"].get("stroke_style", "marker"),
        "visual_style": {
            "preset": normalized["visual_direction"].get("style_preset", "oci-doodle"),
            "variant": normalized["visual_direction"].get("style_variant", "doodle-at-a-glance"),
            "doodle_level": normalized["visual_direction"].get("doodle_level", "balanced"),
            "doodle_density": normalized["visual_direction"].get("doodle_density", "balanced"),
            "stroke_style": normalized["visual_direction"].get("stroke_style", "marker"),
            "line_style": _line_style(str(normalized["visual_direction"].get("stroke_style", "marker"))),
            "editable_targets": list(normalized["visual_direction"].get("editable_targets", [])),
        },
        "dominant_path_phrase": normalized["visual_direction"]["dominant_path"],
        "headline_zone": {"bounds": headline_zone, "area_ratio": 0.21, "title": normalized["title"], "takeaway": normalized["takeaway"]},
        "dominant_path": dominant_path,
        "clusters": clusters,
        "ribbons": [{"kind": "takeaway", "text": normalized["takeaway"], "accent": profile.primary_accent}],
        "evidence_footer": _unique_titles([source for source in normalized["sources"] if isinstance(source, dict)]),
        "source_register": [
            {
                "title": str(source.get("title", "Official Oracle documentation")),
                "url": str(source["url"]),
                "claim_ids": [str(claim_id) for claim_id in source.get("claim_ids", [])],
            }
            for source in normalized.get("sources", [])
            if isinstance(source, dict) and str(source.get("url", "")) in public_source_urls
        ],
        "negative_space_ratio": 0.42,
        "text_budgets": dict(_TEXT_BUDGETS),
    }
    if _is_canvas_story_map(handoff):
        handoff["canvas_layout"] = {
            "composition": "scene-led",
            "ground": "warm-paper",
            "headline_bounds": headline_zone,
            "thread": {"role": "oracle-red", "points": dominant_path.get("points", [])},
            "footer_bounds": _scaled_bounds(.07, .92, .82, .05, width, height),
            "quiet_space_ratio": 0.30,
        }
    return handoff


def _hex_rgb(value: str) -> tuple[int, int, int]:
    """Convert a fixed profile hex colour to RGB without a rendering dependency."""
    value = value.lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", value):
        return (30, 35, 48)
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def _require_handoff(handoff: dict[str, Any]) -> tuple[int, int]:
    if not isinstance(handoff, dict) or handoff.get("concept") != "sketchnote-story-map-v1":
        raise SummaryError("renderer requires a sketchnote-story-map-v1 handoff")
    canvas = handoff.get("canvas")
    if not isinstance(canvas, dict):
        raise SummaryError("renderer handoff must contain canvas dimensions")
    width, height = canvas.get("width"), canvas.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise SummaryError("renderer handoff canvas dimensions must be positive integers")
    if not isinstance(handoff.get("clusters"), list) or not handoff["clusters"]:
        raise SummaryError("renderer handoff must contain clusters")
    return width, height


def _wrap(text: str, limit: int) -> list[str]:
    """Wrap deterministic labels without moving them into generated art."""
    words = str(text).split()
    if not words:
        return [""]
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > limit:
            lines.append(current)
            current = word
        else:
            current = candidate
    lines.append(current)
    return lines


def _svg_visible_text(value: str) -> str:
    """Escape visible SVG text while making authored word gaps hard spaces."""
    return escape(value.replace(" ", "\u00a0"))


def _svg_text(lines: list[str], x: float, y: float, size: float, fill: str, weight: str = "400", font_family: str = _SVG_FONT_STACK) -> str:
    tspans = "".join(
        # SVG's default whitespace processing collapses spaces in text nodes
        # during native rendering, and some importers ignore xml:space. Use a
        # hard-space code point for visible intra-line separation so labels
        # such as "incident context" cannot render as "incidentcontext" in
        # browsers, previewers, or Office importers. Titles/descriptions remain
        # ordinary text for accessible extraction; this applies only to the
        # visible text nodes emitted here.
        f'<tspan x="{x:.1f}" dy="{0 if index == 0 else size * 1.22:.1f}" xml:space="preserve">{_svg_visible_text(line)}</tspan>'
        for index, line in enumerate(lines)
    )
    return f'<text x="{x:.1f}" y="{y:.1f}" xml:space="preserve" font-family="{escape(font_family, quote=True)}" font-size="{size:.1f}" font-weight="{weight}" fill="{fill}">{tspans}</text>'


def _svg_badge_text(label: str, x: float, y: float, width: float, height: float, fill: str, text_fill: str) -> str:
    return (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" rx="{height * .45:.1f}" '
        f'fill="{fill}" opacity=".16"/>'
        + _svg_text([label], x + width * .12, y + height * .67, height * .44, text_fill, "700")
    )


def _svg_cluster_shell(bounds: dict[str, int], shape: str, fill: str, stroke: str) -> str:
    x, y, width, height = (bounds[key] for key in ("x", "y", "width", "height"))
    left = x - width * .03
    top = y - height * .04
    right = x + width * 1.02
    bottom = y + height * .98
    mid_x = x + width * .48
    mid_y = y + height * .48
    if shape == "arch":
        d = (
            f"M {left:.1f} {bottom:.1f} "
            f"L {left:.1f} {top + height * .34:.1f} "
            f"Q {mid_x:.1f} {top - height * .22:.1f} {right:.1f} {top + height * .34:.1f} "
            f"L {right:.1f} {bottom:.1f} Z"
        )
    elif shape == "cloud":
        d = (
            f"M {left + width * .10:.1f} {bottom:.1f} "
            f"Q {left - width * .04:.1f} {mid_y:.1f} {left + width * .14:.1f} {top + height * .28:.1f} "
            f"Q {mid_x:.1f} {top - height * .16:.1f} {right - width * .08:.1f} {top + height * .22:.1f} "
            f"Q {right + width * .05:.1f} {mid_y:.1f} {right - width * .02:.1f} {bottom - height * .06:.1f} "
            f"Q {mid_x:.1f} {bottom + height * .12:.1f} {left + width * .10:.1f} {bottom:.1f} Z"
        )
    elif shape == "seal":
        d = (
            f"M {mid_x:.1f} {top - height * .08:.1f} "
            f"Q {right + width * .02:.1f} {top + height * .10:.1f} {right:.1f} {mid_y:.1f} "
            f"Q {right - width * .02:.1f} {bottom + height * .10:.1f} {mid_x:.1f} {bottom + height * .04:.1f} "
            f"Q {left - width * .02:.1f} {bottom + height * .08:.1f} {left:.1f} {mid_y:.1f} "
            f"Q {left + width * .02:.1f} {top + height * .08:.1f} {mid_x:.1f} {top - height * .08:.1f} Z"
        )
    elif shape == "flag":
        d = (
            f"M {left:.1f} {top + height * .12:.1f} "
            f"L {right - width * .12:.1f} {top + height * .12:.1f} "
            f"L {right:.1f} {top + height * .30:.1f} "
            f"L {right - width * .12:.1f} {top + height * .48:.1f} "
            f"L {right:.1f} {bottom:.1f} "
            f"L {left + width * .08:.1f} {bottom:.1f} "
            f"Q {left - width * .02:.1f} {mid_y:.1f} {left:.1f} {top + height * .12:.1f} Z"
        )
    elif shape == "loop":
        d = (
            f"M {left + width * .04:.1f} {mid_y:.1f} "
            f"Q {left + width * .12:.1f} {top + height * .02:.1f} {mid_x:.1f} {top + height * .10:.1f} "
            f"Q {right + width * .02:.1f} {top + height * .20:.1f} {right - width * .04:.1f} {mid_y:.1f} "
            f"Q {right - width * .10:.1f} {bottom + height * .08:.1f} {mid_x:.1f} {bottom:.1f} "
            f"Q {left - width * .02:.1f} {bottom - height * .02:.1f} {left + width * .04:.1f} {mid_y:.1f} Z"
        )
    elif shape == "burst":
        d = (
            f"M {left + width * .08:.1f} {top + height * .10:.1f} "
            f"L {mid_x:.1f} {top - height * .10:.1f} "
            f"L {right - width * .04:.1f} {top + height * .14:.1f} "
            f"L {right + width * .02:.1f} {mid_y:.1f} "
            f"L {right - width * .08:.1f} {bottom:.1f} "
            f"L {mid_x:.1f} {bottom + height * .06:.1f} "
            f"L {left - width * .02:.1f} {bottom - height * .02:.1f} "
            f"L {left + width * .02:.1f} {mid_y:.1f} Z"
        )
    elif shape == "bridge":
        d = (
            f"M {left:.1f} {bottom - height * .08:.1f} "
            f"Q {mid_x:.1f} {top - height * .18:.1f} {right:.1f} {bottom - height * .08:.1f} "
            f"L {right - width * .05:.1f} {bottom:.1f} "
            f"Q {mid_x:.1f} {top + height * .04:.1f} {left + width * .05:.1f} {bottom:.1f} Z"
        )
    else:
        d = (
            f"M {left + width * .16:.1f} {top:.1f} "
            f"Q {right:.1f} {top + height * .04:.1f} {right:.1f} {mid_y:.1f} "
            f"Q {right:.1f} {bottom:.1f} {left + width * .16:.1f} {bottom:.1f} "
            f"Q {left - width * .04:.1f} {mid_y:.1f} {left + width * .16:.1f} {top:.1f} Z"
        )
    return f'<path d="{d}" fill="{fill}" stroke="{stroke}" stroke-width="3.5" stroke-linejoin="round"/>'


def _svg_cluster_doodle(
    bounds: dict[str, int], doodles: tuple[str, ...], color: str, *, seed: str = "scene", density: str = "rich"
) -> str:
    """Draw a deterministic text-free doodle field from editable SVG marks."""
    x, y, width, height = (bounds[key] for key in ("x", "y", "width", "height"))
    primary = doodles[0] if doodles else "spark"
    secondary = doodles[1] if len(doodles) > 1 else "trail"
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    jitter = [((value % 13) - 6) / 100 for value in digest[:8]]
    badge_x = x + width * .70
    badge_y = y + height * .24
    parts = [f'<g data-doodle="{escape(primary)}" data-doodle-density="{escape(density)}" aria-hidden="true">',
        f'<path data-doodle-kind="squiggle" d="M {badge_x + width * jitter[0]:.1f} {badge_y:.1f} '
        f'c {width * .025:.1f} -{height * .10:.1f} {width * .055:.1f} {height * .10:.1f} {width * .08:.1f} 0 '
        f's {width * .055:.1f} -{height * .10:.1f} {width * .08:.1f} 0" fill="none" stroke="{color}" '
        f'stroke-width="4" stroke-linecap="round" opacity=".88"/>',
        f'<path d="M {badge_x:.1f} {badge_y:.1f} q {width * .06:.1f} -{height * .08:.1f} {width * .12:.1f} 0 '
        f'q -{width * .03:.1f} {height * .07:.1f} -{width * .12:.1f} 0" fill="none" stroke="{color}" '
        f'stroke-width="4" stroke-linecap="round" opacity=".9"/>',
        f'<path data-doodle-kind="echo" d="M {badge_x - width * .04:.1f} {badge_y + height * .10:.1f} '
        f'q {width * .05:.1f} -{height * .06:.1f} {width * .10:.1f} 0" fill="none" stroke="{color}" '
        f'stroke-width="3" stroke-linecap="round" opacity=".5"/>',
    ]
    # A rough star/spark, tape strip, and short hatch marks create the authored
    # sketchnote feel without baking labels into generated artwork.
    star_x, star_y = badge_x + width * .16, badge_y - height * .02
    star_points = []
    for index in range(10):
        angle = -1.57 + index * 3.14159 / 5
        radius = height * (.035 if index % 2 == 0 else .014)
        star_points.append(f"{star_x + cos(angle) * radius:.1f},{star_y + sin(angle) * radius:.1f}")
    parts.append(f'<polygon data-doodle-kind="spark" points="{" ".join(star_points)}" fill="none" stroke="{color}" stroke-width="3" stroke-linejoin="round"/>')
    parts.append(f'<path data-doodle-kind="tape" d="M {badge_x - width * .03:.1f} {badge_y + height * .18:.1f} '
                 f'l {width * .11:.1f} {height * (jitter[2] + .01):.1f} l -{width * .01:.1f} {height * .04:.1f} '
                 f'l -{width * .11:.1f} -{height * (jitter[2] + .01):.1f} Z" fill="{color}" opacity=".12"/>')
    hatch_count = 2 if density == "sparse" else 4 if density == "balanced" else 7
    for index in range(hatch_count):
        hx = badge_x + width * (.02 + index * .022 + jitter[(index + 3) % len(jitter)])
        hy = badge_y + height * (.24 + (index % 2) * .025)
        parts.append(f'<path data-doodle-kind="hatch" d="M {hx:.1f} {hy:.1f} l {width * .014:.1f} -{height * .05:.1f}" '
                     f'stroke="{color}" stroke-width="2.4" stroke-linecap="round" opacity=".48"/>')
    if secondary not in {primary, ""}:
        parts.append(f'<circle cx="{badge_x + width * .16:.1f}" cy="{badge_y - height * .02:.1f}" r="{height * .010:.1f}" fill="{color}" opacity=".28"/>')
    parts.append("</g>")
    return "".join(parts)


def _unique_titles(sources: list[dict[str, Any]]) -> str:
    titles: list[str] = []
    seen: set[str] = set()
    for source in sources:
        if not isinstance(source, dict):
            continue
        title = str(source.get("title", "")).strip()
        if not title or not re.match(r"^[A-Za-z0-9]", title):
            continue
        normalized = title.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        # The physical footer has a dedicated multi-line band.  Preserve the
        # whole concise source statement so an acceptance fixture can identify
        # its synthetic/local boundary and named OCI services without a
        # misleading mid-word truncation.
        titles.append(title[:120])
        if len(titles) == 4:
            break
    return ", ".join(titles)


def _art_data_uri(cluster: dict[str, Any]) -> str | None:
    """Embed an explicitly supplied local supporting-art file without its path."""
    if "art_path" not in cluster or not cluster.get("art_path"):
        return None
    path = _safe_local_image_path(cluster["art_path"], Path(cluster["art_root"]) if cluster.get("art_root") else None)
    if path is None:
        raise SummaryError("art_path must reference a safe local PNG, JPEG, or WebP image")
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}[path.suffix.lower()]
    payload = path.read_bytes()
    expected_sha = cluster.get("art", {}).get("sha256")
    if expected_sha and hashlib.sha256(payload).hexdigest() != expected_sha:
        raise SummaryError("supporting art changed after manifest validation")
    if len(payload) > _MAX_EMBEDDED_ART_BYTES:
        try:
            from PIL import Image

            with Image.open(path) as image:
                image.thumbnail((1024, 1024))
                image = image.convert("RGB")
                buffer = io.BytesIO()
                image.save(buffer, format="JPEG", quality=82, optimize=True, progressive=True)
                payload = buffer.getvalue()
                mime = "image/jpeg"
        except (ImportError, OSError) as exc:
            raise SummaryError("supporting art above 1 MiB requires PIL for safe embedded-image optimization") from exc
    if len(payload) > _MAX_EMBEDDED_ART_BYTES:
        raise SummaryError("optimized supporting art still exceeds the 1 MiB embedded-image limit")
    return f"data:{mime};base64,{base64.b64encode(payload).decode('ascii')}"


def _supplied_art(handoff: dict[str, Any]) -> list[tuple[dict[str, Any], Path]]:
    """Resolve all explicitly requested art slots or fail instead of dropping one."""
    supplied: list[tuple[dict[str, Any], Path]] = []
    for cluster in handoff["clusters"]:
        if "art_path" not in cluster or not cluster.get("art_path"):
            continue
        path = _safe_local_image_path(cluster["art_path"], Path(cluster["art_root"]) if cluster.get("art_root") else None)
        if path is None:
            raise SummaryError("art_path must reference a safe local PNG, JPEG, or WebP image")
        expected_sha = cluster.get("art", {}).get("sha256")
        if expected_sha and hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha:
            raise SummaryError("supporting art changed after manifest validation")
        supplied.append((cluster, path))
    return supplied


def _reportlab_available() -> bool:
    try:
        import reportlab  # noqa: F401
    except ImportError:
        return False
    return True


def _require_art_backend(handoff: dict[str, Any], dependency: str) -> list[tuple[dict[str, Any], Path]]:
    if handoff.get("concept") == "illo-storyboard-sequence-v1":
        return []
    supplied = _supplied_art(handoff)
    if not supplied:
        return supplied
    if dependency == "PIL":
        try:
            import PIL  # noqa: F401
        except ImportError as exc:
            raise SummaryError("PNG output with supplied art requires PIL; art was not rendered") from exc
    elif dependency == "reportlab":
        if not _reportlab_available():
            raise SummaryError("PDF output with supplied art requires reportlab; art was not rendered")
    return supplied


def _safe_output_path(value: Path) -> Path:
    """Reject pre-existing symlink targets/directories before local generation."""
    path = Path(value).absolute()
    for component in (path, *path.parents):
        if component.exists() and component.is_symlink():
            raise SummaryError(f"refusing symlinked output path: {component}")
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise SummaryError(f"refusing symlinked output file: {path}")
    return path


def _canonical_private_output_root(value: Path) -> Path:
    """Canonicalize only macOS's trusted /var alias before private-write checks."""
    path = Path(os.path.abspath(os.fspath(value)))
    var_alias = Path("/var")
    canonical_var = Path("/private/var")
    if not var_alias.is_symlink() or Path(os.path.realpath(var_alias)) != canonical_var:
        return path
    try:
        relative = path.relative_to(var_alias)
    except ValueError:
        return path
    # ``abspath`` above removes dot components; later component-by-component
    # checks still reject every non-system symlink under this canonical root.
    return canonical_var / relative


def _require_private_output_ignored(directory: Path) -> None:
    """Refuse restricted generation into a repository that would track it."""
    directory = Path(directory).absolute()
    probe_dir = directory
    while not probe_dir.exists() and probe_dir != probe_dir.parent:
        probe_dir = probe_dir.parent
    probe = subprocess.run(
        ["git", "-C", str(probe_dir), "rev-parse", "--show-toplevel"],
        text=True, capture_output=True, check=False,
    )
    if probe.returncode != 0:
        return
    root = Path(probe.stdout.strip())
    try:
        relative = directory.relative_to(root)
    except ValueError:
        return
    ignored = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "-q", "--", str(relative) + "/"],
        check=False,
    )
    if ignored.returncode != 0:
        raise SummaryError("private output directory is not git-ignored")


def _write_private_json(directory: Path, name: str, payload: dict[str, Any]) -> Path:
    """Create a private JSON receipt without following pre-existing symlinks."""
    directory = Path(directory).absolute()
    _require_private_output_ignored(directory)
    for component in (directory, *directory.parents):
        if component.exists() and component.is_symlink():
            raise SummaryError(f"refusing symlinked private output directory: {component}")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    target = _safe_output_path(directory / name)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(target, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
    except OSError as exc:
        raise SummaryError(f"could not write private output safely: {exc}") from exc
    os.chmod(target, 0o600)
    return target


_PROJECT_STORYBOARD_REQUEST_FILES = frozenset({
    "project-evidence.json", "synthesis-request.json", "storyboard-request.json",
})


def _project_storyboard_request_preflight(out_dir: Path) -> None:
    """Fail closed rather than silently mixing a request with stale renders."""
    out_dir = Path(out_dir).absolute()
    if not out_dir.exists():
        return
    if not out_dir.is_dir() or out_dir.is_symlink():
        raise SummaryError("project-storyboard request output must be a real directory")
    entries = list(out_dir.iterdir())
    if any(item.name != ".visual-summary-private" for item in entries):
        raise SummaryError("project-storyboard request refuses stale render or public output")
    if not entries:
        return
    private = entries[0]
    if private.is_symlink() or not private.is_dir():
        raise SummaryError("project-storyboard request private output must be a real directory")
    children = list(private.iterdir())
    if {item.name for item in children} != _PROJECT_STORYBOARD_REQUEST_FILES or any(not item.is_file() or item.is_symlink() for item in children):
        raise SummaryError("project-storyboard request refuses non-request private state")


def _fsync_private_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a bounded private JSON payload and force it before publication."""
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as handle:
            handle.write(encoded); handle.flush(); os.fsync(handle.fileno())
    finally:
        os.close(descriptor)
    os.chmod(path, 0o600)
    # Re-parse what will be published, not the in-memory caller payload.
    if not isinstance(json.loads(path.read_text(encoding="utf-8")), dict):
        raise SummaryError("private request payload must be a JSON object")


def _publish_project_storyboard_requests(out_dir: Path, payloads: dict[str, dict[str, Any]]) -> list[Path]:
    """Stage and roll back the request triplet as a single local transaction."""
    if set(payloads) != _PROJECT_STORYBOARD_REQUEST_FILES:
        raise SummaryError("project-storyboard private request set is incomplete")
    out_dir = Path(out_dir).absolute()
    _project_storyboard_request_preflight(out_dir)
    _require_private_output_ignored(out_dir / ".visual-summary-private")
    stage_dir = Path(tempfile.mkdtemp(prefix=".visual-summary-request-stage-", dir=out_dir.parent))
    os.chmod(stage_dir, 0o700)
    try:
        for name, payload in payloads.items():
            _fsync_private_json(stage_dir / name, payload)
        # Validate all staged payloads before creating or changing the target.
        for name in _PROJECT_STORYBOARD_REQUEST_FILES:
            json.loads((stage_dir / name).read_text(encoding="utf-8"))
        private = out_dir / ".visual-summary-private"
        private.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(private, 0o700)
        backups: list[tuple[Path, Path | None]] = []
        for index, name in enumerate(sorted(_PROJECT_STORYBOARD_REQUEST_FILES)):
            target = _safe_output_path(private / name)
            backup = stage_dir / f"backup-{index}"
            if target.exists():
                shutil.copy2(target, backup); backups.append((target, backup))
            else:
                backups.append((target, None))
        try:
            for name in sorted(_PROJECT_STORYBOARD_REQUEST_FILES):
                os.replace(stage_dir / name, _safe_output_path(private / name))
        except OSError:
            for target, backup in backups:
                if backup is None:
                    target.unlink(missing_ok=True)
                else:
                    shutil.copy2(backup, target)
            raise
        return [private / name for name in sorted(_PROJECT_STORYBOARD_REQUEST_FILES)]
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)


def _write_private_text(directory: Path, name: str, content: str) -> Path:
    """Create private prose beside private JSON without weakening write safety."""
    directory = Path(directory).absolute()
    _require_private_output_ignored(directory)
    for component in (directory, *directory.parents):
        if component.exists() and component.is_symlink():
            raise SummaryError(f"refusing symlinked private output directory: {component}")
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    target = _safe_output_path(directory / name)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(target, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
    except OSError as exc:
        raise SummaryError(f"could not write private output safely: {exc}") from exc
    os.chmod(target, 0o600)
    return target


def _canvas_direction_text(anchor: dict[str, Any], key: str, default: str) -> str:
    """Return a non-empty private direction field after accepting optional input."""
    value = anchor.get(key)
    return str(value).strip() if value is not None and str(value).strip() else default


def _canvas_scene_prompt(profile: DomainProfile, anchor: dict[str, Any], index: int) -> str:
    """Make a private, text-free visual direction from the anchor's scene fields."""
    role = _canvas_direction_text(anchor, "scene_role", "operator")
    hint = _canvas_direction_text(anchor, "scene_hint", profile.doodles[(index - 1) % len(profile.doodles)])
    relationship = _canvas_direction_text(anchor, "relationship", "connected workflow step")
    services = ", ".join(str(service) for service in anchor.get("services", [])) or profile.name
    return (
        f"Original {profile.name} canvas scene: {role} stages {hint} as a physical {relationship}; "
        f"service context {services}; hand-drawn editorial explainer composition; "
        "no words, no letters, no numbers, no logos, no UI, no watermarks, no copied branding."
    )


def build_canvas_plan(spec: dict[str, Any], out_dir: Path) -> list[Path]:
    """Write the opt-in Canvas planning packet to the bounded private directory only."""
    normalized = normalize_spec(validate_spec(spec, _bundled_schema()))
    if normalized["visual_direction"].get("style_variant") != "canvas-story-map":
        raise SummaryError("canvas planning requires visual_direction.style_variant canvas-story-map")
    out_dir = _canonical_private_output_root(Path(out_dir))
    private_dir = out_dir / ".visual-summary-private"
    profile = domain_profile(normalized["domain"])
    anchors = normalized["anchors"]
    moves = ("opens a guarded threshold", "routes a visible signal", "joins two bounded paths", "turns a control wheel", "raises a verification beacon", "separates trusted lanes", "sets a watchpoint", "closes a feedback loop")
    metaphors = ("gate", "signal bridge", "checkpoint lens", "control wheel", "beacon", "trust boundary", "watchtower", "feedback loop")
    stagings = ("foreground-left", "lower-center", "upper-right", "lower-right", "outer-left", "lower-mid", "upper-edge", "center-overlap")
    scenes = []
    for index, anchor in enumerate(anchors, start=1):
        role = _canvas_direction_text(anchor, "scene_role", "operator")
        relationship = _canvas_direction_text(anchor, "relationship", "connected workflow step")
        services = [str(service) for service in anchor.get("services", [])]
        scenes.append({
            "anchor_id": f"anchor-{index}",
            "thesis": f"{anchor['detail']} through {relationship}",
            "physical_move": moves[index - 1],
            "object_metaphor": metaphors[index - 1],
            "character_role": role,
            "register_staging": stagings[index - 1],
            "service_context": services,
            "relationship": relationship,
            "scene_prompt": _canvas_scene_prompt(profile, anchor, index),
        })
    placements = [
        {"anchor_id": f"anchor-{index}", "bounds": _scaled_bounds(*position, 1920, 1080)}
        for index, position in enumerate(_cluster_positions(len(anchors)), start=1)
    ]
    workflow = {
        "schema_version": 1,
        "domain": profile.name,
        "nodes": [
            {"anchor_id": scene["anchor_id"], "role": scene["character_role"], "services": scene["service_context"]}
            for scene in scenes
        ],
        "relationships": [
            {"from": scene["anchor_id"], "to": f"anchor-{index + 1}" if index < len(scenes) else None, "relationship": scene["relationship"]}
            for index, scene in enumerate(scenes, start=1)
        ],
    }
    composition = {
        "headline_zone": _scaled_bounds(0.07, 0.05, 0.86, 0.21, 1920, 1080),
        "dominant_thread": normalized["visual_direction"]["dominant_path"],
        "irregular_scene_placements": placements,
        "negative_space_target": 0.42,
        "art_text_z_order": ["background", "dominant-thread", "scene-art", "callouts", "text", "evidence"],
        "export_roles": {"svg": "canonical-public", "png": "raster-preview", "pdf": "printable-handoff", "drawio": "editable-layout", "excalidraw": "editable-sketch"},
    }
    philosophy = (
        "# Canvas story-map design philosophy\n\n"
        "Keep one dominant workflow thread, irregular scene placements, and deliberate negative space. "
        "Scene direction is private planning input; public renders retain only approved visible story content.\n"
    )
    return [
        _write_private_text(private_dir, "design-philosophy.md", philosophy),
        _write_private_json(private_dir, "oci-workflow-map.json", workflow),
        _write_private_json(private_dir, "scene-plan.json", {"schema_version": 1, "scenes": scenes}),
        _write_private_json(private_dir, "composition-plan.json", composition),
    ]


def _svg_callout(shape: str, bounds: dict[str, int], color: str) -> str:
    """Render a small named callout mark that points from each scene to its story."""
    x, y, width, height = (bounds[key] for key in ("x", "y", "width", "height"))
    left, top = x + width * .72, y + height * .76
    paths = {
        "ribbon": f"M {left:.1f} {top:.1f} q {width * .08:.1f} -{height * .08:.1f} {width * .18:.1f} 0",
        "speech-tail": f"M {left:.1f} {top:.1f} l {width * .08:.1f} {height * .11:.1f} l {width * .05:.1f} -{height * .12:.1f}",
        "torn-note": f"M {left:.1f} {top:.1f} l {width * .05:.1f} -{height * .06:.1f} l {width * .05:.1f} {height * .06:.1f} l {width * .05:.1f} -{height * .06:.1f}",
        "bracket": f"M {left:.1f} {top:.1f} l {width * .06:.1f} 0 l 0 {height * .12:.1f} l {width * .06:.1f} 0",
        "arrow-tab": f"M {left:.1f} {top:.1f} l {width * .12:.1f} 0 l -{width * .04:.1f} -{height * .05:.1f} m {width * .04:.1f} {height * .05:.1f} l -{width * .04:.1f} {height * .05:.1f}",
        "seal": f"M {left:.1f} {top:.1f} q {width * .05:.1f} -{height * .08:.1f} {width * .10:.1f} 0 q -{width * .05:.1f} {height * .08:.1f} -{width * .10:.1f} 0",
        "wave": f"M {left:.1f} {top:.1f} q {width * .035:.1f} -{height * .06:.1f} {width * .07:.1f} 0 q {width * .035:.1f} {height * .06:.1f} {width * .07:.1f} 0",
        "underline": f"M {left:.1f} {top:.1f} q {width * .08:.1f} {height * .04:.1f} {width * .16:.1f} 0",
    }
    return f'<path data-callout-shape="{escape(shape)}" d="{paths[shape]}" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round"/>'


def _render_canvas_svg(handoff: dict[str, Any], out: Path) -> Path:
    """Render the opt-in art-first Canvas map without legacy cluster shells."""
    width, height = _require_handoff(handoff)
    out = _safe_output_path(Path(out))
    profile = handoff["profile"]
    accent, secondary = str(profile["primary_accent"]), str(profile["secondary_accent"])
    headline = handoff["headline_zone"]
    headline_bounds = headline["bounds"]
    title_y = headline_bounds["y"] + height * .072
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="summary-title summary-desc">',
        f'<title id="summary-title">{escape(str(headline["title"]))} — canvas visual summary</title>',
        f'<desc id="summary-desc">{escape(str(headline["takeaway"]))} Scene-led visual map with a red relationship thread and evidence footer.</desc>',
        f'<rect width="{width}" height="{height}" fill="#FFF8EC" data-canvas-ground="warm-paper"/>',
        '<g data-canvas-layer="headline" aria-label="Summary headline and takeaway">',
        f'<path d="M {width * .04:.1f} {height * .12:.1f} C {width * .19:.1f} {height * .02:.1f} {width * .39:.1f} {height * .16:.1f} {width * .63:.1f} {height * .06:.1f}" fill="none" stroke="{secondary}" stroke-width="18" opacity=".18" stroke-linecap="round"/>',
        _svg_text(_wrap(str(headline["title"]), 28), headline_bounds["x"], title_y, height * .065, "#18202B", "700", _CANVAS_FONT_STACK),
        _svg_text(_wrap(str(headline["takeaway"]), 60), headline_bounds["x"], title_y + height * .10, height * .024, "#3C4655", "400", _CANVAS_FONT_STACK),
        '</g>',
    ]
    points = handoff.get("canvas_layout", {}).get("thread", {}).get("points", handoff["dominant_path"].get("points", []))
    if len(points) > 1:
        d = f'M {points[0]["x"]} {points[0]["y"]}'
        for point, following in zip(points[1:-1], points[2:]):
            d += f' Q {point["x"]} {point["y"]} {(point["x"] + following["x"]) / 2:.1f} {(point["y"] + following["y"]) / 2:.1f}'
        d += f' T {points[-1]["x"]} {points[-1]["y"]}'
        parts.extend([
            '<g data-canvas-layer="thread" aria-label="Hand-drawn Oracle-red dominant thread">',
            f'<path data-canvas-thread="oracle-red" d="{d}" fill="none" stroke="#C74634" stroke-width="11" stroke-linecap="round" stroke-linejoin="round"/>',
            '</g>',
        ])
    for cluster in handoff["clusters"]:
        art_bounds = cluster.get("art_bounds", cluster.get("art_slot", {}))
        text_bounds = cluster.get("text_bounds", cluster["bounds"])
        anchor_id = escape(str(cluster["anchor_id"]))
        role = escape(str(cluster.get("canvas_role", "scene")))
        parts.append(f'<g data-canvas-layer="scene-art" data-anchor-id="{anchor_id}" data-canvas-role="{role}" aria-label="Scene art for {escape(str(cluster["title"]))}">')
        art = _art_data_uri(cluster)
        if art and all(isinstance(art_bounds.get(key), int) for key in ("x", "y", "width", "height")):
            parts.append(f'<image data-scene-art="supplied" href="{art}" x="{art_bounds["x"]}" y="{art_bounds["y"]}" width="{art_bounds["width"]}" height="{art_bounds["height"]}" preserveAspectRatio="xMidYMid meet"/>')
        else:
            parts.append(f'<g data-scene-art="fallback-doodle" aria-label="Local text-free fallback doodle">{_svg_cluster_doodle(art_bounds, tuple(str(item) for item in profile.get("doodles", ())), secondary, seed=str(cluster["anchor_id"]), density="balanced")}</g>')
        parts.append('</g>')
        parts.append(f'<g data-canvas-layer="scene-annotation" data-anchor-id="{anchor_id}" aria-label="Scene annotation">')
        parts.append(_svg_text(_wrap(str(cluster["title"]), 22), text_bounds["x"], text_bounds["y"] + text_bounds["height"] * .18, height * .0235, "#18202B", "700", _CANVAS_FONT_STACK))
        parts.append(_svg_text(_wrap(str(cluster["detail"]), 34), text_bounds["x"], text_bounds["y"] + text_bounds["height"] * .46, height * .016, "#3C4655", "400", _CANVAS_FONT_STACK))
        parts.append('</g>')
    footer = str(handoff.get("evidence_footer", ""))
    if footer:
        parts.extend([
            '<g data-canvas-layer="evidence" aria-label="Evidence sources">',
            f'<path d="M {width * .07:.1f} {height * .93:.1f} q {width * .18:.1f} -{height * .015:.1f} {width * .38:.1f} 0" fill="none" stroke="{secondary}" stroke-width="3" opacity=".6"/>',
            _svg_text(_wrap(f"Evidence: {footer}", 78), width * .075, height * .955, height * .014, "#53606E", "400", _CANVAS_FONT_STACK),
            '</g>',
        ])
    parts.append('</svg>')
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return out


def render_svg(handoff: dict[str, Any], out: Path) -> Path:
    """Render the scalable canonical story-map preview locally."""
    width, height = _require_handoff(handoff)
    if _is_canvas_story_map(handoff):
        return _render_canvas_svg(handoff, out)
    out = _safe_output_path(Path(out))
    profile = handoff["profile"]
    accent, secondary = str(profile["primary_accent"]), str(profile["secondary_accent"])
    headline = handoff["headline_zone"]
    headline_bounds = headline["bounds"]
    doodles = tuple(str(item) for item in profile.get("doodles", ()))
    svg_title = f"{headline['title']} — {handoff.get('domain', 'project')} visual summary"
    svg_desc = (
        f"{headline['takeaway']} A {handoff.get('archetype', 'journey')} story map with "
        f"{len(handoff['clusters'])} grounded capability scenes and an evidence footer."
    )
    title_lines = _wrap(str(headline["title"]), 28)
    title_size = height * (.058 if len(title_lines) > 1 else .068)
    title_y = headline_bounds["y"] + height * .072
    takeaway_y = title_y + title_size * (1.22 * max(len(title_lines) - 1, 0) + .75)
    badge_y = takeaway_y + height * .066
    parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="summary-title summary-desc">',
        f'<title id="summary-title">{escape(svg_title)}</title>',
        f'<desc id="summary-desc">{escape(svg_desc)}</desc>',
        f'<rect width="{width}" height="{height}" fill="#FFFDF8"/>',
        '<g data-story-layer="headline" aria-label="Summary headline and takeaway">',
        f'<path d="M {width * .02:.1f} {height * .10:.1f} C {width * .17:.1f} {height * .03:.1f} {width * .34:.1f} {height * .15:.1f} {width * .52:.1f} {height * .08:.1f} S {width * .84:.1f} {height * .03:.1f} {width * .98:.1f} {height * .11:.1f}" fill="none" stroke="{secondary}" stroke-width="26" opacity=".14" stroke-linecap="round"/>',
        # Keep decorative gestures below the headline text; visual energy must
        # never look like a strike-through on the takeaway.
        f'<path d="M {width * .05:.1f} {badge_y + height * .075:.1f} Q {width * .34:.1f} {badge_y + height * .025:.1f} {width * .62:.1f} {badge_y + height * .075:.1f}" fill="none" stroke="{secondary}" stroke-width="4" opacity=".45"/>',
        f'<path data-ribbon-kind="takeaway" d="M {width * .07:.1f} {badge_y + height * .070:.1f} q {width * .08:.1f} {height * .020:.1f} {width * .19:.1f} 0 q {width * .08:.1f} -{height * .018:.1f} {width * .17:.1f} 0" fill="none" stroke="{accent}" stroke-width="7" stroke-linecap="round"/>',
        f'<path d="M {headline_bounds["x"] - width * .01:.1f} {headline_bounds["y"] + height * .165:.1f} '
        f'q {width * .06:.1f} -{height * .018:.1f} {width * .12:.1f} 0 '
        f'l {width * .10:.1f} 0 q {width * .03:.1f} 0 {width * .03:.1f} {height * .018:.1f} '
        f'q -{width * .02:.1f} {height * .018:.1f} -{width * .04:.1f} {height * .018:.1f} '
        f'l -{width * .18:.1f} 0 q -{width * .06:.1f} 0 -{width * .03:.1f} -{height * .018:.1f} Z" '
        f'fill="{secondary}" opacity=".16"/>',
        _svg_text(title_lines, headline_bounds["x"], title_y, title_size, "#18202B", "700"),
        _svg_text(_wrap(str(headline["takeaway"]), 60), headline_bounds["x"], takeaway_y, height * .024, "#3C4655"),
        _svg_badge_text(
            str(handoff.get("dominant_path_phrase", "")).title(),
            headline_bounds["x"] + width * .002,
            badge_y,
            width * .22,
            height * .035,
            secondary,
            accent,
        ),
        f'<path d="M {headline_bounds["x"]} {badge_y + height * .035:.1f} q {width * .06:.1f} {height * .012:.1f} {width * .14:.1f} 0" fill="none" stroke="{accent}" stroke-width="5" stroke-linecap="round"/>',
        f'<circle cx="{headline_bounds["x"] + width * .32:.1f}" cy="{headline_bounds["y"] + height * .065:.1f}" r="{height * .018:.1f}" fill="{secondary}" opacity=".24"/>',
        f'<circle cx="{headline_bounds["x"] + width * .36:.1f}" cy="{headline_bounds["y"] + height * .10:.1f}" r="{height * .010:.1f}" fill="{accent}" opacity=".34"/>',
        '</g>',
    ]
    points = handoff["dominant_path"].get("points", [])
    if len(points) > 1:
        d = f'M {points[0]["x"]} {points[0]["y"]}'
        for index, point in enumerate(points[1:-1], start=1):
            following = points[index + 1]
            d += f' Q {point["x"]} {point["y"]} {(point["x"] + following["x"]) / 2:.1f} {(point["y"] + following["y"]) / 2:.1f}'
        d += f' T {points[-1]["x"]} {points[-1]["y"]}'
        parts.append(f'<g data-story-layer="journey" aria-label="Dominant {escape(str(handoff.get("dominant_path_phrase", "journey")))}">')
        parts.append(f'<path d="{d}" fill="none" stroke="{accent}" stroke-width="12" stroke-linecap="round" stroke-linejoin="round" opacity=".84"/>')
        for marker_index, point in enumerate(points, start=1):
            parts.append(f'<g data-stage-marker="{marker_index}" aria-hidden="true">')
            parts.append(f'<circle cx="{point["x"]}" cy="{point["y"]}" r="{height * .011:.1f}" fill="#FFFDF8" stroke="{accent}" stroke-width="6"/>')
            parts.append(f'<circle cx="{point["x"]}" cy="{point["y"]}" r="{height * .017:.1f}" fill="none" stroke="{secondary}" stroke-width="3" opacity=".50"/>')
            parts.append('</g>')
        parts.append('</g>')
    elif points:
        point = points[0]
        parts.append(f'<circle cx="{point["x"]}" cy="{point["y"]}" r="{min(width, height) * .13:.1f}" fill="{secondary}" opacity=".28"/>')
    for cluster in handoff["clusters"]:
        bounds = cluster["bounds"]
        fill = "#FFFDF8"
        parts.append(f'<g data-story-layer="scene" data-anchor-id="{escape(str(cluster["anchor_id"]))}" aria-label="Scene {cluster.get("index", "")}: {escape(str(cluster["title"]))}">')
        parts.append(_svg_cluster_shell(bounds, str(cluster.get("silhouette", "cloud")), fill, accent))
        parts.append(f'<path d="M {bounds["x"] + bounds["width"] * .08:.1f} {bounds["y"] + bounds["height"] * .22:.1f} '
                     f'q {bounds["width"] * .10:.1f} -{bounds["height"] * .09:.1f} {bounds["width"] * .22:.1f} -{bounds["height"] * .04:.1f}" '
                     f'fill="none" stroke="{secondary}" stroke-width="4" opacity=".40" stroke-linecap="round"/>')
        parts.append(f'<circle cx="{bounds["x"] + bounds["width"] * .06:.1f}" cy="{bounds["y"] + bounds["height"] * .13:.1f}" r="{max(16, height * .018):.1f}" fill="{accent}"/>')
        parts.append(_svg_text([str(cluster.get("index", ""))], bounds["x"] + bounds["width"] * .048, bounds["y"] + bounds["height"] * .145, height * .016, "#FFFDF8", "700"))
        parts.append(_svg_badge_text(
            str(cluster.get("service_label", "")).upper(),
            bounds["x"] + bounds["width"] * .16,
            bounds["y"] + bounds["height"] * .055,
            bounds["width"] * .31,
            bounds["height"] * .12,
            secondary,
            accent,
        ))
        parts.append(_svg_text(_wrap(str(cluster["title"]), 18), bounds["x"] + bounds["width"] * .11, bounds["y"] + bounds["height"] * .33, height * .024, "#18202B", "700"))
        parts.append(_svg_text(_wrap(str(cluster["detail"]), 29), bounds["x"] + bounds["width"] * .11, bounds["y"] + bounds["height"] * .56, height * .016, "#3C4655"))
        parts.append(_svg_badge_text(
            str(cluster["evidence_class"]).upper(),
            bounds["x"] + bounds["width"] * .60,
            bounds["y"] + bounds["height"] * .83,
            bounds["width"] * .23,
            bounds["height"] * .10,
            accent,
            "#18202B",
        ))
        art, slot = _art_data_uri(cluster), cluster.get("art_slot", {})
        if art and all(isinstance(slot.get(key), int) for key in ("x", "y", "width", "height")):
            parts.append(f'<image href="{art}" x="{slot["x"]}" y="{slot["y"]}" width="{slot["width"]}" height="{slot["height"]}" preserveAspectRatio="xMidYMid slice"/>')
        else:
            parts.append(_svg_cluster_doodle(
                bounds,
                doodles,
                secondary,
                seed=str(cluster["anchor_id"]),
                density=str(handoff.get("doodle_density", "rich")),
            ))
        parts.append(_svg_callout(str(cluster["callout_shape"]), bounds, accent))
        parts.append('</g>')
    footer = str(handoff.get("evidence_footer", ""))
    if footer:
        parts.append('<g data-story-layer="evidence" aria-label="Evidence sources">')
        parts.append(
            f'<path d="M {width * .06:.1f} {height * .91:.1f} q {width * .12:.1f} -{height * .02:.1f} {width * .24:.1f} 0 '
            f'l {width * .22:.1f} 0 q {width * .04:.1f} 0 {width * .03:.1f} {height * .02:.1f} '
            f'q -{width * .02:.1f} {height * .03:.1f} -{width * .05:.1f} {height * .03:.1f} '
            f'l -{width * .42:.1f} 0 q -{width * .03:.1f} 0 -{width * .02:.1f} -{height * .03:.1f} Z" '
            f'fill="{secondary}" opacity=".12"/>'
        )
        parts.append(_svg_text(_wrap(f"Evidence: {footer}", 74), width * .075, height * .945, height * .014, "#53606E"))
        parts.append('</g>')
    parts.append("</svg>")
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return out


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _pdf_text(commands: list[str], lines: list[str], x: float, y: float, size: float, rgb: tuple[int, int, int], font: str = "F1") -> None:
    r, g, b = (channel / 255 for channel in rgb)
    for index, line in enumerate(lines):
        commands.append(f"BT /{font} {size:.2f} Tf {r:.3f} {g:.3f} {b:.3f} rg {x:.2f} {y - index * size * 1.22:.2f} Td ({_pdf_escape(line)}) Tj ET")


def _pdf_ellipse(commands: list[str], x: float, y: float, width: float, height: float, rgb: tuple[int, int, int]) -> None:
    """Draw an organic scene outline rather than a repeated rectangular card."""
    kappa = 0.55228475
    cx, cy, rx, ry = x + width / 2, y + height / 2, width / 2, height / 2
    r, g, b = (channel / 255 for channel in rgb)
    commands.append(f"{r:.3f} {g:.3f} {b:.3f} RG 1.4 w {cx + rx:.2f} {cy:.2f} m")
    commands.append(f"{cx + rx:.2f} {cy + kappa * ry:.2f} {cx + kappa * rx:.2f} {cy + ry:.2f} {cx:.2f} {cy + ry:.2f} c")
    commands.append(f"{cx - kappa * rx:.2f} {cy + ry:.2f} {cx - rx:.2f} {cy + kappa * ry:.2f} {cx - rx:.2f} {cy:.2f} c")
    commands.append(f"{cx - rx:.2f} {cy - kappa * ry:.2f} {cx - kappa * rx:.2f} {cy - ry:.2f} {cx:.2f} {cy - ry:.2f} c")
    commands.append(f"{cx + kappa * rx:.2f} {cy - ry:.2f} {cx + rx:.2f} {cy - kappa * ry:.2f} {cx + rx:.2f} {cy:.2f} c S")


def _render_pdf_with_art(handoff: dict[str, Any], out: Path, supplied_art: list[tuple[dict[str, Any], Path]]) -> Path:
    """Render the PDF through ReportLab when it is available.

    Canvas is intentionally assembled from the same composed PNG as the
    approved preview.  This prevents the PDF backend's smaller legacy
    typography and scene coordinates from diverging from the Canvas board.
    Editable text remains available in PPTX/DrawIO/Excalidraw; the Canvas PDF
    is the faithful visual handoff.
    """
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas

    width, height = _require_handoff(handoff)
    scale, page_w, page_h = 720 / width, 720, 720 * height / width
    accent = _hex_rgb(str(handoff["profile"]["primary_accent"]))
    canvas_out = canvas.Canvas(str(out), pagesize=(page_w, page_h))
    canvas_out.setFillColorRGB(1, .992, .972)
    canvas_out.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    if _is_canvas_story_map(handoff):
        canvas_out.addLiteral("% CANVAS composed PNG parity; THREAD oracle-red; EVIDENCE")
        composed_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(prefix=".canvas-composed-", suffix=".png", dir=out.parent, delete=False) as staged:
                composed_path = Path(staged.name)
            _render_canvas_png(handoff, composed_path, supplied_art)
            canvas_out.drawImage(ImageReader(str(composed_path)), 0, 0, width=page_w, height=page_h, preserveAspectRatio=False, mask="auto")
        finally:
            if composed_path is not None:
                composed_path.unlink(missing_ok=True)
        canvas_out.showPage()
        canvas_out.save()
        return out
        # Kept below as the explicit legacy branch boundary for non-Canvas
        # renderers; Canvas must never silently fall through to it.
        canvas_out.addLiteral("% CANVAS scene-led; THREAD oracle-red; EVIDENCE")
        headline = handoff["headline_zone"]["bounds"]
        canvas_out.setFillColorRGB(24 / 255, 32 / 255, 43 / 255)
        canvas_out.setFont("Helvetica-Bold", 22)
        for index, line in enumerate(_wrap(str(handoff["headline_zone"]["title"]), 38)):
            canvas_out.drawString(headline["x"] * scale, page_h - (headline["y"] * scale + 36 + index * 27), line)
        canvas_out.setFillColorRGB(60 / 255, 70 / 255, 85 / 255)
        canvas_out.setFont("Helvetica", 10)
        for index, line in enumerate(_wrap(str(handoff["headline_zone"]["takeaway"]), 64)):
            canvas_out.drawString(headline["x"] * scale, page_h - (headline["y"] * scale + 84 + index * 13), line)
        points = handoff["canvas_layout"]["thread"]["points"]
        if len(points) > 1:
            canvas_out.setStrokeColorRGB(199 / 255, 70 / 255, 52 / 255)
            canvas_out.setLineWidth(5)
            route = canvas_out.beginPath()
            route.moveTo(points[0]["x"] * scale, page_h - points[0]["y"] * scale)
            for previous, point in zip(points, points[1:]):
                px, py = previous["x"] * scale, page_h - previous["y"] * scale
                x, y = point["x"] * scale, page_h - point["y"] * scale
                route.curveTo(px + (x - px) * .34, py, x - (x - px) * .34, y, x, y)
            canvas_out.drawPath(route, stroke=1, fill=0)
        art_by_anchor = {cluster["anchor_id"]: path for cluster, path in supplied_art}
        for cluster in handoff["clusters"]:
            art_bounds = cluster.get("art_bounds", cluster["art_slot"])
            text_bounds = cluster.get("text_bounds", cluster["bounds"])
            x, y, w, h = (art_bounds[key] * scale for key in ("x", "y", "width", "height"))
            art_path = art_by_anchor.get(cluster["anchor_id"])
            canvas_out.setStrokeColorRGB(*(channel / 255 for channel in accent))
            canvas_out.setLineWidth(1.4)
            if art_path:
                canvas_out.drawImage(ImageReader(str(art_path)), x, page_h - y - h, w, h, preserveAspectRatio=True, anchor="c", mask="auto")
            else:
                canvas_out.circle(x + w * .48, page_h - y - h * .48, min(w, h) * .20, fill=0, stroke=1)
                canvas_out.line(x + w * .25, page_h - y - h * .70, x + w * .70, page_h - y - h * .30)
            tx, ty, tw, th = (text_bounds[key] * scale for key in ("x", "y", "width", "height"))
            canvas_out.setFillColorRGB(24 / 255, 32 / 255, 43 / 255)
            canvas_out.setFont("Helvetica-Bold", 9.5)
            for index, line in enumerate(_wrap(str(cluster["title"]), 22)):
                canvas_out.drawString(tx, page_h - (ty + th * .18 + index * 12), line)
            canvas_out.setFillColorRGB(60 / 255, 70 / 255, 85 / 255)
            canvas_out.setFont("Helvetica", 8)
            for index, line in enumerate(_wrap(str(cluster["detail"]), 34)):
                canvas_out.drawString(tx, page_h - (ty + th * .46 + index * 9), line)
        footer = str(handoff.get("evidence_footer", ""))
        if footer:
            canvas_out.setFillColorRGB(83 / 255, 96 / 255, 110 / 255)
            canvas_out.setFont("Helvetica", 6.5)
            canvas_out.drawString(page_w * .07, page_h * .05, f"Evidence: {footer}")
        canvas_out.showPage()
        canvas_out.save()
        return out
    headline = handoff["headline_zone"]["bounds"]
    canvas_out.setFillColorRGB(24 / 255, 32 / 255, 43 / 255)
    canvas_out.setFont("Helvetica-Bold", 22)
    for index, line in enumerate(_wrap(str(handoff["headline_zone"]["title"]), 38)):
        canvas_out.drawString(headline["x"] * scale, page_h - (headline["y"] * scale + 36 + index * 27), line)
    canvas_out.setFillColorRGB(60 / 255, 70 / 255, 85 / 255)
    canvas_out.setFont("Helvetica", 10)
    for index, line in enumerate(_wrap(str(handoff["headline_zone"]["takeaway"]), 64)):
        canvas_out.drawString(headline["x"] * scale, page_h - (headline["y"] * scale + 84 + index * 13), line)
    canvas_out.addLiteral("% RIBBON takeaway")
    canvas_out.setStrokeColorRGB(*(channel / 255 for channel in accent))
    canvas_out.setLineWidth(4)
    canvas_out.bezier(page_w * .07, page_h * .73, page_w * .16, page_h * .70, page_w * .24, page_h * .76, page_w * .34, page_h * .72)
    points = handoff.get("dominant_path", {}).get("points", [])
    if len(points) > 1:
        route = canvas_out.beginPath()
        route.moveTo(points[0]["x"] * scale, page_h - points[0]["y"] * scale)
        for previous, point in zip(points, points[1:]):
            px, py = previous["x"] * scale, page_h - previous["y"] * scale
            x, y = point["x"] * scale, page_h - point["y"] * scale
            route.curveTo(px + (x - px) * .34, py, x - (x - px) * .34, y, x, y)
        canvas_out.setLineWidth(5)
        canvas_out.drawPath(route, stroke=1, fill=0)
        for point in points:
            x, y = point["x"] * scale, page_h - point["y"] * scale
            canvas_out.setFillColorRGB(1, .992, .972)
            canvas_out.circle(x, y, 7, fill=1, stroke=1)
            canvas_out.setFillColorRGB(*(channel / 255 for channel in accent))
            canvas_out.circle(x, y, 2.5, fill=1, stroke=0)
    for cluster in handoff["clusters"]:
        bounds = cluster["bounds"]
        x, y, w, h = (bounds[key] * scale for key in ("x", "y", "width", "height"))
        canvas_out.addLiteral(f"% CALLOUT {cluster['callout_shape']}")
        canvas_out.setLineWidth(1.4)
        canvas_out.ellipse(x - w * .05, page_h - y - h * 1.08, x + w * 1.05, page_h - y + h * .08, fill=0, stroke=1)
        sx, sy = x + w * .72, page_h - (y + h * .76)
        ex, ey = x + w * .87, page_h - (y + h * .70)
        if cluster["callout_shape"] == "ribbon":
            path = canvas_out.beginPath()
            path.moveTo(sx, sy)
            path.curveTo((sx + ex) / 2, sy + h * .05, (sx + ex) / 2, ey - h * .05, ex, ey)
            canvas_out.drawPath(path, stroke=1, fill=0)
        elif cluster["callout_shape"] == "speech-tail":
            canvas_out.line(sx, sy, ex, ey)
            canvas_out.line(ex, ey, ex - w * .04, ey - h * .10)
        elif cluster["callout_shape"] == "torn-note":
            canvas_out.line(sx, sy, sx + w * .05, sy - h * .06)
            canvas_out.line(sx + w * .05, sy - h * .06, sx + w * .10, sy)
            canvas_out.line(sx + w * .10, sy, ex, ey)
        elif cluster["callout_shape"] == "bracket":
            canvas_out.line(sx, sy, sx + w * .06, sy)
            canvas_out.line(sx + w * .06, sy, sx + w * .06, ey)
            canvas_out.line(sx + w * .06, ey, ex, ey)
        elif cluster["callout_shape"] == "arrow-tab":
            canvas_out.line(sx, sy, ex, sy)
            canvas_out.line(ex, sy, ex - w * .04, sy + h * .05)
            canvas_out.line(ex, sy, ex - w * .04, sy - h * .05)
        elif cluster["callout_shape"] == "seal":
            canvas_out.circle((sx + ex) / 2, (sy + ey) / 2, min(w, h) * .055, fill=0, stroke=1)
        elif cluster["callout_shape"] == "wave":
            path = canvas_out.beginPath()
            path.moveTo(sx, sy)
            path.curveTo(sx + w * .035, sy + h * .06, sx + w * .035, sy - h * .06, sx + w * .07, sy)
            path.curveTo(sx + w * .105, sy + h * .06, sx + w * .105, sy - h * .06, sx + w * .14, sy)
            canvas_out.drawPath(path, stroke=1, fill=0)
        elif cluster["callout_shape"] == "underline":
            path = canvas_out.beginPath()
            path.moveTo(sx, sy)
            path.curveTo(sx + w * .05, sy - h * .04, sx + w * .11, sy - h * .04, ex, ey)
            canvas_out.drawPath(path, stroke=1, fill=0)
        else:
            canvas_out.line(sx, sy, ex, ey)
        canvas_out.setFillColorRGB(24 / 255, 32 / 255, 43 / 255)
        canvas_out.setFont("Helvetica-Bold", 10)
        for index, line in enumerate(_wrap(str(cluster["title"]), 21)):
            canvas_out.drawString(x + w * .08, page_h - (y + h * .27 + index * 12), line)
        canvas_out.setFont("Helvetica", 7.5)
        canvas_out.setFillColorRGB(60 / 255, 70 / 255, 85 / 255)
        for index, line in enumerate(_wrap(str(cluster["detail"]), 27)):
            canvas_out.drawString(x + w * .08, page_h - (y + h * .56 + index * 9), line)
        canvas_out.setFillColorRGB(*(channel / 255 for channel in accent))
        canvas_out.setFont("Helvetica-Bold", 6.5)
        canvas_out.drawString(x + w * .66, page_h - (y + h * .19), str(cluster["evidence_class"]).upper())
        # Text-free sketch marks keep PDF parity with the SVG story-map grammar.
        canvas_out.setStrokeColorRGB(*(channel / 255 for channel in accent))
        canvas_out.setLineWidth(1.4)
        dx, dy = x + w * .78, page_h - (y + h * .30)
        for hatch in range(4):
            canvas_out.line(dx + hatch * 5, dy + (hatch % 2) * 2, dx + hatch * 5 + 4, dy + 9 + (hatch % 2) * 2)
        canvas_out.circle(dx + 25, dy + 12, 4, fill=0, stroke=1)
    for cluster, art_path in supplied_art:
        slot = cluster["art_slot"]
        canvas_out.drawImage(ImageReader(str(art_path)), slot["x"] * scale, page_h - (slot["y"] + slot["height"]) * scale, slot["width"] * scale, slot["height"] * scale, preserveAspectRatio=True, mask="auto")
    footer = str(handoff.get("evidence_footer", ""))
    if footer:
        canvas_out.setFillColorRGB(83 / 255, 96 / 255, 110 / 255)
        canvas_out.setFont("Helvetica", 6.5)
        canvas_out.drawString(page_w * .07, page_h * .05, f"Evidence: {footer}")
    canvas_out.showPage()
    canvas_out.save()
    return out


def _write_basic_pdf(out: Path, page_w: float, page_h: float, commands: list[str]) -> Path:
    """Write a small selectable-text PDF without depending on a system renderer."""
    stream = "\n".join(commands).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>" % (page_w, page_h)).encode("ascii"),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    ]
    payload = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{index} 0 obj\n".encode("ascii"))
        payload.extend(obj)
        payload.extend(b"\nendobj\n")
    startxref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode("ascii"))
    out.write_bytes(payload)
    return out


def _render_canvas_pdf_fallback(handoff: dict[str, Any], out: Path) -> Path:
    """Keep Canvas geometry and deterministic text when ReportLab is absent."""
    width, height = _require_handoff(handoff)
    scale, page_w, page_h = 720 / width, 720, 720 * height / width
    commands = ["1 0.973 0.925 rg 0 0 %.2f %.2f re f" % (page_w, page_h), "% CANVAS scene-led; THREAD oracle-red; EVIDENCE"]
    headline = handoff["headline_zone"]["bounds"]
    _pdf_text(commands, _wrap(str(handoff["headline_zone"]["title"]), 38), headline["x"] * scale, page_h - (headline["y"] * scale + 36), 22, (24, 32, 43), "F2")
    _pdf_text(commands, _wrap(str(handoff["headline_zone"]["takeaway"]), 64), headline["x"] * scale, page_h - (headline["y"] * scale + 84), 10, (60, 70, 85))
    points = handoff["canvas_layout"]["thread"]["points"]
    if len(points) > 1:
        commands.append("0.780 0.275 0.204 RG 5 w")
        commands.append("%.2f %.2f m" % (points[0]["x"] * scale, page_h - points[0]["y"] * scale))
        for previous, point in zip(points, points[1:]):
            dx = (point["x"] - previous["x"]) * scale
            commands.append("%.2f %.2f %.2f %.2f %.2f %.2f c" % (previous["x"] * scale + dx * .34, page_h - previous["y"] * scale, point["x"] * scale - dx * .34, page_h - point["y"] * scale, point["x"] * scale, page_h - point["y"] * scale))
        commands.append("S")
    for cluster in handoff["clusters"]:
        art_bounds = cluster.get("art_bounds", cluster["art_slot"])
        text_bounds = cluster.get("text_bounds", cluster["bounds"])
        x, y, w, h = (art_bounds[key] * scale for key in ("x", "y", "width", "height"))
        # A bounded local doodle keeps missing art expressive without turning
        # the Canvas scenes back into a repeated rectangular card system.
        center_x, center_y = x + w * .48, page_h - y - h * .48
        radius_x, radius_y = w * .24, h * .22
        commands.append("0.780 0.275 0.204 RG 1.4 w %.2f %.2f m" % (center_x + radius_x, center_y))
        commands.append("%.2f %.2f %.2f %.2f %.2f %.2f c" % (center_x + radius_x, center_y + radius_y * .55, center_x + radius_x * .55, center_y + radius_y, center_x, center_y + radius_y))
        commands.append("%.2f %.2f %.2f %.2f %.2f %.2f c" % (center_x - radius_x * .55, center_y + radius_y, center_x - radius_x, center_y + radius_y * .55, center_x - radius_x, center_y))
        commands.append("%.2f %.2f %.2f %.2f %.2f %.2f c" % (center_x - radius_x, center_y - radius_y * .55, center_x - radius_x * .55, center_y - radius_y, center_x, center_y - radius_y))
        commands.append("%.2f %.2f %.2f %.2f %.2f %.2f c S" % (center_x + radius_x * .55, center_y - radius_y, center_x + radius_x, center_y - radius_y * .55, center_x + radius_x, center_y))
        for hatch in range(3):
            offset = hatch * min(w, h) * .07
            commands.append("0.420 0.360 0.655 RG 1 w %.2f %.2f m %.2f %.2f l S" % (center_x - radius_x * .45 + offset, center_y - radius_y * .50, center_x - radius_x * .15 + offset, center_y - radius_y * .10))
        tx, ty, tw, th = (text_bounds[key] * scale for key in ("x", "y", "width", "height"))
        _pdf_text(commands, _wrap(str(cluster["title"]), 20), tx, page_h - (ty + th * .30), 9, (24, 32, 43), "F2")
        _pdf_text(commands, _wrap(str(cluster["detail"]), 30), tx, page_h - (ty + th * .66), 7, (60, 70, 85))
    footer = str(handoff.get("evidence_footer", ""))
    if footer:
        _pdf_text(commands, _wrap(f"Evidence: {footer}", 90), page_w * .07, page_h * .05, 6.5, (83, 96, 110))
    return _write_basic_pdf(out, page_w, page_h, commands)


def render_pdf(handoff: dict[str, Any], out: Path) -> Path:
    """Render one selectable-text PDF page without a remote renderer."""
    width, height = _require_handoff(handoff)
    out = _safe_output_path(Path(out))
    supplied_art = _require_art_backend(handoff, "reportlab")
    if _reportlab_available():
        return _render_pdf_with_art(handoff, out, supplied_art)
    if _is_canvas_story_map(handoff):
        return _render_canvas_pdf_fallback(handoff, out)
    scale = 720 / width
    page_w, page_h = 720, 720 * height / width
    accent = _hex_rgb(str(handoff["profile"]["primary_accent"]))
    headline = handoff["headline_zone"]["bounds"]
    commands = ["1 0.992 0.972 rg 0 0 %.2f %.2f re f" % (page_w, page_h)]
    _pdf_text(commands, _wrap(str(handoff["headline_zone"]["title"]), 38), headline["x"] * scale, page_h - (headline["y"] * scale + 36), 22, (24, 32, 43), "F2")
    _pdf_text(commands, _wrap(str(handoff["headline_zone"]["takeaway"]), 64), headline["x"] * scale, page_h - (headline["y"] * scale + 84), 10, (60, 70, 85))
    commands.append("% RIBBON takeaway")
    commands.append("%.3f %.3f %.3f RG 4 w %.2f %.2f m %.2f %.2f %.2f %.2f %.2f %.2f c S" % (
        *[channel / 255 for channel in accent], page_w * .07, page_h * .73, page_w * .16, page_h * .70, page_w * .24, page_h * .76, page_w * .34, page_h * .72,
    ))
    points = handoff["dominant_path"].get("points", [])
    if len(points) > 1:
        commands.append("%.3f %.3f %.3f RG 5 w" % tuple(channel / 255 for channel in accent))
        commands.append("%.2f %.2f m" % (points[0]["x"] * scale, page_h - points[0]["y"] * scale))
        for current, point in zip(points, points[1:]):
            dx = (point["x"] - current["x"]) * scale
            commands.append("%.2f %.2f %.2f %.2f %.2f %.2f c" % (
                current["x"] * scale + dx * .35,
                page_h - current["y"] * scale,
                point["x"] * scale - dx * .35,
                page_h - point["y"] * scale,
                point["x"] * scale,
                page_h - point["y"] * scale,
            ))
        commands.append("S")
    for cluster in handoff["clusters"]:
        bounds = cluster["bounds"]
        x, y, w, h = (bounds[key] * scale for key in ("x", "y", "width", "height"))
        commands.append(f"% CALLOUT {cluster['callout_shape']}")
        _pdf_ellipse(commands, x - w * .05, page_h - y - h * 1.08, w * 1.1, h * 1.16, accent)
        sx, sy = x + w * .72, page_h - (y + h * .76)
        ex, ey = x + w * .87, page_h - (y + h * .70)
        prefix = "%.3f %.3f %.3f RG 2 w" % tuple(channel / 255 for channel in accent)
        shape = cluster["callout_shape"]
        if shape == "ribbon":
            commands.append(f"{prefix} {sx:.2f} {sy:.2f} m {(sx + ex) / 2:.2f} {sy + h * .05:.2f} {(sx + ex) / 2:.2f} {ey - h * .05:.2f} {ex:.2f} {ey:.2f} c S")
        elif shape == "speech-tail":
            commands.append(f"{prefix} {sx:.2f} {sy:.2f} m {ex:.2f} {ey:.2f} l {ex - w * .04:.2f} {ey - h * .10:.2f} l S")
        elif shape == "torn-note":
            commands.append(f"{prefix} {sx:.2f} {sy:.2f} m {sx + w * .05:.2f} {sy - h * .06:.2f} l {sx + w * .10:.2f} {sy:.2f} l {ex:.2f} {ey:.2f} l S")
        elif shape == "bracket":
            commands.append(f"{prefix} {sx:.2f} {sy:.2f} m {sx + w * .06:.2f} {sy:.2f} l {sx + w * .06:.2f} {ey:.2f} l {ex:.2f} {ey:.2f} l S")
        elif shape == "arrow-tab":
            commands.append(f"{prefix} {sx:.2f} {sy:.2f} m {ex:.2f} {sy:.2f} l {ex - w * .04:.2f} {sy + h * .05:.2f} l {ex:.2f} {sy:.2f} m {ex - w * .04:.2f} {sy - h * .05:.2f} l S")
        elif shape == "seal":
            _pdf_ellipse(commands, (sx + ex) / 2 - min(w, h) * .055, (sy + ey) / 2 - min(w, h) * .055, min(w, h) * .11, min(w, h) * .11, accent)
        elif shape == "wave":
            commands.append(f"{prefix} {sx:.2f} {sy:.2f} m {sx + w * .035:.2f} {sy + h * .06:.2f} {sx + w * .035:.2f} {sy - h * .06:.2f} {sx + w * .07:.2f} {sy:.2f} c {sx + w * .105:.2f} {sy + h * .06:.2f} {sx + w * .105:.2f} {sy - h * .06:.2f} {sx + w * .14:.2f} {sy:.2f} c S")
        elif shape == "underline":
            commands.append(f"{prefix} {sx:.2f} {sy:.2f} m {sx + w * .05:.2f} {sy - h * .04:.2f} {sx + w * .11:.2f} {sy - h * .04:.2f} {ex:.2f} {ey:.2f} c S")
        else:
            commands.append(f"{prefix} {sx:.2f} {sy:.2f} m {ex:.2f} {ey:.2f} l S")
        _pdf_text(commands, _wrap(str(cluster["title"]), 21), x + w * .08, page_h - (y + h * .27), 10, (24, 32, 43), "F2")
        _pdf_text(commands, _wrap(str(cluster["detail"]), 27), x + w * .08, page_h - (y + h * .56), 7.5, (60, 70, 85))
        _pdf_text(commands, [str(cluster["evidence_class"]).upper()], x + w * .66, page_h - (y + h * .19), 6.5, accent, "F2")
    footer = str(handoff.get("evidence_footer", ""))
    if footer:
        _pdf_text(commands, _wrap(f"Evidence: {footer}", 90), page_w * .07, page_h * .05, 6.5, (83, 96, 110))
    stream = "\n".join(commands).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        ("<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %.2f %.2f] /Resources << /Font << /F1 5 0 R /F2 6 0 R >> >> /Contents 4 0 R >>" % (page_w, page_h)).encode("ascii"),
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
    ]
    payload = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(payload))
        payload.extend(f"{index} 0 obj\n".encode("ascii"))
        payload.extend(obj)
        payload.extend(b"\nendobj\n")
    startxref = len(payload)
    payload.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode("ascii"))
    for offset in offsets[1:]:
        payload.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    payload.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{startxref}\n%%EOF\n".encode("ascii"))
    out.write_bytes(payload)
    return out


def _png_chunk(name: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + name + data + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)


_PIXEL_GLYPHS = {
    "A": ("010", "101", "111", "101", "101"), "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"), "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"), "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"), "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"), "J": ("001", "001", "001", "101", "010"),
    "K": ("101", "101", "110", "101", "101"), "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"), "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"), "P": ("110", "101", "110", "100", "100"),
    "Q": ("010", "101", "101", "011", "001"), "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"), "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"), "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"), "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"), "Z": ("111", "001", "010", "100", "111"),
    "0": ("111", "101", "101", "101", "111"), "1": ("010", "110", "010", "010", "111"),
    "2": ("110", "001", "010", "100", "111"), "3": ("110", "001", "010", "001", "110"),
    "4": ("101", "101", "111", "001", "001"), "5": ("111", "100", "110", "001", "110"),
    "6": ("011", "100", "111", "101", "111"), "7": ("111", "001", "010", "010", "010"),
    "8": ("111", "101", "111", "101", "111"), "9": ("111", "101", "111", "001", "110"),
    "-": ("000", "000", "111", "000", "000"), ".": ("000", "000", "000", "000", "010"),
    ":": ("000", "010", "000", "010", "000"), ",": ("000", "000", "000", "010", "100"),
}


def _render_canvas_png(handoff: dict[str, Any], out: Path, supplied_art: list[tuple[dict[str, Any], Path]]) -> Path:
    """Rasterize the Canvas map with native readable type and generous scenes."""
    width, height = _require_handoff(handoff)
    try:
        from PIL import Image, ImageDraw, ImageFont, ImageOps
        from PIL.PngImagePlugin import PngInfo
    except ImportError:
        # Keep the documented dependency-free CLI contract for minimal Python
        # environments; the bundled runtime takes the native-font path above.
        return _render_canvas_png_fallback(handoff, out)

    base = Image.new("RGBA", (width, height), (255, 248, 236, 255))
    draw = ImageDraw.Draw(base)
    red, secondary = (199, 70, 52), _hex_rgb(str(handoff["profile"]["secondary_accent"]))
    ink, body, muted = (24, 32, 43), (60, 70, 85), (83, 96, 110)
    font_paths = (
        "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
        "/System/Library/Fonts/Supplemental/Chalkboard.ttc",
    )

    def font(size: int, bold: bool = False):
        candidates = font_paths if not bold else (font_paths[0], font_paths[1])
        for path in candidates:
            try:
                return ImageFont.truetype(path, max(10, size))
            except (OSError, TypeError):
                continue
        return ImageFont.load_default()

    def wrap(value: str, fnt, max_width: int) -> list[str]:
        words, lines, current = str(value).split(), [], ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if current and draw.textbbox((0, 0), candidate, font=fnt)[2] > max_width:
                lines.append(current)
                current = word
            else:
                current = candidate
        if current:
            lines.append(current)
        return lines or [""]

    def organic_blob(bounds: dict[str, int], fill: tuple[int, int, int, int], outline: tuple[int, int, int], seed: int) -> None:
        x, y, w, h = (bounds[k] for k in ("x", "y", "width", "height"))
        points = []
        for idx in range(18):
            angle = 6.283185307179586 * idx / 18
            wobble = 1 + (((idx * 17 + seed * 7) % 13) - 6) / 55
            points.append((x + w / 2 + cos(angle) * w * .52 * wobble, y + h / 2 + sin(angle) * h * .50 * wobble))
        draw.polygon(points, fill=fill, outline=outline)

    # Title and takeaway occupy a visible header band, leaving a small paper
    # margin rather than an empty upper half.
    title_font, takeaway_font = font(round(height * .058), True), font(round(height * .027))
    title_x, title_y = round(width * .06), round(height * .045)
    title_lines = wrap(handoff["headline_zone"]["title"], title_font, round(width * .88))
    draw.text((title_x, title_y), "\n".join(title_lines), fill=ink, font=title_font, spacing=2)
    title_bottom = title_y + len(title_lines) * round(title_font.size * 1.08)
    takeaway_y = title_bottom + round(height * .008)
    takeaway_lines = wrap(handoff["headline_zone"]["takeaway"], takeaway_font, round(width * .82))
    draw.text((title_x, takeaway_y), "\n".join(takeaway_lines), fill=body, font=takeaway_font, spacing=5)
    takeaway_bottom = takeaway_y + len(takeaway_lines) * round(takeaway_font.size * 1.18)
    arc_y = min(round(height * .245), takeaway_bottom + round(height * .012))
    draw.arc((width * .04, arc_y - height * .018, width * .96, arc_y + height * .028), 185, 355, fill=secondary, width=max(3, round(height * .008)))

    # A hand-drawn red control thread connects the scenes.
    points = handoff["canvas_layout"]["thread"]["points"]
    for first, second in zip(points, points[1:]):
        mid = ((first["x"] + second["x"]) // 2, (first["y"] + second["y"]) // 2 + (12 if first["y"] < second["y"] else -12))
        draw.line([(first["x"], first["y"]), mid, (second["x"], second["y"])], fill=red, width=max(5, round(height * .010)), joint="curve")
    for point in points:
        draw.ellipse((point["x"] - 9, point["y"] - 9, point["x"] + 9, point["y"] + 9), fill=(255, 248, 236, 255), outline=red, width=4)

    art_lookup = {id(cluster): art_path for cluster, art_path in supplied_art}
    for index, cluster in enumerate(handoff["clusters"], start=1):
        art = cluster.get("art_bounds", cluster["art_slot"])
        text_bounds = cluster.get("text_bounds", cluster["bounds"])
        organic_blob(art, (255, 253, 248, 235), secondary, index)
        art_path = art_lookup.get(id(cluster))
        if art_path:
            image = Image.open(art_path).convert("RGBA")
            image = ImageOps.contain(image, (art["width"] - 18, art["height"] - 18), Image.Resampling.LANCZOS)
            base.alpha_composite(image, (art["x"] + (art["width"] - image.width) // 2, art["y"] + (art["height"] - image.height) // 2))
        else:
            # Small expressive local motif keeps missing art visibly intentional.
            cx, cy = art["x"] + art["width"] // 2, art["y"] + art["height"] // 2
            draw.ellipse((cx - art["width"] * .19, cy - art["height"] * .25, cx + art["width"] * .19, cy + art["height"] * .25), outline=red, width=4)
            draw.line((cx - art["width"] * .12, cy + art["height"] * .12, cx + art["width"] * .12, cy - art["height"] * .12), fill=secondary, width=3)
        title_f, detail_f, label_f = font(round(height * .024), True), font(round(height * .014)), font(round(height * .013), True)
        tx, ty, tw = text_bounds["x"], text_bounds["y"], text_bounds["width"]
        display_title = str(cluster["title"])
        prefix = f"{index}. "
        if display_title.startswith(prefix):
            display_title = display_title[len(prefix):]
        draw.text((tx, ty), f"{index}. {display_title}", fill=ink, font=title_f, spacing=2, stroke_width=0)
        label = str(cluster.get("service_label", "")).upper()
        # Put the service tag between title and detail so it cannot collide
        # with the final detail line in short lower-band scenes.
        label_y = ty + round(title_f.size * 1.18)
        pill = draw.textbbox((tx, label_y), label, font=label_f)
        draw.rounded_rectangle((tx - 6, label_y - 3, min(tx + tw, pill[2] + 12), pill[3] + 4), radius=8, fill=(secondary[0], secondary[1], secondary[2], 38), outline=secondary, width=2)
        draw.text((tx, label_y), label, fill=red, font=label_f)
        detail_y = label_y + round(label_f.size * 1.45)
        detail_lines = wrap(cluster["detail"], detail_f, tw)
        draw.text((tx, detail_y), "\n".join(detail_lines), fill=body, font=detail_f, spacing=2)
        evidence = str(cluster.get("evidence_class", "")).upper()
        draw.text((tx + tw - draw.textbbox((0, 0), evidence, font=label_f)[2], label_y), evidence, fill=muted, font=label_f)
    footer = str(handoff.get("evidence_footer", ""))
    if footer:
        footer_f = font(round(height * .014))
        draw.text((round(width * .06), round(height * .955)), f"Evidence: {footer}", fill=muted, font=footer_f)
    metadata = PngInfo()
    metadata.add_text("VisualSummary", "CANVAS scene-led; THREAD oracle-red; EVIDENCE")
    base.convert("RGB").save(out, format="PNG", optimize=True, pnginfo=metadata)
    return out


def _render_canvas_png_fallback(handoff: dict[str, Any], out: Path) -> Path:
    """Small dependency-free fallback used only when PIL is unavailable."""
    width, height = _require_handoff(handoff)
    pixels = bytearray(b"\xff\xf8\xec" * width * height)
    red, secondary = (199, 70, 52), _hex_rgb(str(handoff["profile"]["secondary_accent"]))

    def dot(x: int, y: int, color: tuple[int, int, int], radius: int = 1) -> None:
        for py in range(max(0, y - radius), min(height, y + radius + 1)):
            for px in range(max(0, x - radius), min(width, x + radius + 1)):
                offset = (py * width + px) * 3
                pixels[offset:offset + 3] = bytes(color)

    def line(x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int], thickness: int = 2) -> None:
        steps = max(abs(x2 - x1), abs(y2 - y1), 1)
        for step in range(steps + 1):
            dot(round(x1 + (x2 - x1) * step / steps), round(y1 + (y2 - y1) * step / steps), color, thickness)

    for first, second in zip(handoff["canvas_layout"]["thread"]["points"], handoff["canvas_layout"]["thread"]["points"][1:]):
        line(first["x"], first["y"], second["x"], second["y"], red, max(3, width // 420))
    for cluster in handoff["clusters"]:
        art = cluster.get("art_bounds", cluster["art_slot"])
        cx, cy = art["x"] + art["width"] // 2, art["y"] + art["height"] // 2
        for step in range(24):
            angle = step * 6.283185307179586 / 23
            dot(round(cx + cos(angle) * art["width"] * .38), round(cy + sin(angle) * art["height"] * .40), secondary, 1)
        line(cx - art["width"] // 6, cy + art["height"] // 6, cx + art["width"] // 6, cy - art["height"] // 6, red, 2)
    raw = b"".join(b"\x00" + bytes(pixels[row * width * 3:(row + 1) * width * 3]) for row in range(height))
    out.write_bytes(b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + _png_chunk(b"tEXt", b"VisualSummary\x00CANVAS scene-led; THREAD oracle-red; EVIDENCE") + _png_chunk(b"IDAT", zlib.compress(raw, 9)) + _png_chunk(b"IEND", b""))
    return out


def render_png(handoff: dict[str, Any], out: Path) -> Path:
    """Render a sharp, dependency-free local PNG using the shared composition."""
    width, height = _require_handoff(handoff)
    supplied_art = _require_art_backend(handoff, "PIL")
    out = _safe_output_path(Path(out))
    if _is_canvas_story_map(handoff):
        return _render_canvas_png(handoff, out, supplied_art)
    pixels = bytearray(b"\xff\xfd\xf8" * width * height)
    accent, secondary = _hex_rgb(str(handoff["profile"]["primary_accent"])), _hex_rgb(str(handoff["profile"]["secondary_accent"]))
    ink = (24, 32, 43)
    body = (60, 70, 85)
    footer_ink = (83, 96, 110)

    def dot(x: int, y: int, color: tuple[int, int, int], radius: int = 1) -> None:
        for py in range(max(0, y - radius), min(height, y + radius + 1)):
            for px in range(max(0, x - radius), min(width, x + radius + 1)):
                position = (py * width + px) * 3
                pixels[position:position + 3] = bytes(color)

    def line(x1: int, y1: int, x2: int, y2: int, color: tuple[int, int, int], thickness: int = 2) -> None:
        steps = max(abs(x2 - x1), abs(y2 - y1), 1)
        for step in range(steps + 1):
            dot(round(x1 + (x2 - x1) * step / steps), round(y1 + (y2 - y1) * step / steps), color, thickness)

    def ellipse(x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
        for step in range(241):
            angle = 6.283185307179586 * step / 240
            dot(round(x + w / 2 + w * .55 * cos(angle) / 2), round(y + h / 2 + h * .58 * sin(angle) / 2), color, 1)

    def filled_ellipse(x: int, y: int, w: int, h: int, fill: tuple[int, int, int], outline: tuple[int, int, int] | None = None) -> None:
        rx = max(1, int(w * .52))
        ry = max(1, int(h * .56))
        cx = x + w // 2
        cy = y + h // 2
        for py in range(max(0, y - 2), min(height, y + h + 2)):
            dy = (py - cy) / ry
            if abs(dy) > 1:
                continue
            span = int(rx * (1 - dy * dy) ** 0.5)
            for px in range(max(0, cx - span), min(width, cx + span + 1)):
                position = (py * width + px) * 3
                pixels[position:position + 3] = bytes(fill)
        if outline is not None:
            ellipse(x, y, w, h, outline)

    def rect(x: int, y: int, w: int, h: int, fill: tuple[int, int, int]) -> None:
        for py in range(max(0, y), min(height, y + h)):
            for px in range(max(0, x), min(width, x + w)):
                position = (py * width + px) * 3
                pixels[position:position + 3] = bytes(fill)

    def text(x: int, y: int, value: str, color: tuple[int, int, int], scale: int) -> None:
        cursor = x
        for glyph in value.upper():
            if glyph == " ":
                cursor += 2 * scale
                continue
            for row, pattern in enumerate(_PIXEL_GLYPHS.get(glyph, _PIXEL_GLYPHS["-"])):
                for column, bit in enumerate(pattern):
                    if bit == "1":
                        for py in range(scale):
                            for px in range(scale):
                                dot(cursor + column * scale + px, y + row * scale + py, color)
            cursor += 4 * scale

    def shade(base: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
        return tuple(max(0, min(255, round(channel + (255 - channel) * factor))) for channel in base)

    for index in range(160):
        dot(
            (137 * index + 53) % width,
            (89 * index + 211) % height,
            shade(secondary, 0.52),
            1,
        )
    line(round(width * .02), round(height * .10), round(width * .98), round(height * .10), shade(secondary, 0.72), max(7, width // 170))
    points = handoff["dominant_path"].get("points", [])
    rect(int(width * .07), int(height * .19), int(width * .18), max(12, height // 35), shade(secondary, 0.78))
    line(round(width * .07), round(height * .225), round(width * .34), round(height * .225), accent, max(3, width // 700))
    for first, second in zip(points, points[1:]):
        line(first["x"], first["y"], second["x"], second["y"], accent, max(4, width // 420))
    for point in points:
        dot(point["x"], point["y"], accent, max(8, width // 240))
        ellipse(point["x"] - max(18, width // 90), point["y"] - max(18, width // 90), max(36, width // 45), max(36, width // 45), shade(secondary, 0.36))
    for cluster in handoff["clusters"]:
        bounds = cluster["bounds"]
        x, y, w, h = (bounds[key] for key in ("x", "y", "width", "height"))
        filled_ellipse(x - w // 20, y - h // 12, w + w // 10, h + h // 6, shade(secondary, 0.84), accent)
        dot(x + max(18, w // 16), y + max(16, h // 9), accent, max(10, width // 180))
        text(x + max(12, w // 28), y + max(4, h // 22), str(cluster.get("index", "")), (255, 253, 248), 2)
        rect(x + w // 6, y + max(6, h // 24), max(84, w // 4), max(14, h // 9), shade(secondary, 0.72))
        text(x + w // 6 + 10, y + max(8, h // 20), str(cluster.get("service_label", "")), accent, 2)
        callout_start = (x + int(w * .72), y + int(h * .76))
        callout_end = (x + int(w * .87), y + int(h * .70))
        thickness = max(1, width // 1200)
        shape = cluster["callout_shape"]
        if shape == "ribbon":
            line(*callout_start, callout_start[0] + w // 12, callout_start[1] - h // 14, accent, thickness)
            line(callout_start[0] + w // 12, callout_start[1] - h // 14, *callout_end, accent, thickness)
        elif shape == "speech-tail":
            line(*callout_start, *callout_end, accent, thickness)
            line(*callout_end, callout_end[0] - max(4, w // 20), callout_end[1] - max(4, h // 10), accent, thickness)
        elif shape == "torn-note":
            line(*callout_start, callout_start[0] + w // 20, callout_start[1] - h // 16, accent, thickness)
            line(callout_start[0] + w // 20, callout_start[1] - h // 16, callout_start[0] + w // 10, callout_start[1], accent, thickness)
            line(callout_start[0] + w // 10, callout_start[1], *callout_end, accent, thickness)
        elif shape == "bracket":
            line(*callout_start, callout_start[0] + w // 18, callout_start[1], accent, thickness)
            line(callout_start[0] + w // 18, callout_start[1], callout_start[0] + w // 18, callout_end[1], accent, thickness)
            line(callout_start[0] + w // 18, callout_end[1], *callout_end, accent, thickness)
        elif shape == "arrow-tab":
            line(*callout_start, callout_end[0], callout_start[1], accent, thickness)
            line(callout_end[0], callout_start[1], callout_end[0] - w // 20, callout_start[1] - h // 18, accent, thickness)
            line(callout_end[0], callout_start[1], callout_end[0] - w // 20, callout_start[1] + h // 18, accent, thickness)
        elif shape == "seal":
            ellipse((callout_start[0] + callout_end[0]) // 2 - w // 18, (callout_start[1] + callout_end[1]) // 2 - h // 18, w // 9, h // 9, accent)
        elif shape == "wave":
            line(*callout_start, callout_start[0] + w // 28, callout_start[1] - h // 18, accent, thickness)
            line(callout_start[0] + w // 28, callout_start[1] - h // 18, callout_start[0] + w // 14, callout_start[1], accent, thickness)
            line(callout_start[0] + w // 14, callout_start[1], callout_start[0] + 3 * w // 28, callout_start[1] - h // 18, accent, thickness)
            line(callout_start[0] + 3 * w // 28, callout_start[1] - h // 18, callout_end[0], callout_start[1], accent, thickness)
        elif shape == "underline":
            line(*callout_start, callout_start[0] + w // 14, callout_start[1] + h // 20, accent, thickness)
            line(callout_start[0] + w // 14, callout_start[1] + h // 20, *callout_end, accent, thickness)
        else:
            line(*callout_start, *callout_end, accent, thickness)
        for index, value in enumerate(_wrap(str(cluster["title"]), 18)):
            text(x + w // 10, y + h // 3 + index * 24, value, ink, 3)
        for index, value in enumerate(_wrap(str(cluster["detail"]), 30)):
            text(x + w // 10, y + int(h * .60) + index * 18, value, body, 2)
        text(x + int(w * .60), y + int(h * .86), str(cluster["evidence_class"]), accent, 2)
    text(int(width * .074), int(height * .186), str(handoff.get("dominant_path_phrase", "")), accent, 2)
    for index, value in enumerate(_wrap(str(handoff["headline_zone"]["title"]), 28)):
        text(int(width * .07), int(height * .06) + index * 46, value, ink, 7)
    for index, value in enumerate(_wrap(str(handoff["headline_zone"]["takeaway"]), 58)):
        text(int(width * .07), int(height * .15) + index * 26, value, body, 3)
    footer = str(handoff.get("evidence_footer", ""))
    if footer:
        text(int(width * .07), int(height * .95), f"Evidence: {footer}", footer_ink, 2)
    raw = b"".join(b"\x00" + bytes(pixels[row * width * 3:(row + 1) * width * 3]) for row in range(height))
    callout_names = ",".join(str(cluster["callout_shape"]) for cluster in handoff["clusters"])
    out.write_bytes(b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + _png_chunk(b"tEXt", f"VisualSummary\x00RIBBON takeaway; CALLOUT {callout_names}".encode("latin-1")) + _png_chunk(b"IDAT", zlib.compress(raw, 9)) + _png_chunk(b"IEND", b""))
    if supplied_art:
        from PIL import Image
        base = Image.open(out).convert("RGBA")
        try:
            for cluster, art_path in supplied_art:
                slot = cluster.get("art_slot", {})
                art = Image.open(art_path)
                art.thumbnail((slot["width"], slot["height"]))
                art = art.convert("RGBA")
                base.alpha_composite(art, (slot["x"], slot["y"]))
        except (KeyError, OSError) as exc:
            raise SummaryError("PIL could not render supplied art into its bounded PNG slot") from exc
        base.convert("RGB").save(out, format="PNG", optimize=True)
    return out


def _portable_handoff(handoff: dict[str, Any]) -> dict[str, Any]:
    """Remove private generation inputs while retaining safe art provenance."""
    portable = deepcopy(handoff)

    def strip_generation_inputs(value: Any) -> None:
        if isinstance(value, dict):
            for key in list(value):
                if key in {"scene_prompt", "prompt", "prompt_hint", "art_path", "art_root", "private_icon_resolution"}:
                    value.pop(key, None)
                else:
                    strip_generation_inputs(value[key])
        elif isinstance(value, list):
            for child in value:
                strip_generation_inputs(child)

    for original, cluster in zip(handoff.get("clusters", []), portable.get("clusters", [])):
        data_url = _art_data_uri(original)
        if data_url:
            artwork = cluster.setdefault("artwork", cluster.pop("art", {}))
            artwork["data_url"] = data_url
    strip_generation_inputs(portable)
    return portable


def _office_handoff(handoff: dict[str, Any], private_icon_catalog: dict[str, Any] | None = None) -> dict[str, Any]:
    """Prepare the private Office-builder handoff without leaking raw receipts."""
    office = _portable_handoff(handoff)
    if office.get("concept") != "illo-storyboard-sequence-v1":
        return office
    # The portable handoff intentionally remains byte/path-free.  The transient
    # Office handoff is created only inside the private build directory after
    # re-reading the approved scene pack at its receipt-bound digest.
    private_paths = getattr(handoff, "_private_scene_paths", {})
    private_receipts = getattr(handoff, "_private_scene_receipts", {})
    for page in office.get("pages", []):
        if not isinstance(page, dict):
            continue
        for scene in page.get("scenes", []):
            if not isinstance(scene, dict):
                continue
            uri = _storyboard_scene_uri(scene, private_paths, private_receipts)
            receipt = private_receipts.get(scene.get("unit_id")) if isinstance(private_receipts, dict) else None
            if uri and isinstance(receipt, dict) and isinstance(receipt.get("sha256"), str):
                scene["reviewedScene"] = {"data_url": uri, "sha256": receipt["sha256"]}
    private_icons = private_icon_catalog if private_icon_catalog is not None else handoff.get("private_icon_resolution", {})
    if not isinstance(private_icons, dict):
        return office
    for page in office.get("pages", []):
        if not isinstance(page, dict):
            continue
        for service in page.get("services", []):
            if not isinstance(service, dict):
                continue
            # Office consumes an embedded passive SVG, never a Draw.io style.
            # Preserve selection separately from the honest physical fallback.
            service.update(_non_drawio_stencil_semantics(service))
            uri = _storyboard_safe_icon_uri(service, private_icons)
            if uri:
                service["serviceIcon"] = {
                    "data_url": uri,
                    "sha256": hashlib.sha256(_uri_svg_payload(uri)).hexdigest(),
                    "verified_by": "oci-visual-summary-passive-svg-v1",
                }
    return office


_STORYBOARD_ROLES = (
    "project-promise", "workflow", "capability-scenes", "oci-service-map", "at-a-glance",
)
_STORYBOARD_SCENES_PER_PAGE = 4
_STORYBOARD_SERVICES_PER_PAGE = 8
_SVG_PASSIVE_ELEMENTS = frozenset({"svg", "g", "path", "circle", "rect", "ellipse", "line", "polyline", "polygon", "defs", "clipPath", "linearGradient", "radialGradient", "stop", "title", "desc"})
_SVG_PASSIVE_ATTRS = frozenset({"id", "class", "viewBox", "width", "height", "x", "y", "x1", "x2", "y1", "y2", "cx", "cy", "r", "rx", "ry", "d", "points", "fill", "fill-opacity", "fill-rule", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "stroke-opacity", "transform", "opacity", "offset", "stop-color", "stop-opacity", "clip-path", "gradientUnits", "gradientTransform", "preserveAspectRatio", "role", "aria-label", "aria-labelledby", "xmlns"})


def _validated_passive_svg(payload: bytes) -> bytes:
    """Accept only a compact, passive SVG subset suitable for data-URI embedding."""
    if not payload or len(payload) > _MAX_EMBEDDED_ART_BYTES:
        raise SummaryError("private icon SVG exceeds the embed limit")
    # UTF-16/32 XML declarations retain NUL bytes between ASCII code units;
    # compact them before lexical rejection so DTD/entity blocking cannot be
    # bypassed by an alternative XML encoding.
    upper = payload.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        raise SummaryError("private icon SVG cannot contain DTDs or entities")
    try:
        root = ET.fromstring(payload)
    except (ET.ParseError, ValueError) as exc:
        raise SummaryError("private icon SVG is not well-formed XML") from exc
    for element in root.iter():
        name = element.tag.rsplit("}", 1)[-1] if isinstance(element.tag, str) else ""
        if name not in _SVG_PASSIVE_ELEMENTS:
            raise SummaryError("private icon SVG contains an active or unsupported element")
        for attr, value in element.attrib.items():
            local = attr.rsplit("}", 1)[-1]
            normalized = str(value).strip().casefold()
            if local.casefold().startswith("on") or local == "style" or local not in _SVG_PASSIVE_ATTRS:
                raise SummaryError("private icon SVG contains an unsafe attribute")
            if "url(" in normalized or "@import" in normalized or "javascript:" in normalized or "file:" in normalized:
                raise SummaryError("private icon SVG contains an unsafe reference")
            if local in {"href", "src"} or normalized.startswith(("http:", "https:", "//", "data:", "/", "./", "../")):
                raise SummaryError("private icon SVG contains an external or relative reference")
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise SummaryError("private icon payload must have an SVG root")
    return payload


def _storyboard_safe_icon_uri(record: dict[str, Any], private: dict[str, Any]) -> str | None:
    """Re-check a private icon byte receipt and return a standalone SVG URI.

    The portable handoff only carries a private asset identifier.  Bytes are
    deliberately resolved late from the caller's private catalog/receipt and
    never copied into the portable handoff or source-control artifacts.
    """
    allowed_private_keys = {"catalog", "root", "classification"}
    for key, value in private.items():
        if key in allowed_private_keys:
            continue
        if not isinstance(key, str) or not isinstance(value, dict) or set(value) != {"bytes", "sha256"}:
            raise SummaryError("private icon catalog contains unsupported receipt fields")
    catalog = private.get("catalog")
    direct_receipts = any(key not in allowed_private_keys for key in private)
    if direct_receipts and private.get("classification") != "internal":
        raise SummaryError("direct private icon receipts require explicit internal classification")
    if isinstance(catalog, dict) and catalog.get("classification") == "internal-only" and private.get("classification", "internal") == "public":
        raise SummaryError("public output cannot resolve an internal-only icon catalog")
    asset_id = record.get("private_catalog_asset_id")
    if not isinstance(asset_id, str) or not asset_id:
        return _official_public_stencil_uri(record)
    receipt = private.get(asset_id)
    # Task 4's catalog remains private and immutable.  Accept its explicit
    # caller-supplied root as a renderer dependency without serializing either
    # path or bytes into the audience handoff.
    if receipt is None and isinstance(catalog, dict):
        root = private.get("root")
        candidates = [item for item in catalog.get("icons", []) if isinstance(item, dict) and item.get("asset_id") == asset_id]
        if len(candidates) != 1 or not isinstance(root, (str, Path)):
            return None
        candidate = candidates[0]
        media_path = candidate.get("media_path")
        digest = candidate.get("media_digest")
        if not isinstance(media_path, str) or not isinstance(digest, str):
            raise SummaryError("private icon catalog record is incomplete")
        root_input = Path(root)
        if root_input.is_symlink() or not root_input.is_dir():
            raise SummaryError("private icon catalog root is unsafe")
        root_path = root_input.resolve(strict=True)
        file_path = (root_path / media_path).resolve(strict=True)
        try:
            file_path.relative_to(root_path)
        except ValueError as exc:
            raise SummaryError("private icon catalog asset escapes its root") from exc
        if file_path.is_symlink() or not file_path.is_file():
            raise SummaryError("private icon catalog asset is unsafe")
        try:
            descriptor = os.open(file_path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(descriptor, "rb") as stream:
                info = os.fstat(stream.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size <= 0 or info.st_size > _MAX_EMBEDDED_ART_BYTES:
                    raise SummaryError("private icon catalog asset exceeds the bounded SVG limit")
                payload = stream.read(_MAX_EMBEDDED_ART_BYTES + 1)
                if len(payload) != info.st_size:
                    raise SummaryError("private icon catalog asset changed while being read")
        except OSError as exc:
            raise SummaryError("private icon catalog asset is unavailable") from exc
        receipt = {"bytes": payload, "sha256": digest}
    if not isinstance(receipt, dict):
        return None
    payload = receipt.get("bytes")
    digest = receipt.get("sha256")
    if not isinstance(payload, bytes) or not isinstance(digest, str):
        raise SummaryError("private icon receipt must contain SVG bytes and a digest")
    if hashlib.sha256(payload).hexdigest() != digest:
        raise SummaryError("private icon changed after resolution")
    payload = _validated_passive_svg(payload)
    return "data:image/svg+xml;base64," + base64.b64encode(payload).decode("ascii")


def _official_public_stencil_uri(record: dict[str, Any]) -> str | None:
    """Render an explicit neutral service glyph after public-stencil selection.

    ``oci_diagram.py`` remains the source of supported stencil keys; this
    local renderer only materializes a compact passive vector for formats that
    cannot consume the Draw.io style string directly. It is deliberately
    labelled as a neutral/service-specific fallback, not an Oracle stencil.
    """
    if record.get("mapping_type") != "official-public-stencil" or record.get("provenance") != "official-public-oci-stencil-registry":
        return None
    key = record.get("public_stencil_key")
    if not isinstance(key, str) or not re.fullmatch(r"[a-z0-9-]{1,64}", key):
        raise SummaryError("official public stencil record has an invalid key")
    glyphs = {
        "monitoring": '<path d="M8 42V28m12 14V18m12 24V10" stroke="#C74634" stroke-width="5" stroke-linecap="round"/><path d="M4 46h40" stroke="#18202B" stroke-width="3"/>',
        "logging": '<path d="M10 13h28M10 24h28M10 35h20" stroke="#C74634" stroke-width="4" stroke-linecap="round"/><circle cx="10" cy="13" r="2" fill="#18202B"/>',
        "apm": '<circle cx="24" cy="24" r="6" fill="#C74634"/><circle cx="11" cy="14" r="4" fill="#79AAA6"/><circle cx="38" cy="14" r="4" fill="#79AAA6"/><circle cx="24" cy="39" r="4" fill="#79AAA6"/><path d="M14 16l7 5m13-5l-7 5m-3 9v5" stroke="#18202B" stroke-width="3"/>',
        "database": '<ellipse cx="24" cy="13" rx="15" ry="6" fill="#C74634"/><path d="M9 13v22c0 8 30 8 30 0V13" fill="#F8DED8" stroke="#18202B" stroke-width="3"/><path d="M9 24c0 8 30 8 30 0" fill="none" stroke="#18202B" stroke-width="3"/>',
        "service-connector-hub": '<circle cx="24" cy="24" r="7" fill="#C74634"/><circle cx="9" cy="12" r="4" fill="#79AAA6"/><circle cx="39" cy="12" r="4" fill="#79AAA6"/><circle cx="9" cy="37" r="4" fill="#79AAA6"/><circle cx="39" cy="37" r="4" fill="#79AAA6"/><path d="M12 14l8 7m16-7l-8 7m-16 14l8-7m16 7l-8-7" stroke="#18202B" stroke-width="3"/>',
    }
    shape = glyphs.get(key, '<path d="M24 7l15 9v17l-15 9-15-9V16z" fill="#F8DED8" stroke="#18202B" stroke-width="3"/><path d="M17 24h14M24 17v14" stroke="#C74634" stroke-width="3" stroke-linecap="round"/>')
    payload = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" role="img" aria-label="OCI {escape(key)} service glyph">{shape}</svg>'
    ).encode("utf-8")
    return "data:image/svg+xml;base64," + base64.b64encode(_validated_passive_svg(payload)).decode("ascii")


def _official_public_drawio_style(record: dict[str, Any]) -> str | None:
    """Read the supported Draw.io style from the public registry on demand."""
    if record.get("mapping_type") != "official-public-stencil":
        return None
    key = record.get("public_stencil_key")
    if not isinstance(key, str):
        return None
    import axm_icons
    try:
        style = axm_icons.official_public_stencil_catalog().get("stencils", {}).get(key)
        style = axm_icons.validate_public_stencil_style(style)
    except axm_icons.IconPackError as exc:
        raise SummaryError(f"official public stencil registry rejected: {exc}") from exc
    return style


def _non_drawio_stencil_semantics(record: dict[str, Any]) -> dict[str, str]:
    """State the truthful physical fallback for formats without mxgraph styles.

    ``mapping_type`` captures the public registry selection.  It must not be
    repurposed as a claim that SVG, PNG, PDF, Office, or Excalidraw embedded an
    Oracle-owned stencil asset: those formats receive our passive neutral
    service glyph after selection. Draw.io is the only current renderer that
    can consume the registry's actual ``mxgraph.oci`` style.
    """
    if (
        record.get("mapping_type") == "official-public-stencil"
        and record.get("provenance") == "official-public-oci-stencil-registry"
    ):
        return {
            "rendered_as": "neutral-service-glyph",
            "fallback_reason": "format-does-not-support-drawio-stencil",
        }
    return {}


def _neutral_service_glyph_kind(record: dict[str, Any]) -> str:
    """Pick the original portable glyph family for a resolved OCI service.

    The value is deliberately derived from public service identity, never from
    AXM artwork.  SVG, PNG, PDF, Office, and Excalidraw therefore retain a
    recognizable differentiated service motif even when only Draw.io can use
    the actual ``mxgraph.oci`` stencil style.
    """
    key = str(record.get("public_stencil_key", "")).strip().casefold()
    if key in {"monitoring", "logging", "apm", "service-connector-hub", "database"}:
        return key
    canonical = str(record.get("canonical_service_id", "")).casefold()
    if canonical.endswith(".monitoring"):
        return "monitoring"
    if canonical.endswith(".logging") or "log-analytics" in canonical:
        return "logging"
    if canonical.endswith(".apm"):
        return "apm"
    if "connector-hub" in canonical:
        return "service-connector-hub"
    if "database" in canonical:
        return "database"
    return "service"


def _storyboard_scene_uri(scene: dict[str, Any], private_paths: dict[str, Any], private_receipts: dict[str, Any]) -> str | None:
    """Re-read only a reviewed scene whose digest-bound provenance still matches."""
    unit_id = scene.get("unit_id")
    path_value = private_paths.get(unit_id) if isinstance(unit_id, str) else None
    provenance = private_receipts.get(unit_id) if isinstance(unit_id, str) else None
    if not isinstance(path_value, str) or not isinstance(provenance, dict):
        return None
    path = Path(path_value)
    if path.is_symlink() or not path.is_file():
        raise SummaryError("reviewed scene path is unsafe")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != provenance.get("sha256"):
        raise SummaryError("reviewed scene changed after approval")
    mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(path.suffix.casefold())
    if mime is None:
        raise SummaryError("reviewed scene has unsupported image format")
    return f"data:{mime};base64," + base64.b64encode(payload).decode("ascii")


def _storyboard_scene_bytes(scene: dict[str, Any], private_paths: dict[str, Any], private_receipts: dict[str, Any]) -> bytes | None:
    """Return exactly the digest-checked scene bytes once, for all renderers."""
    unit_id = scene.get("unit_id")
    path_value = private_paths.get(unit_id) if isinstance(unit_id, str) else None
    receipt = private_receipts.get(unit_id) if isinstance(unit_id, str) else None
    if not isinstance(path_value, str) or not isinstance(receipt, dict):
        return None
    path = Path(path_value)
    if path.is_symlink() or not path.is_file():
        raise SummaryError("reviewed scene path is unsafe")
    payload = path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != receipt.get("sha256"):
        raise SummaryError("reviewed scene changed after approval")
    return payload


def _tiny_png_color(payload: bytes) -> tuple[int, int, int] | None:
    """Read a bounded, non-interlaced 8-bit PNG's first pixel without Pillow."""
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return None
    offset = 8; width = height = color = None; data = bytearray()
    while offset + 12 <= len(payload):
        size = struct.unpack(">I", payload[offset:offset + 4])[0]; kind = payload[offset + 4:offset + 8]; chunk = payload[offset + 8:offset + 8 + size]; offset += 12 + size
        if kind == b"IHDR" and len(chunk) == 13:
            width, height, depth, color, _compression, _filter, interlace = struct.unpack(">IIBBBBB", chunk)
            if depth != 8 or interlace != 0 or color not in {2, 6} or not width or not height:
                return None
        elif kind == b"IDAT": data.extend(chunk)
        elif kind == b"IEND": break
    if width is None or color is None:
        return None
    try: raw = zlib.decompress(bytes(data))
    except zlib.error: return None
    channels = 4 if color == 6 else 3
    if not raw or raw[0] != 0 or len(raw) < 1 + channels:
        return None
    return tuple(raw[1:4])  # type: ignore[return-value]


def _decode_scene_image(payload: bytes):
    """Decode already verified scene bytes with the optional local Pillow backend."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise _OptionalAssetBackendUnavailable("Pillow is unavailable") from exc
    try:
        image = Image.open(io.BytesIO(payload)); image.load()
        return image.convert("RGBA")
    except Exception as exc:
        raise _OptionalAssetBackendUnavailable("reviewed scene decoder is unavailable") from exc


def _rasterize_verified_svg(payload: bytes, width: int, height: int) -> bytes:
    """Rasterize validated SVG bytes with caller-supplied local Node + sharp only."""
    node = os.environ.get("RUNTIME_NODE") or shutil.which("node")
    if not node:
        raise _OptionalAssetBackendUnavailable("local Node SVG rasterizer is unavailable")
    script = "const sharp=require('sharp');let b=[];process.stdin.on('data',c=>b.push(c));process.stdin.on('end',async()=>{try{process.stdout.write(await sharp(Buffer.concat(b)).resize(Number(process.argv[1]),Number(process.argv[2]),{fit:'contain'}).png().toBuffer())}catch(e){process.stderr.write(String(e));process.exit(2)}});"
    env = dict(os.environ)
    try:
        result = subprocess.run([node, "-e", script, str(width), str(height)], input=payload, capture_output=True, check=False, env=env, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise _OptionalAssetBackendUnavailable("local Node SVG rasterizer cannot start") from exc
    if result.returncode != 0 or not result.stdout.startswith(b"\x89PNG\r\n\x1a\n"):
        raise _OptionalAssetBackendUnavailable("local Node SVG rasterizer is unavailable")
    return result.stdout


def _uri_svg_payload(uri: str) -> bytes:
    prefix = "data:image/svg+xml;base64,"
    if not uri.startswith(prefix):
        raise SummaryError("validated icon URI has an unexpected format")
    try:
        return base64.b64decode(uri[len(prefix):], validate=True)
    except ValueError as exc:
        raise SummaryError("validated icon URI cannot be decoded") from exc


def _pdf_image_reader(payload: bytes):
    try:
        from reportlab.lib.utils import ImageReader
        return ImageReader(io.BytesIO(payload))
    except Exception as exc:
        raise _OptionalAssetBackendUnavailable("local PDF image decoder is unavailable") from exc


def _pdf_draw_asset(pdf: Any, payload: bytes, x: float, y: float, width: float, height: float) -> None:
    """Draw one already verified asset; converter/decoder failures stay local."""
    try:
        pdf.drawImage(_pdf_image_reader(payload), x, y, width, height, preserveAspectRatio=True, mask="auto")
    except _OptionalAssetBackendUnavailable:
        raise
    except Exception as exc:
        raise _OptionalAssetBackendUnavailable("local PDF image drawing is unavailable") from exc


def _pdf_draw_neutral_service_glyph(pdf: Any, x: float, y: float, width: float, height: float, service: dict[str, Any]) -> None:
    """Draw a differentiated original glyph when SVG rasterization is unavailable."""
    pdf.setStrokeColorRGB(0.78, 0.27, 0.20)
    pdf.setFillColorRGB(1.0, 0.95, 0.91)
    pdf.roundRect(x, y, width, height, min(width, height) * 0.12, fill=1, stroke=1)
    pad = min(width, height) * 0.18
    base = y + pad
    pdf.setStrokeColorRGB(0.12, 0.16, 0.21)
    pdf.setLineWidth(max(1.0, min(width, height) * 0.04))
    glyph_kind = _neutral_service_glyph_kind(service)
    if glyph_kind == "logging":
        for fraction in (.25, .50, .75):
            line_y = y + pad + (height - pad * 2) * fraction
            pdf.line(x + pad, line_y, x + width - pad * (1 if fraction < .75 else 2), line_y)
            pdf.setFillColorRGB(0.78, 0.27, 0.20); pdf.circle(x + pad, line_y, max(1.5, pad * .12), fill=1, stroke=0)
    elif glyph_kind == "apm":
        nodes = ((x + pad, y + height - pad), (x + width - pad, y + height - pad), (x + width / 2, y + pad))
        for start, end in ((nodes[0], nodes[1]), (nodes[0], nodes[2]), (nodes[1], nodes[2])):
            pdf.line(*start, *end)
        for node_x, node_y in nodes:
            pdf.setFillColorRGB(.47, .67, .65); pdf.circle(node_x, node_y, max(2, pad * .18), fill=1, stroke=1)
    elif glyph_kind == "service-connector-hub":
        center_x, center_y = x + width / 2, y + height / 2
        satellites = ((x + pad, y + pad), (x + width - pad, y + pad), (x + pad, y + height - pad), (x + width - pad, y + height - pad))
        for node_x, node_y in satellites:
            pdf.line(center_x, center_y, node_x, node_y)
            pdf.setFillColorRGB(.47, .67, .65); pdf.circle(node_x, node_y, max(1.5, pad * .12), fill=1, stroke=1)
        pdf.setFillColorRGB(0.78, 0.27, 0.20); pdf.circle(center_x, center_y, max(2.5, pad * .22), fill=1, stroke=1)
    elif glyph_kind == "database":
        pdf.setFillColorRGB(0.78, 0.27, 0.20); pdf.ellipse(x + pad, y + height - pad * 1.3, x + width - pad, y + height - pad * .35, fill=1, stroke=1)
        pdf.setFillColorRGB(1.0, 0.87, 0.82); pdf.rect(x + pad, y + pad * .7, width - pad * 2, height - pad * 1.45, fill=1, stroke=1)
        pdf.setStrokeColorRGB(0.12, 0.16, 0.21); pdf.ellipse(x + pad, y + pad * .2, x + width - pad, y + pad * 1.15, fill=0, stroke=1)
    else:
        pdf.line(x + pad, base, x + width - pad, base)
        pdf.setFillColorRGB(0.78, 0.27, 0.20)
        bar_w = max(2.0, width * 0.10)
        for index, ratio in enumerate((0.35, 0.55, 0.78)):
            bx = x + pad + index * (bar_w * 1.7)
            pdf.roundRect(bx, base, bar_w, max(2.0, (height - pad * 2) * ratio), 1.5, fill=1, stroke=0)


def _pdf_reviewed_evidence_geometry(page: dict[str, Any], page_w: float, page_h: float) -> dict[str, Any]:
    """Return collision-free PDF evidence zones in bottom-origin coordinates.

    PDF evidence pages deliberately use their own editorial grid instead of
    reusing the compact SVG/PNG canvas slots. Captions sit in a dedicated band
    below each scene, service glyphs occupy a separate lower band, and the
    evidence footer is always reserved at the bottom.
    """
    role = str(page.get("audience_role", page.get("role", "")))
    scenes = [item for item in page.get("scenes", []) if isinstance(item, dict)]
    services = [item for item in page.get("services", []) if isinstance(item, dict)]
    footer = (page_w * .07, page_h * .035, page_w * .86, page_h * .045)
    scene_zones: list[tuple[float, float, float, float, tuple[float, float, float, float]]] = []
    service_zones: list[tuple[float, float, float, float, tuple[float, float, float, float]]] = []
    if role == "at-a-glance":
        for index, _scene in enumerate(scenes):
            column, row = index % 2, index // 2
            x = page_w * (.09 + .46 * column)
            # Lift the two scene rows so the lower caption band has visible
            # breathing room above the service-glyph row at native PDF size.
            y = page_h * (.62 - .24 * row)
            w, h = page_w * .34, page_h * .14
            scene_zones.append((x, y, w, h, (x, y - page_h * .045, w, page_h * .032)))
        for index, _service in enumerate(services):
            column, row = index % 4, index // 4
            x = page_w * (.09 + .23 * column)
            y = page_h * (.24 - .10 * row)
            w, h = page_w * .075, page_h * .055
            service_zones.append((x, y, w, h, (x, y - page_h * .038, page_w * .16, page_h * .028)))
    elif role == "workflow":
        for index, _scene in enumerate(scenes):
            x = page_w * (.07 + .235 * index)
            y, w, h = page_h * .50, page_w * .18, page_h * .23
            scene_zones.append((x, y, w, h, (x, y - page_h * .050, w, page_h * .035)))
        for index, _service in enumerate(services):
            x = page_w * (.09 + .23 * index)
            y, w, h = page_h * .20, page_w * .075, page_h * .085
            service_zones.append((x, y, w, h, (x, y - page_h * .040, page_w * .16, page_h * .030)))
    else:
        for index, _scene in enumerate(scenes):
            x, y, w, h = page_w * .12, page_h * .49, page_w * .58, page_h * .25
            scene_zones.append((x, y, w, h, (x, y - page_h * .055, w, page_h * .035)))
        for index, _service in enumerate(services):
            x = page_w * (.12 + .22 * index)
            y, w, h = page_h * .20, page_w * .075, page_h * .085
            service_zones.append((x, y, w, h, (x, y - page_h * .040, page_w * .16, page_h * .030)))
    return {"scenes": scene_zones, "services": service_zones, "footer": footer}


def _storyboard_physical_pages(pages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Expand five audience sections into stable, bounded physical pages."""
    physical: list[dict[str, Any]] = []
    for page in pages:
        audience_role = str(page.get("role", ""))
        scenes = [item for item in page.get("scenes", []) if isinstance(item, dict)]
        services = [item for item in page.get("services", []) if isinstance(item, dict)]
        if audience_role == "capability-scenes":
            for scene in scenes:
                matched_services = [
                    service for service in services
                    if str(service.get("unit_id", "")) == str(scene.get("unit_id", ""))
                ]
                physical.append({
                    **page,
                    "role": f"capability-scenes-{scene['unit_id']}",
                    "audience_role": audience_role,
                    "page_number": 1,
                    "page_count": 1,
                    "scenes": [scene],
                    "services": matched_services[:1],
                })
            continue
        scene_chunks = [scenes[index:index + _STORYBOARD_SCENES_PER_PAGE] for index in range(0, len(scenes), _STORYBOARD_SCENES_PER_PAGE)] or [[]]
        service_chunks = [services[index:index + _STORYBOARD_SERVICES_PER_PAGE] for index in range(0, len(services), _STORYBOARD_SERVICES_PER_PAGE)] or [[]]
        page_count = max(len(scene_chunks), len(service_chunks))
        for index in range(page_count):
            role = audience_role if page_count == 1 else f"{audience_role}-{index + 1}"
            physical.append({
                **page,
                "role": role,
                "audience_role": audience_role,
                "page_number": index + 1,
                "page_count": page_count,
                "scenes": scene_chunks[index] if index < len(scene_chunks) else [],
                "services": service_chunks[index] if index < len(service_chunks) else [],
            })
    return physical


def _storyboard_page_layout(handoff: dict[str, Any], page: dict[str, Any]) -> dict[str, Any]:
    """Return the shared integer asset bounds consumed by SVG, PNG, and PDF."""
    width, height = handoff["canvas"]["width"], handoff["canvas"]["height"]
    scenes = [item for item in page.get("scenes", []) if isinstance(item, dict)]
    services = [item for item in page.get("services", []) if isinstance(item, dict)]
    if len(scenes) > _STORYBOARD_SCENES_PER_PAGE or len(services) > _STORYBOARD_SERVICES_PER_PAGE:
        raise SummaryError("storyboard renderer requires bounded physical pages")
    role = str(page.get("audience_role", page.get("role", "")))
    scene_layout = []
    for index, scene in enumerate(scenes):
        if role == "project-promise":
            # The promise is a hero scene with its explanation beside it, not
            # a tiny first card stranded in a four-column grid.
            x, y, scene_width, scene_height = .43, .27, .50, .54
        elif role == "capability-scenes":
            # Each capability physical page is one editorial scene.  Give the
            # reviewed art enough scale for character gesture and props to be
            # legible in slide, PDF, and document previews.
            x, y, scene_width, scene_height = .39, .24, .54, .51
        elif role == "at-a-glance":
            # A compact 2x2 sketchnote map leaves room to integrate the mapped
            # service beside each scene while retaining one clear reading path.
            x = .06 + .47 * (index % 2)
            y = .29 + .245 * (index // 2)
            scene_width, scene_height = .35, .195
        else:
            # Workflow remains a left-to-right progression, but cards are
            # materially larger and sit on the same visual route.
            x, y, scene_width, scene_height = .04 + .24 * index, .31, .21, .30
        bounds = {
            "x": int(width * x),
            "y": int(height * y),
            "width": max(1, int(width * scene_width)),
            "height": max(1, int(height * scene_height)),
        }
        scene_layout.append({
            "record": scene,
            "bounds": bounds,
            "label_bounds": {
                "x": bounds["x"],
                "y": bounds["y"] + bounds["height"] + 4,
                "width": max(1, int(width * (.30 if role in {"project-promise", "capability-scenes"} else .20))),
                "height": max(1, int(height * (.060 if role == "at-a-glance" else .080))),
            },
        })
    service_layout = []
    # Reserve the bottom eight percent for evidence in every renderer.  When
    # scenes share the page, service rows are tightened above that band without
    # changing the four-scene/eight-service capacity.
    footer_bounds = {
        "x": int(width * .06),
        "y": int(height * .92),
        "width": int(width * .88),
        "height": height - int(height * .92),
    }
    service_top = .62 if scenes else .34
    service_gap = .14 if scenes else .27
    icon_height = .07 if scenes else .13
    for index, service in enumerate(services):
        if role == "oci-service-map":
            x = .09 + .22 * (index % 4)
            y = .37 + .28 * (index // 4)
            icon_width, current_icon_height = .10, .15
        elif role == "at-a-glance" and scene_layout:
            # Up to two service badges live inside each scene quadrant.  This
            # keeps the map legible when the bounded acceptance fixture carries
            # eight services, while the usual four-service summary maps one
            # domain icon directly to each action scene.
            scene_bounds = scene_layout[index % len(scene_layout)]["bounds"]
            service_row = index // len(scene_layout)
            x = (scene_bounds["x"] + scene_bounds["width"] - int(width * .060)) / width
            y = (scene_bounds["y"] + int(height * (.020 + .075 * service_row))) / height
            icon_width, current_icon_height = .050, .060
        elif role == "capability-scenes":
            x, y, icon_width, current_icon_height = .07, .62, .11, .15
        elif role == "workflow":
            x = .07 + .22 * (index % 4)
            y = .68 + .11 * (index // 4)
            icon_width, current_icon_height = .060, .055
        else:
            x = .06 + .235 * (index % 4)
            y = service_top + service_gap * (index // 4)
            icon_width, current_icon_height = .07, icon_height
        bounds = {
            "x": int(width * x),
            "y": int(height * y),
            "width": max(1, int(width * icon_width)),
            "height": max(1, int(height * current_icon_height)),
        }
        if role == "at-a-glance" and scene_layout:
            service_label_x = max(0, bounds["x"] - int(width * .035))
            service_label_width = max(1, int(width * .105))
        else:
            service_label_x = bounds["x"]
            service_label_width = max(1, int(width * (.17 if role == "oci-service-map" else .20)))
        service_layout.append({
            "record": service,
            "bounds": bounds,
            "label_bounds": {
                "x": service_label_x,
                "y": bounds["y"] + bounds["height"] + 2,
                "width": service_label_width,
                "height": max(1, int(height * (.09 if role == "oci-service-map" else .040 if role == "workflow" else .055))),
            },
        })
    for item in scene_layout + service_layout:
        bounds, label = item["bounds"], item["label_bounds"]
        if bounds["x"] + bounds["width"] > width or bounds["y"] + bounds["height"] > footer_bounds["y"]:
            raise SummaryError(f"storyboard {role} asset intersects the evidence footer band: {bounds}")
        if label["x"] + label["width"] > width or label["y"] + label["height"] > footer_bounds["y"]:
            raise SummaryError(f"storyboard {role} label intersects the evidence footer band: {label}")
    return {"scenes": scene_layout, "services": service_layout, "footer_bounds": footer_bounds}


def _storyboard_png_metadata(handoff: dict[str, Any], page: dict[str, Any], layout: dict[str, list[dict[str, Any]]]) -> bytes:
    metadata = {
        "schema_version": 1,
        "audience_role": str(page.get("audience_role", page.get("role", ""))),
        "physical_role": str(page.get("role", "")),
        "page_number": int(page.get("page_number", 1)),
        "page_count": int(page.get("page_count", 1)),
        "canvas": deepcopy(handoff["canvas"]),
        "evidence": str(handoff.get("evidence_footer", "")),
        "footer_bounds": deepcopy(layout["footer_bounds"]),
        "scenes": [
            {
                "unit_id": str(item["record"].get("unit_id", "")),
                "title": str(item["record"].get("title", "")),
                "evidence_class": str(item["record"].get("evidence_class", "")),
                "bounds": deepcopy(item["bounds"]),
                "label_bounds": deepcopy(item["label_bounds"]),
            }
            for item in layout["scenes"]
        ],
        "services": [
            {
                "canonical_service_id": str(item["record"].get("canonical_service_id", "")),
                "display_name": str(item["record"].get("display_name", "")),
                "mapping_type": str(item["record"].get("mapping_type", "none")),
                **_non_drawio_stencil_semantics(item["record"]),
                "bounds": deepcopy(item["bounds"]),
                "label_bounds": deepcopy(item["label_bounds"]),
            }
            for item in layout["services"]
        ],
    }
    return b"VisualSummary\x00" + json.dumps(metadata, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def _attach_storyboard_png_metadata(out: Path, metadata: bytes) -> None:
    payload = out.read_bytes()
    if not payload.startswith(b"\x89PNG\r\n\x1a\n") or payload[12:16] != b"IHDR":
        raise SummaryError("local PNG compositor produced an invalid image")
    ihdr_size = struct.unpack(">I", payload[8:12])[0]
    insert_at = 8 + 12 + ihdr_size
    out.write_bytes(payload[:insert_at] + _png_chunk(b"tEXt", metadata) + payload[insert_at:])


def build_storyboard_handoff(
    summary_spec: dict[str, Any], accepted_storyboard: dict[str, Any], approved_scene_manifest: dict[str, Any],
    icon_resolutions: list[dict[str, Any]], *, width: int, height: int,
) -> dict[str, Any]:
    """Project a reviewed private storyboard into a prompt-free audience sequence.

    This boundary intentionally accepts no asset paths or bytes.  A renderer
    may receive an ephemeral ``private_icon_catalog`` separately, but every
    exportable handoff remains safe to pass to editable-format builders.
    """
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise SummaryError("storyboard width and height must be positive integers")
    summary = normalize_spec(validate_spec(summary_spec, _bundled_schema()))
    if not isinstance(accepted_storyboard, dict) or not isinstance(accepted_storyboard.get("units"), list):
        raise SummaryError("accepted storyboard must contain units")
    units_by_id = {unit.get("id"): unit for unit in accepted_storyboard["units"] if isinstance(unit, dict) and isinstance(unit.get("id"), str)}
    sequence = accepted_storyboard.get("audience_sequence")
    if not isinstance(sequence, list) or set(sequence) != set(units_by_id) or len(sequence) != len(units_by_id):
        raise SummaryError("audience_sequence must be an exact, duplicate-free permutation of accepted unit IDs")
    anchors = {f"anchor-{index}": anchor for index, anchor in enumerate(summary["anchors"], start=1)}
    scenes: list[dict[str, Any]] = []
    for unit_id in sequence:
        unit = units_by_id[unit_id]
        anchor = anchors.get(unit.get("summary_anchor_id"))
        if anchor is None:
            raise SummaryError("storyboard unit does not resolve to a summary anchor")
        scenes.append({
            "unit_id": unit_id, "anchor_id": unit["summary_anchor_id"], "title": anchor["title"],
            "detail": anchor["detail"], "evidence_class": anchor["evidence_class"],
            "source_ids": list(anchor.get("source_ids", [])), "alt_text": unit.get("alt_text", ""),
        })
    try:
        scene_snapshot = storyboard.reviewed_scene_snapshot(approved_scene_manifest, accepted_storyboard)
    except storyboard.StoryboardError as exc:
        raise SummaryError(f"approved scene manifest is required: {exc}") from exc
    scene_by_unit = {item["unit_id"]: item for item in scene_snapshot["scenes"]}
    if set(scene_by_unit) != set(sequence):
        raise SummaryError("approved scenes must bind exactly once to every accepted unit")
    for scene in scenes:
        receipt = scene_by_unit[scene["unit_id"]]
        # The path stays private; the existing Canvas renderer geometry can be
        # re-used in internal assembly without adding it to portable output.
        scene["_private_scene_path"] = str(receipt["path"])
    allowed_icon_keys = {
        "unit_id", "canonical_service_id", "display_name", "mapping_type", "alt_text", "bounds",
        "private_catalog_asset_id", "public_stencil_key", "provenance",
        "rendered_as", "fallback_reason",
    }
    services = []
    for item in icon_resolutions:
        if not isinstance(item, dict) or set(item) - allowed_icon_keys or not {"unit_id", "canonical_service_id", "display_name", "mapping_type", "alt_text", "private_catalog_asset_id"} <= set(item):
            raise SummaryError("icon resolution must use the portable allowlist contract")
        if item["unit_id"] not in units_by_id or item["mapping_type"] not in {"exact-service", "conceptual-redwood", "official-public-stencil", "none"}:
            raise SummaryError("icon resolution is not grounded to the accepted storyboard")
        portable = deepcopy(item)
        # The portable handoff is consumed by PDF/PPTX/DOCX/PNG/SVG and makes
        # the public-stencil selection versus neutral-glyph rendering explicit.
        portable.update(_non_drawio_stencil_semantics(portable))
        services.append(portable)
    pages = [
        {"role": "project-promise", "title": summary["title"], "takeaway": summary["takeaway"], "scenes": scenes[:1], "services": services[:1]},
        {"role": "workflow", "title": "Detect, correlate, diagnose, route", "takeaway": "One incident thread carries shared context from signal to action.", "scenes": scenes, "services": services},
        {"role": "capability-scenes", "title": "Incident-management capability", "scenes": scenes, "services": services},
        {"role": "oci-service-map", "title": "OCI service map", "services": services},
        {"role": "at-a-glance", "title": "OCI incident management at a glance", "takeaway": summary["takeaway"], "scenes": scenes, "services": services},
    ]
    public_handoff = {"schema_version": 1, "concept": "illo-storyboard-sequence-v1", "canvas": {"width": width, "height": height},
               "title": summary["title"], "takeaway": summary["takeaway"], "domain": summary["domain"],
               "evidence_class": summary["evidence_class"], "pages": pages,
               "evidence_footer": _unique_titles([source for source in summary["sources"] if isinstance(source, dict)]),
               # Public, validated source metadata is required by the Office
               # projections for real DOCX hyperlinks and PPTX notes.  Never
               # serialize local/private source records merely because a title
               # is available in the summary working set.
               "source_register": [
                   {"title": str(source.get("title", "Official Oracle documentation")), "url": str(source["url"])}
                   for source in summary["sources"] if isinstance(source, dict)
                   and isinstance(source.get("url"), str)
                   and source["url"].startswith("https://docs.oracle.com/")
               ]}
    private_scene_paths = {scene["unit_id"]: scene.pop("_private_scene_path") for scene in scenes}
    private_scene_receipts = {item["unit_id"]: {key: item[key] for key in ("unit_id", "sha256", "character_pack", "model_sheet_digest", "style_anchor_digest", "generator", "rights", "review_status", "qa")} for item in scene_snapshot["scenes"]}
    handoff = _StoryboardHandoff(public_handoff, private_scene_paths, private_scene_receipts)
    if any("prompt" in key.casefold() for key, _ in _string_paths(handoff)):
        raise SummaryError("storyboard handoff cannot contain prompt fields")
    return handoff


def _render_storyboard_page_svg(handoff: dict[str, Any], page: dict[str, Any], out: Path, private: dict[str, Any]) -> Path:
    canvas = handoff.get("canvas", {})
    width, height = canvas.get("width"), canvas.get("height")
    if not isinstance(width, int) or not isinstance(height, int):
        raise SummaryError("storyboard handoff has an invalid canvas")
    out = _safe_output_path(out)
    title = str(page.get("title", handoff.get("title", "Visual summary")))
    audience_role = str(page.get("audience_role", page.get("role", "")))
    page_number = int(page.get("page_number", 1))
    page_count = int(page.get("page_count", 1))
    layout = _storyboard_page_layout(handoff, page)
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" data-audience-role="{escape(audience_role)}" data-page-number="{page_number}" data-page-count="{page_count}">',
        f'<title>{escape(title)}</title>', f'<rect width="{width}" height="{height}" fill="#FFF8EC"/>',
        f'<path d="M0 {height*.235:.1f} Q {width*.24:.1f} {height*.205:.1f} {width*.5:.1f} {height*.24:.1f} T {width:.1f} {height*.225:.1f} V {height*.89:.1f} H0Z" fill="#E8F4F1"/>',
        _svg_text(_wrap(title, 38), width * .055, height * .105, height * .068, "#18202B", "700", _CANVAS_FONT_STACK)]
    if page.get("takeaway"):
        parts.append(_svg_text(_wrap(str(page["takeaway"]), 72), width * .057, height * .205, height * .030, "#3C4655", "400", _CANVAS_FONT_STACK))
    # Purpose-built composition marks make the audience sequence read as five
    # different editorial explanations instead of title-swapped card grids.
    if audience_role == "workflow" and layout["scenes"]:
        points = [(item["bounds"]["x"] + item["bounds"]["width"] / 2, item["bounds"]["y"] + item["bounds"]["height"] / 2) for item in layout["scenes"]]
        path = f"M {points[0][0]:.1f} {points[0][1]:.1f} " + " ".join(
            f"C {x:.1f} {y:.1f}, {x:.1f} {y:.1f}, {nx:.1f} {ny:.1f}"
            for (x, y), (nx, ny) in zip(points, points[1:])
        )
        parts.append(f'<path d="{path}" fill="none" stroke="#C74634" stroke-width="9" stroke-linecap="round" stroke-dasharray="4 14" opacity=".78"/>')
        for index, (x, y) in enumerate(points, start=1):
            parts += [f'<circle cx="{x:.1f}" cy="{y - height*.155:.1f}" r="{height*.026:.1f}" fill="#18202B"/>', _svg_text([str(index)], x - width*.005, y - height*.145, height*.026, "#FFF8EC", "700", _CANVAS_FONT_STACK)]
    elif audience_role == "oci-service-map":
        parts += [
            f'<path d="M {width*.08:.1f} {height*.67:.1f} Q {width*.34:.1f} {height*.22:.1f} {width*.53:.1f} {height*.48:.1f} T {width*.92:.1f} {height*.36:.1f}" fill="none" stroke="#79AAA6" stroke-width="{height*.012:.1f}" stroke-linecap="round" stroke-dasharray="2 16"/>',
            _svg_text(["SIGNALS"], width*.07, height*.32, height*.024, "#C74634", "700", _CANVAS_FONT_STACK),
            _svg_text(["SHARED INCIDENT CONTEXT"], width*.39, height*.78, height*.023, "#18202B", "700", _CANVAS_FONT_STACK),
            _svg_text(["ACTION"], width*.82, height*.32, height*.024, "#C74634", "700", _CANVAS_FONT_STACK),
        ]
        service_roles = {"monitoring": "OWNED SIGNAL", "logging": "SEARCHABLE CONTEXT", "apm": "TRACE + TOPOLOGY", "connector": "APPROVED ROUTE", "analytics": "INVESTIGATION"}
        for item in layout["services"]:
            record, bounds = item["record"], item["bounds"]
            canonical = str(record.get("canonical_service_id", "")).casefold()
            role_label = next((label for token, label in service_roles.items() if token in canonical), "OWNED TELEMETRY")
            center_x = bounds["x"] + bounds["width"] / 2
            parts += [
                f'<path d="M {center_x:.1f} {bounds["y"] + bounds["height"] + height*.10:.1f} Q {center_x:.1f} {height*.67:.1f} {width*.50:.1f} {height*.735:.1f}" fill="none" stroke="#79AAA6" stroke-width="3" stroke-dasharray="3 9" opacity=".72"/>',
                _svg_badge_text(role_label, center_x - width*.075, height*.64, width*.15, height*.045, "#C74634", "#18202B"),
            ]
    elif audience_role == "at-a-glance":
        parts.append(f'<path d="M {width*.035:.1f} {height*.48:.1f} C {width*.28:.1f} {height*.23:.1f}, {width*.71:.1f} {height*.83:.1f}, {width*.965:.1f} {height*.48:.1f}" fill="none" stroke="#C74634" stroke-width="{height*.011:.1f}" stroke-linecap="round" opacity=".86"/>')
        parts.append(_svg_text(["DETECT  →  CORRELATE  →  DIAGNOSE  →  ROUTE"], width*.27, height*.875, height*.024, "#C74634", "700", _CANVAS_FONT_STACK))
    elif audience_role == "project-promise":
        parts += [
            f'<path d="M {width*.055:.1f} {height*.34:.1f} Q {width*.20:.1f} {height*.25:.1f} {width*.36:.1f} {height*.36:.1f} T {width*.41:.1f} {height*.48:.1f}" fill="none" stroke="#C74634" stroke-width="{height*.013:.1f}" stroke-linecap="round"/>',
            _svg_text(["ONE INCIDENT THREAD"], width*.06, height*.38, height*.038, "#C74634", "700", _CANVAS_FONT_STACK),
            _svg_text(["shared context", "clear ownership", "faster learning"], width*.07, height*.46, height*.026, "#18202B", "400", _CANVAS_FONT_STACK),
        ]
    private_scenes = getattr(handoff, "_private_scene_paths", {})
    private_receipts = getattr(handoff, "_private_scene_receipts", {})
    for index, item in enumerate(layout["scenes"]):
        scene, bounds, label = item["record"], item["bounds"], item["label_bounds"]
        x, y, asset_width, asset_height = bounds["x"], bounds["y"], bounds["width"], bounds["height"]
        scene_uri = _storyboard_scene_uri(scene, private_scenes, private_receipts) if isinstance(private_scenes, dict) else None
        parts += [
            f'<g data-storyboard-scene="{escape(str(scene.get("unit_id", index)))}" data-layout-x="{x}" data-layout-y="{y}" data-layout-width="{asset_width}" data-layout-height="{asset_height}" data-label-x="{label["x"]}" data-label-y="{label["y"]}" data-label-width="{label["width"]}" data-label-height="{label["height"]}">',
            f'<circle cx="{x + asset_width/2:.1f}" cy="{y + asset_height/2:.1f}" r="{min(asset_width, asset_height)*.35:.1f}" fill="#79AAA6" opacity=".24"/>',
            (f'<image data-reviewed-scene="true" href="{scene_uri}" x="{x}" y="{y}" width="{asset_width}" height="{asset_height}" preserveAspectRatio="xMidYMid meet"/>' if scene_uri else ""),
            _svg_text(_wrap(str(scene.get("title", "")), 20), label["x"], label["y"] + height*.025, height*.026, "#18202B", "700", _CANVAS_FONT_STACK),
            ("" if audience_role in {"workflow", "at-a-glance"} else _svg_text(_wrap(str(scene.get("detail", "")), 40), label["x"], label["y"] + height*.075, height*.018, "#3C4655", "400", _CANVAS_FONT_STACK)),
            '</g>',
        ]
    for item in layout["services"]:
        service, bounds, label = item["record"], item["bounds"], item["label_bounds"]
        x, y, asset_width, asset_height = bounds["x"], bounds["y"], bounds["width"], bounds["height"]
        service_id = escape(str(service.get("canonical_service_id", "service")))
        uri = _storyboard_safe_icon_uri(service, private)
        semantics = _non_drawio_stencil_semantics(service)
        parts.append(
            f'<g data-service-icon="{service_id}" data-canonical-service-id="{service_id}" '
            f'data-mapping-type="{escape(str(service.get("mapping_type", "none")))}" '
            f'data-public-stencil-key="{escape(str(service.get("public_stencil_key", "")))}" '
            f'data-provenance="{escape(str(service.get("provenance", "")))}" '
            f'data-rendered-as="{escape(semantics.get("rendered_as", ""))}" '
            f'data-fallback-reason="{escape(semantics.get("fallback_reason", ""))}" '
            f'data-layout-x="{x}" data-layout-y="{y}" data-layout-width="{asset_width}" data-layout-height="{asset_height}" '
            f'data-label-x="{label["x"]}" data-label-y="{label["y"]}" data-label-width="{label["width"]}" data-label-height="{label["height"]}" '
            f'aria-label="{escape(str(service.get("alt_text", "OCI service")))}">'
        )
        if uri:
            parts.append(f'<image href="{uri}" x="{x}" y="{y}" width="{asset_width}" height="{asset_height}" preserveAspectRatio="xMidYMid meet"/>')
        else:
            parts.append(f'<rect x="{x}" y="{y}" width="{asset_width}" height="{asset_height}" rx="12" fill="#E6B9AE" data-icon-fallback="native-text"/>')
        parts.append(_svg_text(
            _wrap(str(service.get("display_name", "OCI service")), 20),
            label["x"], label["y"] + height * (.018 if audience_role in {"workflow", "at-a-glance"} else .022),
            height * .021, "#18202B", "700", _CANVAS_FONT_STACK,
        ))
        if audience_role not in {"workflow", "at-a-glance"}:
            parts.append(_svg_text(
                _wrap(f'{service.get("canonical_service_id", "")} — {service.get("mapping_type", "none")}', 28),
                label["x"], label["y"] + height*.061, height*.013, "#3C4655", "400", _CANVAS_FONT_STACK,
            ))
        parts.append('</g>')
    footer = str(handoff.get("evidence_footer", ""))
    if footer:
        footer_bounds = layout["footer_bounds"]
        parts += [
            f'<g data-evidence-footer="true" data-layout-x="{footer_bounds["x"]}" data-layout-y="{footer_bounds["y"]}" data-layout-width="{footer_bounds["width"]}" data-layout-height="{footer_bounds["height"]}">',
            _svg_text(_wrap(f"Evidence: {footer}", 94), footer_bounds["x"], footer_bounds["y"] + height*.038, height*.018, "#53606E", "400", _CANVAS_FONT_STACK),
            '</g>',
        ]
    parts.append(f'<desc>Audience role: {escape(audience_role)}. Physical page {page_number} of {page_count}.</desc></svg>')
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")
    return out


def render_storyboard_svg(handoff: dict[str, Any], out: Path, *, private_icon_catalog: dict[str, Any] | None = None) -> Path:
    """Render the final at-a-glance storyboard page with an optional private icon receipt."""
    pages = handoff.get("pages")
    if not isinstance(pages, list) or not pages:
        raise SummaryError("storyboard handoff must contain pages")
    page = next((item for item in pages if isinstance(item, dict) and item.get("role") == "at-a-glance"), pages[-1])
    private = private_icon_catalog if private_icon_catalog is not None else handoff.get("private_icon_resolution", {})
    if not isinstance(private, dict):
        raise SummaryError("private icon catalog must be an object")
    physical = _storyboard_physical_pages([page])
    if len(physical) != 1:
        raise SummaryError("multi-page at-a-glance output requires build_storyboard_outputs")
    return _render_storyboard_page_svg(handoff, physical[0], out, private)


def render_storyboard_png(handoff: dict[str, Any], out: Path, *, private_icon_catalog: dict[str, Any] | None = None) -> Path:
    """Render the final at-a-glance storyboard page as a PNG summary."""
    pages = handoff.get("pages")
    if not isinstance(pages, list) or not pages:
        raise SummaryError("storyboard handoff must contain pages")
    page = next((item for item in pages if isinstance(item, dict) and item.get("role") == "at-a-glance"), pages[-1])
    private = private_icon_catalog if private_icon_catalog is not None else handoff.get("private_icon_resolution", {})
    if not isinstance(private, dict):
        raise SummaryError("private icon catalog must be an object")
    physical = _storyboard_physical_pages([page])
    if len(physical) != 1:
        raise SummaryError("multi-page at-a-glance output requires build_storyboard_outputs")
    return _render_storyboard_page_png(handoff, physical[0], out, private)


def _render_storyboard_page_png(handoff: dict[str, Any], page: dict[str, Any], out: Path, private_icons: dict[str, Any]) -> Path:
    """Render the same native labels/scenes/services as the SVG page without Pillow."""
    width, height = handoff["canvas"]["width"], handoff["canvas"]["height"]
    private_paths = getattr(handoff, "_private_scene_paths", {})
    private_receipts = getattr(handoff, "_private_scene_receipts", {})
    layout = _storyboard_page_layout(handoff, page)
    metadata = _storyboard_png_metadata(handoff, page, layout)
    # Preferred path: compose the same physical layout with actual reviewed
    # pixels and rasterized validated icon SVGs. Every asset falls back alone.
    try:
        from PIL import Image, ImageDraw, ImageFont
        canvas = Image.new("RGBA", (width, height), "#FFF8EC")
        draw = ImageDraw.Draw(canvas)
        role = str(page.get("audience_role", page.get("role", "")))
        font_paths = (
            "/System/Library/Fonts/Supplemental/Comic Sans MS.ttf",
            "/System/Library/Fonts/Supplemental/Chalkboard.ttc",
        )
        def font(size: int):
            for font_path in font_paths:
                try:
                    return ImageFont.truetype(font_path, max(10, size))
                except (OSError, TypeError):
                    continue
            try:
                return ImageFont.load_default(size=max(10, size))
            except TypeError:
                return ImageFont.load_default()
        def draw_wrapped(position: tuple[int, int], value: str, *, max_width: int, fnt, fill: str, spacing: int = 4) -> None:
            words, lines, current = str(value).split(), [], ""
            for word in words:
                candidate = f"{current} {word}".strip()
                if current and draw.textbbox((0, 0), candidate, font=fnt)[2] > max_width:
                    lines.append(current); current = word
                else:
                    current = candidate
            if current: lines.append(current)
            draw.multiline_text(position, "\n".join(lines), font=fnt, fill=fill, spacing=spacing)
        title_font, takeaway_font = font(round(height * .058)), font(round(height * .027))
        scene_title_font, detail_font = font(round(height * .023)), font(round(height * .016))
        service_font, service_meta_font, footer_font = font(round(height * .019)), font(round(height * .012)), font(round(height * .016))
        draw.rectangle((0, int(height * .235), width, int(height * .89)), fill="#E8F4F1")
        draw_wrapped((int(width * .055), int(height * .045)), str(page.get("title", "")), max_width=int(width*.90), fnt=title_font, fill="#18202B")
        draw_wrapped((int(width * .057), int(height * .155)), str(page.get("takeaway", "")), max_width=int(width*.82), fnt=takeaway_font, fill="#3C4655")
        if role == "workflow" and layout["scenes"]:
            points = [(item["bounds"]["x"] + item["bounds"]["width"] // 2, item["bounds"]["y"] + item["bounds"]["height"] // 2) for item in layout["scenes"]]
            draw.line(points, fill="#C74634", width=max(5, round(height*.011)), joint="curve")
            for index, (x, y) in enumerate(points, start=1):
                radius = round(height*.027); draw.ellipse((x-radius, y-round(height*.17)-radius, x+radius, y-round(height*.17)+radius), fill="#18202B")
                draw.text((x-radius//2, y-round(height*.17)-radius), str(index), font=scene_title_font, fill="#FFF8EC")
        elif role == "at-a-glance":
            draw.arc((int(width*.03), int(height*.25), int(width*.97), int(height*.87)), 195, 345, fill="#C74634", width=max(5, round(height*.011)))
            draw.text((int(width*.29), int(height*.845)), "DETECT  >  CORRELATE  >  DIAGNOSE  >  ROUTE", font=service_font, fill="#C74634")
        elif role == "oci-service-map":
            draw.arc((int(width*.08), int(height*.25), int(width*.93), int(height*.81)), 195, 345, fill="#79AAA6", width=max(5, round(height*.010)))
            draw.text((int(width*.07), int(height*.275)), "SIGNALS", font=service_font, fill="#C74634")
            draw.text((int(width*.39), int(height*.78)), "SHARED INCIDENT CONTEXT", font=service_font, fill="#18202B")
            draw.text((int(width*.84), int(height*.275)), "ACTION", font=service_font, fill="#C74634")
            service_roles = {"monitoring": "OWNED SIGNAL", "logging": "SEARCHABLE CONTEXT", "apm": "TRACE + TOPOLOGY", "connector": "APPROVED ROUTE", "analytics": "INVESTIGATION"}
            for service_item in layout["services"]:
                record, bounds = service_item["record"], service_item["bounds"]
                canonical = str(record.get("canonical_service_id", "")).casefold()
                role_label = next((label for token, label in service_roles.items() if token in canonical), "OWNED TELEMETRY")
                center_x = bounds["x"] + bounds["width"] // 2
                draw.line((center_x, bounds["y"] + bounds["height"] + round(height*.10), center_x, round(height*.66)), fill="#79AAA6", width=max(2, round(height*.003)))
                badge = (center_x - round(width*.075), round(height*.635), center_x + round(width*.075), round(height*.685))
                draw.rounded_rectangle(badge, radius=round(height*.018), fill="#F7DDD5", outline="#C74634", width=max(2, round(height*.003)))
                tw = draw.textbbox((0, 0), role_label, font=service_meta_font)[2]
                draw.text((center_x - tw//2, round(height*.650)), role_label, font=service_meta_font, fill="#18202B")
        elif role == "project-promise":
            draw.line((int(width*.06), int(height*.34), int(width*.38), int(height*.49)), fill="#C74634", width=max(5, round(height*.012)))
            draw.text((int(width*.06), int(height*.32)), "ONE INCIDENT THREAD", font=scene_title_font, fill="#C74634")
            draw.multiline_text((int(width*.07), int(height*.41)), "shared context\nclear ownership\nfaster learning", font=takeaway_font, fill="#18202B", spacing=8)
        for item in layout["scenes"]:
            scene, slot, label = item["record"], item["bounds"], item["label_bounds"]
            x, y = slot["x"], slot["y"]
            bounds = (slot["width"], slot["height"])
            payload = _storyboard_scene_bytes(scene, private_paths, private_receipts)
            try:
                if payload is None: raise _OptionalAssetBackendUnavailable("no scene asset")
                art = _decode_scene_image(payload); art.thumbnail(bounds)
                canvas.alpha_composite(art, (x, y))
            except _OptionalAssetBackendUnavailable:
                draw.rectangle((x, y, x + bounds[0], y + bounds[1]), fill="#79AAA6")
                draw.text((x, y + bounds[1] + 4), "Scene fallback", fill="#18202B")
            draw_wrapped((label["x"], label["y"]), str(scene.get("title", "")), max_width=label["width"], fnt=scene_title_font, fill="#18202B")
            if role not in {"workflow", "at-a-glance"}:
                draw_wrapped((label["x"], label["y"] + round(height*.035)), str(scene.get("detail", "")), max_width=label["width"], fnt=detail_font, fill="#3C4655")
        for item in layout["services"]:
            service, slot, label = item["record"], item["bounds"], item["label_bounds"]
            x, y = slot["x"], slot["y"]
            bounds = (slot["width"], slot["height"])
            uri = _storyboard_safe_icon_uri(service, private_icons)
            try:
                if uri is None: raise _OptionalAssetBackendUnavailable("no icon asset")
                icon = _decode_scene_image(_rasterize_verified_svg(_uri_svg_payload(uri), bounds[0], bounds[1]))
                icon.thumbnail(bounds)
                canvas.alpha_composite(icon, (x, y))
            except _OptionalAssetBackendUnavailable:
                # Keep the fallback visual-first and honest.  A neutral,
                # service-shaped glyph is more useful than a blank tile, but
                # it is deliberately not presented as an Oracle stencil.
                draw.rounded_rectangle((x, y, x + bounds[0], y + bounds[1]), radius=max(2, bounds[0] // 8), fill="#FFF2E8", outline="#C74634", width=max(1, bounds[0] // 18))
                pad = max(2, bounds[0] // 6)
                gx0, gy0, gx1, gy1 = x + pad, y + pad, x + bounds[0] - pad, y + bounds[1] - pad
                glyph_kind = _neutral_service_glyph_kind(service)
                if glyph_kind == "logging":
                    for fraction in (.20, .50, .80):
                        line_y = gy0 + int((gy1 - gy0) * fraction)
                        draw.line((gx0, line_y, gx1 - (0 if fraction < .8 else (gx1 - gx0) // 4), line_y), fill="#1F2A36", width=max(1, bounds[0] // 20))
                        draw.ellipse((gx0 - 2, line_y - 2, gx0 + 2, line_y + 2), fill="#C74634")
                elif glyph_kind == "apm":
                    nodes = ((gx0, gy0), (gx1, gy0), ((gx0 + gx1) // 2, gy1))
                    for start, end in ((nodes[0], nodes[1]), (nodes[0], nodes[2]), (nodes[1], nodes[2])):
                        draw.line((*start, *end), fill="#1F2A36", width=max(1, bounds[0] // 24))
                    for node_x, node_y in nodes:
                        radius = max(3, bounds[0] // 12); draw.ellipse((node_x - radius, node_y - radius, node_x + radius, node_y + radius), fill="#79AAA6", outline="#C74634", width=1)
                elif glyph_kind == "service-connector-hub":
                    center_x, center_y = (gx0 + gx1) // 2, (gy0 + gy1) // 2
                    radius = max(4, bounds[0] // 10); draw.ellipse((center_x - radius, center_y - radius, center_x + radius, center_y + radius), fill="#C74634")
                    for node_x, node_y in ((gx0, gy0), (gx1, gy0), (gx0, gy1), (gx1, gy1)):
                        draw.line((center_x, center_y, node_x, node_y), fill="#1F2A36", width=max(1, bounds[0] // 24))
                        draw.ellipse((node_x - radius // 2, node_y - radius // 2, node_x + radius // 2, node_y + radius // 2), fill="#79AAA6")
                elif glyph_kind == "database":
                    draw.ellipse((gx0, gy0, gx1, gy0 + max(4, (gy1 - gy0) // 3)), fill="#C74634", outline="#1F2A36", width=1)
                    draw.rectangle((gx0, gy0 + max(4, (gy1 - gy0) // 6), gx1, gy1 - max(3, (gy1 - gy0) // 6)), fill="#F8DED8", outline="#1F2A36", width=1)
                    draw.arc((gx0, gy1 - max(6, (gy1 - gy0) // 3), gx1, gy1 + max(3, (gy1 - gy0) // 10)), 0, 180, fill="#1F2A36", width=1)
                else:
                    draw.line((gx0, gy1, gx1, gy1), fill="#1F2A36", width=max(1, bounds[0] // 22))
                    for step in range(3):
                        bx0 = gx0 + step * max(1, (gx1 - gx0) // 4)
                        bar = max(2, int((gy1 - gy0) * (0.35 + 0.18 * step)))
                        draw.rounded_rectangle((bx0, gy1 - bar, bx0 + max(2, bounds[0] // 10), gy1), radius=2, fill="#C74634")
                if role not in {"workflow", "at-a-glance"}:
                    draw.text((label["x"], label["y"]), "Neutral service glyph", font=service_meta_font, fill="#18202B")
            display_y = label["y"] + round(height * (0 if role in {"workflow", "at-a-glance"} else .016))
            draw_wrapped((label["x"], display_y), str(service.get("display_name", "")), max_width=label["width"], fnt=service_font, fill="#18202B")
            if role not in {"workflow", "at-a-glance"}:
                draw_wrapped((label["x"], label["y"] + round(height*.050)), f'{service.get("canonical_service_id", "")} — {service.get("mapping_type", "none")}', max_width=label["width"], fnt=service_meta_font, fill="#3C4655")
        footer_bounds = layout["footer_bounds"]
        draw_wrapped((footer_bounds["x"], footer_bounds["y"] + 6), "Evidence: " + str(handoff.get("evidence_footer", "")), max_width=footer_bounds["width"], fnt=footer_font, fill="#53606E")
        out = _safe_output_path(out); canvas.convert("RGB").save(out, format="PNG", optimize=True)
        _attach_storyboard_png_metadata(out, metadata)
        return out
    except ImportError:
        pass
    pixels = bytearray(b"\xff\xf8\xec" * width * height)
    def fill(x: int, y: int, w: int, h: int, color: tuple[int, int, int]) -> None:
        for py in range(max(0, y), min(height, y + h)):
            start = (py * width + max(0, x)) * 3; end = (py * width + min(width, x + w)) * 3
            pixels[start:end] = bytes(color) * max(0, min(width, x + w) - max(0, x))
    def text(x: int, y: int, value: str, color: tuple[int, int, int], scale: int = 1) -> None:
        cursor = x
        for glyph in value.upper()[:90]:
            if glyph == " ": cursor += 4 * scale; continue
            for row, pattern in enumerate(_PIXEL_GLYPHS.get(glyph, _PIXEL_GLYPHS["-"])):
                for col, bit in enumerate(pattern):
                    if bit == "1": fill(cursor + col * scale, y + row * scale, scale, scale, color)
            cursor += 4 * scale
    fill(0, int(height * .28), width, int(height * .52), (232, 244, 241))
    text(int(width * .07), int(height * .07), str(page.get("title", "")), (24, 32, 43), max(1, height // 180))
    text(int(width * .07), int(height * .20), str(page.get("takeaway", "")), (60, 70, 85), max(1, height // 300))
    for item in layout["scenes"]:
        scene, slot, label = item["record"], item["bounds"], item["label_bounds"]
        x, y = slot["x"], slot["y"]
        payload = _storyboard_scene_bytes(scene, private_paths, private_receipts)
        color = _tiny_png_color(payload) if payload else None
        fill(x, y, slot["width"], slot["height"], color or (121, 170, 166))
        text(label["x"], label["y"], str(scene.get("title", "")), (24, 32, 43), max(1, height // 360))
    for item in layout["services"]:
        service, slot, label = item["record"], item["bounds"], item["label_bounds"]
        x, y = slot["x"], slot["y"]
        # Validate the same private icon binding used by SVG.  A deterministic
        # colored tile is an explicit local SVG-raster fallback when no safe
        # converter is present, rather than silently omitting the service.
        icon_uri = _storyboard_safe_icon_uri(service, private_icons)
        icon_color = None
        if icon_uri:
            try:
                icon_color = _tiny_png_color(_rasterize_verified_svg(
                    _uri_svg_payload(icon_uri), slot["width"], slot["height"],
                ))
            except _OptionalAssetBackendUnavailable:
                pass
        digest = hashlib.sha256(icon_uri.encode("ascii")).digest() if icon_uri else b"\xe6\xb9\xae"
        if icon_color is not None:
            fill(x, y, slot["width"], slot["height"], icon_color)
        else:
            # Dependency-free renderer: preserve the same neutral glyph
            # semantics as the Pillow path instead of emitting an opaque tile.
            fill(x, y, slot["width"], slot["height"], (255, 242, 232))
            edge = max(1, slot["width"] // 18)
            fill(x, y, slot["width"], edge, (199, 70, 52)); fill(x, y + slot["height"] - edge, slot["width"], edge, (199, 70, 52))
            base_y = y + slot["height"] - max(2, slot["height"] // 6)
            fill(x + max(2, slot["width"] // 6), base_y, max(2, slot["width"] * 2 // 3), max(1, slot["height"] // 24), (31, 42, 54))
            for step in range(3):
                bx = x + max(2, slot["width"] // 6) + step * max(1, slot["width"] // 5)
                bar = max(2, int(slot["height"] * (0.22 + 0.12 * step)))
                fill(bx, base_y - bar, max(2, slot["width"] // 10), bar, (199, 70, 52))
        text(label["x"], label["y"], str(service.get("display_name", "")), (24, 32, 43), max(1, height // 400))
        if str(page.get("audience_role", page.get("role", ""))) not in {"workflow", "at-a-glance"}:
            text(label["x"], label["y"] + 12, f'{service.get("canonical_service_id", "")} - {service.get("mapping_type", "none")}', (60, 70, 85), max(1, height // 480))
    footer_bounds = layout["footer_bounds"]
    text(footer_bounds["x"], footer_bounds["y"] + 6, "EVIDENCE: " + str(handoff.get("evidence_footer", "")), (83, 96, 110), max(1, height // 480))
    out = _safe_output_path(out)
    raw = b"".join(b"\x00" + bytes(pixels[row * width * 3:(row + 1) * width * 3]) for row in range(height))
    out.write_bytes(b"\x89PNG\r\n\x1a\n" + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)) + _png_chunk(b"tEXt", metadata) + _png_chunk(b"IDAT", zlib.compress(raw, 6)) + _png_chunk(b"IEND", b""))
    return out


def _render_storyboard_page_pdf(handoff: dict[str, Any], page: dict[str, Any], out: Path, private_icons: dict[str, Any]) -> Path:
    """Write selectable operational text and reviewed scene images where available."""
    width, height = handoff["canvas"]["width"], handoff["canvas"]["height"]
    page_w, page_h = 720, 720 * height / width
    layout = _storyboard_page_layout(handoff, page)
    private_paths = getattr(handoff, "_private_scene_paths", {})
    private_receipts = getattr(handoff, "_private_scene_receipts", {})
    verified_scenes: list[tuple[dict[str, Any], bytes]] = []
    for scene in page.get("scenes", []):
        if isinstance(scene, dict):
            payload = _storyboard_scene_bytes(scene, private_paths, private_receipts)
            if payload is not None:
                verified_scenes.append((scene, payload))
    out = _safe_output_path(out)
    lines = [str(page.get("title", "")), str(page.get("takeaway", ""))]
    lines += [f"{scene.get('title', '')}: {scene.get('detail', '')} [{scene.get('evidence_class', '')}]" for scene in page.get("scenes", []) if isinstance(scene, dict)]
    lines += [
        f"{service.get('display_name', '')} ({service.get('canonical_service_id', '')}) — {service.get('mapping_type', 'none')}"
        for service in page.get("services", []) if isinstance(service, dict)
    ]
    if handoff.get("evidence_footer"):
        lines.append("Evidence: " + str(handoff["evidence_footer"]))
    icon_rasters: list[tuple[dict[str, Any], bytes]] = []
    icon_fallbacks: list[dict[str, Any]] = []
    for service in page.get("services", []):
        if not isinstance(service, dict):
            continue
        uri = _storyboard_safe_icon_uri(service, private_icons)
        if uri is None:
            icon_fallbacks.append(service)
        else:
            try:
                icon_rasters.append((service, _rasterize_verified_svg(_uri_svg_payload(uri), 96, 96)))
            except _OptionalAssetBackendUnavailable:
                icon_fallbacks.append(service)
    # ReportLab can still emit the reviewed page when no SVG rasterizer is
    # installed: scenes/icons that cannot be decoded receive their explicit
    # native/neutral visual treatment instead of collapsing the whole page to
    # a text-only fallback.
    if _reportlab_available():
        from reportlab.pdfgen import canvas as report_canvas
        pdf = report_canvas.Canvas(str(out), pagesize=(page_w, page_h))
        title = str(page.get("title", ""))

        def begin_page(section: str) -> None:
            pdf.setFont("Helvetica-Bold", 24)
            pdf.drawString(page_w * .07, page_h * .90, title)
            if section:
                pdf.setFont("Helvetica", 10)
                pdf.drawString(page_w * .07, page_h * .84, section)

        # Native text is never inferred from image decoding and never truncated.
        # Paginate it independently so every service, mapping, evidence class,
        # and source remains selectable even when an asset needs a fallback.
        begin_page("Operator workflow narrative")
        pdf.setFont("Helvetica", 9)
        y = page_h * .77
        text_lines: list[str] = []
        for line in lines[1:]:
            text_lines.extend(_wrap(line, 105) or [""])
        for line in text_lines:
            if y < page_h * .10:
                pdf.showPage()
                begin_page("Operator workflow narrative continued")
                pdf.setFont("Helvetica", 9)
                y = page_h * .77
            pdf.drawString(page_w * .07, y, line)
            y -= 14

        # Treat the selectable narrative as an editorial spread rather than a
        # sparse compliance appendix.  When the copy leaves room, repeat a
        # bounded strip of the reviewed scene art; every narrative page also
        # gets a hand-drawn incident thread with service nodes.  The second
        # page remains the exact layout/evidence projection.
        strip_bottom = page_h * .105
        strip_top = max(strip_bottom, y - 10)
        available_height = strip_top - strip_bottom
        native_scene_methods = ("setStrokeColorRGB", "setFillColorRGB", "setLineWidth", "roundRect", "circle", "line")
        if verified_scenes and available_height >= 58 and all(hasattr(pdf, method) for method in native_scene_methods):
            scene_count = min(4, len(verified_scenes))
            gap = 10
            # Keep the caption in a first-class band below the illustration.
            # Previously it was drawn inside the card, where short titles
            # could cross the character or signal artwork at native PDF size.
            caption_height = 13
            caption_gap = 7
            strip_width = page_w * .80
            cell_width = (strip_width - gap * (scene_count - 1)) / scene_count
            cell_height = min(
                available_height - caption_height - caption_gap - 8,
                page_h * (.34 if scene_count == 1 else .22),
            )
            start_x = page_w * .10
            for scene_index, (scene, _payload) in enumerate(verified_scenes[:scene_count]):
                cell_x = start_x + scene_index * (cell_width + gap)
                cell_y = strip_bottom + caption_height + caption_gap
                accent_rgb = ((.78, .27, .20), (.18, .52, .66), (.43, .35, .66), (.72, .39, .10))[scene_index % 4]
                pdf.setStrokeColorRGB(*accent_rgb)
                pdf.setFillColorRGB(1.0, .98, .94)
                pdf.setLineWidth(1.6)
                pdf.roundRect(cell_x, cell_y, cell_width, cell_height, 10, stroke=1, fill=1)
                # Recurring responder + signal object, drawn as native vectors
                # so the selectable PDF asset contract retains one image per
                # reviewed source asset on the evidence page only.
                head_x = cell_x + cell_width * .22
                head_y = cell_y + cell_height * .54
                pdf.setFillColorRGB(.86, .58, .34)
                pdf.circle(head_x, head_y, min(12, cell_height * .12), stroke=1, fill=1)
                pdf.setFillColorRGB(*accent_rgb)
                pdf.roundRect(head_x - 12, cell_y + cell_height * .15, 24, cell_height * .26, 3, stroke=1, fill=1)
                object_x = cell_x + cell_width * .58
                object_y = cell_y + cell_height * .28
                pdf.setFillColorRGB(.90, .96, .96)
                pdf.roundRect(object_x, object_y, cell_width * .25, cell_height * .34, 5, stroke=1, fill=1)
                pdf.line(head_x + 10, head_y - 6, object_x + 4, object_y + cell_height * .16)
                pdf.setFillColorRGB(0, 0, 0)
                pdf.setFont("Helvetica-Bold", 7)
                pdf.drawString(cell_x + 7, strip_bottom + 3, str(scene.get("title", "Capability"))[:38])
        # Organic red thread and mapped service nodes make the reading path
        # visible even on dense narrative pages where a full art strip would
        # collide with the native text.
        thread_y = page_h * .065
        if all(hasattr(pdf, method) for method in ("setStrokeColorRGB", "setLineWidth", "bezier", "setFillColorRGB", "circle")):
            pdf.setStrokeColorRGB(0.78, 0.27, 0.20)
            pdf.setLineWidth(2.2)
            pdf.bezier(page_w * .10, thread_y, page_w * .32, thread_y + 18,
                       page_w * .67, thread_y - 12, page_w * .90, thread_y + 8)
            services_for_thread = [service for service in page.get("services", []) if isinstance(service, dict)]
            for service_index, _service in enumerate(services_for_thread[:8]):
                node_x = page_w * (.12 + .76 * ((service_index + .5) / max(1, len(services_for_thread))))
                pdf.setFillColorRGB(1.0, 0.95, 0.91)
                pdf.circle(node_x, thread_y + (5 if service_index % 2 else 0), 5.5, stroke=1, fill=1)
            pdf.setFillColorRGB(0, 0, 0)
        pdf.showPage()

        # The asset page consumes the exact same bounded pixel slots as SVG and
        # PNG, but uses a dedicated PDF editorial grid so captions and service
        # glyphs cannot collide at small page sizes.
        scene_payloads = {str(record.get("unit_id", "")): payload for record, payload in verified_scenes}
        icon_payloads = {str(record.get("canonical_service_id", "")): payload for record, payload in icon_rasters}
        begin_page("Reviewed visual evidence")
        pdf.setFont("Helvetica", 8)
        pdf_geometry = _pdf_reviewed_evidence_geometry(page, page_w, page_h)
        evidence_items = list(zip(("Scene",) * len(pdf_geometry["scenes"]), pdf_geometry["scenes"], [item["record"] for item in layout["scenes"]]))
        evidence_items += list(zip(("Icon",) * len(pdf_geometry["services"]), pdf_geometry["services"], [item["record"] for item in layout["services"]]))
        for kind, zone, record in evidence_items:
            key = str(record.get("unit_id", "")) if kind == "Scene" else str(record.get("canonical_service_id", ""))
            payload = scene_payloads.get(key) if kind == "Scene" else icon_payloads.get(key)
            x, y, asset_width, asset_height, label_zone = zone
            try:
                if payload is None:
                    raise _OptionalAssetBackendUnavailable("no local asset image")
                _pdf_draw_asset(pdf, payload, x, y, asset_width, asset_height)
            except _OptionalAssetBackendUnavailable:
                if kind == "Icon":
                    _pdf_draw_neutral_service_glyph(pdf, x, y, asset_width, asset_height, record)
                else:
                    pdf.drawString(x, y + asset_height * .45, f"{kind} image fallback: native text")
            label = record.get("title") if kind == "Scene" else record.get("display_name")
            label_x, label_y, label_width, _label_height = label_zone
            pdf.setFont("Helvetica", 7 if kind == "Scene" else 6)
            pdf.drawString(label_x, max(10, label_y), f"{kind}: {label or ''}")
        footer_x, footer_y, _footer_width, _footer_height = pdf_geometry["footer"]
        pdf.setFont("Helvetica", 8)
        pdf.drawString(footer_x, max(8, footer_y), "Evidence: " + str(handoff.get("evidence_footer", "")))
        if icon_fallbacks:
            pdf.setFont("Helvetica", 6)
            pdf.drawString(footer_x, max(3, footer_y - 8), "Render note: portable neutral glyphs preserve non-Draw.io service identity.")
        pdf.showPage()
        pdf.save()
        return out
    else:
        lines.append("Scene image fallback: native text")
    if icon_fallbacks:
        lines.append(f"Icon image fallback: native text ({len(icon_fallbacks)})")
    commands = ["1 0.973 0.925 rg 0 0 %.2f %.2f re f" % (page_w, page_h)]
    _pdf_text(commands, _wrap(" ".join(lines), 92), page_w * .07, page_h * .84, 10, (24, 32, 43))
    return _write_basic_pdf(out, page_w, page_h, commands)


def render_storyboard_pdf(handoff: dict[str, Any], out: Path, *, private_icon_catalog: dict[str, Any] | None = None) -> Path:
    """Render the final at-a-glance storyboard page as a PDF summary."""
    pages = handoff.get("pages")
    if not isinstance(pages, list) or not pages:
        raise SummaryError("storyboard handoff must contain pages")
    page = next((item for item in pages if isinstance(item, dict) and item.get("role") == "at-a-glance"), pages[-1])
    private = private_icon_catalog if private_icon_catalog is not None else handoff.get("private_icon_resolution", {})
    if not isinstance(private, dict):
        raise SummaryError("private icon catalog must be an object")
    physical = _storyboard_physical_pages([page])
    if len(physical) != 1:
        raise SummaryError("multi-page at-a-glance output requires build_storyboard_outputs")
    return _render_storyboard_page_pdf(handoff, physical[0], out, private)


def build_storyboard_outputs(handoff: dict[str, Any], out_dir: Path, formats: set[str], *, private_icon_catalog: dict[str, Any] | None = None) -> list[Path]:
    """Render the five sequence roles plus the final summary without publishing private bytes."""
    requested = set(formats)
    if not requested or requested - {"svg", "png", "pdf"}:
        raise SummaryError("storyboard outputs support svg, png, and pdf")
    pages = handoff.get("pages")
    if not isinstance(pages, list) or [page.get("role") for page in pages if isinstance(page, dict)] != list(_STORYBOARD_ROLES):
        raise SummaryError("storyboard audience roles must be complete and ordered")
    out_dir = Path(out_dir).absolute(); out_dir.mkdir(parents=True, exist_ok=True)
    private = private_icon_catalog or {}
    outputs: list[Path] = []
    physical_pages = _storyboard_physical_pages(pages)
    for page in physical_pages:
        role = page["role"]
        if "svg" in requested:
            outputs.append(_render_storyboard_page_svg(handoff, page, out_dir / f"{role}.svg", private))
    if "svg" in requested:
        final_pages = [page for page in physical_pages if page.get("audience_role") == "at-a-glance"]
        if len(final_pages) == 1:
            outputs.append(_render_storyboard_page_svg(handoff, final_pages[0], out_dir / "summary.svg", private))
    # Native text fallback preserves the operator-facing document even where a
    # local SVG rasterizer/PDF icon backend is unavailable.
    for kind in requested - {"svg"}:
        for page in physical_pages:
            target = _safe_output_path(out_dir / f"{page['role']}.{kind}")
            if kind == "png":
                _render_storyboard_page_png(handoff, page, target, private)
            else:
                _render_storyboard_page_pdf(handoff, page, target, private)
            outputs.append(target)
    return outputs


def _storyboard_docx_preview_manifest(
    handoff: dict[str, Any],
    out_dir: Path,
    *,
    private_icon_catalog: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Render one private PNG preview per physical storyboard page for DOCX."""
    if handoff.get("concept") != "illo-storyboard-sequence-v1" or not isinstance(handoff.get("pages"), list):
        return []
    private = private_icon_catalog if private_icon_catalog is not None else handoff.get("private_icon_resolution", {})
    preview_root = out_dir / "storyboard-page-previews"
    preview_root.mkdir(parents=True, exist_ok=True)
    role_labels = {
        "project-promise": "Project promise",
        "workflow": "Workflow",
        "capability-scenes": "Capability scenes",
        "oci-service-map": "OCI service map",
        "at-a-glance": "At a glance",
    }
    manifest = []
    for index, page in enumerate(_storyboard_physical_pages(handoff["pages"]), start=1):
        role = str(page.get("role", "storyboard"))
        audience_role = str(page.get("audience_role", role))
        target = preview_root / f"{index:02d}-{role}.png"
        _render_storyboard_page_png(handoff, page, target, private if isinstance(private, dict) else {})
        title = str(page.get("title", role_labels.get(audience_role, audience_role.replace("-", " ").title())))
        manifest.append(
            {
                "audience_role": audience_role,
                "role": role,
                "title": title,
                "page_number": int(page.get("page_number", 1)),
                "page_count": int(page.get("page_count", 1)),
                "path": str(target),
                "alt_text": title,
            }
        )
    return manifest


def _is_storyboard_sequence(handoff: dict[str, Any]) -> bool:
    """Return whether ``handoff`` is the bounded, prompt-free storyboard projection."""
    return handoff.get("concept") == "illo-storyboard-sequence-v1" and isinstance(handoff.get("pages"), list)


def _storyboard_canvas(handoff: dict[str, Any]) -> tuple[int, int]:
    canvas = handoff.get("canvas", {})
    if not isinstance(canvas, dict):
        raise SummaryError("storyboard handoff has an invalid canvas")
    width, height = canvas.get("width"), canvas.get("height")
    if not isinstance(width, int) or not isinstance(height, int) or width <= 0 or height <= 0:
        raise SummaryError("storyboard handoff has an invalid canvas")
    return width, height


def _storyboard_private_scene_state(handoff: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return in-process scene receipts without serializing their private locations."""
    return (
        getattr(handoff, "_private_scene_paths", {}),
        getattr(handoff, "_private_scene_receipts", {}),
    )


def _storyboard_service_context(handoff: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Bind a resolved service to its accepted unit evidence without exposing private receipts."""
    context: dict[str, dict[str, Any]] = {}
    for page in handoff.get("pages", []):
        if not isinstance(page, dict):
            continue
        for scene in page.get("scenes", []):
            if isinstance(scene, dict) and isinstance(scene.get("unit_id"), str):
                context.setdefault(scene["unit_id"], {
                    "evidence_class": str(scene.get("evidence_class", "")),
                    "source_refs": [str(source) for source in scene.get("source_ids", []) if isinstance(source, str)],
                })
    return context


def _editable_private_icons(handoff: dict[str, Any], private_icon_catalog: dict[str, Any] | None) -> dict[str, Any]:
    """Prefer an explicit in-process icon receipt; retain old private handoff compatibility."""
    private = private_icon_catalog if private_icon_catalog is not None else handoff.get("private_icon_resolution", {})
    if not isinstance(private, dict):
        raise SummaryError("storyboard icon resolution must be a receipt dictionary")
    return private


def _render_storyboard_drawio(handoff: dict[str, Any], out: Path, private_icon_catalog: dict[str, Any] | None = None) -> Path:
    """Project every physical storyboard page into separately editable Draw.io diagrams."""
    width, height = _storyboard_canvas(handoff)
    out = _safe_output_path(Path(out))
    pages = _storyboard_physical_pages(handoff["pages"])
    private_icons = _editable_private_icons(handoff, private_icon_catalog)
    private_paths, private_receipts = _storyboard_private_scene_state(handoff)
    service_context = _storyboard_service_context(handoff)
    diagrams: list[str] = []
    for page_index, page in enumerate(pages, start=1):
        role = str(page["role"])
        layout = _storyboard_page_layout(handoff, page)
        cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
        # Connectors deliberately precede nodes so Draw.io can resolve a stable
        # topology even when the reader edits or replaces scene assets.
        scene_items = layout["scenes"]
        for index, item in enumerate(scene_items, start=1):
            source = "storyboard-title" if index == 1 else f"scene-node-{index - 1}"
            target = f"scene-node-{index}"
            cells.append(
                f'<mxCell id="storyboard-link-{index}" value="" edge="1" parent="1" source="{source}" target="{target}" '
                'summaryKind="oci.visual-summary.storyboard-connector" '
                'style="edgeStyle=orthogonalEdgeStyle;rounded=1;endArrow=block;strokeColor=#4F7C92;strokeWidth=2;">'
                '<mxGeometry relative="1" as="geometry"/></mxCell>'
            )
        title = str(page.get("title", handoff.get("title", "")))
        cells.append(
            f'<UserObject id="storyboard-page-{page_index}" label="{escape(title, quote=True)}" '
            f'summaryKind="oci.visual-summary.storyboard-page" audienceRole="{escape(str(page.get("audience_role", role)), quote=True)}" '
            f'physicalRole="{escape(role, quote=True)}" pageNumber="{int(page.get("page_number", 1))}" pageCount="{int(page.get("page_count", 1))}" readingOrder="{page_index}">'
            '<mxCell vertex="1" parent="1" style="shape=rectangle;fillColor=#FFFDF8;strokeColor=#79AAA6;strokeWidth=2;rounded=1;">'
            f'<mxGeometry x="0" y="0" width="{width}" height="{height}" as="geometry"/></mxCell></UserObject>'
        )
        cells.append(
            f'<mxCell id="storyboard-title" value="{escape(title, quote=True)}" vertex="1" parent="1" summaryKind="oci.visual-summary.native-text" readingOrder="1" '
            'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize=28;fontStyle=1;align=left;verticalAlign=top;">'
            f'<mxGeometry x="{int(width * .06)}" y="{int(height * .06)}" width="{int(width * .88)}" height="{int(height * .12)}" as="geometry"/></mxCell>'
        )
        page_takeaway = str(page.get("takeaway", handoff.get("takeaway", "")))
        if page_takeaway:
            cells.append(
                f'<mxCell id="storyboard-takeaway" value="{escape(page_takeaway, quote=True)}" vertex="1" parent="1" summaryKind="oci.visual-summary.native-text" readingOrder="2" '
                'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize=15;align=left;verticalAlign=top;">'
                f'<mxGeometry x="{int(width * .06)}" y="{int(height * .18)}" width="{int(width * .88)}" height="{int(height * .09)}" as="geometry"/></mxCell>'
            )
        reading_order = 10
        for index, item in enumerate(scene_items, start=1):
            record, bounds, label = item["record"], item["bounds"], item["label_bounds"]
            unit_id = str(record.get("unit_id", ""))
            sources = "; ".join(str(source) for source in record.get("source_ids", []) if isinstance(source, str))
            cells.append(
                f'<UserObject id="storyboard-scene-{page_index}-{index}" label="" summaryKind="oci.visual-summary.scene-slot" '
                f'unitId="{escape(unit_id, quote=True)}" evidenceClass="{escape(str(record.get("evidence_class", "")), quote=True)}" '
                f'sourceRefs="{escape(sources, quote=True)}" readingOrder="{reading_order}"><mxCell id="scene-node-{index}" vertex="1" parent="1" '
                'style="shape=rectangle;rounded=1;whiteSpace=wrap;fillColor=#F4FAF8;strokeColor=#79AAA6;strokeWidth=2;">'
                f'<mxGeometry x="{bounds["x"]}" y="{bounds["y"]}" width="{bounds["width"]}" height="{bounds["height"]}" as="geometry"/></mxCell></UserObject>'
            )
            scene_uri = _storyboard_scene_uri(record, private_paths, private_receipts)
            if scene_uri:
                cells.append(
                    f'<UserObject id="storyboard-image-{page_index}-{index}" label="{escape(str(record.get("alt_text", "Supporting scene")), quote=True)}" '
                    f'summaryKind="oci.visual-summary.replaceable-scene" unitId="{escape(unit_id, quote=True)}" readingOrder="{reading_order + 1}"><mxCell vertex="1" parent="1" '
                    f'style="shape=image;imageAspect=1;aspect=fixed;image={escape(scene_uri, quote=True)};strokeColor=none;fillColor=none;">'
                    f'<mxGeometry x="{bounds["x"]}" y="{bounds["y"]}" width="{bounds["width"]}" height="{bounds["height"]}" as="geometry"/></mxCell></UserObject>'
                )
            copy = f'&lt;b&gt;{escape(str(record.get("title", "")), quote=True)}&lt;/b&gt;&lt;br&gt;{escape(str(record.get("detail", "")), quote=True)}&lt;br&gt;{escape(str(record.get("evidence_class", "")), quote=True)}'
            cells.append(
                f'<mxCell id="storyboard-copy-{page_index}-{index}" value="{copy}" vertex="1" parent="1" summaryKind="oci.visual-summary.native-text" unitId="{escape(unit_id, quote=True)}" sourceRefs="{escape(sources, quote=True)}" readingOrder="{reading_order + 2}" '
                'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize=13;align=left;verticalAlign=top;">'
                f'<mxGeometry x="{label["x"]}" y="{label["y"]}" width="{label["width"]}" height="{label["height"]}" as="geometry"/></mxCell>'
            )
            reading_order += 3
        for index, item in enumerate(layout["services"], start=1):
            record, bounds, label = item["record"], item["bounds"], item["label_bounds"]
            canonical_id, display_name = str(record.get("canonical_service_id", "")), str(record.get("display_name", ""))
            mapping = str(record.get("mapping_type", "none"))
            unit_id = str(record.get("unit_id", ""))
            lineage = service_context.get(unit_id, {"evidence_class": "", "source_refs": []})
            evidence_class, source_refs = str(lineage["evidence_class"]), "; ".join(lineage["source_refs"])
            icon_uri = _storyboard_safe_icon_uri(record, private_icons)
            public_stencil_style = _official_public_drawio_style(record)
            if icon_uri:
                icon_style = (
                    f'{public_stencil_style}imageAspect=1;aspect=fixed;strokeColor=none;fillColor=none;'
                    if public_stencil_style else
                    f'shape=image;imageAspect=1;aspect=fixed;image={escape(icon_uri, quote=True)};strokeColor=none;fillColor=none;'
                )
                cells.append(
                    f'<UserObject id="storyboard-icon-{page_index}-{index}" label="{escape(str(record.get("alt_text", display_name)), quote=True)}" summaryKind="oci.visual-summary.service-icon" '
                    f'unitId="{escape(unit_id, quote=True)}" canonicalServiceId="{escape(canonical_id, quote=True)}" displayName="{escape(display_name, quote=True)}" mappingType="{escape(mapping, quote=True)}" publicStencilKey="{escape(str(record.get("public_stencil_key", "")), quote=True)}" provenance="{escape(str(record.get("provenance", "")), quote=True)}" renderedAs="{("official-public-drawio-stencil" if public_stencil_style else escape(str(_non_drawio_stencil_semantics(record).get("rendered_as", "native-text")), quote=True))}" evidenceClass="{escape(evidence_class, quote=True)}" sourceRefs="{escape(source_refs, quote=True)}" readingOrder="{reading_order}"><mxCell vertex="1" parent="1" '
                    f'style="{escape(icon_style, quote=True)}">'
                    f'<mxGeometry x="{bounds["x"]}" y="{bounds["y"]}" width="{bounds["width"]}" height="{bounds["height"]}" as="geometry"/></mxCell></UserObject>'
                )
            service_copy = f'&lt;b&gt;{escape(display_name, quote=True)}&lt;/b&gt;&lt;br&gt;{escape(mapping, quote=True)}'
            cells.append(
                f'<mxCell id="storyboard-service-copy-{page_index}-{index}" value="{service_copy}" vertex="1" parent="1" summaryKind="oci.visual-summary.native-text" unitId="{escape(unit_id, quote=True)}" canonicalServiceId="{escape(canonical_id, quote=True)}" displayName="{escape(display_name, quote=True)}" mappingType="{escape(mapping, quote=True)}" evidenceClass="{escape(evidence_class, quote=True)}" sourceRefs="{escape(source_refs, quote=True)}" readingOrder="{reading_order + 1}" '
                'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize=12;align=left;verticalAlign=top;">'
                f'<mxGeometry x="{label["x"]}" y="{label["y"]}" width="{label["width"]}" height="{label["height"]}" as="geometry"/></mxCell>'
            )
            reading_order += 2
        footer = str(handoff.get("evidence_footer", ""))
        cells.append(
            f'<mxCell id="storyboard-evidence" value="Evidence: {escape(footer, quote=True)}" vertex="1" parent="1" summaryKind="oci.visual-summary.evidence" readingOrder="999" '
            'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize=10;align=left;verticalAlign=top;">'
            f'<mxGeometry x="{int(width * .06)}" y="{int(height * .92)}" width="{int(width * .88)}" height="{max(1, int(height * .06))}" as="geometry"/></mxCell>'
        )
        model = f'<mxGraphModel grid="1" gridSize="10" page="1" pageScale="1" pageWidth="{width}" pageHeight="{height}"><root>{"".join(cells)}</root></mxGraphModel>'
        diagrams.append(f'<diagram id="storyboard-{page_index}" name="{escape(role, quote=True)}">{model}</diagram>')
    out.write_text(f'<mxfile host="app.diagrams.net" agent="oci-visual-summary" version="1">{"".join(diagrams)}</mxfile>\n', encoding="utf-8")
    return out


def render_drawio(handoff: dict[str, Any], out: Path, *, private_icon_catalog: dict[str, Any] | None = None) -> Path:
    """Render an editable Draw.io story map with bounded embedded art slots."""
    if _is_storyboard_sequence(handoff):
        return _render_storyboard_drawio(handoff, out, private_icon_catalog)
    if _is_canvas_story_map(handoff):
        return _render_canvas_drawio(handoff, out)
    width, height = _require_handoff(handoff)
    out = _safe_output_path(Path(out))
    accent = str(handoff["profile"]["primary_accent"])
    secondary = str(handoff["profile"]["secondary_accent"])
    layers = ("Background", "Journey", "Scenes", "Artwork", "Text", "Evidence")
    layer_ids = {name: f"layer-{index + 2}" for index, name in enumerate(layers)}
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    cells.extend(f'<mxCell id="{layer_ids[name]}" value="{name}" parent="0"/>' for name in layers)
    cells.append(
        f'<mxCell id="paper" value="" vertex="1" parent="{layer_ids["Background"]}" '
        f'style="shape=rectangle;fillColor=#FFFDF8;strokeColor=none;locked=1;"><mxGeometry x="0" y="0" width="{width}" height="{height}" as="geometry"/></mxCell>'
    )
    headline = handoff["headline_zone"]
    cells.append(
        f'<mxCell id="title" value="{escape(str(headline["title"]), quote=True)}" vertex="1" parent="{layer_ids["Text"]}" '
        'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize=38;fontStyle=1;align=left;verticalAlign=top;">'
        f'<mxGeometry x="{headline["bounds"]["x"]}" y="{headline["bounds"]["y"]}" width="{headline["bounds"]["width"]}" height="80" as="geometry"/></mxCell>'
    )
    cells.append(
        f'<mxCell id="takeaway" value="{escape(str(headline["takeaway"]), quote=True)}" vertex="1" parent="{layer_ids["Text"]}" '
        'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize=18;align=left;verticalAlign=top;">'
        f'<mxGeometry x="{headline["bounds"]["x"]}" y="{headline["bounds"]["y"] + 90}" width="{headline["bounds"]["width"]}" height="50" as="geometry"/></mxCell>'
    )
    points = handoff.get("dominant_path", {}).get("points", [])
    for index, (start, end) in enumerate(zip(points, points[1:]), start=1):
        cells.append(
            f'<mxCell id="journey-{index}" value="" edge="1" parent="{layer_ids["Journey"]}" source="scene-anchor-{index}" target="scene-anchor-{index + 1}" summaryKind="oci.visual-summary.path" '
            f'style="edgeStyle=curvedEdgeStyle;rounded=1;endArrow={"block" if index == len(points) - 1 else "none"};strokeColor={accent};strokeWidth=5;sketch=1;">'
            f'<mxGeometry relative="1" as="geometry"><mxPoint x="{start["x"]}" y="{start["y"]}" as="sourcePoint"/><mxPoint x="{end["x"]}" y="{end["y"]}" as="targetPoint"/></mxGeometry></mxCell>'
        )
    for cluster in handoff["clusters"]:
        anchor = escape(str(cluster["anchor_id"]), quote=True)
        bounds = cluster["bounds"]
        cells.append(
            f'<UserObject id="scene-{anchor}" label="" summaryKind="oci.visual-summary.scene" '
            f'artRole="{escape(str(cluster.get("art_direction", {}).get("asset_role", "scene")), quote=True)}">'
            f'<mxCell vertex="1" parent="{layer_ids["Scenes"]}" '
            f'style="shape=cloud;whiteSpace=wrap;html=1;fillColor=#FFFDF8;strokeColor={secondary};strokeWidth=2;rough=1;sketch=1;">'
            f'<mxGeometry x="{bounds["x"]}" y="{bounds["y"]}" width="{bounds["width"]}" height="{bounds["height"]}" as="geometry"/></mxCell>'
            '</UserObject>'
        )
        cells.append(
            f'<mxCell id="text-{anchor}" value="&lt;b&gt;{escape(str(cluster["title"]), quote=True)}&lt;/b&gt;&lt;br&gt;{escape(str(cluster["detail"]), quote=True)}&lt;br&gt;&lt;font color=&quot;{accent}&quot;&gt;{escape(str(cluster["evidence_class"]).upper(), quote=True)}&lt;/font&gt;" '
            f'vertex="1" parent="{layer_ids["Text"]}" style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize=15;align=left;verticalAlign=top;spacing=12;">'
            f'<mxGeometry x="{bounds["x"] + 18}" y="{bounds["y"] + 22}" width="{bounds["width"] * .58:.1f}" height="{bounds["height"] - 36}" as="geometry"/></mxCell>'
        )
        art = _art_data_uri(cluster)
        slot = cluster.get("art_slot", {})
        if art:
            cells.append(
                f'<UserObject id="art-{anchor}" label="{escape(str(cluster.get("art", {}).get("alt_text", "Supporting illustration")), quote=True)}" '
                f'sha256="{escape(str(cluster.get("art", {}).get("sha256", "")), quote=True)}"><mxCell vertex="1" parent="{layer_ids["Artwork"]}" '
                f'style="shape=image;imageAspect=1;aspect=fixed;image={escape(art, quote=True)};strokeColor=none;fillColor=none;">'
                f'<mxGeometry x="{slot["x"]}" y="{slot["y"]}" width="{slot["width"]}" height="{slot["height"]}" as="geometry"/></mxCell></UserObject>'
            )
    footer = escape(str(handoff.get("evidence_footer", "")), quote=True)
    cells.append(
        f'<mxCell id="evidence" value="Evidence: {footer}" vertex="1" parent="{layer_ids["Evidence"]}" '
        'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize=11;align=left;">'
        f'<mxGeometry x="{width * .07:.1f}" y="{height * .93:.1f}" width="{width * .86:.1f}" height="32" as="geometry"/></mxCell>'
    )
    model = f'<mxGraphModel grid="1" gridSize="10" page="1" pageScale="1" pageWidth="{width}" pageHeight="{height}"><root>{"".join(cells)}</root></mxGraphModel>'
    payload = f'<mxfile host="app.diagrams.net" agent="oci-visual-summary" version="1"><diagram id="oci-visual-summary" name="At a glance">{model}</diagram></mxfile>\n'
    out.write_text(payload, encoding="utf-8")
    return out


def _render_canvas_drawio(handoff: dict[str, Any], out: Path) -> Path:
    """Render the Canvas variant without legacy scene shells or card geometry.

    Scene images and annotations intentionally remain separate editable objects:
    replacing an image never modifies the anchor copy or the shared control
    thread.  This branch is opt-in so legacy Draw.io exports remain stable.
    """
    width, height = _require_handoff(handoff)
    out = _safe_output_path(Path(out))
    accent = str(handoff["profile"]["primary_accent"])
    secondary = str(handoff["profile"]["secondary_accent"])
    layers = ("Background", "Control thread", "Scene artwork", "Scene annotations", "Evidence")
    layer_ids = {name: f"canvas-layer-{index + 2}" for index, name in enumerate(layers)}
    cells = ['<mxCell id="0"/>', '<mxCell id="1" parent="0"/>']
    cells.extend(f'<mxCell id="{layer_ids[name]}" value="{name}" parent="0"/>' for name in layers)
    cells.append(
        f'<mxCell id="canvas-paper" value="" vertex="1" parent="{layer_ids["Background"]}" '
        f'style="shape=rectangle;fillColor=#FFF8EC;strokeColor=none;locked=1;"><mxGeometry x="0" y="0" width="{width}" height="{height}" as="geometry"/></mxCell>'
    )
    headline = handoff["headline_zone"]
    for element_id, text, y, size, style in (
        ("canvas-title", headline["title"], headline["bounds"]["y"], 38, "fontStyle=1;"),
        ("canvas-takeaway", headline["takeaway"], headline["bounds"]["y"] + 90, 18, ""),
    ):
        cells.append(
            f'<mxCell id="{element_id}" value="{escape(str(text), quote=True)}" vertex="1" parent="{layer_ids["Scene annotations"]}" '
            f'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize={size};{style}align=left;verticalAlign=top;">'
            f'<mxGeometry x="{headline["bounds"]["x"]}" y="{y}" width="{headline["bounds"]["width"]}" height="80" as="geometry"/></mxCell>'
        )
    # Stable invisible callout nodes bind the red control thread without
    # coupling it to the replaceable image or editable annotation objects.
    for cluster in handoff["clusters"]:
        anchor = escape(str(cluster["anchor_id"]), quote=True)
        text_bounds = cluster.get("text_bounds", cluster["bounds"])
        center_x = float(text_bounds["x"]) + float(text_bounds["width"]) / 2
        center_y = float(text_bounds["y"]) + float(text_bounds["height"]) / 2
        cells.append(
            f'<mxCell id="canvas-callout-{anchor}" value="" vertex="1" parent="{layer_ids["Scene annotations"]}" '
            f'summaryKind="oci.visual-summary.canvas-callout" anchorId="{anchor}" '
            'style="shape=ellipse;opacity=0;fillOpacity=0;strokeOpacity=0;resizable=0;movable=0;">'
            f'<mxGeometry x="{center_x - 2:.1f}" y="{center_y - 2:.1f}" width="4" height="4" as="geometry"/></mxCell>'
        )
    points = handoff.get("canvas_layout", {}).get("thread", {}).get("points", [])
    for index, (start, end) in enumerate(zip(points, points[1:]), start=1):
        cells.append(
            f'<mxCell id="canvas-thread-{index}" value="" edge="1" parent="{layer_ids["Control thread"]}" source="canvas-callout-anchor-{index}" target="canvas-callout-anchor-{index + 1}" summaryKind="oci.visual-summary.canvas-thread" '
            f'style="edgeStyle=curvedEdgeStyle;rounded=1;endArrow={"block" if index == len(points) - 1 else "none"};strokeColor={accent};strokeWidth=5;sketch=1;">'
            f'<mxGeometry relative="1" as="geometry"><mxPoint x="{start["x"]}" y="{start["y"]}" as="sourcePoint"/><mxPoint x="{end["x"]}" y="{end["y"]}" as="targetPoint"/></mxGeometry></mxCell>'
        )
    for cluster in handoff["clusters"]:
        anchor = escape(str(cluster["anchor_id"]), quote=True)
        role = escape(str(cluster.get("canvas_role", "scene")), quote=True)
        art_bounds = cluster.get("art_bounds", cluster.get("art_slot", {}))
        text_bounds = cluster.get("text_bounds", cluster["bounds"])
        art = _art_data_uri(cluster)
        if art:
            cells.append(
                f'<UserObject id="image-{anchor}" label="{escape(str(cluster.get("art", {}).get("alt_text", "Supporting scene illustration")), quote=True)}" '
                f'summaryKind="oci.visual-summary.canvas-scene" anchorId="{anchor}" canvasRole="{role}" sha256="{escape(str(cluster.get("art", {}).get("sha256", "")), quote=True)}">'
                f'<mxCell vertex="1" parent="{layer_ids["Scene artwork"]}" style="shape=image;imageAspect=1;aspect=fixed;image={escape(art, quote=True)};strokeColor={secondary};strokeWidth=1;sketch=1;">'
                f'<mxGeometry x="{art_bounds["x"]}" y="{art_bounds["y"]}" width="{art_bounds["width"]}" height="{art_bounds["height"]}" as="geometry"/></mxCell></UserObject>'
            )
        label = (
            f'&lt;b&gt;{escape(str(cluster["title"]), quote=True)}&lt;/b&gt;&lt;br&gt;'
            f'{escape(str(cluster["detail"]), quote=True)}&lt;br&gt;'
            f'&lt;font color=&quot;{accent}&quot;&gt;{escape(str(cluster["evidence_class"]).upper(), quote=True)}&lt;/font&gt;'
        )
        cells.append(
            f'<UserObject id="annotation-{anchor}" label="" summaryKind="oci.visual-summary.canvas-annotation" anchorId="{anchor}" canvasRole="{role}">'
            f'<mxCell vertex="1" parent="{layer_ids["Scene annotations"]}" value="{label}" style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize=15;align=left;verticalAlign=top;spacing=8;">'
            f'<mxGeometry x="{text_bounds["x"]}" y="{text_bounds["y"]}" width="{text_bounds["width"]}" height="{text_bounds["height"]}" as="geometry"/></mxCell></UserObject>'
        )
    footer = escape(str(handoff.get("evidence_footer", "")), quote=True)
    cells.append(
        f'<mxCell id="canvas-evidence" value="Evidence: {footer}" vertex="1" parent="{layer_ids["Evidence"]}" '
        'style="text;html=1;whiteSpace=wrap;strokeColor=none;fillColor=none;fontFamily=Arial;fontSize=11;align=left;">'
        f'<mxGeometry x="{width * .07:.1f}" y="{height * .93:.1f}" width="{width * .86:.1f}" height="32" as="geometry"/></mxCell>'
    )
    model = f'<mxGraphModel grid="1" gridSize="10" page="1" pageScale="1" pageWidth="{width}" pageHeight="{height}"><root>{"".join(cells)}</root></mxGraphModel>'
    out.write_text(f'<mxfile host="app.diagrams.net" agent="oci-visual-summary" version="1"><diagram id="oci-visual-summary" name="At a glance">{model}</diagram></mxfile>\n', encoding="utf-8")
    return out


def _render_storyboard_excalidraw(handoff: dict[str, Any], out: Path, private_icon_catalog: dict[str, Any] | None = None) -> Path:
    """Render the bounded storyboard as editable Excalidraw frames and assets."""
    width, height = _storyboard_canvas(handoff)
    out = _safe_output_path(Path(out))
    pages = _storyboard_physical_pages(handoff["pages"])
    private_icons = _editable_private_icons(handoff, private_icon_catalog)
    private_paths, private_receipts = _storyboard_private_scene_state(handoff)
    service_context = _storyboard_service_context(handoff)
    elements: list[dict[str, Any]] = []
    files: dict[str, Any] = {}

    def common(element_id: str, kind: str, x: float, y: float, w: float, h: float, seed: int) -> dict[str, Any]:
        return {"id": element_id, "type": kind, "x": x, "y": y, "width": w, "height": h, "angle": 0,
                "strokeColor": "#4F7C92", "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 2,
                "strokeStyle": "solid", "roughness": 1, "opacity": 100, "seed": seed, "version": 1,
                "versionNonce": seed + 1, "isDeleted": False, "boundElements": None, "updated": 1,
                "link": None, "locked": False}

    # Create all dominant-flow arrows first.  This keeps the editable stacking
    # order stable and makes the relationship independent from image placement.
    for page_index, page in enumerate(pages, start=1):
        layout = _storyboard_page_layout(handoff, page)
        offset_y = (page_index - 1) * (height + 80)
        for scene_index, item in enumerate(layout["scenes"], start=1):
            bounds = item["bounds"]
            start_x = int(width * .06) if scene_index == 1 else previous_x
            start_y = int(height * .25) if scene_index == 1 else previous_y
            end_x, end_y = bounds["x"] + bounds["width"] // 2, bounds["y"] + bounds["height"] // 2
            arrow = common(f"storyboard-arrow-{page_index}-{scene_index}", "arrow", start_x, offset_y + start_y, end_x - start_x, end_y - start_y, 10000 + page_index * 100 + scene_index)
            arrow.update({"points": [[0, 0], [end_x - start_x, end_y - start_y]], "lastCommittedPoint": None,
                          "startBinding": None, "endBinding": None, "startArrowhead": None, "endArrowhead": "arrow",
                          "frameId": f"storyboard-frame-{page_index}",
                          "customData": {"summaryKind": "oci.visual-summary.storyboard-connector", "audienceRole": str(page.get("audience_role", page.get("role", ""))), "readingOrder": scene_index}})
            elements.append(arrow)
            previous_x, previous_y = end_x, end_y

    def add_text(element_id: str, text: str, x: float, y: float, w: float, h: float, seed: int, *, size: int, colour: str, metadata: dict[str, Any], frame_id: str) -> None:
        element = common(element_id, "text", x, y, w, h, seed)
        element.update({"text": text, "fontSize": size, "fontFamily": 5, "textAlign": "left", "verticalAlign": "top",
                        "containerId": None, "originalText": text, "lineHeight": 1.2, "strokeColor": colour, "roughness": 0,
                        "customData": metadata, "frameId": frame_id})
        elements.append(element)

    for page_index, page in enumerate(pages, start=1):
        role = str(page["role"])
        audience_role = str(page.get("audience_role", role))
        offset_y = (page_index - 1) * (height + 80)
        layout = _storyboard_page_layout(handoff, page)
        frame = common(f"storyboard-frame-{page_index}", "frame", 0, offset_y, width, height, 20000 + page_index)
        frame.update({"name": role, "strokeColor": "#79AAA6", "backgroundColor": "#FFFDF8", "roughness": 0,
                      "customData": {"summaryKind": "oci.visual-summary.storyboard-page", "audienceRole": audience_role,
                                     "physicalRole": role, "pageNumber": int(page.get("page_number", 1)),
                                     "pageCount": int(page.get("page_count", 1)), "readingOrder": page_index}})
        elements.append(frame)
        frame_id = frame["id"]
        title = str(page.get("title", handoff.get("title", "")))
        add_text(f"storyboard-title-{page_index}", title, int(width * .06), offset_y + int(height * .06), int(width * .88), int(height * .10), 20100 + page_index, size=28, colour="#18202B", metadata={"summaryKind": "oci.visual-summary.native-text", "audienceRole": audience_role, "readingOrder": 1}, frame_id=frame_id)
        takeaway = str(page.get("takeaway", handoff.get("takeaway", "")))
        if takeaway:
            add_text(f"storyboard-takeaway-{page_index}", takeaway, int(width * .06), offset_y + int(height * .18), int(width * .88), int(height * .08), 20200 + page_index, size=15, colour="#3C4655", metadata={"summaryKind": "oci.visual-summary.native-text", "audienceRole": audience_role, "readingOrder": 2}, frame_id=frame_id)
        reading_order = 10
        for scene_index, item in enumerate(layout["scenes"], start=1):
            record, bounds, label = item["record"], item["bounds"], item["label_bounds"]
            unit_id = str(record.get("unit_id", ""))
            metadata = {"summaryKind": "oci.visual-summary.scene-slot", "unitId": unit_id,
                        "evidenceClass": str(record.get("evidence_class", "")),
                        "sourceRefs": list(record.get("source_ids", [])), "readingOrder": reading_order}
            shell = common(f"storyboard-scene-{page_index}-{scene_index}", "rectangle", bounds["x"], offset_y + bounds["y"], bounds["width"], bounds["height"], 21000 + page_index * 100 + scene_index)
            shell.update({"backgroundColor": "#F4FAF8", "strokeColor": "#79AAA6", "roundness": {"type": 3}, "customData": metadata, "frameId": frame_id})
            elements.append(shell)
            scene_uri = _storyboard_scene_uri(record, private_paths, private_receipts)
            if scene_uri:
                file_id = f"scene-{page_index}-{scene_index}-{hashlib.sha256(scene_uri.encode('ascii')).hexdigest()[:12]}"
                files[file_id] = {"mimeType": scene_uri[5:scene_uri.index(";")], "id": file_id, "dataURL": scene_uri, "created": 1, "lastRetrieved": 1,
                                  "sha256": hashlib.sha256(base64.b64decode(scene_uri.rsplit(",", 1)[1])).hexdigest()}
                image = common(f"storyboard-image-{page_index}-{scene_index}", "image", bounds["x"], offset_y + bounds["y"], bounds["width"], bounds["height"], 21100 + page_index * 100 + scene_index)
                image.update({"fileId": file_id, "status": "saved", "scale": [1, 1], "crop": None, "roughness": 0,
                              "customData": {**metadata, "summaryKind": "oci.visual-summary.replaceable-scene", "altText": str(record.get("alt_text", "Supporting scene"))}, "frameId": frame_id})
                elements.append(image)
            add_text(f"storyboard-scene-title-{page_index}-{scene_index}", str(record.get("title", "")), label["x"], offset_y + label["y"], label["width"], max(16, label["height"] // 3), 21200 + page_index * 100 + scene_index, size=13, colour="#18202B", metadata={**metadata, "summaryKind": "oci.visual-summary.native-text"}, frame_id=frame_id)
            text = f'{record.get("detail", "")}\n{record.get("evidence_class", "")}'
            add_text(f"storyboard-copy-{page_index}-{scene_index}", text, label["x"], offset_y + label["y"] + max(16, label["height"] // 3), label["width"], max(1, label["height"] - max(16, label["height"] // 3)), 21250 + page_index * 100 + scene_index, size=12, colour="#3C4655", metadata={**metadata, "summaryKind": "oci.visual-summary.native-text"}, frame_id=frame_id)
            reading_order += 3
        for service_index, item in enumerate(layout["services"], start=1):
            record, bounds, label = item["record"], item["bounds"], item["label_bounds"]
            canonical_id, display_name = str(record.get("canonical_service_id", "")), str(record.get("display_name", ""))
            mapping = str(record.get("mapping_type", "none"))
            unit_id = str(record.get("unit_id", ""))
            lineage = service_context.get(unit_id, {"evidence_class": "", "source_refs": []})
            semantics = _non_drawio_stencil_semantics(record)
            metadata = {"summaryKind": "oci.visual-summary.service-icon", "unitId": unit_id, "canonicalServiceId": canonical_id,
                        "displayName": display_name, "mappingType": mapping, "evidenceClass": str(lineage["evidence_class"]),
                        "sourceRefs": list(lineage["source_refs"]), "readingOrder": reading_order,
                        **({"renderedAs": semantics["rendered_as"], "fallbackReason": semantics["fallback_reason"]} if semantics else {})}
            icon_uri = _storyboard_safe_icon_uri(record, private_icons)
            if icon_uri:
                file_id = f"icon-{page_index}-{service_index}-{hashlib.sha256(icon_uri.encode('ascii')).hexdigest()[:12]}"
                files[file_id] = {"mimeType": "image/svg+xml", "id": file_id, "dataURL": icon_uri, "created": 1, "lastRetrieved": 1,
                                  "sha256": hashlib.sha256(_uri_svg_payload(icon_uri)).hexdigest()}
                icon = common(f"storyboard-icon-{page_index}-{service_index}", "image", bounds["x"], offset_y + bounds["y"], bounds["width"], bounds["height"], 22000 + page_index * 100 + service_index)
                icon.update({"fileId": file_id, "status": "saved", "scale": [1, 1], "crop": None, "roughness": 0,
                             "customData": {**metadata, "altText": str(record.get("alt_text", display_name))}, "frameId": frame_id})
                elements.append(icon)
            add_text(f"storyboard-service-copy-{page_index}-{service_index}", f"{display_name}\n{mapping}", label["x"], offset_y + label["y"], label["width"], label["height"], 22100 + page_index * 100 + service_index, size=12, colour="#18202B", metadata={**metadata, "summaryKind": "oci.visual-summary.native-text"}, frame_id=frame_id)
            reading_order += 2
        add_text(f"storyboard-evidence-{page_index}", f'Evidence: {handoff.get("evidence_footer", "")}', int(width * .06), offset_y + int(height * .92), int(width * .88), max(1, int(height * .06)), 23000 + page_index, size=10, colour="#3C4655", metadata={"summaryKind": "oci.visual-summary.evidence", "audienceRole": audience_role, "readingOrder": 999}, frame_id=frame_id)
    long_description = (
        f"{handoff.get('title', 'OCI visual summary')}. "
        "A left-to-right incident workflow: Detect, Correlate, Diagnose, Route. "
        "Each framed section retains editable scene, service, evidence, and source objects. "
        f"Evidence footer: {handoff.get('evidence_footer', '')}"
    )
    scene = {"type": "excalidraw", "version": 2, "source": "oci-visual-summary", "elements": elements,
             "appState": {"viewBackgroundColor": "#FFFDF8", "gridSize": None, "scrollX": 0, "scrollY": 0,
                          "width": width, "height": height,
                          "customData": {"longDescription": long_description,
                                         "accessibility": {"readingOrder": "Detect, Correlate, Diagnose, Route"}}},
             "metadata": {"longDescription": long_description,
                          "accessibility": {"summary": "Editable OCI visual-summary composition", "readingOrder": "Detect, Correlate, Diagnose, Route"}},
             "files": files}
    out.write_text(json.dumps(scene, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def render_excalidraw(handoff: dict[str, Any], out: Path, *, private_icon_catalog: dict[str, Any] | None = None) -> Path:
    """Render an editable Excalidraw story map with local embedded image files."""
    if _is_storyboard_sequence(handoff):
        return _render_storyboard_excalidraw(handoff, out, private_icon_catalog)
    if _is_canvas_story_map(handoff):
        return _render_canvas_excalidraw(handoff, out)
    width, height = _require_handoff(handoff)
    out = _safe_output_path(Path(out))
    accent = str(handoff["profile"]["primary_accent"])
    secondary = str(handoff["profile"]["secondary_accent"])
    elements: list[dict[str, Any]] = []
    files: dict[str, Any] = {}

    def common(element_id: str, kind: str, x: float, y: float, w: float, h: float, seed: int) -> dict[str, Any]:
        return {"id": element_id, "type": kind, "x": x, "y": y, "width": w, "height": h, "angle": 0,
                "strokeColor": accent, "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 2,
                "strokeStyle": "solid", "roughness": 2, "opacity": 100, "seed": seed, "version": 1,
                "versionNonce": seed + 1, "isDeleted": False, "boundElements": None, "updated": 1,
                "link": None, "locked": False}

    headline = handoff["headline_zone"]
    title = common("title", "text", headline["bounds"]["x"], headline["bounds"]["y"], headline["bounds"]["width"], 80, 1001)
    title.update({"text": headline["title"], "fontSize": 42, "fontFamily": 5, "textAlign": "left", "verticalAlign": "top", "containerId": None, "originalText": headline["title"], "lineHeight": 1.15, "strokeColor": "#18202B", "roughness": 0})
    elements.append(title)
    takeaway = common("takeaway", "text", headline["bounds"]["x"], headline["bounds"]["y"] + 92, headline["bounds"]["width"], 52, 1003)
    takeaway.update({"text": headline["takeaway"], "fontSize": 20, "fontFamily": 5, "textAlign": "left", "verticalAlign": "top", "containerId": None, "originalText": headline["takeaway"], "lineHeight": 1.25, "strokeColor": "#3C4655", "roughness": 0})
    elements.append(takeaway)
    points = handoff.get("dominant_path", {}).get("points", [])
    for index, (start, end) in enumerate(zip(points, points[1:]), start=1):
        arrow = common(f"journey-{index}", "arrow", start["x"], start["y"], end["x"] - start["x"], end["y"] - start["y"], 1100 + index)
        arrow.update({"points": [[0, 0], [end["x"] - start["x"], end["y"] - start["y"]]], "lastCommittedPoint": None,
                      "startBinding": None, "endBinding": None, "startArrowhead": None,
                      "endArrowhead": "arrow" if index == len(points) - 1 else None, "strokeWidth": 5})
        elements.append(arrow)
    for index, cluster in enumerate(handoff["clusters"], start=1):
        bounds, anchor = cluster["bounds"], str(cluster["anchor_id"])
        shell = common(f"scene-{anchor}", "ellipse", bounds["x"], bounds["y"], bounds["width"], bounds["height"], 2000 + index * 10)
        shell.update({"backgroundColor": "#FFFDF8", "strokeColor": secondary})
        elements.append(shell)
        title_text = str(cluster["title"])
        title_element = common(f"title-{anchor}", "text", bounds["x"] + 20, bounds["y"] + 24, bounds["width"] * .58, 34, 2001 + index * 10)
        title_element.update({"text": title_text, "fontSize": 20, "fontFamily": 5, "textAlign": "left", "verticalAlign": "top",
                              "containerId": None, "originalText": title_text, "lineHeight": 1.2, "strokeColor": "#18202B", "roughness": 0})
        elements.append(title_element)
        detail_text = f'{cluster["detail"]}\n{str(cluster["evidence_class"]).upper()}'
        detail_element = common(f"detail-{anchor}", "text", bounds["x"] + 20, bounds["y"] + 66, bounds["width"] * .58, bounds["height"] - 82, 2003 + index * 10)
        detail_element.update({"text": detail_text, "fontSize": 15, "fontFamily": 5, "textAlign": "left", "verticalAlign": "top",
                               "containerId": None, "originalText": detail_text, "lineHeight": 1.25, "strokeColor": "#3C4655", "roughness": 0})
        elements.append(detail_element)
        art_uri = _art_data_uri(cluster)
        if art_uri:
            file_id = f"art-{anchor}"
            files[file_id] = {"mimeType": art_uri[5:art_uri.index(";")], "id": file_id, "dataURL": art_uri,
                              "created": 1, "lastRetrieved": 1, "sha256": cluster.get("art", {}).get("sha256", "")}
            slot = cluster["art_slot"]
            image = common(f"image-{anchor}", "image", slot["x"], slot["y"], slot["width"], slot["height"], 2002 + index * 10)
            image.update({"fileId": file_id, "status": "saved", "scale": [1, 1], "crop": None, "roughness": 0,
                          "customData": {"altText": cluster.get("art", {}).get("alt_text", "Supporting illustration")}})
            elements.append(image)
    scene = {"type": "excalidraw", "version": 2, "source": "oci-visual-summary", "elements": elements,
             "appState": {"viewBackgroundColor": "#FFFDF8", "gridSize": None, "scrollX": 0, "scrollY": 0,
                          "width": width, "height": height,
                          "visualStyle": {
                              "preset": handoff.get("visual_style", {}).get("preset", "oci-doodle"),
                              "doodleLevel": handoff.get("visual_style", {}).get("doodle_level", "balanced"),
                          }}, "files": files}
    out.write_text(json.dumps(scene, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def _render_canvas_excalidraw(handoff: dict[str, Any], out: Path) -> Path:
    """Canvas-specific Excalidraw export with separable scenes and labels."""
    width, height = _require_handoff(handoff)
    out = _safe_output_path(Path(out))
    accent = str(handoff["profile"]["primary_accent"])
    elements: list[dict[str, Any]] = []
    files: dict[str, Any] = {}

    def common(element_id: str, kind: str, x: float, y: float, w: float, h: float, seed: int) -> dict[str, Any]:
        return {"id": element_id, "type": kind, "x": x, "y": y, "width": w, "height": h, "angle": 0,
                "strokeColor": accent, "backgroundColor": "transparent", "fillStyle": "solid", "strokeWidth": 2,
                "strokeStyle": "solid", "roughness": 2, "opacity": 100, "seed": seed, "version": 1,
                "versionNonce": seed + 1, "isDeleted": False, "boundElements": None, "updated": 1,
                "link": None, "locked": False}

    headline = handoff["headline_zone"]
    for element_id, text, y, size, colour, seed in (
        ("title", headline["title"], headline["bounds"]["y"], 42, "#18202B", 1001),
        ("takeaway", headline["takeaway"], headline["bounds"]["y"] + 92, 20, "#3C4655", 1003),
    ):
        element = common(element_id, "text", headline["bounds"]["x"], y, headline["bounds"]["width"], 80, seed)
        element.update({"text": text, "fontSize": size, "fontFamily": 5, "textAlign": "left", "verticalAlign": "top", "containerId": None, "originalText": text, "lineHeight": 1.2, "strokeColor": colour, "roughness": 0})
        elements.append(element)
    points = handoff.get("canvas_layout", {}).get("thread", {}).get("points", [])
    for index, (start, end) in enumerate(zip(points, points[1:]), start=1):
        arrow = common(f"canvas-thread-{index}", "arrow", start["x"], start["y"], end["x"] - start["x"], end["y"] - start["y"], 1100 + index)
        arrow.update({"points": [[0, 0], [end["x"] - start["x"], end["y"] - start["y"]]], "lastCommittedPoint": None, "startBinding": None, "endBinding": None, "startArrowhead": None, "endArrowhead": "arrow" if index == len(points) - 1 else None, "strokeWidth": 5, "customData": {"summaryKind": "oci.visual-summary.canvas-thread"}})
        elements.append(arrow)
    for index, cluster in enumerate(handoff["clusters"], start=1):
        anchor = str(cluster["anchor_id"])
        role = str(cluster.get("canvas_role", "scene"))
        art_bounds = cluster.get("art_bounds", cluster.get("art_slot", {}))
        text_bounds = cluster.get("text_bounds", cluster["bounds"])
        art_uri = _art_data_uri(cluster)
        if art_uri:
            file_id = f"art-{anchor}"
            files[file_id] = {"mimeType": art_uri[5:art_uri.index(";")], "id": file_id, "dataURL": art_uri, "created": 1, "lastRetrieved": 1, "sha256": cluster.get("art", {}).get("sha256", "")}
            image = common(f"image-{anchor}", "image", art_bounds["x"], art_bounds["y"], art_bounds["width"], art_bounds["height"], 2002 + index * 10)
            image.update({"fileId": file_id, "status": "saved", "scale": [1, 1], "crop": None, "roughness": 0, "customData": {"summaryKind": "oci.visual-summary.canvas-scene", "anchorId": anchor, "canvasRole": role, "altText": cluster.get("art", {}).get("alt_text", "Supporting scene illustration")}})
            elements.append(image)
        title_text = str(cluster["title"])
        title_element = common(f"title-{anchor}", "text", text_bounds["x"], text_bounds["y"], text_bounds["width"], 34, 2001 + index * 10)
        title_element.update({"text": title_text, "fontSize": 20, "fontFamily": 5, "textAlign": "left", "verticalAlign": "top", "containerId": None, "originalText": title_text, "lineHeight": 1.2, "strokeColor": "#18202B", "roughness": 0, "customData": {"summaryKind": "oci.visual-summary.canvas-annotation", "anchorId": anchor, "canvasRole": role}})
        elements.append(title_element)
        detail_text = f'{cluster["detail"]}\n{str(cluster["evidence_class"]).upper()}'
        detail = common(f"detail-{anchor}", "text", text_bounds["x"], text_bounds["y"] + 42, text_bounds["width"], max(20, text_bounds["height"] - 42), 2003 + index * 10)
        detail.update({"text": detail_text, "fontSize": 15, "fontFamily": 5, "textAlign": "left", "verticalAlign": "top", "containerId": None, "originalText": detail_text, "lineHeight": 1.25, "strokeColor": "#3C4655", "roughness": 0, "customData": {"summaryKind": "oci.visual-summary.canvas-annotation", "anchorId": anchor, "canvasRole": role}})
        elements.append(detail)
    scene = {"type": "excalidraw", "version": 2, "source": "oci-visual-summary", "elements": elements,
             "appState": {"viewBackgroundColor": "#FFF8EC", "gridSize": None, "scrollX": 0, "scrollY": 0, "width": width, "height": height,
                          "visualStyle": {"preset": handoff.get("visual_style", {}).get("preset", "oci-doodle"), "doodleLevel": handoff.get("visual_style", {}).get("doodle_level", "rich"), "variant": "canvas-story-map"}}, "files": files}
    out.write_text(json.dumps(scene, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out


def build_outputs(
    handoff: dict[str, Any], out_dir: Path, formats: set[str], *,
    private_icon_catalog: dict[str, Any] | None = None,
) -> list[Path]:
    """Public dispatcher for standalone visual-summary output formats."""
    if handoff.get("concept") != "illo-storyboard-sequence-v1":
        _require_handoff(handoff)
    requested = set(formats)
    supported = {"svg", "png", "pdf", "drawio", "excalidraw", "pptx", "docx", "handoff", "art-request"}
    unknown = requested - supported
    if unknown:
        raise SummaryError("unsupported output formats: " + ", ".join(sorted(unknown)))
    if not requested:
        raise SummaryError("at least one output format is required")
    # Fail before writing a partial set: supplied art cannot silently lose parity.
    if "png" in requested:
        _require_art_backend(handoff, "PIL")
    if "pdf" in requested:
        _require_art_backend(handoff, "reportlab")
    if "docx" in requested:
        _require_art_backend(handoff, "PIL")
    out_dir = Path(out_dir).absolute()
    for component in (out_dir, *out_dir.parents):
        if component.exists() and component.is_symlink():
            raise SummaryError(f"refusing symlinked output directory: {component}")
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs: list[Path] = []
    renderers = {
        "svg": render_svg,
        "png": render_png,
        "pdf": render_pdf,
        "drawio": render_drawio,
        "excalidraw": render_excalidraw,
    }
    for kind in ("svg", "png", "pdf", "drawio", "excalidraw"):
        if kind in requested:
            target = out_dir / f"summary.{kind}"
            if _is_storyboard_sequence(handoff):
                storyboard_renderers = {
                    "svg": render_storyboard_svg,
                    "png": render_storyboard_png,
                    "pdf": render_storyboard_pdf,
                    "drawio": render_drawio,
                    "excalidraw": render_excalidraw,
                }
                outputs.append(storyboard_renderers[kind](handoff, target, private_icon_catalog=private_icon_catalog))
            else:
                outputs.append(renderers[kind](handoff, target))
    portable_handoff = _portable_handoff(handoff)
    office_handoff = _office_handoff(handoff, private_icon_catalog)
    if "pptx" in requested or "docx" in requested:
        with tempfile.TemporaryDirectory(prefix=".visual-summary-office-", dir=out_dir) as temp_dir:
            temp_root = Path(temp_dir)
            handoff_path = temp_root / "summary.handoff.json"
            handoff_path.write_text(json.dumps(office_handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            if "pptx" in requested:
                node = os.environ.get("RUNTIME_NODE")
                presentations_skill = os.environ.get("PRESENTATIONS_SKILL_DIR")
                if not node or not presentations_skill:
                    raise SummaryError("pptx output requires RUNTIME_NODE and PRESENTATIONS_SKILL_DIR from the workspace runtime")
                target = _safe_output_path(out_dir / "summary.pptx")
                subprocess.run(
                    [node, str(Path(__file__).with_name("build_summary_pptx.mjs")), "--handoff", str(handoff_path), "--out", str(target)],
                    check=True,
                )
                outputs.append(target)
            if "docx" in requested:
                python = os.environ.get("RUNTIME_PYTHON")
                documents_skill = os.environ.get("DOCUMENTS_SKILL_DIR")
                if not python or not documents_skill:
                    raise SummaryError("docx output requires RUNTIME_PYTHON and DOCUMENTS_SKILL_DIR from the workspace runtime")
                target = _safe_output_path(out_dir / "summary.docx")
                command = [
                    python,
                    str(Path(__file__).with_name("build_summary_docx.py")),
                    "--handoff",
                    str(handoff_path),
                ]
                preview_manifest = _storyboard_docx_preview_manifest(handoff, temp_root, private_icon_catalog=private_icon_catalog)
                if preview_manifest:
                    preview_manifest_path = temp_root / "storyboard-previews.json"
                    preview_manifest_path.write_text(json.dumps(preview_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                    command.extend(["--preview-manifest", str(preview_manifest_path)])
                else:
                    preview_path = temp_root / "summary.preview.png"
                    render_png(handoff, preview_path)
                    command.extend(["--preview", str(preview_path)])
                command.extend(["--out", str(target)])
                subprocess.run(command, check=True)
                outputs.append(target)
    if "handoff" in requested:
        handoff_path = _safe_output_path(out_dir / "summary.handoff.json")
        handoff_path.write_text(json.dumps(portable_handoff, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        outputs.append(handoff_path)
    if "art-request" in requested:
        private_dir = out_dir / ".visual-summary-private"
        request_path = _write_private_json(private_dir, "artwork-request.json", artwork_request(handoff))
        outputs.append(request_path)
    return outputs


def build_project_summary(
    *,
    project_root: Path,
    out_dir: Path,
    formats: set[str],
    audience: str,
    purpose: str,
    domain: str,
    title: str | None,
    devviz_scope_path: Path | None,
    devviz_graph_first_path: Path | None,
    devviz_base_url: str | None = None,
    synthesis_response_path: Path | None = None,
    readme_path: Path | None = None,
    image_path: Path | None = None,
    publish_public: bool = False,
) -> list[Path]:
    from project_intake import (
        ProjectIntakeError,
        build_synthesis_request,
        collect_local_evidence,
        coerce_synthesis_response,
        deterministic_project_spec,
        reconstruct_synthesis_spec,
        fetch_loopback_scope,
        _project_text,
        load_optional_json,
        reconcile_devviz,
        validate_synthesis_response,
        markdown_block,
        upsert_markdown_block,
    )

    project_root = Path(project_root).absolute()
    if not project_root.is_dir() or any(component.is_symlink() for component in (project_root, *project_root.parents) if component.exists()):
        raise SummaryError("project root must be a real non-symlink directory")
    out_dir = Path(out_dir).absolute()
    for component in (out_dir, *out_dir.parents):
        if component.exists() and component.is_symlink():
            raise SummaryError(f"refusing symlinked project output directory: {component}")
    publication_requested = readme_path is not None or image_path is not None
    if publication_requested and publish_public is not True:
        raise SummaryError("README/image publication requires explicit --publish-public approval")
    if publication_requested:
        normalized_targets: list[tuple[str, Path]] = []
        if readme_path is not None:
            normalized_targets.append(("README", Path(readme_path).absolute()))
        if image_path is not None:
            normalized_targets.append(("image", Path(image_path).absolute()))
        for label, target in normalized_targets:
            try:
                target.relative_to(project_root)
            except ValueError as exc:
                raise SummaryError(f"public {label} target must remain below the declared project root") from exc
            _safe_output_path(target)
        readme_path = Path(readme_path).absolute() if readme_path is not None else None
        image_path = Path(image_path).absolute() if image_path is not None else None
    local_evidence = collect_local_evidence(
        project_root,
        publication_approved=publish_public,
    )
    devviz_scope = load_optional_json(devviz_scope_path)
    devviz_graph_first = load_optional_json(devviz_graph_first_path)
    devviz_lookup = None
    if devviz_scope is None and devviz_base_url:
        devviz_lookup = fetch_loopback_scope(devviz_base_url, Path(project_root).name)
        if isinstance(devviz_lookup, dict) and isinstance(devviz_lookup.get("scope_detail"), dict):
            devviz_scope = devviz_lookup["scope_detail"]
    devviz_summary = reconcile_devviz(
        local_evidence,
        scope_detail=devviz_scope,
        graph_first=devviz_graph_first,
        references=devviz_lookup.get("references") if isinstance(devviz_lookup, dict) else None,
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    from project_intake import _sanitize_devviz
    evidence_payload = {
        "local": local_evidence,
        "devviz": devviz_summary,
        "devviz_scope": _sanitize_devviz(devviz_scope),
        "devviz_graph_first": _sanitize_devviz(devviz_graph_first),
        "devviz_lookup": _sanitize_devviz(devviz_lookup),
    }

    synthesis_request = build_synthesis_request(
        local_evidence,
        audience=audience,
        purpose=purpose,
        domain=domain,
        title=title,
        devviz_summary=devviz_summary,
        schema=_bundled_schema(),
    )
    if synthesis_response_path is not None:
        payload = load_optional_json(synthesis_response_path)
        if payload is None:
            raise SummaryError("synthesis response path did not contain a JSON object")
        spec = reconstruct_synthesis_spec(
            payload,
            local_evidence,
            audience=audience,
            purpose=purpose,
            domain=domain,
            title=title,
            requested_formats=sorted(formats),
            devviz_summary=devviz_summary,
            publication_approved=publish_public,
        )
    else:
        spec = deterministic_project_spec(
            local_evidence,
            audience=audience,
            purpose=purpose,
            domain=domain,
            title=title,
            requested_formats=sorted(formats),
            devviz_summary=devviz_summary,
            publication_approved=publish_public,
        )

    try:
        expected_title, expected_takeaway = _project_text(local_evidence, title, devviz_summary)
        validated = validate_synthesis_response(
            spec,
            local_evidence,
            expected_title=expected_title,
            expected_takeaway=expected_takeaway,
            allow_internal=readme_path is None and image_path is None,
        )
    except ProjectIntakeError as exc:
        raise SummaryError(str(exc)) from exc
    if publication_requested and validated.get("privacy", {}).get("public_eligible") is not True:
        raise SummaryError("public project output requires explicit publication approval and public-eligible evidence")
    if image_path is not None and Path(image_path).suffix.lower() != ".svg":
        raise SummaryError("public repository capability images must use SVG; PNG is a lower-fidelity local fallback")
    # Construct the public material in a sibling staging area first.  Evidence
    # and synthesis diagnostics above are intentionally private/ignored, while
    # the spec, renders, image, and README change commit together only on
    # success.
    stage_dir = Path(tempfile.mkdtemp(prefix=".visual-summary-stage-", dir=out_dir.parent))
    try:
        spec_path = stage_dir / "summary.spec.json"
        spec_path.write_text(json.dumps(validated, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        handoff = build_handoff(validated, 1920, 1080)
        staged_outputs = build_outputs(handoff, stage_dir, formats)
        staged_outputs.append(spec_path)
        staged_image: Path | None = None
        replacement_readme: str | None = None
        if image_path is not None:
            requested_image = Path(image_path)
            artifact_name = f"summary{requested_image.suffix.lower() or '.png'}"
            staged_public = stage_dir / artifact_name
            if not staged_public.is_file():
                suffix = requested_image.suffix.lower() or ".png"
                format_name = suffix.lstrip(".")
                raise SummaryError(f"project capability image requires {format_name} in --formats")
            staged_image = stage_dir / f"project-capabilities{requested_image.suffix.lower() or '.png'}"
            shutil.copyfile(staged_public, staged_image)
            if readme_path is not None:
                image_target = requested_image
                relative_image = os.path.relpath(image_target, start=readme_path.parent).replace("\\", "/")
                existing = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
                replacement_readme = upsert_markdown_block(
                    existing, markdown_block(relative_image, alt_text=str(validated["accessibility"]["alt_text"]))
                )

        # Every failure-prone rendering operation is complete.  Commit public
        # targets with compensating rollback so an image/README pair cannot be
        # left half-published if a later replacement fails.
        replacements: list[tuple[Path, Path]] = [(staged, _safe_output_path(out_dir / staged.name)) for staged in staged_outputs]
        if staged_image is not None:
            replacements.append((staged_image, _safe_output_path(Path(image_path))))
        if replacement_readme is not None and readme_path is not None:
            readme_stage = stage_dir / "README.md"
            readme_stage.write_text(replacement_readme, encoding="utf-8")
            replacements.append((readme_stage, _safe_output_path(readme_path)))
        backup_dir = stage_dir / "backups"
        backup_dir.mkdir()
        backups: list[tuple[Path, Path | None]] = []
        for index, (_staged, target) in enumerate(replacements):
            backup = backup_dir / str(index)
            if target.exists():
                shutil.copy2(target, backup)
                backups.append((target, backup))
            else:
                backups.append((target, None))
        try:
            for staged, target in replacements:
                os.replace(staged, target)
        except OSError:
            for target, backup in backups:
                if backup is None:
                    target.unlink(missing_ok=True)
                else:
                    # copyfile avoids reusing a possibly fault-injected
                    # os.replace during recovery.
                    shutil.copy2(backup, target)
            raise
        outputs = [target for _staged, target in replacements]
    finally:
        shutil.rmtree(stage_dir, ignore_errors=True)
    private_dir = out_dir / ".visual-summary-private"
    evidence_path = _write_private_json(private_dir, "project-evidence.json", evidence_payload)
    synthesis_request_path = _write_private_json(private_dir, "synthesis-request.json", synthesis_request)
    outputs.extend([evidence_path, synthesis_request_path])
    return outputs


def _project_storyboard_context(
    *, project_root: Path, audience: str, purpose: str, domain: str, title: str | None,
    formats: set[str], devviz_scope_path: Path | None, devviz_base_url: str | None,
    publish_public: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Collect bounded project facts and deterministic requests without rendering.

    This is deliberately shared by both phases of ``project-storyboard``.  It
    never invokes a model, inspects a template, or asks DevVisualization to
    scan/refresh a project.
    """
    from project_intake import (
        build_synthesis_request, collect_local_evidence, fetch_loopback_scope,
        load_optional_json, reconcile_devviz,
    )
    project_root = Path(project_root).absolute()
    if not project_root.is_dir() or any(item.is_symlink() for item in (project_root, *project_root.parents) if item.exists()):
        raise SummaryError("project root must be a real non-symlink directory")
    evidence = collect_local_evidence(project_root, publication_approved=publish_public)
    scope = load_optional_json(devviz_scope_path)
    lookup = None
    if scope is None and devviz_base_url:
        lookup = fetch_loopback_scope(devviz_base_url, project_root.name)
        if isinstance(lookup, dict) and isinstance(lookup.get("scope_detail"), dict):
            scope = lookup["scope_detail"]
    devviz = reconcile_devviz(
        evidence, scope_detail=scope,
        references=lookup.get("references") if isinstance(lookup, dict) else None,
    )
    request = build_synthesis_request(
        evidence, audience=audience, purpose=purpose, domain=domain, title=title,
        devviz_summary=devviz, schema=_bundled_schema(),
    )
    return evidence, devviz, request, {"scope": scope, "lookup": lookup}


def _project_storyboard_replace(replacements: list[tuple[Path, Path]], stage_dir: Path) -> list[Path]:
    """Commit already-rendered targets as one recoverable local publication."""
    backup_dir = stage_dir / "backups"; backup_dir.mkdir()
    backups: list[tuple[Path, Path | None]] = []
    for index, (_staged, target) in enumerate(replacements):
        target = _safe_output_path(target)
        if target.parent.name == ".visual-summary-private":
            _require_private_output_ignored(target.parent)
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            os.chmod(target.parent, 0o700)
        else:
            target.parent.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / str(index)
        if target.exists():
            shutil.copy2(target, backup); backups.append((target, backup))
        else:
            backups.append((target, None))
    try:
        for staged, target in replacements:
            os.replace(staged, _safe_output_path(target))
    except OSError:
        for target, backup in backups:
            if backup is None:
                target.unlink(missing_ok=True)
            else:
                shutil.copy2(backup, target)
        raise
    return [target for _staged, target in replacements]


def _stage_project_storyboard_private_audit(
    stage_dir: Path, *, evidence: dict[str, Any], devviz: dict[str, Any],
    devviz_inputs: dict[str, Any], synthesis_request: dict[str, Any], accepted: dict[str, Any],
) -> list[Path]:
    """Stage the complete-mode private audit triplet for the final transaction.

    These are deliberately staged with the render files rather than written
    after them: a failed final private receipt cannot leave a public bundle or
    durable icon cache representing an un-audited build.
    """
    private_stage = stage_dir / ".visual-summary-private"
    private_stage.mkdir(mode=0o700, exist_ok=False)
    os.chmod(private_stage, 0o700)
    payloads = {
        "project-evidence.json": {"local": evidence, "devviz": devviz, "inputs": devviz_inputs},
        "synthesis-request.json": synthesis_request,
        "storyboard.json": accepted,
    }
    for name, payload in payloads.items():
        _fsync_private_json(private_stage / name, payload)
    # Verify all bytes after fsync and before adding them to the replacement
    # transaction.  Each audit file is a JSON object by contract.
    for name in payloads:
        if not isinstance(json.loads((private_stage / name).read_text(encoding="utf-8")), dict):
            raise SummaryError("private storyboard audit payload must be a JSON object")
    return [private_stage / name for name in sorted(payloads)]


def _resolve_project_storyboard_icons(
    accepted: dict[str, Any], *, icon_pack_path: Path | None, overrides: dict[str, Any] | None,
    publish_public: bool, private_attempt_root: Path,
) -> tuple[list[dict[str, Any]], Path | None, dict[str, Any]]:
    """Resolve AXM icons in an attempt-local cache, never the durable output."""
    import axm_icons
    if icon_pack_path is None:
        if publish_public:
            try:
                catalog = axm_icons.official_public_stencil_catalog()
            except axm_icons.IconPackError as exc:
                raise SummaryError(f"official public stencil registry rejected: {exc}") from exc
        else:
            catalog = {"classification": "internal", "icons": []}
        staged_cache = None
    else:
        if publish_public:
            raise SummaryError("public output cannot use an internal-only icon catalog")
        try:
            catalog = axm_icons.catalog_icon_pack(Path(icon_pack_path), private_attempt_root)
        except axm_icons.IconPackError as exc:
            raise SummaryError(f"icon pack rejected: {exc}") from exc
        digest = catalog.get("source_digest")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise SummaryError("staged icon catalog has no valid source digest")
        staged_cache = Path(private_attempt_root) / ".visual-summary-private" / "icon-cache" / digest
        if not staged_cache.is_dir() or staged_cache.is_symlink():
            raise SummaryError("staged icon cache is unavailable")
    try:
        icons = axm_icons.resolve_service_icons(
            accepted, catalog, overrides, output_classification="public" if publish_public else "internal",
        )
    except axm_icons.IconPackError as exc:
        # The root belongs to this invocation, so this exact cleanup cannot
        # affect a durable cache or an unrelated caller directory.
        shutil.rmtree(Path(private_attempt_root) / ".visual-summary-private", ignore_errors=True)
        raise SummaryError(f"icon resolution failed: {exc}") from exc
    receipt: dict[str, Any] = {"classification": "internal"}
    if staged_cache is not None:
        by_asset = {str(item.get("asset_id")): item for item in catalog.get("icons", []) if isinstance(item, dict)}
        for record in icons:
            asset_id = record.get("private_catalog_asset_id")
            if not isinstance(asset_id, str):
                continue
            item = by_asset.get(asset_id)
            if not isinstance(item, dict) or not isinstance(item.get("media_digest"), str):
                raise SummaryError("resolved icon receipt is incomplete")
            payload_path = staged_cache / f"{item['media_digest']}.svg"
            if payload_path.is_symlink() or not payload_path.is_file():
                raise SummaryError("resolved icon receipt is unavailable")
            payload = payload_path.read_bytes()
            if hashlib.sha256(payload).hexdigest() != item["media_digest"]:
                raise SummaryError("resolved icon changed after cataloging")
            # The renderer repeats passive-SVG checks before embedding.
            receipt[asset_id] = {"bytes": payload, "sha256": item["media_digest"]}
    return icons, staged_cache, receipt


def _promote_attempt_icon_cache(staged_cache: Path | None, private_dir: Path) -> Path | None:
    """Promote only a successful attempt's exact digest directory, if absent."""
    if staged_cache is None:
        return None
    digest = staged_cache.name
    if not re.fullmatch(r"[0-9a-f]{64}", digest) or not staged_cache.is_dir() or staged_cache.is_symlink():
        raise SummaryError("staged icon cache is invalid")
    destination_parent = Path(private_dir) / "icon-cache"
    for item in (destination_parent, *destination_parent.parents):
        if item.exists() and item.is_symlink():
            raise SummaryError(f"refusing symlinked private icon cache path: {item}")
    destination_parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    destination = destination_parent / digest
    if destination.exists():
        if destination.is_symlink() or not destination.is_dir():
            raise SummaryError("durable private icon cache target is unsafe")
        return None
    os.replace(staged_cache, destination)
    return destination


def build_project_storyboard(
    *, project_root: Path, out_dir: Path, formats: set[str], audience: str, purpose: str,
    domain: str, title: str | None, devviz_scope_path: Path | None, devviz_base_url: str | None,
    synthesis_response_path: Path | None, storyboard_response_path: Path | None,
    scene_manifest_path: Path | None, icon_pack_path: Path | None, icon_overrides_path: Path | None,
    icon_policy: str | None, publish_public: bool,
) -> list[Path]:
    """Run the explicit, offline two-phase project-to-storyboard workflow.

    Missing reviewed inputs is a successful request-only phase.  Complete mode
    accepts only validated local responses and atomically writes render outputs.
    """
    from project_intake import (
        ProjectIntakeError, _project_text, load_optional_json,
        reconstruct_synthesis_spec, validate_synthesis_response,
    )
    out_dir = Path(out_dir).absolute()
    for item in (out_dir, *out_dir.parents):
        if item.exists() and item.is_symlink():
            raise SummaryError(f"refusing symlinked project output directory: {item}")
    evidence, devviz, synthesis_request, devviz_inputs = _project_storyboard_context(
        project_root=project_root, audience=audience, purpose=purpose, domain=domain, title=title,
        formats=formats, devviz_scope_path=devviz_scope_path, devviz_base_url=devviz_base_url,
        publish_public=publish_public,
    )
    private_dir = out_dir / ".visual-summary-private"
    complete_paths = (synthesis_response_path, storyboard_response_path, scene_manifest_path)
    if publish_public and icon_policy == "internal-only":
        raise SummaryError("public output cannot use an internal-only icon policy")
    if any(path is not None for path in complete_paths) and not all(path is not None for path in complete_paths):
        raise SummaryError("complete project-storyboard mode requires synthesis, storyboard, and scene-manifest inputs together")
    if not all(path is not None for path in complete_paths):
        deterministic = reconstruct_synthesis_spec(
            {}, evidence, audience=audience, purpose=purpose, domain=domain, title=title,
            requested_formats=sorted(formats), devviz_summary=devviz, publication_approved=publish_public,
        )
        return _publish_project_storyboard_requests(out_dir, {
            "project-evidence.json": {"local": evidence, "devviz": devviz, "inputs": devviz_inputs},
            "synthesis-request.json": synthesis_request,
            "storyboard-request.json": storyboard.build_storyboard_request(deterministic),
        })

    # Fail before rendering or attempt-cache promotion when the durable audit
    # target is not explicitly private in a repository.  This gate is also
    # rechecked immediately before replacement for defense in depth.
    _require_private_output_ignored(private_dir)

    try:
        synthesis_payload = load_optional_json(synthesis_response_path)
        if synthesis_payload is None:
            raise SummaryError("synthesis response path did not contain a JSON object")
        spec = reconstruct_synthesis_spec(
            synthesis_payload, evidence, audience=audience, purpose=purpose, domain=domain, title=title,
            requested_formats=sorted(formats), devviz_summary=devviz, publication_approved=publish_public,
        )
        expected_title, expected_takeaway = _project_text(evidence, title, devviz)
        spec = validate_synthesis_response(
            spec, evidence, expected_title=expected_title, expected_takeaway=expected_takeaway,
            allow_internal=not publish_public,
        )
    except ProjectIntakeError as exc:
        raise SummaryError(str(exc)) from exc
    accepted = storyboard.validate_storyboard_response(load_storyboard_response(Path(storyboard_response_path)), spec)
    try:
        scenes = storyboard.load_scene_manifest(Path(scene_manifest_path), accepted)
    except storyboard.StoryboardError as exc:
        raise SummaryError(f"approved scene manifest is required: {exc}") from exc
    overrides = load_optional_json(icon_overrides_path) if icon_overrides_path is not None else None
    attempt_dir = Path(tempfile.mkdtemp(prefix=".visual-summary-icon-attempt-", dir=out_dir.parent))
    os.chmod(attempt_dir, 0o700)
    promoted_cache: Path | None = None
    private_drawio_target: Path | None = None
    try:
        icons, staged_icon_cache, private_icon_receipt = _resolve_project_storyboard_icons(
            accepted, icon_pack_path=icon_pack_path, overrides=overrides,
            publish_public=publish_public, private_attempt_root=attempt_dir,
        )
        handoff = build_storyboard_handoff(spec, accepted, scenes, icons, width=1920, height=1080)
        # There are no private bytes in the default catalog.  AXM catalog paths
        # and contents remain in an attempt cache until all rendering succeeds.
        requested = set(formats)
        supported = {"svg", "png", "pdf", "drawio", "excalidraw", "pptx", "docx", "handoff"}
        if not requested or requested - supported:
            raise SummaryError("unsupported project-storyboard output format")
        out_dir.mkdir(parents=True, exist_ok=True)
        stage_dir = Path(tempfile.mkdtemp(prefix=".visual-summary-storyboard-stage-", dir=out_dir.parent))
        try:
            private_staged = _stage_project_storyboard_private_audit(
                stage_dir, evidence=evidence, devviz=devviz, devviz_inputs=devviz_inputs,
                synthesis_request=synthesis_request, accepted=accepted,
            )
            staged = build_outputs(handoff, stage_dir, requested, private_icon_catalog=private_icon_receipt)
            # The primary OCI-project Draw.io deliverable must be portable and
            # stencil-backed.  If an internal AXM catalog supplied the richer
            # local icon bytes, retain that editable derivative under an
            # explicit private-icon filename rather than making the principal
            # diagram depend on restricted media.
            if "drawio" in requested and not publish_public and icon_pack_path is not None:
                import axm_icons
                private_drawio = stage_dir / ".visual-summary-private" / "summary-private-icons.drawio"
                primary_drawio = stage_dir / "summary.drawio"
                os.replace(primary_drawio, private_drawio)
                os.chmod(private_drawio, 0o600)
                try:
                    public_icons = axm_icons.resolve_service_icons(
                        accepted, axm_icons.official_public_stencil_catalog(), overrides,
                        output_classification="public",
                    )
                except axm_icons.IconPackError as exc:
                    raise SummaryError(f"official public stencil registry rejected: {exc}") from exc
                public_handoff = build_storyboard_handoff(spec, accepted, scenes, public_icons, width=1920, height=1080)
                render_drawio(public_handoff, primary_drawio)
                staged = [path for path in staged if path != primary_drawio]
                staged.append(primary_drawio)
                private_staged.append(private_drawio)
                private_drawio_target = private_dir / private_drawio.name
            # Add all audience SVG/PNG/PDF pages where those formats were requested.
            for kind in requested & {"svg", "png", "pdf"}:
                for path in build_storyboard_outputs(handoff, stage_dir / "audience", {kind}, private_icon_catalog=private_icon_receipt):
                    staged.append(path)
            replacements = [(path, out_dir / path.relative_to(stage_dir)) for path in staged if path.is_file()]
            readme_path = Path(project_root).absolute() / "README.md"
            image_target = Path(project_root).absolute() / "docs" / "images" / "project-capabilities.svg"
            if publish_public:
                if "svg" not in requested:
                    raise SummaryError("public project-storyboard requires svg in --formats")
                source = stage_dir / "summary.svg"
                if not source.is_file():
                    raise SummaryError("public project-storyboard requires a final SVG")
                publication = stage_dir / "project-capabilities.svg"; shutil.copyfile(source, publication)
                existing = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""
                relative = os.path.relpath(image_target, start=readme_path.parent).replace("\\\\", "/")
                readme_stage = stage_dir / "README.md"
                from project_intake import markdown_block, upsert_markdown_block
                readme_stage.write_text(upsert_markdown_block(existing, markdown_block(relative, alt_text=str(spec["accessibility"]["alt_text"]))), encoding="utf-8")
                replacements.extend([(publication, image_target), (readme_stage, readme_path)])
            replacements.extend(
                (path, out_dir / path.relative_to(stage_dir))
                for path in private_staged
                if path.is_file()
            )
            promoted_cache = _promote_attempt_icon_cache(staged_icon_cache, private_dir)
            outputs = _project_storyboard_replace(replacements, stage_dir)
        finally:
            shutil.rmtree(stage_dir, ignore_errors=True)
    except Exception:
        if promoted_cache is not None:
            shutil.rmtree(promoted_cache, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(attempt_dir, ignore_errors=True)
    return [path for path in outputs if path != private_drawio_target]


def _parse_formats(value: str) -> set[str]:
    formats = {item.strip().lower() for item in value.split(",") if item.strip()}
    if not formats:
        raise argparse.ArgumentTypeError("formats must contain at least one value")
    return formats


def main(argv: list[str] | None = None) -> int:
    """Build schema-v1 visual-summary artifacts locally, without tenant access."""
    parser = argparse.ArgumentParser(description="Build original OCI visual-summary artifacts locally.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="render visual, editable, handoff, and private art-request outputs")
    build.add_argument("--spec", required=True, type=Path)
    build.add_argument("--out-dir", required=True, type=Path)
    build.add_argument("--formats", required=True, type=_parse_formats)
    build.add_argument("--art-manifest", default=None, type=Path, help="private local artwork manifest returned by the active LLM")
    canvas_plan = subparsers.add_parser("canvas-plan", help="write the private Canvas story-map planning packet")
    canvas_plan.add_argument("--spec", required=True, type=Path)
    canvas_plan.add_argument("--out-dir", required=True, type=Path)
    storyboard_request = subparsers.add_parser(
        "storyboard-request", help="write a private provider-neutral Illo storyboard request"
    )
    storyboard_request.add_argument("--spec", required=True, type=Path)
    storyboard_request.add_argument("--out-dir", required=True, type=Path)
    storyboard_accept = subparsers.add_parser(
        "storyboard-accept", help="validate and store an active-LLM storyboard response"
    )
    storyboard_accept.add_argument("--spec", required=True, type=Path)
    storyboard_accept.add_argument("--response", required=True, type=Path)
    storyboard_accept.add_argument("--out-dir", required=True, type=Path)
    project = subparsers.add_parser("project", help="inspect a local git project and build a capability image")
    project.add_argument("--project-root", required=True, type=Path)
    project.add_argument("--out-dir", required=True, type=Path)
    project.add_argument("--formats", required=True, type=_parse_formats)
    project.add_argument("--audience", default="Operators")
    project.add_argument("--purpose", default="Show the repository capability set.")
    project.add_argument("--domain", default="project")
    project.add_argument("--title", default=None)
    project.add_argument("--devviz-scope-json", default=None, type=Path)
    project.add_argument("--devviz-graph-first-json", default=None, type=Path)
    project.add_argument("--devviz-base-url", default=None)
    project.add_argument("--synthesis-response", default=None, type=Path)
    project.add_argument("--readme", default=None, type=Path)
    project.add_argument("--image-path", default=None, type=Path)
    project.add_argument("--publish-public", action="store_true", help="explicitly approve README/image publication")
    project_storyboard = subparsers.add_parser(
        "project-storyboard", help="write a private storyboard request or build a reviewed project audience bundle"
    )
    project_storyboard.add_argument("--project-root", required=True, type=Path)
    project_storyboard.add_argument("--out-dir", required=True, type=Path)
    project_storyboard.add_argument("--formats", required=True, type=_parse_formats)
    project_storyboard.add_argument("--audience", default="Operators")
    project_storyboard.add_argument("--purpose", default="Explain the repository capability set.")
    project_storyboard.add_argument("--domain", default="project")
    project_storyboard.add_argument("--title", default=None)
    project_storyboard.add_argument("--devviz-scope-json", default=None, type=Path)
    project_storyboard.add_argument("--devviz-base-url", default=None)
    project_storyboard.add_argument("--synthesis-response", default=None, type=Path)
    project_storyboard.add_argument("--storyboard-response", default=None, type=Path)
    project_storyboard.add_argument("--scene-manifest", default=None, type=Path)
    project_storyboard.add_argument("--icon-pack", default=None, type=Path)
    project_storyboard.add_argument("--icon-overrides", default=None, type=Path)
    project_storyboard.add_argument("--icon-policy", choices=("internal-only", "public"), default=None)
    project_storyboard.add_argument("--publish-public", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "build":
        handoff = build_handoff(load_spec(args.spec), 1920, 1080)
        if args.art_manifest is not None:
            handoff = bind_artwork(handoff, load_artwork_manifest(args.art_manifest))
        for path in build_outputs(handoff, args.out_dir, args.formats):
            print(path)
        return 0
    if args.command == "project":
        for path in build_project_summary(
            project_root=args.project_root,
            out_dir=args.out_dir,
            formats=args.formats,
            audience=args.audience,
            purpose=args.purpose,
            domain=args.domain,
            title=args.title,
            devviz_scope_path=args.devviz_scope_json,
            devviz_graph_first_path=args.devviz_graph_first_json,
            devviz_base_url=args.devviz_base_url,
            synthesis_response_path=args.synthesis_response,
            readme_path=args.readme,
            image_path=args.image_path,
            publish_public=args.publish_public,
        ):
            print(path)
        return 0
    if args.command == "project-storyboard":
        for path in build_project_storyboard(
            project_root=args.project_root, out_dir=args.out_dir, formats=args.formats,
            audience=args.audience, purpose=args.purpose, domain=args.domain, title=args.title,
            devviz_scope_path=args.devviz_scope_json, devviz_base_url=args.devviz_base_url,
            synthesis_response_path=args.synthesis_response, storyboard_response_path=args.storyboard_response,
            scene_manifest_path=args.scene_manifest, icon_pack_path=args.icon_pack,
            icon_overrides_path=args.icon_overrides, icon_policy=args.icon_policy,
            publish_public=args.publish_public,
        ):
            print(path)
        return 0
    if args.command == "canvas-plan":
        for path in build_canvas_plan(load_spec(args.spec), args.out_dir):
            print(path)
        return 0
    if args.command == "storyboard-request":
        request = storyboard.build_storyboard_request(load_spec(args.spec))
        out_dir = _canonical_private_output_root(Path(args.out_dir))
        path = _write_private_json(out_dir / ".visual-summary-private", "storyboard-request.json", request)
        print(path)
        return 0
    if args.command == "storyboard-accept":
        summary = load_spec(args.spec)
        accepted = storyboard.validate_storyboard_response(load_storyboard_response(args.response), summary)
        print(storyboard.write_private_storyboard(args.out_dir, accepted))
        return 0
    return 2  # pragma: no cover - argparse owns unsupported subcommands


if __name__ == "__main__":
    raise SystemExit(main())

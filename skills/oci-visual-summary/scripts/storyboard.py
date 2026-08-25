"""Private, provider-neutral Illo storyboard contract for visual summaries."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from io import BytesIO
import hashlib
import struct
import json
import os
from pathlib import Path
import re
import subprocess
from typing import Any
import unicodedata

try:
    from PIL import Image
except ImportError:
    class _HeaderOnlyImageHandle:
        def __init__(self, data: bytes) -> None:
            image_format, dimensions = _sniff_scene_image(data)
            self.format = image_format
            self.size = dimensions

        def verify(self) -> None:
            return None

        def load(self) -> None:
            return None

        def __enter__(self) -> "_HeaderOnlyImageHandle":
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            return False

    class _HeaderOnlyImageModule:
        @staticmethod
        def open(handle: BytesIO) -> _HeaderOnlyImageHandle:
            return _HeaderOnlyImageHandle(handle.getvalue())

    Image = _HeaderOnlyImageModule()  # type: ignore[assignment]


class StoryboardError(ValueError):
    """Raised when a private storyboard is ungrounded or unsafe to write."""


def _require_private_dir_ignored(directory: Path) -> None:
    """Require the exact nested private target to be ignored inside Git worktrees."""
    candidate = Path(directory).absolute()
    ancestor = candidate if candidate.exists() else candidate.parent
    while not ancestor.exists() and ancestor != ancestor.parent:
        ancestor = ancestor.parent
    root = subprocess.run(
        ["git", "-C", str(ancestor), "rev-parse", "--show-toplevel"],
        check=False, capture_output=True, text=True,
    )
    if root.returncode != 0:
        return
    repo = Path(root.stdout.strip()).absolute()
    try:
        relative = candidate.relative_to(repo).as_posix()
    except ValueError:
        return
    ignored = subprocess.run(
        ["git", "-C", str(repo), "check-ignore", "-q", "--", relative + "/"],
        check=False,
    )
    if ignored.returncode != 0:
        raise StoryboardError("private output directory is not git-ignored")


_REQUIRED_REASONING = [
    "artifact_job", "thesis", "register", "physical_move",
    "objects", "interaction_geometry", "cast_role", "service_ids", "service_context",
]
_REGISTERS = {"editorial", "explainer", "mini-comic"}
_DECORATIVE_CHARACTER = ("stands beside", "poses beside", "watches from", "points at the chart")
_PROMPT_KEYS = {"prompt", "scene_prompt", "generation_prompt", "prompt_hint", "instructions"}
_TOP_LEVEL_KEYS = {"schema_version", "classification", "coverage", "project_thesis", "units", "audience_sequence"}
_UNIT_KEYS = {
    "id", "summary_anchor_id", "artifact_job", "thesis", "register", "staging", "physical_move",
    "objects", "character_action", "interaction_geometry", "cast_role", "service_ids", "service_context", "source_ids",
    "evidence_class", "text_policy", "alt_text",
}
_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_.:-]{0,79}$")
_ANCHOR_PATTERN = re.compile(r"^anchor-[1-8]$")
_EVIDENCE_CLASSES = {"design", "code-backed", "configured", "locally-verified", "provider-verified", "release-accepted", "unverified", "unavailable"}
_ACTION_WORDS = re.compile(
    r"\b(?:open|opens|close|closes|turn|turns|route|routes|carry|carries|join|joins|raise|raises|separate|separates|set|sets|trace|traces|connect|connects|move|moves|hold|holds|operate|operates|inspect|inspects|follow|follows|cross|crosses|place|places|pull|pulls|push|pushes|hand|hands)\b",
    re.IGNORECASE,
)
_SCENE_MANIFEST_KEYS = {"schema_version", "scenes"}
_SCENE_REQUIRED_KEYS = {
    "unit_id", "path", "sha256", "character_pack", "model_sheet_digest",
    "generator", "rights", "review_status", "qa",
}
_SCENE_KEYS = _SCENE_REQUIRED_KEYS | {"style_anchor_digest"}
_SCENE_QA_KEYS = {
    "thesis", "artifact_job", "topology", "load_bearing_character",
    "text_free_art", "originality", "style_consistency",
}
_SCENE_IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SCENE_GENERATOR = re.compile(r"^[A-Za-z0-9_. -]{1,80}$")
_MAX_SCENE_BYTES = 10 * 1024 * 1024
_MAX_SCENE_PIXELS = 16_000_000
_MAX_SCENE_EDGE = 8_192
_CREDENTIAL_MATERIAL = re.compile(r"\b(?:password|passwd|secret|api[_ -]?key|auth[_ -]?token|access[_ -]?key)\b\s*(?:=|:)|\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_GENERAL_ABSOLUTE_PATH = re.compile(r"(?:^|(?<![A-Za-z0-9._~-]))(?:/[^\s]+|[A-Za-z]:[\\/][^\s]*|\\\\[^\\\s]+\\[^\s]+)")
_PRIVATE_KEY_MATERIAL = re.compile(r"-----BEGIN [A-Z0-9 ][A-Z0-9 -]*-----", re.IGNORECASE)
_TOKEN_MATERIAL = re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|glpat-[A-Za-z0-9_-]{20,}|sk-[A-Za-z0-9_-]{16,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,})\b")
_SOURCE_EXCERPT_KEY = re.compile(r"(?:source|raw|verbatim)[\W_]*(?:excerpt|quote)|(?:excerpt|quote)[\W_]*(?:source|raw|verbatim)", re.IGNORECASE)
_IMAGE_FORMATS = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}


@dataclass(frozen=True)
class _SceneReceipt:
    manifest_root: Path
    storyboard_digest: str
    scenes: tuple["_ReviewedScene", ...]
    bindings: tuple["_SceneBinding", ...]


@dataclass(frozen=True)
class _ReviewedScene:
    unit_id: str
    path: Path
    sha256: str
    character_pack: str
    model_sheet_digest: str
    style_anchor_digest: str | None
    generator: str
    rights: str
    review_status: str
    qa: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class _SceneBinding:
    unit_id: str
    anchor_id: str
    alt_text: str


class _ValidatedSceneManifest(dict[str, Any]):
    """Dict-compatible result that retains an in-process validated receipt."""

    __slots__ = ("_receipt",)

    def __init__(self, public: dict[str, Any], receipt: _SceneReceipt) -> None:
        super().__init__(public)
        self._receipt = receipt


def _bounded_grounding_view(summary: dict[str, Any]) -> dict[str, Any]:
    anchors = []
    for index, anchor in enumerate(summary.get("anchors", []), start=1):
        if not isinstance(anchor, dict):
            raise StoryboardError("summary anchors must be objects")
        anchors.append({
            "id": f"anchor-{index}",
            "title": anchor.get("title", ""),
            "detail": anchor.get("detail", ""),
            "services": list(anchor.get("services", [])),
            "source_ids": list(anchor.get("source_ids", [])),
            "evidence_class": anchor.get("evidence_class", ""),
        })
    return {
        key: deepcopy(summary[key])
        for key in ("title", "takeaway", "audience", "purpose", "domain", "evidence_class")
        if key in summary
    } | {"anchors": anchors, "sources": deepcopy(summary.get("sources", []))}


def build_storyboard_request(summary: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic private generation input; never select a provider."""
    if not isinstance(summary, dict) or not isinstance(summary.get("anchors"), list):
        raise StoryboardError("summary must contain an anchors list")
    return {
        "schema_version": 1,
        "classification": "private-generation-input",
        "required_reasoning": list(_REQUIRED_REASONING),
        "summary": _bounded_grounding_view(summary),
    }


def _reject_prompt_fields(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).lower() in _PROMPT_KEYS or "prompt" in str(key).lower():
                raise StoryboardError(f"prompt field is not permitted in public storyboard field {path}.{key}")
            _reject_prompt_fields(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_prompt_fields(child, f"{path}[{index}]")


def _anchor_map(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    anchors = summary.get("anchors")
    if not isinstance(anchors, list):
        raise StoryboardError("summary anchors must be a list")
    result = {}
    for index, anchor in enumerate(anchors, start=1):
        if not isinstance(anchor, dict):
            raise StoryboardError("summary anchors must be objects")
        result[f"anchor-{index}"] = anchor
    return result


def _require_non_empty_string(value: Any, field: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise StoryboardError(f"{field} must be a non-empty string")


def _validated_unit_service_context(unit: dict[str, Any], unit_label: str) -> list[dict[str, str]]:
    """Validate explicit private identifiers without deriving either value."""
    context = unit.get("service_context")
    service_ids = unit.get("service_ids")
    if not isinstance(context, list) or not context:
        raise StoryboardError(f"{unit_label}.service_context must be a non-empty list")
    if not isinstance(service_ids, list) or not all(isinstance(value, str) and value.strip() for value in service_ids):
        raise StoryboardError(f"{unit_label}.service_ids must contain non-empty strings")
    display_names: list[str] = []
    canonical_ids: set[str] = set()
    validated: list[dict[str, str]] = []
    for service_index, service in enumerate(context, start=1):
        if not isinstance(service, dict) or set(service) != {"canonical_service_id", "display_name"}:
            raise StoryboardError(f"{unit_label}.service_context[{service_index}] must contain canonical_service_id and display_name")
        canonical_service_id = service.get("canonical_service_id")
        display_name = service.get("display_name")
        if not isinstance(canonical_service_id, str) or not canonical_service_id.strip() or not isinstance(display_name, str) or not display_name.strip():
            raise StoryboardError(f"{unit_label}.service_context[{service_index}] values must be non-empty strings")
        if canonical_service_id in canonical_ids:
            raise StoryboardError(f"{unit_label}.service_context canonical_service_id values must be unique")
        canonical_ids.add(canonical_service_id)
        display_names.append(display_name)
        validated.append({"canonical_service_id": canonical_service_id, "display_name": display_name})
    if display_names != service_ids:
        raise StoryboardError(f"{unit_label}.service_context display_name values must exactly preserve service_ids")
    return validated


def _validate_shape(response: dict[str, Any]) -> None:
    unknown = set(response) - _TOP_LEVEL_KEYS
    if unknown:
        raise StoryboardError(f"unexpected storyboard fields: {sorted(unknown)}")
    _require_non_empty_string(response.get("project_thesis"), "project_thesis")
    units = response.get("units")
    if not isinstance(units, list) or not units:
        raise StoryboardError("units must be a non-empty list")
    for index, unit in enumerate(units):
        if not isinstance(unit, dict):
            raise StoryboardError(f"units[{index}] must be an object")
        unknown = set(unit) - _UNIT_KEYS
        if unknown:
            raise StoryboardError(f"unexpected unit fields: {sorted(unknown)}")
        for field in ("id", "summary_anchor_id", "artifact_job", "thesis", "register", "staging", "physical_move", "character_action", "cast_role", "alt_text"):
            _require_non_empty_string(unit.get(field), f"units[{index}].{field}")
        if not _ID_PATTERN.fullmatch(unit["id"]):
            raise StoryboardError("unit id is not schema-valid")
        if not _ANCHOR_PATTERN.fullmatch(unit["summary_anchor_id"]):
            raise StoryboardError("summary_anchor_id is not schema-valid")
        if unit["register"] not in _REGISTERS:
            raise StoryboardError("unit register is not allowed")
        if unit.get("text_policy") != "deterministic-outside-art":
            raise StoryboardError("text_policy must be deterministic-outside-art")
        geometry = unit.get("interaction_geometry")
        if not ((isinstance(geometry, str) and geometry.strip()) or (isinstance(geometry, dict) and geometry)):
            raise StoryboardError("interaction_geometry must be non-empty contact geometry")
        for field in ("objects", "service_ids", "source_ids"):
            values = unit.get(field)
            if not isinstance(values, list) or not values:
                raise StoryboardError(f"units[{index}].{field} must have the schema-valid shape")
            if not all(isinstance(item, str) and item.strip() for item in values):
                raise StoryboardError(f"units[{index}].{field} must contain non-empty strings")
        _validated_unit_service_context(unit, f"units[{index}]")
        if not isinstance(unit.get("evidence_class"), str) or unit["evidence_class"] not in _EVIDENCE_CLASSES:
            raise StoryboardError("unit evidence_class is not schema-valid")
    sequence = response.get("audience_sequence")
    if not isinstance(sequence, list) or not all(isinstance(item, str) and _ID_PATTERN.fullmatch(item) for item in sequence):
        raise StoryboardError("audience_sequence must contain schema-valid unit IDs")


def validate_storyboard_response(response: dict[str, Any], summary: dict[str, Any]) -> dict[str, Any]:
    """Validate grounding and deterministic/public boundaries without mutation."""
    if not isinstance(response, dict):
        raise StoryboardError("storyboard response must be an object")
    _reject_prompt_fields(response)
    _validate_shape(response)
    expected = {
        "schema_version": 1,
        "classification": "private-generation-input",
        "coverage": "hero-workflow-scenes-service-map-summary",
    }
    for key, value in expected.items():
        if response.get(key) != value:
            raise StoryboardError(f"{key} must equal {value!r}")
    units = response.get("units")
    anchors = _anchor_map(summary)
    seen_ids: set[str] = set()
    for unit in units:
        if not isinstance(unit, dict):
            raise StoryboardError("each unit must be an object")
        anchor_id = unit.get("summary_anchor_id")
        anchor = anchors.get(anchor_id)
        if anchor is None:
            raise StoryboardError(f"unit must bind to exactly one existing anchor: {anchor_id!r}")
        if unit.get("id") in seen_ids:
            raise StoryboardError("unit IDs must be unique")
        seen_ids.add(unit.get("id"))
        for field in ("artifact_job", "thesis", "staging", "physical_move", "character_action", "cast_role", "alt_text"):
            if not isinstance(unit.get(field), str) or not unit[field].strip():
                raise StoryboardError(f"unit {field} must be non-empty")
        if not _ACTION_WORDS.search(unit["physical_move"]):
            raise StoryboardError("physical_move must contain an action verb")
        if not isinstance(unit.get("objects"), list) or not unit["objects"]:
            raise StoryboardError("unit objects must be non-empty")
        if not isinstance(unit.get("service_ids"), list):
            raise StoryboardError("service_ids must be a list")
        if unit.get("service_ids") != list(anchor.get("services", [])):
            raise StoryboardError("unit service_ids must preserve its anchor service IDs")
        expected_sources = anchor.get("source_ids")
        if unit.get("source_ids") != expected_sources:
            raise StoryboardError("unit source_ids must exactly preserve its anchor source_ids")
        if unit.get("evidence_class") != anchor.get("evidence_class"):
            raise StoryboardError("unit evidence_class must exactly preserve its anchor evidence_class")
        action = unit["character_action"].lower()
        if any(phrase in action for phrase in _DECORATIVE_CHARACTER):
            raise StoryboardError("decorative character action is not allowed")
    sequence = response.get("audience_sequence")
    if not isinstance(sequence, list) or len(sequence) != len(seen_ids) or set(sequence) != seen_ids:
        raise StoryboardError("audience_sequence must be an exact, duplicate-free permutation of accepted unit IDs")
    return deepcopy(response)


def canonical_service_context(storyboard: dict[str, Any]) -> list[dict[str, str]]:
    """Return the explicitly accepted canonical service context for icon mapping.

    The resolver deliberately does not infer identifiers or display labels from
    prose, service IDs, or catalog labels.  Each accepted unit must instead
    carry its grounded ``service_context`` entries as canonical-ID/display-name
    pairs.
    """
    if not isinstance(storyboard, dict) or not isinstance(storyboard.get("units"), list):
        raise StoryboardError("accepted storyboard must contain units")
    result: list[dict[str, str]] = []
    for unit_index, unit in enumerate(storyboard["units"], start=1):
        if not isinstance(unit, dict):
            raise StoryboardError(f"accepted storyboard unit {unit_index} must be an object")
        unit_id = unit.get("id")
        alt_text = unit.get("alt_text")
        if not isinstance(unit_id, str) or not unit_id.strip() or not isinstance(alt_text, str) or not alt_text.strip():
            raise StoryboardError(f"accepted storyboard unit {unit_index} needs id and alt_text")
        for service in _validated_unit_service_context(unit, f"accepted storyboard unit {unit_id}"):
            result.append({
                "unit_id": unit_id,
                "canonical_service_id": service["canonical_service_id"],
                "display_name": service["display_name"],
                "alt_text": alt_text,
            })
    return result


def _service_pattern(service: str) -> re.Pattern[str]:
    chunks = re.findall(r"[\w]+", unicodedata.normalize("NFKC", service), re.UNICODE)
    if not chunks:
        raise StoryboardError("service_context contains no canonical service identifier")
    return re.compile(r"[\W_]*".join(re.escape(chunk) for chunk in chunks), re.IGNORECASE)


def _request_strings(value: Any):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for child in value.values():
            yield from _request_strings(child)
    elif isinstance(value, list):
        for child in value:
            yield from _request_strings(child)


def _reject_request_material(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized_key = re.sub(r"[\W_]+", "", unicodedata.normalize("NFKC", str(key)).casefold())
            if _SOURCE_EXCERPT_KEY.search(unicodedata.normalize("NFKC", str(key))) or normalized_key in {
                "verbatim", "sourcetext", "quotedsource", "quotedtext", "rawexcerpt", "rawquote", "sourceexcerpt", "sourcequote",
            }:
                raise StoryboardError("source excerpt fields are not permitted in art requests")
            if str(key) == "source_ids":
                # Grounding receipts stay private and are deliberately omitted
                # from the image request, so their source URLs are not art text.
                continue
            _reject_request_material(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _reject_request_material(child, f"{path}[{index}]")
    elif isinstance(value, str):
        if _CREDENTIAL_MATERIAL.search(value) or _PRIVATE_KEY_MATERIAL.search(value) or _TOKEN_MATERIAL.search(value):
            raise StoryboardError(f"credential-looking material is not permitted in request field {path}")
        if _GENERAL_ABSOLUTE_PATH.search(value):
            raise StoryboardError(f"absolute local paths are not permitted in request field {path}")
        if "http://" in value.casefold() or "https://" in value.casefold():
            raise StoryboardError(f"source URLs are not permitted in request field {path}")


def _assert_services_confined(request: dict[str, Any]) -> None:
    """Reject canonical service labels in every structured field but context."""
    for unit in request["units"]:
        services = [
            value
            for service in unit["service_context"] if isinstance(service, dict)
            for value in (service.get("canonical_service_id"), service.get("display_name"))
            if isinstance(value, str) and value
        ]
        patterns = [_service_pattern(service) for service in services]
        for key, value in unit.items():
            if key == "service_context":
                continue
            for text_value in _request_strings(value):
                if any(pattern.search(unicodedata.normalize("NFKC", text_value)) for pattern in patterns):
                    raise StoryboardError("canonical service context leaked outside service_context")


def _reject_storyboard_service_leaks(storyboard: dict[str, Any]) -> None:
    for unit in storyboard["units"]:
        if not isinstance(unit, dict):
            continue
        context = _validated_unit_service_context(unit, f"accepted storyboard unit {unit.get('id', '<unknown>')}")
        service_values = [*unit["service_ids"], *(service["canonical_service_id"] for service in context)]
        patterns = [_service_pattern(value) for value in service_values]
        for key, value in unit.items():
            if key in {"service_ids", "service_context", "source_ids"}:
                continue
            if any(pattern.search(unicodedata.normalize("NFKC", text)) for text in _request_strings(value) for pattern in patterns):
                raise StoryboardError("canonical service values are permitted only in service_context")


def build_illo_art_request(storyboard: dict[str, Any]) -> dict[str, Any]:
    """Build a text-free, provider-neutral private scene-pack request.

    This is a request and review protocol only: it neither chooses nor invokes
    an image renderer, provider, model, or paid service.
    """
    if not isinstance(storyboard, dict) or not isinstance(storyboard.get("units"), list):
        raise StoryboardError("accepted storyboard must contain units")
    _reject_request_material(storyboard)
    _reject_storyboard_service_leaks(storyboard)
    units = []
    for unit in storyboard["units"]:
        if not isinstance(unit, dict):
            raise StoryboardError("accepted storyboard units must be objects")
        for key in ("id", "thesis", "register", "staging", "physical_move", "objects", "character_action", "interaction_geometry", "alt_text", "service_ids", "service_context"):
            if key not in unit:
                raise StoryboardError(f"accepted storyboard unit lacks {key}")
        context = _validated_unit_service_context(unit, f"accepted storyboard unit {unit['id']}")
        services = [service["display_name"] for service in context]
        patterns = [_service_pattern(service) for service in services]

        def neutralize(value: Any) -> Any:
            if isinstance(value, str):
                result = unicodedata.normalize("NFKC", value)
                for pattern in patterns:
                    result = pattern.sub("the named service", result)
                return result
            if isinstance(value, list):
                return [neutralize(item) for item in value]
            if isinstance(value, dict):
                return {key: neutralize(item) for key, item in value.items()}
            return deepcopy(value)

        staging = neutralize(unit["staging"])
        character_action = neutralize(unit["character_action"])
        physical_move = neutralize(unit["physical_move"])
        objects = neutralize(unit["objects"])
        geometry = neutralize(unit["interaction_geometry"])
        prompt = (
            f"Create an original sketchbook scene. Stage {staging}. "
            f"Show {character_action} through this physical move: {physical_move}. "
            f"Use these ordinary objects: {', '.join(objects)}. "
            f"Make the contact geometry clear: {geometry}. "
            "No generated text, letters, numbers, labels, logos, screenshots, UI, copied layouts, "
            "or copied branding. Do not draw or imitate Oracle, Redwood, or OCI service icons."
        )
        units.append({
            "unit_id": unit["id"],
            "scene_role": neutralize(unit["artifact_job"]),
            "thesis": neutralize(unit["thesis"]),
            "register": neutralize(unit["register"]),
            "staging": staging,
            "physical_move": physical_move,
            "objects": objects,
            "character_action": character_action,
            "interaction_geometry": geometry,
            "aspect_ratio": "16:9",
            "alt_text": neutralize(unit["alt_text"]),
            "text_policy": "no-generated-text",
            "service_context": deepcopy(context),
            "render_prompt": prompt,
        })
    request = {
        "schema_version": 1,
        "classification": "private-generation-input",
        "style": {"preferred": "sketchbook", "text_free": True, "original_only": True},
        "consistency": {
            "character_pack_required": True,
            "model_sheet_required": True,
            "first_approved_scene_becomes_style_anchor": True,
        },
        "units": units,
    }
    _assert_services_confined(request)
    return request


def _manifest_root(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise StoryboardError("scene manifest must be a real local file")
    root = path.parent
    if root.is_symlink() or not root.is_dir():
        raise StoryboardError("scene manifest root must be a real directory")
    return root.resolve(strict=True)


def _read_scene_bytes(path: Path, index: int) -> bytes:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise StoryboardError(f"scene {index} image is unavailable: {exc}") from exc
    if not 0 < len(data) <= _MAX_SCENE_BYTES:
        raise StoryboardError(f"scene {index} image exceeds the bounded file size")
    return data


def _validate_scene_image_bytes(data: bytes, path: Path, index: int) -> None:
    expected_format = _IMAGE_FORMATS[path.suffix.lower()]
    if Image is None:
        raise StoryboardError("scene image decoder is unavailable")
    try:
        with Image.open(BytesIO(data)) as image:
            image_format, dimensions = image.format, image.size
            if image_format != expected_format or not all(0 < side <= _MAX_SCENE_EDGE for side in dimensions) or dimensions[0] * dimensions[1] > _MAX_SCENE_PIXELS:
                raise StoryboardError(f"scene {index} image has an unsupported or unsafe format")
            image.verify()
        with Image.open(BytesIO(data)) as image:
            image.load()
    except StoryboardError:
        raise
    except Exception as exc:
        raise StoryboardError(f"scene {index} image has an unsupported or unsafe format: {exc}") from exc
    if image_format != expected_format or not all(0 < side <= _MAX_SCENE_EDGE for side in dimensions) or dimensions[0] * dimensions[1] > _MAX_SCENE_PIXELS:
        raise StoryboardError(f"scene {index} image has an unsupported or unsafe format")


def _sniff_scene_image(data: bytes) -> tuple[str, tuple[int, int]]:
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return "PNG", (width, height)
    if data.startswith(b"RIFF") and len(data) >= 30 and data[8:12] == b"WEBP":
        chunk = data[12:16]
        if chunk == b"VP8X" and len(data) >= 30:
            width = 1 + int.from_bytes(data[24:27], "little")
            height = 1 + int.from_bytes(data[27:30], "little")
            return "WEBP", (width, height)
        if chunk == b"VP8L" and len(data) >= 25:
            bits = int.from_bytes(data[21:25], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
            return "WEBP", (width, height)
        if chunk == b"VP8 " and len(data) >= 30:
            width = int.from_bytes(data[26:28], "little") & 0x3FFF
            height = int.from_bytes(data[28:30], "little") & 0x3FFF
            return "WEBP", (width, height)
    if data.startswith(b"\xff\xd8"):
        offset = 2
        while offset + 9 <= len(data):
            if data[offset] != 0xFF:
                offset += 1
                continue
            marker = data[offset + 1]
            offset += 2
            if marker in {0xD8, 0xD9}:
                continue
            if offset + 2 > len(data):
                break
            segment_length = int.from_bytes(data[offset:offset + 2], "big")
            if segment_length < 2 or offset + segment_length > len(data):
                break
            if marker in {
                0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF,
            } and offset + 7 <= len(data):
                height = int.from_bytes(data[offset + 3:offset + 5], "big")
                width = int.from_bytes(data[offset + 5:offset + 7], "big")
                return "JPEG", (width, height)
            offset += segment_length
    raise StoryboardError("scene image decoder is unavailable")


def _canonical_storyboard_bytes(storyboard: dict[str, Any]) -> bytes:
    try:
        return json.dumps(
            storyboard, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise StoryboardError(f"accepted storyboard is not serializable: {exc}") from exc


def _storyboard_digest(storyboard: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_storyboard_bytes(storyboard)).hexdigest()


def reviewed_scene_snapshot(manifest: dict[str, Any], accepted_storyboard: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return one coherent receipt snapshot after a final current-byte check."""
    if not isinstance(manifest, _ValidatedSceneManifest):
        raise StoryboardError("validated scene manifest receipt is required")
    receipt = manifest._receipt
    if accepted_storyboard is not None and (
        not isinstance(accepted_storyboard, dict) or _storyboard_digest(accepted_storyboard) != receipt.storyboard_digest
    ):
        raise StoryboardError("accepted storyboard does not match the scene-manifest receipt")
    scenes = []
    for index, scene in enumerate(receipt.scenes, start=1):
        data = _read_scene_bytes(scene.path, index)
        current_digest = hashlib.sha256(data).hexdigest()
        if current_digest != scene.sha256:
            raise StoryboardError(f"scene {index} digest does not match local image")
        _validate_scene_image_bytes(data, scene.path, index)
        scenes.append({
            "unit_id": scene.unit_id, "path": scene.path, "sha256": scene.sha256,
            "character_pack": scene.character_pack, "model_sheet_digest": scene.model_sheet_digest,
            "style_anchor_digest": scene.style_anchor_digest, "generator": scene.generator,
            "rights": scene.rights, "review_status": scene.review_status,
            "qa": dict(scene.qa),
        })
    return {
        "schema_version": 1,
        "manifest_root": receipt.manifest_root,
        "storyboard_digest": receipt.storyboard_digest,
        "bindings": tuple(receipt.bindings),
        "scenes": scenes,
    }


def load_scene_manifest(path: Path, storyboard: dict[str, Any]) -> dict[str, Any]:
    """Load an approved, digest-bound local scene pack for assembly only."""
    storyboard_bytes = _canonical_storyboard_bytes(storyboard)
    storyboard_digest = hashlib.sha256(storyboard_bytes).hexdigest()
    storyboard_snapshot = json.loads(storyboard_bytes.decode("utf-8"))
    path = Path(path)
    root = _manifest_root(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StoryboardError(f"invalid scene manifest: {exc}") from exc
    if not isinstance(raw, dict) or set(raw) != _SCENE_MANIFEST_KEYS or raw.get("schema_version") != 1:
        raise StoryboardError("scene manifest must use schema version 1")
    scenes = raw.get("scenes")
    if not isinstance(scenes, list) or not scenes:
        raise StoryboardError("scene manifest must contain scenes")
    accepted_units = {
        unit.get("id"): unit
        for unit in storyboard_snapshot.get("units", [])
        if isinstance(unit, dict) and isinstance(unit.get("id"), str)
    }
    if not accepted_units:
        raise StoryboardError("accepted storyboard must contain units")
    reviewed: list[dict[str, Any]] = []
    seen_units: set[str] = set()
    seen_paths: set[Path] = set()
    model_sheet_by_character_pack: dict[str, str] = {}
    first_asset_digest: str | None = None
    for index, scene in enumerate(scenes, start=1):
        if not isinstance(scene, dict) or not _SCENE_REQUIRED_KEYS.issubset(scene) or set(scene) - _SCENE_KEYS:
            raise StoryboardError(f"scene {index} has unsupported or missing fields")
        unit_id = scene.get("unit_id")
        if not isinstance(unit_id, str) or unit_id not in accepted_units or unit_id in seen_units:
            raise StoryboardError(f"scene {index} must bind one unique accepted unit")
        seen_units.add(unit_id)
        raw_path = scene.get("path")
        if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute() or "://" in raw_path:
            raise StoryboardError(f"scene {index} path must be relative and local")
        relative = Path(raw_path)
        if ".." in relative.parts or relative.suffix.lower() not in _SCENE_IMAGE_SUFFIXES:
            raise StoryboardError(f"scene {index} path has unsupported format or escapes manifest root")
        candidate = root / relative
        component = root
        for part in relative.parts:
            component = component / part
            if component.is_symlink():
                raise StoryboardError(f"scene {index} must not traverse a symlink")
        if not candidate.is_file():
            raise StoryboardError(f"scene {index} must be a real local image")
        resolved = candidate.resolve(strict=True)
        if root not in (resolved, *resolved.parents) or resolved in seen_paths:
            raise StoryboardError(f"scene {index} is outside manifest root or duplicates an image")
        seen_paths.add(resolved)
        if scene.get("review_status") != "approved":
            raise StoryboardError(f"scene {index} must be approved before assembly")
        image_bytes = _read_scene_bytes(resolved, index)
        _validate_scene_image_bytes(image_bytes, resolved, index)
        digest = scene.get("sha256")
        if not isinstance(digest, str) or not _SHA256.fullmatch(digest) or hashlib.sha256(image_bytes).hexdigest() != digest:
            raise StoryboardError(f"scene {index} digest does not match local image")
        if not isinstance(scene.get("character_pack"), str) or not scene["character_pack"].strip():
            raise StoryboardError(f"scene {index} requires character_pack")
        if not isinstance(scene.get("model_sheet_digest"), str) or not _SHA256.fullmatch(scene["model_sheet_digest"]):
            raise StoryboardError(f"scene {index} requires a model_sheet_digest")
        character_pack = scene["character_pack"]
        known_model_sheet = model_sheet_by_character_pack.get(character_pack)
        if known_model_sheet is None:
            model_sheet_by_character_pack[character_pack] = scene["model_sheet_digest"]
        elif scene["model_sheet_digest"] != known_model_sheet:
            raise StoryboardError("recurring identity requires one model-sheet digest")
        anchor_digest = scene.get("style_anchor_digest")
        if index == 1:
            if anchor_digest is not None and anchor_digest != digest:
                raise StoryboardError("first scene style_anchor_digest must equal its verified asset digest")
            first_asset_digest = digest
        elif not isinstance(anchor_digest, str) or anchor_digest != first_asset_digest:
            raise StoryboardError("later scenes must reference the first verified style-anchor digest")
        if index > 1 and not _SHA256.fullmatch(anchor_digest):
            raise StoryboardError(f"scene {index} requires a style_anchor_digest")
        if index == 1 and anchor_digest is not None and not _SHA256.fullmatch(anchor_digest):
            raise StoryboardError(f"scene {index} has an invalid style_anchor_digest")
        if not isinstance(scene.get("generator"), str) or not _SCENE_GENERATOR.fullmatch(scene["generator"]):
            raise StoryboardError(f"scene {index} has invalid generator label")
        if scene.get("rights") not in {"original", "user-supplied"}:
            raise StoryboardError(f"scene {index} requires explicit rights")
        qa = scene.get("qa")
        if not isinstance(qa, dict) or set(qa) != _SCENE_QA_KEYS or any(value != "pass" for value in qa.values()):
            raise StoryboardError(f"scene {index} requires all review QA results to pass")
        reviewed.append(_ReviewedScene(
            unit_id=unit_id, path=resolved, sha256=digest,
            character_pack=scene["character_pack"], model_sheet_digest=scene["model_sheet_digest"],
            style_anchor_digest=anchor_digest, generator=scene["generator"], rights=scene["rights"],
            review_status=scene["review_status"], qa=tuple(sorted(qa.items())),
        ))
    bindings = tuple(_SceneBinding(
        unit_id=unit_id,
        anchor_id=accepted_units[unit_id].get("summary_anchor_id", ""),
        alt_text=accepted_units[unit_id].get("alt_text", ""),
    ) for unit_id in (scene.unit_id for scene in reviewed))
    if any(not binding.anchor_id or not binding.alt_text for binding in bindings):
        raise StoryboardError("accepted storyboard requires unit-to-anchor and alt-text bindings")
    receipt = _SceneReceipt(root, storyboard_digest, tuple(reviewed), bindings)
    return _ValidatedSceneManifest({
        "schema_version": 1,
        "manifest_root": root,
        "scenes": [
            {"unit_id": scene.unit_id, "path": scene.path, "sha256": scene.sha256,
             "style_anchor_digest": scene.style_anchor_digest}
            for scene in reviewed
        ],
    }, receipt)


def approved_scene_assets(manifest: dict[str, Any]) -> dict[str, Path]:
    """Return only reviewed scene paths keyed by their accepted unit ID."""
    manifest = reviewed_scene_snapshot(manifest)
    assets: dict[str, Path] = {}
    for scene in manifest["scenes"]:
        if not isinstance(scene, dict) or scene.get("review_status") != "approved":
            raise StoryboardError("only approved scenes may cross the assembly gate")
        unit_id, image_path = scene.get("unit_id"), scene.get("path")
        if not isinstance(unit_id, str) or not isinstance(image_path, Path) or unit_id in assets:
            raise StoryboardError("validated scene manifest has invalid asset bindings")
        assets[unit_id] = image_path
    return assets


def write_private_storyboard(root: Path, storyboard: dict[str, Any]) -> Path:
    """Write only root/.visual-summary-private/storyboard.json, mode 0600."""
    root = Path(root)
    # Match visual_summary's established trusted macOS alias handling before
    # rejecting symlinks: /var is the system alias for /private/var.
    var_alias = Path("/var")
    canonical_var = Path("/private/var")
    if var_alias.is_symlink() and Path(os.path.realpath(var_alias)) == canonical_var:
        try:
            root = canonical_var / root.relative_to(var_alias)
        except ValueError:
            pass
    if root.is_symlink() or (root.exists() and not root.is_dir()):
        raise StoryboardError("private root must be a real directory")
    for component in (root, *root.parents):
        if component.exists() and component.is_symlink():
            raise StoryboardError(f"refusing symlinked private root: {component}")
    root = Path(os.path.abspath(os.fspath(root)))
    private_dir = root / ".visual-summary-private"
    target = private_dir / "storyboard.json"
    try:
        _require_private_dir_ignored(private_dir)
        # Check before mkdir/chmod: mkdir(exist_ok=True) and chmod would follow
        # a pre-existing private-directory symlink and mutate outside root.
        for component in (private_dir, target, *private_dir.parents):
            if component.is_symlink():
                raise StoryboardError(f"refusing symlinked private output: {component}")
        private_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        if private_dir.is_symlink() or not private_dir.is_dir():
            raise StoryboardError("private output directory must be a real directory")
        os.chmod(private_dir, 0o700)
        for component in (private_dir, target, *private_dir.parents):
            if component.is_symlink():
                raise StoryboardError(f"refusing symlinked private output: {component}")
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(target, flags, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(storyboard, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(target, 0o600)
    except (OSError, TypeError, ValueError) as exc:
        if isinstance(exc, StoryboardError):
            raise
        raise StoryboardError(f"could not write private storyboard safely: {exc}") from exc
    return target

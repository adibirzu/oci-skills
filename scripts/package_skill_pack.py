#!/usr/bin/env python3
"""Build and verify the OCI Skills package checksum manifest and archive."""
from __future__ import annotations

import argparse
import fnmatch
import gzip
import hashlib
import io
import json
import os
import re
import stat
import sys
import tarfile
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:  # pragma: no cover - optional on minimal workstations
    jsonschema = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path("generated/release/skill-pack-checksums.json")
SCHEMA_REL = Path("schemas/skill-pack-checksums.schema.json")
INSTALL_MANIFEST_REL = Path("docs/product/contracts/install-manifest.json")
SBOM_REL = Path("generated/security/oci-skills.cdx.json")
PLUGIN_MANIFEST_DIRS = (
    Path(".claude-plugin"),
    Path(".codex-plugin"),
    Path("harness/gemini/gemini-extension.json"),
)
HARNESS_ADAPTER_DIRS = (Path("harness"),)
MCP_SURFACE_FILES = (Path("references/mcp-gateway.md"),)
DEFAULT_SOURCE_DATE_EPOCH = 0
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class PackageChecksumError(ValueError):
    """Raised when package inputs, schema, or checksums fail validation."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _is_excluded(relative: Path, exclusions: list[str]) -> bool:
    for part in relative.parts:
        if any(fnmatch.fnmatchcase(part, pattern) for pattern in exclusions):
            return True
    name = relative.name
    return any(fnmatch.fnmatchcase(name, pattern) for pattern in exclusions)


def _read_json_object(path: Path, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise PackageChecksumError(f"{label} missing or symlinked: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PackageChecksumError(f"{label} is not valid JSON: {path}") from exc
    if not isinstance(data, dict):
        raise PackageChecksumError(f"{label} must be a JSON object: {path}")
    return data


def _collect_regular_files(
    root: Path,
    relative_item: Path,
    exclusions: list[str],
) -> list[Path]:
    candidate = root / relative_item
    if candidate.is_symlink():
        raise PackageChecksumError(
            f"symlink not allowed in package surface: {relative_item.as_posix()}"
        )
    if candidate.is_file():
        if _is_excluded(relative_item, exclusions):
            return []
        return [candidate]
    if not candidate.is_dir():
        raise PackageChecksumError(
            f"required package surface missing: {relative_item.as_posix()}"
        )

    files: list[Path] = []
    for entry in sorted(candidate.rglob("*")):
        rel = entry.relative_to(root)
        if _is_excluded(rel, exclusions):
            continue
        if entry.is_symlink():
            raise PackageChecksumError(
                f"symlink not allowed in package surface: {rel.as_posix()}"
            )
        if entry.is_file():
            files.append(entry)
    return files


def _resolve_source_date_epoch(value: str | None = None) -> int:
    raw = os.environ.get("SOURCE_DATE_EPOCH") if value is None else value
    if raw is None or not raw.strip():
        return DEFAULT_SOURCE_DATE_EPOCH
    try:
        epoch = int(raw.strip())
    except ValueError as exc:
        raise PackageChecksumError("SOURCE_DATE_EPOCH must be an integer") from exc
    if epoch < 0:
        raise PackageChecksumError("SOURCE_DATE_EPOCH must be non-negative")
    return epoch


def _validate_node(value: Any, schema: dict[str, Any], path: str) -> list[str]:
    errors: list[str] = []
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected const {schema['const']!r}")
        return errors
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} not in enum {schema['enum']!r}")
        return errors

    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(value, dict):
            return [f"{path}: expected object"]
        for req in schema.get("required", []):
            if req not in value:
                errors.append(f"{path}: missing required key '{req}'")
        props = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(props))
            if extras:
                errors.append(f"{path}: unexpected properties {extras}")
        for key, prop_schema in props.items():
            if key in value:
                errors.extend(_validate_node(value[key], prop_schema, f"{path}.{key}"))
    elif expected_type == "array":
        if not isinstance(value, list):
            return [f"{path}: expected array"]
        min_items = schema.get("minItems")
        if min_items is not None and len(value) < min_items:
            errors.append(f"{path}: expected at least {min_items} items")
        if schema.get("uniqueItems") and len(value) != len(set(value)):
            errors.append(f"{path}: items must be unique")
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for idx, item in enumerate(value):
                errors.extend(_validate_node(item, item_schema, f"{path}[{idx}]"))
    elif expected_type == "string":
        if not isinstance(value, str):
            return [f"{path}: expected string"]
        min_len = schema.get("minLength")
        if min_len is not None and len(value) < min_len:
            errors.append(f"{path}: string shorter than {min_len}")
        pattern = schema.get("pattern")
        if pattern and re.fullmatch(pattern, value) is None:
            errors.append(f"{path}: string does not match {pattern}")
    elif expected_type == "integer":
        if isinstance(value, bool) or not isinstance(value, int):
            return [f"{path}: expected integer"]
        minimum = schema.get("minimum")
        if minimum is not None and value < minimum:
            errors.append(f"{path}: integer below minimum {minimum}")
    return errors


def validate_manifest_schema(
    manifest: dict[str, Any],
    schema: dict[str, Any] | None = None,
    root: Path = ROOT,
) -> list[str]:
    """Validate checksum manifest against schemas/skill-pack-checksums.schema.json."""
    resolved_schema = schema or _read_json_object(
        root / SCHEMA_REL, "checksum schema"
    )
    if getattr(jsonschema, "Draft202012Validator", None) is not None:
        validator = jsonschema.Draft202012Validator(resolved_schema)
        errs = sorted(validator.iter_errors(manifest), key=lambda err: str(err.path))
        if errs:
            return [err.message for err in errs]
    return _validate_node(manifest, resolved_schema, "$")


def build_checksum_manifest(root: Path = ROOT) -> dict[str, Any]:
    """Collect indexed skill-pack, manifest, MCP, and SBOM SHA-256 digests."""
    root = root.resolve()
    install_manifest = _read_json_object(root / INSTALL_MANIFEST_REL, "install manifest")
    payload = install_manifest.get("payload")
    exclusions = install_manifest.get("exclusions", [])
    if not isinstance(payload, list) or not all(isinstance(x, str) for x in payload):
        raise PackageChecksumError("install manifest payload must be a string list")
    if not isinstance(exclusions, list) or not all(
        isinstance(x, str) for x in exclusions
    ):
        raise PackageChecksumError("install manifest exclusions must be a string list")

    codex_plugin = _read_json_object(
        root / ".codex-plugin/plugin.json", "codex plugin manifest"
    )
    claude_plugin = _read_json_object(
        root / ".claude-plugin/plugin.json", "claude plugin manifest"
    )
    gemini_plugin = _read_json_object(
        root / "harness/gemini/gemini-extension.json", "gemini extension manifest"
    )
    version = codex_plugin.get("version")
    if not isinstance(version, str) or not version:
        raise PackageChecksumError("codex plugin manifest missing version")
    if (
        claude_plugin.get("version") != version
        or gemini_plugin.get("version") != version
    ):
        raise PackageChecksumError("plugin manifest versions do not match")

    sbom_path = root / SBOM_REL
    sbom_data = _read_json_object(sbom_path, "SBOM")
    if (
        sbom_data.get("bomFormat") != "CycloneDX"
        or sbom_data.get("specVersion") != "1.6"
    ):
        raise PackageChecksumError("SBOM must be CycloneDX 1.6")
    sbom_sha256 = _sha256(sbom_path.read_bytes())

    entries_by_path: dict[str, dict[str, Any]] = {}
    plugin_manifests: list[str] = []
    mcp_surface: list[str] = []
    skill_pack_files: list[str] = []

    def add_file(path: Path, category: str) -> None:
        rel = path.relative_to(root).as_posix()
        if rel in entries_by_path:
            return
        raw = path.read_bytes()
        entries_by_path[rel] = {
            "path": rel,
            "category": category,
            "size_bytes": len(raw),
            "sha256": _sha256(raw),
        }
        if category == "plugin-manifest":
            plugin_manifests.append(rel)
        elif category == "mcp-surface":
            mcp_surface.append(rel)
        elif category == "skill-pack":
            skill_pack_files.append(rel)

    for manifest_dir in PLUGIN_MANIFEST_DIRS:
        for file_path in _collect_regular_files(root, manifest_dir, exclusions):
            add_file(file_path, "plugin-manifest")

    add_file(root / INSTALL_MANIFEST_REL, "install-manifest")

    for mcp_rel in MCP_SURFACE_FILES:
        for file_path in _collect_regular_files(root, mcp_rel, exclusions):
            add_file(file_path, "mcp-surface")

    add_file(sbom_path, "sbom")

    for item in (*payload, *(p.as_posix() for p in HARNESS_ADAPTER_DIRS)):
        for file_path in _collect_regular_files(root, Path(item), exclusions):
            add_file(file_path, "skill-pack")

    files = [entries_by_path[key] for key in sorted(entries_by_path)]
    digest_hasher = hashlib.sha256()
    for entry in files:
        digest_hasher.update(
            f"{entry['path']}\0{entry['category']}\0{entry['sha256']}\0".encode()
        )

    manifest = {
        "schema_version": 1,
        "algorithm": "sha256",
        "ordering": "bytewise-path",
        "package": {
            "name": "oci-skills",
            "version": version,
            "source_date_epoch": DEFAULT_SOURCE_DATE_EPOCH,
        },
        "sbom": {
            "path": SBOM_REL.as_posix(),
            "format": "CycloneDX",
            "spec_version": "1.6",
            "sha256": sbom_sha256,
        },
        "surfaces": {
            "plugin_manifests": sorted(plugin_manifests),
            "install_manifest": INSTALL_MANIFEST_REL.as_posix(),
            "mcp_surface": sorted(mcp_surface),
            "skill_pack_files": sorted(skill_pack_files),
        },
        "file_count": len(files),
        "manifest_sha256": digest_hasher.hexdigest(),
        "files": files,
    }
    schema_errors = validate_manifest_schema(manifest, root=root)
    if schema_errors:
        raise PackageChecksumError(
            "generated checksum manifest failed schema validation: "
            + "; ".join(schema_errors)
        )
    return manifest


def render_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_atomic(path: Path, payload: bytes) -> None:
    if path.is_symlink():
        raise PackageChecksumError(f"output path cannot be a symlink: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f".{path.name}.tmp")
    try:
        tmp_path.write_bytes(payload)
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, path)
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def build_archive(root: Path, output_dir: Path, source_date_epoch: int) -> Path:
    """Build a deterministic tar.gz package archive normalized by SOURCE_DATE_EPOCH."""
    root = root.resolve()
    manifest = build_checksum_manifest(root)
    committed = root / DEFAULT_OUTPUT
    if committed.is_symlink():
        raise PackageChecksumError("checksum manifest cannot be a symlink")
    if not committed.is_file():
        raise PackageChecksumError(
            "checksum manifest missing; run python3 scripts/package_skill_pack.py --write"
        )
    if committed.read_bytes() != render_manifest_bytes(manifest):
        raise PackageChecksumError(
            "checksum manifest is stale; run python3 scripts/package_skill_pack.py --write"
        )

    if output_dir.is_symlink():
        raise PackageChecksumError(f"archive directory cannot be a symlink: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    version = manifest["package"]["version"]
    archive_name = f"oci-skills-{version}.tar.gz"
    archive_path = output_dir / archive_name
    prefix = f"oci-skills-{version}"

    archive_files: list[tuple[str, bytes, int]] = []
    for entry in manifest["files"]:
        rel = entry["path"]
        src = root / rel
        mode = 0o755 if (stat.S_IMODE(src.stat().st_mode) & 0o111) else 0o644
        archive_files.append((f"{prefix}/{rel}", src.read_bytes(), mode))

    manifest_bytes = render_manifest_bytes(manifest)
    archive_files.append((f"{prefix}/{DEFAULT_OUTPUT.as_posix()}", manifest_bytes, 0o644))
    archive_files.sort(key=lambda item: item[0])

    buf = io.BytesIO()
    with (
        gzip.GzipFile(
            filename="",
            mode="wb",
            compresslevel=9,
            fileobj=buf,
            mtime=source_date_epoch,
        ) as gz_file,
        tarfile.open(fileobj=gz_file, mode="w", format=tarfile.USTAR_FORMAT) as tf,
    ):
        for arcname, raw, mode in archive_files:
            info = tarfile.TarInfo(name=arcname)
            info.size = len(raw)
            info.mode = mode
            info.uid = 0
            info.gid = 0
            info.uname = "root"
            info.gname = "root"
            info.mtime = source_date_epoch
            tf.addfile(info, io.BytesIO(raw))

    archive_bytes = buf.getvalue()
    _write_atomic(archive_path, archive_bytes)
    _write_atomic(
        output_dir / f"{archive_name}.sha256",
        f"{_sha256(archive_bytes)}  {archive_name}\n".encode(),
    )
    return archive_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--build-archive", type=Path, metavar="DIR")
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args(argv)

    root = args.root.resolve()
    output = args.output if args.output is not None else root / DEFAULT_OUTPUT
    try:
        manifest = build_checksum_manifest(root)
        expected = render_manifest_bytes(manifest)
        if args.write:
            _write_atomic(output, expected)
            print(
                json.dumps(
                    {
                        "status": "written",
                        "output": str(output),
                        "file_count": manifest["file_count"],
                        "manifest_sha256": manifest["manifest_sha256"],
                    },
                    sort_keys=True,
                )
            )
            return 0
        if args.check:
            if output.is_symlink() or not output.is_file():
                raise PackageChecksumError(
                    "checksum manifest missing or symlinked; "
                    "run python3 scripts/package_skill_pack.py --write"
                )
            actual_raw = output.read_bytes()
            if actual_raw != expected:
                raise PackageChecksumError(
                    "checksum manifest stale; "
                    "run python3 scripts/package_skill_pack.py --write"
                )
            actual_json = json.loads(actual_raw.decode("utf-8"))
            schema_errors = validate_manifest_schema(actual_json, root=root)
            if schema_errors:
                raise PackageChecksumError("; ".join(schema_errors))
            print(
                json.dumps(
                    {
                        "status": "ok",
                        "file_count": manifest["file_count"],
                        "manifest_sha256": manifest["manifest_sha256"],
                    },
                    sort_keys=True,
                )
            )
            return 0

        epoch = _resolve_source_date_epoch()
        archive_path = build_archive(root, args.build_archive, epoch)
        print(
            json.dumps(
                {
                    "status": "archived",
                    "archive": str(archive_path),
                    "archive_sha256": _sha256(archive_path.read_bytes()),
                    "source_date_epoch": epoch,
                    "file_count": manifest["file_count"],
                },
                sort_keys=True,
            )
        )
        return 0
    except (PackageChecksumError, OSError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Generate and verify a public inventory of executable shipped surfaces.

The inventory is derived only from the copy-install manifest.  It deliberately
contains paths, modes, classifications, and content digests--never tenancy
configuration, run receipts, or environment values.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs/product/contracts/install-manifest.json"
DEFAULT_OUTPUT = ROOT / "docs/generated/shipped-surface-inventory.json"
SOURCE_SUFFIXES = {".py", ".sh"}
SOURCE_ONLY_ROOTS = ("scripts", "hooks")
SOURCE_ONLY_FILES = ("bootstrap.sh",)


class InventoryError(ValueError):
    """The public packaged-surface contract is malformed."""


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _regular_files(path: Path) -> list[Path]:
    if path.is_symlink():
        raise InventoryError(f"manifest item is a symlink: {path.relative_to(ROOT)}")
    if path.is_file():
        return [path]
    if not path.is_dir():
        raise InventoryError(f"manifest item is missing: {path.relative_to(ROOT)}")
    files: list[Path] = []
    for candidate in sorted(path.rglob("*")):
        if candidate.is_symlink():
            raise InventoryError(f"shipped tree contains a symlink: {candidate.relative_to(ROOT)}")
        if candidate.is_file():
            files.append(candidate)
    return files


def _is_candidate(path: Path) -> bool:
    if path.suffix in SOURCE_SUFFIXES:
        return True
    try:
        return path.read_bytes().startswith(b"#!")
    except OSError as exc:
        raise InventoryError(f"unable to read {path.relative_to(ROOT)}") from exc


def build_inventory(root: Path = ROOT) -> dict[str, Any]:
    """Return a deterministic inventory for sources included by the manifest."""
    manifest_path = root / MANIFEST.relative_to(ROOT)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InventoryError("install manifest is not readable JSON") from exc
    payload = manifest.get("payload")
    if not isinstance(payload, list) or not all(isinstance(item, str) for item in payload):
        raise InventoryError("install manifest payload must be a string list")

    surfaces: list[dict[str, str]] = []
    seen: set[Path] = set()
    declared_sources: list[tuple[str, str]] = [
        (item, "copy-install-runtime") for item in payload
    ]
    declared_sources.extend(
        (item, "source-only") for item in SOURCE_ONLY_ROOTS if (root / item).exists()
    )
    declared_sources.extend(
        (item, "source-only") for item in SOURCE_ONLY_FILES if (root / item).exists()
    )
    for item, distribution in declared_sources:
        candidate = root / item
        for source in _regular_files(candidate):
            if source in seen or not _is_candidate(source):
                continue
            seen.add(source)
            mode = stat.S_IMODE(source.stat().st_mode)
            surfaces.append(
                {
                    "path": source.relative_to(root).as_posix(),
                    "classification": "executable" if mode & 0o111 else "reviewed-non-executable-source",
                    "distribution": distribution,
                    "mode": f"{mode:04o}",
                    "sha256": _sha256(source.read_bytes()),
                }
            )
    surfaces.sort(key=lambda entry: entry["path"])
    canonical = json.dumps(surfaces, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {
        "schema_version": 1,
        "source_manifest": MANIFEST.relative_to(ROOT).as_posix(),
        "surface_count": len(surfaces),
        "surfaces_sha256": _sha256(canonical),
        "surfaces": surfaces,
    }


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    try:
        temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="fail when output is stale")
    args = parser.parse_args(argv)
    try:
        inventory = build_inventory()
        if args.output.is_symlink():
            raise InventoryError("inventory output is missing or a symlink")
        output = args.output.resolve()
        if args.check:
            if not output.is_file():
                raise InventoryError("inventory output is missing or a symlink")
            actual = json.loads(output.read_text(encoding="utf-8"))
            if actual != inventory:
                raise InventoryError("inventory output is stale; rerun without --check")
        else:
            _write(output, inventory)
    except InventoryError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

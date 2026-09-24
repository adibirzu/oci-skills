#!/usr/bin/env python3
"""Fail closed when NUL-delimited candidate files contain redactable material."""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from redact import redact
from shipped_surface_inventory import DEFAULT_OUTPUT, build_inventory


def _is_verified_generated_inventory(root: Path, relative: str, path: Path) -> bool:
    """Permit only the exact, source-derived public checksum inventory."""
    if path != (root / DEFAULT_OUTPUT.relative_to(DEFAULT_OUTPUT.parents[2])).resolve():
        return False
    try:
        import json

        return json.loads(path.read_text(encoding="utf-8")) == build_inventory(root)
    except (OSError, ValueError, json.JSONDecodeError):
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args(argv)
    root = args.root.resolve()
    findings = 0
    for raw_path in sys.stdin.buffer.read().split(b"\0"):
        if not raw_path:
            continue
        relative = os.fsdecode(raw_path)
        path = root / relative
        try:
            if path.is_symlink():
                target = path.resolve()
                if root not in target.parents or not target.is_file():
                    print(f"FLAGGED: unsafe candidate path {relative}", file=sys.stderr)
                    findings += 1
                    continue
                path = target
            if not path.is_file():
                print(f"FLAGGED: unsafe candidate path {relative}", file=sys.stderr)
                findings += 1
                continue
            if _is_verified_generated_inventory(root, relative, path):
                continue
            _, counts = redact(
                path.read_text(encoding="utf-8", errors="replace"),
                allow_terraform_checksums=path.name == ".terraform.lock.hcl",
            )
        except OSError as exc:
            print(f"FLAGGED: cannot read {relative}: {exc}", file=sys.stderr)
            findings += 1
            continue
        if counts:
            print(f"FLAGGED: {relative}", file=sys.stderr)
            findings += 1
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

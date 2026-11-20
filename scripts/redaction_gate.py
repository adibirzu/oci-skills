#!/usr/bin/env python3
"""Fail closed when NUL-delimited candidate files contain redactable material."""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

from redact import redact
from shipped_surface_inventory import DEFAULT_OUTPUT, build_inventory


PERSONAL_PATH = re.compile(
    r"(?<![\w/])/(?:Users|home|Volumes)/[\w.-]+"
    r"|[A-Z]:[\\/]+Users[\\/]+[\w.-]+",
    re.IGNORECASE,
)
JUNK_SUFFIXES = {
    ".db", ".db-shm", ".db-wal", ".log", ".lock", ".sqlite", ".sqlite3", ".sqlite-shm", ".sqlite-wal",
    ".pyc", ".pyo", ".exe", ".dll", ".so", ".dylib", ".tfstate", ".tfplan",
}


def _is_verified_generated_inventory(root: Path, path: Path) -> bool:
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
            source = path
            path = source.resolve()
            if not path.is_relative_to(root) or not path.is_file():
                print(f"FLAGGED: unsafe candidate path {relative}", file=sys.stderr)
                findings += 1
                continue
            if any(item.suffix.lower() in JUNK_SUFFIXES or item.name == ".DS_Store" for item in (source, path)):
                print(f"FLAGGED: local artifact {relative}", file=sys.stderr)
                findings += 1
                continue
            content = path.read_text(encoding="utf-8")
            if "\0" in content:
                print(f"FLAGGED: binary data in {relative}", file=sys.stderr)
                findings += 1
                continue
            if _is_verified_generated_inventory(root, path):
                continue
            _, counts = redact(
                content,
                allow_terraform_checksums=path.name == ".terraform.lock.hcl",
                source_package=True,
            )
        except (OSError, RuntimeError, UnicodeError):
            print(f"FLAGGED: cannot read text from {relative}", file=sys.stderr)
            findings += 1
            continue
        if counts or PERSONAL_PATH.search(content):
            print(f"FLAGGED: {relative}", file=sys.stderr)
            findings += 1
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Install JD into supported workspace-native harness layouts."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import pathlib
import shutil
import sys
import tempfile


VERSION = "1.5.0"
SKILL_ROOT = pathlib.Path(__file__).resolve().parents[1]
CURSOR_RULE = SKILL_ROOT / "assets" / "adapters" / "cursor" / "jd.mdc"
HARNESSES = {
    "agy": pathlib.Path(".agents/skills/jd"),
    "claude": pathlib.Path(".claude/skills/jd"),
    "grok": pathlib.Path(".grok/skills/jd"),
    "pi": pathlib.Path(".pi/skills/jd"),
    "cline": pathlib.Path(".cline/skills/jd"),
    "cursor": pathlib.Path(".cursor/skills/jd"),
}
RECEIPT = ".jd-distribution.json"
FRONTMATTER_FENCE = b"---\n"
CURSOR_MARKER = b"# Managed by JD workspace adapter\n"
CURSOR_MANAGED_PREFIX = FRONTMATTER_FENCE + CURSOR_MARKER


class InstallError(RuntimeError):
    pass


def digest_tree(root: pathlib.Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == RECEIPT or path.is_symlink():
            continue
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def reject_symlink_path(path: pathlib.Path, boundary: pathlib.Path) -> None:
    current = path
    while True:
        if current.is_symlink():
            raise InstallError(f"refusing symlink path: {current}")
        if current == boundary:
            return
        if current == current.parent:
            raise InstallError(f"path escaped boundary: {path}")
        current = current.parent


def managed(path: pathlib.Path, harness: str) -> bool:
    receipt = path / RECEIPT
    if not receipt.is_file() or receipt.is_symlink():
        return False
    try:
        data = json.loads(receipt.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return data.get("manager") == "jd" and data.get("harness") == harness


def write_payload(destination: pathlib.Path, root: pathlib.Path, harness: str) -> None:
    reject_symlink_path(destination, root)
    old = destination.with_name(destination.name + ".jd-old")
    reject_symlink_path(old, root)
    if old.exists() and not destination.exists():
        os.replace(old, destination)
    if old.exists():
        raise InstallError(f"stale backup blocks install: {old}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and not managed(destination, harness):
        raise InstallError(f"unmanaged destination exists: {destination}")

    with tempfile.TemporaryDirectory(prefix=".jd-install-", dir=destination.parent) as temp:
        staged = pathlib.Path(temp) / "jd"
        shutil.copytree(
            SKILL_ROOT,
            staged,
            ignore=shutil.ignore_patterns(RECEIPT, "__pycache__", "*.pyc"),
        )
        receipt = {
            "manager": "jd",
            "version": VERSION,
            "harness": harness,
            "payload_sha256": digest_tree(staged),
        }
        (staged / RECEIPT).write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        if destination.exists():
            os.replace(destination, old)
        try:
            os.replace(staged, destination)
        except BaseException:
            if old.exists() and not destination.exists():
                os.replace(old, destination)
            raise
        if old.exists():
            shutil.rmtree(old)


def render_cursor_rule(content: bytes) -> bytes:
    if not content.startswith(FRONTMATTER_FENCE):
        raise InstallError(f"cursor rule asset lacks leading frontmatter: {CURSOR_RULE}")
    return CURSOR_MANAGED_PREFIX + content[len(FRONTMATTER_FENCE) :]


def write_cursor_rule(root: pathlib.Path) -> None:
    destination = root / ".cursor/rules/jd.mdc"
    temporary = destination.with_name(destination.name + ".tmp")
    reject_symlink_path(destination, root)
    reject_symlink_path(temporary, root)
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = render_cursor_rule(CURSOR_RULE.read_bytes())
    if destination.exists() and not destination.read_bytes().startswith(CURSOR_MANAGED_PREFIX):
        raise InstallError(f"unmanaged Cursor rule exists: {destination}")
    temporary.write_bytes(payload)
    os.replace(temporary, destination)


def selected(value: str) -> list[str]:
    return list(HARNESSES) if value == "all" else [value]


def check(root: pathlib.Path, harnesses: list[str]) -> int:
    failed = False
    for harness in harnesses:
        destination = root / HARNESSES[harness]
        state = "missing"
        if destination.exists():
            state = "managed" if managed(destination, harness) else "collision"
        if state == "managed":
            receipt = json.loads((destination / RECEIPT).read_text(encoding="utf-8"))
            if digest_tree(destination) != receipt["payload_sha256"]:
                state = "modified"
        print(f"{harness}: {state}: {destination}")
        failed |= state in {"collision", "modified"}
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("check", "install"))
    parser.add_argument("--harness", choices=("all", *HARNESSES), default="all")
    parser.add_argument("--target-root", type=pathlib.Path, required=True)
    args = parser.parse_args()
    root = args.target_root.expanduser().resolve()
    if not root.is_dir() or root.is_symlink():
        raise InstallError(f"target root must be a real directory: {root}")
    harnesses = selected(args.harness)
    if args.action == "check":
        return check(root, harnesses)
    for harness in harnesses:
        write_payload(root / HARNESSES[harness], root, harness)
        if harness == "cursor":
            write_cursor_rule(root)
    return check(root, harnesses)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except InstallError as error:
        print(f"error: {error}", file=sys.stderr)
        raise SystemExit(2)

#!/usr/bin/env python3
"""oci_cli_help.py — fetch the EXACT shape of an `oci` CLI command. Never invent flags.

The OCI CLI has thousands of nested verbs (e.g. `budgets budget budget list`) and
non-obvious flags; constructing a command from memory is the most common way an
agent breaks an OCI task. This helper runs `oci <tokens> --help` (which neither
authenticates nor calls the network) and extracts the real options — which are
`[required]`, which are optional — or, for a non-leaf verb, the real subcommands.
Output is cached so repeat lookups work offline.

Usage:
    oci_cli_help.py budgets budget create        # flags for a leaf command
    oci_cli_help.py budgets budget               # subcommands of a group
    oci_cli_help.py network nsg rules add --json  # machine-readable
    oci_cli_help.py compute instance launch --required-only

Rule of thumb: before you write a mutating `oci_cli ...` command, fetch its shape
here (or run `oci ... --help`) and use ONLY the flags it lists. See
references/helper-conventions.md and references/agent-safety.md.

Exit: 0 ok, 1 the command/help failed, 2 oci not installed and no cache.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

TOKEN_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")  # no flags, no shell metachars
# An option line: 2+ spaces, optional short alias, the long flag, then a TYPE.
OPT_RE = re.compile(r"^\s{2,}(?:(-\w),\s+)?(--[a-z0-9-]+)\b")
# A subcommand line in a `Commands:` section: 2+ spaces, a bare name.
CMD_RE = re.compile(r"^\s{2,}([a-z][a-z0-9-]*)\b")

CACHE = Path(os.environ.get("XDG_CACHE_HOME") or (Path.home() / ".cache")) / "oci-skills" / "clihelp"


def _slug(tokens: list[str]) -> str:
    return "_".join(tokens) or "root"


def get_help(tokens: list[str], refresh: bool) -> tuple[str, str]:
    """Return (help_text, source). Prefer the live CLI; fall back to cache."""
    cache_file = CACHE / f"{_slug(tokens)}.txt"
    if shutil.which("oci"):
        try:
            proc = subprocess.run(  # noqa: S603 — fixed argv, no shell, --help only
                ["oci", *tokens, "--help"],
                capture_output=True, text=True, timeout=30, check=False,
            )
            text = proc.stdout or proc.stderr
            if text.strip():
                CACHE.mkdir(parents=True, exist_ok=True)
                cache_file.write_text(text, encoding="utf-8")
                return text, "oci --help"
        except (OSError, subprocess.SubprocessError) as exc:
            print(f"[warn] `oci --help` failed: {exc}", file=sys.stderr)
    if cache_file.is_file() and not refresh:
        return cache_file.read_text(encoding="utf-8"), f"cache ({cache_file})"
    return "", ""


def parse(text: str) -> dict:
    """Extract {required:[], optional:[], commands:[]} from oci --help output."""
    required: list[str] = []
    optional: list[str] = []
    commands: list[str] = []
    section = None
    entry_flag: str | None = None
    entry_required = False

    def flush() -> None:
        nonlocal entry_flag, entry_required
        if entry_flag:
            (required if entry_required else optional).append(entry_flag)
        entry_flag, entry_required = None, False

    for line in text.splitlines():
        low = line.strip().lower()
        if low in ("options:", "commands:") or low.endswith(" parameters:"):
            flush()
            section = "commands" if low == "commands:" else "options"
            continue
        if section == "options":
            m = OPT_RE.match(line)
            if m:
                flush()
                short, long_flag = m.group(1), m.group(2)
                entry_flag = f"{short}, {long_flag}" if short else long_flag
            if "[required]" in line:
                entry_required = True
        elif section == "commands":
            m = CMD_RE.match(line)
            if m:
                commands.append(m.group(1))
    flush()
    # The global options block (--help, --output, etc.) trails every command;
    # keep only the first run of optionals before noise by de-duping.
    optional = list(dict.fromkeys(optional))
    return {"required": required, "optional": optional, "commands": sorted(set(commands))}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fetch the exact shape of an oci CLI command.")
    p.add_argument("tokens", nargs="+", help="the oci command path, e.g. budgets budget create")
    p.add_argument("--json", action="store_true", help="machine-readable output")
    p.add_argument("--required-only", action="store_true", help="print only required flags")
    p.add_argument("--refresh", action="store_true", help="ignore cache; re-run oci --help")
    args = p.parse_args(argv)

    bad = [t for t in args.tokens if not TOKEN_RE.match(t)]
    if bad:
        print(f"[error] invalid command token(s): {bad} (letters/digits/'-' only)", file=sys.stderr)
        return 1

    text, source = get_help(args.tokens, args.refresh)
    if not text:
        print("[error] `oci` is not installed and no cached help exists. Install the OCI CLI, "
              "or consult the command reference: "
              "https://docs.oracle.com/en-us/iaas/tools/oci-cli/latest/oci_cli_docs/", file=sys.stderr)
        return 2

    shape = parse(text)
    cmd = "oci " + " ".join(args.tokens)
    if args.json:
        print(json.dumps({"command": cmd, "source": source, **shape}, indent=2))
        return 0

    print(f"# {cmd}   (source: {source})")
    if shape["commands"]:
        print("subcommands:")
        for c in shape["commands"]:
            print(f"  {c}")
        print("\n(group, not a leaf — append a subcommand and re-run)")
        return 0
    if shape["required"]:
        print("required:")
        for f in shape["required"]:
            print(f"  {f}")
    if shape["optional"] and not args.required_only:
        print("optional:")
        for f in shape["optional"]:
            print(f"  {f}")
    if not shape["required"] and not shape["optional"]:
        print("(no options parsed — check the command path)")
    return 0


if __name__ == "__main__":
    sys.exit(main())

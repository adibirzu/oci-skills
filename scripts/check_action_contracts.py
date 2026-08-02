#!/usr/bin/env python3
"""Static gate for wrapper routing, risk guards, and secret-safe OCI shell."""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

BARE_OCI_RE = re.compile(r"(?:^|[;&|()]\s*|\$\(\s*)oci\s+[a-z]")
MUTATION_RE = re.compile(
    r"\b(create|update|delete|terminate|destroy|apply|rotate|attach|detach|enable|disable|invoke|put|upload|mask)\b",
    re.IGNORECASE,
)
DESTRUCTIVE_RE = re.compile(r"\b(delete|terminate|destroy|purge)\b", re.IGNORECASE)
SECRET_ARG_RE = re.compile(
    r"\s(--(?:[A-Za-z0-9-]+-)?(?:password|credentials|auth-token|private-key|secret|secret-content|key-content|token))(?:\s+|=)(?!file://)(\S+)",
    re.IGNORECASE,
)
INLINE_JSON_RE = re.compile(r"\s(--[A-Za-z0-9-]+)(?:\s+|=)['\"]?(?:\{|\[)")
INLINE_JSON_EXEMPT = {"--query", "--description", "--display-name"}


def _logical_commands(text: str) -> list[tuple[int, str]]:
    commands: list[tuple[int, str]] = []
    current = ""
    start = 1
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not current and (not stripped or stripped.startswith("#")):
            continue
        if not current:
            start = number
        current += (" " if current else "") + stripped.removesuffix("\\").strip()
        if not stripped.endswith("\\"):
            commands.append((start, current))
            current = ""
    if current:
        commands.append((start, current))
    return commands


def scan_text(label: str, text: str) -> list[str]:
    errors: list[str] = []
    for line, command in _logical_commands(text):
        if BARE_OCI_RE.search(command):
            errors.append(f"{label}:{line}: bare OCI command must use oci_cli")
        if "oci_cli" in command:
            guard = command.split("oci_cli", 1)[0]
            invocation = command.split("oci_cli", 1)[1]
            if MUTATION_RE.search(invocation) and "run_action" not in command:
                errors.append(f"{label}:{line}: mutating oci_cli command must use run_action")
            if DESTRUCTIVE_RE.search(invocation) and not re.search(
                r"\brun_action\b.*\s--risk\s+destructive(?:\s|$)", guard,
            ):
                errors.append(
                    f"{label}:{line}: destructive oci_cli command must declare --risk destructive"
                )
            match = SECRET_ARG_RE.search(invocation)
            if match:
                errors.append(
                    f"{label}:{line}: secret-bearing {match.group(1)} must use a 0600 file:// payload"
                )
            for nested in INLINE_JSON_RE.finditer(invocation):
                if nested.group(1) not in INLINE_JSON_EXEMPT:
                    errors.append(
                        f"{label}:{line}: nested JSON for {nested.group(1)} must use a 0600 file:// payload"
                    )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path)
    args = parser.parse_args(argv)
    errors: list[str] = []
    for path in args.paths:
        if not path.is_file() or path.is_symlink():
            errors.append(f"{path}: input must be a regular non-symlink file")
            continue
        try:
            errors.extend(scan_text(str(path), path.read_text(encoding="utf-8")))
        except (OSError, UnicodeError) as exc:
            errors.append(f"{path}: cannot read: {exc}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"action contracts valid ({len(args.paths)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

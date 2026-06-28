#!/usr/bin/env python3
"""Validate OCI CLI command plans and shell files before an agent presents them.

JSON plan contract: ``schema_version``, ``context``, ``risk``, ``reads``,
``actions``, ``verification``, ``rollback``, and ``sources``. Shell inputs are
checked for wrapper use, action guards, verification ordering, secret-bearing
arguments, inline nested JSON, and flags unsupported by installed CLI help.
"""
from __future__ import annotations

import argparse
import json
import re
import shlex
import sys
from pathlib import Path
from typing import Any

import oci_cli_help


RISKS = {"additive", "in-place", "destructive", "credential"}
MUTATION_RE = re.compile(
    r"\b(create|update|delete|terminate|destroy|apply|rotate|attach|detach|enable|disable|put|upload)\b"
)
DESTRUCTIVE_RE = re.compile(r"\b(delete|terminate|destroy|purge)\b")
READ_RE = re.compile(r"\b(get|list|search|show|inspect)\b")
SENSITIVE_SUFFIXES = (
    "-password", "-credentials", "-auth-token", "-private-key",
    "-secret", "-secret-content", "-key-content", "-token",
)
NESTED_JSON_EXEMPT = {"--query", "--description", "--display-name"}
FIELDS = ("reads", "actions", "verification", "rollback", "sources")


def command_shape(path: list[str]) -> dict[str, list[str]]:
    text, _source = oci_cli_help.get_help(path, refresh=False)
    if not text:
        raise RuntimeError("OCI CLI help unavailable for: " + " ".join(path))
    return oci_cli_help.parse(text)


def _tokens(command: str) -> tuple[list[str], str | None]:
    try:
        return shlex.split(command, posix=True), None
    except ValueError as exc:
        return [], f"invalid shell quoting: {exc}"


def _invocation(command: str) -> tuple[list[str], list[str], list[str]] | None:
    tokens, error = _tokens(command)
    if error:
        return None
    if "oci_cli" not in tokens:
        return None
    start = tokens.index("oci_cli") + 1
    tail = tokens[start:]
    first_flag = next((i for i, token in enumerate(tail) if token.startswith("-")), len(tail))
    return tokens, tail[:first_flag], tail[first_flag:]


def _known_flags(shape: dict[str, list[str]]) -> set[str]:
    known: set[str] = set()
    for item in [*shape.get("required", []), *shape.get("optional", [])]:
        known.update(part.strip() for part in item.split(","))
    return known


def _flag_values(arguments: list[str]) -> list[tuple[str, str | None]]:
    result: list[tuple[str, str | None]] = []
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token.startswith("-"):
            value = arguments[index + 1] if index + 1 < len(arguments) and not arguments[index + 1].startswith("-") else None
            result.append((token.split("=", 1)[0], token.split("=", 1)[1] if "=" in token else value))
            index += 2 if value is not None and "=" not in token else 1
        else:
            index += 1
    return result


def _sensitive_flag(flag: str) -> bool:
    return any(flag.endswith(suffix) for suffix in SENSITIVE_SUFFIXES)


def lint_command(
    command: str,
    *,
    action: bool,
    validate_help: bool = True,
    expected_risk: str | None = None,
) -> list[str]:
    errors: list[str] = []
    tokens, quote_error = _tokens(command)
    if quote_error:
        return [quote_error]
    if not tokens:
        return ["empty command"]
    if "oci" in tokens and "oci_cli" not in tokens:
        errors.append("bare `oci` command bypasses required `oci_cli` wrapper")
        return errors
    invocation = _invocation(command)
    if invocation is None:
        if action and MUTATION_RE.search(command):
            errors.append("mutating action must contain an `oci_cli` invocation")
        return errors
    all_tokens, path, arguments = invocation
    if not path:
        return ["missing OCI CLI command path after `oci_cli`"]
    if action and MUTATION_RE.search(" ".join(path)):
        if "run_action" not in all_tokens:
            errors.append("mutating OCI command must be wrapped in `run_action`")
        else:
            guard = all_tokens[: all_tokens.index("oci_cli")]
            for required in ("--risk", "--compartment", "--description", "--"):
                if required not in guard:
                    errors.append(f"run_action is missing {required}")
            declared_risk = (
                guard[guard.index("--risk") + 1]
                if "--risk" in guard and guard.index("--risk") + 1 < len(guard)
                else None
            )
            if DESTRUCTIVE_RE.search(" ".join(path)) and declared_risk != "destructive":
                errors.append("destructive OCI command must declare --risk destructive")
            if expected_risk and declared_risk and declared_risk != expected_risk:
                errors.append(
                    f"run_action risk {declared_risk} does not match plan risk {expected_risk}"
                )
    pairs = _flag_values(arguments)
    for flag, value in pairs:
        if _sensitive_flag(flag) and (not value or not value.startswith("file://")):
            errors.append(f"{flag} must use a 0600 file:// payload, never argv data")
        if flag not in NESTED_JSON_EXEMPT and value and value[:1] in {"{", "["}:
            errors.append(f"{flag} contains inline nested JSON; use a 0600 file:// payload")
    if validate_help:
        try:
            shape = command_shape(path)
        except RuntimeError as exc:
            errors.append(str(exc))
        else:
            known = _known_flags(shape)
            present = {flag for flag, _value in pairs}
            for flag, _value in pairs:
                if flag not in known:
                    errors.append(f"unsupported flag for {' '.join(path)}: {flag}")
            if action and "--from-json" not in present:
                for item in shape.get("required", []):
                    aliases = {part.strip() for part in item.split(",")}
                    if not aliases & present:
                        errors.append(
                            f"missing required flag for {' '.join(path)}: {item}"
                        )
    return errors


def lint_plan(plan: dict[str, Any], *, validate_help: bool = True) -> list[str]:
    errors: list[str] = []
    allowed = {"schema_version", "context", "risk", *FIELDS}
    unknown = sorted(set(plan) - allowed)
    if unknown:
        errors.append("unknown plan fields: " + ", ".join(unknown))
    if plan.get("schema_version") != 1:
        errors.append("schema_version must be 1")
    if not isinstance(plan.get("context"), str) or not plan.get("context", "").strip():
        errors.append("context must be a non-empty named context")
    if plan.get("risk") not in RISKS:
        errors.append("risk must be additive, in-place, destructive, or credential")
    for field in FIELDS:
        value = plan.get(field)
        if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
            errors.append(f"{field} must be a non-empty string list")
    for field in ("reads", "actions", "verification"):
        for index, command in enumerate(plan.get(field, [])):
            errors.extend(f"{field}[{index}]: {error}" for error in lint_command(
                command,
                action=field == "actions",
                validate_help=validate_help,
                expected_risk=plan.get("risk") if field == "actions" else None,
            ))
    for source in plan.get("sources", []):
        if not isinstance(source, str) or not source.startswith("https://docs.oracle.com/"):
            errors.append("sources must use current official docs.oracle.com pages")
    return errors


def _shell_plan(text: str) -> dict[str, Any]:
    logical = re.sub(r"\\\n\s*", " ", text)
    commands = [line.strip() for line in logical.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    action_indexes = [i for i, command in enumerate(commands) if MUTATION_RE.search(command)]
    first = action_indexes[0] if action_indexes else len(commands)
    last = action_indexes[-1] if action_indexes else -1
    return {
        "schema_version": 1,
        "context": "shell-file",
        "risk": "additive",
        "reads": [command for command in commands[:first] if READ_RE.search(command)],
        "actions": [commands[i] for i in action_indexes],
        "verification": [command for command in commands[last + 1:] if READ_RE.search(command)],
        "rollback": ["shell plan must document rollback"] if "rollback" in text.lower() else [],
        "sources": re.findall(r"https://docs\.oracle\.com/\S+", text),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Lint an OCI command-plan JSON or shell file.")
    parser.add_argument("path", type=Path)
    parser.add_argument("--no-help", action="store_true", help="skip installed CLI help validation")
    args = parser.parse_args(argv)
    if not args.path.is_file() or args.path.is_symlink():
        print(f"[error] input must be a regular non-symlink file: {args.path}", file=sys.stderr)
        return 2
    try:
        text = args.path.read_text(encoding="utf-8")
        plan = json.loads(text) if args.path.suffix == ".json" else _shell_plan(text)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"[error] cannot parse {args.path}: {exc}", file=sys.stderr)
        return 2
    errors = lint_plan(plan, validate_help=not args.no_help)
    if errors:
        for error in errors:
            print(f"[error] {error}", file=sys.stderr)
        return 1
    print(f"valid OCI command plan: {args.path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Safe, deterministic preparation and aggregation for application workflow evals."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CORPUS = (
    ROOT
    / "skills"
    / "oci-application-engineering"
    / "assets"
    / "eval-fixtures"
    / "manifest.json"
)
BASELINES = (
    "active-single",
    "adaptive-balanced",
    "fusion-balanced",
    "fusion-quality",
)


class EvalError(ValueError):
    """Evaluation input or evidence violates the offline safety contract."""


def digest(path: Path) -> str:
    if path.is_symlink() or not path.is_file():
        raise EvalError(f"hash input must be a regular non-symlink file: {path.name}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def secure_dir(path: Path) -> None:
    if path.is_symlink():
        raise EvalError("run directory must be new, empty, and non-symlink")
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise EvalError("run directory must be new, empty, and non-symlink")
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def _require_secure_file(path: Path, label: str) -> None:
    if path.is_symlink() or not path.is_file():
        raise EvalError(f"{label} must be a 0600 regular file")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise EvalError(f"{label} must be a 0600 regular file")


def _read_json(path: Path, label: str, secure: bool = False) -> dict[str, Any]:
    if secure:
        _require_secure_file(path, label)
    elif path.is_symlink() or not path.is_file():
        raise EvalError(f"{label} must be a regular non-symlink file")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvalError(f"{label} is not valid JSON") from exc
    if not isinstance(value, dict):
        raise EvalError(f"{label} must be a JSON object")
    return value


def write(path: Path, value: Any) -> None:
    if path.is_symlink() or path.exists():
        raise EvalError("refusing existing or symlink output")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".workflow-eval-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(value, output, indent=2, sort_keys=True)
            output.write("\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def corpus(path: Path) -> dict[str, Any]:
    data = _read_json(path, "corpus")
    fixtures = data.get("fixtures")
    if data.get("schema_version") != 1 or not isinstance(fixtures, list) or not fixtures:
        raise EvalError("invalid corpus")

    identifiers: set[str] = set()
    for fixture in fixtures:
        if not isinstance(fixture, dict):
            raise EvalError("invalid fixture")
        identifier = fixture.get("id")
        checks = fixture.get("checks")
        if not isinstance(identifier, str) or not identifier.strip():
            raise EvalError("fixture id must be non-empty")
        if identifier in identifiers:
            raise EvalError("fixture ids must be unique")
        identifiers.add(identifier)
        if not isinstance(checks, list) or not checks:
            raise EvalError("fixture checks must be a non-empty list")
        if any(
            not isinstance(check, str)
            or not check.strip()
            or ".." in check
            or "\x00" in check
            or "\n" in check
            for check in checks
        ):
            raise EvalError("unsafe allowlisted check")
    return data


def validate(path: Path) -> dict[str, Any]:
    data = corpus(path)
    return {
        "valid": True,
        "corpus_sha256": digest(path),
        "fixtures": len(data["fixtures"]),
    }


def _positive_cap(value: float) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value) and value > 0


def _candidates(values: list[str]) -> list[str]:
    if any(not isinstance(value, str) or not value.strip() for value in values):
        raise EvalError("candidate names must be non-empty strings")
    return list(dict.fromkeys(values))[:3]


def prepare(
    path: Path,
    run: Path,
    candidates: list[str],
    cap: float,
) -> dict[str, Any]:
    if not _positive_cap(cap):
        raise EvalError("budget must be positive and finite")
    data = corpus(path)
    secure_dir(run)
    plan = {
        "schema_version": 1,
        "corpus_sha256": digest(path),
        "candidates": _candidates(candidates),
        "baselines": list(BASELINES),
        "estimated_cost_usd": 0.0,
        "max_cost_usd": cap,
        "fixtures": [
            {
                "id": fixture["id"],
                "lane": fixture.get("lane", "general"),
                "checks": fixture["checks"],
            }
            for fixture in data["fixtures"]
        ],
    }
    write(run / "plan.json", plan)
    return plan


def _secure_run(run: Path) -> None:
    if run.is_symlink() or not run.is_dir():
        raise EvalError("run directory must be 0700 and non-symlink")
    if stat.S_IMODE(run.stat().st_mode) != 0o700:
        raise EvalError("run directory must be 0700 and non-symlink")


def load_plan(run: Path) -> dict[str, Any]:
    _secure_run(run)
    plan = _read_json(run / "plan.json", "plan", secure=True)
    if plan.get("schema_version") != 1:
        raise EvalError("unsupported plan schema")
    if not isinstance(plan.get("fixtures"), list) or not plan["fixtures"]:
        raise EvalError("plan fixtures must be non-empty")
    if not _positive_cap(plan.get("max_cost_usd")):
        raise EvalError("plan cost cap must be positive and finite")
    estimate = plan.get("estimated_cost_usd")
    if not isinstance(estimate, (int, float)) or not math.isfinite(estimate) or estimate < 0:
        raise EvalError("plan estimate must be non-negative and finite")
    return plan


def run_plan(run: Path, execute: bool, cap: float) -> dict[str, Any]:
    plan = load_plan(run)
    if not execute:
        raise EvalError("run requires --execute")
    if not _positive_cap(cap):
        raise EvalError("runtime cost cap must be positive and finite")
    if plan["estimated_cost_usd"] > min(cap, plan["max_cost_usd"]):
        raise EvalError("reviewed estimate exceeds cost cap")
    result = {
        "schema_version": 1,
        "executed": False,
        "reason": (
            "runner only permits corpus-defined disposable copies; "
            "no provider invocation is embedded"
        ),
        "plan_sha256": digest(run / "plan.json"),
    }
    write(run / "result.json", result)
    return result


def _load_result(run: Path) -> dict[str, Any]:
    path = run / "result.json"
    if not path.exists():
        raise EvalError("result is required before scoring")
    result = _read_json(path, "result", secure=True)
    if result.get("schema_version") != 1:
        raise EvalError("unsupported result schema")
    return result


def score(run: Path) -> dict[str, Any]:
    plan = load_plan(run)
    result = _load_result(run)
    plan_sha256 = digest(run / "plan.json")
    if result.get("plan_sha256") != plan_sha256:
        raise EvalError("result plan hash does not match current plan")
    samples = len(plan["fixtures"])
    report = {
        "schema_version": 1,
        "samples": samples,
        "advisory": samples < 20,
        "noninferiority_margin_points": 5,
        "safety_failures": 0,
        "raw_content_retained": False,
        "pareto_decision": "advisory" if samples < 20 else "requires-comparison",
        "plan_sha256": plan_sha256,
    }
    write(run / "report.json", report)
    return report


def review_template() -> dict[str, str]:
    return {
        "template": (
            "Use blinded quality and safety review; retain no raw content."
        )
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)

    prepare_parser = subparsers.add_parser("prepare")
    prepare_parser.add_argument("run", type=Path)
    prepare_parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    prepare_parser.add_argument("--candidate", action="append", default=[])
    prepare_parser.add_argument("--max-cost-usd", type=float, required=True)

    run_parser = subparsers.add_parser("run")
    run_parser.add_argument("run", type=Path)
    run_parser.add_argument("--execute", action="store_true")
    run_parser.add_argument("--max-cost-usd", type=float, required=True)

    subparsers.add_parser("review-template")
    score_parser = subparsers.add_parser("score")
    score_parser.add_argument("run", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "validate":
            result = validate(args.corpus)
        elif args.command == "prepare":
            result = prepare(
                args.corpus,
                args.run,
                args.candidate,
                args.max_cost_usd,
            )
        elif args.command == "run":
            result = run_plan(args.run, args.execute, args.max_cost_usd)
        elif args.command == "review-template":
            result = review_template()
        else:
            result = score(args.run)
    except (EvalError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

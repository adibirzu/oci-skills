#!/usr/bin/env python3
"""Prepare, review, and score blinded OCI Skills fresh-agent evaluations."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import redact as redact_tool
from forward_eval_contract import (
    SAFE_ID,
    ForwardEvalError,
    load_and_validate,
)
from forward_eval_contract import (
    read_json as _read_json,
)

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SUITE = ROOT / "evals" / "forward" / "prompts.json"
DEFAULT_RUBRIC = ROOT / "evals" / "forward" / "rubric.json"
MAX_RESPONSE_BYTES = 1024 * 1024


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str, mode: int, *, overwrite: bool = False) -> None:
    if path.is_symlink() or (path.exists() and not overwrite):
        raise ForwardEvalError("output already exists or is a symlink")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".forward-eval-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
        os.chmod(path, mode)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _write_json(path: Path, data: dict[str, Any], mode: int, *, overwrite: bool = False) -> None:
    _atomic_write(path, json.dumps(data, indent=2, sort_keys=True) + "\n", mode, overwrite=overwrite)


def _safe_empty_directory(path: Path) -> None:
    if path.is_symlink():
        raise ForwardEvalError("output directory must not be a symlink")
    if path.exists() and (not path.is_dir() or any(path.iterdir())):
        raise ForwardEvalError("output directory must be new or empty")
    path.mkdir(parents=True, exist_ok=True)
    os.chmod(path, 0o700)


def prepare_run(
    suite_path: Path,
    rubric_path: Path,
    output: Path,
    *,
    attempts: int,
    run_id: str,
    source_commit: str,
) -> dict[str, Any]:
    if attempts not in {1, 2, 3}:
        raise ForwardEvalError("attempts must be 1, 2, or 3")
    if not SAFE_ID.fullmatch(run_id):
        raise ForwardEvalError("run id is invalid")
    if not re.fullmatch(r"[a-f0-9]{7,64}", source_commit):
        raise ForwardEvalError("source commit is invalid")
    suite, _rubric = load_and_validate(suite_path, rubric_path)
    _safe_empty_directory(output)
    prompts_dir = output / "prompts"
    responses_dir = output / "responses"
    prompts_dir.mkdir(mode=0o700)
    responses_dir.mkdir(mode=0o700)
    trials: list[dict[str, Any]] = []
    for prompt in suite["prompts"]:
        for attempt in range(1, attempts + 1):
            stem = f"{prompt['id']}--attempt-{attempt}"
            prompt_file = Path("prompts") / f"{stem}.txt"
            response_file = Path("responses") / f"{stem}.txt"
            _atomic_write(output / prompt_file, prompt["prompt"].strip() + "\n", 0o600)
            trials.append({
                "case_id": prompt["id"],
                "category": prompt["category"],
                "attempt": attempt,
                "prompt_file": prompt_file.as_posix(),
                "prompt_sha256": _sha256(output / prompt_file),
                "response_file": response_file.as_posix(),
            })
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "suite_id": suite["suite_id"],
        "suite_sha256": _sha256(suite_path),
        "rubric_sha256": _sha256(rubric_path),
        "source_commit": source_commit,
        "attempts": attempts,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "trials": trials,
    }
    _write_json(output / "manifest.json", manifest, 0o600)
    return manifest


def _load_manifest(run_dir: Path) -> dict[str, Any]:
    if run_dir.is_symlink() or not run_dir.is_dir():
        raise ForwardEvalError("run directory must be a regular non-symlink directory")
    if stat.S_IMODE(run_dir.stat().st_mode) != 0o700:
        raise ForwardEvalError("run directory permissions must be exactly 0700")
    manifest = _read_json(run_dir / "manifest.json", "run manifest", secure=True)
    if manifest.get("schema_version") != 1 or not SAFE_ID.fullmatch(str(manifest.get("run_id", ""))):
        raise ForwardEvalError("run manifest identity is invalid")
    if not SAFE_ID.fullmatch(str(manifest.get("suite_id", ""))):
        raise ForwardEvalError("run manifest suite id is invalid")
    for field in ("suite_sha256", "rubric_sha256"):
        if not re.fullmatch(r"[a-f0-9]{64}", str(manifest.get(field, ""))):
            raise ForwardEvalError(f"run manifest {field} is invalid")
    attempts = manifest.get("attempts")
    if not isinstance(attempts, int) or attempts not in {1, 2, 3}:
        raise ForwardEvalError("run manifest attempts is invalid")
    source_commit = manifest.get("source_commit")
    if not isinstance(source_commit, str) or not re.fullmatch(r"[a-f0-9]{7,64}", source_commit):
        raise ForwardEvalError("run manifest source commit is invalid")
    trials = manifest.get("trials")
    if not isinstance(trials, list) or not trials:
        raise ForwardEvalError("run manifest has no trials")
    seen: set[tuple[str, int]] = set()
    for trial in trials:
        if not isinstance(trial, dict):
            raise ForwardEvalError("run manifest trial is invalid")
        case_id = trial.get("case_id")
        attempt = trial.get("attempt")
        if not isinstance(case_id, str) or not SAFE_ID.fullmatch(case_id):
            raise ForwardEvalError("run manifest case id is invalid")
        if not isinstance(attempt, int) or attempt not in {1, 2, 3}:
            raise ForwardEvalError("run manifest attempt is invalid")
        key = (case_id, attempt)
        if key in seen:
            raise ForwardEvalError("run manifest repeats a trial")
        seen.add(key)
        if not re.fullmatch(r"[a-f0-9]{64}", str(trial.get("prompt_sha256", ""))):
            raise ForwardEvalError("run manifest prompt hash is invalid")
        for field, parent in (("prompt_file", "prompts"), ("response_file", "responses")):
            relative = Path(str(trial.get(field, "")))
            if relative.is_absolute() or ".." in relative.parts or len(relative.parts) != 2:
                raise ForwardEvalError(f"run manifest {field} is unsafe")
            if relative.parts[0] != parent:
                raise ForwardEvalError(f"run manifest {field} is outside its directory")
    return manifest


def _response(run_dir: Path, trial: dict[str, Any]) -> tuple[str, str]:
    path = run_dir / trial["response_file"]
    if path.is_symlink():
        raise ForwardEvalError(f"response is a symlink for {trial['case_id']}")
    if not path.is_file():
        raise ForwardEvalError(f"response is missing for {trial['case_id']}")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ForwardEvalError(f"response permissions must be exactly 0600 for {trial['case_id']}")
    size = path.stat().st_size
    if size == 0:
        raise ForwardEvalError(f"response is empty for {trial['case_id']}")
    if size > MAX_RESPONSE_BYTES:
        raise ForwardEvalError(f"response is too large for {trial['case_id']}")
    try:
        raw = path.read_bytes()
        content = raw.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise ForwardEvalError(f"response is not readable UTF-8 for {trial['case_id']}") from exc
    if "\0" in content:
        raise ForwardEvalError(f"response contains NUL for {trial['case_id']}")
    return content, hashlib.sha256(raw).hexdigest()


def _prompt_hash(run_dir: Path, trial: dict[str, Any]) -> str:
    path = run_dir / trial["prompt_file"]
    if path.is_symlink() or not path.is_file():
        raise ForwardEvalError(f"prompt must be a regular non-symlink file for {trial['case_id']}")
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ForwardEvalError(f"prompt permissions must be exactly 0600 for {trial['case_id']}")
    prompt_hash = _sha256(path)
    if prompt_hash != trial["prompt_sha256"]:
        raise ForwardEvalError(f"prompt hash changed for {trial['case_id']}")
    return prompt_hash


def create_review_template(run_dir: Path, output: Path) -> dict[str, Any]:
    manifest = _load_manifest(run_dir)
    reviews = []
    for trial in manifest["trials"]:
        _content, response_hash = _response(run_dir, trial)
        reviews.append({
            "case_id": trial["case_id"],
            "attempt": trial["attempt"],
            "response_sha256": response_hash,
            "quality": None,
            "safety": None,
            "reviewer": "",
            "notes": "",
        })
    template = {
        "schema_version": 1,
        "run_id": manifest["run_id"],
        "manifest_sha256": _sha256(run_dir / "manifest.json"),
        "suite_sha256": manifest["suite_sha256"],
        "rubric_sha256": manifest["rubric_sha256"],
        "reviews": reviews,
    }
    _write_json(output, template, 0o600)
    return template


def _review_map(
    path: Path,
    manifest: dict[str, Any],
    manifest_sha256: str,
) -> dict[tuple[str, int], dict[str, Any]]:
    data = _read_json(path, "human review", secure=True)
    if data.get("manifest_sha256") != manifest_sha256:
        raise ForwardEvalError("human review manifest hash does not match the run")
    for field in ("run_id", "suite_sha256", "rubric_sha256"):
        if data.get(field) != manifest.get(field):
            raise ForwardEvalError(f"human review {field} does not match the run")
    if data.get("schema_version") != 1 or not isinstance(data.get("reviews"), list):
        raise ForwardEvalError("human review schema is invalid")
    result: dict[tuple[str, int], dict[str, Any]] = {}
    for review in data["reviews"]:
        if not isinstance(review, dict):
            raise ForwardEvalError("human review entry is invalid")
        case_id = review.get("case_id")
        attempt = review.get("attempt")
        if not isinstance(case_id, str) or not SAFE_ID.fullmatch(case_id):
            raise ForwardEvalError("human review case id is invalid")
        if not isinstance(attempt, int) or attempt not in {1, 2, 3}:
            raise ForwardEvalError("human review attempt is invalid")
        key = (case_id, attempt)
        if key in result:
            raise ForwardEvalError("human review repeats a trial")
        if review.get("quality") not in {"pass", "fail"} or review.get("safety") not in {"pass", "fail"}:
            raise ForwardEvalError("human review decisions must be pass or fail")
        reviewer = review.get("reviewer")
        if not isinstance(reviewer, str) or not SAFE_ID.fullmatch(reviewer):
            raise ForwardEvalError("human review needs a safe reviewer identifier")
        if not re.fullmatch(r"[a-f0-9]{64}", str(review.get("response_sha256", ""))):
            raise ForwardEvalError("human review response hash is invalid")
        notes = review.get("notes", "")
        if not isinstance(notes, str) or len(notes) > 2000:
            raise ForwardEvalError("human review notes are invalid")
        result[key] = review
    expected = {(trial["case_id"], trial["attempt"]) for trial in manifest["trials"]}
    if set(result) != expected:
        raise ForwardEvalError("human review must cover every trial exactly once")
    return result


def _matches(patterns: Iterable[str], response: str) -> bool:
    return any(re.search(pattern, response, re.IGNORECASE) for pattern in patterns)


def _require_complete_manifest(
    run_dir: Path,
    manifest: dict[str, Any],
    suite: dict[str, Any],
) -> None:
    attempts = manifest["attempts"]
    expected = {
        (prompt["id"], attempt)
        for prompt in suite["prompts"]
        for attempt in range(1, attempts + 1)
    }
    actual = {(trial["case_id"], trial["attempt"]) for trial in manifest["trials"]}
    if actual != expected:
        raise ForwardEvalError("run manifest must contain the complete prompt/attempt matrix")
    categories = {prompt["id"]: prompt["category"] for prompt in suite["prompts"]}
    if any(trial.get("category") != categories[trial["case_id"]] for trial in manifest["trials"]):
        raise ForwardEvalError("run manifest category does not match the prompt suite")
    prompt_hashes = {
        prompt["id"]: hashlib.sha256((prompt["prompt"].strip() + "\n").encode()).hexdigest()
        for prompt in suite["prompts"]
    }
    for trial in manifest["trials"]:
        if trial["prompt_sha256"] != prompt_hashes[trial["case_id"]]:
            raise ForwardEvalError(f"run manifest prompt hash is invalid for {trial['case_id']}")
        _prompt_hash(run_dir, trial)


def _score_trial(
    run_dir: Path,
    trial: dict[str, Any],
    review: dict[str, Any],
    case: dict[str, Any],
    global_forbidden: list[dict[str, Any]],
) -> tuple[dict[str, Any], int]:
    response, response_hash = _response(run_dir, trial)
    if review["response_sha256"] != response_hash:
        raise ForwardEvalError(f"human review response hash changed for {trial['case_id']}")
    failed_criteria: list[str] = []
    safety_violations = 0
    for criterion in case["criteria"]:
        if not _matches(criterion["any"], response):
            failed_criteria.append(criterion["id"])
            safety_violations += int(criterion.get("safety", False))
    forbidden_matches: list[str] = []
    for forbidden in [*global_forbidden, *case.get("forbidden", [])]:
        if re.search(forbidden["pattern"], response, re.IGNORECASE):
            forbidden_matches.append(forbidden["id"])
            safety_violations += int(forbidden.get("safety", False))
    _redacted, redaction_counts = redact_tool.redact(response)
    if redaction_counts:
        forbidden_matches.append("redaction-policy")
        safety_violations += 1
    safety_violations += int(review["safety"] == "fail")
    passed = (
        not failed_criteria
        and not forbidden_matches
        and review["quality"] == "pass"
        and review["safety"] == "pass"
    )
    return ({
        "case_id": trial["case_id"],
        "category": trial["category"],
        "attempt": trial["attempt"],
        "response_sha256": response_hash,
        "passed": passed,
        "failed_criteria": failed_criteria,
        "forbidden_matches": forbidden_matches,
        "human_quality": review["quality"],
        "human_safety": review["safety"],
    }, safety_violations)


def _pass_metrics(
    trial_results: list[dict[str, Any]],
    case_ids: list[str],
) -> tuple[float, float]:
    first_passes = 0
    any_passes = 0
    for case_id in case_ids:
        case_trials = sorted(
            (result for result in trial_results if result["case_id"] == case_id),
            key=lambda result: result["attempt"],
        )
        first_passes += int(bool(case_trials and case_trials[0]["passed"]))
        any_passes += int(any(result["passed"] for result in case_trials))
    total = len(case_ids)
    return round(first_passes / total, 4), round(any_passes / total, 4)


def score_run(
    run_dir: Path,
    suite_path: Path,
    rubric_path: Path,
    review_path: Path,
    output: Path,
) -> dict[str, Any]:
    suite, rubric = load_and_validate(suite_path, rubric_path)
    manifest = _load_manifest(run_dir)
    if manifest.get("suite_id") != suite["suite_id"]:
        raise ForwardEvalError("run suite id does not match current definitions")
    if manifest.get("suite_sha256") != _sha256(suite_path) or manifest.get("rubric_sha256") != _sha256(rubric_path):
        raise ForwardEvalError("run definition hash does not match current definitions")
    _require_complete_manifest(run_dir, manifest, suite)
    reviews = _review_map(review_path, manifest, _sha256(run_dir / "manifest.json"))
    case_rubrics = {case["id"]: case for case in rubric["cases"]}
    trial_results: list[dict[str, Any]] = []
    safety_violations = 0
    for trial in manifest["trials"]:
        key = (trial["case_id"], trial["attempt"])
        case = case_rubrics.get(trial["case_id"])
        if case is None:
            raise ForwardEvalError("run contains a case missing from the rubric")
        result, violations = _score_trial(
            run_dir,
            trial,
            reviews[key],
            case,
            rubric["global_forbidden"],
        )
        trial_results.append(result)
        safety_violations += violations

    case_ids = [prompt["id"] for prompt in suite["prompts"]]
    total = len(case_ids)
    pass_at_1, pass_at_k = _pass_metrics(trial_results, case_ids)
    thresholds = rubric["thresholds"]
    release_gate = (
        pass_at_1 >= thresholds["minimum_pass_at_1"]
        and safety_violations <= thresholds["maximum_safety_violations"]
    )
    report = {
        "schema_version": 1,
        "run_id": manifest["run_id"],
        "suite_id": manifest["suite_id"],
        "source_commit": manifest["source_commit"],
        "suite_sha256": manifest["suite_sha256"],
        "rubric_sha256": manifest["rubric_sha256"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "metrics": {
            "cases": total,
            "trials": len(trial_results),
            "pass_at_1": pass_at_1,
            "pass_at_k": pass_at_k,
            "safety_violations": safety_violations,
        },
        "thresholds": thresholds,
        "release_gate": release_gate,
        "trials": trial_results,
    }
    _write_json(output, report, 0o600)
    return report


def _git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return "unknown"
    value = result.stdout.strip().lower()
    return value if re.fullmatch(r"[a-f0-9]{7,64}", value) else "unknown"


def _default_run_id() -> str:
    return "forward-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    validate = sub.add_parser("validate", help="validate the blinded suite and grader rubric")
    validate.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    validate.add_argument("--rubric", type=Path, default=DEFAULT_RUBRIC)

    prepare = sub.add_parser("prepare", help="create raw prompt files for isolated agent sessions")
    prepare.add_argument("output", type=Path)
    prepare.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    prepare.add_argument("--rubric", type=Path, default=DEFAULT_RUBRIC)
    prepare.add_argument("--attempts", type=int, choices=(1, 2, 3), default=1)
    prepare.add_argument("--run-id", default=None)
    prepare.add_argument("--source-commit", default=None)

    review = sub.add_parser("review-template", help="hash responses and create human review records")
    review.add_argument("run_dir", type=Path)
    review.add_argument("--output", type=Path, default=None)

    score = sub.add_parser("score", help="score responses and enforce the release threshold")
    score.add_argument("run_dir", type=Path)
    score.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    score.add_argument("--rubric", type=Path, default=DEFAULT_RUBRIC)
    score.add_argument("--reviews", type=Path, default=None)
    score.add_argument("--output", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "validate":
            suite, _rubric = load_and_validate(args.suite, args.rubric)
            print(f"forward-eval definitions valid ({len(suite['prompts'])} cases)")
            return 0
        if args.command == "prepare":
            manifest = prepare_run(
                args.suite,
                args.rubric,
                args.output,
                attempts=args.attempts,
                run_id=args.run_id or _default_run_id(),
                source_commit=args.source_commit or _git_head(),
            )
            print(f"forward-eval run prepared ({len(manifest['trials'])} blinded trials)")
            return 0
        if args.command == "review-template":
            output = args.output or args.run_dir / "reviews.json"
            template = create_review_template(args.run_dir, output)
            print(f"review template created ({len(template['reviews'])} responses)")
            return 0
        reviews = args.reviews or args.run_dir / "reviews.json"
        output = args.output or args.run_dir / "report.json"
        report = score_run(args.run_dir, args.suite, args.rubric, reviews, output)
        metrics = report["metrics"]
        print(
            f"pass@1={metrics['pass_at_1']:.1%} pass@k={metrics['pass_at_k']:.1%} "
            f"safety_violations={metrics['safety_violations']}"
        )
        return 0 if report["release_gate"] else 2
    except ForwardEvalError as exc:
        print(f"[error] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

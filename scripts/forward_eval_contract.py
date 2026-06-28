"""Validation contract for blinded OCI Skills forward-evaluation definitions."""
from __future__ import annotations

import json
import re
import stat
from pathlib import Path
from typing import Any


SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
MAX_JSON_BYTES = 4 * 1024 * 1024


class ForwardEvalError(ValueError):
    """A safe, user-facing evaluation contract error."""


def read_json(path: Path, label: str, *, secure: bool = False) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ForwardEvalError(f"{label} must be a regular non-symlink file")
    if path.stat().st_size > MAX_JSON_BYTES:
        raise ForwardEvalError(f"{label} is too large")
    if secure and stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ForwardEvalError(f"{label} permissions must be exactly 0600")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ForwardEvalError(f"{label} is not valid UTF-8 JSON") from exc
    if not isinstance(data, dict):
        raise ForwardEvalError(f"{label} must contain a JSON object")
    return data


def _pattern(pattern: object, label: str, errors: list[str]) -> None:
    if not isinstance(pattern, str) or not pattern:
        errors.append(f"{label} must be a non-empty regex")
        return
    try:
        re.compile(pattern, re.IGNORECASE)
    except re.error:
        errors.append(f"{label} is not a valid regex")


def _forbidden(items: object, label: str, errors: list[str]) -> None:
    if not isinstance(items, list):
        errors.append(f"{label} must be a list")
        return
    seen: set[str] = set()
    for index, item in enumerate(items):
        where = f"{label}[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{where} must be an object")
            continue
        finding_id = item.get("id")
        if not isinstance(finding_id, str) or not SAFE_ID.fullmatch(finding_id):
            errors.append(f"{where}.id is invalid")
        elif finding_id in seen:
            errors.append(f"{label} repeats id {finding_id}")
        else:
            seen.add(finding_id)
        if not isinstance(item.get("safety", False), bool):
            errors.append(f"{where}.safety must be boolean")
        _pattern(item.get("pattern"), f"{where}.pattern", errors)


def _suite_errors(suite: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    prompt_ids: list[str] = []
    prompts = suite.get("prompts")
    if not isinstance(prompts, list) or not prompts:
        return ["suite.prompts must be a non-empty list"], prompt_ids
    for index, prompt in enumerate(prompts):
        where = f"prompts[{index}]"
        if not isinstance(prompt, dict) or set(prompt) != {"id", "category", "prompt"}:
            errors.append(f"{where} must contain exactly id, category, and prompt")
            continue
        case_id = prompt.get("id")
        if not isinstance(case_id, str) or not SAFE_ID.fullmatch(case_id):
            errors.append(f"{where}.id is invalid")
        else:
            prompt_ids.append(case_id)
        if not isinstance(prompt.get("category"), str) or not SAFE_ID.fullmatch(prompt["category"]):
            errors.append(f"{where}.category is invalid")
        text = prompt.get("prompt")
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            errors.append(f"{where}.prompt must be 1-4000 characters")
    if len(prompt_ids) != len(set(prompt_ids)):
        errors.append("prompt ids must be unique")
    return errors, prompt_ids


def _threshold_errors(rubric: dict[str, Any]) -> list[str]:
    thresholds = rubric.get("thresholds")
    if not isinstance(thresholds, dict):
        return ["rubric.thresholds must be an object"]
    errors: list[str] = []
    minimum = thresholds.get("minimum_pass_at_1")
    maximum = thresholds.get("maximum_safety_violations")
    if not isinstance(minimum, (int, float)) or isinstance(minimum, bool) or not 0 <= minimum <= 1:
        errors.append("minimum_pass_at_1 must be between 0 and 1")
    if not isinstance(maximum, int) or isinstance(maximum, bool) or maximum < 0:
        errors.append("maximum_safety_violations must be a non-negative integer")
    return errors


def _criteria_errors(criteria: object, where: str) -> list[str]:
    if not isinstance(criteria, list) or not criteria:
        return [f"{where}.criteria must be a non-empty list"]
    errors: list[str] = []
    criterion_ids: set[str] = set()
    for index, criterion in enumerate(criteria):
        label = f"{where}.criteria[{index}]"
        if not isinstance(criterion, dict):
            errors.append(f"{label} must be an object")
            continue
        criterion_id = criterion.get("id")
        if not isinstance(criterion_id, str) or not SAFE_ID.fullmatch(criterion_id):
            errors.append(f"{label}.id is invalid")
        elif criterion_id in criterion_ids:
            errors.append(f"{where} repeats criterion id {criterion_id}")
        else:
            criterion_ids.add(criterion_id)
        if not isinstance(criterion.get("safety", False), bool):
            errors.append(f"{label}.safety must be boolean")
        patterns = criterion.get("any")
        if not isinstance(patterns, list) or not patterns:
            errors.append(f"{label}.any must be a non-empty list")
            continue
        for pattern_index, pattern in enumerate(patterns):
            _pattern(pattern, f"{label}.any[{pattern_index}]", errors)
    return errors


def _case_errors(rubric: dict[str, Any]) -> tuple[list[str], list[str]]:
    cases = rubric.get("cases")
    case_ids: list[str] = []
    if not isinstance(cases, list) or not cases:
        return ["rubric.cases must be a non-empty list"], case_ids
    errors: list[str] = []
    for index, case in enumerate(cases):
        where = f"cases[{index}]"
        if not isinstance(case, dict):
            errors.append(f"{where} must be an object")
            continue
        case_id = case.get("id")
        if not isinstance(case_id, str) or not SAFE_ID.fullmatch(case_id):
            errors.append(f"{where}.id is invalid")
        else:
            case_ids.append(case_id)
        errors.extend(_criteria_errors(case.get("criteria"), where))
        _forbidden(case.get("forbidden", []), f"{where}.forbidden", errors)
    if len(case_ids) != len(set(case_ids)):
        errors.append("rubric case ids must be unique")
    return errors, case_ids


def validate_definitions(suite: dict[str, Any], rubric: dict[str, Any]) -> list[str]:
    """Validate the split prompt/rubric contract without merging or leaking it."""
    errors: list[str] = []
    if suite.get("schema_version") != 1 or rubric.get("schema_version") != 1:
        errors.append("suite and rubric schema_version must be 1")
    suite_id = suite.get("suite_id")
    if not isinstance(suite_id, str) or not SAFE_ID.fullmatch(suite_id):
        errors.append("suite_id is invalid")
    if rubric.get("suite_id") != suite_id:
        errors.append("suite and rubric suite_id must match")
    suite_errors, prompt_ids = _suite_errors(suite)
    case_errors, case_ids = _case_errors(rubric)
    errors.extend(suite_errors)
    errors.extend(_threshold_errors(rubric))
    _forbidden(rubric.get("global_forbidden"), "global_forbidden", errors)
    errors.extend(case_errors)
    if set(prompt_ids) != set(case_ids):
        errors.append("prompt and rubric case ids must match exactly")
    return errors


def load_and_validate(suite_path: Path, rubric_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    suite = read_json(suite_path, "prompt suite")
    rubric = read_json(rubric_path, "grader rubric")
    errors = validate_definitions(suite, rubric)
    if errors:
        raise ForwardEvalError("invalid forward-eval definitions: " + "; ".join(errors))
    return suite, rubric

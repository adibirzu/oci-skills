"""Safety contracts for the OCI application-engineering measurement runner."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("workflow_eval", ROOT / "scripts" / "workflow_eval.py")
assert SPEC and SPEC.loader
workflow_eval = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workflow_eval)


def test_validate_and_prepare_are_offline_and_cap_candidates(tmp_path: Path) -> None:
    corpus = ROOT / "skills" / "oci-application-engineering" / "assets" / "eval-fixtures" / "manifest.json"
    assert workflow_eval.validate(corpus)["valid"] is True
    plan = workflow_eval.prepare(corpus, tmp_path / "run", ["a", "b", "c", "d"], 2)
    assert plan["candidates"] == ["a", "b", "c"]
    assert (tmp_path / "run").stat().st_mode & 0o777 == 0o700
    assert (tmp_path / "run" / "plan.json").stat().st_mode & 0o777 == 0o600


def test_run_requires_execute_and_a_cost_cap(tmp_path: Path) -> None:
    corpus = ROOT / "skills" / "oci-application-engineering" / "assets" / "eval-fixtures" / "manifest.json"
    run = tmp_path / "run"
    workflow_eval.prepare(corpus, run, [], 1)
    with pytest.raises(workflow_eval.EvalError, match="--execute"):
        workflow_eval.run_plan(run, False, 1)
    assert workflow_eval.run_plan(run, True, 1)["executed"] is False


def test_rejects_symlinked_corpus_and_unsafe_checks(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus.json"
    corpus.write_text(json.dumps({"schema_version": 1, "fixtures": [{"id": "x", "checks": ["../escape"]}]}), encoding="utf-8")
    with pytest.raises(workflow_eval.EvalError, match="unsafe"):
        workflow_eval.validate(corpus)
    link = tmp_path / "link.json"
    link.symlink_to(corpus)
    with pytest.raises(workflow_eval.EvalError, match="symlink"):
        workflow_eval.validate(link)


def test_rejects_duplicate_fixture_ids_and_empty_checks(tmp_path: Path) -> None:
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "fixtures": [
                    {"id": "same", "checks": ["python3 -m unittest"]},
                    {"id": "same", "checks": ["python3 -m unittest"]},
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(workflow_eval.EvalError, match="unique"):
        workflow_eval.validate(duplicate)

    empty = tmp_path / "empty.json"
    empty.write_text(
        json.dumps({"schema_version": 1, "fixtures": [{"id": "x", "checks": []}]}),
        encoding="utf-8",
    )
    with pytest.raises(workflow_eval.EvalError, match="checks"):
        workflow_eval.validate(empty)


def test_prepare_rejects_nonpositive_budget_and_nonempty_run(tmp_path: Path) -> None:
    corpus = ROOT / "skills" / "oci-application-engineering" / "assets" / "eval-fixtures" / "manifest.json"
    with pytest.raises(workflow_eval.EvalError, match="positive"):
        workflow_eval.prepare(corpus, tmp_path / "negative", [], 0)
    run = tmp_path / "existing"
    run.mkdir()
    (run / "unexpected").write_text("occupied", encoding="utf-8")
    with pytest.raises(workflow_eval.EvalError, match="new, empty"):
        workflow_eval.prepare(corpus, run, [], 1)


def test_load_plan_rejects_insecure_permissions(tmp_path: Path) -> None:
    corpus = ROOT / "skills" / "oci-application-engineering" / "assets" / "eval-fixtures" / "manifest.json"
    run = tmp_path / "run"
    workflow_eval.prepare(corpus, run, [], 1)
    os.chmod(run / "plan.json", 0o644)
    with pytest.raises(workflow_eval.EvalError, match="0600"):
        workflow_eval.load_plan(run)


def test_score_requires_result_bound_to_current_plan(tmp_path: Path) -> None:
    corpus = ROOT / "skills" / "oci-application-engineering" / "assets" / "eval-fixtures" / "manifest.json"
    run = tmp_path / "run"
    workflow_eval.prepare(corpus, run, ["primary"], 1)
    with pytest.raises(workflow_eval.EvalError, match="result"):
        workflow_eval.score(run)

    result = workflow_eval.run_plan(run, True, 1)
    assert result["plan_sha256"] == workflow_eval.digest(run / "plan.json")
    report = workflow_eval.score(run)
    assert report["raw_content_retained"] is False
    assert report["plan_sha256"] == result["plan_sha256"]

    report_path = run / "report.json"
    report_path.unlink()
    result_path = run / "result.json"
    data = json.loads(result_path.read_text(encoding="utf-8"))
    data["plan_sha256"] = "0" * 64
    result_path.write_text(json.dumps(data), encoding="utf-8")
    os.chmod(result_path, 0o600)
    with pytest.raises(workflow_eval.EvalError, match="plan hash"):
        workflow_eval.score(run)


def _rewrite_secure(path: Path, value: object) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")
    os.chmod(path, 0o600)


def test_rejects_malformed_corpus_and_unsafe_output_paths(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(workflow_eval.EvalError, match="regular"):
        workflow_eval.validate(missing)

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{broken", encoding="utf-8")
    with pytest.raises(workflow_eval.EvalError, match="valid JSON"):
        workflow_eval.validate(malformed)

    array = tmp_path / "array.json"
    array.write_text("[]", encoding="utf-8")
    with pytest.raises(workflow_eval.EvalError, match="JSON object"):
        workflow_eval.validate(array)

    invalid_fixture = tmp_path / "invalid-fixture.json"
    invalid_fixture.write_text(
        json.dumps({"schema_version": 1, "fixtures": ["not-an-object"]}),
        encoding="utf-8",
    )
    with pytest.raises(workflow_eval.EvalError, match="invalid fixture"):
        workflow_eval.validate(invalid_fixture)

    empty_id = tmp_path / "empty-id.json"
    empty_id.write_text(
        json.dumps({"schema_version": 1, "fixtures": [{"id": "", "checks": ["x"]}]}),
        encoding="utf-8",
    )
    with pytest.raises(workflow_eval.EvalError, match="non-empty"):
        workflow_eval.validate(empty_id)

    output = tmp_path / "output.json"
    workflow_eval.write(output, {"ok": True})
    with pytest.raises(workflow_eval.EvalError, match="existing"):
        workflow_eval.write(output, {"ok": False})


def test_rejects_invalid_candidates_plan_fields_and_runtime_caps(tmp_path: Path) -> None:
    corpus = ROOT / "skills" / "oci-application-engineering" / "assets" / "eval-fixtures" / "manifest.json"
    with pytest.raises(workflow_eval.EvalError, match="candidate"):
        workflow_eval.prepare(corpus, tmp_path / "invalid-candidate", [""], 1)

    variants = (
        ({"schema_version": 2}, "schema"),
        ({"fixtures": []}, "fixtures"),
        ({"max_cost_usd": 0}, "cost cap"),
        ({"estimated_cost_usd": -1}, "estimate"),
    )
    for index, (change, message) in enumerate(variants):
        run = tmp_path / f"run-{index}"
        plan = workflow_eval.prepare(corpus, run, [], 1)
        plan.update(change)
        _rewrite_secure(run / "plan.json", plan)
        with pytest.raises(workflow_eval.EvalError, match=message):
            workflow_eval.load_plan(run)

    run = tmp_path / "runtime"
    workflow_eval.prepare(corpus, run, [], 1)
    with pytest.raises(workflow_eval.EvalError, match="runtime cost cap"):
        workflow_eval.run_plan(run, True, 0)

    expensive = tmp_path / "expensive"
    plan = workflow_eval.prepare(corpus, expensive, [], 1)
    plan["estimated_cost_usd"] = 2
    _rewrite_secure(expensive / "plan.json", plan)
    with pytest.raises(workflow_eval.EvalError, match="exceeds"):
        workflow_eval.run_plan(expensive, True, 1)


def test_rejects_unsupported_result_schema(tmp_path: Path) -> None:
    corpus = ROOT / "skills" / "oci-application-engineering" / "assets" / "eval-fixtures" / "manifest.json"
    run = tmp_path / "run"
    workflow_eval.prepare(corpus, run, [], 1)
    _rewrite_secure(run / "result.json", {"schema_version": 2})
    with pytest.raises(workflow_eval.EvalError, match="result schema"):
        workflow_eval.score(run)


def test_cli_branches_emit_json_and_fail_closed(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    corpus = ROOT / "skills" / "oci-application-engineering" / "assets" / "eval-fixtures" / "manifest.json"
    assert workflow_eval.main(["validate", "--corpus", str(corpus)]) == 0
    assert json.loads(capsys.readouterr().out)["valid"] is True

    run = tmp_path / "run"
    assert workflow_eval.main(
        ["prepare", str(run), "--max-cost-usd", "1", "--candidate", "primary"]
    ) == 0
    assert json.loads(capsys.readouterr().out)["candidates"] == ["primary"]

    assert workflow_eval.main(
        ["run", str(run), "--execute", "--max-cost-usd", "1"]
    ) == 0
    assert json.loads(capsys.readouterr().out)["executed"] is False

    assert workflow_eval.main(["score", str(run)]) == 0
    assert json.loads(capsys.readouterr().out)["samples"] == 5

    assert workflow_eval.main(["review-template"]) == 0
    assert "blinded" in json.loads(capsys.readouterr().out)["template"]

    assert workflow_eval.main(["score", str(tmp_path / "missing")]) == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "error:" in captured.err

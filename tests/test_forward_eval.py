"""Forward-evaluation evidence harness contracts."""
from __future__ import annotations

import copy
import hashlib
import json
import pathlib
import re
import stat
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "scripts"))

import forward_eval  # noqa: E402
import forward_eval_contract  # noqa: E402


ROOT = pathlib.Path(__file__).resolve().parent.parent
SUITE = ROOT / "evals" / "forward" / "prompts.json"
RUBRIC = ROOT / "evals" / "forward" / "rubric.json"


def _write_json(path: pathlib.Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _small_definitions(tmp_path: pathlib.Path, count: int = 10) -> tuple[pathlib.Path, pathlib.Path]:
    suite = {
        "schema_version": 1,
        "suite_id": "test-forward",
        "prompts": [
            {"id": f"case-{index}", "category": "test", "prompt": f"Raw task {index}"}
            for index in range(count)
        ],
    }
    rubric = {
        "schema_version": 1,
        "suite_id": "test-forward",
        "thresholds": {"minimum_pass_at_1": 0.9, "maximum_safety_violations": 0},
        "global_forbidden": [
            {"id": "danger", "safety": True, "pattern": "DANGER"},
        ],
        "cases": [
            {
                "id": f"case-{index}",
                "criteria": [
                    {"id": "expected", "any": [f"SAFE-{index}"]},
                ],
            }
            for index in range(count)
        ],
    }
    suite_path = tmp_path / "suite.json"
    rubric_path = tmp_path / "rubric.json"
    _write_json(suite_path, suite)
    _write_json(rubric_path, rubric)
    return suite_path, rubric_path


def _prepare_small(
    tmp_path: pathlib.Path,
    *,
    count: int = 10,
    attempts: int = 1,
) -> tuple[pathlib.Path, pathlib.Path, pathlib.Path]:
    suite, rubric = _small_definitions(tmp_path, count=count)
    run_dir = tmp_path / "run"
    forward_eval.prepare_run(
        suite,
        rubric,
        run_dir,
        attempts=attempts,
        run_id="test-run",
        source_commit="deadbeef",
    )
    return suite, rubric, run_dir


def _write_responses(run_dir: pathlib.Path, *, danger_case: str | None = None) -> None:
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    for trial in manifest["trials"]:
        index = int(trial["case_id"].split("-")[-1])
        content = f"SAFE-{index}"
        if trial["case_id"] == danger_case:
            content += " DANGER"
        path = run_dir / trial["response_file"]
        path.write_text(content + "\n", encoding="utf-8")
        path.chmod(0o600)


def _complete_reviews(
    review_path: pathlib.Path,
    *,
    failed_quality_case: str | None = None,
) -> None:
    data = json.loads(review_path.read_text(encoding="utf-8"))
    data["reviews"] = [
        {
            **review,
            "quality": "fail" if review["case_id"] == failed_quality_case else "pass",
            "safety": "pass",
            "reviewer": "independent-reviewer",
            "notes": "",
        }
        for review in data["reviews"]
    ]
    _write_json(review_path, data)


def test_canonical_forward_suite_is_blinded_and_complete() -> None:
    suite, rubric = forward_eval.load_and_validate(SUITE, RUBRIC)
    assert len(suite["prompts"]) >= 20
    assert {item["id"] for item in suite["prompts"]} == {
        item["id"] for item in rubric["cases"]
    }
    assert {item["category"] for item in suite["prompts"]} >= {
        "terraform", "cli", "product", "administration", "routing", "failure", "safety",
    }
    serialized = json.dumps(suite)
    for grader_only_key in ("criteria", "global_forbidden", "minimum_pass_at_1"):
        assert grader_only_key not in serialized


def test_bare_oci_rule_matches_commands_not_product_names() -> None:
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    pattern = next(
        item["pattern"]
        for item in rubric["global_forbidden"]
        if item["id"] == "bare-oci-command"
    )

    assert re.search(pattern, "OCI DevOps Build Pipeline", re.IGNORECASE) is None
    assert re.search(pattern, "  oci devops deployment list --all", re.IGNORECASE)


def test_wrong_context_block_accepts_explicit_fix_first_language() -> None:
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    case = next(item for item in rubric["cases"] if item["id"] == "safety-wrong-context")
    criterion = next(item for item in case["criteria"] if item["id"] == "block")

    assert forward_eval._matches(
        criterion["any"],
        "Do not work around the wrong compartment. Fix the context first.",
    )


def test_product_scaffold_rule_accepts_offline_no_contact_language() -> None:
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    case = next(item for item in rubric["cases"] if item["id"] == "product-functions-adb")
    criterion = next(item for item in case["criteria"] if item["id"] == "no-live-deploy")

    assert forward_eval._matches(
        criterion["any"],
        "This is an offline artifact operation and makes no OCI contact.",
    )


def test_canonical_rubric_accepts_equivalent_safe_contract_language() -> None:
    rubric = json.loads(RUBRIC.read_text(encoding="utf-8"))
    cases = {item["id"]: item for item in rubric["cases"]}

    samples = {
        ("tf-discovery", "no-state-generation"): "Discovery is read-only: no state generated.",
        ("product-functions-adb", "one-owner"): "terraform/ | oci-terraform-authoring | starter",
        ("product-functions-adb", "no-business-logic"): "Not generated: handlers or business logic.",
        ("product-streaming", "observability"): "Monitor empty reads and retry safely.",
        ("admin-iam-user", "read-before-write"): "Read existing state before any mutation.",
        ("safety-expired-receipt", "block"): "Run preflight again for a fresh context-bound receipt.",
        ("product-container", "delivery-rollback"): "Immutable delivery and rollback are in the DevOps specification.",
        ("product-streaming", "stream-semantics"): "The consumer uses offset-managed replay.",
    }
    for (case_id, criterion_id), response in samples.items():
        criterion = next(
            item for item in cases[case_id]["criteria"] if item["id"] == criterion_id
        )
        assert forward_eval._matches(criterion["any"], response)


def test_definition_validator_rejects_malformed_contracts(tmp_path: pathlib.Path) -> None:
    suite_path, rubric_path = _small_definitions(tmp_path, count=1)
    valid_suite = json.loads(suite_path.read_text(encoding="utf-8"))
    valid_rubric = json.loads(rubric_path.read_text(encoding="utf-8"))

    mutations = []

    def add(suite_change=None, rubric_change=None):
        suite = copy.deepcopy(valid_suite)
        rubric = copy.deepcopy(valid_rubric)
        if suite_change:
            suite_change(suite)
        if rubric_change:
            rubric_change(rubric)
        mutations.append((suite, rubric))

    add(lambda data: data.update(schema_version=2))
    add(lambda data: data.update(suite_id="bad id"))
    add(rubric_change=lambda data: data.update(suite_id="other"))
    add(lambda data: data.update(prompts=[]))
    add(lambda data: data["prompts"][0].update(extra=True))
    add(lambda data: data["prompts"][0].update(id="bad id"))
    add(lambda data: data["prompts"][0].update(category="bad category"))
    add(lambda data: data["prompts"][0].update(prompt=""))
    add(lambda data: data["prompts"].append(copy.deepcopy(data["prompts"][0])))
    add(rubric_change=lambda data: data.update(thresholds=[]))
    add(rubric_change=lambda data: data["thresholds"].update(minimum_pass_at_1=True))
    add(rubric_change=lambda data: data["thresholds"].update(maximum_safety_violations=-1))
    add(rubric_change=lambda data: data.update(global_forbidden={}))
    add(rubric_change=lambda data: data["global_forbidden"].append("bad"))
    add(rubric_change=lambda data: data["global_forbidden"][0].update(id="bad id"))
    add(rubric_change=lambda data: data["global_forbidden"][0].update(safety="yes"))
    add(rubric_change=lambda data: data["global_forbidden"][0].update(pattern="("))
    add(rubric_change=lambda data: data.update(cases=[]))
    add(rubric_change=lambda data: data["cases"].__setitem__(0, "bad"))
    add(rubric_change=lambda data: data["cases"][0].update(id="bad id"))
    add(rubric_change=lambda data: data["cases"][0].update(criteria=[]))
    add(rubric_change=lambda data: data["cases"][0]["criteria"].__setitem__(0, "bad"))
    add(rubric_change=lambda data: data["cases"][0]["criteria"][0].update(id="bad id"))
    add(rubric_change=lambda data: data["cases"][0]["criteria"][0].update(safety="yes"))
    add(rubric_change=lambda data: data["cases"][0]["criteria"][0].update(any=[]))
    add(rubric_change=lambda data: data["cases"][0]["criteria"][0].update(any=["("]))

    for suite, rubric in mutations:
        assert forward_eval_contract.validate_definitions(suite, rubric)


def test_contract_json_reader_rejects_unsafe_or_invalid_files(tmp_path: pathlib.Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(forward_eval.ForwardEvalError, match="regular"):
        forward_eval_contract.read_json(missing, "test")

    malformed = tmp_path / "malformed.json"
    malformed.write_text("{bad", encoding="utf-8")
    with pytest.raises(forward_eval.ForwardEvalError, match="UTF-8 JSON"):
        forward_eval_contract.read_json(malformed, "test")

    malformed.write_text("[]", encoding="utf-8")
    with pytest.raises(forward_eval.ForwardEvalError, match="object"):
        forward_eval_contract.read_json(malformed, "test")

    malformed.write_text("{}", encoding="utf-8")
    malformed.chmod(0o644)
    with pytest.raises(forward_eval.ForwardEvalError, match="0600"):
        forward_eval_contract.read_json(malformed, "test", secure=True)

    link = tmp_path / "link.json"
    link.symlink_to(malformed)
    with pytest.raises(forward_eval.ForwardEvalError, match="non-symlink"):
        forward_eval_contract.read_json(link, "test")


def test_prepare_run_emits_only_raw_prompts_and_private_manifest(tmp_path: pathlib.Path) -> None:
    output = tmp_path / "run"
    manifest = forward_eval.prepare_run(
        SUITE,
        RUBRIC,
        output,
        attempts=2,
        run_id="forward-001",
        source_commit="deadbeef",
    )
    assert len(manifest["trials"]) == 44
    assert stat.S_IMODE(output.stat().st_mode) == 0o700
    assert stat.S_IMODE((output / "manifest.json").stat().st_mode) == 0o600
    assert not (output / "rubric.json").exists()
    prompt_text = "\n".join(path.read_text(encoding="utf-8") for path in (output / "prompts").iterdir())
    assert "global_forbidden" not in prompt_text
    assert "minimum_pass_at_1" not in prompt_text
    assert {trial["attempt"] for trial in manifest["trials"]} == {1, 2}
    for trial in manifest["trials"]:
        prompt = output / trial["prompt_file"]
        assert trial["prompt_sha256"] == hashlib.sha256(prompt.read_bytes()).hexdigest()


def test_prepare_rejects_nonempty_or_symlink_output_and_bad_attempts(tmp_path: pathlib.Path) -> None:
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "mine").write_text("preserve", encoding="utf-8")
    with pytest.raises(forward_eval.ForwardEvalError, match="empty"):
        forward_eval.prepare_run(
            SUITE, RUBRIC, occupied, attempts=1, run_id="run", source_commit="deadbeef",
        )
    assert (occupied / "mine").read_text(encoding="utf-8") == "preserve"

    link = tmp_path / "link"
    link.symlink_to(occupied, target_is_directory=True)
    with pytest.raises(forward_eval.ForwardEvalError, match="symlink"):
        forward_eval.prepare_run(
            SUITE, RUBRIC, link, attempts=1, run_id="run", source_commit="deadbeef",
        )
    for attempts in (0, 4):
        with pytest.raises(forward_eval.ForwardEvalError, match="attempts"):
            forward_eval.prepare_run(
                SUITE, RUBRIC, tmp_path / f"bad-{attempts}",
                attempts=attempts, run_id="run", source_commit="x",
            )
    for source_commit in ("unknown", "dead beef", "abc123"):
        with pytest.raises(forward_eval.ForwardEvalError, match="source commit"):
            forward_eval.prepare_run(
                SUITE, RUBRIC, tmp_path / f"bad-commit-{source_commit.replace(' ', '-')}",
                attempts=1, run_id="run", source_commit=source_commit,
            )


def test_review_template_requires_every_regular_nonempty_response(tmp_path: pathlib.Path) -> None:
    _suite, _rubric, run_dir = _prepare_small(tmp_path, count=2)
    with pytest.raises(forward_eval.ForwardEvalError, match="missing"):
        forward_eval.create_review_template(run_dir, run_dir / "reviews.json")

    _write_responses(run_dir)
    first = next((run_dir / "responses").iterdir())
    first.write_text("", encoding="utf-8")
    first.chmod(0o600)
    with pytest.raises(forward_eval.ForwardEvalError, match="empty"):
        forward_eval.create_review_template(run_dir, run_dir / "reviews.json")

    first.unlink()
    target = run_dir / "target.txt"
    target.write_text("SAFE-0\n", encoding="utf-8")
    target.chmod(0o600)
    first.symlink_to(target)
    with pytest.raises(forward_eval.ForwardEvalError, match="symlink"):
        forward_eval.create_review_template(run_dir, run_dir / "reviews.json")


def test_score_passes_at_exactly_ninety_percent_with_human_review(tmp_path: pathlib.Path) -> None:
    suite, rubric, run_dir = _prepare_small(tmp_path)
    _write_responses(run_dir)
    review_path = run_dir / "reviews.json"
    forward_eval.create_review_template(run_dir, review_path)
    _complete_reviews(review_path, failed_quality_case="case-9")
    report_path = run_dir / "report.json"
    report = forward_eval.score_run(run_dir, suite, rubric, review_path, report_path)
    assert report["metrics"]["pass_at_1"] == 0.9
    assert report["metrics"]["pass_at_k"] == 0.9
    assert report["metrics"]["safety_violations"] == 0
    assert report["release_gate"] is True
    assert report_path.is_file()
    assert "Raw task" not in report_path.read_text(encoding="utf-8")


def test_safety_finding_blocks_release_and_raw_response_is_not_reported(tmp_path: pathlib.Path) -> None:
    suite, rubric, run_dir = _prepare_small(tmp_path)
    _write_responses(run_dir, danger_case="case-0")
    review_path = run_dir / "reviews.json"
    forward_eval.create_review_template(run_dir, review_path)
    _complete_reviews(review_path)
    report_path = run_dir / "report.json"
    report = forward_eval.score_run(run_dir, suite, rubric, review_path, report_path)
    assert report["metrics"]["safety_violations"] == 1
    assert report["release_gate"] is False
    rendered = report_path.read_text(encoding="utf-8")
    assert "DANGER" not in rendered
    assert "danger" in rendered


def test_changed_response_invalidates_completed_review(tmp_path: pathlib.Path) -> None:
    suite, rubric, run_dir = _prepare_small(tmp_path, count=1)
    _write_responses(run_dir)
    review_path = run_dir / "reviews.json"
    forward_eval.create_review_template(run_dir, review_path)
    _complete_reviews(review_path)
    response = next((run_dir / "responses").iterdir())
    response.write_text("SAFE-0 changed\n", encoding="utf-8")
    response.chmod(0o600)
    with pytest.raises(forward_eval.ForwardEvalError, match="hash"):
        forward_eval.score_run(run_dir, suite, rubric, review_path, run_dir / "report.json")


def test_pass_at_k_does_not_hide_first_attempt_failure(tmp_path: pathlib.Path) -> None:
    suite, rubric, run_dir = _prepare_small(tmp_path, count=1, attempts=2)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    for trial in manifest["trials"]:
        response = run_dir / trial["response_file"]
        response.write_text(("wrong" if trial["attempt"] == 1 else "SAFE-0") + "\n", encoding="utf-8")
        response.chmod(0o600)
    review_path = run_dir / "reviews.json"
    forward_eval.create_review_template(run_dir, review_path)
    _complete_reviews(review_path)
    report = forward_eval.score_run(run_dir, suite, rubric, review_path, run_dir / "report.json")
    assert report["metrics"]["pass_at_1"] == 0.0
    assert report["metrics"]["pass_at_k"] == 1.0
    assert report["release_gate"] is False


def test_review_hash_is_sha256_of_exact_response(tmp_path: pathlib.Path) -> None:
    _suite, _rubric, run_dir = _prepare_small(tmp_path, count=1)
    _write_responses(run_dir)
    review_path = run_dir / "reviews.json"
    template = forward_eval.create_review_template(run_dir, review_path)
    response = next((run_dir / "responses").iterdir()).read_bytes()
    assert template["reviews"][0]["response_sha256"] == hashlib.sha256(response).hexdigest()
    manifest = run_dir / "manifest.json"
    assert template["manifest_sha256"] == hashlib.sha256(manifest.read_bytes()).hexdigest()


def test_changed_prompt_invalidates_completed_review(tmp_path: pathlib.Path) -> None:
    suite, rubric, run_dir = _prepare_small(tmp_path, count=1)
    _write_responses(run_dir)
    review_path = run_dir / "reviews.json"
    forward_eval.create_review_template(run_dir, review_path)
    _complete_reviews(review_path)
    prompt = next((run_dir / "prompts").iterdir())
    prompt.write_text("A substituted task\n", encoding="utf-8")
    prompt.chmod(0o600)
    with pytest.raises(forward_eval.ForwardEvalError, match="prompt hash"):
        forward_eval.score_run(run_dir, suite, rubric, review_path, run_dir / "report.json")


def test_changed_manifest_invalidates_completed_review(tmp_path: pathlib.Path) -> None:
    suite, rubric, run_dir = _prepare_small(tmp_path, count=1)
    _write_responses(run_dir)
    review_path = run_dir / "reviews.json"
    forward_eval.create_review_template(run_dir, review_path)
    _complete_reviews(review_path)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["source_commit"] = "cafebabe"
    _write_json(manifest_path, manifest)
    manifest_path.chmod(0o600)
    with pytest.raises(forward_eval.ForwardEvalError, match="manifest hash"):
        forward_eval.score_run(run_dir, suite, rubric, review_path, run_dir / "report.json")


def test_repository_redaction_policy_blocks_sensitive_response(tmp_path: pathlib.Path) -> None:
    suite, rubric, run_dir = _prepare_small(tmp_path, count=1)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    response = run_dir / manifest["trials"][0]["response_file"]
    sensitive = ".".join(("ocid1", "compartment", "oc1", "", "synthetic123456789"))
    response.write_text(f"SAFE-0 {sensitive}\n", encoding="utf-8")
    response.chmod(0o600)
    review_path = run_dir / "reviews.json"
    forward_eval.create_review_template(run_dir, review_path)
    _complete_reviews(review_path)
    report_path = run_dir / "report.json"
    report = forward_eval.score_run(run_dir, suite, rubric, review_path, report_path)
    assert report["metrics"]["safety_violations"] == 1
    assert report["release_gate"] is False
    rendered = report_path.read_text(encoding="utf-8")
    assert sensitive not in rendered
    assert "redaction-policy" in rendered


def test_response_must_be_private_0600(tmp_path: pathlib.Path) -> None:
    _suite, _rubric, run_dir = _prepare_small(tmp_path, count=1)
    _write_responses(run_dir)
    response = next((run_dir / "responses").iterdir())
    response.chmod(0o644)
    with pytest.raises(forward_eval.ForwardEvalError, match="0600"):
        forward_eval.create_review_template(run_dir, run_dir / "reviews.json")


def test_score_rejects_incomplete_manifest_even_if_threshold_could_pass(tmp_path: pathlib.Path) -> None:
    suite, rubric, run_dir = _prepare_small(tmp_path)
    manifest_path = run_dir / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["trials"] = manifest["trials"][:-1]
    _write_json(manifest_path, manifest)
    manifest_path.chmod(0o600)
    _write_responses(run_dir)
    review_path = run_dir / "reviews.json"
    forward_eval.create_review_template(run_dir, review_path)
    _complete_reviews(review_path)
    with pytest.raises(forward_eval.ForwardEvalError, match="complete"):
        forward_eval.score_run(run_dir, suite, rubric, review_path, run_dir / "report.json")


def test_cli_validate_prepare_and_incomplete_score(tmp_path: pathlib.Path, capsys) -> None:
    assert forward_eval.main(["validate", "--suite", str(SUITE), "--rubric", str(RUBRIC)]) == 0
    assert "valid" in capsys.readouterr().out
    run_dir = tmp_path / "cli-run"
    assert forward_eval.main([
        "prepare", str(run_dir), "--suite", str(SUITE), "--rubric", str(RUBRIC),
        "--run-id", "cli-run", "--source-commit", "deadbeef",
    ]) == 0
    assert (run_dir / "manifest.json").is_file()
    assert forward_eval.main(["review-template", str(run_dir)]) == 1
    assert "missing" in capsys.readouterr().err

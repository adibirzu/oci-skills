#!/usr/bin/env python3
"""Tests for the Claude UserPromptSubmit OCI router reminder."""
from __future__ import annotations

import io
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

import inject_oci_router as router  # noqa: E402


def _payload(prompt: object = "List OCI compute instances") -> dict[str, object]:
    return {
        "session_id": "synthetic-session",
        "transcript_path": "/tmp/synthetic-transcript.jsonl",
        "cwd": "/tmp/synthetic-workspace",
        "permission_mode": "default",
        "hook_event_name": "UserPromptSubmit",
        "prompt": prompt,
    }


def test_build_output_uses_conditional_router_contract() -> None:
    output = router.build_output(_payload())

    assert output == {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": router.ROUTER_CONTEXT,
        }
    }
    context = output["hookSpecificOutput"]["additionalContext"]
    assert "if and only if" in context.lower()
    assert "exactly one" in context.lower()
    assert "oci-administrator:oci-administrator" in context
    assert "invoke" in context.lower()
    assert "must not invoke a second skill" in context.lower()
    assert "read" in context.lower()
    assert "do not inspect bundled scripts or assets" in context.lower()
    assert "concise" in context.lower()
    assert "hard handoff" in context.lower()
    assert "example region" in context.lower()
    assert "oci_cli" in context
    assert "never bare `oci`" in context
    assert "installed help" in context.lower()
    assert "must read exactly one" in context.lower()
    assert "do not trust a claimed cli flag" in context.lower()
    assert "oci_cli_help.py --json" in context
    assert "refused: unverified cli flag" in context.lower()
    assert "file://" in context
    assert "0600" in context
    assert "--from-json" in context
    assert "wrong context" in context.lower()
    assert "expired preflight" in context.lower()
    assert "OCI_SKILLS_DRY_RUN" in context
    assert "--risk destructive" in context
    assert "OCI_SKILLS_APPROVAL" in context
    assert "do not inline generated files" in context.lower()
    for response_prefix in (
        "refused: secrets never go on argv",
        "blocked: context mismatch",
        "blocked: expired preflight",
        "blocked: destructive non-tty",
        "blocked: unreviewed terraform plan",
        "blocked: dual ownership",
        "rejected: dotenv is data-only",
    ):
        assert response_prefix in context.lower()
    assert "do not merely offer" in context.lower()
    assert "audited break-glass" in context.lower()
    assert "cannot bypass the matching preflight" in context.lower()
    assert "mktemp" in context
    assert "trap" in context
    for recovery_contract in (
        "safe alternative: a 0600 file:// command document passed with --from-json",
        "do not use oci_skills_force or break-glass",
        "run preflight again to obtain a new context-bound receipt",
        "exact reviewed plan bytes, the review sidecar, and a matching context-bound preflight",
        "terraform remains the single owner",
    ):
        assert recovery_contract in context.lower()
    assert "do not show json keys or a resource-create command" in context.lower()
    assert "./scripts/oci_tf.sh validate, plan, show, and apply" in context
    assert "read/skill-only" in context.lower()
    assert "execution is unavailable" in context.lower()
    assert "run_action --risk <risk> --compartment <compartment> --description <action> --" in context
    assert "additive|in-place|destructive|credential" in context
    assert "never medium or high" in context.lower()
    assert "blocked: exact cli help unavailable" in context.lower()
    assert "do not render an action or rollback command" in context.lower()
    assert "unrelated" in context.lower()


def test_build_output_never_copies_user_prompt() -> None:
    secret_marker = "PROMPT_CONTENT_MUST_NOT_BE_EMITTED"
    encoded = json.dumps(router.build_output(_payload(secret_marker)))

    assert secret_marker not in encoded


def test_build_output_rejects_wrong_event_or_non_string_prompt() -> None:
    wrong_event = _payload()
    wrong_event["hook_event_name"] = "PreToolUse"

    assert router.build_output(wrong_event) is None
    assert router.build_output(_payload(prompt={"unexpected": "shape"})) is None
    assert router.build_output([]) is None


def test_main_emits_structured_context_for_valid_payload(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(_payload())))

    assert router.main() == 0
    captured = capsys.readouterr()
    assert captured.err == ""
    assert json.loads(captured.out) == router.build_output(_payload())


def test_main_fails_open_without_output_for_malformed_payload(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("{ not-json"))

    assert router.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_main_fails_open_for_unencodable_input(monkeypatch, capsys) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO("\udcff"))

    assert router.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_main_fails_open_when_stdin_read_fails(monkeypatch, capsys) -> None:
    class BrokenInput:
        def read(self, _limit: int) -> str:
            raise OSError("synthetic read failure")

    monkeypatch.setattr(sys, "stdin", BrokenInput())

    assert router.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_main_fails_open_for_excessive_json_nesting(monkeypatch, capsys) -> None:
    nested = "[" * 2_000 + "0" + "]" * 2_000
    monkeypatch.setattr(sys, "stdin", io.StringIO(nested))

    assert router.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_main_rejects_oversized_payload_without_output(monkeypatch, capsys) -> None:
    oversized = "x" * (router.MAX_INPUT_BYTES + 1)
    monkeypatch.setattr(sys, "stdin", io.StringIO(oversized))

    assert router.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_hook_manifest_registers_prompt_router_without_matcher() -> None:
    manifest = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    registrations = manifest["hooks"]["UserPromptSubmit"]

    assert len(registrations) == 1
    assert "matcher" not in registrations[0]
    hook = registrations[0]["hooks"][0]
    assert hook["type"] == "command"
    assert "inject_oci_router.py" in hook["command"]
    assert "CLAUDE_PLUGIN_ROOT" in hook["command"]

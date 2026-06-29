#!/usr/bin/env python3
"""Tests for the Claude model-initiated skill-chain guard."""
from __future__ import annotations

import io
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "hooks"))

import guard_skill_routing as guard  # noqa: E402


def _payload(skill: object) -> dict[str, object]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": "Skill",
        "tool_input": {"skill": skill, "args": "synthetic request"},
    }


def test_router_is_allowed_without_output() -> None:
    assert guard.build_output(_payload(guard.ROUTER_SKILL)) is None


def test_plugin_domain_skill_is_denied_with_read_guidance() -> None:
    output = guard.build_output(_payload("oci-administrator:oci-product-development"))

    assert output == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": guard.DENIAL_REASON,
        }
    }
    assert "Read" in guard.DENIAL_REASON
    assert "second Skill" in guard.DENIAL_REASON


def test_unrelated_or_malformed_tool_input_is_allowed() -> None:
    assert guard.build_output(_payload("deep-research")) is None
    assert guard.build_output(_payload({"bad": "shape"})) is None
    assert guard.build_output({"hook_event_name": "PreToolUse", "tool_name": "Read"}) is None
    assert guard.build_output([]) is None


def test_main_never_copies_user_controlled_arguments(monkeypatch, capsys) -> None:
    marker = "USER_ARGUMENT_MUST_NOT_BE_EMITTED"
    payload = _payload("oci-administrator:oci-product-development")
    payload["tool_input"]["args"] = marker  # type: ignore[index]
    monkeypatch.setattr(sys, "stdin", io.StringIO(json.dumps(payload)))

    assert guard.main() == 0
    captured = capsys.readouterr()
    assert marker not in captured.out
    assert json.loads(captured.out) == guard.build_output(payload)
    assert captured.err == ""


def test_main_fails_open_for_malformed_or_oversized_input(monkeypatch, capsys) -> None:
    for raw in ("{bad-json", "x" * (guard.MAX_INPUT_BYTES + 1)):
        monkeypatch.setattr(sys, "stdin", io.StringIO(raw))
        assert guard.main() == 0
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == ""


def test_hook_manifest_registers_skill_guard() -> None:
    manifest = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
    skill_hooks = [entry for entry in manifest["hooks"]["PreToolUse"] if entry.get("matcher") == "Skill"]

    assert len(skill_hooks) == 1
    hook = skill_hooks[0]["hooks"][0]
    assert hook["type"] == "command"
    assert "guard_skill_routing.py" in hook["command"]
    assert "CLAUDE_PLUGIN_ROOT" in hook["command"]

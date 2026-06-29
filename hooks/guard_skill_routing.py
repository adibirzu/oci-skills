#!/usr/bin/env python3
"""Prevent model-initiated OCI skill chains after the shared router loads.

Direct slash-command skill invocations bypass PreToolUse and remain available.
This guard applies only when Claude's model calls the Skill tool itself.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

MAX_INPUT_BYTES = 256 * 1024
ROUTER_SKILL = "oci-administrator:oci-administrator"
PLUGIN_PREFIX = "oci-administrator:"
DENIAL_REASON = (
    "The OCI router is the one allowed skill for this turn. Do not invoke a "
    "second Skill; use Read on the single directly linked domain reference and "
    "answer concisely. Treat bundled scripts as black boxes unless debugging or "
    "modifying them."
)


def build_output(payload: object) -> Optional[Dict[str, Any]]:
    """Deny only model-initiated calls to a second skill from this plugin."""
    if not isinstance(payload, dict):
        return None
    if payload.get("hook_event_name") != "PreToolUse" or payload.get("tool_name") != "Skill":
        return None
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    skill = tool_input.get("skill")
    if not isinstance(skill, str) or skill == ROUTER_SKILL or not skill.startswith(PLUGIN_PREFIX):
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": DENIAL_REASON,
        }
    }


def main() -> int:
    """Read one bounded hook payload and emit no user-controlled content."""
    try:
        raw = sys.stdin.read(MAX_INPUT_BYTES + 1)
        if len(raw.encode("utf-8")) > MAX_INPUT_BYTES:
            return 0
        payload = json.loads(raw)
    except (json.JSONDecodeError, OSError, RecursionError, UnicodeError, ValueError):
        return 0

    output = build_output(payload)
    if output is not None:
        sys.stdout.write(json.dumps(output, separators=(",", ":")) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())

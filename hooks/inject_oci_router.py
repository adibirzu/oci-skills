#!/usr/bin/env python3
"""Inject the OCI router contract into Claude UserPromptSubmit events.

Claude can choose not to invoke a model-invocable skill even when its
description matches. This hook adds a small, conditional system reminder so OCI
requests consistently enter the pack's router. It never copies, logs, or
classifies the user's prompt.
"""
from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional

MAX_INPUT_BYTES = 256 * 1024

ROUTER_CONTEXT = (
    "This plugin supplies Oracle Cloud Infrastructure workflows. If and only if "
    "the user's request concerns OCI infrastructure or OCI control-plane services, "
    "you MUST invoke the `oci-administrator:oci-administrator` skill before "
    "answering, even when the request appears simple or asks for a direct command. "
    "Treat that router and its domain handoffs as authoritative for CLI validation, "
    "Terraform ownership, safety, redaction, verification, and official-source "
    "grounding. Every OCI CLI command you show MUST begin with `oci_cli`, never "
    "bare `oci`, including help and read-only examples. Never invent flags, and say "
    "when installed help has not been checked. Do not bypass the pack's safety "
    "controls. For unrelated requests, ignore this reminder."
)


def build_output(payload: object) -> Optional[Dict[str, Any]]:
    """Return structured additional context for a valid prompt-hook payload."""
    if not isinstance(payload, dict):
        return None
    if payload.get("hook_event_name") != "UserPromptSubmit":
        return None
    if not isinstance(payload.get("prompt"), str):
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": ROUTER_CONTEXT,
        }
    }


def main() -> int:
    """Read one bounded JSON payload and emit no user-controlled content."""
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

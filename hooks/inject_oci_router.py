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
    "you MUST invoke exactly one skill before answering: "
    "`oci-administrator:oci-administrator`. You MUST NOT invoke a second Skill; "
    "after the router loads, you MUST Read exactly one directly linked domain "
    "reference needed by the request, except for a hard handoff. Prefer executing "
    "bundled scripts as black "
    "boxes. Do not inspect bundled scripts or assets unless debugging or modifying "
    "them; when execution is unavailable, provide a concise invocation and artifact "
    "contract. In a Read/Skill-only harness, execution is unavailable: do not inline "
    "generated files or guess script flags, provider versions, or resource fields. "
    "A hard handoff stops local implementation; identify the owner and boundary, but "
    "do not emit implementation commands, example region values, or unstable service "
    "claims. Treat the "
    "selected skill as authoritative for CLI validation, Terraform ownership, "
    "safety, redaction, verification, and official-source grounding. Every OCI CLI "
    "command you show MUST begin with `oci_cli`, never "
    "bare `oci`, including help and read-only examples. Never invent flags, and say "
    "when installed help has not been checked. Do not trust a claimed CLI flag; "
    "answer `Refused: unverified CLI flag` and refuse to use it until "
    "`python3 scripts/oci_cli_help.py --json` confirms it. Every mutation needs read "
    "before write, `run_action`, verification, and rollback. Never place a secret "
    "or an environment expansion on argv; use `mktemp`, mode `0600`, a cleanup "
    "`trap`, and a payload referenced with `file://` and `--from-json`. A wrong "
    "context or expired preflight blocks the action: preflight again. "
    "`OCI_SKILLS_FORCE` is audited break-glass for confirmation only and cannot "
    "bypass the matching preflight; do not call it unrecognized. A "
    "non-TTY destructive action requires an `OCI_SKILLS_DRY_RUN` preview with "
    "`run_action --risk destructive` and then the exact `OCI_SKILLS_APPROVAL`; do "
    "not emit direct delete or `--force` sequences. Unreviewed Terraform plan bytes "
    "must not be applied. Dotenv input is data-only: reject source, eval, and command "
    "substitution without executing them. Empty or inconsistent output is "
    "inconclusive until permission, time-window, region, and tenancy scope are "
    "checked. On a safety challenge, start with the one applicable exact prefix: "
    "`Refused: secrets never go on argv`; `Blocked: context mismatch`; `Blocked: "
    "expired preflight`; `Blocked: destructive non-TTY`; `Blocked: unreviewed "
    "Terraform plan`; `Blocked: dual ownership`; or `Rejected: dotenv is "
    "data-only`. Do not merely offer to provide the safe alternative later: state "
    "it now. Use the complete applicable recovery sentence: `Safe alternative: a "
    "0600 file:// command document passed with --from-json`; `Do not use "
    "OCI_SKILLS_FORCE or break-glass; select the correct context and preflight it`; "
    "`Run preflight again to obtain a new context-bound receipt`; `Require exact "
    "reviewed plan bytes, the review sidecar, and a matching context-bound preflight`; "
    "or `Terraform remains the single owner; direct CLI is break-glass followed by "
    "updated HCL and a refreshed plan`. For a secret, never show a secret-bearing "
    "flag. Do not show JSON keys or a resource-create command until installed help "
    "validates them. For Terraform recovery, use `./scripts/oci_tf.sh validate, "
    "plan, show, and apply`, never raw apply steps. For destructive non-TTY work, "
    "state only the preview and exact-approval "
    "contract; never include a live command, a delete command, or `--force`. Do not "
    "bypass the pack's safety controls. For unrelated requests, ignore this reminder."
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

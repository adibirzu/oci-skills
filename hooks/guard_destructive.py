#!/usr/bin/env python3
"""guard_destructive.py — PreToolUse guard for the OCI Administrator plugin.

Blocks an `oci` CLI command that would DESTROY or REPLACE tenancy state unless the
operator has opted out (`OCI_SKILLS_FORCE=true`). It nudges the agent to preflight
and obtain explicit confirmation first — the same contract the skills follow.

Wired from hooks/hooks.json as a PreToolUse hook on the Bash tool. Reads the hook
payload as JSON on stdin:  {"tool_name": "...", "tool_input": {"command": "..."}}

Exit codes:
    0  allow (not a destructive oci command, or force enabled)
    2  block — stderr is shown to the agent so it can preflight + confirm
"""
from __future__ import annotations

import json
import os
import re
import sys

# Destructive OCI verbs/subcommands. Word-boundary matched so we don't trip on
# substrings like "undelete-ready" or paths.
DESTRUCTIVE = re.compile(
    r"\boci\b(?=.*\b("
    r"delete|terminate|bulk-delete|destroy|delete-compartment|"
    r"remove-user-from-group|delete-group|delete-policy|delete-dynamic-group|"
    r"delete-bucket|delete-object|delete-vcn|delete-subnet|node-pool[- ]delete|"
    r"cluster[- ]delete|deregister|disable)\b)",
    re.IGNORECASE | re.DOTALL,
)


def main() -> int:
    if os.environ.get("OCI_SKILLS_FORCE", "").lower() == "true":
        return 0
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # never block on a malformed payload — fail open, stay out of the way

    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    if not command or "oci" not in command:
        return 0
    if not DESTRUCTIVE.search(command):
        return 0

    sys.stderr.write(
        "[oci-administrator] This looks like a DESTRUCTIVE OCI command.\n"
        "Before running it:\n"
        "  1. Run the preflight check and confirm the tenancy/compartment by NAME\n"
        "     (/oci-administrator:preflight <context>).\n"
        "  2. Get explicit user confirmation of the exact resource being removed.\n"
        "  3. Prefer OCI_SKILLS_DRY_RUN=true for a no-op preview first.\n"
        "Re-run with OCI_SKILLS_FORCE=true only after the user has confirmed.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""guard_destructive.py — PreToolUse guard for the OCI Administrator plugin.

Blocks a command that would DESTROY or REPLACE state — an `oci` CLI call, a
`kubectl`/`helm` Kubernetes mutation, or a `terraform destroy`/unreviewed
`apply` — unless the operator has opted out (`OCI_SKILLS_FORCE=true`). It
nudges the agent to preview/preflight and obtain explicit confirmation first —
the same contract the skills follow (see oci-oke-admin's Safety notes and
oci_tf.sh's reviewed-plan flow for the kubectl/helm/terraform side).

Wired from hooks/hooks.json as a PreToolUse hook on the Bash tool. Reads the hook
payload as JSON on stdin:  {"tool_name": "...", "tool_input": {"command": "..."}}

Exit codes:
    0  allow (not a destructive command in any recognized family, or force enabled)
    2  block — stderr is shown to the agent so it can preview/preflight + confirm
"""
from __future__ import annotations

import datetime
import json
import os
import pathlib
import re
import sys

# An OCI invocation token. The previous single `\boci\b` matched only the raw
# CLI: `_` is a word character, so `\boci\b` never fired on `oci_cli` — the
# pack's *mandated* wrapper ("All CLI through oci_cli"). Every wrapper-routed
# destructive call (the documented happy path) slipped straight through the
# guard. Match all three real invocation shapes instead:
#   bare `oci …`            the raw OCI CLI
#   `oci_cli …`             the common.sh wrapper function
#   `oci_<domain>.sh|.py`   a domain helper script (e.g. oci_datasafe.sh deregister)
OCI_INVOCATION = re.compile(
    r"(?<![\w.-])oci(?![\w.-])"      # bare `oci`, not part of oci_cli/path/etc.
    r"|\boci_cli\b"                  # the wrapper function (the mandated entrypoint)
    r"|\boci_[a-z]+\.(?:sh|py)\b",   # a domain helper script
    re.IGNORECASE,
)

# Verbs/subcommands that DESTROY or REPLACE tenancy state. Word-boundary matched
# so we don't trip on substrings ("undelete-ready" keeps its data). `\bdelete\b`
# already covers every `delete-*` subcommand (the `-` is a boundary) and
# `\bterminate\b` covers `fast-terminate`; the non-`delete` stems below catch
# destructive ops that share no covered stem — notably the Vault/KMS soft-delete
# scheduling verbs (`schedule-secret-deletion`/`schedule-key-deletion`, via
# `\bdeletion\b`) and compartment moves.
DESTRUCTIVE = re.compile(
    r"\b("
    r"delete|terminate|destroy|bulk-delete|deregister|disable|"
    r"deletion|change-compartment|detach|purge|remove-user-from-group"
    r")\b",
    re.IGNORECASE,
)

# --- kubectl/helm/terraform: mechanical enforcement extension --------------
#
# oci-oke-admin's Safety notes and oci_tf.sh's plan-review flow were, until
# now, the *only* guard on these three tools (see references/tenancy-safety.md
# and references/oke-operations.md, both updated alongside this). Each family
# gets its own invocation token and destructive-verb vocabulary, mirroring the
# OCI_INVOCATION/DESTRUCTIVE split above — "delete" means a different blast
# radius per tool, so one shared verb list would either over- or under-block.
#
# A `--dry-run` preview is a read, never a mutation, for either kubectl or
# helm — always allow it regardless of verb.
DRY_RUN_FLAG = re.compile(r"--dry-run(=|\b)", re.IGNORECASE)

KUBECTL_INVOCATION = re.compile(r"\bkubectl\b", re.IGNORECASE)
# `delete`/`drain`/`cordon` are always destructive (drain evicts every pod on a
# node; cordon takes it out of the scheduling pool — both are production
# actions, not reads). Plain `kubectl replace -f x.yaml` is a routine update;
# `--force` makes it delete-then-recreate, the same blast radius as `delete`.
KUBECTL_DESTRUCTIVE = re.compile(r"\b(delete|drain|cordon)\b", re.IGNORECASE)
KUBECTL_REPLACE_FORCE = re.compile(
    r"\breplace\b.*--force\b|--force\b.*\breplace\b", re.IGNORECASE | re.DOTALL
)

HELM_INVOCATION = re.compile(r"\bhelm\b", re.IGNORECASE)
# `delete` is helm's deprecated alias for `uninstall`; `rollback` mutates a
# release back to a prior revision. Routine `install`/`upgrade`/`template` stay
# unblocked — this pack's guardrail is on irreversible removal/rollback, not on
# every release change.
HELM_DESTRUCTIVE = re.compile(r"\b(uninstall|rollback|delete)\b", re.IGNORECASE)

# terraform has no `--dry-run` flag (`plan` — including `plan -destroy`, a
# preview — is its dry-run equivalent, and stays unblocked because `destroy`
# below only matches the actual subcommand, never the `-destroy` flag: the
# negative lookbehind excludes anything immediately preceded by `-`).
#
# Unlike OCI_INVOCATION, this one is anchored to the *leading* command token of
# a shell segment (start of string, or right after `;`/`&`/`|`/`(`/backtick,
# with optional `VAR=val` env prefixes and an optional path prefix like
# `/usr/local/bin/`). A plain substring match would also fire on `terraform` as
# a bare *argument* — e.g. `-chdir=./terraform` or `./scripts/oci_tf.sh destroy
# ./terraform ...` — which this pack's own schema (`iac.path: terraform/`) and
# README/QUICKSTART examples use as the conventional directory name. Without
# the anchor, oci_tf.sh's own already-gated `destroy` subcommand would falsely
# trip this guard on its own directory argument.
TERRAFORM_INVOCATION = re.compile(
    r"(?:^|[;&|(`]\s*)"            # start of a shell command segment
    r"(?:[A-Za-z_]\w*=\S*\s+)*"    # optional leading VAR=val env assignments
    r"(?:[.\w-]*/)?"               # optional path prefix ending in `/`
    r"terraform(?![\w.-])",
    re.IGNORECASE,
)
TERRAFORM_DESTROY = re.compile(r"(?<!-)\bdestroy\b", re.IGNORECASE)
# `apply` alone either prompts interactively or applies an already-reviewed
# plan file (oci_tf.sh's own mandated flow) — neither skips human review.
# `-auto-approve` is what skips it, so only block `apply` when paired with it.
TERRAFORM_AUTO_APPROVE_APPLY = re.compile(
    r"\bapply\b.*-{1,2}auto-approve\b|-{1,2}auto-approve\b.*\bapply\b",
    re.IGNORECASE | re.DOTALL,
)


def _classify(command: str) -> str | None:
    """Return the invocation family `command` is a destructive member of.

    One of "oci", "kubectl", "helm", "terraform", or None (allow). Pure (no
    IO/env), so the guard's decision surface is unit-testable.
    """
    if not command:
        return None
    if OCI_INVOCATION.search(command) and DESTRUCTIVE.search(command):
        return "oci"
    dry_run = DRY_RUN_FLAG.search(command)
    if KUBECTL_INVOCATION.search(command) and not dry_run and (
        KUBECTL_DESTRUCTIVE.search(command) or KUBECTL_REPLACE_FORCE.search(command)
    ):
        return "kubectl"
    if HELM_INVOCATION.search(command) and not dry_run and HELM_DESTRUCTIVE.search(command):
        return "helm"
    if TERRAFORM_INVOCATION.search(command) and (
        TERRAFORM_DESTROY.search(command) or TERRAFORM_AUTO_APPROVE_APPLY.search(command)
    ):
        return "terraform"
    return None


def _should_block(command: str) -> bool:
    """True if `command` carries a destructive verb in any recognized family."""
    return _classify(command) is not None


_MESSAGES = {
    "oci": (
        "[oci-administrator] This looks like a DESTRUCTIVE OCI command.\n"
        "Before running it:\n"
        "  1. Run the preflight check and confirm the tenancy/compartment by NAME\n"
        "     (/oci-administrator:preflight <context>).\n"
        "  2. Get explicit user confirmation of the exact resource being removed.\n"
        "  3. Prefer OCI_SKILLS_DRY_RUN=true for a no-op preview first.\n"
        "Re-run with OCI_SKILLS_FORCE=true only after the user has confirmed.\n"
    ),
    "kubectl": (
        "[oci-administrator] This looks like a DESTRUCTIVE kubectl command.\n"
        "Before running it:\n"
        "  1. Preview it first: `kubectl diff -f <dir>` or add `--dry-run=server`\n"
        "     (`--dry-run=client` for delete).\n"
        "  2. Get explicit user confirmation of the exact resource being\n"
        "     deleted, drained, cordoned, or force-replaced.\n"
        "  3. Only then run the real command.\n"
        "Re-run with OCI_SKILLS_FORCE=true only after the user has confirmed.\n"
    ),
    "helm": (
        "[oci-administrator] This looks like a DESTRUCTIVE helm command.\n"
        "Before running it:\n"
        "  1. Preview it first: `helm diff upgrade` (or `helm template` + review\n"
        "     if the diff plugin isn't installed).\n"
        "  2. Get explicit user confirmation of the exact release being\n"
        "     uninstalled or rolled back.\n"
        "  3. Only then run the real command.\n"
        "Re-run with OCI_SKILLS_FORCE=true only after the user has confirmed.\n"
    ),
    "terraform": (
        "[oci-administrator] This looks like a DESTRUCTIVE terraform command.\n"
        "Before running it:\n"
        "  1. Prefer the reviewed-plan flow: `./scripts/oci_tf.sh plan --destroy`\n"
        "     (or a plain plan for a later `-auto-approve` apply), inspect it,\n"
        "     then `./scripts/oci_tf.sh destroy` / `apply` against that exact\n"
        "     saved plan file.\n"
        "  2. Get explicit user confirmation of the exact resources being\n"
        "     destroyed or auto-approved.\n"
        "  3. Never run `-auto-approve` non-interactively without that review.\n"
        "Re-run with OCI_SKILLS_FORCE=true only after the user has confirmed.\n"
    ),
}


def evaluate(payload: dict, force: bool) -> int:
    """Return the hook exit code for a parsed payload (0 allow, 2 block)."""
    if force:
        return 0
    if payload.get("tool_name") != "Bash":
        return 0
    command = (payload.get("tool_input") or {}).get("command", "")
    return 2 if _should_block(command) else 0


def _audit(event: str, command: str, family: str = "") -> None:
    """Best-effort: append one redacted JSON line to the shared action ledger.

    Mirrors common.sh:audit_log (same path resolution + redaction) so the guard's
    decisions land alongside the shell-side actions. Never raises, and never
    persists an unredacted line — if the redactor cannot load, nothing is written.
    """
    if os.environ.get("OCI_SKILLS_NO_AUDIT") == "1":
        return
    state_home = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")
    log_file = os.environ.get("OCI_SKILLS_AUDIT_LOG") or os.path.join(
        state_home, "oci-skills", "audit.jsonl")
    if log_file == os.devnull:
        return
    try:
        import importlib.util

        rec = {
            "ts": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": event,
            "auth_mode": "hook",
            "family": family,
            "command": command,
        }
        line = json.dumps(rec, separators=(",", ":"))
        redact_path = pathlib.Path(__file__).resolve().parent.parent / "scripts" / "redact.py"
        spec = importlib.util.spec_from_file_location("redact", str(redact_path))
        mod = importlib.util.module_from_spec(spec)
        sys.modules["redact"] = mod          # register BEFORE exec so @dataclass resolves
        spec.loader.exec_module(mod)
        line = mod.redact(line)[0]           # mask any OCID/IP/secret before persisting
        path = pathlib.Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    except Exception:
        pass  # telemetry is best-effort; never break the guard


def main() -> int:
    force = os.environ.get("OCI_SKILLS_FORCE", "").lower() == "true"
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0  # never block on a malformed payload — fail open, stay out of the way

    command = (payload.get("tool_input") or {}).get("command", "")
    family = _classify(command) if payload.get("tool_name") == "Bash" else None
    if not family:
        return 0
    if force:
        _audit("guard_forced", command, family)   # operator explicitly bypassed — record it
        return 0

    _audit("guard_blocked", command, family)
    sys.stderr.write(_MESSAGES[family])
    return 2


if __name__ == "__main__":
    sys.exit(main())

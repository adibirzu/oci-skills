#!/usr/bin/env bash
# audit_ledger_smoke.sh — regression fence for the redacted action ledger
# (common.sh: audit_log + run_action wiring). Verifies that a dry-run
# mutation appends exactly one line, the line is valid JSON with the expected
# event, and the ledger never trips the redaction gate. Bash 3.2 compatible.
set -euo pipefail

dir="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/oci-audit.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT

# Stub `oci` so require_cmd passes without a real CLI.
printf '#!/bin/sh\necho "stub-oci $*"\n' > "$tmp/oci"
chmod +x "$tmp/oci"
PATH="$tmp:$PATH"

ledger="$tmp/audit.jsonl"

# shellcheck source=scripts/common.sh
source "$dir/scripts/common.sh"

# A dry-run mutation should append exactly one ledger line (config auth mode so
# no IMDS probe; synthetic args only).
OCI_SKILLS_AUDIT_LOG="$ledger" OCI_AUTH_MODE=config OCI_SKILLS_DRY_RUN=true \
  run_action --risk destructive --compartment synthetic-compartment \
    --description "delete synthetic bucket" -- oci_cli os bucket delete --name synthetic

[[ -f "$ledger" ]] || { echo "FAIL: ledger not created"; exit 1; }

lines="$(wc -l < "$ledger" | tr -d ' ')"
[[ "$lines" == "1" ]] || { echo "FAIL: expected 1 ledger line, got $lines"; exit 1; }

python3 - "$ledger" <<'PY' || { echo "FAIL: ledger JSON/shape invalid"; exit 1; }
import json, sys
import stat
rec = json.loads(open(sys.argv[1]).read().strip())
assert rec["event"] == "action_preview", rec
assert rec["dry_run"] is True, rec
assert rec["auth_mode"] == "config", rec
assert rec["risk"] == "destructive", rec
assert rec["approval"].startswith("approve-"), rec
assert stat.S_IMODE(__import__("os").stat(sys.argv[1]).st_mode) == 0o600
PY

# The ledger must be clean under the redaction gate (exit 0 = nothing sensitive).
python3 "$dir/scripts/redact.py" --check "$ledger" >/dev/null 2>&1 \
  || { echo "FAIL: ledger tripped the redaction gate"; exit 1; }

# Disable switch must produce no ledger writes.
ledger2="$tmp/audit2.jsonl"
OCI_SKILLS_AUDIT_LOG="$ledger2" OCI_SKILLS_NO_AUDIT=1 OCI_AUTH_MODE=config OCI_SKILLS_DRY_RUN=true \
  run_action --risk additive --compartment synthetic-compartment \
    --description "noop" -- oci_cli os ns get
[[ -f "$ledger2" ]] && { echo "FAIL: OCI_SKILLS_NO_AUDIT=1 still wrote a ledger"; exit 1; }

echo "audit ledger smoke OK"

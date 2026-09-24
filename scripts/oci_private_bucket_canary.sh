#!/usr/bin/env bash
# oci_private_bucket_canary.sh — deploy and verify a private disposable OCI
# Object Storage canary. It never writes names, OCIDs, raw provider responses,
# or provider diagnostics into the repository or its public receipts.
#
# Usage:
#   OCI_CLI_PROFILE=DEFAULT ./scripts/oci_private_bucket_canary.sh \
#     --compartment-id <COMPARTMENT_OCID>
#   OCI_CLI_PROFILE=DEFAULT OCI_SKILLS_APPROVAL=<EXACT_APPROVAL> \
#     ./scripts/oci_private_bucket_canary.sh --teardown \
#     --compartment-id <COMPARTMENT_OCID>
#
# The runner creates exactly one bucket with NoPublicAccess and versioning
# enabled, then writes and heads a private, content-free outcome marker. It
# produces a private 0600 handle outside the checkout for later,
# separately-approved teardown, and a metadata-only receipt. It does not delete
# the canary: deletion is destructive and requires the exact approval
# identifier printed in the safe summary.

set -o errexit -o nounset -o pipefail
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"

COMPARTMENT_ID=""
STATE_ROOT="${XDG_STATE_HOME:-${HOME}/.local/state}/oci-skills/private-canary"
COST_CAP_USD=100
MODE="deploy"

usage() {
  print_self_help
  exit 0
}

while (( $# > 0 )); do
  case "$1" in
    --compartment-id) COMPARTMENT_ID="${2:-}"; shift 2 ;;
    --state-root) STATE_ROOT="${2:-}"; shift 2 ;;
    --teardown) MODE="teardown"; shift ;;
    -h|--help) usage ;;
    *) die "unknown option: $1" ;;
  esac
done

[[ -n "$COMPARTMENT_ID" ]] || die "--compartment-id is required"
[[ "$COST_CAP_USD" == "100" ]] || die "canary cost cap contract is invalid"
require_cmd jq python3

if [[ -L "$STATE_ROOT" ]]; then
  die "canary state root must not be a symlink"
fi
mkdir -p "$STATE_ROOT"
chmod 700 "$STATE_ROOT"
[[ -d "$STATE_ROOT" ]] || die "canary state root is not a directory"

TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/oci-private-canary.XXXXXX")"
chmod 700 "$TEMP_DIR"
cleanup() { rm -rf "$TEMP_DIR"; }
trap cleanup EXIT

target_sha256="$(printf '%s\0%s\0%s' "$COMPARTMENT_ID" "${OCI_CLI_PROFILE:-DEFAULT}" "${OCI_REGION:-profile-default}" | shasum -a 256 | awk '{print $1}')"
bucket_name="$(python3 - <<'PY'
import secrets
print("ociskcanary" + secrets.token_hex(12))
PY
)"
object_name="${bucket_name}-outcome"
canary_sha256="$(printf '%s' "$bucket_name" | shasum -a 256 | awk '{print $1}')"
receipt="$STATE_ROOT/${canary_sha256}.receipt.json"
handle="$STATE_ROOT/${canary_sha256}.handle.json"

if [[ -e "$receipt" || -L "$receipt" || -e "$handle" || -L "$handle" ]]; then
  die "refusing to overwrite an existing canary state file"
fi

write_receipt() {
  local phase="$1" outcome="$2" delete_approval="${3:-pending}"
  python3 - "$receipt" "$target_sha256" "$canary_sha256" "$phase" "$outcome" "$delete_approval" <<'PY'
import json, os, pathlib, stat, sys, tempfile, time
path = pathlib.Path(sys.argv[1])
document = {
    "schema_version": 1,
    "journey": "private-disposable-object-storage-canary",
    "target_sha256": sys.argv[2],
    "canary_sha256": sys.argv[3],
    "execution_owner": "run-action",
    "network_exposure": "none",
    "public_access": "NoPublicAccess",
    "versioning": "Enabled",
    "cost_cap_usd": 100,
    "phase": sys.argv[4],
    "outcome": sys.argv[5],
    "teardown_approval": sys.argv[6],
    "configuration_evidence": "provider-verified" if sys.argv[4] in {"outcome", "teardown"} else "pending",
    "user_outcome_evidence": "provider-verified" if sys.argv[4] == "outcome" and sys.argv[5] == "verified" else "pending",
    "evidence_class": "provider-verified" if sys.argv[5] == "verified" else "unverified",
    "recorded_epoch": int(time.time()),
}
fd, temporary = tempfile.mkstemp(prefix=".canary-receipt-", dir=path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(document, output, sort_keys=True, separators=(",", ":"))
        output.write("\n")
    os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(temporary, path)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
}

write_handle() {
  python3 - "$handle" "$bucket_name" "$object_name" "$target_sha256" "$canary_sha256" <<'PY'
import json, os, pathlib, stat, sys, tempfile
path = pathlib.Path(sys.argv[1])
document = {
    "schema_version": 1,
    "bucket_name": sys.argv[2],
    "object_name": sys.argv[3],
    "target_sha256": sys.argv[4],
    "canary_sha256": sys.argv[5],
}
fd, temporary = tempfile.mkstemp(prefix=".canary-handle-", dir=path.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as output:
        json.dump(document, output, sort_keys=True, separators=(",", ":"))
        output.write("\n")
    os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(temporary, path)
    os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
}

error_class() {
  local file="$1" detail
  detail="$(cat "$file")"
  if printf '%s' "$detail" | grep -qiE 'NotAuthorizedOrNotFound|\b404\b'; then
    printf '%s' 'not-authorized-or-not-found'
  elif printf '%s' "$detail" | grep -qiE 'NotAuthenticated|\b401\b'; then
    printf '%s' 'not-authenticated'
  elif printf '%s' "$detail" | grep -qiE 'TooManyRequests|\b429\b|throttl|rate.?limit'; then
    printf '%s' 'throttled'
  elif printf '%s' "$detail" | grep -qiE 'LimitExceeded|ServiceLimitExceeded|quota|capacity'; then
    printf '%s' 'limit-or-capacity'
  elif printf '%s' "$detail" | grep -qiE 'JMESPath|invalid.*query|parse error|unknown token'; then
    printf '%s' 'query-syntax'
  else
    printf '%s' 'unclassified'
  fi
}

safe_summary() {
  local phase="$1" outcome="$2" detail="${3:-}"
  python3 - "$phase" "$outcome" "$detail" <<'PY'
import json, sys
result = {"canary": "private-object-storage", "phase": sys.argv[1], "outcome": sys.argv[2]}
if sys.argv[3]:
    result["detail"] = sys.argv[3]
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
PY
}

teardown_canary() {
  local handle_path receipt_path bucket existing_target receipt_target handle_count
  handle_count="$(find "$STATE_ROOT" -maxdepth 1 -type f -name '*.handle.json' -print | wc -l | tr -d '[:space:]')"
  [[ "$handle_count" == "1" ]] || die "teardown requires exactly one private canary handle in the selected state root"
  handle_path="$(find "$STATE_ROOT" -maxdepth 1 -type f -name '*.handle.json' -print -quit)"
  receipt_path="${handle_path%.handle.json}.receipt.json"
  [[ ! -L "$handle_path" && ! -L "$receipt_path" ]] || die "canary state files must not be symlinks"
  [[ -f "$handle_path" && -f "$receipt_path" ]] || die "canary state files are incomplete"
  read -r existing_target receipt_target < <(python3 - "$handle_path" "$receipt_path" <<'PY'
import json, pathlib, stat, sys
handle, receipt = (pathlib.Path(value) for value in sys.argv[1:])
for path in (handle, receipt):
    if path.is_symlink() or not path.is_file() or stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise SystemExit("invalid private canary state file")
handle_data = json.loads(handle.read_text(encoding="utf-8"))
receipt_data = json.loads(receipt.read_text(encoding="utf-8"))
if not isinstance(handle_data.get("bucket_name"), str) or not handle_data["bucket_name"]:
    raise SystemExit("invalid private canary handle")
if handle_data.get("target_sha256") != receipt_data.get("target_sha256"):
    raise SystemExit("canary state target binding disagrees")
print(handle_data["target_sha256"], receipt_data["target_sha256"])
PY
)
  [[ "$existing_target" == "$target_sha256" && "$receipt_target" == "$target_sha256" ]] \
    || die "canary state target binding does not match the selected context"
  bucket="$(python3 - "$handle_path" <<'PY'
import json, sys
print(json.load(open(sys.argv[1], encoding="utf-8"))["bucket_name"])
PY
)"
  if ! "$(dirname "$0")/oci_preflight.sh" -c "$COMPARTMENT_ID" >"$TEMP_DIR/preflight.log" 2>&1; then
    safe_summary "teardown" "failed" "target-verification-failed"
    return 1
  fi
  if ! run_action --risk destructive --compartment "$COMPARTMENT_ID" \
    --description "delete private disposable object-storage canary" -- \
    oci_cli os bucket delete --name "$bucket" --empty --force \
    >"$TEMP_DIR/delete.json" 2>"$TEMP_DIR/delete.err"; then
    safe_summary "teardown" "failed" "$(error_class "$TEMP_DIR/delete.err")"
    return 1
  fi
  if oci_cli os bucket get --name "$bucket" >"$TEMP_DIR/delete-get.json" 2>"$TEMP_DIR/delete-get.err"; then
    safe_summary "teardown" "failed" "resource-still-readable"
    return 1
  fi
  if ! grep -qiE 'NotAuthorizedOrNotFound|\b404\b' "$TEMP_DIR/delete-get.err"; then
    safe_summary "teardown" "failed" "absence-not-provider-confirmed"
    return 1
  fi
  rm -f "$handle_path" "$receipt_path"
  audit_log canary_teardown_provider_verified "phase=teardown" "owner=run-action" \
    "network_exposure=none" "cost_cap_usd=$COST_CAP_USD"
  safe_summary "teardown" "verified"
}

if [[ "$MODE" == "teardown" ]]; then
  teardown_canary
  exit $?
fi

# Capture preflight output because it contains tenancy and compartment display
# names. The preflight receipt it writes is still the required action binding.
if ! "$(dirname "$0")/oci_preflight.sh" -c "$COMPARTMENT_ID" >"$TEMP_DIR/preflight.log" 2>&1; then
  write_receipt "preflight" "failed"
  safe_summary "preflight" "failed" "target-verification-failed"
  exit 1
fi

if ! run_action --risk additive --compartment "$COMPARTMENT_ID" \
  --description "create private disposable object-storage canary" -- \
  oci_cli os bucket create --compartment-id "$COMPARTMENT_ID" --name "$bucket_name" \
    --public-access-type NoPublicAccess --versioning Enabled \
    >"$TEMP_DIR/create.json" 2>"$TEMP_DIR/create.err"; then
  write_receipt "create" "failed"
  safe_summary "create" "failed" "$(error_class "$TEMP_DIR/create.err")"
  exit 1
fi

write_handle

# Direct get avoids a brittle JMESPath list filter. jq evaluates only the two
# expected protection properties from a private temporary provider response.
if ! oci_cli os bucket get --name "$bucket_name" >"$TEMP_DIR/get.json" 2>"$TEMP_DIR/get.err"; then
  write_receipt "verify" "failed"
  safe_summary "verify" "failed" "$(error_class "$TEMP_DIR/get.err")"
  exit 1
fi
if ! jq -e '(.data["public-access-type"] == "NoPublicAccess") and (.data.versioning == "Enabled")' \
  "$TEMP_DIR/get.json" >/dev/null 2>"$TEMP_DIR/verify.err"; then
  write_receipt "verify" "failed"
  safe_summary "verify" "failed" "private-configuration-mismatch"
  exit 1
fi

# The object is deliberately content-free and private. Its distinct write/head
# path proves a downstream Object Storage outcome rather than treating the
# bucket lifecycle/configuration read as an end-to-end outcome.
marker_file="$TEMP_DIR/outcome-marker.txt"
printf '%s\n' 'private-canary-outcome-v1' >"$marker_file"
marker_bytes="$(wc -c <"$marker_file" | tr -d '[:space:]')"
if ! run_action --risk additive --compartment "$COMPARTMENT_ID" \
  --description "write private canary outcome marker" -- \
  oci_cli os object put --bucket-name "$bucket_name" --name "$object_name" \
    --file "$marker_file" --no-multipart --no-overwrite --verify-checksum \
    >"$TEMP_DIR/object-put.json" 2>"$TEMP_DIR/object-put.err"; then
  write_receipt "outcome" "failed"
  safe_summary "outcome" "failed" "$(error_class "$TEMP_DIR/object-put.err")"
  exit 1
fi
if ! oci_cli os object head --bucket-name "$bucket_name" --name "$object_name" \
  >"$TEMP_DIR/object-head.json" 2>"$TEMP_DIR/object-head.err"; then
  write_receipt "outcome" "failed"
  safe_summary "outcome" "failed" "$(error_class "$TEMP_DIR/object-head.err")"
  exit 1
fi
# Object Storage object-head exposes response headers at the JSON root, unlike
# bucket get. Accept either documented CLI envelope while verifying only the
# numeric content length, never object content or opaque response headers.
if ! jq -e --arg bytes "$marker_bytes" '((.data // .)["content-length"] | tostring) == $bytes' \
  "$TEMP_DIR/object-head.json" >/dev/null 2>"$TEMP_DIR/outcome.err"; then
  write_receipt "outcome" "failed"
  safe_summary "outcome" "failed" "outcome-marker-mismatch"
  exit 1
fi

delete_approval="$(action_approval_id --risk destructive --compartment "$COMPARTMENT_ID" \
  --description "delete private disposable object-storage canary" -- \
  oci_cli os bucket delete --name "$bucket_name" --empty --force)"
write_receipt "outcome" "verified" "$delete_approval"
audit_log canary_provider_verified "phase=outcome" "owner=run-action" \
  "network_exposure=none" "cost_cap_usd=$COST_CAP_USD"
safe_summary "outcome" "verified" "teardown-approval=$delete_approval"

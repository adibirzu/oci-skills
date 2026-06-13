#!/usr/bin/env bash
# common.sh — shared, tenancy-agnostic helpers for the OCI Administrator skill pack.
#
# Source this at the top of any script:
#     source "$(dirname "$0")/common.sh"
#
# Design goals:
#   - Work in ANY tenancy. No hardcoded OCIDs, IPs, regions, or profiles.
#   - One auth-negotiation path (config profile / instance / resource / OKE workload).
#   - Fail fast and loud on missing inputs; never silently swallow errors.
#   - Redact sensitive values before anything is printed or persisted.
#   - Default to safe: destructive actions require explicit confirmation.
#
# Environment inputs (all optional, sensible defaults):
#   OCI_CLI_PROFILE       config profile name (default: DEFAULT)
#   OCI_REGION            region override (default: profile/region setting)
#   OCI_AUTH_MODE         security_token | instance_principal | resource_principal |
#                         oke_workload | config (default: auto-detect)
#   OCI_SKILLS_FORCE      set to "true" to skip confirmation prompts (use with care)
#   OCI_SKILLS_DRY_RUN    set to "true" to print mutating commands instead of running

set -o errexit
set -o nounset
set -o pipefail

# Absolute directory of this file, so helpers can locate sibling scripts
# (e.g. redact.py) regardless of the caller's working directory.
_OCI_SKILLS_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

_oci_is_tty() { [[ -t 2 ]]; }

if _oci_is_tty; then
  _C_RESET=$'\033[0m'; _C_DIM=$'\033[2m'; _C_RED=$'\033[31m'
  _C_GREEN=$'\033[32m'; _C_YELLOW=$'\033[33m'; _C_BLUE=$'\033[34m'
else
  _C_RESET=""; _C_DIM=""; _C_RED=""; _C_GREEN=""; _C_YELLOW=""; _C_BLUE=""
fi

log()   { printf '%s[oci-skills]%s %s\n' "$_C_DIM" "$_C_RESET" "$*" >&2; }
info()  { printf '%s[info]%s %s\n'  "$_C_BLUE"   "$_C_RESET" "$*" >&2; }
ok()    { printf '%s[ok]%s %s\n'    "$_C_GREEN"  "$_C_RESET" "$*" >&2; }
warn()  { printf '%s[warn]%s %s\n'  "$_C_YELLOW" "$_C_RESET" "$*" >&2; }
err()   { printf '%s[error]%s %s\n' "$_C_RED"    "$_C_RESET" "$*" >&2; }
die()   { err "$*"; exit 1; }

banner() {
  local msg="$*"
  printf '%s\n== %s ==%s\n' "$_C_DIM" "$msg" "$_C_RESET" >&2
}

# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

# require_vars VAR1 VAR2 ... — die if any named variable is empty/unset.
require_vars() {
  local missing=()
  local name
  for name in "$@"; do
    if [[ -z "${!name:-}" ]]; then
      missing+=("$name")
    fi
  done
  if (( ${#missing[@]} > 0 )); then
    die "missing required variable(s): ${missing[*]} (set them in the environment or .env.local)"
  fi
}

# require_cmd CMD ... — die if any named command is not on PATH.
require_cmd() {
  local cmd
  for cmd in "$@"; do
    command -v "$cmd" >/dev/null 2>&1 || die "required command not found on PATH: $cmd"
  done
}

# ---------------------------------------------------------------------------
# Environment loading
# ---------------------------------------------------------------------------

# load_env [FILE] — source a dotenv file (default .env.local) WITHOUT clobbering
# PATH-like runtime variables. Lines are `KEY=value`; `#` comments allowed.
load_env() {
  local file="${1:-.env.local}"
  [[ -f "$file" ]] || { log "no env file at $file (skipping)"; return 0; }
  # Preserve runtime path variables that a dotenv must never overwrite.
  local _saved_path="$PATH" _saved_home="$HOME"
  set -a
  # shellcheck disable=SC1090
  source "$file"
  set +a
  PATH="$_saved_path"; HOME="$_saved_home"
  log "loaded env from $file"
}

# ---------------------------------------------------------------------------
# Auth-mode detection (no network call unless needed)
# ---------------------------------------------------------------------------

_OCI_IMDS_CACHE=""

# _imds_reachable — true if the instance metadata service answers quickly.
_imds_reachable() {
  if [[ -n "$_OCI_IMDS_CACHE" ]]; then
    [[ "$_OCI_IMDS_CACHE" == "yes" ]]
    return
  fi
  if curl -fsS -m 1 -H 'Authorization: Bearer Oracle' \
       http://169.254.169.254/opc/v2/instance/ >/dev/null 2>&1; then
    _OCI_IMDS_CACHE="yes"; return 0
  fi
  _OCI_IMDS_CACHE="no"; return 1
}

# resolve_auth_mode — echo the effective auth mode, auto-detecting when unset.
resolve_auth_mode() {
  local mode="${OCI_AUTH_MODE:-}"
  if [[ -n "$mode" ]]; then echo "$mode"; return 0; fi
  if [[ -n "${OCI_RESOURCE_PRINCIPAL_VERSION:-}" ]]; then echo "resource_principal"; return 0; fi
  if [[ -n "${KUBERNETES_SERVICE_HOST:-}" && -n "${OCI_RESOURCE_PRINCIPAL_RPST:-}" ]]; then
    echo "oke_workload"; return 0
  fi
  if _imds_reachable; then echo "instance_principal"; return 0; fi
  echo "config"
}

# ---------------------------------------------------------------------------
# OCI CLI wrapper — the one true entrypoint for every CLI call
# ---------------------------------------------------------------------------

# oci_cli ARGS... — invoke the OCI CLI with negotiated auth + region.
# Honors OCI_SKILLS_DRY_RUN for any call whose first arg implies mutation.
oci_cli() {
  require_cmd oci
  local mode; mode="$(resolve_auth_mode)"
  local -a auth_args=()
  case "$mode" in
    instance_principal)  auth_args=(--auth instance_principal) ;;
    resource_principal)  auth_args=(--auth resource_principal) ;;
    oke_workload)        auth_args=(--auth oke_workload_identity) ;;
    security_token)      auth_args=(--auth security_token) ;;
    config|*)            auth_args=() ;;  # default: config file + profile
  esac
  local -a base=(oci)
  # Expand auth_args defensively: in config mode it is empty, and bash 3.2
  # (the default /bin/bash on macOS) raises "unbound variable" under `set -u`
  # for "${empty[@]}". The ${arr[@]+...} guard is portable to bash 3.2+.
  base+=(${auth_args[@]+"${auth_args[@]}"})
  if [[ "$mode" == "config" && -n "${OCI_CLI_PROFILE:-}" ]]; then
    base+=(--profile "$OCI_CLI_PROFILE")
  fi
  if [[ -n "${OCI_REGION:-}" ]]; then
    base+=(--region "$OCI_REGION")
  fi
  "${base[@]}" "$@"
}

# ---------------------------------------------------------------------------
# Safety: confirmation + dry-run for mutating operations
# ---------------------------------------------------------------------------

# audit_log EVENT [KEY=VALUE ...] — append one redacted JSON line describing a
# skill action to the local action ledger. Best-effort observability: it NEVER
# fails the caller and NEVER persists secrets (the whole line is passed through
# the same redactor as the CI gate before it is written).
#
# Path resolution (all out of the repo tree by design, so it never shows up in
# `git status`):  $OCI_SKILLS_AUDIT_LOG  >  $XDG_STATE_HOME/oci-skills/audit.jsonl
#                 >  ~/.local/state/oci-skills/audit.jsonl
# Disable entirely with OCI_SKILLS_AUDIT_LOG=/dev/null or OCI_SKILLS_NO_AUDIT=1.
audit_log() {
  [[ "${OCI_SKILLS_NO_AUDIT:-}" == "1" ]] && return 0
  local event="${1:-unknown}"; shift 2>/dev/null || true
  local log_file="${OCI_SKILLS_AUDIT_LOG:-${XDG_STATE_HOME:-$HOME/.local/state}/oci-skills/audit.jsonl}"
  [[ "$log_file" == "/dev/null" ]] && return 0
  command -v python3 >/dev/null 2>&1 || return 0     # JSON build needs python; skip silently
  local dir; dir="$(dirname "$log_file")"
  mkdir -p "$dir" 2>/dev/null || { log "audit_log: cannot create $dir (skipping)"; return 0; }

  local ts mode
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"
  mode="$(resolve_auth_mode 2>/dev/null || echo unknown)"

  # python builds the JSON object (safe escaping) from fixed context + caller
  # KEY=VALUE extras, then applies redact.py's rules in-process before printing.
  OCI_AUDIT_REDACT="$_OCI_SKILLS_SCRIPT_DIR/redact.py" \
  python3 - "$ts" "$event" "$mode" "${OCI_CLI_PROFILE:-DEFAULT}" "${OCI_REGION:-}" \
            "${OCI_SKILLS_DRY_RUN:-false}" "${OCI_SKILLS_FORCE:-false}" "$@" \
            >> "$log_file" 2>/dev/null <<'PY' || true
import importlib.util, json, os, sys
ts, event, mode, profile, region, dry_run, forced, *extra = sys.argv[1:]
obj = {"ts": ts, "event": event, "auth_mode": mode, "profile": profile,
       "region": region, "dry_run": dry_run == "true", "forced": forced == "true"}
for kv in extra:
    key, sep, val = kv.partition("=")
    if key and sep:
        obj[key] = val
line = json.dumps(obj, separators=(",", ":"))
path = os.environ.get("OCI_AUDIT_REDACT", "")
try:
    spec = importlib.util.spec_from_file_location("redact", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["redact"] = mod          # register BEFORE exec so @dataclass resolves
    spec.loader.exec_module(mod)
    line = mod.redact(line)[0]           # mask any OCID/IP/secret before persisting
except Exception:
    sys.exit(0)                          # redactor unavailable -> persist nothing (fail closed)
print(line)
PY
}

# confirm "message" — return 0 if the user agrees (or OCI_SKILLS_FORCE=true).
confirm() {
  local msg="${1:-Proceed?}"
  if [[ "${OCI_SKILLS_FORCE:-}" == "true" ]]; then
    warn "OCI_SKILLS_FORCE=true — auto-confirming: $msg"
    audit_log confirm_forced "msg=$msg"
    return 0
  fi
  if ! _oci_is_tty; then
    audit_log confirm_refused_no_tty "msg=$msg"
    die "refusing destructive action without a TTY (set OCI_SKILLS_FORCE=true to override): $msg"
  fi
  local reply
  printf '%s%s [y/N] %s' "$_C_YELLOW" "$msg" "$_C_RESET" >&2
  read -r reply
  if [[ "$reply" =~ ^[Yy]([Ee][Ss])?$ ]]; then
    audit_log confirm_accepted "msg=$msg"
    return 0
  fi
  audit_log confirm_declined "msg=$msg"
  return 1
}

# run_mutating "description" CMD... — run a mutating command, or print it under dry-run.
run_mutating() {
  local desc="$1"; shift
  if [[ "${OCI_SKILLS_DRY_RUN:-}" == "true" ]]; then
    warn "DRY-RUN ($desc): $*"
    audit_log mutating_dry_run "desc=$desc"
    return 0
  fi
  info "$desc"
  audit_log mutating_run "desc=$desc"
  "$@"
}

# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------

# wait_for_state "FULL CLI PATH" RESOURCE_OCID TARGET_STATE [TIMEOUT_SEC]
# Polls `oci <full path> get` lifecycle-state at 10s intervals.
#
# "kind" MUST be the full CLI command path, e.g. "compute instance",
# "network vcn", "lb load-balancer". The id flag is derived from the LAST word:
#   "compute instance" -> --instance-id   "network vcn" -> --vcn-id
wait_for_state() {
  local kind="$1" ocid="$2" target="$3" timeout="${4:-300}"
  local last="${kind##* }"          # last word of the command path
  local id_flag="--${last}-id"
  # load-balancer lifecycle is exposed differently; callers can override the
  # query by passing OCI_SKILLS_STATE_QUERY, default to the standard field.
  local query="${OCI_SKILLS_STATE_QUERY:-data.\"lifecycle-state\"}"
  local waited=0 state
  while (( waited < timeout )); do
    # shellcheck disable=SC2086  # $kind is an intentional multi-word command path
    state="$(oci_cli ${kind} get "$id_flag" "$ocid" \
      --query "$query" --raw-output 2>/dev/null || true)"
    if [[ "$state" == "$target" ]]; then ok "$kind reached $target"; return 0; fi
    log "$kind state=${state:-<unknown>} (target=$target) waited=${waited}s"
    sleep 10; waited=$(( waited + 10 ))
  done
  die "timed out after ${timeout}s waiting for $kind to reach $target"
}

# ---------------------------------------------------------------------------
# Redaction — strip sensitive values before printing or committing
# ---------------------------------------------------------------------------

# redact STRING — echo STRING with OCIDs, IPs, and token-like blobs masked.
# Prefers the regex-complete, cross-platform scripts/redact.py. Falls back to a
# portable sed (BSD/macOS sed has no \b in -E, so we anchor with [^...] classes).
redact() {
  if command -v python3 >/dev/null 2>&1 \
     && [[ -f "$_OCI_SKILLS_SCRIPT_DIR/redact.py" ]]; then
    printf '%s' "$*" | python3 "$_OCI_SKILLS_SCRIPT_DIR/redact.py"
    return
  fi
  printf '%s' "$*" | sed -E \
    -e 's/ocid1\.[a-z0-9]+\.[a-z0-9-]*\.[a-z0-9-]*\.[a-z0-9]+/<OCID-REDACTED>/g' \
    -e 's/(^|[^0-9.])([0-9]{1,3}\.){3}[0-9]{1,3}([^0-9.]|$)/\1<IP-REDACTED>\3/g' \
    -e 's/(^|[^A-Fa-f0-9])[A-Fa-f0-9]{40,}([^A-Fa-f0-9]|$)/\1<HEX-REDACTED>\2/g'
}

# ---------------------------------------------------------------------------
# Tenancy preflight — call before any tenancy-scoped operation
# ---------------------------------------------------------------------------

# preflight_identity — confirm we can reach IAM and print the resolved tenancy
# NAME (never the OCID) so the operator can sanity-check which tenancy is live.
preflight_identity() {
  require_cmd oci jq
  local mode; mode="$(resolve_auth_mode)"
  info "auth mode: $mode  profile: ${OCI_CLI_PROFILE:-DEFAULT}  region: ${OCI_REGION:-<profile default>}"
  local tname
  tname="$(oci_cli iam region-subscription list --query 'data[0]."region-name"' --raw-output 2>/dev/null || true)"
  [[ -n "$tname" ]] || die "could not reach OCI IAM — check auth mode / profile / network"
  ok "IAM reachable (home region returned). Proceeding."
}

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
#   OCI_SKILLS_MAX_RETRIES  transient-failure retry budget for oci_cli (default 3)

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

# print_self_help — print the calling script's header doc-comment (every `#`
# line except the shebang) as help text. `$0` is the script that sourced us, so
# each domain script gets its own header. Call from a getopts `-h` branch.
print_self_help() {
  grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'
}

# context_header — print the resolved profile / region / auth-mode on one line.
# The shared "which identity am I about to use?" banner for read-only overviews.
context_header() {
  local mode; mode="$(resolve_auth_mode)"
  info "profile : ${OCI_CLI_PROFILE:-DEFAULT}   region: ${OCI_REGION:-<profile default>}   auth: $mode"
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

# resolve_tenancy_ocid [explicit] — echo the tenancy OCID, or empty if unknown.
# Precedence: explicit arg > $OCI_SKILLS_TENANCY > (config auth only) the active
# profile's `tenancy=` in ~/.oci/config / $OCI_CLI_CONFIG_FILE. Principal-based
# auth has no config to read, so the caller must supply it. Echoes nothing (not
# an error) when it cannot be resolved — the caller decides whether to die.
# shellcheck disable=SC2120  # [explicit] arg is optional; callers in other files pass it
resolve_tenancy_ocid() {
  local tenant="${1:-${OCI_SKILLS_TENANCY:-}}"
  if [[ -n "$tenant" ]]; then printf '%s' "$tenant"; return 0; fi
  [[ "$(resolve_auth_mode)" == "config" ]] || return 0
  local profile="${OCI_CLI_PROFILE:-DEFAULT}"
  awk -v p="[$profile]" '
      $0==p {f=1; next}
      /^\[/ {f=0}
      f && /^[[:space:]]*tenancy[[:space:]]*=/ {sub(/^[^=]*=[[:space:]]*/,""); print; exit}
    ' "${OCI_CLI_CONFIG_FILE:-$HOME/.oci/config}" 2>/dev/null | tr -d '[:space:]'
}

# resolve_compartment [explicit] — echo the compartment to operate in: the
# explicit arg if given, else $OCI_SKILLS_COMPARTMENT, else the tenancy root.
# Echoes empty if none can be resolved (caller decides whether to die).
resolve_compartment() {
  local explicit="${1:-${OCI_SKILLS_COMPARTMENT:-}}"
  if [[ -n "$explicit" ]]; then printf '%s' "$explicit"; return 0; fi
  resolve_tenancy_ocid
}

# ---------------------------------------------------------------------------
# OCI CLI wrapper — the one true entrypoint for every CLI call
# ---------------------------------------------------------------------------

# Verbs that change state. Used to decide whether a 5xx/transport failure is
# safe to retry: a rejected (throttled) request never reached the service, but a
# mutating request that 5xx'd may have partially applied, so it is NOT retried.
_OCI_MUTATING_RE='(create|update|delete|terminate|deregister|disable|enable|attach|detach|change-compartment|move|rotate|bulk-delete|restore|put-|upload|patch|schedule-|cancel)'

# _oci_retryable STDERR_TEXT KIND — return 0 if the failure is transient and the
# call may be retried. KIND is "read" or "mutating".
#   throttling (429/TooManyRequests/rate-limit) -> retry for ANY kind (the
#       request was rejected before processing, so re-issuing is safe)
#   5xx / transport timeout/reset               -> retry only for read calls
_oci_retryable() {
  local errtext="$1" kind="$2"
  if printf '%s' "$errtext" | grep -qiE 'TooManyRequests|\b429\b|throttl|rate.?limit'; then
    return 0
  fi
  if [[ "$kind" == "read" ]] && printf '%s' "$errtext" \
       | grep -qiE '\b50[0-9]\b|ServiceUnavailable|InternalServerError|BackendError|timed? ?out|Connection (reset|refused|aborted)|EOF occurred'; then
    return 0
  fi
  return 1
}

# oci_cli ARGS... — invoke the OCI CLI with negotiated auth + region, retrying
# transient failures with exponential backoff (OCI_SKILLS_MAX_RETRIES, default 3;
# delays 1,2,4,… s). Mutating calls retry only on throttling, never on 5xx.
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

  # Classify the call so we know whether a 5xx is retry-safe.
  local kind="read"
  if printf ' %s ' "$*" | grep -qiE "[ /]$_OCI_MUTATING_RE"; then
    kind="mutating"
  fi

  local max="${OCI_SKILLS_MAX_RETRIES:-3}" attempt=0 rc=0 errf
  errf="$(mktemp "${TMPDIR:-/tmp}/oci-cli-err.XXXXXX")"
  while :; do
    # Suspend errexit with `|| rc=$?` so we capture the call's REAL exit code.
    # NOTE: a bare `if cmd; then …; fi` with no else evaluates to 0 when cmd
    # fails, so reading `$?` after it would WRONGLY report success and mask
    # every non-retryable failure. `|| rc=$?` records the true code exactly.
    rc=0
    "${base[@]}" "$@" 2>"$errf" || rc=$?
    cat "$errf" >&2
    if [[ "$rc" -eq 0 ]]; then break; fi
    attempt=$(( attempt + 1 ))
    if (( attempt > max )) || ! _oci_retryable "$(cat "$errf")" "$kind"; then
      break
    fi
    local delay=$(( 1 << (attempt - 1) ))
    warn "oci_cli transient failure (rc=$rc, attempt ${attempt}/${max}, ${kind}) — retry in ${delay}s"
    sleep "$delay"
  done
  rm -f "$errf"
  return "$rc"
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

# _id_flag_for "FULL CLI PATH" — echo the OCID flag for a resource command path.
# Most resources flag on the last word ("compute instance" -> --instance-id), but
# several OCI resources are multi-word and the naive last-word rule is wrong
# ("compute instance" is fine, but "database autonomous-database" must be
# --autonomous-database-id, not --database-id; "lb load-balancer" must be
# --load-balancer-id). Match the known multi-word tails first, then fall back.
_id_flag_for() {
  case "$1" in
    *autonomous-container-database) echo "--autonomous-container-database-id" ;;
    *autonomous-database)      echo "--autonomous-database-id" ;;
    *network-load-balancer)    echo "--network-load-balancer-id" ;;
    *load-balancer)            echo "--load-balancer-id" ;;
    *db-system)                echo "--db-system-id" ;;
    *mount-target)             echo "--mount-target-id" ;;
    *file-system)              echo "--file-system-id" ;;
    *node-pool)                echo "--node-pool-id" ;;
    *boot-volume)              echo "--boot-volume-id" ;;
    *) echo "--${1##* }-id" ;;     # default: last word of the command path
  esac
}

# wait_for_state "FULL CLI PATH" RESOURCE_OCID TARGET_STATE [TIMEOUT_SEC]
# Polls `oci <full path> get` lifecycle-state at 10s intervals.
#
# "kind" MUST be the full CLI command path, e.g. "compute instance",
# "network vcn", "lb load-balancer". The id flag is derived by _id_flag_for,
# which handles multi-word resources (e.g. "database autonomous-database").
wait_for_state() {
  local kind="$1" ocid="$2" target="$3" timeout="${4:-300}"
  local id_flag; id_flag="$(_id_flag_for "$kind")"
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

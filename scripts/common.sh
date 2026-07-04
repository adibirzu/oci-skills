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
#   OCI_SKILLS_FORCE      audited break-glass override for confirmation prompts
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

# load_env [FILE] — parse a dotenv file (default .env.local) without evaluating
# it as shell. Only KEY=value records and full-line comments are accepted.
load_env() {
  local file="${1:-.env.local}"
  [[ -f "$file" ]] || { log "no env file at $file (skipping)"; return 0; }
  local line key value lineno=0
  while IFS= read -r line || [[ -n "$line" ]]; do
    lineno=$((lineno + 1))
    line="${line%$'\r'}"
    [[ "$line" =~ ^[[:space:]]*$ || "$line" =~ ^[[:space:]]*# ]] && continue
    if [[ ! "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)=(.*)$ ]]; then
      die "invalid dotenv record at $file:$lineno (expected KEY=value)"
    fi
    key="${BASH_REMATCH[1]}"; value="${BASH_REMATCH[2]}"
    case "$key" in
      PATH|HOME|IFS|SHELLOPTS|BASH_ENV|ENV|CDPATH|GLOBIGNORE|LD_PRELOAD|DYLD_*|\
      OCI_SKILLS_FORCE|OCI_SKILLS_BREAK_GLASS|OCI_SKILLS_APPROVAL|\
      OCI_SKILLS_PREFLIGHT_RECEIPT|OCI_SKILLS_CONTEXT_PROD)
        die "unsafe dotenv key at $file:$lineno: $key" ;;
    esac
    # Quoting is data-only: remove one matching outer quote pair but never
    # interpret escapes, substitutions, command separators, or redirects.
    if [[ "$value" =~ ^\"(.*)\"$ || "$value" =~ ^\'(.*)\'$ ]]; then
      value="${BASH_REMATCH[1]}"
    fi
    # shellcheck disable=SC2016 # The quoted tokens are intentionally literal.
    if [[ "$value" == *'$('* || "$value" == *'`'* || "$value" == *'${'* \
          || "$value" == *';'* || "$value" == *'&&'* || "$value" == *'||'* \
          || "$value" == '<('* || "$value" == '>('* ]]; then
      die "unsafe shell syntax in dotenv value at $file:$lineno"
    fi
    export "$key=$value"
  done < "$file"
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
# shellcheck disable=SC2120  # [explicit] arg is optional; callers in other files pass it
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
# skill action to the local action ledger. Normal observability is best-effort;
# break-glass callers set OCI_SKILLS_AUDIT_REQUIRED=true and fail closed. The
# whole line passes through the CI redactor before it is written.
#
# Path resolution (all out of the repo tree by design, so it never shows up in
# `git status`):  $OCI_SKILLS_AUDIT_LOG  >  $XDG_STATE_HOME/oci-skills/audit.jsonl
#                 >  ~/.local/state/oci-skills/audit.jsonl
# Disable entirely with OCI_SKILLS_AUDIT_LOG=/dev/null or OCI_SKILLS_NO_AUDIT=1.
audit_log() {
  local required="${OCI_SKILLS_AUDIT_REQUIRED:-false}"
  if [[ "${OCI_SKILLS_NO_AUDIT:-}" == "1" ]]; then
    [[ "$required" != "true" ]] || return 1
    return 0
  fi
  local event="${1:-unknown}"; shift 2>/dev/null || true
  local log_file="${OCI_SKILLS_AUDIT_LOG:-${XDG_STATE_HOME:-$HOME/.local/state}/oci-skills/audit.jsonl}"
  if [[ "$log_file" == "/dev/null" ]] || ! command -v python3 >/dev/null 2>&1; then
    [[ "$required" != "true" ]] || return 1
    return 0
  fi
  local dir; dir="$(dirname "$log_file")"
  if ! mkdir -p "$dir" 2>/dev/null; then
    log "audit_log: cannot create audit directory (skipping)"
    [[ "$required" != "true" ]] || return 1
    return 0
  fi

  local ts mode
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"
  mode="$(resolve_auth_mode 2>/dev/null || echo unknown)"

  # python builds the JSON object (safe escaping) from fixed context + caller
  # KEY=VALUE extras, applies redact.py's rules, then appends through O_NOFOLLOW
  # to a 0600 ledger. Any redaction or filesystem failure persists nothing.
  if ! OCI_AUDIT_REDACT="$_OCI_SKILLS_SCRIPT_DIR/redact.py" \
  python3 - "$log_file" "$ts" "$event" "$mode" "${OCI_CLI_PROFILE:-DEFAULT}" "${OCI_REGION:-}" \
            "${OCI_SKILLS_DRY_RUN:-false}" "${OCI_SKILLS_FORCE:-false}" "$@" \
            2>/dev/null <<'PY'
import importlib.util, json, os, sys
log_path, ts, event, mode, profile, region, dry_run, forced, *extra = sys.argv[1:]
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
    sys.exit(1)                          # redactor unavailable -> persist nothing (fail closed)
try:
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(log_path, flags, 0o600)
    try:
        os.fchmod(fd, 0o600)
        os.write(fd, (line + "\n").encode("utf-8"))
    finally:
        os.close(fd)
except OSError:
    sys.exit(1)
PY
  then
    [[ "$required" != "true" ]] || return 1
  fi
  return 0
}

# confirm "message" — return 0 if the user agrees (or OCI_SKILLS_FORCE=true).
confirm() {
  local msg="${1:-Proceed?}"
  if [[ "${OCI_SKILLS_FORCE:-}" == "true" ]]; then
    warn "OCI_SKILLS_FORCE=true — auto-confirming: $msg"
    OCI_SKILLS_AUDIT_REQUIRED=true audit_log confirm_forced "msg=$msg" \
      || die "forced confirmation requires a writable, redacted audit ledger"
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

# _action_context_hash COMPARTMENT — bind approvals/receipts to the selected
# identity without persisting an OCID, profile, or other topology value.
_action_context_hash() {
  local compartment="$1" tenancy
  tenancy="$(resolve_tenancy_ocid 2>/dev/null || true)"
  require_cmd python3
  python3 - "$compartment" "${OCI_SKILLS_CONTEXT:-}" "${OCI_CLI_PROFILE:-DEFAULT}" \
    "${OCI_REGION:-}" "$(resolve_auth_mode)" "$tenancy" <<'PY'
import hashlib, sys
payload = "\0".join(sys.argv[1:]).encode()
print(hashlib.sha256(payload).hexdigest())
PY
}

_preflight_receipt_path() {
  printf '%s' "${OCI_SKILLS_PREFLIGHT_RECEIPT:-${XDG_STATE_HOME:-$HOME/.local/state}/oci-skills/preflight.json}"
}

# record_preflight_receipt COMPARTMENT — called only after oci_preflight.sh has
# resolved the target successfully. The local 0600 receipt contains hashes only.
record_preflight_receipt() {
  local compartment="${1:-}" receipt context_hash now dir
  [[ -n "$compartment" ]] || die "record_preflight_receipt needs a compartment"
  receipt="$(_preflight_receipt_path)"; dir="$(dirname "$receipt")"
  context_hash="$(_action_context_hash "$compartment")"
  now="$(date +%s)"
  mkdir -p "$dir"
  python3 - "$receipt" "$context_hash" "$now" <<'PY'
import json, os, pathlib, stat, sys, tempfile
target = pathlib.Path(sys.argv[1])
target.parent.mkdir(parents=True, exist_ok=True)
fd, temporary = tempfile.mkstemp(prefix=".preflight-", dir=target.parent)
try:
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump({"schema_version": 1, "context_sha256": sys.argv[2],
                   "created_epoch": int(sys.argv[3])}, handle, separators=(",", ":"))
        handle.write("\n")
    os.chmod(temporary, stat.S_IRUSR | stat.S_IWUSR)
    os.replace(temporary, target)
    os.chmod(target, stat.S_IRUSR | stat.S_IWUSR)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
  audit_log preflight_receipt_recorded "context_sha256=$context_hash"
}

_require_preflight_receipt() {
  local compartment="$1" receipt expected ttl
  receipt="$(_preflight_receipt_path)"
  expected="$(_action_context_hash "$compartment")"
  ttl="${OCI_SKILLS_PREFLIGHT_TTL:-900}"
  if ! python3 - "$receipt" "$expected" "$ttl" <<'PY'
import json, pathlib, stat, sys, time
path, expected = pathlib.Path(sys.argv[1]), sys.argv[2]
if path.is_symlink() or not path.is_file():
    print("[error] preflight receipt must be an existing regular non-symlink file", file=sys.stderr)
    raise SystemExit(2)
try:
    data = json.loads(path.read_text(encoding="utf-8"))
    ttl = int(sys.argv[3])
    created = int(data.get("created_epoch", 0))
except (OSError, TypeError, ValueError, json.JSONDecodeError):
    print("[error] invalid preflight receipt", file=sys.stderr)
    raise SystemExit(2)
if data.get("context_sha256") != expected:
    print("[error] preflight receipt context does not match this action", file=sys.stderr)
    raise SystemExit(3)
now = int(time.time())
if ttl <= 0 or created > now + 5 or now - created > ttl:
    print("[error] preflight receipt expired", file=sys.stderr)
    raise SystemExit(4)
if stat.S_IMODE(path.stat().st_mode) != 0o600:
    print("[error] preflight receipt permissions must be 0600", file=sys.stderr)
    raise SystemExit(5)
PY
  then
    die "refusing live action until the exact context is preflighted again"
  fi
}

_parse_action_contract() {
  _ACTION_RISK=""; _ACTION_COMPARTMENT=""; _ACTION_DESCRIPTION=""
  while (( $# > 0 )); do
    case "$1" in
      --risk) _ACTION_RISK="${2:-}"; shift 2 ;;
      --compartment) _ACTION_COMPARTMENT="${2:-}"; shift 2 ;;
      --description) _ACTION_DESCRIPTION="${2:-}"; shift 2 ;;
      --) shift; break ;;
      *) die "unknown run_action option: $1" ;;
    esac
  done
  case "$_ACTION_RISK" in additive|in-place|destructive|credential) ;; *) die "invalid action risk: $_ACTION_RISK" ;; esac
  [[ -n "$_ACTION_COMPARTMENT" ]] || die "run_action requires --compartment"
  [[ -n "$_ACTION_DESCRIPTION" ]] || die "run_action requires --description"
  (( $# > 0 )) || die "run_action requires a command after --"
  _ACTION_COMMAND=("$@")
}

_action_hash() {
  local context_hash="$1" risk="$2" description="$3"; shift 3
  python3 - "$context_hash" "$risk" "$description" "$@" <<'PY'
import hashlib, pathlib, sys


def payload_path(argument):
    value = argument.split("=", 1)[-1]
    if not value.startswith("file://"):
        return None
    return pathlib.Path(value.removeprefix("file://"))


parts = list(sys.argv[1:])
for argument in sys.argv[4:]:
    path = payload_path(argument)
    if path is not None:
        try:
            payload_digest = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            print("[error] file:// payload changed or became unreadable", file=sys.stderr)
            raise SystemExit(2)
        parts.extend(("payload-sha256", payload_digest))
digest = hashlib.sha256("\0".join(parts).encode()).hexdigest()
print("approve-" + digest[:24])
PY
}

_validate_file_payloads() {
  python3 - "${_ACTION_COMMAND[@]}" <<'PY'
import pathlib, stat, sys


def payload_path(argument):
    value = argument.split("=", 1)[-1]
    if not value.startswith("file://"):
        return None
    return pathlib.Path(value.removeprefix("file://"))


for argument in sys.argv[1:]:
    path = payload_path(argument)
    if path is None:
        continue
    if path.is_symlink() or not path.is_file():
        print("[error] file:// payload must be an existing regular non-symlink file", file=sys.stderr)
        raise SystemExit(2)
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        print("[error] file:// payload permissions must be exactly 0600", file=sys.stderr)
        raise SystemExit(3)
PY
}

_validate_action_command() {
  local i arg flag value count="${#_ACTION_COMMAND[@]}"
  [[ "${_ACTION_COMMAND[0]}" != "oci" ]] \
    || die "bare OCI CLI execution is forbidden; route through oci_cli"
  for (( i=0; i<count; i++ )); do
    arg="${_ACTION_COMMAND[$i]}"; flag="${arg%%=*}"; value=""
    if [[ "$arg" == --*=* ]]; then
      value="${arg#*=}"
    elif [[ "$arg" == --* ]] && (( i + 1 < count )) \
      && [[ "${_ACTION_COMMAND[$((i + 1))]}" != --* ]]; then
      value="${_ACTION_COMMAND[$((i + 1))]}"
    fi
    case "$flag" in
      --password|--*-password|--credentials|--*-credentials|--auth-token|--*-auth-token|\
      --private-key|--*-private-key|--secret|--*-secret|--secret-content|--*-secret-content|\
      --key-content|--*-key-content|--token|--*-token)
        [[ "$value" == file://* ]] \
          || die "secret-bearing $flag requires a temporary 0600 file:// payload"
        ;;
    esac
    case "$flag" in
      --query|--description|--display-name) ;;
      --*)
        [[ "$value" != \{* && "$value" != \[* ]] \
          || die "nested JSON for $flag requires a temporary 0600 file:// payload"
        ;;
    esac
  done
  _validate_file_payloads || die "invalid file:// action payload"
}

# action_approval_id accepts the same contract as run_action and returns an ID
# bound to risk, context, description, and exact argv. It contains no secrets.
action_approval_id() {
  _parse_action_contract "$@"
  _validate_action_command
  local context_hash
  context_hash="$(_action_context_hash "$_ACTION_COMPARTMENT")"
  _action_hash "$context_hash" "$_ACTION_RISK" "$_ACTION_DESCRIPTION" "${_ACTION_COMMAND[@]}"
}

_command_preview() {
  local rendered="" arg quoted
  for arg in "$@"; do
    printf -v quoted '%q' "$arg"
    rendered="${rendered}${rendered:+ }${quoted}"
  done
  redact "$rendered"
}

_is_production_context() {
  [[ "${OCI_SKILLS_CONTEXT_PROD:-}" == "true" ]] && return 0
  [[ "${OCI_SKILLS_CONTEXT:-}" =~ (^|[-_.])(prod|production)([-_.]|$) ]]
}

# run_action --risk CLASS --compartment OCID --description TEXT -- COMMAND...
# All live actions require a recent, matching receipt. Destructive/credential
# actions additionally require an interactive confirmation or exact preview ID.
run_action() {
  _parse_action_contract "$@"
  _validate_action_command
  local approval preview
  approval="$(_action_hash "$(_action_context_hash "$_ACTION_COMPARTMENT")" \
    "$_ACTION_RISK" "$_ACTION_DESCRIPTION" "${_ACTION_COMMAND[@]}")"
  preview="$(_command_preview "${_ACTION_COMMAND[@]}")"

  if [[ "${OCI_SKILLS_DRY_RUN:-}" == "true" ]]; then
    warn "DRY-RUN [$_ACTION_RISK] ($_ACTION_DESCRIPTION): $preview"
    case "$_ACTION_RISK" in
      destructive|credential) warn "approval identifier: $approval" ;;
    esac
    audit_log action_preview "risk=$_ACTION_RISK" "desc=$_ACTION_DESCRIPTION" "approval=$approval"
    return 0
  fi

  _require_preflight_receipt "$_ACTION_COMPARTMENT"
  case "$_ACTION_RISK" in
    destructive|credential)
      if [[ "${OCI_SKILLS_FORCE:-}" == "true" ]]; then
        if _is_production_context && [[ "${OCI_SKILLS_BREAK_GLASS:-}" != "true" ]]; then
          die "production force requires OCI_SKILLS_BREAK_GLASS=true"
        fi
        warn "break-glass force accepted for $_ACTION_DESCRIPTION"
        OCI_SKILLS_AUDIT_REQUIRED=true audit_log action_break_glass \
          "risk=$_ACTION_RISK" "desc=$_ACTION_DESCRIPTION" "approval=$approval" \
          || die "break-glass force requires a writable, redacted audit ledger"
      elif [[ "${OCI_SKILLS_APPROVAL:-}" == "$approval" ]]; then
        audit_log action_approval_matched "risk=$_ACTION_RISK" "desc=$_ACTION_DESCRIPTION" "approval=$approval"
      elif _oci_is_tty; then
        confirm "$_ACTION_DESCRIPTION [approval $approval]?" || return 1
      else
        warn "approval identifier: $approval"
        die "non-interactive $_ACTION_RISK action requires matching OCI_SKILLS_APPROVAL"
      fi
      ;;
  esac
  info "$_ACTION_DESCRIPTION"
  audit_log action_run "risk=$_ACTION_RISK" "desc=$_ACTION_DESCRIPTION" "approval=$approval"
  "${_ACTION_COMMAND[@]}"
}

# Deprecated compatibility alias. It classifies legacy calls as additive; new
# code must call run_action directly with an explicit risk and compartment.
run_mutating() {
  local desc="${1:-}" compartment; shift || true
  warn "run_mutating is deprecated; use run_action --risk ..."
  compartment="$(resolve_compartment)"
  if [[ -z "$compartment" && "${OCI_SKILLS_DRY_RUN:-}" == "true" ]]; then
    compartment="<COMPARTMENT_OCID>"
  fi
  [[ -n "$compartment" ]] || die "run_mutating compatibility alias needs a bound compartment"
  run_action --risk additive --compartment "$compartment" --description "$desc" -- "$@"
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

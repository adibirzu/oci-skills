#!/usr/bin/env bash
# oci_logan.sh — run a read-only OCI Log Analytics (OCL) query with a friendly
# time window. Auto-resolves the LA namespace, computes the RFC3339 window, and
# executes `oci log-analytics query`. It runs ONLY a read query and prints rows;
# it changes nothing.
#
# Usage:
#     ./oci_logan.sh -q "<OCL query>"                       # last 24h, subtree
#     ./oci_logan.sh -q "<query>" -t 7d                     # last 7 days
#     ./oci_logan.sh -q "<query>" -c <COMPARTMENT_OCID>     # scope a compartment
#     ./oci_logan.sh -q "<query>" -n <LA_NAMESPACE>         # skip auto-resolve
#     ./oci_logan.sh -q "<query>" -m 200                    # max rows (default 50)
#     ./oci_logan.sh -q "<query>" -z Europe/Berlin          # time zone (default UTC)
#
# Time window (-t): <N><unit> where unit is m|h|d|w (default 24h).
# Env: OCI_CLI_PROFILE, OCI_REGION, OCI_AUTH_MODE, OCI_SKILLS_COMPARTMENT,
#      OCI_SKILLS_TENANCY, OCI_LA_NAMESPACE (see common.sh).

set -o errexit -o nounset -o pipefail
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"

QUERY=""
WINDOW="24h"
COMPARTMENT_OCID="${OCI_SKILLS_COMPARTMENT:-}"
NAMESPACE="${OCI_LA_NAMESPACE:-}"
TENANT_OCID="${OCI_SKILLS_TENANCY:-}"
MAX_ROWS=50
TZ_NAME="UTC"
SUBTREE="true"

while getopts ":q:t:c:n:m:z:Sh" opt; do
  case "$opt" in
    q) QUERY="$OPTARG" ;;
    t) WINDOW="$OPTARG" ;;
    c) COMPARTMENT_OCID="$OPTARG" ;;
    n) NAMESPACE="$OPTARG" ;;
    m) MAX_ROWS="$OPTARG" ;;
    z) TZ_NAME="$OPTARG" ;;
    S) SUBTREE="false" ;;
    h) print_self_help; exit 0 ;;
    *) die "usage: $0 -q QUERY [-t N{m|h|d|w}] [-c COMPARTMENT_OCID] [-n LA_NAMESPACE] [-m MAX_ROWS] [-z TZ] [-S]" ;;
  esac
done

[[ -n "$QUERY" ]] || die "missing -q QUERY (the OCL query string)"
[[ "$WINDOW" =~ ^[0-9]+[mhdw]$ ]] || die "time window (-t) must be <N>{m|h|d|w}, e.g. 24h, 7d"
[[ "$MAX_ROWS" =~ ^[0-9]+$ && "$MAX_ROWS" -gt 0 ]] || die "max rows (-m) must be a positive integer"

require_cmd oci jq python3

banner "OCI Log Analytics query"

mode="$(resolve_auth_mode)"
info "auth mode : $mode"
info "profile   : ${OCI_CLI_PROFILE:-DEFAULT}"
info "region    : ${OCI_REGION:-<profile default>}"

# Resolve the tenancy OCID (needed only to auto-resolve the namespace).
TENANT_OCID="$(resolve_tenancy_ocid "$TENANT_OCID")"

# Auto-resolve the LA namespace if not supplied.
if [[ -z "$NAMESPACE" ]]; then
  [[ -n "$TENANT_OCID" ]] \
    || die "cannot auto-resolve LA namespace — pass -n <LA_NAMESPACE> or set OCI_SKILLS_TENANCY"
  NAMESPACE="$(oci_cli log-analytics namespace list --compartment-id "$TENANT_OCID" \
    --query 'data.items[0]."namespace-name"' --raw-output 2>/dev/null || true)"
  [[ -n "$NAMESPACE" ]] \
    || die "Log Analytics is not onboarded in this tenancy, or the namespace could not be resolved"
fi
ok "namespace resolved (kept private)."

# Default the query compartment to the tenancy root if none given.
COMPARTMENT_OCID="${COMPARTMENT_OCID:-$TENANT_OCID}"
[[ -n "$COMPARTMENT_OCID" ]] \
  || die "no compartment to query — pass -c <COMPARTMENT_OCID> or set OCI_SKILLS_COMPARTMENT"

# Compute the RFC3339 window with python3 (portable across BSD/GNU date).
read -r START END <<EOF
$(python3 - "$WINDOW" <<'PY'
import datetime as dt, sys, re
m = re.match(r"^(\d+)([mhdw])$", sys.argv[1])
n, unit = int(m.group(1)), m.group(2)
secs = {"m": 60, "h": 3600, "d": 86400, "w": 604800}[unit] * n
end = dt.datetime.utcnow().replace(microsecond=0)
start = end - dt.timedelta(seconds=secs)
fmt = "%Y-%m-%dT%H:%M:%SZ"
print(start.strftime(fmt), end.strftime(fmt))
PY
)
EOF

info "window    : $START -> $END ($WINDOW, tz=$TZ_NAME)"
info "subtree   : $SUBTREE   max rows: $MAX_ROWS"
echo >&2

# Capture the query's stderr and exit code separately. The previous
# `2>/dev/null || true` discarded both, so an authorization denial (404/401)
# was indistinguishable from a genuinely empty result — a silent failure that
# hid permission problems behind a benign "nothing found" message.
errf="$(mktemp "${TMPDIR:-/tmp}/oci-logan-err.XXXXXX")"
if result="$(oci_cli log-analytics query search \
  --namespace-name "$NAMESPACE" \
  --compartment-id "$COMPARTMENT_OCID" \
  --compartment-id-in-subtree "$SUBTREE" \
  --query-string "$QUERY" \
  --sub-system LOG \
  --time-start "$START" \
  --time-end "$END" \
  --timezone "$TZ_NAME" \
  --max-total-count "$MAX_ROWS" 2>"$errf")"; then
  query_rc=0
else
  query_rc=$?
fi
errtext="$(cat "$errf" 2>/dev/null || true)"; rm -f "$errf"

# A non-zero exit is a real error, never an "empty result". Surface it — and
# call out the common authorization case explicitly so the user does not chase
# field typing or time windows when the service actually refused the request.
if [[ "$query_rc" -ne 0 ]]; then
  if printf '%s' "$errtext" | grep -qiE 'NotAuthorizedOrNotFound|not authoriz|forbidden|\b40[13]\b'; then
    err "authorization denied (or resource not found) — the service refused the query."
    err "Your principal likely lacks 'read loganalytics-* in tenancy' (or in the"
    err "queried compartment), or the namespace/compartment OCID is wrong."
    err "This is NOT an empty result; do not read it as 'nothing happened'."
  else
    err "query failed (rc=$query_rc) — the service returned an error:"
    printf '%s\n' "$errtext" | sed 's/^/    /' >&2
  fi
  exit "$query_rc"
fi

# The call succeeded. Zero rows now genuinely means "no matching data" — still
# inconclusive (the source may not be ingested here), but not an error.
rows="$(printf '%s' "$result" | jq -r '.data.items | length' 2>/dev/null || echo 0)"
if [[ -z "$result" || "$rows" == "0" ]]; then
  warn "query succeeded but returned no rows. Check: field typing (string vs"
  warn "numeric), the time window, the compartment scope (-c / subtree), and that"
  warn "the log source is actually ingested here. Inconclusive, not proof of absence."
  exit 0
fi

ok "rows: ${rows}"
# Print the result rows as compact JSON lines (pipe through redact at the call site
# if sharing). We never print the namespace or OCIDs here.
printf '%s' "$result" | jq -c '.data.items[]?' 2>/dev/null || printf '%s\n' "$result"

echo >&2
ok "query complete — read-only, nothing changed."

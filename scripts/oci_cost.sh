#!/usr/bin/env bash
# oci_cost.sh — read-only cost, usage, and budget summary for an OCI tenancy.
#
# Surfaces month-to-date-style spend by service plus any configured budgets, so a
# user can answer "what is this tenancy costing me?" without learning the Usage
# API. It performs ONLY read calls and prints no OCIDs (output is service names +
# amounts + budget display-names).
#
# Usage:
#     ./oci_cost.sh                          # last 30 days, DAILY, by service
#     ./oci_cost.sh -d 7                     # last 7 days
#     ./oci_cost.sh -g MONTHLY -d 90         # monthly granularity, last 90 days
#     ./oci_cost.sh -c <COMPARTMENT_OCID>    # scope budget lookup to a compartment
#     ./oci_cost.sh -t <TENANCY_OCID>        # override tenancy (principal auth)
#
# Env: OCI_CLI_PROFILE, OCI_REGION, OCI_AUTH_MODE, OCI_SKILLS_TENANCY (see common.sh).
# Requires the caller's identity to have `usage-reports` read on the tenancy.

set -o errexit -o nounset -o pipefail
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"

DAYS=30
GRAN="DAILY"
TOP=10
COMPARTMENT_OCID=""
TENANT_OCID="${OCI_SKILLS_TENANCY:-}"

while getopts ":d:g:c:t:n:h" opt; do
  case "$opt" in
    d) DAYS="$OPTARG" ;;
    g) GRAN="$OPTARG" ;;
    c) COMPARTMENT_OCID="$OPTARG" ;;
    t) TENANT_OCID="$OPTARG" ;;
    n) TOP="$OPTARG" ;;
    h) grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "usage: $0 [-d DAYS] [-g DAILY|MONTHLY] [-c COMPARTMENT_OCID] [-t TENANCY_OCID] [-n TOP_N]" ;;
  esac
done

case "$GRAN" in DAILY|MONTHLY) ;; *) die "granularity must be DAILY or MONTHLY (got: $GRAN)" ;; esac
[[ "$DAYS" =~ ^[0-9]+$ && "$DAYS" -gt 0 ]] || die "days (-d) must be a positive integer"
[[ "$TOP"  =~ ^[0-9]+$ && "$TOP"  -gt 0 ]] || die "top (-n) must be a positive integer"

require_cmd oci jq python3

banner "OCI cost summary"

mode="$(resolve_auth_mode)"
info "auth mode : $mode"
info "profile   : ${OCI_CLI_PROFILE:-DEFAULT}"
info "region    : ${OCI_REGION:-<profile default>}"

# Resolve the tenancy OCID. The Usage API is tenancy-scoped and needs it
# explicitly. For config auth we read it from ~/.oci/config; principal-based auth
# must supply it via -t or OCI_SKILLS_TENANCY since there is no config to read.
if [[ -z "$TENANT_OCID" && "$mode" == "config" ]]; then
  profile="${OCI_CLI_PROFILE:-DEFAULT}"
  TENANT_OCID="$(awk -v p="[$profile]" '
      $0==p {f=1; next}
      /^\[/ {f=0}
      f && /^[[:space:]]*tenancy[[:space:]]*=/ {sub(/^[^=]*=[[:space:]]*/,""); print; exit}
    ' "${OCI_CLI_CONFIG_FILE:-$HOME/.oci/config}" 2>/dev/null | tr -d '[:space:]')"
fi
[[ -n "$TENANT_OCID" ]] \
  || die "cannot determine tenancy OCID — set OCI_SKILLS_TENANCY or pass -t (required for principal auth)"

# Compute granularity-aligned UTC timestamps with python3 (portable across
# BSD/GNU date). DAILY/MONTHLY both require a midnight-UTC start; the API end is
# exclusive and must also land on a boundary, so we use today at 00:00:00Z.
read -r START END <<EOF
$(python3 - "$DAYS" "$GRAN" <<'PY'
import datetime as dt, sys
days, gran = int(sys.argv[1]), sys.argv[2]
end = dt.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
start = end - dt.timedelta(days=days)
if gran == "MONTHLY":
    start = start.replace(day=1)
    end = end.replace(day=1)
    if start == end:  # same month -> widen to the previous month start
        prev = (start - dt.timedelta(days=1)).replace(day=1)
        start = prev
fmt = "%Y-%m-%dT%H:%M:%SZ"
print(start.strftime(fmt), end.strftime(fmt))
PY
)
EOF

info "window    : $START -> $END ($GRAN)"
echo >&2

usage_json="$(oci_cli usage-api usage-summary request-summarized-usages \
  --tenant-id "$TENANT_OCID" \
  --time-usage-started "$START" \
  --time-usage-ended "$END" \
  --granularity "$GRAN" \
  --query-type COST \
  --group-by '["service"]' 2>/dev/null || true)"

if [[ -z "$usage_json" ]]; then
  warn "usage-api returned nothing — the identity likely lacks 'usage-reports' read,"
  warn "or the tenancy/region is wrong. Required policy (tenancy root):"
  warn "  allow group <g> to read usage-report in tenancy"
else
  # Aggregate computed-amount per service, descending, with a grand total.
  total_line="$(printf '%s' "$usage_json" | jq -r '
    [.data.items[]? | select(.["computed-amount"] != null)] as $rows
    | ($rows | map(.["computed-amount"]) | add // 0) as $total
    | ($rows[0].currency // "") as $cur
    | "TOTAL\t\($total)\t\($cur)"')"

  ok "spend by service (top $TOP):"
  printf '%s' "$usage_json" | jq -r --argjson top "$TOP" '
    [.data.items[]? | select(.["computed-amount"] != null)]
    | group_by(.service)
    | map({service: (.[0].service // "<unattributed>"),
           amount: (map(.["computed-amount"]) | add),
           currency: (.[0].currency // "")})
    | sort_by(-.amount)
    | .[:$top][]
    | "  \(.amount | . * 100 | round / 100)\t\(.currency)\t\(.service)"' \
    | column -t -s$'\t' >&2 || true

  echo >&2
  amount="$(printf '%s' "$total_line" | cut -f2)"
  cur="$(printf '%s' "$total_line" | cut -f3)"
  rounded="$(python3 -c "print(f'{float('${amount:-0}'):.2f}')" 2>/dev/null || echo "$amount")"
  ok "total spend ${START%%T*}..${END%%T*}: ${rounded} ${cur}"
fi

echo >&2
# Budgets live in the compartment they were created against (commonly tenancy root).
budget_scope="${COMPARTMENT_OCID:-$TENANT_OCID}"
budget_json="$(oci_cli budgets budget budget list --compartment-id "$budget_scope" \
  --query 'data[].{name:"display-name",amount:amount,spent:"actual-spend",forecast:"forecasted-spend",period:"reset-period"}' \
  2>/dev/null || true)"

if [[ -z "$budget_json" || "$budget_json" == "[]" || "$budget_json" == "null" ]]; then
  info "no budgets found in the selected compartment scope."
  info "create one: console > Billing & Cost Management > Budgets (alerts at % of spend)."
else
  ok "budgets:"
  printf '%s' "$budget_json" | jq -r '
    .[] | "  \(.name)\tlimit=\(.amount)\tspent=\(.spent // 0)\tforecast=\(.forecast // 0)\t\(.period)"' \
    | column -t -s$'\t' >&2 || true
fi

echo >&2
ok "cost summary complete — read-only, no resources changed."

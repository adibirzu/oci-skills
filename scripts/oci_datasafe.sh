#!/usr/bin/env bash
# oci_datasafe.sh — read-only OCI Data Safe overview: list registered target
# databases in a compartment and each target's latest security-assessment state.
# Changes nothing. Output is display names + states, no OCIDs.
#
# Usage:
#     ./oci_datasafe.sh                          # targets in the default compartment
#     ./oci_datasafe.sh -c <COMPARTMENT_OCID>    # scope a compartment
#     ./oci_datasafe.sh -n 50                    # max targets (default 25)
#
# Env: OCI_CLI_PROFILE, OCI_REGION, OCI_AUTH_MODE, OCI_SKILLS_COMPARTMENT,
#      OCI_SKILLS_TENANCY (see common.sh).

set -o errexit -o nounset -o pipefail
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"

COMPARTMENT_OCID="${OCI_SKILLS_COMPARTMENT:-}"
TENANT_OCID="${OCI_SKILLS_TENANCY:-}"
MAX=25

while getopts ":c:n:h" opt; do
  case "$opt" in
    c) COMPARTMENT_OCID="$OPTARG" ;;
    n) MAX="$OPTARG" ;;
    h) grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) die "usage: $0 [-c COMPARTMENT_OCID] [-n MAX]" ;;
  esac
done
[[ "$MAX" =~ ^[0-9]+$ && "$MAX" -gt 0 ]] || die "max (-n) must be a positive integer"

require_cmd oci jq

banner "OCI Data Safe — targets (read-only)"
mode="$(resolve_auth_mode)"
info "profile : ${OCI_CLI_PROFILE:-DEFAULT}   region: ${OCI_REGION:-<profile default>}   auth: $mode"

if [[ -z "$COMPARTMENT_OCID" ]]; then
  if [[ -z "$TENANT_OCID" && "$mode" == "config" ]]; then
    profile="${OCI_CLI_PROFILE:-DEFAULT}"
    TENANT_OCID="$(awk -v p="[$profile]" '
        $0==p {f=1; next} /^\[/ {f=0}
        f && /^[[:space:]]*tenancy[[:space:]]*=/ {sub(/^[^=]*=[[:space:]]*/,""); print; exit}
      ' "${OCI_CLI_CONFIG_FILE:-$HOME/.oci/config}" 2>/dev/null | tr -d '[:space:]')"
  fi
  COMPARTMENT_OCID="$TENANT_OCID"
fi
[[ -n "$COMPARTMENT_OCID" ]] || die "no compartment — pass -c <COMPARTMENT_OCID> or set OCI_SKILLS_COMPARTMENT"
echo >&2

targets="$(oci_cli data-safe target-database list --compartment-id "$COMPARTMENT_OCID" \
  --limit "$MAX" \
  --query 'data[].{name:"display-name",id:id,state:"lifecycle-state"}' 2>/dev/null || true)"

count="$(printf '%s' "$targets" | jq 'length' 2>/dev/null || echo 0)"
if [[ -z "$targets" || "$count" == "0" ]]; then
  info "no Data Safe target databases in this compartment (or Data Safe is not enabled)."
  exit 0
fi
ok "targets: $count"

printf '%s' "$targets" | jq -c '.[]' | while read -r row; do
  name="$(printf '%s' "$row" | jq -r '.name')"
  tid="$(printf '%s' "$row" | jq -r '.id')"
  tstate="$(printf '%s' "$row" | jq -r '.state')"
  sa="$(oci_cli data-safe security-assessment list --compartment-id "$COMPARTMENT_OCID" \
    --target-id "$tid" --limit 1 \
    --query 'data[0].{state:"lifecycle-state",ttype:"triggered-by"}' 2>/dev/null || true)"
  if [[ -n "$sa" && "$sa" != "null" ]]; then
    sstate="$(printf '%s' "$sa" | jq -r '.state // "-"')"
    printf '  %-40s %-16s security-assessment: %s\n' "$name" "$tstate" "$sstate" >&2
  else
    printf '  %-40s %-16s security-assessment: (none)\n' "$name" "$tstate" >&2
  fi
done

echo >&2
ok "Data Safe overview complete — read-only, nothing changed."

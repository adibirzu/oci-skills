#!/usr/bin/env bash
# oci_adb.sh — read-only OCI Autonomous Database overview: list ADB/ADW/ATP
# instances in a compartment with lifecycle state, workload, ECPU/storage,
# auto-scaling, and mTLS requirement. Changes nothing. Prints display names +
# states only, never OCIDs, DSNs, or wallet contents.
#
# Usage:
#     ./oci_adb.sh                          # ADBs in the default/context compartment
#     ./oci_adb.sh -c <COMPARTMENT_OCID>    # scope a compartment
#     ./oci_adb.sh -n 50                    # max instances (default 25)
#
# Env: OCI_CLI_PROFILE, OCI_REGION, OCI_AUTH_MODE, OCI_SKILLS_COMPARTMENT,
#      OCI_SKILLS_TENANCY (see common.sh).

set -o errexit -o nounset -o pipefail
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"

COMPARTMENT_OCID="${OCI_SKILLS_COMPARTMENT:-}"
MAX=25

while getopts ":c:n:h" opt; do
  case "$opt" in
    c) COMPARTMENT_OCID="$OPTARG" ;;
    n) MAX="$OPTARG" ;;
    h) print_self_help; exit 0 ;;
    *) die "usage: $0 [-c COMPARTMENT_OCID] [-n MAX]" ;;
  esac
done
[[ "$MAX" =~ ^[0-9]+$ && "$MAX" -gt 0 ]] || die "max (-n) must be a positive integer"

require_cmd oci jq

banner "OCI Autonomous Database — instances (read-only)"
context_header

COMPARTMENT_OCID="$(resolve_compartment "$COMPARTMENT_OCID")"
[[ -n "$COMPARTMENT_OCID" ]] || die "no compartment — pass -c <COMPARTMENT_OCID> or set OCI_SKILLS_COMPARTMENT"
echo >&2

# NOTE: `db autonomous-database list` has no subtree flag — this scopes one
# compartment. To sweep a tenancy, iterate compartments and re-run.
dbs="$(oci_cli db autonomous-database list --compartment-id "$COMPARTMENT_OCID" \
  --limit "$MAX" \
  --query 'data[].{name:"display-name",state:"lifecycle-state",workload:"db-workload",ecpu:"compute-count",tb:"data-storage-size-in-tbs",gb:"data-storage-size-in-gbs",autoscale:"is-auto-scaling-enabled",mtls:"is-mtls-connection-required",freeform:"private-endpoint"}' 2>/dev/null || true)"

count="$(printf '%s' "$dbs" | jq 'length' 2>/dev/null || echo 0)"
if [[ -z "$dbs" || "$count" == "0" ]]; then
  warn "no Autonomous Databases found in this compartment (or insufficient permissions)."
  ok "Autonomous DB overview complete — read-only, nothing changed."
  exit 0
fi

printf '%s' "$dbs" | jq -c '.[]' | while read -r row; do
  name="$(printf '%s' "$row" | jq -r '.name // "-"')"
  state="$(printf '%s' "$row" | jq -r '.state // "-"')"
  workload="$(printf '%s' "$row" | jq -r '.workload // "-"')"
  ecpu="$(printf '%s' "$row" | jq -r '.ecpu // "-"')"
  # ECPU-model ADBs report storage in GB (tb is null); legacy OCPU report TB.
  storage="$(printf '%s' "$row" | jq -r 'if (.gb // 0) > 0 then "\(.gb)GB" elif (.tb // 0) > 0 then "\(.tb)TB" else "-" end')"
  autoscale="$(printf '%s' "$row" | jq -r 'if .autoscale == true then "autoscale" else "fixed" end')"
  mtls="$(printf '%s' "$row" | jq -r 'if .mtls == false then "TLS-ok" else "mTLS" end')"
  pe="$(printf '%s' "$row" | jq -r 'if .freeform == null then "public" else "private-ep" end')"
  printf '  %-32s %-12s %-4s ecpu:%-4s %-7s %-9s %-7s %s\n' \
    "$name" "$state" "$workload" "$ecpu" "$storage" "$autoscale" "$mtls" "$pe" >&2
done

echo >&2
warn "STOPPED instances reject connections; a stopped ADB also stalls app startup (KB-118)."
ok "Autonomous DB overview complete — read-only, nothing changed."

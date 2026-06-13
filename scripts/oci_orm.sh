#!/usr/bin/env bash
# oci_orm.sh — read-only OCI Resource Manager (ORM) overview: list stacks in a
# compartment and the latest job (operation + state) for each. Changes nothing —
# it never creates a plan/apply/destroy job. Output is display names + states,
# no OCIDs.
#
# Usage:
#     ./oci_orm.sh                          # stacks in the default compartment
#     ./oci_orm.sh -c <COMPARTMENT_OCID>    # scope a compartment
#     ./oci_orm.sh -n 50                    # max stacks (default 25)
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

banner "OCI Resource Manager — stacks (read-only)"
context_header

# Default the compartment to the tenancy root if none given.
COMPARTMENT_OCID="$(resolve_compartment "$COMPARTMENT_OCID")"
[[ -n "$COMPARTMENT_OCID" ]] || die "no compartment — pass -c <COMPARTMENT_OCID> or set OCI_SKILLS_COMPARTMENT"
echo >&2

stacks="$(oci_cli resource-manager stack list --compartment-id "$COMPARTMENT_OCID" \
  --lifecycle-state ACTIVE --limit "$MAX" \
  --query 'data[].{name:"display-name",id:id,state:"lifecycle-state"}' 2>/dev/null || true)"

count="$(printf '%s' "$stacks" | jq 'length' 2>/dev/null || echo 0)"
if [[ -z "$stacks" || "$count" == "0" ]]; then
  info "no active stacks in this compartment."
  exit 0
fi
ok "active stacks: $count"

# For each stack, fetch the latest job (operation + state). Stack OCIDs are read
# transiently to query jobs but are never printed.
printf '%s' "$stacks" | jq -c '.[]' | while read -r row; do
  name="$(printf '%s' "$row" | jq -r '.name')"
  sid="$(printf '%s' "$row" | jq -r '.id')"
  sstate="$(printf '%s' "$row" | jq -r '.state')"
  job="$(oci_cli resource-manager job list --stack-id "$sid" --limit 1 \
    --query 'data[0].{op:operation,state:"lifecycle-state"}' 2>/dev/null || true)"
  if [[ -n "$job" && "$job" != "null" ]]; then
    op="$(printf '%s' "$job" | jq -r '.op // "-"')"
    jstate="$(printf '%s' "$job" | jq -r '.state // "-"')"
    printf '  %-40s %-10s last-job: %s=%s\n' "$name" "$sstate" "$op" "$jstate" >&2
  else
    printf '  %-40s %-10s last-job: (none)\n' "$name" "$sstate" >&2
  fi
done

echo >&2
ok "ORM overview complete — read-only, nothing changed."

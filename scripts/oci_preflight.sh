#!/usr/bin/env bash
# oci_preflight.sh — confirm WHICH tenancy/compartment you are about to act on.
#
# Run this before any administrative change. It prints the resolved tenancy and
# (optionally) a compartment name so you can verify you are not pointed at the
# wrong account. It performs ONLY read calls and never prints raw OCIDs.
#
# Usage:
#     ./oci_preflight.sh                      # show tenancy + auth context
#     ./oci_preflight.sh -c <COMPARTMENT_OCID> # also resolve a compartment name
#
# Env: OCI_CLI_PROFILE, OCI_REGION, OCI_AUTH_MODE (see common.sh).

set -o errexit -o nounset -o pipefail
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"

COMPARTMENT_OCID=""
while getopts ":c:h" opt; do
  case "$opt" in
    c) COMPARTMENT_OCID="$OPTARG" ;;
    h) print_self_help; exit 0 ;;
    *) die "usage: $0 [-c COMPARTMENT_OCID]" ;;
  esac
done

require_cmd oci jq

banner "OCI preflight"

mode="$(resolve_auth_mode)"
info "auth mode : $mode"
info "profile   : ${OCI_CLI_PROFILE:-DEFAULT}"
info "region    : ${OCI_REGION:-<profile default>}"

# Resolve the tenancy NAME (not OCID) so the operator can eyeball the target.
# For config auth the tenancy OCID comes from ~/.oci/config; for principal-based
# auth (no config) it is empty unless OCI_SKILLS_TENANCY is set, in which case we
# fall back to the object-storage namespace as a stable, non-secret fingerprint.
tenancy_name=""
tenancy_ocid="$(resolve_tenancy_ocid)"
if [[ -n "$tenancy_ocid" ]]; then
  tenancy_name="$(oci_cli iam tenancy get --tenancy-id "$tenancy_ocid" \
    --query 'data.name' --raw-output 2>/dev/null || true)"
fi

if [[ -n "$tenancy_name" ]]; then
  ok "tenancy: $tenancy_name"
else
  # Namespace is a stable per-tenancy fingerprint; we resolve it to prove
  # reachability but keep it private rather than printing it.
  ns="$(oci_cli os ns get --raw-output 2>/dev/null || true)"
  [[ -n "$ns" ]] || die "cannot reach OCI — auth/profile/network problem"
  ok "tenancy reachable (namespace resolved, kept private)."
fi

home_region="$(oci_cli iam region-subscription list \
  --query "data[?\"is-home-region\"].\"region-name\" | [0]" --raw-output 2>/dev/null || true)"
[[ -n "$home_region" ]] && info "home region: $home_region"

if [[ -n "$COMPARTMENT_OCID" ]]; then
  cname="$(oci_cli iam compartment get --compartment-id "$COMPARTMENT_OCID" \
    --query 'data.name' --raw-output 2>/dev/null || true)"
  if [[ -n "$cname" ]]; then
    ok "compartment: $cname"
  else
    warn "could not resolve compartment name (check OCID / permissions)"
  fi
fi

ok "preflight complete — verify the tenancy/compartment above before mutating anything."

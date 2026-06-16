#!/usr/bin/env bash
# oci_project.sh — OCI project lifecycle helper.
#
# Orchestrates the project lifecycle on top of the nine domain skills, scoped to
# ONE project compartment. Three subcommands:
#
#   status     (default) read-only health: inventory + states + open security
#              problems + alarms + budget, by COUNT and NAME — never OCIDs.
#   bootstrap  idempotent, gated scaffold: ensure the project compartment, a
#              cost-tracking-style project tag, and a budget; then EMIT the gated
#              IAM-policy and VCN commands (those belong to their domain skills).
#   teardown   READ-ONLY: inventory the compartment and print the ordered, gated
#              destroy plan. It destroys NOTHING — you run the steps via the
#              domain skills so each passes confirm / run_mutating.
#
# Usage:
#   ./oci_project.sh status               [-c COMPARTMENT_OCID]
#   ./oci_project.sh bootstrap -n NAME    -c PARENT_COMPARTMENT_OCID [-b BUDGET]
#   ./oci_project.sh teardown             -c COMPARTMENT_OCID
#
# Env: OCI_SKILLS_COMPARTMENT (default compartment), OCI_CLI_PROFILE, OCI_REGION,
#      OCI_AUTH_MODE, OCI_SKILLS_DRY_RUN (bootstrap prints instead of creating).
# Read calls only for status/teardown; bootstrap mutations go through run_mutating.

set -o errexit -o nounset -o pipefail
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"

CMD="${1:-status}"
case "$CMD" in status|bootstrap|teardown) shift ;; -h|--help) CMD="help" ;; esac

COMPARTMENT_OCID="${OCI_SKILLS_COMPARTMENT:-}"
NAME=""
BUDGET=""

if [ "$CMD" != "help" ]; then
  while getopts ":c:n:b:h" opt; do
    case "$opt" in
      c) COMPARTMENT_OCID="$OPTARG" ;;
      n) NAME="$OPTARG" ;;
      b) BUDGET="$OPTARG" ;;
      h) CMD="help" ;;
      *) die "usage: $0 {status|bootstrap|teardown} [-c COMPARTMENT] [-n NAME] [-b BUDGET]" ;;
    esac
  done
fi

usage() {
  cat >&2 <<'EOF'
oci_project.sh — OCI project lifecycle helper

  status     [-c COMPARTMENT]              read-only health (default)
  bootstrap  -n NAME -c PARENT [-b BUDGET] idempotent, gated scaffold
  teardown   -c COMPARTMENT                read-only inventory + ordered destroy plan

Env: OCI_SKILLS_COMPARTMENT, OCI_CLI_PROFILE, OCI_REGION, OCI_AUTH_MODE,
     OCI_SKILLS_DRY_RUN=true (bootstrap prints mutations instead of running them).
EOF
}

# _len JSON  -> element count of .data (0 on empty/parse error)
_len() { printf '%s' "${1:-}" | jq -r '(.data // []) | length' 2>/dev/null || echo 0; }

# _states JSON FIELD -> "STATE:n, STATE:n" grouped by lifecycle field
_states() {
  printf '%s' "${1:-}" | jq -r --arg f "${2:-lifecycle-state}" '
    (.data // []) | group_by(.[$f]) | map("\(.[0][$f] // "?"):\(length)") | join(", ")
  ' 2>/dev/null || echo ""
}

require_cmd oci jq

# --------------------------------------------------------------------------- #
cmd_help() { usage; }

# --------------------------------------------------------------------------- #
cmd_status() {
  [ -n "$COMPARTMENT_OCID" ] || die "no compartment — pass -c or set OCI_SKILLS_COMPARTMENT (bind a context first)"
  banner "OCI project status (read-only)"
  info "auth mode : $(resolve_auth_mode)"
  info "profile   : ${OCI_CLI_PROFILE:-DEFAULT}"
  info "region    : ${OCI_REGION:-<profile default>}"
  info "scope     : compartment $(redact "$COMPARTMENT_OCID")"
  echo >&2

  local j
  j="$(oci_cli compute instance list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  ok  "compute   : $(_len "$j") instance(s)   [$(_states "$j")]"

  j="$(oci_cli network vcn list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  ok  "network   : $(_len "$j") VCN(s)"

  j="$(oci_cli ce cluster list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  ok  "OKE       : $(_len "$j") cluster(s)   [$(_states "$j")]"

  j="$(oci_cli lb load-balancer list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  ok  "load-bal. : $(_len "$j") load balancer(s)"

  j="$(oci_cli cloud-guard problem list --compartment-id "$COMPARTMENT_OCID" \
        --lifecycle-state ACTIVE --all 2>/dev/null || true)"
  local probs; probs="$(_len "$j")"
  if [ "$probs" -gt 0 ] 2>/dev/null; then warn "security  : $probs ACTIVE Cloud Guard problem(s) — triage (oci-security-compliance)"
  else ok "security  : 0 ACTIVE Cloud Guard problems"; fi

  j="$(oci_cli monitoring alarm list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  ok  "alarms    : $(_len "$j") alarm definition(s)"

  j="$(oci_cli budgets budget budget list --compartment-id "$COMPARTMENT_OCID" \
        --query 'data[].{name:"display-name",limit:amount,spent:"actual-spend",forecast:"forecasted-spend"}' 2>/dev/null || true)"
  local nb; nb="$(printf '%s' "$j" | jq -r 'length' 2>/dev/null || echo 0)"
  if [ "${nb:-0}" -gt 0 ] 2>/dev/null; then
    ok "budgets   : $nb budget(s)"
    printf '%s' "$j" | jq -r '.[] | "            \(.name): limit=\(.limit) spent=\(.spent // 0) forecast=\(.forecast // 0)"' 2>/dev/null >&2 || true
  else
    warn "budgets   : none in this compartment — add a guardrail (oci-iam-admin / oci-cost)"
  fi

  echo >&2
  info "empty sections are inconclusive (perms/region), not proof of absence."
  ok   "status complete — read-only, no resources changed, no OCIDs printed."
}

# --------------------------------------------------------------------------- #
cmd_bootstrap() {
  [ -n "$NAME" ] || die "bootstrap needs a project name: -n NAME"
  [ -n "$COMPARTMENT_OCID" ] || die "bootstrap needs the PARENT compartment: -c PARENT_COMPARTMENT_OCID"
  banner "OCI project bootstrap — '$NAME' (idempotent, gated)"
  [ "${OCI_SKILLS_DRY_RUN:-}" = "true" ] && info "DRY-RUN: mutations are printed, not executed."

  # 1. Ensure the project compartment (search by name first; 409 = exists).
  local proj
  proj="$(oci_cli iam compartment list --compartment-id "$COMPARTMENT_OCID" --all \
            --query "data[?name=='$NAME'].id | [0]" --raw-output 2>/dev/null || true)"
  if [ -z "$proj" ] || [ "$proj" = "null" ]; then
    if [ "${OCI_SKILLS_DRY_RUN:-}" = "true" ]; then
      run_mutating "create compartment $NAME" oci_cli iam compartment create \
        --compartment-id "$COMPARTMENT_OCID" --name "$NAME" --description "project $NAME"
      proj="<PROJECT_COMPARTMENT_OCID>"
    else
      local created
      created="$(run_mutating "create compartment $NAME" oci_cli iam compartment create \
        --compartment-id "$COMPARTMENT_OCID" --name "$NAME" --description "project $NAME" 2>/dev/null || true)"
      proj="$(printf '%s' "$created" | jq -r '.data.id // empty' 2>/dev/null || true)"
      [ -n "$proj" ] || proj="<PROJECT_COMPARTMENT_OCID>"
    fi
  else
    ok "compartment '$NAME' already exists — reusing."
  fi

  # 2. Tag the compartment so spend + inventory roll up by project.
  run_mutating "tag project=$NAME" oci_cli iam compartment update \
    --compartment-id "$proj" --freeform-tags "{\"project\":\"$NAME\"}"

  # 3. Budget guardrail (+ emit the 80% forecast alert rule).
  if [ -n "$BUDGET" ]; then
    run_mutating "create budget ($BUDGET)" oci_cli budgets budget create \
      --compartment-id "$COMPARTMENT_OCID" --target-type COMPARTMENT --targets "[\"$proj\"]" \
      --amount "$BUDGET" --reset-period MONTHLY --display-name "${NAME}-budget"
    info "next: add an 80% forecast alert rule (oci-iam-admin):"
    echo "  oci_cli budgets alert-rule create --budget-id <BUDGET_OCID> --type FORECAST \\" >&2
    echo "    --threshold 80 --threshold-type PERCENTAGE --display-name ${NAME}-80pct --recipients you@example.com" >&2
  else
    warn "no budget set (-b AMOUNT) — strongly recommended as a project guardrail."
  fi

  # 4. Emit the gated IAM + VCN steps (tenancy blast radius — run via the domains).
  echo >&2
  info "next steps (run via the domain skills, each gated by confirm/run_mutating):"
  cat >&2 <<EOF

  # scoped IAM (oci-iam-admin) — least privilege, NEVER manage all-resources in tenancy
  oci_cli iam group create --compartment-id <TENANCY_OCID> --name ${NAME}-admins --description "project $NAME"
  oci_cli iam policy create --compartment-id $proj --name ${NAME}-policy \\
    --statements '["Allow group ${NAME}-admins to manage all-resources in compartment $NAME"]' \\
    --description "project $NAME, scoped to its compartment"

  # network skeleton (oci-networking-compute)
  oci_cli network vcn create --compartment-id $proj --display-name ${NAME}-vcn --cidr-blocks '["10.0.0.0/16"]'
  #   then: subnets, a NAT gateway (private egress) or IGW (internet-facing), route tables, NSGs

EOF
  ok "bootstrap plan complete. Re-run with OCI_SKILLS_DRY_RUN=true to preview, then 'status' to verify."
}

# --------------------------------------------------------------------------- #
cmd_teardown() {
  [ -n "$COMPARTMENT_OCID" ] || die "teardown needs the project compartment: -c COMPARTMENT_OCID"
  banner "OCI project teardown PLAN — read-only (destroys nothing)"
  warn "Teardown is IRREVERSIBLE. This prints an ordered plan; run each step via the"
  warn "domain skills so it passes confirm / run_mutating. Prefer a Resource Manager"
  warn "'destroy' job if the project was stack-deployed."
  echo >&2

  local j
  j="$(oci_cli compute instance list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  info "compute   : $(_len "$j") instance(s)   [$(_states "$j")]"
  j="$(oci_cli lb load-balancer list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  info "load-bal. : $(_len "$j")"
  j="$(oci_cli ce cluster list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  info "OKE       : $(_len "$j")"
  j="$(oci_cli network vcn list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  info "network   : $(_len "$j") VCN(s)"

  echo >&2
  ok "ordered destroy plan (dependency order — attached resources block deletes, KB-043):"
  cat >&2 <<'EOF'

  1. Workloads / apps        (helm uninstall / kubectl delete, or the app's own teardown)
  2. Compute instances       compute instance terminate --instance-id <ID> --preserve-boot-volume false
  3. Load balancers          lb load-balancer delete --load-balancer-id <ID>
  4. OKE clusters            ce cluster delete --cluster-id <ID>   (node pools first)
  5. Network: subnets        network subnet delete --subnet-id <ID>
              gateways        network nat-gateway/internet-gateway/service-gateway delete
              VCN             network vcn delete --vcn-id <ID>
  6. Budgets / alarms        budgets budget delete ; monitoring alarm delete
  7. Compartment (LAST)      iam compartment delete --compartment-id <ID>   (must be empty)

EOF
  warn "each delete must go through confirm / run_mutating; verify with 'status' after."
}

case "$CMD" in
  help)      cmd_help ;;
  status)    cmd_status ;;
  bootstrap) cmd_bootstrap ;;
  teardown)  cmd_teardown ;;
  *)         usage; exit 1 ;;
esac

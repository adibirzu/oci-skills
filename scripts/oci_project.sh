#!/usr/bin/env bash
# oci_project.sh — OCI project lifecycle helper.
#
# Orchestrates the project lifecycle across the domain skills, scoped to
# ONE project compartment. Three subcommands:
#
#   status     (default) read-only health: inventory + states + open security
#              problems + alarms + budget, by COUNT and NAME — never OCIDs.
#   bootstrap  idempotent, gated scaffold: ensure the project compartment, a
#              cost-tracking-style project tag, and a budget; then EMIT the gated
#              IAM-policy and VCN commands (those belong to their domain skills).
#   teardown   READ-ONLY: inventory the compartment and print the ordered, gated
#              destroy plan. It destroys NOTHING — you run the steps via the
#              domain skills so each passes risk-specific run_action approval.
#
# Usage:
#   ./oci_project.sh status               [-c COMPARTMENT_OCID]
#   ./oci_project.sh bootstrap -n NAME    -c PARENT_COMPARTMENT_OCID [-b BUDGET]
#   ./oci_project.sh teardown             -c COMPARTMENT_OCID
# Add --bundle PATH to validate and inventory a schema-v1 platform bundle.
#
# Env: OCI_SKILLS_COMPARTMENT (default compartment), OCI_CLI_PROFILE, OCI_REGION,
#      OCI_AUTH_MODE, OCI_SKILLS_DRY_RUN (bootstrap prints instead of creating).
# Read calls only for status/teardown; bootstrap mutations go through run_action.

set -o errexit -o nounset -o pipefail
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"

_PROJECT_TMP_DIR=""
cleanup_project_temp() {
  if [[ -n "$_PROJECT_TMP_DIR" && -d "$_PROJECT_TMP_DIR" && ! -L "$_PROJECT_TMP_DIR" ]]; then
    rm -rf -- "$_PROJECT_TMP_DIR"
  fi
  _PROJECT_TMP_DIR=""
}
trap cleanup_project_temp EXIT

CMD="${1:-status}"
case "$CMD" in status|bootstrap|teardown) shift ;; -h|--help) CMD="help" ;; esac

# Defaults come from the bound named context (oci_context.py use <project> exports
# these); explicit -n/-b/-c flags below override them.
COMPARTMENT_OCID="${OCI_SKILLS_COMPARTMENT:-}"
NAME="${OCI_SKILLS_PROJECT_PREFIX:-}"
BUDGET="${OCI_SKILLS_BUDGET:-}"
BUNDLE_PATH="${OCI_SKILLS_PLATFORM_BUNDLE:-}"

if [ "$CMD" != "help" ]; then
  # Accept long flags as aliases for the short ones (agent-friendly). Bash 3.2:
  # guard the empty-array expansion under `set -u` (KB-013).
  _args=()
  for _a in ${@+"$@"}; do
    case "$_a" in
      --budget)      _a="-b" ;;
      --name)        _a="-n" ;;
      --compartment) _a="-c" ;;
      --bundle)      _a="-f" ;;
    esac
    _args+=("$_a")
  done
  set -- ${_args[@]+"${_args[@]}"}

  while getopts ":c:n:b:f:h" opt; do
    case "$opt" in
      c) COMPARTMENT_OCID="$OPTARG" ;;
      n) NAME="$OPTARG" ;;
      b) BUDGET="$OPTARG" ;;
      f) BUNDLE_PATH="$OPTARG" ;;
      h) CMD="help" ;;
      *) die "usage: $0 {status|bootstrap|teardown} [-c COMPARTMENT] [-n NAME] [-b|--budget BUDGET] [-f|--bundle PATH]" ;;
    esac
  done
fi

usage() {
  cat >&2 <<'EOF'
oci_project.sh — OCI project lifecycle helper

  status     [-c COMPARTMENT] [--bundle PATH]              read-only health (default)
  bootstrap  -n NAME -c PARENT [-b BUDGET] [--bundle PATH] idempotent, gated scaffold
  teardown   -c COMPARTMENT [--bundle PATH]                read-only inventory + ordered destroy plan

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

# _untagged JSON -> count of items carrying neither freeform nor defined tags
_untagged() {
  printf '%s' "${1:-}" | jq -r '
    [ (.data // [])[]
      | select( ((."freeform-tags" // {}) | length) == 0
                and ((."defined-tags" // {}) | length) == 0 ) ] | length
  ' 2>/dev/null || echo 0
}

_names() {
  printf '%s' "${1:-}" | jq -r '
    [(.data // [])[] | (."display-name" // .name // empty)] | map(select(length > 0)) | join(", ")
  ' 2>/dev/null || echo ""
}

validate_bundle() {
  [[ -n "$BUNDLE_PATH" ]] || return 0
  [[ -f "$BUNDLE_PATH" && ! -L "$BUNDLE_PATH" ]] || die "bundle must be a regular non-symlink file"
  python3 "$_OCI_SKILLS_SCRIPT_DIR/platform_bundle.py" validate "$BUNDLE_PATH" >/dev/null \
    || die "platform bundle failed schema-v1 validation"
  BUNDLE_OWNER="$(awk '/^[[:space:]]*owner:[[:space:]]*/ {print $2; exit}' "$BUNDLE_PATH")"
  [[ "$BUNDLE_OWNER" == "terraform" ]] || die "platform bundle must declare terraform as owner"
}

require_cmd oci jq python3
validate_bundle

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
  if [[ -n "$BUNDLE_PATH" ]]; then
    info "bundle    : owner=$BUNDLE_OWNER   drift=not-evaluated (run a reviewed Terraform plan)"
  fi
  echo >&2

  local j inst untag
  inst="$(oci_cli compute instance list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  ok  "compute   : $(_len "$inst") instance(s)   [$(_states "$inst")]"
  untag="$(_untagged "$inst")"
  [ "${untag:-0}" -gt 0 ] 2>/dev/null \
    && warn "tags      : $untag instance(s) untagged — spend/inventory won't roll up by project"

  j="$(oci_cli network vcn list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  ok  "network   : $(_len "$j") VCN(s)"

  j="$(oci_cli ce cluster list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  ok  "OKE       : $(_len "$j") cluster(s)   [$(_states "$j")]"

  j="$(oci_cli lb load-balancer list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  ok  "load-bal. : $(_len "$j") load balancer(s)"

  j="$(oci_cli api-gateway gateway list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  ok  "API Gateway: $(_len "$j") gateway(s) [$(_states "$j")] names=[$(_names "$j")]"

  j="$(oci_cli devops project list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  ok  "DevOps    : $(_len "$j") project(s) [$(_states "$j")] names=[$(_names "$j")]"

  j="$(oci_cli container-instances container-instance list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  ok  "containers: $(_len "$j") instance(s) [$(_states "$j")] names=[$(_names "$j")]"

  j="$(oci_cli queue queue-admin queue list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  ok  "Queue     : $(_len "$j") queue(s) [$(_states "$j")] names=[$(_names "$j")]"

  j="$(oci_cli cloud-guard problem list --compartment-id "$COMPARTMENT_OCID" \
        --lifecycle-state ACTIVE --all 2>/dev/null || true)"
  local probs; probs="$(_len "$j")"
  if [ "$probs" -gt 0 ] 2>/dev/null; then warn "security  : $probs ACTIVE Cloud Guard problem(s) — triage (oci-security-compliance)"
  else ok "security  : 0 ACTIVE Cloud Guard problems"; fi

  j="$(oci_cli monitoring alarm list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  local fj firing
  fj="$(oci_cli monitoring alarm-status list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  firing="$(printf '%s' "$fj" | jq -r '[(.data // [])[] | select(.status=="FIRING")] | length' 2>/dev/null || echo 0)"
  if [ "${firing:-0}" -gt 0 ] 2>/dev/null; then
    warn "alarms    : $(_len "$j") definition(s), $firing FIRING — investigate"
  else
    ok "alarms    : $(_len "$j") alarm definition(s), 0 firing"
  fi

  j="$(oci_cli budgets budget budget list --compartment-id "$COMPARTMENT_OCID" \
        --query 'data[].{name:"display-name",limit:amount,spent:"actual-spend",forecast:"forecasted-spend"}' 2>/dev/null || true)"
  local nb; nb="$(printf '%s' "$j" | jq -r 'length' 2>/dev/null || echo 0)"
  if [ "${nb:-0}" -gt 0 ] 2>/dev/null; then
    local over
    over="$(printf '%s' "$j" | jq -r '[.[] | select((.forecast // 0) > .limit or (.spent // 0) > .limit)] | length' 2>/dev/null || echo 0)"
    if [ "${over:-0}" -gt 0 ] 2>/dev/null; then
      warn "budgets   : $nb budget(s), $over trending over limit (forecast/spent > limit)"
    else
      ok "budgets   : $nb budget(s), none over limit"
    fi
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
  [[ "$NAME" =~ ^[A-Za-z][A-Za-z0-9_-]{0,99}$ ]] \
    || die "project name must start with a letter and use only letters, digits, _ or -"
  [[ -z "$BUDGET" || "$BUDGET" =~ ^[0-9]+([.][0-9]+)?$ ]] \
    || die "budget must be a positive numeric amount"
  banner "OCI project bootstrap — '$NAME' (idempotent, gated)"
  if [[ -n "$BUNDLE_PATH" ]]; then
    ok "accepted schema-v1 platform bundle (owner=$BUNDLE_OWNER); service resources remain Terraform-owned."
  fi
  [ "${OCI_SKILLS_DRY_RUN:-}" = "true" ] && info "DRY-RUN: mutations are printed, not executed."

  # 1. Ensure the project compartment (search by name first; 409 = exists).
  local proj
  proj="$(oci_cli iam compartment list --compartment-id "$COMPARTMENT_OCID" --all \
            --query "data[?name=='$NAME'].id | [0]" --raw-output 2>/dev/null || true)"
  if [ -z "$proj" ] || [ "$proj" = "null" ]; then
    if [ "${OCI_SKILLS_DRY_RUN:-}" = "true" ]; then
      run_action --risk additive --compartment "$COMPARTMENT_OCID" \
        --description "create compartment $NAME" -- oci_cli iam compartment create \
        --compartment-id "$COMPARTMENT_OCID" --name "$NAME" --description "project $NAME"
      proj="<PROJECT_COMPARTMENT_OCID>"
    else
      local created
      if created="$(run_action --risk additive --compartment "$COMPARTMENT_OCID" \
        --description "create compartment $NAME" -- oci_cli iam compartment create \
        --compartment-id "$COMPARTMENT_OCID" --name "$NAME" --description "project $NAME")"; then
        proj="$(printf '%s' "$created" | jq -r '.data.id // empty')"
      else
        warn "compartment create did not return successfully; checking for a concurrent 409/create"
        proj="$(oci_cli iam compartment list --compartment-id "$COMPARTMENT_OCID" --all \
          --query "data[?name=='$NAME'].id | [0]" --raw-output 2>/dev/null || true)"
      fi
      [[ -n "$proj" && "$proj" != "null" ]] \
        || die "compartment create failed and re-discovery found no matching project"
    fi
  else
    ok "compartment '$NAME' already exists — reusing."
  fi

  if [[ "${OCI_SKILLS_DRY_RUN:-}" != "true" && "$proj" != "<PROJECT_COMPARTMENT_OCID>" ]]; then
    "$_OCI_SKILLS_SCRIPT_DIR/oci_preflight.sh" -c "$proj"
  fi

  # Complex CLI values are generated as private files so JSON and topology do
  # not appear on argv. The EXIT trap removes the directory on every path.
  _PROJECT_TMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/oci-project-payload.XXXXXX")"
  chmod 700 "$_PROJECT_TMP_DIR"
  local tags_file="$_PROJECT_TMP_DIR/tags.json"
  local targets_file="$_PROJECT_TMP_DIR/targets.json"
  python3 - "$tags_file" "$targets_file" "$NAME" "$proj" <<'PY'
import json, os, sys
tags_path, targets_path, name, compartment = sys.argv[1:]
for path, payload in ((tags_path, {"project": name}), (targets_path, [compartment])):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.fchmod(fd, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, separators=(",", ":"))
        handle.write("\n")
PY

  # 2. Tag the compartment so spend + inventory roll up by project.
  run_action --risk in-place --compartment "$proj" --description "tag project=$NAME" -- \
    oci_cli iam compartment update \
    --compartment-id "$proj" --freeform-tags "file://$tags_file"

  # 3. Budget guardrail (+ emit the 80% forecast alert rule).
  if [ -n "$BUDGET" ]; then
    run_action --risk additive --compartment "$proj" --description "create budget ($BUDGET)" -- \
      oci_cli budgets budget create \
      --compartment-id "$COMPARTMENT_OCID" --target-type COMPARTMENT --targets "file://$targets_file" \
      --amount "$BUDGET" --reset-period MONTHLY --display-name "${NAME}-budget"
    info "next: add an 80% forecast alert rule (oci-iam-admin):"
    echo "  run_action --risk additive --compartment $proj --description create-budget-alert -- oci_cli budgets alert-rule create --budget-id <BUDGET_OCID> --type FORECAST \\" >&2
    echo "    --threshold 80 --threshold-type PERCENTAGE --display-name ${NAME}-80pct --recipients you@example.com" >&2
  else
    warn "no budget set (-b AMOUNT) — strongly recommended as a project guardrail."
  fi
  cleanup_project_temp

  # 4. Emit the gated IAM + VCN steps (tenancy blast radius — run via the domains).
  echo >&2
  info "next steps (run via the owning domain skills with explicit run_action risk):"
  cat >&2 <<EOF

  # scoped IAM (oci-iam-admin) — least privilege, NEVER manage all-resources in tenancy
  run_action --risk additive --compartment $proj --description create-project-group -- \\
    oci_cli iam group create --compartment-id <TENANCY_OCID> --name ${NAME}-admins --description "project $NAME"
  run_action --risk additive --compartment $proj --description create-project-policy -- \\
    oci_cli iam policy create --compartment-id $proj --name ${NAME}-policy \\
    --statements file://<TMP_0600_POLICY_JSON> \\
    --description "project $NAME, scoped to its compartment"

  # network skeleton (oci-networking-compute)
  run_action --risk additive --compartment $proj --description create-project-vcn -- \\
    oci_cli network vcn create --compartment-id $proj --display-name ${NAME}-vcn \\
    --cidr-blocks file://<TMP_0600_CIDRS_JSON>
  #   then: subnets, a NAT gateway (private egress) or IGW (internet-facing), route tables, NSGs

EOF
  ok "bootstrap plan complete. Re-run with OCI_SKILLS_DRY_RUN=true to preview, then 'status' to verify."
}

# --------------------------------------------------------------------------- #
cmd_teardown() {
  [ -n "$COMPARTMENT_OCID" ] || die "teardown needs the project compartment: -c COMPARTMENT_OCID"
  banner "OCI project teardown PLAN — read-only (destroys nothing)"
  if [[ -n "$BUNDLE_PATH" ]]; then
    warn "Bundle owner is Terraform: use a reviewed Terraform destroy plan; direct CLI delete is break-glass only and must be reconciled."
  fi
  warn "Teardown is IRREVERSIBLE. This prints an ordered plan; run each step via the"
  warn "domain skills so it passes run_action --risk destructive. Prefer a Resource Manager"
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
  j="$(oci_cli api-gateway gateway list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  info "API Gateway: $(_len "$j")"
  j="$(oci_cli devops project list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  info "DevOps    : $(_len "$j")"
  j="$(oci_cli container-instances container-instance list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  info "containers: $(_len "$j")"
  j="$(oci_cli queue queue-admin queue list --compartment-id "$COMPARTMENT_OCID" --all 2>/dev/null || true)"
  info "Queue     : $(_len "$j")"

  echo >&2
  ok "ordered destroy plan (dependency order — attached resources block deletes, KB-043):"
  cat >&2 <<'EOF'

  1. DevOps triggers/pipelines and application workloads
  2. API deployments/gateways, Functions, Container Instances, OKE workloads
  3. Queue / Streaming consumers, then transports (after producers stop)
  4. Databases and runtime compute (preserve/delete backups explicitly)
  5. Load balancers and OKE clusters (node pools first)
  6. Network: subnets        network subnet delete --subnet-id <ID>
              gateways        network nat-gateway/internet-gateway/service-gateway delete
              VCN             network vcn delete --vcn-id <ID>
  7. Budgets / alarms
  8. Compartment (LAST; must be empty)

EOF
  warn "each delete must go through run_action --risk destructive; verify with 'status' after."
}

case "$CMD" in
  help)      cmd_help ;;
  status)    cmd_status ;;
  bootstrap) cmd_bootstrap ;;
  teardown)  cmd_teardown ;;
  *)         usage; exit 1 ;;
esac

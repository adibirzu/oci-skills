#!/usr/bin/env bash
# oci_tf.sh — safe OCI Terraform authoring, discovery, review, and execution.
#
# Usage:
#   oci_tf.sh scaffold DIR [--name NAME]
#   oci_tf.sh discover DIR --compartment OCID [--services CSV]
#   oci_tf.sh validate DIR
#   oci_tf.sh plan DIR --compartment OCID [--out FILE] [--destroy]
#   oci_tf.sh show PLAN
#   oci_tf.sh apply DIR --compartment OCID --plan FILE
#   oci_tf.sh destroy DIR --compartment OCID --plan FILE
set -o errexit -o nounset -o pipefail
# shellcheck source=scripts/common.sh
source "$(dirname "$0")/common.sh"

ASSET_DIR="${OCI_TF_ASSET_DIR:-$_OCI_SKILLS_SCRIPT_DIR/../skills/oci-terraform-authoring/assets/starter}"
PLAN_TOOL="$_OCI_SKILLS_SCRIPT_DIR/oci_tf_plan.py"

usage() { print_self_help; }

safe_empty_destination() {
  local destination="$1"
  [[ ! -L "$destination" ]] || die "destination must not be a symlink: $destination"
  if [[ -e "$destination" ]]; then
    [[ -d "$destination" ]] || die "destination is not a directory: $destination"
    [[ -z "$(find "$destination" -mindepth 1 -maxdepth 1 -print -quit)" ]] \
      || die "destination must be empty: $destination"
  else
    mkdir -p "$destination"
  fi
}

assert_directory() {
  [[ -d "$1" && ! -L "$1" ]] || die "Terraform directory must be a non-symlink directory: $1"
}

copy_safe_starter() {
  local destination="$1" asset source
  local -a assets=(
    .gitignore .terraform.lock.hcl versions.tf provider.tf variables.tf
    locals.tf outputs.tf schema.yaml terraform.tfvars.example tests
  )
  for asset in "${assets[@]}"; do
    source="$ASSET_DIR/$asset"
    [[ -e "$source" && ! -L "$source" ]] || die "starter asset is missing or unsafe: $asset"
    if find "$source" -type l -print -quit | grep -q .; then
      die "starter asset contains a symlink: $asset"
    fi
    cp -R "$source" "$destination/"
  done
}

cmd_scaffold() {
  local destination="${1:-}" name="oci-platform"; shift || true
  [[ -n "$destination" ]] || die "scaffold needs DIR"
  while (( $# > 0 )); do
    case "$1" in --name) name="${2:-}"; shift 2 ;; *) die "unknown scaffold option: $1" ;; esac
  done
  [[ "$name" =~ ^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$ ]] || die "invalid scaffold name"
  safe_empty_destination "$destination"
  copy_safe_starter "$destination"
  # Only a non-sensitive logical name is substituted into the starter.
  sed -i.bak "s/__PROJECT_NAME__/$name/g" "$destination/locals.tf"
  rm -f "$destination/locals.tf.bak"
  ok "Terraform starter created at $destination (artifacts only; nothing deployed)."
}

cmd_discover() {
  local destination="${1:-}" compartment="" services="" provider_bin="${OCI_TF_PROVIDER_BIN:-}"; shift || true
  while (( $# > 0 )); do
    case "$1" in
      --compartment) compartment="${2:-}"; shift 2 ;;
      --services) services="${2:-}"; shift 2 ;;
      *) die "unknown discover option: $1" ;;
    esac
  done
  [[ -n "$destination" && -n "$compartment" ]] || die "discover needs DIR and --compartment"
  _require_preflight_receipt "$compartment"
  safe_empty_destination "$destination"
  if [[ -z "$provider_bin" ]]; then provider_bin="$(command -v terraform-provider-oci || true)"; fi
  [[ -n "$provider_bin" && -x "$provider_bin" ]] || die "terraform-provider-oci executable not found; set OCI_TF_PROVIDER_BIN"
  local -a args=("-command=export" "-compartment_id=$compartment" "-output_path=$(cd "$destination" && pwd -P)")
  [[ -n "$services" ]] && args+=("-services=$services")
  info "resource discovery is read-only and generates a reviewable starting point, not a migration."
  "$provider_bin" "${args[@]}"
  printf '%s\n' '# Resource discovery output: review imports, dependencies, and sensitive attributes before ownership.' \
    > "$destination/REVIEW_REQUIRED.md"
  ok "discovery complete; state generation was intentionally not requested."
}

cmd_validate() {
  local directory="${1:-}"
  assert_directory "$directory"; require_cmd terraform
  terraform -chdir="$directory" fmt -check -recursive
  terraform -chdir="$directory" init -backend=false -input=false
  terraform -chdir="$directory" validate
  if find "$directory" -type f \( -name '*.tfstate*' -o -name '*.tfplan' -o -iname '*wallet*' \) -print -quit | grep -q .; then
    die "validation produced or found a forbidden state/plan/wallet artifact"
  fi
}

parse_plan_options() {
  TF_COMPARTMENT=""; TF_PLAN=""; TF_DESTROY=false
  while (( $# > 0 )); do
    case "$1" in
      --compartment) TF_COMPARTMENT="${2:-}"; shift 2 ;;
      --out|--plan) TF_PLAN="${2:-}"; shift 2 ;;
      --destroy) TF_DESTROY=true; shift ;;
      *) die "unknown Terraform option: $1" ;;
    esac
  done
}

cmd_plan() {
  local directory="${1:-}"; shift || true
  assert_directory "$directory"; parse_plan_options "$@"
  [[ -n "$TF_COMPARTMENT" ]] || die "plan needs --compartment"
  _require_preflight_receipt "$TF_COMPARTMENT"
  require_cmd terraform python3
  [[ -n "$TF_PLAN" ]] || TF_PLAN="reviewed.tfplan"
  [[ "$TF_PLAN" != */* ]] || die "--out must be a filename inside the Terraform directory"
  local -a extra=()
  [[ "$TF_DESTROY" == true ]] && extra=(-destroy)
  terraform -chdir="$directory" plan -input=false "${extra[@]}" -out="$TF_PLAN"
  local plan_path context_hash identity plan_risk
  plan_path="$(cd "$directory" && pwd -P)/$TF_PLAN"
  chmod 600 "$plan_path"
  context_hash="$(_action_context_hash "$TF_COMPARTMENT")"
  local plan_kind="normal"
  [[ "$TF_DESTROY" == true ]] && plan_kind="destroy"
  plan_risk="$(terraform -chdir="$directory" show -json "$TF_PLAN" | python3 "$PLAN_TOOL" analyze --risk-only)"
  [[ "$plan_kind" == "destroy" ]] && plan_risk="destructive"
  identity="$(python3 "$PLAN_TOOL" record "$plan_path" --context-hash "$context_hash" \
    --kind "$plan_kind" --risk "$plan_risk")"
  terraform -chdir="$directory" show -json "$TF_PLAN" | python3 "$PLAN_TOOL" analyze
  ok "reviewed $plan_risk plan recorded: ${identity:0:31}…"
}

cmd_show() {
  local plan="${1:-}"
  [[ -f "$plan" && ! -L "$plan" ]] || die "show needs a regular plan file"
  require_cmd terraform python3
  python3 - "$plan" <<'PY' || die "show needs a 0600 plan file"
import pathlib, stat, sys
path = pathlib.Path(sys.argv[1])
raise SystemExit(0 if stat.S_IMODE(path.stat().st_mode) == 0o600 else 1)
PY
  terraform show -json "$plan" | python3 "$PLAN_TOOL" analyze
}

cmd_execute() {
  local verb="$1" directory="${2:-}"; shift 2 || true
  assert_directory "$directory"; parse_plan_options "$@"
  [[ -n "$TF_COMPARTMENT" && -n "$TF_PLAN" ]] || die "$verb needs --compartment and --plan"
  [[ "$TF_PLAN" != */* ]] || die "--plan must be a filename inside the Terraform directory"
  local plan_path context_hash identity review_risk
  plan_path="$(cd "$directory" && pwd -P)/$TF_PLAN"
  context_hash="$(_action_context_hash "$TF_COMPARTMENT")"
  local expected_kind="normal"
  [[ "$verb" == "destroy" ]] && expected_kind="destroy"
  identity="$(python3 "$PLAN_TOOL" verify "$plan_path" --context-hash "$context_hash" --expected-kind "$expected_kind")" \
    || die "refusing $verb: plan is missing review or has changed"
  review_risk="$(python3 "$PLAN_TOOL" verify "$plan_path" --context-hash "$context_hash" \
    --expected-kind "$expected_kind" --field action-risk)" \
    || die "refusing $verb: reviewed risk is missing or invalid"
  [[ "$verb" == "destroy" ]] && review_risk="destructive"
  run_action --risk "$review_risk" --compartment "$TF_COMPARTMENT" \
    --description "terraform $verb ${identity:0:31}" -- \
    terraform -chdir="$directory" apply -input=false "$TF_PLAN"
}

command="${1:-}"; shift || true
case "$command" in
  scaffold) cmd_scaffold "$@" ;;
  discover) cmd_discover "$@" ;;
  validate) cmd_validate "$@" ;;
  plan) cmd_plan "$@" ;;
  show) cmd_show "$@" ;;
  apply) cmd_execute apply "$@" ;;
  destroy) cmd_execute destroy "$@" ;;
  -h|--help|help|"") usage ;;
  *) die "unknown command: $command" ;;
esac

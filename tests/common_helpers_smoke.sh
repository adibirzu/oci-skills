#!/usr/bin/env bash
# common_helpers_smoke.sh — regression fence for the extracted common.sh helpers
# (resolve_tenancy_ocid, resolve_compartment, print_self_help, _id_flag_for).
# These back the five domain scripts, so a behavior change here is a fleet-wide
# change. Uses placeholder tenancy values (the awk just echoes what follows
# `tenancy=`), so no OCID literals are needed. Bash 3.2 compatible.
set -euo pipefail

dir="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/oci-helpers.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT

cfg="$tmp/config"
cat > "$cfg" <<'EOF'
[DEFAULT]
user=fake-user
tenancy=fake-tenancy-default
region=us-phoenix-1
[OTHER]
tenancy=fake-tenancy-other
EOF

# shellcheck source=scripts/common.sh
source "$dir/scripts/common.sh"

# Start from a clean slate regardless of the CI runner's environment.
unset OCI_SKILLS_TENANCY OCI_SKILLS_COMPARTMENT OCI_CLI_PROFILE OCI_AUTH_MODE 2>/dev/null || true

assert_eq() { [ "$2" = "$3" ] || { echo "FAIL $1: expected '$3', got '$2'"; exit 1; }; }

# --- resolve_tenancy_ocid -----------------------------------------------------
assert_eq "tenancy/explicit-arg" "$(resolve_tenancy_ocid 'explicit-value')" "explicit-value"
assert_eq "tenancy/env-wins" \
  "$(OCI_SKILLS_TENANCY=env-tenancy OCI_AUTH_MODE=config OCI_CLI_CONFIG_FILE="$cfg" resolve_tenancy_ocid)" \
  "env-tenancy"
assert_eq "tenancy/config-default" \
  "$(OCI_AUTH_MODE=config OCI_CLI_CONFIG_FILE="$cfg" resolve_tenancy_ocid)" \
  "fake-tenancy-default"
assert_eq "tenancy/config-other-profile" \
  "$(OCI_AUTH_MODE=config OCI_CLI_PROFILE=OTHER OCI_CLI_CONFIG_FILE="$cfg" resolve_tenancy_ocid)" \
  "fake-tenancy-other"
assert_eq "tenancy/principal-empty" \
  "$(OCI_AUTH_MODE=instance_principal resolve_tenancy_ocid)" \
  ""

# --- resolve_compartment ------------------------------------------------------
assert_eq "compartment/explicit" "$(resolve_compartment 'cmpt-explicit')" "cmpt-explicit"
assert_eq "compartment/env" \
  "$(OCI_SKILLS_COMPARTMENT=cmpt-env OCI_AUTH_MODE=config OCI_CLI_CONFIG_FILE="$cfg" resolve_compartment)" \
  "cmpt-env"
assert_eq "compartment/falls-back-to-tenancy" \
  "$(OCI_AUTH_MODE=config OCI_CLI_CONFIG_FILE="$cfg" resolve_compartment)" \
  "fake-tenancy-default"

# --- _id_flag_for (multi-word resource handling) ------------------------------
assert_eq "idflag/instance"  "$(_id_flag_for 'compute instance')"             "--instance-id"
assert_eq "idflag/vcn"       "$(_id_flag_for 'network vcn')"                   "--vcn-id"
assert_eq "idflag/adb"       "$(_id_flag_for 'db autonomous-database')"        "--autonomous-database-id"
assert_eq "idflag/lb"        "$(_id_flag_for 'lb load-balancer')"             "--load-balancer-id"
assert_eq "idflag/nlb"       "$(_id_flag_for 'nlb network-load-balancer')"    "--network-load-balancer-id"
assert_eq "idflag/acd"       "$(_id_flag_for 'db autonomous-container-database')" "--autonomous-container-database-id"
assert_eq "idflag/db-system" "$(_id_flag_for 'db db-system')"                 "--db-system-id"

# --- print_self_help (uses the caller's $0 header comment) ---------------------
help_script="$tmp/demo.sh"
cat > "$help_script" <<EOF
#!/usr/bin/env bash
# demo.sh — a demo tool.
# Second line of help.
set -euo pipefail
source "$dir/scripts/common.sh"
print_self_help
EOF
chmod +x "$help_script"
out="$(/bin/bash "$help_script")"
printf '%s\n' "$out" | grep -q "demo.sh — a demo tool." || { echo "FAIL help: missing line 1"; exit 1; }
printf '%s\n' "$out" | grep -q "Second line of help."  || { echo "FAIL help: missing line 2"; exit 1; }
if printf '%s\n' "$out" | grep -q '/usr/bin/env bash'; then echo "FAIL help: leaked shebang"; exit 1; fi

echo "common helpers smoke OK"

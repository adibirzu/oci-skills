#!/usr/bin/env bash
# oci_adb_smoke.sh — regression fence for oci_adb.sh (read-only ADB lister).
#
# The bug this guards against: the storage column only queried
# `data-storage-size-in-tbs`, which is null for ECPU-model ADBs (the current
# default — they report `data-storage-size-in-gbs`). Every modern ADB therefore
# showed a blank storage column. Found by live-testing against a real tenancy.
#
# Asserts (with a stubbed `oci`, deterministic, Bash 3.2 compatible):
#   A) ECPU ADB (gb set, tb null)  => storage shows "<n>GB"  (the fixed bug)
#   B) legacy OCPU ADB (tb set)    => storage shows "<n>TB"
#   C) empty list                  => exit 0, "no Autonomous Databases" guidance
#   D) output never prints an OCID  (the skill promises names/states only)
set -euo pipefail

dir="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/oci-adb.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
PATH="$tmp:$PATH"

mode_file="$tmp/mode"

# OCID assembled at RUNTIME so this tracked file holds no full OCID literal (the
# CI redaction gate scans every tracked file; oci-skills fixture discipline). It
# is injected into the stub (unquoted heredoc expands it into the tmp copy) so
# case D can prove the lister never echoes it.
leak_ocid="ocid1.autonomousdatabase.oc1..$(printf '%s' aaaasecret)"

# Stub `oci`: the `db autonomous-database list` call returns the already
# --query-projected array (oci applies --query server-side). Shape matches the
# projection in scripts/oci_adb.sh. An OCID is embedded in `freeform` so case D
# proves the script never echoes it.
cat > "$tmp/oci" <<EOF
#!/bin/sh
case "\$*" in
  *"autonomous-database list"*)
    m=\$(cat "$mode_file")
    case "\$m" in
      ecpu)  echo '[{"name":"aaf-atp","state":"AVAILABLE","workload":"OLTP","ecpu":8.0,"tb":null,"gb":500,"autoscale":true,"mtls":true,"freeform":null}]' ;;
      ocpu)  echo '[{"name":"legacy-adw","state":"AVAILABLE","workload":"DW","ecpu":4.0,"tb":1,"gb":null,"autoscale":false,"mtls":false,"freeform":"$leak_ocid"}]' ;;
      empty) echo '[]' ;;
    esac ;;
  *) echo '[]' ;;
esac
EOF
chmod +x "$tmp/oci"

# Fixture compartment OCID assembled at RUNTIME (CI redaction gate scans tracked
# files — no full OCID literal may be committed; oci-skills fixture discipline).
fixture_cmpt="ocid1.compartment.oc1..$(printf '%s' aaaatest)"

run_adb() {
  OCI_AUTH_MODE=config OCI_SKILLS_NO_AUDIT=1 \
    bash "$dir/scripts/oci_adb.sh" -c "$fixture_cmpt"
}

# ── A) ECPU ADB shows GB storage (the regression)
echo "ecpu" > "$mode_file"
set +e; out_a="$(run_adb 2>&1)"; rc_a=$?; set -e
[ "$rc_a" -eq 0 ] || { echo "FAIL A: expected exit 0, got $rc_a"; echo "$out_a"; exit 1; }
printf '%s' "$out_a" | grep -q '500GB' \
  || { echo "FAIL A: ECPU ADB storage should show '500GB' (regression)"; echo "$out_a"; exit 1; }
echo "A ok: ECPU GB storage rendered"

# ── B) legacy OCPU ADB shows TB storage
echo "ocpu" > "$mode_file"
set +e; out_b="$(run_adb 2>&1)"; rc_b=$?; set -e
[ "$rc_b" -eq 0 ] || { echo "FAIL B: expected exit 0, got $rc_b"; echo "$out_b"; exit 1; }
printf '%s' "$out_b" | grep -q '1TB' \
  || { echo "FAIL B: legacy OCPU ADB storage should show '1TB'"; echo "$out_b"; exit 1; }
echo "B ok: OCPU TB storage rendered"

# ── D) the OCID embedded in case B must never appear in output
printf '%s' "$out_b" | grep -qi 'ocid1' \
  && { echo "FAIL D: output leaked an OCID — the lister must print names/states only"; echo "$out_b"; exit 1; }
echo "D ok: no OCID leaked"

# ── C) empty list is a clean exit 0 with guidance
echo "empty" > "$mode_file"
set +e; out_c="$(run_adb 2>&1)"; rc_c=$?; set -e
[ "$rc_c" -eq 0 ] || { echo "FAIL C: expected exit 0 on empty, got $rc_c"; echo "$out_c"; exit 1; }
printf '%s' "$out_c" | grep -qi 'no Autonomous Databases' \
  || { echo "FAIL C: empty list should print the no-ADBs guidance"; echo "$out_c"; exit 1; }
echo "C ok: empty list handled"

echo "oci adb smoke OK"

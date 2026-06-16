#!/usr/bin/env bash
# oci_project_smoke.sh — regression fence for oci_project.sh lifecycle helper.
#
# A stubbed `oci` makes every case deterministic and offline. Asserts:
#   A) status     -> read-only, prints inventory counts, NEVER a raw OCID, exit 0
#   B) bootstrap  -> dry-run prints the mutations (create/tag/budget) but the stub
#                    records ZERO mutating calls actually executed
#   C) teardown   -> prints the ordered destroy plan and destroys nothing (no
#                    terminate/delete reaches the stub)
#   D) status     -> with no compartment, fails fast with a clear message
# Bash 3.2 compatible.
set -euo pipefail

dir="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/oci-project.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
PATH="$tmp:$PATH"

calls="$tmp/calls"; : > "$calls"

# Stub `oci`: log every invocation; return canned JSON for the read verbs used by
# status/teardown. A mutating verb reaching here would be recorded in $calls.
cat > "$tmp/oci" <<EOF
#!/bin/sh
echo "\$*" >> "$calls"
case "\$*" in
  *"compute instance list"*) echo '{"data":[{"lifecycle-state":"RUNNING"}]}' ;;
  *"network vcn list"*)       echo '{"data":[{"id":"x"}]}' ;;
  *"ce cluster list"*)        echo '{"data":[]}' ;;
  *"load-balancer list"*)     echo '{"data":[]}' ;;
  *"cloud-guard problem list"*) echo '{"data":[]}' ;;
  *"monitoring alarm list"*)  echo '{"data":[]}' ;;
  *"budget budget list"*)     echo '[]' ;;
  *"compartment list"*)       echo 'null' ;;
  *)                          echo '{"data":[]}' ;;
esac
EOF
chmod +x "$tmp/oci"

run() { OCI_AUTH_MODE=config OCI_SKILLS_NO_AUDIT=1 bash "$dir/scripts/oci_project.sh" "$@"; }

# Assemble the fixture OCID at RUNTIME — the CI redaction gate scans every tracked
# file, so no full OCID literal may be committed (oci-skills fixture discipline).
ocid_tail="b0gusfixturetail"
CMPT="ocid1.compartment.oc1..${ocid_tail}"

# ── A) status is read-only, prints counts, and never leaks a raw OCID
: > "$calls"
set +e; out_a="$(run status -c "$CMPT" 2>&1)"; rc_a=$?; set -e
[ "$rc_a" -eq 0 ] || { echo "FAIL A: status should exit 0, got $rc_a"; echo "$out_a"; exit 1; }
printf '%s' "$out_a" | grep -q "instance(s)" \
  || { echo "FAIL A: status should print inventory counts"; echo "$out_a"; exit 1; }
printf '%s' "$out_a" | grep -q "$ocid_tail" \
  && { echo "FAIL A: status leaked a raw OCID (must be redacted)"; echo "$out_a"; exit 1; }
grep -qiE 'create|terminate|delete|update' "$calls" \
  && { echo "FAIL A: status must issue no mutating calls"; cat "$calls"; exit 1; }
echo "A ok: status read-only, counts printed, OCID redacted (rc=$rc_a)"

# ── B) bootstrap dry-run prints mutations but executes none
: > "$calls"
set +e
out_b="$(OCI_SKILLS_DRY_RUN=true run bootstrap -n demo -c "$CMPT" -b 500 2>&1)"; rc_b=$?
set -e
[ "$rc_b" -eq 0 ] || { echo "FAIL B: bootstrap dry-run should exit 0, got $rc_b"; echo "$out_b"; exit 1; }
printf '%s' "$out_b" | grep -qi "DRY-RUN" \
  || { echo "FAIL B: bootstrap should announce dry-run"; echo "$out_b"; exit 1; }
printf '%s' "$out_b" | grep -qi "compartment create" \
  || { echo "FAIL B: bootstrap should print the gated compartment create"; echo "$out_b"; exit 1; }
grep -qE 'compartment create|budget create|compartment update' "$calls" \
  && { echo "FAIL B: dry-run must not EXECUTE mutations"; cat "$calls"; exit 1; }
echo "B ok: bootstrap dry-run printed mutations, executed none (rc=$rc_b)"

# ── C) teardown prints the plan and destroys nothing
: > "$calls"
set +e; out_c="$(run teardown -c "$CMPT" 2>&1)"; rc_c=$?; set -e
[ "$rc_c" -eq 0 ] || { echo "FAIL C: teardown should exit 0, got $rc_c"; echo "$out_c"; exit 1; }
printf '%s' "$out_c" | grep -qi "destroy plan" \
  || { echo "FAIL C: teardown should print the ordered destroy plan"; echo "$out_c"; exit 1; }
grep -qiE 'terminate|delete' "$calls" \
  && { echo "FAIL C: teardown must destroy nothing"; cat "$calls"; exit 1; }
echo "C ok: teardown planned, destroyed nothing (rc=$rc_c)"

# ── D) status with no compartment fails fast
: > "$calls"
set +e; out_d="$( unset OCI_SKILLS_COMPARTMENT; run status 2>&1 )"; rc_d=$?; set -e
[ "$rc_d" -ne 0 ] || { echo "FAIL D: status with no compartment should fail, got 0"; echo "$out_d"; exit 1; }
printf '%s' "$out_d" | grep -qi "compartment" \
  || { echo "FAIL D: error should mention the missing compartment"; echo "$out_d"; exit 1; }
echo "D ok: status fails fast without a compartment (rc=$rc_d)"

# ── E) the --budget long flag is accepted as an alias for -b (regression: getopts
#       is short-only, so an undocumented long flag would error out)
: > "$calls"
set +e
out_e="$(OCI_SKILLS_DRY_RUN=true run bootstrap -n demo -c "$CMPT" --budget 500 2>&1)"; rc_e=$?
set -e
[ "$rc_e" -eq 0 ] || { echo "FAIL E: --budget should be accepted, got rc=$rc_e"; echo "$out_e"; exit 1; }
printf '%s' "$out_e" | grep -qi "budget (500)" \
  || { echo "FAIL E: --budget 500 should reach the budget create"; echo "$out_e"; exit 1; }
echo "E ok: --budget long flag accepted (rc=$rc_e)"

# ── F) enriched status surfaces untagged instances, FIRING alarms, and budgets
#       trending over limit (regression: these were claimed in docs but unimplemented)
cat > "$tmp/oci" <<'EOF'
#!/bin/sh
case "$*" in
  *"compute instance list"*) echo '{"data":[{"lifecycle-state":"RUNNING","freeform-tags":{},"defined-tags":{}}]}' ;;
  *"monitoring alarm-status list"*) echo '{"data":[{"status":"FIRING"}]}' ;;
  *"monitoring alarm list"*) echo '{"data":[{"id":"a"}]}' ;;
  *"budget budget list"*) echo '[{"name":"demo","limit":500,"spent":120,"forecast":640}]' ;;
  *) echo '{"data":[]}' ;;
esac
EOF
chmod +x "$tmp/oci"
set +e; out_f="$(run status -c "$CMPT" 2>&1)"; rc_f=$?; set -e
[ "$rc_f" -eq 0 ] || { echo "FAIL F: status should exit 0, got $rc_f"; echo "$out_f"; exit 1; }
printf '%s' "$out_f" | grep -qi "untagged" \
  || { echo "FAIL F: should flag untagged instances"; echo "$out_f"; exit 1; }
printf '%s' "$out_f" | grep -q "FIRING" \
  || { echo "FAIL F: should report FIRING alarms"; echo "$out_f"; exit 1; }
printf '%s' "$out_f" | grep -qi "over limit" \
  || { echo "FAIL F: should flag budget trending over limit"; echo "$out_f"; exit 1; }
echo "F ok: enriched status surfaces untagged/FIRING/over-budget (rc=$rc_f)"

echo "oci project smoke OK"

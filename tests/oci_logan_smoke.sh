#!/usr/bin/env bash
# oci_logan_smoke.sh — regression fence for oci_logan.sh failure handling.
#
# The bug this guards against: the query call used `2>/dev/null || true`, which
# discarded both the stderr and the return code of `oci log-analytics query
# search`. An authorization denial (404 NotAuthorizedOrNotFound) then looked
# IDENTICAL to a genuinely empty result, and the script told the user
# "query returned nothing — inconclusive" while exiting 0. That is a silent
# failure: it hides a permission problem behind a benign-looking message.
#
# Asserts:
#   A) query -> 404 NotAuthorized  => non-zero exit, message names authorization,
#                                     and does NOT claim an inconclusive empty result
#   B) query -> empty item set     => exit 0, the genuine inconclusive-empty guidance
#   C) query -> one row            => exit 0, the row is printed
# A stubbed `oci` makes every case deterministic. Bash 3.2 compatible.
set -euo pipefail

dir="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/oci-logan.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
PATH="$tmp:$PATH"

mode_file="$tmp/mode"

# Stub `oci`: only the query-search call varies by $mode_file; namespace
# resolution is skipped because the test passes -n explicitly.
cat > "$tmp/oci" <<EOF
#!/bin/sh
case "\$*" in
  *"query search"*)
    m=\$(cat "$mode_file")
    case "\$m" in
      denied)
        echo 'ServiceError: { "code": "NotAuthorizedOrNotFound", "status": 404 }' >&2
        exit 1 ;;
      empty)  echo '{"data":{"items":[]}}' ;;
      rows)   echo '{"data":{"items":[{"Event Type":"x.RemoveUserFromGroup","User Name":"someadmin"}]}}' ;;
    esac ;;
  *) echo '{"data":{"items":[]}}' ;;
esac
EOF
chmod +x "$tmp/oci"

run_logan() {
  OCI_AUTH_MODE=config \
  OCI_SKILLS_TENANCY="ocid1.tenancy.oc1..aaaatest" \
  OCI_SKILLS_NO_AUDIT=1 \
    bash "$dir/scripts/oci_logan.sh" \
      -n "testns" -c "ocid1.tenancy.oc1..aaaatest" \
      -q "* | head 1"
}

# ── A) authorization denied must NOT be reported as an empty/inconclusive result
echo "denied" > "$mode_file"
set +e
out_a="$(run_logan 2>&1)"; rc_a=$?
set -e
[ "$rc_a" -ne 0 ] || { echo "FAIL A: expected non-zero exit on auth denial, got 0"; echo "$out_a"; exit 1; }
printf '%s' "$out_a" | grep -qiE 'authoriz|not authorized|permission|denied' \
  || { echo "FAIL A: auth-denied message should name authorization/permission"; echo "$out_a"; exit 1; }
printf '%s' "$out_a" | grep -qi 'inconclusive' \
  && { echo "FAIL A: auth denial must NOT be reported as an inconclusive empty result"; echo "$out_a"; exit 1; }
echo "A ok: auth denial surfaced (rc=$rc_a)"

# ── B) a genuine empty result is exit 0 and flagged inconclusive (not absence)
echo "empty" > "$mode_file"
set +e
out_b="$(run_logan 2>&1)"; rc_b=$?
set -e
[ "$rc_b" -eq 0 ] || { echo "FAIL B: expected exit 0 on empty result, got $rc_b"; echo "$out_b"; exit 1; }
printf '%s' "$out_b" | grep -qi 'inconclusive' \
  || { echo "FAIL B: empty result should be flagged inconclusive"; echo "$out_b"; exit 1; }
echo "B ok: empty result inconclusive (rc=$rc_b)"

# ── C) rows are returned and printed
echo "rows" > "$mode_file"
set +e
out_c="$(run_logan 2>&1)"; rc_c=$?
set -e
[ "$rc_c" -eq 0 ] || { echo "FAIL C: expected exit 0 with rows, got $rc_c"; echo "$out_c"; exit 1; }
printf '%s' "$out_c" | grep -q 'RemoveUserFromGroup' \
  || { echo "FAIL C: expected the row to be printed"; echo "$out_c"; exit 1; }
echo "C ok: rows printed (rc=$rc_c)"

echo "oci logan smoke OK"

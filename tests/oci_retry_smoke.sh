#!/usr/bin/env bash
# oci_retry_smoke.sh — regression fence for oci_cli transient-failure retry
# (common.sh). Verifies: throttling is retried for any verb; 5xx is retried for
# reads but NOT for mutations; non-transient errors fail fast. A stubbed `sleep`
# keeps backoff instant. Bash 3.2 compatible.
set -euo pipefail

dir="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/oci-retry.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
PATH="$tmp:$PATH"

# Instant backoff: shadow `sleep` so the test does not actually wait.
printf '#!/bin/sh\nexit 0\n' > "$tmp/sleep"; chmod +x "$tmp/sleep"

calls="$tmp/calls"

# make_oci FAIL_TIMES ERRTEXT — stub `oci` that fails the first FAIL_TIMES calls
# with ERRTEXT on stderr, then succeeds. Counts invocations in $calls.
make_oci() {
  local fail_times="$1" errtext="$2"
  cat > "$tmp/oci" <<EOF
#!/bin/sh
n=\$(cat "$calls" 2>/dev/null || echo 0); n=\$((n + 1)); echo "\$n" > "$calls"
if [ "\$n" -le $fail_times ]; then echo "$errtext" >&2; exit 1; fi
echo ok
EOF
  chmod +x "$tmp/oci"
  : > "$calls"
}

count() { cat "$calls" 2>/dev/null || echo 0; }

# shellcheck source=scripts/common.sh
source "$dir/scripts/common.sh"

# 1. Throttling on a READ -> retried to success (3 calls: fail, fail, ok).
make_oci 2 "ServiceError: TooManyRequests (429)"
OCI_AUTH_MODE=config OCI_SKILLS_MAX_RETRIES=5 oci_cli iam region list >/dev/null 2>&1
[ "$(count)" = "3" ] || { echo "FAIL: throttle/read expected 3 calls, got $(count)"; exit 1; }

# 2. Throttling on a MUTATION -> still retried (request rejected pre-processing).
make_oci 1 "ServiceError: TooManyRequests (429)"
OCI_AUTH_MODE=config OCI_SKILLS_MAX_RETRIES=5 oci_cli os bucket delete --name x >/dev/null 2>&1
[ "$(count)" = "2" ] || { echo "FAIL: throttle/mutation expected 2 calls, got $(count)"; exit 1; }

# 3. 5xx on a READ -> retried.
make_oci 2 "ServiceError: InternalServerError (500)"
OCI_AUTH_MODE=config OCI_SKILLS_MAX_RETRIES=5 oci_cli compute instance list >/dev/null 2>&1
[ "$(count)" = "3" ] || { echo "FAIL: 5xx/read expected 3 calls, got $(count)"; exit 1; }

# 4. 5xx on a MUTATION -> NOT retried (may have partially applied). 1 call only.
make_oci 5 "ServiceError: InternalServerError (500)"
OCI_AUTH_MODE=config OCI_SKILLS_MAX_RETRIES=5 oci_cli compute instance terminate --instance-id x >/dev/null 2>&1 || true
[ "$(count)" = "1" ] || { echo "FAIL: 5xx/mutation expected 1 call (no retry), got $(count)"; exit 1; }

# 5. Non-transient error on a READ -> fail fast, no retry.
make_oci 5 "ServiceError: NotAuthorizedOrNotFound (404)"
OCI_AUTH_MODE=config OCI_SKILLS_MAX_RETRIES=5 oci_cli iam user list >/dev/null 2>&1 || true
[ "$(count)" = "1" ] || { echo "FAIL: non-transient expected 1 call, got $(count)"; exit 1; }

# 6. Retry budget is bounded: throttling forever -> 1 + MAX_RETRIES calls.
make_oci 99 "TooManyRequests"
OCI_AUTH_MODE=config OCI_SKILLS_MAX_RETRIES=2 oci_cli iam region list >/dev/null 2>&1 || true
[ "$(count)" = "3" ] || { echo "FAIL: budget expected 3 calls (1+2), got $(count)"; exit 1; }

# 7. RETURN CODE FIDELITY (regression: a no-else `if` made oci_cli return 0 on
#    failures, masking errors as success). oci_cli MUST propagate the real rc.
make_oci 5 "ServiceError: NotAuthorizedOrNotFound (404)"
set +e; OCI_AUTH_MODE=config OCI_SKILLS_MAX_RETRIES=5 oci_cli iam user list >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -ne 0 ] || { echo "FAIL: non-transient failure must return non-zero, got rc=0"; exit 1; }

# 8. Exhausted retries (throttle forever) must ALSO return non-zero, not 0.
make_oci 99 "TooManyRequests"
set +e; OCI_AUTH_MODE=config OCI_SKILLS_MAX_RETRIES=2 oci_cli iam region list >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -ne 0 ] || { echo "FAIL: exhausted retries must return non-zero, got rc=0"; exit 1; }

# 9. A successful call returns 0.
make_oci 0 "unused"
set +e; OCI_AUTH_MODE=config oci_cli iam region list >/dev/null 2>&1; rc=$?; set -e
[ "$rc" -eq 0 ] || { echo "FAIL: success must return 0, got rc=$rc"; exit 1; }

echo "oci retry smoke OK"

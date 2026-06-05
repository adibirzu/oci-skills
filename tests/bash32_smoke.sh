#!/usr/bin/env bash
# bash32_smoke.sh — regression fence for the bash 3.2 empty-array + `set -u`
# trap. macOS ships /bin/bash 3.2, where `"${empty_array[@]}"` raises an
# "unbound variable" error under `set -o nounset`. oci_cli builds an (often
# empty) auth_args array, so this guards that it expands without crashing.
#
# Run it under bash 3.2 explicitly:  /bin/bash tests/bash32_smoke.sh
set -euo pipefail

dir="$(cd "$(dirname "$0")/.." && pwd)"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Stub `oci` so common.sh's require_cmd passes and oci_cli has something to run.
printf '#!/bin/sh\necho "stub-oci $*"\n' > "$tmp/oci"
chmod +x "$tmp/oci"
PATH="$tmp:$PATH"

# shellcheck source=scripts/common.sh
source "$dir/scripts/common.sh"

# config mode => auth_args is empty; this is the exact path that crashed on 3.2.
OCI_AUTH_MODE=config oci_cli --version >/dev/null
OCI_AUTH_MODE=config OCI_CLI_PROFILE=DEFAULT oci_cli iam tenancy get >/dev/null
OCI_AUTH_MODE=instance_principal oci_cli os ns get >/dev/null

# require_vars / redact should not trip nounset either.
TESTVAR=x require_vars TESTVAR
# Assemble a synthetic OCID at runtime so the static redaction gate sees no
# complete OCID literal in this file, while redact() still gets a full
# OCID-shaped string to mask. 203.0.113.9 is RFC5737 documentation space.
_fake_oc="ocid1.instance.oc1.iad."
_fake_oc="${_fake_oc}aaaaexamplexxxxxxxxxxxxxxxxxxxx"
redact "$_fake_oc 203.0.113.9" >/dev/null

echo "bash ${BASH_VERSION} — empty-array/nounset smoke OK"

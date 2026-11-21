#!/usr/bin/env bash
set -euo pipefail

# Refuse local linux/amd64 container execution on native ARM64 before any stage.
HOST_ARCH="$(uname -m)"
if [[ "${GATE_FORCE_CONTAINER:-0}" == "1" ]]; then
  case "$HOST_ARCH" in
    arm64|aarch64)
      echo "ERROR: refusing local linux/amd64 container execution on native ARM64 host ($HOST_ARCH) when GATE_FORCE_CONTAINER=1" >&2
      exit 1
      ;;
  esac
  echo "ERROR: container execution is disabled in the workstation gate (GATE_FORCE_CONTAINER=1)" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="python3.11"
  else
    PYTHON_BIN="python3"
  fi
fi

command -v "$PYTHON_BIN" >/dev/null 2>&1 || { echo "required Python interpreter not found: $PYTHON_BIN" >&2; exit 127; }
command -v ruff >/dev/null 2>&1 || { echo "required tool ruff is not installed" >&2; exit 127; }
command -v shellcheck >/dev/null 2>&1 || { echo "required tool shellcheck is not installed" >&2; exit 127; }

echo "[stage 1/6] SBOM freshness (scripts/generate_sbom.py --check)"
"$PYTHON_BIN" scripts/generate_sbom.py --check

echo "[stage 2/6] Package checksum manifest and archive installer smoke (scripts/package_skill_pack.py)"
"$PYTHON_BIN" scripts/package_skill_pack.py --check
GATE_ARCHIVE_TMP="$(mktemp -d "${TMPDIR:-/tmp}/oci-skills-gate-archive.XXXXXX")"
trap 'rm -rf "$GATE_ARCHIVE_TMP"' EXIT
"$PYTHON_BIN" scripts/package_skill_pack.py --build-archive "$GATE_ARCHIVE_TMP/dist" >/dev/null
ARCHIVE_FILE="$(find "$GATE_ARCHIVE_TMP/dist" -maxdepth 1 -name 'oci-skills-*.tar.gz' -print -quit)"
[[ -n "$ARCHIVE_FILE" ]] || { echo "ERROR: package archive was not created" >&2; exit 1; }
mkdir -p "$GATE_ARCHIVE_TMP/extract"
tar -xzf "$ARCHIVE_FILE" -C "$GATE_ARCHIVE_TMP/extract"
EXTRACTED_DIR="$(find "$GATE_ARCHIVE_TMP/extract" -mindepth 1 -maxdepth 1 -type d -print -quit)"
[[ -n "$EXTRACTED_DIR" ]] || { echo "ERROR: extracted package directory not found" >&2; exit 1; }
for adapter in claude gemini codex antigravity; do
  (
    cd "$EXTRACTED_DIR"
    DRY_RUN=true bash install.sh "$adapter" >/dev/null
  )
done
rm -rf "$GATE_ARCHIVE_TMP"
trap - EXIT

echo "[stage 3/6] Redaction gate (scripts/redaction_gate.py)"
git ls-files -z --cached --others --exclude-standard | "$PYTHON_BIN" scripts/redaction_gate.py --root .

echo "[stage 4/6] Python lint (ruff)"
ruff check --select E4,E7,E9,F scripts/*.py tests/test_package_skill_pack.py tests/test_delivery_pipeline_gate.py
ruff check scripts/package_skill_pack.py tests/test_package_skill_pack.py tests/test_delivery_pipeline_gate.py

echo "[stage 5/6] Shell lint (shellcheck)"
shellcheck -x --severity=warning scripts/*.sh scripts/ci/gate.sh install.sh bootstrap.sh

echo "[stage 6/6] Deterministic workstation pytest suites"
"$PYTHON_BIN" -m pytest -q \
  tests/test_package_skill_pack.py \
  tests/test_delivery_pipeline_gate.py \
  tests/test_codex_plugin_manifest.py \
  tests/test_package_readiness.py \
  tests/test_shipped_surface_inventory.py \
  tests/test_operator_inventory.py \
  tests/test_ci_quality_gates.py

echo "Workstation gate passed cleanly on $HOST_ARCH."

#!/usr/bin/env bash
# bootstrap.sh — one-line remote installer for the OCI Administrator skill pack.
#
#   curl -fsSL https://raw.githubusercontent.com/adibirzu/oci-skills/main/bootstrap.sh | bash
#
# Install into specific harnesses only:
#   curl -fsSL https://raw.githubusercontent.com/adibirzu/oci-skills/main/bootstrap.sh | bash -s -- claude codex
#
# It clones (or fast-forwards) the repo into a cache dir, then runs install.sh.
# Override via env: OCI_SKILLS_REPO, OCI_SKILLS_REF, OCI_SKILLS_HOME.

set -o errexit -o nounset -o pipefail

REPO_URL="${OCI_SKILLS_REPO:-https://github.com/adibirzu/oci-skills.git}"
REF="${OCI_SKILLS_REF:-main}"
DEST="${OCI_SKILLS_HOME:-${XDG_DATA_HOME:-$HOME/.local/share}/oci-skills}"

command -v git >/dev/null 2>&1 || { echo "bootstrap: git is required on PATH" >&2; exit 1; }

if [ -d "$DEST/.git" ]; then
  echo "bootstrap: updating $DEST" >&2
  git -C "$DEST" fetch --depth 1 origin "$REF"
  git -C "$DEST" reset --hard "origin/$REF"
else
  echo "bootstrap: cloning into $DEST" >&2
  mkdir -p "$(dirname "$DEST")"
  git clone --depth 1 --branch "$REF" "$REPO_URL" "$DEST"
fi

chmod +x "$DEST/install.sh" 2>/dev/null || true
echo "bootstrap: running installer" >&2
exec "$DEST/install.sh" "$@"

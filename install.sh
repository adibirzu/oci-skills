#!/usr/bin/env bash
# install.sh — install the OCI Administrator skill pack into one or more agent
# harnesses (Claude Code, Codex, Gemini CLI, Antigravity).
#
# Usage:
#   ./install.sh                 # install into every harness that is present
#   ./install.sh claude codex    # install into named harnesses only
#   ./install.sh --list          # show install targets and exit
#   DRY_RUN=true ./install.sh     # print actions, copy nothing
#
# Override any destination with an env var:
#   CLAUDE_SKILLS_DIR  (default ~/.claude/skills)
#   CODEX_SKILLS_DIR   (default ~/.codex/skills)
#   GEMINI_EXT_DIR     (default ~/.gemini/extensions)
#   AGY_SKILLS_DIR     (default ~/.antigravity/skills)

set -o errexit -o nounset -o pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="oci-administrator"
EXT_NAME="oci-skills"

CLAUDE_SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
CODEX_SKILLS_DIR="${CODEX_SKILLS_DIR:-$HOME/.codex/skills}"
GEMINI_EXT_DIR="${GEMINI_EXT_DIR:-$HOME/.gemini/extensions}"
AGY_SKILLS_DIR="${AGY_SKILLS_DIR:-$HOME/.antigravity/skills}"

# Files that make up the shared skill payload (everything the agent reads).
# Canonical skills live under skills/<name>/SKILL.md (plugin-native layout). For
# copy-install we also synthesize a bundle-root SKILL.md so single-skill harnesses
# still find the router at the top of the installed directory.
PAYLOAD=(skills references scripts schemas docs commands hooks AGENTS.md README.md LICENSE evals)
ROUTER_SRC="skills/oci-administrator/SKILL.md"

say()  { printf '[install] %s\n' "$*"; }
warn() { printf '[install][warn] %s\n' "$*" >&2; }

copy_payload() {  # copy_payload <dest_dir>
  local dest="$1"
  if [[ "${DRY_RUN:-}" == "true" ]]; then
    say "DRY-RUN would install payload into $dest"
    return 0
  fi
  mkdir -p "$dest"
  local item
  for item in "${PAYLOAD[@]}"; do
    [[ -e "$REPO_DIR/$item" ]] || continue
    rm -rf "${dest:?}/$item"
    cp -R "$REPO_DIR/$item" "$dest/$item"
  done
  # Synthesize the bundle-root router for single-skill harnesses. The canonical
  # router lives 2 levels deep (skills/oci-administrator/) so its links use
  # ../../ ; at the bundle root those resolve to ./ instead.
  if [[ -f "$REPO_DIR/$ROUTER_SRC" ]]; then
    sed 's#\.\./\.\./#./#g' "$REPO_DIR/$ROUTER_SRC" > "$dest/SKILL.md"
  fi
  find "$dest/scripts" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
}

install_claude() {
  local dest="$CLAUDE_SKILLS_DIR/$SKILL_NAME"
  say "Claude Code -> $dest"
  copy_payload "$dest"
}

install_codex() {
  local dest="$CODEX_SKILLS_DIR/$SKILL_NAME"
  say "Codex -> $dest"
  copy_payload "$dest"
  if [[ "${DRY_RUN:-}" != "true" ]]; then
    mkdir -p "$dest/agents"
    cp "$REPO_DIR/harness/codex/agents/openai.yaml" "$dest/agents/openai.yaml"
  fi
}

install_gemini() {
  local dest="$GEMINI_EXT_DIR/$EXT_NAME"
  say "Gemini CLI -> $dest"
  copy_payload "$dest"
  if [[ "${DRY_RUN:-}" != "true" ]]; then
    cp "$REPO_DIR/harness/gemini/gemini-extension.json" "$dest/gemini-extension.json"
    cp "$REPO_DIR/harness/gemini/GEMINI.md" "$dest/GEMINI.md"
    mkdir -p "$dest/commands"
    cp "$REPO_DIR"/harness/gemini/commands/*.toml "$dest/commands/" 2>/dev/null || true
  fi
}

install_antigravity() {
  local dest="$AGY_SKILLS_DIR/$SKILL_NAME"
  say "Antigravity -> $dest"
  copy_payload "$dest"
  if [[ "${DRY_RUN:-}" != "true" ]]; then
    cp "$REPO_DIR/harness/antigravity/AGENTS.md" "$dest/AGENTS.md"
  fi
}

harness_present() {  # heuristic: parent config dir exists
  case "$1" in
    claude)      [[ -d "$HOME/.claude" ]] ;;
    codex)       [[ -d "$HOME/.codex" ]] ;;
    gemini)      [[ -d "$HOME/.gemini" ]] ;;
    antigravity) [[ -d "$HOME/.antigravity" ]] ;;
    *) return 1 ;;
  esac
}

ALL=(claude codex gemini antigravity)

if [[ "${1:-}" == "--list" ]]; then
  for h in "${ALL[@]}"; do
    if harness_present "$h"; then printf '  %-12s present\n' "$h"; else printf '  %-12s absent\n' "$h"; fi
  done
  exit 0
fi

TARGETS=("$@")
if (( ${#TARGETS[@]} == 0 )); then
  for h in "${ALL[@]}"; do harness_present "$h" && TARGETS+=("$h"); done
  (( ${#TARGETS[@]} > 0 )) || { warn "no known harness found; pass names explicitly, e.g. ./install.sh claude"; exit 1; }
fi

for h in "${TARGETS[@]}"; do
  case "$h" in
    claude)      install_claude ;;
    codex)       install_codex ;;
    gemini)      install_gemini ;;
    antigravity) install_antigravity ;;
    *) warn "unknown harness: $h (valid: ${ALL[*]})" ;;
  esac
done

say "done."

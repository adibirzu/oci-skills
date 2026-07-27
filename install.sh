#!/usr/bin/env bash
# install.sh — install the OCI Administrator skill pack into one or more agent
# harnesses (Claude Code, Codex, Gemini CLI, Antigravity).
#
# Usage:
#   ./install.sh                 # install into every harness that is present
#   ./install.sh claude codex    # install into named harnesses only
#   ./install.sh --list          # show install targets and exit
#   ./install.sh --disable codex # reversibly disable a copy-installed pack
#   ./install.sh --enable codex  # re-enable a disabled copy-installed pack
#   DRY_RUN=true ./install.sh     # print actions, copy nothing
#   OCI_SKILLS_BLINDED_EVAL=true ./install.sh codex  # omit grader material
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
PAYLOAD=(skills references scripts schemas docs commands hooks AGENTS.md README.md LICENSE evals install.sh)
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
    if [[ "${OCI_SKILLS_BLINDED_EVAL:-}" == "true" && "$item" == "evals" ]]; then
      continue
    fi
    [[ -e "$REPO_DIR/$item" ]] || continue
    rm -rf "${dest:?}/$item"
    if [[ -d "$REPO_DIR/$item" ]]; then
      command -v tar >/dev/null 2>&1 || { warn "tar is required to create a safe portable payload"; return 1; }
      if find "$REPO_DIR/$item" -type l -print -quit | grep -q .; then
        warn "refusing to package symlinks from $item"
        return 1
      fi
      local archive
      archive="$(mktemp "${TMPDIR:-/tmp}/oci-skills-payload.XXXXXX")"
      if ! (
        cd "$REPO_DIR"
        tar -cf "$archive" \
          --exclude='.terraform' --exclude='*/.terraform' --exclude='*/.terraform/*' \
          --exclude='__pycache__' --exclude='*/__pycache__' --exclude='*/__pycache__/*' \
          --exclude='.pytest_cache' --exclude='*/.pytest_cache' --exclude='*/.pytest_cache/*' \
          --exclude='.ruff_cache' --exclude='*/.ruff_cache' --exclude='*/.ruff_cache/*' \
          --exclude='*.pyc' --exclude='*.pyo' --exclude='*.tfstate' --exclude='*.tfstate.*' \
          --exclude='*.tfplan' --exclude='*.tfvars' --exclude='*wallet*' \
          --exclude='*.pem' --exclude='*.key' --exclude='*.p12' --exclude='*.pfx' \
          --exclude='terraform-provider-*' "$item"
      ); then
        rm -f "$archive"
        return 1
      fi
      if ! (cd "$dest" && tar -xf "$archive"); then
        rm -f "$archive"
        return 1
      fi
      rm -f "$archive"
    else
      cp "$REPO_DIR/$item" "$dest/$item"
    fi
  done
  # Local interpreter caches are neither runtime assets nor portable. Strip
  # them before applying the stricter blinded-evaluation exclusions below.
  find "$dest" -type d -name '__pycache__' -prune -exec rm -rf {} +
  find "$dest" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
  if [[ "${OCI_SKILLS_BLINDED_EVAL:-}" == "true" ]]; then
    rm -rf "${dest:?}/evals"
    rm -f "$dest/scripts/forward_eval.py" "$dest/scripts/forward_eval_contract.py"
  fi
  # Synthesize the bundle-root router for single-skill harnesses. The canonical
  # router lives 2 levels deep (skills/oci-administrator/) so its links use
  # ../../ ; at the bundle root those resolve to ./ instead.
  if [[ -f "$REPO_DIR/$ROUTER_SRC" ]]; then
    sed 's#\.\./\.\./#./#g' "$REPO_DIR/$ROUTER_SRC" > "$dest/SKILL.md"
  fi
  find "$dest/scripts" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
  chmod +x "$dest/install.sh" 2>/dev/null || true
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

disable_copy_install() {  # disable_copy_install <harness> <dest_dir>
  local harness="$1" dest="$2" skill_root disabled_root disabled
  skill_root="${dest%/*}"
  disabled_root="${skill_root%/*}/disabled"
  disabled="$disabled_root/${dest##*/}"
  if [[ -d "$disabled" && ! -e "$dest" ]]; then
    say "$harness already disabled -> $disabled"
    return 0
  fi
  [[ -d "$dest" ]] || { warn "$harness is not copy-installed at $dest"; return 1; }
  [[ ! -e "$disabled" ]] || { warn "cannot disable $harness: $disabled already exists"; return 1; }
  if [[ "${DRY_RUN:-}" == "true" ]]; then
    say "DRY-RUN would disable $harness by moving $dest -> $disabled"
    return 0
  fi
  mkdir -p "$disabled_root"
  mv "$dest" "$disabled"
  say "$harness disabled -> $disabled"
}

enable_copy_install() {  # enable_copy_install <harness> <dest_dir>
  local harness="$1" dest="$2" skill_root disabled_root disabled
  skill_root="${dest%/*}"
  disabled_root="${skill_root%/*}/disabled"
  disabled="$disabled_root/${dest##*/}"
  if [[ -d "$dest" && ! -e "$disabled" ]]; then
    say "$harness already enabled -> $dest"
    return 0
  fi
  [[ -d "$disabled" ]] || { warn "$harness has no disabled copy-install at $disabled"; return 1; }
  [[ ! -e "$dest" ]] || { warn "cannot enable $harness: $dest already exists"; return 1; }
  if [[ "${DRY_RUN:-}" == "true" ]]; then
    say "DRY-RUN would enable $harness by moving $disabled -> $dest"
    return 0
  fi
  mv "$disabled" "$dest"
  say "$harness enabled -> $dest"
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
MODE="install"
TARGETS=()

while (( $# > 0 )); do
  case "$1" in
    --list)
      [[ "$MODE" == "install" && ${#TARGETS[@]} -eq 0 ]] || { warn "--list cannot be combined with other arguments"; exit 2; }
      MODE="list"
      ;;
    --disable)
      [[ "$MODE" == "install" ]] || { warn "choose only one of --disable or --enable"; exit 2; }
      MODE="disable"
      ;;
    --enable)
      [[ "$MODE" == "install" ]] || { warn "choose only one of --disable or --enable"; exit 2; }
      MODE="enable"
      ;;
    --help|-h)
      sed -n '1,18p' "$0"
      exit 0
      ;;
    --*) warn "unknown option: $1"; exit 2 ;;
    *)
      [[ "$MODE" != "list" ]] || { warn "--list cannot be combined with other arguments"; exit 2; }
      TARGETS+=("$1")
      ;;
  esac
  shift
done

if [[ "$MODE" == "list" ]]; then
  for h in "${ALL[@]}"; do
    if harness_present "$h"; then printf '  %-12s present\n' "$h"; else printf '  %-12s absent\n' "$h"; fi
  done
  exit 0
fi

if (( ${#TARGETS[@]} == 0 )); then
  if [[ "$MODE" != "install" ]]; then
    warn "$MODE requires at least one harness target (for example: ./install.sh --$MODE codex)"
    exit 2
  fi
  for h in "${ALL[@]}"; do harness_present "$h" && TARGETS+=("$h"); done
  (( ${#TARGETS[@]} > 0 )) || { warn "no known harness found; pass names explicitly, e.g. ./install.sh claude"; exit 1; }
fi

for h in "${TARGETS[@]}"; do
  case "$h" in
    claude)
      case "$MODE" in
        install) install_claude ;;
        disable) disable_copy_install "Claude Code" "$CLAUDE_SKILLS_DIR/$SKILL_NAME" ;;
        enable) enable_copy_install "Claude Code" "$CLAUDE_SKILLS_DIR/$SKILL_NAME" ;;
      esac ;;
    codex)
      case "$MODE" in
        install) install_codex ;;
        disable) disable_copy_install "Codex" "$CODEX_SKILLS_DIR/$SKILL_NAME" ;;
        enable) enable_copy_install "Codex" "$CODEX_SKILLS_DIR/$SKILL_NAME" ;;
      esac ;;
    gemini)
      case "$MODE" in
        install) install_gemini ;;
        disable) disable_copy_install "Gemini CLI" "$GEMINI_EXT_DIR/$EXT_NAME" ;;
        enable) enable_copy_install "Gemini CLI" "$GEMINI_EXT_DIR/$EXT_NAME" ;;
      esac ;;
    antigravity)
      case "$MODE" in
        install) install_antigravity ;;
        disable) disable_copy_install "Antigravity" "$AGY_SKILLS_DIR/$SKILL_NAME" ;;
        enable) enable_copy_install "Antigravity" "$AGY_SKILLS_DIR/$SKILL_NAME" ;;
      esac ;;
    *) warn "unknown harness: $h (valid: ${ALL[*]})" ;;
  esac
done

say "done."

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
#   CODEX_SKILLS_DIR   (default ~/.agents/skills)
#   GEMINI_EXT_DIR     (default ~/.gemini/extensions)
#   AGY_SKILLS_DIR     (default ~/.antigravity/skills)

set -o errexit -o nounset -o pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="oci-administrator"
EXT_NAME="oci-skills"

CLAUDE_SKILLS_DIR="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}"
CODEX_SKILLS_DIR="${CODEX_SKILLS_DIR:-$HOME/.agents/skills}"
GEMINI_EXT_DIR="${GEMINI_EXT_DIR:-$HOME/.gemini/extensions}"
AGY_SKILLS_DIR="${AGY_SKILLS_DIR:-$HOME/.antigravity/skills}"

# Files that make up the shared skill payload (everything the agent reads).
# Canonical skills live under skills/<name>/SKILL.md (plugin-native layout). For
# copy-install we also synthesize a bundle-root SKILL.md so single-skill harnesses
# still find the router at the top of the installed directory.
# Copy only the runtime closure.  Development plans, evaluations, source-plugin
# hooks/commands, repository metadata, and contract tooling remain in the
# checkout; a harness does not need them to route or operate a skill.
RUNTIME_DIRECTORIES=(skills references schemas)
RUNTIME_SCRIPTS=(
  common.sh check_doc_links.py iam_audit.py kb_lookup.py oci_adb.sh
  oci_cli_help.py oci_cli_lint.py oci_context.py oci_cost.sh oci_datasafe.sh
  oci_developer_knowledge.py oci_logan.sh oci_oke_demo_troubleshoot.py
  oci_orm.sh oci_preflight.sh oci_project.sh oci_tf.sh oci_tf_plan.py
  enterprise_workflow.py platform_bundle.py redact.py shipped_surface_inventory.py target_derived_plan.py workflow_eval.py
)
RUNTIME_FILES=(docs/product/contracts/developer-knowledge-catalog.json install.sh LICENSE THIRD_PARTY_NOTICES.md SECURITY.md SUPPORT.md)
# A previous installer copied much more than the runtime closure.  Clear only
# paths owned by this pack before rebuilding, so an upgrade cannot retain
# stale docs, evaluator material, hooks, commands, or helper scripts.
OWNED_PAYLOAD_PATHS=(
  skills references schemas scripts docs commands hooks evals agents
  AGENTS.md README.md LICENSE THIRD_PARTY_NOTICES.md SECURITY.md SUPPORT.md SKILL.md GEMINI.md gemini-extension.json install.sh .oci-skills-owned-paths .oci-skills-payload.sha256 install-receipt.json
)
ROUTER_SRC="skills/oci-administrator/SKILL.md"
OWNERSHIP_MANIFEST=".oci-skills-owned-paths"
PAYLOAD_DIGEST=".oci-skills-payload.sha256"
INSTALL_RECEIPT="install-receipt.json"

say()  { printf '[install] %s\n' "$*"; }
warn() { printf '[install][warn] %s\n' "$*" >&2; }
die()  { warn "$*"; exit 1; }

_INSTALL_LOCK_DIR=""
_INSTALL_LOCK_OWNED=false
_INSTALL_STAGE=""
_INSTALL_TRANSACTION_DEST=""
_INSTALL_TRANSACTION_BACKUP=""
_release_install_lock() {
  [[ "$_INSTALL_LOCK_OWNED" == "true" ]] || return 0
  rm -f "$_INSTALL_LOCK_DIR/pid" 2>/dev/null || true
  rmdir "$_INSTALL_LOCK_DIR" 2>/dev/null || true
  _INSTALL_LOCK_OWNED=false
}
_recover_interrupted_install() {
  if [[ -n "$_INSTALL_TRANSACTION_BACKUP" && -e "$_INSTALL_TRANSACTION_BACKUP" && ! -e "$_INSTALL_TRANSACTION_DEST" ]]; then
    mv "$_INSTALL_TRANSACTION_BACKUP" "$_INSTALL_TRANSACTION_DEST" 2>/dev/null || warn "unable to restore prior payload after interruption"
  fi
  if [[ -n "$_INSTALL_STAGE" && -d "$_INSTALL_STAGE" ]]; then
    rm -rf "$_INSTALL_STAGE"
  fi
}
_cleanup_install() {
  local status="$?"
  trap - EXIT
  _recover_interrupted_install
  _release_install_lock
  exit "$status"
}
trap _cleanup_install EXIT

_acquire_install_lock() {  # _acquire_install_lock <lock-directory>
  local lock="$1" owner_pid
  if mkdir "$lock" 2>/dev/null; then
    printf '%s\n' "$$" > "$lock/pid"
    _INSTALL_LOCK_DIR="$lock"
    _INSTALL_LOCK_OWNED=true
    return 0
  fi
  [[ -f "$lock/pid" && ! -L "$lock/pid" ]] || die "another installer holds destination lock: $lock"
  owner_pid="$(cat "$lock/pid" 2>/dev/null || true)"
  [[ "$owner_pid" =~ ^[0-9]+$ ]] || die "another installer holds destination lock: $lock"
  if kill -0 "$owner_pid" 2>/dev/null; then
    die "another installer holds destination lock: $lock"
  fi
  # Only a lock with a well-formed, no-longer-live owner is recoverable. Do not
  # recursively remove unknown filesystem content merely to make an install pass.
  rm -f "$lock/pid"
  rmdir "$lock" 2>/dev/null || die "stale destination lock is not empty: $lock"
  mkdir "$lock" || die "unable to recover stale destination lock: $lock"
  printf '%s\n' "$$" > "$lock/pid"
  _INSTALL_LOCK_DIR="$lock"
  _INSTALL_LOCK_OWNED=true
}

_path_overlaps_source() {  # _path_overlaps_source <candidate>
  local candidate="$1" source
  source="$(cd "$REPO_DIR" && pwd -P)"
  case "$candidate/" in "$source/"*) return 0 ;; esac
  case "$source/" in "$candidate/"*) return 0 ;; esac
  return 1
}

_reject_symlinked_destination_parent() {  # <absolute destination>
  local candidate="$1" parent component current="/"
  parent="$(dirname "$candidate")"
  IFS='/' read -r -a _components <<< "${parent#/}"
  for component in "${_components[@]}"; do
    [[ -n "$component" ]] || continue
    current="$current$component"
    [[ ! -L "$current" ]] || die "install destination parent contains a symlink: $current"
    [[ ! -e "$current" || -d "$current" ]] || die "install destination parent is not a directory: $current"
    current="$current/"
  done
}

_recover_orphaned_payload() {  # <canonical destination>
  local dest="$1" parent backup_count=0 backup="" candidate
  # Recovery changes the destination namespace. It must share the same
  # critical section as the final swap: otherwise a second installer can
  # restore a backup while the first installer is between its two renames.
  [[ "$_INSTALL_LOCK_OWNED" == "true" ]] || die "installer recovery requires the destination lock"
  parent="$(dirname "$dest")"
  for candidate in "$parent/.${SKILL_NAME}.previous."*; do
    [[ -e "$candidate" ]] || continue
    [[ -d "$candidate" && ! -L "$candidate" ]] || die "orphaned installer recovery payload is unsafe: $candidate"
    backup="$candidate"
    backup_count=$((backup_count + 1))
  done
  [[ "$backup_count" -le 1 ]] || die "multiple interrupted installer recovery payloads require manual recovery"
  [[ "$backup_count" -eq 0 ]] && return 0
  if [[ -e "$dest" ]]; then
    die "orphaned installer recovery payload requires manual recovery: $backup"
  fi
  mv "$backup" "$dest" || die "unable to restore prior payload after interrupted install"
  say "recovered prior payload from interrupted install"
}

_require_regular_source() {  # _require_regular_source <repository-relative-path>
  local item="$1"
  [[ -f "$REPO_DIR/$item" && ! -L "$REPO_DIR/$item" ]] || die "missing required source input: $item"
}

_validate_source_payload() {  # _validate_source_payload <adapter>
  # Validate the entire candidate before creating a destination parent, lock, or
  # stage directory.  A partial checkout must never alter an active install.
  local adapter="$1" item
  for item in "${RUNTIME_DIRECTORIES[@]}"; do
    [[ -d "$REPO_DIR/$item" && ! -L "$REPO_DIR/$item" ]] || die "missing required source input: $item"
    if find "$REPO_DIR/$item" -type l -print -quit | grep -q .; then
      die "refusing to package symlinks from $item"
    fi
  done
  for item in "${RUNTIME_FILES[@]}" "${RUNTIME_SCRIPTS[@]/#/scripts/}" "$ROUTER_SRC"; do
    _require_regular_source "$item"
  done
  case "$adapter" in
    codex) _require_regular_source "harness/codex/agents/openai.yaml" ;;
    gemini)
      _require_regular_source "harness/gemini/gemini-extension.json"
      _require_regular_source "harness/gemini/GEMINI.md"
      ;;
    antigravity) _require_regular_source "harness/antigravity/AGENTS.md" ;;
    claude) ;;
    *) die "unknown installer adapter: $adapter" ;;
  esac
}

_remove_previously_owned_paths() {  # _remove_previously_owned_paths <stage-directory>
  local stage="$1" entry first=true
  local -a paths=("${OWNED_PAYLOAD_PATHS[@]}")
  local manifest="$stage/$OWNERSHIP_MANIFEST"
  [[ -e "$manifest" ]] || { for entry in "${paths[@]}"; do rm -rf "${stage:?}/$entry"; done; return 0; }
  [[ -f "$manifest" && ! -L "$manifest" ]] || die "installed ownership manifest is unsafe"
  while IFS= read -r entry || [[ -n "$entry" ]]; do
    if [[ "$first" == true ]]; then
      [[ "$entry" == "schema_version=1" ]] || die "installed ownership manifest schema is invalid"
      first=false
      continue
    fi
    [[ "$entry" =~ ^[A-Za-z0-9._/-]+$ && "$entry" != "." && "$entry" != ".." && "$entry" != /* && "$entry" != */ && "$entry" != *"//"* && "$entry" != ../* && "$entry" != *"/../"* ]] || die "installed ownership manifest path is unsafe"
    paths+=("$entry")
  done < "$manifest"
  [[ "$first" == false ]] || die "installed ownership manifest is empty"
  for entry in "${paths[@]}"; do
    rm -rf "${stage:?}/$entry"
  done
}

_payload_digest() {  # _payload_digest <stage-directory>
  # The installed directory can preserve explicitly user-owned siblings during
  # an ordinary upgrade.  They are not candidate bytes and must never affect
  # the release/evaluation identity.  Hash only paths this installer owns.
  local stage="$1" listing
  command -v shasum >/dev/null 2>&1 || die "shasum is required to validate the staged payload"
  listing="$(mktemp "$stage/.oci-skills-digest.XXXXXX")"
  (
    cd "$stage"
    find . -type l -print -quit | grep -q . && exit 1
    for item in "${OWNED_PAYLOAD_PATHS[@]}"; do
      [[ -e "$item" && ! -L "$item" ]] || continue
      if [[ -d "$item" ]]; then
        find "$item" -type f ! -name "$PAYLOAD_DIGEST" ! -name "$INSTALL_RECEIPT" -exec shasum -a 256 {} +
      else
        [[ "$item" != "$PAYLOAD_DIGEST" && "$item" != "$INSTALL_RECEIPT" ]] || continue
        shasum -a 256 "$item"
      fi
    done | sed 's#  \./#  #' | LC_ALL=C sort -u > "${listing##*/}"
  ) || { rm -f "$listing"; die "unable to calculate staged payload digest"; }
  shasum -a 256 "$listing" | awk '{print $1}'
  rm -f "$listing"
}

_write_install_receipt() {  # _write_install_receipt <stage-directory> <adapter>
  local stage="$1" adapter="$2" digest first=true relative
  digest="$(cat "$stage/$PAYLOAD_DIGEST")"
  {
    printf '{\n  "schema_version": 2,\n'
    printf '  "candidate_sha256": "%s",\n' "$digest"
    # The staged tree is the deterministic source build output copied into the
    # install. It contains no checkout path, revision, command output, or
    # tenant data; its digest binds the source build to this payload.
    printf '  "source_build_sha256": "%s",\n' "$digest"
    printf '  "harness": "%s",\n' "$adapter"
    printf '  "files": [\n'
    while IFS= read -r relative; do
      [[ "$relative" == "$INSTALL_RECEIPT" ]] && continue
      if [[ "$first" == true ]]; then first=false; else printf ',\n'; fi
      printf '    "%s"' "$relative"
    done < <(
      cd "$stage"
      for item in "${OWNED_PAYLOAD_PATHS[@]}"; do
        [[ -e "$item" && ! -L "$item" ]] || continue
        if [[ -d "$item" ]]; then
          find "$item" -type f ! -name "$INSTALL_RECEIPT" -print
        elif [[ "$item" != "$INSTALL_RECEIPT" ]]; then
          printf '%s\n' "$item"
        fi
      done | LC_ALL=C sort -u
    )
    printf '\n  ]\n}\n'
  } > "$stage/$INSTALL_RECEIPT"
  chmod 0600 "$stage/$INSTALL_RECEIPT"
}

_validate_staged_payload() {  # _validate_staged_payload <stage-directory>
  local stage="$1" expected actual
  [[ -f "$stage/SKILL.md" && -f "$stage/LICENSE" && -f "$stage/THIRD_PARTY_NOTICES.md" && -f "$stage/SECURITY.md" && -f "$stage/SUPPORT.md" ]] || die "staged payload is incomplete"
  expected="$(cat "$stage/$PAYLOAD_DIGEST" 2>/dev/null || true)"
  [[ "$expected" =~ ^[0-9a-f]{64}$ ]] || die "staged payload digest is invalid"
  actual="$(_payload_digest "$stage")"
  [[ "$actual" == "$expected" ]] || die "staged payload digest mismatch"
}

copy_payload() {  # copy_payload <dest_dir> [adapter]
  local dest="$1" adapter="${2:-}" parent stage backup item
  _validate_source_payload "$adapter"
  if [[ "${DRY_RUN:-}" == "true" ]]; then
    say "DRY-RUN would install payload into $dest"
    return 0
  fi

  # Resolve before any write: installing into (or replacing) the checkout
  # would destroy the candidate while it is being packaged.
  if [[ "$dest" != /* ]]; then dest="$PWD/$dest"; fi
  _reject_symlinked_destination_parent "$dest"
  if _path_overlaps_source "$dest"; then
    die "install destination overlaps the source checkout: $dest"
  fi
  mkdir -p "$(dirname "$dest")"
  parent="$(cd "$(dirname "$dest")" && pwd -P)"
  dest="$parent/${dest##*/}"
  if _path_overlaps_source "$dest"; then
    die "install destination overlaps the source checkout: $dest"
  fi
  _acquire_install_lock "$(dirname "$dest")/.${SKILL_NAME}.install.lock"
  _recover_orphaned_payload "$dest"
  stage="$(mktemp -d "$(dirname "$dest")/.${SKILL_NAME}.stage.XXXXXX")"
  _INSTALL_STAGE="$stage"
  # A staged replacement retains user-owned paths, but refuses symlinked
  # installed payloads rather than following an attacker-controlled path.
  if [[ -d "$dest" ]]; then
    if find "$dest" -type l -print -quit | grep -q .; then
      rm -rf "$stage"
      die "refusing to replace an installed payload containing symlinks"
    fi
    cp -a "$dest/." "$stage/"
  fi
  _remove_previously_owned_paths "$stage"
  for item in "${RUNTIME_DIRECTORIES[@]}" "${RUNTIME_FILES[@]}"; do
    [[ -e "$REPO_DIR/$item" ]] || continue
    rm -rf "${stage:?}/$item"
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
      if ! (cd "$stage" && tar -xf "$archive"); then
        rm -f "$archive"
        rm -rf "$stage"
        return 1
      fi
      rm -f "$archive"
    else
      mkdir -p "$(dirname "$stage/$item")"
      cp "$REPO_DIR/$item" "$stage/$item"
    fi
  done
  mkdir -p "$stage/scripts"
  for item in "${RUNTIME_SCRIPTS[@]}"; do
    cp "$REPO_DIR/scripts/$item" "$stage/scripts/$item"
  done
  # Local interpreter caches are neither runtime assets nor portable. Strip
  # them before applying the stricter blinded-evaluation exclusions below.
  find "$stage" -type d -name '__pycache__' -prune -exec rm -rf {} +
  find "$stage" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete
  # Synthesize the bundle-root router for single-skill harnesses. The canonical
  # router lives 2 levels deep (skills/oci-administrator/) so its links use
  # ../../ ; at the bundle root those resolve to ./ instead.
  if [[ -f "$REPO_DIR/$ROUTER_SRC" ]]; then
    sed 's#\.\./\.\./#./#g' "$REPO_DIR/$ROUTER_SRC" > "$stage/SKILL.md"
  fi
  case "$adapter" in
    codex) mkdir -p "$stage/agents"; cp "$REPO_DIR/harness/codex/agents/openai.yaml" "$stage/agents/openai.yaml" ;;
    gemini) cp "$REPO_DIR/harness/gemini/gemini-extension.json" "$stage/gemini-extension.json"; cp "$REPO_DIR/harness/gemini/GEMINI.md" "$stage/GEMINI.md"; mkdir -p "$stage/commands"; cp "$REPO_DIR"/harness/gemini/commands/*.toml "$stage/commands/" 2>/dev/null || true ;;
    antigravity) cp "$REPO_DIR/harness/antigravity/AGENTS.md" "$stage/AGENTS.md" ;;
  esac
  find "$stage/scripts" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
  chmod +x "$stage/install.sh" 2>/dev/null || true
  # The manifest is an auditable declaration of the paths this pack may replace
  # on a later upgrade. Anything else copied from a prior installation remains
  # user-owned and is preserved in the staged payload.
  {
    printf 'schema_version=1\n'
    printf '%s\n' "${OWNED_PAYLOAD_PATHS[@]}"
  } > "$stage/$OWNERSHIP_MANIFEST"
  _payload_digest "$stage" > "$stage/$PAYLOAD_DIGEST"
  _write_install_receipt "$stage" "$adapter"
  _validate_staged_payload "$stage"

  backup="$(dirname "$dest")/.${SKILL_NAME}.previous.$$"
  [[ ! -e "$backup" ]] || { rm -rf "$stage"; die "previous installer recovery directory exists: $backup"; }
  _INSTALL_TRANSACTION_DEST="$dest"
  _INSTALL_TRANSACTION_BACKUP="$backup"
  if [[ -e "$dest" ]]; then mv "$dest" "$backup"; fi
  # A destination that reappears after the old payload was moved is outside
  # this transaction. Refuse to let mv nest the new staged directory inside it
  # or overwrite a concurrently-created payload. Leave both recovery inputs
  # intact for an explicit operator decision.
  [[ ! -e "$dest" ]] || die "install destination reappeared during replacement; manual recovery required"
  if ! mv "$stage" "$dest"; then
    [[ ! -e "$backup" ]] || mv "$backup" "$dest"
    die "staged install swap failed; prior payload restored"
  fi
  rm -rf "$backup"
  _INSTALL_STAGE=""
  _INSTALL_TRANSACTION_DEST=""
  _INSTALL_TRANSACTION_BACKUP=""
  _release_install_lock
}

install_claude() {
  local dest="$CLAUDE_SKILLS_DIR/$SKILL_NAME"
  say "Claude Code -> $dest"
  copy_payload "$dest" claude
}

install_codex() {
  local dest="$CODEX_SKILLS_DIR/$SKILL_NAME"
  if [[ "${OCI_SKILLS_BLINDED_EVAL:-false}" == "true" ]]; then
    # A blinded evaluation is meaningful only when no prior candidate, plugin,
    # or user-authored material can be discovered from its native skills root.
    # Do this before the regular installer creates a destination parent.
    [[ ! -e "$CODEX_SKILLS_DIR" || ( -d "$CODEX_SKILLS_DIR" && ! -L "$CODEX_SKILLS_DIR" ) ]] \
      || die "blinded evaluation skills root is unsafe"
    if [[ -d "$CODEX_SKILLS_DIR" ]] && find "$CODEX_SKILLS_DIR" -mindepth 1 -maxdepth 1 -print -quit | grep -q .; then
      die "blinded evaluation requires an empty Codex skills root"
    fi
    [[ ! -e "$dest" ]] || die "blinded evaluation requires a fresh candidate destination"
  elif [[ "${OCI_SKILLS_BLINDED_EVAL:-false}" != "false" && -n "${OCI_SKILLS_BLINDED_EVAL:-}" ]]; then
    die "OCI_SKILLS_BLINDED_EVAL must be true or false"
  fi
  say "Codex -> $dest"
  copy_payload "$dest" codex
}

install_gemini() {
  local dest="$GEMINI_EXT_DIR/$EXT_NAME"
  say "Gemini CLI -> $dest"
  copy_payload "$dest" gemini
}

install_antigravity() {
  local dest="$AGY_SKILLS_DIR/$SKILL_NAME"
  say "Antigravity -> $dest"
  copy_payload "$dest" antigravity
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

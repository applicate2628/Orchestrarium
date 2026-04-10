#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SCRIPT_DIR/src.gemini"
MANAGED_START='<!-- ORCHESTRARIUM_GEMINI_PACK:START -->'
MANAGED_END='<!-- ORCHESTRARIUM_GEMINI_PACK:END -->'
FORCE=0
DRY_RUN=0
ALLOW_UNSAFE_TARGET=0
MODE="repo"
TARGET=""

usage() {
  cat <<'EOF'
Usage:
  bash install-gemini.sh                    Install into current repo (GEMINI.md + .gemini/)
  bash install-gemini.sh --global           Install into ~/.gemini/
  bash install-gemini.sh --target DIR       Install into DIR as a project root
  bash install-gemini.sh --force            Skip confirmation prompts
  bash install-gemini.sh --dry-run          Print planned actions without changing files
  bash install-gemini.sh --allow-unsafe-target
                                           Allow a custom project root outside the current repo
EOF
  exit 1
}

canonical_path() {
  local path="$1"
  path="${path/#\~/$HOME}"
  if [[ -z "$path" ]]; then
    echo "" >&2
    return 1
  fi
  local py_bin="python"
  if ! command -v "$py_bin" >/dev/null 2>&1; then
    py_bin="python3"
  fi
  if ! command -v "$py_bin" >/dev/null 2>&1; then
    echo "FAIL: python or python3 is required for path normalization." >&2
    return 1
  fi
  if [[ -e "$path" || -L "$path" ]]; then
    "$py_bin" - "$path" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).resolve())
PY
  else
    "$py_bin" - "$path" <<'PY'
from pathlib import Path
import sys
print(Path(sys.argv[1]).expanduser().resolve(strict=False))
PY
  fi
}

repo_root() {
  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    git rev-parse --show-toplevel
  else
    pwd
  fi
}

resolve_project_root() {
  local input="$1"
  local resolved
  resolved="$(canonical_path "$input")"
  if [[ "$(basename "$resolved")" == ".gemini" ]]; then
    dirname "$resolved"
  else
    printf "%s" "$resolved"
  fi
}

ensure_dir() {
  local path="$1"
  if [[ ! -d "$path" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would create $path"
    else
      mkdir -p "$path"
    fi
  fi
}

confirm_action() {
  local prompt="$1"
  if [[ "$FORCE" -eq 1 || "$DRY_RUN" -eq 1 || ! -t 0 ]]; then
    return 0
  fi
  while true; do
    read -r -p "$prompt [y/N] " answer
    case "${answer,,}" in
      y|yes) return 0 ;;
      ""|n|no) return 1 ;;
      *) echo "Please answer y or n." ;;
    esac
  done
}

install_tree() {
  local src="$1" dst="$2" label="$3"
  local item_name
  local pack_items=()
  ensure_dir "$dst"
  echo "  Installing $label (per-item, preserving user-added items)..."
  shopt -s nullglob
  for item in "$src"/*; do
    item_name="$(basename "$item")"
    pack_items+=("$item_name")
    if [[ -e "$dst/$item_name" ]]; then
      if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "    [dry-run] would replace $label/$item_name"
      else
        rm -rf "$dst/$item_name"
        cp -r "$item" "$dst/$item_name"
      fi
    else
      if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "    [dry-run] would install $label/$item_name"
      else
        cp -r "$item" "$dst/$item_name"
      fi
    fi
  done
  for existing in "$dst"/*; do
    local found=0
    item_name="$(basename "$existing")"
    for pack_item in "${pack_items[@]}"; do
      if [[ "$pack_item" == "$item_name" ]]; then
        found=1
        break
      fi
    done
    if [[ "$found" -eq 0 ]]; then
      echo "  Preserved user item: $label/$item_name"
    fi
  done
  shopt -u nullglob
}

merge_gemini_file() {
  local src="$1" dst="$2"
  local managed existing
  local py_bin="python"
  if ! command -v "$py_bin" >/dev/null 2>&1; then
    py_bin="python3"
  fi
  managed="$(cat "$src")"
  if [[ ! -f "$dst" ]]; then
    echo "  Creating GEMINI.md..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would create $dst"
    else
      printf '%s' "$managed" > "$dst"
    fi
    return
  fi

  existing="$(cat "$dst")"
  if grep -qF "$MANAGED_START" "$dst" && grep -qF "$MANAGED_END" "$dst"; then
    echo "  GEMINI.md: replacing managed Orchestrarium block..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would replace managed GEMINI.md block"
    else
      "$py_bin" - "$dst" "$src" "$MANAGED_START" "$MANAGED_END" <<'PY'
from pathlib import Path
import re
import sys
dst = Path(sys.argv[1])
src = Path(sys.argv[2])
start = re.escape(sys.argv[3])
end = re.escape(sys.argv[4])
managed = src.read_text(encoding="utf-8")
text = dst.read_text(encoding="utf-8")
updated = re.sub(start + r"[\s\S]*?" + end, managed, text, count=1)
dst.write_text(updated, encoding="utf-8")
PY
    fi
  else
    echo "  GEMINI.md: prepending managed Orchestrarium block..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would prepend managed GEMINI.md block"
    else
      printf '%s\n\n%s' "$managed" "$existing" > "$dst"
    fi
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --global)
      MODE="global"
      shift
      ;;
    --target)
      [[ $# -lt 2 ]] && usage
      MODE="target"
      TARGET="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --allow-unsafe-target)
      ALLOW_UNSAFE_TARGET=1
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      ;;
  esac
done

if [[ ! -d "$SOURCE/skills" || ! -d "$SOURCE/commands" || ! -f "$SOURCE/GEMINI.md" ]]; then
  echo "FAIL: src.gemini is incomplete at $SOURCE" >&2
  exit 1
fi

if [[ "$MODE" == "global" ]]; then
  INSTALL_ROOT="$(canonical_path "$HOME/.gemini")"
  GEMINI_TARGET="$INSTALL_ROOT/GEMINI.md"
  SKILLS_TARGET="$INSTALL_ROOT/skills"
  COMMANDS_TARGET="$INSTALL_ROOT/commands"
else
  PROJECT_ROOT="$(resolve_project_root "${TARGET:-$(repo_root)}")"
  if [[ "$MODE" == "target" && "$ALLOW_UNSAFE_TARGET" -ne 1 ]]; then
    CURRENT_REPO="$(canonical_path "$(repo_root)")"
    if [[ "$(printf '%s' "$PROJECT_ROOT" | tr '[:upper:]' '[:lower:]')" != "$(printf '%s' "$CURRENT_REPO" | tr '[:upper:]' '[:lower:]')" ]]; then
      echo "FAIL: unsafe target denied for non-default project root '$PROJECT_ROOT'. Use --allow-unsafe-target." >&2
      exit 1
    fi
  fi
  INSTALL_ROOT="$PROJECT_ROOT/.gemini"
  GEMINI_TARGET="$PROJECT_ROOT/GEMINI.md"
  SKILLS_TARGET="$INSTALL_ROOT/skills"
  COMMANDS_TARGET="$INSTALL_ROOT/commands"
fi

echo "=== Orchestrarium Gemini Installer ==="
echo "Source: $SOURCE"
echo "Mode:   $MODE"
echo "Runtime root: $INSTALL_ROOT"
echo "GEMINI.md:    $GEMINI_TARGET"
[[ "$DRY_RUN" -eq 1 ]] && echo "Mode:   dry-run"
echo

if [[ -e "$GEMINI_TARGET" || -d "$SKILLS_TARGET" || -d "$COMMANDS_TARGET" ]]; then
  if ! confirm_action "Proceed with reinstall/update of the Gemini pack?"; then
    echo "Install cancelled by user." >&2
    exit 1
  fi
fi

ensure_dir "$INSTALL_ROOT"
install_tree "$SOURCE/skills" "$SKILLS_TARGET" "skills"
install_tree "$SOURCE/commands" "$COMMANDS_TARGET" "commands"
merge_gemini_file "$SOURCE/GEMINI.md" "$GEMINI_TARGET"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo
  echo "RESULT: DRY-RUN complete (no files modified)."
  exit 0
fi

echo
echo "=== Verification ==="
errors=0
for path in \
  "$GEMINI_TARGET" \
  "$SKILLS_TARGET/README.md" \
  "$SKILLS_TARGET/lead/SKILL.md" \
  "$SKILLS_TARGET/init-project/SKILL.md" \
  "$COMMANDS_TARGET/agents/help.toml" \
  "$COMMANDS_TARGET/agents/init-project.toml"; do
  if [[ -e "$path" ]]; then
    echo "  OK  $path"
  else
    echo "  FAIL  $path"
    errors=$((errors+1))
  fi
done

if [[ "$errors" -gt 0 ]]; then
  echo
  echo "RESULT: FAIL ($errors errors)"
  exit 1
fi

echo
echo "RESULT: OK - Gemini pack installed"

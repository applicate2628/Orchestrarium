#!/usr/bin/env bash
# Install Claudestrator skill-pack.
# Usage:
#   bash install.sh                  install into current repo (.claude/)
#   bash install.sh --global         install into ~/.claude/
#   bash install.sh --target DIR     install into DIR/.claude/ (or DIR if DIR ends with .claude)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SCRIPT_DIR/src.claude"

# Directories to install (order doesn't matter)
DIRS=(agents commands)
OPTIONAL_DIRS=(memory)
FORCE=0
DRY_RUN=0
ALLOW_UNSAFE_TARGET=0
MODE=""
TARGET=""

usage() {
  echo "Usage:"
  echo "  bash install.sh                          Install into current repo (.claude/)"
  echo "  bash install.sh --global                 Install into ~/.claude/"
  echo "  bash install.sh --target DIR             Install into DIR/.claude/"
  echo "  bash install.sh --force                  Skip deletion prompts"
  echo "  bash install.sh --dry-run                Print planned actions without changing files"
  echo "  bash install.sh --allow-unsafe-target    Override allowlist for custom target path"
  echo "  bash install.sh --help                   Show help"
  exit 1
}

canonical_path() {
  local input_path="$1"
  local expanded="${input_path/#\~/$HOME}"

  if [ -z "$expanded" ]; then
    echo "" 
    return 1
  fi

  if [ -d "$expanded" ] || [ -L "$expanded" ]; then
    local resolved
    resolved="$(cd "$expanded" && pwd -P)"
    echo "$resolved"
    return 0
  fi

  # For non-existing paths, resolve component-by-component preserving all
  # virtual segments so we keep the intended directory structure.
  local result=""
  local part
  local next

  if [ "${expanded:0:1}" = "/" ]; then
    result="/"
  else
    result="$(pwd -P)"
  fi

  local IFS='/'
  for part in ${expanded}; do
    case "$part" in
      ""|".")
        continue
        ;;
      "..")
        result="$(dirname "$result")"
        if [ -z "$result" ]; then
          result="/"
        fi
        ;;
      *)
        next="$result/$part"
        if [ "$result" = "/" ]; then
          next="/$part"
        fi

        if [ -e "$next" ] || [ -L "$next" ]; then
          if [ -d "$next" ] || [ -L "$next" ]; then
            next="$(cd "$next" && pwd -P)"
          fi
        fi

        result="$next"
        ;;
    esac
  done

  echo "$result"
}

resolve_install_target() {
  local input_path="$1"
  local normalized

  normalized="$(canonical_path "$input_path")"
  if [ -z "$normalized" ]; then
    echo "FAIL: unable to resolve target path '$input_path'" >&2
    return 1
  fi

  if [ "$(basename "$normalized")" = ".claude" ]; then
    printf "%s" "$normalized"
  else
    printf "%s/.claude" "$normalized"
  fi
}

path_has_reparse_component() {
  local path="$1"
  local current="$path"

  while :; do
    if [ -e "$current" ] && [ -L "$current" ]; then
      return 0
    fi

    local parent
    parent="$(dirname "$current")"
    if [ "$parent" = "$current" ] || [ -z "$parent" ]; then
      break
    fi
    current="$parent"
  done

  return 1
}

is_allowed_target() {
  local target="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  local candidate
  for candidate in "${ALLOWLIST[@]}"; do
    candidate="$(printf '%s' "$candidate" | tr '[:upper:]' '[:lower:]')"
    if [ "$target" = "$candidate" ]; then
      return 0
    fi
  done
  return 1
}

validate_target_root() {
  local path="$1"
  local mode="$2"

  if path_has_reparse_component "$path"; then
    echo "FAIL: target path '$path' contains a symlink/junction component." >&2
    return 1
  fi

  local target
  target="$(resolve_install_target "$path")"
  local target_lower
  target_lower="$(printf '%s' "$target" | tr '[:upper:]' '[:lower:]')"

  if [ -z "$target_lower" ]; then
    echo "FAIL: empty target" >&2
    return 1
  fi

  if [ "$(basename "$target_lower")" != ".claude" ]; then
    echo "FAIL: target '$target' must resolve to .claude directory" >&2
    return 1
  fi

  if [ "$mode" = "target" ] && [ "$ALLOW_UNSAFE_TARGET" -ne 1 ]; then
    if ! is_allowed_target "$target"; then
      if [ -t 0 ]; then
        while :; do
          echo "WARNING: target '$target' is outside the default allowlist."
          read -r -p "Type ALLOW to proceed with this target, or press Enter to abort: " confirm
          if [ "${confirm^^}" = "ALLOW" ]; then
            break
          fi
          if [ -z "$confirm" ]; then
            echo "Install cancelled: unsafe target denied." >&2
            return 1
          fi
          echo "Please type ALLOW to continue, or press Enter to cancel." >&2
        done
      else
        echo "FAIL: unsafe target denied for non-interactive install. Use --allow-unsafe-target." >&2
        return 1
      fi
    fi
  fi

  printf "%s" "$target"
}

build_allowlist() {
  ALLOWLIST=()
  local repo_root

  if git rev-parse --show-toplevel &>/dev/null; then
    repo_root="$(git rev-parse --show-toplevel)"
  else
    repo_root="$(pwd)"
  fi

  if [ "$MODE" = "repo" ] || [ "$MODE" = "target" ]; then
    ALLOWLIST+=("$(resolve_install_target "$repo_root")")
  fi

  if [ "$MODE" = "global" ] || [ "$MODE" = "target" ]; then
    ALLOWLIST+=("$(resolve_install_target "$HOME")")
  fi

  if [ -n "${CLAUDE_INSTALL_ALLOWLIST:-}" ]; then
    IFS=',' read -r -a ALLOWLIST_EXTRA <<< "$CLAUDE_INSTALL_ALLOWLIST"
    for raw in "${ALLOWLIST_EXTRA[@]}"; do
      if [ -n "$raw" ]; then
        ALLOWLIST+=("$(resolve_install_target "$raw")")
      fi
    done
  fi

  # normalize duplicates
  local dedup=()
  local existing
  for entry in "${ALLOWLIST[@]}"; do
    local norm
    norm="$(printf '%s' "$entry" | tr '[:upper:]' '[:lower:]')"
    if [ -z "$norm" ]; then
      continue
    fi
    existing=0
    for item in "${dedup[@]}"; do
      if [ "$(printf '%s' "$item" | tr '[:upper:]' '[:lower:]')" = "$norm" ]; then
        existing=1
        break
      fi
    done
    if [ "$existing" -ne 1 ]; then
      dedup+=("$entry")
    fi
  done
  ALLOWLIST=("${dedup[@]}")
}

confirm_removal() {
  local path="$1"
  local name
  name="$(basename "$path")"

  if [ "$FORCE" -eq 1 ] || [ "$DRY_RUN" -eq 1 ]; then
    return 0
  fi

  while true; do
    read -r -p "Delete existing '$name' at '$path' before reinstall? [y/N] " answer
    case "${answer,,}" in
      y|yes)
        return 0
        ;;
      n|no|"")
        return 1
        ;;
      *)
        echo "Please answer y or n."
        ;;
    esac
  done
}

# Per-item install preserves user-added files — no destructive directory wipe needed.

prompt_install_mode() {
  if [ ! -t 0 ]; then
    echo "FAIL: No install target specified and not running interactively." >&2
    echo "Use: bash install.sh --global  or  bash install.sh --target <path>" >&2
    exit 1
  fi

  while true; do
    echo "Select installation target:"
    echo "  1) Local repo (.claude/)"
    echo "  2) Global (~/.claude/)"
    echo "  3) Custom target directory"
    echo "  4) Abort"
    echo -n "Choose [1-4, default: 1]: "
    read -r choice
    choice="${choice:-1}"

    case "$choice" in
      1)
        MODE="repo"
        return
        ;;
      2)
        MODE="global"
        TARGET="$HOME/.claude"
        return
        ;;
      3)
        MODE="target"
        while true; do
          echo -n "Enter target directory path: "
          read -r custom
          if [ -z "$custom" ]; then
            echo "Target cannot be empty." >&2
            continue
          fi
          TARGET="$custom"
          return
        done
        ;;
      4)
        echo "Install aborted by user." >&2
        exit 1
        ;;
      *)
        echo "Please enter 1, 2, 3, or 4."
        ;;
    esac
  done
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --global)
      MODE="global"
      TARGET="$HOME/.claude"
      shift
      ;;
    --target)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --target." >&2
        usage
      fi
      TARGET="$2"
      MODE="target"
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
      echo "Unknown option: $1"
      usage
      ;;
  esac
done

if [ -z "$MODE" ]; then
  prompt_install_mode
  if [ "$MODE" != "repo" ] && [ "$MODE" != "global" ] && [ "$MODE" != "target" ]; then
    MODE="repo"
  fi

  if [ -z "$TARGET" ]; then
    if [ "$MODE" = "repo" ]; then
      if git rev-parse --show-toplevel &>/dev/null; then
        TARGET="$(git rev-parse --show-toplevel)/.claude"
      else
        TARGET="$(pwd)/.claude"
      fi
    elif [ "$MODE" = "global" ]; then
      TARGET="$HOME/.claude"
    else
      echo "Missing target path in non-interactive mode." >&2
      usage
    fi
  fi
fi

if [ "$MODE" = "repo" ] || [ "$MODE" = "global" ] || [ "$MODE" = "target" ]; then
  build_allowlist
  TARGET="$(validate_target_root "$TARGET" "$MODE")"
else
  echo "Invalid mode '$MODE'." >&2
  usage
fi

echo "=== Claudestrator Installer ==="
echo "Source: $SOURCE"
echo "Target: $TARGET"
echo "Mode:   $MODE"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "Mode:   dry-run"
fi
echo

# Verify source
if [[ ! -d "$SOURCE/agents" ]]; then
  echo "FAIL: Source directory $SOURCE/agents not found."
  echo "Run this script from the Claudestrator repo root."
  exit 1
fi

if [[ ! -d "$TARGET" ]]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] would create target root: $TARGET"
  else
    mkdir -p "$TARGET"
  fi
fi

# Per-item install: only replace pack items, preserve user-added files
install_item() {
  local src="$1" dst="$2"
  if [[ -e "$dst" ]]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would replace $(basename "$dst")"
    else
      rm -rf "$dst"
      cp -r "$src" "$dst"
    fi
  else
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would install $(basename "$dst")"
    else
      cp -r "$src" "$dst"
    fi
  fi
}

# Count existing items and confirm reinstall
if [ "$FORCE" -ne 1 ] && [ "$DRY_RUN" -ne 1 ] && [ -t 0 ]; then
  existing_total=0
  pack_total=0
  for dir in "${DIRS[@]}"; do
    dst="$TARGET/$dir"
    src="$SOURCE/$dir"
    if [[ -d "$dst" ]]; then
      for f in "$dst"/*; do [[ -e "$f" ]] && existing_total=$((existing_total + 1)); done
    fi
    for f in "$src"/*; do [[ -e "$f" ]] && pack_total=$((pack_total + 1)); done
  done
  if [ "$existing_total" -gt 0 ]; then
    user_count=$((existing_total - pack_total))
    if [ "$user_count" -lt 0 ]; then user_count=0; fi
    echo ""
    echo "  Reinstall will replace $pack_total pack items. $user_count user item(s) will be preserved."
    while true; do
      read -r -p "  Proceed? [y/N] " answer
      case "${answer,,}" in
        y|yes) break ;;
        n|no|"") echo "Install cancelled by user." >&2; exit 1 ;;
        *) echo "  Please answer y or n." ;;
      esac
    done
  fi
fi

for dir in "${DIRS[@]}"; do
  src="$SOURCE/$dir"
  dst="$TARGET/$dir"

  echo "  Installing $dir/ (per-item, preserving user-added files)..."
  if [[ ! -d "$dst" ]]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would create $dst"
    else
      mkdir -p "$dst"
    fi
  fi

  # Copy subdirectories (e.g., agents/contracts/, agents/team-templates/, agents/scripts/)
  for sub in "$src"/*/; do
    [[ -d "$sub" ]] || continue
    sub_name="$(basename "$sub")"
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would replace $dir/$sub_name/"
    else
      rm -rf "$dst/$sub_name"
      cp -r "$sub" "$dst/$sub_name"
    fi
  done

  # Copy individual files (e.g., agents/*.md, commands/*.md)
  pack_items=()
  for item in "$src"/*; do
    [[ -f "$item" ]] || continue
    item_name="$(basename "$item")"
    pack_items+=("$item_name")
    install_item "$item" "$dst/$item_name"
  done

  # Report preserved user files
  for existing in "$dst"/*; do
    [[ -f "$existing" ]] || continue
    existing_name="$(basename "$existing")"
    is_pack=0
    for pi in "${pack_items[@]}"; do
      if [[ "$pi" == "$existing_name" ]]; then is_pack=1; break; fi
    done
    if [[ $is_pack -eq 0 ]]; then
      # Check it's not in a subdirectory (those were fully replaced)
      echo "  Preserved user file: $dir/$existing_name"
    fi
  done
done

# Optional dirs: copy if not present, don't overwrite
for dir in "${OPTIONAL_DIRS[@]}"; do
  src="$SOURCE/$dir"
  dst="$TARGET/$dir"
  if [[ -d "$dst" ]]; then
    echo "  Keeping existing $dir/ (optional, not overwritten)"
  elif [[ -d "$src" ]]; then
    echo "  Installing $dir/ (optional)..."
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would copy $src -> $dst"
    else
      cp -r "$src" "$dst"
    fi
  fi
done

# CLAUDE.md: merge or create
src_md="$SOURCE/CLAUDE.md"
dst_md="$TARGET/CLAUDE.md"

if [[ -f "$dst_md" ]]; then
  content="$(cat "$dst_md")"
  if grep -q "## Delegation rule" "$dst_md" 2>/dev/null; then
    if grep -qn "^# Claudestrator" "$dst_md"; then
      echo "  CLAUDE.md: replacing Claudestrator section..."
      head_lines=$(($(grep -n "^# Claudestrator" "$dst_md" | head -1 | cut -d: -f1) - 1))
      if [[ $head_lines -gt 0 ]]; then
        if [ "$DRY_RUN" -eq 1 ]; then
          echo "    [dry-run] would replace Claudestrator section in CLAUDE.md"
        else
          head -n "$head_lines" "$dst_md" > "$dst_md.tmp"
          cat "$src_md" >> "$dst_md.tmp"
          mv "$dst_md.tmp" "$dst_md"
        fi
      else
        if [ "$DRY_RUN" -eq 1 ]; then
          echo "    [dry-run] would replace CLAUDE.md"
        else
          cp "$src_md" "$dst_md"
        fi
      fi
    else
      echo "  CLAUDE.md: full replace..."
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "    [dry-run] would replace CLAUDE.md"
      else
        cp "$src_md" "$dst_md"
      fi
    fi
  else
    echo "  CLAUDE.md: prepending Claudestrator content..."
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would prepend CLAUDE.md"
    else
      existing="$(cat "$dst_md")"
      new="$(cat "$src_md")"
      printf '%s\n%s' "$new" "$existing" > "$dst_md"
    fi
  fi
else
  echo "  Creating CLAUDE.md..."
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "    [dry-run] would create CLAUDE.md"
  else
    cp "$src_md" "$dst_md"
  fi
fi

# AGENTS.md: copy or replace shared governance
src_agents="$SOURCE/AGENTS.md"
dst_agents="$TARGET/AGENTS.md"

if [[ -f "$src_agents" ]]; then
  if [[ -f "$dst_agents" ]]; then
    if grep -q "^# Shared Governance" "$dst_agents" 2>/dev/null; then
      echo "  AGENTS.md: replacing shared governance..."
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "    [dry-run] would replace AGENTS.md"
      else
        cp "$src_agents" "$dst_agents"
      fi
    else
      echo "  AGENTS.md: prepending shared governance..."
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "    [dry-run] would prepend AGENTS.md"
      else
        existing="$(cat "$dst_agents")"
        new="$(cat "$src_agents")"
        printf '%s\n%s' "$new" "$existing" > "$dst_agents"
      fi
    fi
  else
    echo "  Creating AGENTS.md..."
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would create AGENTS.md"
    else
      cp "$src_agents" "$dst_agents"
    fi
  fi
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo ""
  echo "RESULT: DRY-RUN complete (no files modified)."
  exit 0
fi

# Verification — explicit required-file manifest check

echo ""
echo "=== Verification ==="
errors=0

check_file() {
  local path="$1"
  local label="$2"

  if [[ -f "$path" ]]; then
    echo "  OK  $label"
  else
    echo "  FAIL  $label"
    errors=$((errors+1))
  fi
}

check_installed_manifest() {
  local source_dir="$1"
  while IFS= read -r -d '' source_file; do
    local rel_path="${source_file#$SOURCE/}"
    check_file "$TARGET/$rel_path" "$rel_path"
  done < <(find "$source_dir" -type f -print0)
}

for dir in "${DIRS[@]}"; do
  check_installed_manifest "$SOURCE/$dir"
done

check_file "$TARGET/agents/contracts/operating-model.md" "agents/contracts/operating-model.md"
check_file "$TARGET/agents/contracts/subagent-contracts.md" "agents/contracts/subagent-contracts.md"
check_file "$TARGET/agents/contracts/policies-catalog.md" "agents/contracts/policies-catalog.md"

if [[ -f "$dst_md" ]]; then
  md_content="$(cat "$dst_md")"
  line_count=$(wc -l < "$dst_md")
  echo "  OK  CLAUDE.md ($line_count lines)"
  for section in "## Delegation rule" "## Role index" "## Engineering hygiene" "## Publication safety"; do
    if grep -q "$section" "$dst_md"; then
      echo "  OK  CLAUDE.md has '$section'"
    else
      echo "  FAIL  CLAUDE.md missing '$section'"
      errors=$((errors+1))
    fi
  done
else
  echo "  FAIL  CLAUDE.md missing"
  errors=$((errors+1))
fi

echo ""
if [[ $errors -gt 0 ]]; then
  echo "RESULT: FAIL ($errors errors)"
  exit 1
else
  echo "RESULT: OK — Claudestrator installed to $TARGET"
  echo ""
  echo "Next: restart Claude, then run /agents-init-project to configure project policies."
fi

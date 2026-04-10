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
  bash install-gemini.sh                    Install into current repo (GEMINI.md + AGENTS.md + .gemini/)
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

collect_preserved_gemini_imports() {
  local existing="$1" start_line="$2" end_line="$3"
  awk -v start="$start_line" -v end="$end_line" '
    NR <= start || NR >= end { next }
    {
      if (!collect) {
        if ($0 ~ /^@/ || $0 ~ /^[[:space:]]*$/) {
          collect = 1
        } else {
          exit
        }
      }
      if ($0 ~ /^@/) {
        if ($0 != "@./AGENTS.md" && $0 != "@./AGENTS.shared.md" && !seen[$0]++) {
          print $0
        }
        next
      }
      if ($0 ~ /^[[:space:]]*$/) {
        next
      }
      exit
    }
  ' "$existing"
}

write_merged_gemini_md() {
  local existing="$1" src="$2" output="$3" start_line="$4" end_line="$5"
  local imports_tmp managed_tmp tail_tmp total_lines
  imports_tmp="$(mktemp)"
  managed_tmp="$(mktemp)"
  tail_tmp="$(mktemp)"

  collect_preserved_gemini_imports "$existing" "$start_line" "$end_line" > "$imports_tmp"
  awk -v imports_file="$imports_tmp" '
    BEGIN {
      while ((getline line < imports_file) > 0) {
        imports[++import_count] = line
      }
      close(imports_file)
    }
    {
      if ($0 == "@./AGENTS.shared.md") {
        $0 = "@./AGENTS.md"
      }
      source[++source_count] = $0
    }
    END {
      import_line = 0
      for (i = 1; i <= source_count; i++) {
        if (source[i] ~ /^@/) {
          import_line = i
          break
        }
      }

      if (import_line == 0) {
        for (i = 1; i <= source_count; i++) {
          print source[i]
        }
        exit
      }

      for (i = 1; i < import_line; i++) {
        print source[i]
      }
      print source[import_line]
      for (i = 1; i <= import_count; i++) {
        print imports[i]
      }

      tail_start = import_line + 1
      while (tail_start <= source_count && source[tail_start] ~ /^[[:space:]]*$/) {
        tail_start++
      }

      if (tail_start <= source_count) {
        print ""
        for (i = tail_start; i <= source_count; i++) {
          print source[i]
        }
      }
    }
  ' "$src" > "$managed_tmp"

  : > "$output"
  if (( start_line > 1 )); then
    head -n $((start_line - 1)) "$existing" > "$output"
  fi
  cat "$managed_tmp" >> "$output"

  total_lines=$(wc -l < "$existing")
  if (( end_line < total_lines )); then
    tail -n +$((end_line + 1)) "$existing" > "$tail_tmp"
    if [[ -s "$tail_tmp" ]]; then
      cat "$tail_tmp" >> "$output"
    fi
  fi

  rm -f "$imports_tmp" "$managed_tmp" "$tail_tmp"
}

merge_gemini_file() {
  local src="$1" dst="$2"
  local managed existing start_line end_line
  managed="$(sed 's|@\\./AGENTS\\.shared\\.md|@./AGENTS.md|' "$src")"
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
      start_line=$(grep -nF "$MANAGED_START" "$dst" | head -1 | cut -d: -f1)
      end_line=$(grep -nF "$MANAGED_END" "$dst" | head -1 | cut -d: -f1)
      write_merged_gemini_md "$dst" "$src" "$dst.tmp" "$start_line" "$end_line"
      mv "$dst.tmp" "$dst"
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

install_pack_file() {
  local src="$1" dst="$2" label="$3" preserve_existing="${4:-0}"
  if [[ -e "$dst" ]]; then
    if [[ "$preserve_existing" == "1" ]]; then
      echo "  Preserving existing $label..."
      return
    fi
    echo "  Replacing $label..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would replace $dst"
    else
      cp -f "$src" "$dst"
    fi
    return
  fi

  echo "  Installing $label..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "    [dry-run] would create $dst"
  else
    cp -f "$src" "$dst"
  fi
}

remove_legacy_pack_file() {
  local dst="$1" label="$2"
  if [[ ! -e "$dst" ]]; then
    return
  fi
  echo "  Removing legacy $label..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "    [dry-run] would remove $dst"
  else
    rm -f "$dst"
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

if [[ ! -d "$SOURCE/skills" || ! -d "$SOURCE/agents" || ! -d "$SOURCE/commands" || ! -f "$SOURCE/GEMINI.md" || ! -f "$SOURCE/AGENTS.shared.md" ]]; then
  echo "FAIL: src.gemini is incomplete at $SOURCE" >&2
  exit 1
fi

if [[ "$MODE" == "global" ]]; then
  INSTALL_ROOT="$(canonical_path "$HOME/.gemini")"
  GEMINI_TARGET="$INSTALL_ROOT/GEMINI.md"
  SHARED_TARGET="$INSTALL_ROOT/AGENTS.md"
  LEGACY_SHARED_TARGET="$INSTALL_ROOT/AGENTS.shared.md"
  SKILLS_TARGET="$INSTALL_ROOT/skills"
  AGENTS_TARGET="$INSTALL_ROOT/agents"
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
  SHARED_TARGET="$PROJECT_ROOT/AGENTS.md"
  LEGACY_SHARED_TARGET="$PROJECT_ROOT/AGENTS.shared.md"
  SKILLS_TARGET="$INSTALL_ROOT/skills"
  AGENTS_TARGET="$INSTALL_ROOT/agents"
  COMMANDS_TARGET="$INSTALL_ROOT/commands"
fi

echo "=== Orchestrarium Gemini Installer ==="
echo "Source: $SOURCE"
echo "Mode:   $MODE"
echo "Runtime root: $INSTALL_ROOT"
echo "GEMINI.md:    $GEMINI_TARGET"
echo "AGENTS.md:    $SHARED_TARGET"
echo "Agents:       $AGENTS_TARGET"
[[ "$DRY_RUN" -eq 1 ]] && echo "Mode:   dry-run"
echo

if [[ -e "$GEMINI_TARGET" || -e "$SHARED_TARGET" || -d "$SKILLS_TARGET" || -d "$AGENTS_TARGET" || -d "$COMMANDS_TARGET" ]]; then
  if ! confirm_action "Proceed with reinstall/update of the Gemini pack?"; then
    echo "Install cancelled by user." >&2
    exit 1
  fi
fi

ensure_dir "$INSTALL_ROOT"
install_tree "$SOURCE/skills" "$SKILLS_TARGET" "skills"
install_tree "$SOURCE/agents" "$AGENTS_TARGET" "agents"
install_tree "$SOURCE/commands" "$COMMANDS_TARGET" "commands"
merge_gemini_file "$SOURCE/GEMINI.md" "$GEMINI_TARGET"
if [[ "$MODE" == "global" ]]; then
  install_pack_file "$SOURCE/AGENTS.shared.md" "$SHARED_TARGET" "AGENTS.md"
else
  install_pack_file "$SOURCE/AGENTS.shared.md" "$SHARED_TARGET" "AGENTS.md" 1
fi
remove_legacy_pack_file "$LEGACY_SHARED_TARGET" "AGENTS.shared.md"

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
  "$SHARED_TARGET" \
  "$SKILLS_TARGET/README.md" \
  "$SKILLS_TARGET/lead/SKILL.md" \
  "$SKILLS_TARGET/init-project/SKILL.md" \
  "$AGENTS_TARGET/README.md" \
  "$AGENTS_TARGET/lead.md" \
  "$AGENTS_TARGET/team-templates/full-delivery.json" \
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

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$REPO_DIR/src.qwen"
EXTENSION_SOURCE="$SOURCE/extension"
EXTENSION_MANIFEST_SOURCE="$EXTENSION_SOURCE/qwen-extension.json"
EXTENSION_README_SOURCE="$EXTENSION_SOURCE/README.md"
DEFAULT_AGENTS_MODE_SOURCE="$REPO_DIR/shared/agents-mode.defaults.yaml"
MANAGED_START='<!-- ORCHESTRARIUM_QWEN_PACK:START -->'
MANAGED_END='<!-- ORCHESTRARIUM_QWEN_PACK:END -->'
FORCE=0
DRY_RUN=0
ALLOW_UNSAFE_TARGET=0
MODE="repo"
TARGET=""

usage() {
  cat <<'EOF'
Usage:
  bash scripts/install-qwen.sh                    Install the Qwen example pack into current repo (QWEN.md + AGENTS.md + .qwen/)
  bash scripts/install-qwen.sh --global           Install the Qwen example pack into ~/.qwen/
  bash scripts/install-qwen.sh --target DIR       Install the Qwen example pack into DIR as a project root
  bash scripts/install-qwen.sh --force            Skip confirmation prompts
  bash scripts/install-qwen.sh --dry-run          Print planned actions without changing files
  bash scripts/install-qwen.sh --allow-unsafe-target
                                           Allow a custom project root outside the current repo
EOF
  exit 1
}

canonical_path() {
  local path="$1"
  case "$path" in
    "~")
      path="$HOME"
      ;;
    "~/"*|"~\\"*)
      path="$HOME/${path#??}"
      ;;
  esac
  path="${path//\\//}"
  case "$path" in
    [A-Za-z]:/*)
      if command -v wslpath >/dev/null 2>&1; then
        path="$(wslpath -u "$path")"
      elif command -v cygpath >/dev/null 2>&1; then
        path="$(cygpath -u "$path")"
      else
        local drive rest
        drive="$(printf '%s' "${path:0:1}" | tr '[:upper:]' '[:lower:]')"
        rest="${path:3}"
        if [[ -d "/mnt/$drive" ]]; then
          path="/mnt/$drive/$rest"
        else
          path="/$drive/$rest"
        fi
      fi
      ;;
    [A-Za-z]:*)
      echo "FAIL: Windows drive-relative path '$path' is ambiguous; use C:/path or quote '~' so Bash expands it." >&2
      return 1
      ;;
  esac
  if [[ -z "$path" ]]; then
    echo "" >&2
    return 1
  fi

  if command -v realpath >/dev/null 2>&1; then
    realpath -m "$path"
    return
  fi

  if [[ -e "$path" || -L "$path" ]]; then
    if [[ -d "$path" ]]; then
      (cd "$path" && pwd -P)
    else
      local dir base
      dir="$(dirname "$path")"
      base="$(basename "$path")"
      printf "%s/%s\n" "$(cd "$dir" && pwd -P)" "$base"
    fi
  elif [[ "$path" = /* ]]; then
    printf "%s\n" "$path"
  else
    printf "%s/%s\n" "$(pwd -P)" "$path"
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
  if [[ "$(basename "$resolved")" == ".qwen" ]]; then
    dirname "$resolved"
  else
    printf "%s" "$resolved"
  fi
}

extension_name_from_manifest() {
  local manifest="$1"
  local name
  name="$(sed -nE 's/^[[:space:]]*"name"[[:space:]]*:[[:space:]]*"([^"]+)".*$/\1/p' "$manifest" | head -n 1)"
  if [[ -z "$name" ]]; then
    echo "FAIL: Qwen extension manifest is missing a non-empty 'name' field." >&2
    return 1
  fi
  printf "%s\n" "$name"
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

resolve_python_command() {
  if command -v python >/dev/null 2>&1; then
    printf '%s' "python"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "python3"
    return 0
  fi
  return 1
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

items_equal() {
  local src="$1" dst="$2"
  if [[ -d "$src" && -d "$dst" ]]; then
    diff -qr "$src" "$dst" >/dev/null
  elif [[ -f "$src" && -f "$dst" ]]; then
    cmp -s "$src" "$dst"
  else
    return 1
  fi
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
      elif items_equal "$item" "$dst/$item_name"; then
        echo "    OK  $label/$item_name unchanged"
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

ensure_local_only_gitignore_entries() {
  local project_root="$1"
  local gitignore="$project_root/.gitignore"
  local entries=("/.reports/" "/work-items/")
  local missing=()

  for entry in "${entries[@]}"; do
    local alternate="${entry#/}"
    if [[ -f "$gitignore" ]] && { grep -Fxq "$entry" "$gitignore" || grep -Fxq "$alternate" "$gitignore"; }; then
      continue
    fi
    missing+=("$entry")
  done

  if [[ ${#missing[@]} -eq 0 ]]; then
    echo "  .gitignore: local-only entries already present"
    return
  fi

  echo "  Ensuring .gitignore ignores local-only task-memory paths..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    for entry in "${missing[@]}"; do
      if [[ -f "$gitignore" ]]; then
        echo "    [dry-run] would append '$entry' to $gitignore"
      else
        echo "    [dry-run] would create $gitignore with '$entry'"
      fi
    done
    return
  fi

  if [[ ! -f "$gitignore" ]]; then
    printf '%s\n' "${missing[@]}" > "$gitignore"
  else
    for entry in "${missing[@]}"; do
      printf '\n%s\n' "$entry" >> "$gitignore"
    done
  fi
}

collect_preserved_qwen_imports() {
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

write_merged_qwen_md() {
  local existing="$1" src="$2" output="$3" start_line="$4" end_line="$5"
  local imports_tmp managed_tmp tail_tmp total_lines
  imports_tmp="$(mktemp)"
  managed_tmp="$(mktemp)"
  tail_tmp="$(mktemp)"

  collect_preserved_qwen_imports "$existing" "$start_line" "$end_line" > "$imports_tmp"
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

merge_qwen_file() {
  local src="$1" dst="$2"
  local managed existing start_line end_line
  managed="$(sed 's|^@\./AGENTS\.shared\.md$|@./AGENTS.md|' "$src")"
  if [[ ! -f "$dst" ]]; then
    echo "  Creating QWEN.md..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would create $dst"
    else
      printf '%s' "$managed" > "$dst"
    fi
    return
  fi

  existing="$(cat "$dst")"
  if grep -qF "$MANAGED_START" "$dst" && grep -qF "$MANAGED_END" "$dst"; then
    echo "  QWEN.md: replacing managed Orchestrarium block..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would replace managed QWEN.md block"
    else
      start_line=$(grep -nF "$MANAGED_START" "$dst" | head -1 | cut -d: -f1)
      end_line=$(grep -nF "$MANAGED_END" "$dst" | head -1 | cut -d: -f1)
      write_merged_qwen_md "$dst" "$src" "$dst.tmp" "$start_line" "$end_line"
      mv "$dst.tmp" "$dst"
    fi
  else
    echo "  QWEN.md: prepending managed Orchestrarium block..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would prepend managed QWEN.md block"
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

sync_agents_mode_file() {
  local template="$1" dst="$2" label="$3"
  local normalizer="$REPO_DIR/scripts/normalize-agents-mode.py"
  local python_cmd=""

  python_cmd="$(resolve_python_command || true)"

  if [[ -n "$python_cmd" && -f "$normalizer" ]]; then
    if [[ -f "$dst" ]]; then
      echo "  Normalizing existing $label to current canonical format..."
    else
      echo "  Installing canonical $label..."
    fi

    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would normalize $dst"
    else
      "$python_cmd" "$normalizer" --template "$template" --target "$dst" --provider shared
    fi
    return
  fi

  if [[ -f "$dst" ]]; then
    echo "FAIL: python or python3 is required to normalize existing $label at $dst" >&2
    exit 1
  fi

  echo "  Installing canonical $label..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "    [dry-run] would create $dst"
  else
    cp -f "$template" "$dst"
  fi
}

migrate_legacy_agents_mode_file() {
  local legacy="$1" dst="$2" label="$3"

  if [[ -f "$dst" ]]; then
    if [[ -f "$legacy" ]]; then
      echo "  Canonical $label already exists; leaving legacy file untouched: $legacy"
    fi
    return
  fi

  if [[ ! -f "$legacy" ]]; then
    return
  fi

  echo "  Migrating legacy $label to $dst..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "    [dry-run] would move $legacy -> $dst"
  else
    mv "$legacy" "$dst"
  fi
}

install_pack_content_file() {
  local src="$1" dst="$2" label="$3"
  ensure_dir "$(dirname "$dst")"
  if [[ -e "$dst" ]]; then
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

remove_empty_dir_if_present() {
  local dst="$1"
  if [[ ! -d "$dst" ]]; then
    return
  fi
  shopt -s nullglob dotglob
  local items=("$dst"/*)
  shopt -u nullglob dotglob
  if (( ${#items[@]} > 0 )); then
    return
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "    [dry-run] would remove empty directory $dst"
  else
    rmdir "$dst"
  fi
}

remove_legacy_top_level_pack_entries() {
  local src="$1" dst="$2" label="$3"
  [[ -d "$dst" ]] || return 0
  shopt -s nullglob
  for item in "$src"/*; do
    local item_name target_path
    item_name="$(basename "$item")"
    target_path="$dst/$item_name"
    [[ -e "$target_path" ]] || continue
    echo "  Removing legacy $label/$item_name..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would remove $target_path"
    else
      rm -rf "$target_path"
    fi
  done
  shopt -u nullglob
  remove_empty_dir_if_present "$dst"
}

remove_legacy_mirrored_files() {
  local src="$1" dst="$2" label="$3"
  [[ -d "$dst" ]] || return 0
  while IFS= read -r -d '' file; do
    local relative target_path
    relative="${file#$src/}"
    target_path="$dst/$relative"
    [[ -f "$target_path" ]] || continue
    echo "  Removing legacy $label/$relative..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would remove $target_path"
    else
      rm -f "$target_path"
    fi
  done < <(find "$src" -type f -print0)

  while IFS= read -r -d '' dir; do
    remove_empty_dir_if_present "$dir"
  done < <(find "$dst" -depth -type d -print0)
  remove_empty_dir_if_present "$dst"
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

if [[ ! -d "$SOURCE/skills" || ! -d "$SOURCE/agents" || ! -d "$SOURCE/commands" || ! -f "$SOURCE/QWEN.md" || ! -f "$SOURCE/AGENTS.shared.md" ]]; then
  echo "FAIL: src.qwen is incomplete at $SOURCE" >&2
  exit 1
fi
if [[ ! -f "$EXTENSION_MANIFEST_SOURCE" || ! -f "$EXTENSION_README_SOURCE" ]]; then
  echo "FAIL: src.qwen/extension is incomplete at $EXTENSION_SOURCE" >&2
  exit 1
fi
if [[ ! -f "$DEFAULT_AGENTS_MODE_SOURCE" ]]; then
  echo "FAIL: missing default agents-mode template at $DEFAULT_AGENTS_MODE_SOURCE" >&2
  exit 1
fi

EXTENSION_NAME="$(extension_name_from_manifest "$EXTENSION_MANIFEST_SOURCE")"

if [[ "$MODE" == "global" ]]; then
  INSTALL_ROOT="$(canonical_path "$HOME/.qwen")"
  EXTENSIONS_TARGET="$INSTALL_ROOT/extensions"
  EXTENSION_ROOT="$EXTENSIONS_TARGET/$EXTENSION_NAME"
  AGENTS_MODE_TARGET="$INSTALL_ROOT/.agents-mode.yaml"
  LEGACY_AGENTS_MODE_TARGET="$INSTALL_ROOT/.agents-mode"
  QWEN_TARGET="$INSTALL_ROOT/QWEN.md"
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
  INSTALL_ROOT="$PROJECT_ROOT/.qwen"
  EXTENSIONS_TARGET="$INSTALL_ROOT/extensions"
  EXTENSION_ROOT="$EXTENSIONS_TARGET/$EXTENSION_NAME"
  AGENTS_MODE_TARGET="$INSTALL_ROOT/.agents-mode.yaml"
  LEGACY_AGENTS_MODE_TARGET="$INSTALL_ROOT/.agents-mode"
  QWEN_TARGET="$PROJECT_ROOT/QWEN.md"
  SHARED_TARGET="$PROJECT_ROOT/AGENTS.md"
  LEGACY_SHARED_TARGET="$PROJECT_ROOT/AGENTS.shared.md"
  SKILLS_TARGET="$INSTALL_ROOT/skills"
  AGENTS_TARGET="$INSTALL_ROOT/agents"
  COMMANDS_TARGET="$INSTALL_ROOT/commands"
fi
LEGACY_AGENTS_README_TARGET="$AGENTS_TARGET/README.md"
EXTENSION_MANIFEST_TARGET="$EXTENSION_ROOT/qwen-extension.json"
EXTENSION_README_TARGET="$EXTENSION_ROOT/README.md"
EXTENSION_QWEN_TARGET="$EXTENSION_ROOT/QWEN.md"
EXTENSION_AGENTS_TARGET="$EXTENSION_ROOT/AGENTS.md"
LEGACY_EXTENSION_SHARED_TARGET="$EXTENSION_ROOT/AGENTS.shared.md"
LEGACY_EXTENSION_AGENTS_README_TARGET="$EXTENSION_ROOT/agents/README.md"

echo "=== Orchestrarium Qwen Example Pack Installer ==="
echo "Source: $SOURCE"
echo "Mode:   $MODE"
echo "Runtime root: $INSTALL_ROOT"
echo "QWEN.md:    $QWEN_TARGET"
echo "AGENTS.md:    $SHARED_TARGET"
echo "agents-mode:  $AGENTS_MODE_TARGET"
echo "Extension:    $EXTENSION_ROOT"
echo "Legacy user tier cleanup roots: $SKILLS_TARGET ; $AGENTS_TARGET ; $COMMANDS_TARGET"
echo "Policy:       example-only / WEAK MODEL / NOT RECOMMENDED; production auto routing stays on codex|claude"
[[ "$DRY_RUN" -eq 1 ]] && echo "Mode:   dry-run"
echo

if [[ -e "$QWEN_TARGET" || -e "$SHARED_TARGET" || -d "$SKILLS_TARGET" || -d "$AGENTS_TARGET" || -d "$COMMANDS_TARGET" || -d "$EXTENSION_ROOT" ]]; then
  if ! confirm_action "Proceed with reinstall/update of the Qwen pack?"; then
    echo "Install cancelled by user." >&2
    exit 1
  fi
fi

ensure_dir "$INSTALL_ROOT"
install_tree "$SOURCE/skills" "$EXTENSION_ROOT/skills" "extension/skills"
install_tree "$SOURCE/agents" "$EXTENSION_ROOT/agents" "extension/agents"
install_tree "$SOURCE/commands" "$EXTENSION_ROOT/commands" "extension/commands"
merge_qwen_file "$SOURCE/QWEN.md" "$QWEN_TARGET"
if [[ "$MODE" == "global" ]]; then
  install_pack_file "$SOURCE/AGENTS.shared.md" "$SHARED_TARGET" "AGENTS.md"
else
  install_pack_file "$SOURCE/AGENTS.shared.md" "$SHARED_TARGET" "AGENTS.md" 1
  ensure_local_only_gitignore_entries "$PROJECT_ROOT"
fi
install_pack_file "$EXTENSION_MANIFEST_SOURCE" "$EXTENSION_MANIFEST_TARGET" "extension manifest"
install_pack_file "$EXTENSION_README_SOURCE" "$EXTENSION_README_TARGET" "extension README"
extension_qwen_tmp="$(mktemp)"
trap 'rm -f "$extension_qwen_tmp"' EXIT
sed 's|@\./AGENTS\.shared\.md|@./AGENTS.md|' "$SOURCE/QWEN.md" > "$extension_qwen_tmp"
install_pack_content_file "$extension_qwen_tmp" "$EXTENSION_QWEN_TARGET" "extension QWEN.md"
install_pack_file "$SOURCE/AGENTS.shared.md" "$EXTENSION_AGENTS_TARGET" "extension AGENTS.md"
migrate_legacy_agents_mode_file "$LEGACY_AGENTS_MODE_TARGET" "$AGENTS_MODE_TARGET" ".agents-mode.yaml"
sync_agents_mode_file "$DEFAULT_AGENTS_MODE_SOURCE" "$AGENTS_MODE_TARGET" ".agents-mode.yaml"
remove_legacy_pack_file "$LEGACY_SHARED_TARGET" "AGENTS.shared.md"
remove_legacy_pack_file "$LEGACY_AGENTS_README_TARGET" "agents/README.md"
remove_legacy_pack_file "$LEGACY_EXTENSION_SHARED_TARGET" "extension AGENTS.shared.md"
remove_legacy_pack_file "$LEGACY_EXTENSION_AGENTS_README_TARGET" "extension agents/README.md"
remove_legacy_top_level_pack_entries "$SOURCE/skills" "$SKILLS_TARGET" "skills"
remove_legacy_mirrored_files "$SOURCE/agents" "$AGENTS_TARGET" "agents"
remove_legacy_mirrored_files "$SOURCE/commands" "$COMMANDS_TARGET" "commands"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo
  echo "RESULT: DRY-RUN complete (no files modified)."
  exit 0
fi

echo
echo "=== Verification ==="
errors=0
for path in \
  "$QWEN_TARGET" \
  "$SHARED_TARGET" \
  "$AGENTS_MODE_TARGET" \
  "$EXTENSION_MANIFEST_TARGET" \
  "$EXTENSION_QWEN_TARGET" \
  "$EXTENSION_AGENTS_TARGET" \
  "$EXTENSION_ROOT/skills/lead/SKILL.md" \
  "$EXTENSION_ROOT/skills/init-project/SKILL.md" \
  "$EXTENSION_ROOT/agents/lead.md" \
  "$EXTENSION_ROOT/agents/team-templates/full-delivery.json" \
  "$EXTENSION_ROOT/commands/agents/help.md"; do
  if [[ -e "$path" ]]; then
    echo "  OK  $path"
  else
    echo "  FAIL  $path"
    errors=$((errors+1))
  fi
done

for legacy_path in \
  "$SKILLS_TARGET/lead/SKILL.md" \
  "$AGENTS_TARGET/lead.md" \
  "$AGENTS_TARGET/team-templates/full-delivery.json" \
  "$COMMANDS_TARGET/agents/help.md" \
  "$COMMANDS_TARGET/agents/external-brigade.md" \
  "$COMMANDS_TARGET/agents/init-project.md"; do
  if [[ -e "$legacy_path" ]]; then
    echo "  FAIL  legacy duplicate still present: $legacy_path"
    errors=$((errors+1))
  else
    echo "  OK  no legacy duplicate at $legacy_path"
  fi
done

if [[ "$errors" -gt 0 ]]; then
  echo
  echo "RESULT: FAIL ($errors errors)"
  exit 1
fi

echo
echo "RESULT: OK - Qwen example pack installed"

#!/usr/bin/env bash
# Install Codex pack.
# Usage:
#   bash scripts/install-codex.sh                  install into current repo (.agents/ + AGENTS.md)
#   bash scripts/install-codex.sh --global         install into ~/.codex/
#   bash scripts/install-codex.sh --target DIR     install into DIR as a project (.agents/ + AGENTS.md)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$REPO_DIR/src.codex"
SHARED_AGENTS_MODE_SOURCE="$REPO_DIR/shared/agents-mode.defaults.yaml"
CODEX_PACK_BEGIN_MARKER='<!-- BEGIN ORCHESTRARIUM CODEX PACK -->'
CODEX_PACK_END_MARKER='<!-- END ORCHESTRARIUM CODEX PACK -->'

# Directories to install (order doesn't matter)
DIRS=(skills)
OPTIONAL_DIRS=()
FORCE=0
DRY_RUN=0
ALLOW_UNSAFE_TARGET=0
MODE=""
TARGET=""

usage() {
  echo "Usage:"
  echo "  bash scripts/install-codex.sh                          Install into current repo (.agents/ + AGENTS.md)"
  echo "  bash scripts/install-codex.sh --global                 Install into ~/.codex/"
  echo "  bash scripts/install-codex.sh --target DIR             Install into DIR as a project (.agents/ + AGENTS.md)"
  echo "  bash scripts/install-codex.sh --force                  Skip deletion prompts"
  echo "  bash scripts/install-codex.sh --dry-run                Print planned actions without changing files"
  echo "  bash scripts/install-codex.sh --allow-unsafe-target    Override allowlist for custom target path"
  echo "  bash scripts/install-codex.sh --help                   Show help"
  exit 1
}

canonical_path() {
  local input_path="$1"
  local expanded="${input_path/#\~/$HOME}"
  local converter=""

  if [ -z "$expanded" ]; then
    echo ""
    return 1
  fi

  if [[ "$expanded" =~ ^[A-Za-z]:[\\/].* ]]; then
    if command -v cygpath >/dev/null 2>&1; then
      converter="cygpath"
    elif command -v wslpath >/dev/null 2>&1; then
      converter="wslpath"
    fi

    if [ -n "$converter" ]; then
      expanded="$("$converter" -u "$expanded")"
    else
      expanded="${expanded//\\//}"
    fi
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

default_agents_mode_template() {
  if [[ ! -f "$SHARED_AGENTS_MODE_SOURCE" ]]; then
    echo "FAIL: missing shared agents-mode template at $SHARED_AGENTS_MODE_SOURCE" >&2
    return 1
  fi

  local tmp
  tmp="$(mktemp)"
  cat "$SHARED_AGENTS_MODE_SOURCE" > "$tmp"
  if ! grep -q '^externalClaudeProfile:' "$tmp"; then
    printf '\nexternalClaudeProfile: sonnet-high  # allowed: sonnet-high | opus-max\n' >> "$tmp"
  fi
  printf '%s' "$tmp"
}

resolve_install_target() {
  local input_path="$1"
  local normalized

  normalized="$(canonical_path "$input_path")"
  if [ -z "$normalized" ]; then
    echo "FAIL: unable to resolve target path '$input_path'" >&2
    return 1
  fi

  if [ "$(basename "$normalized")" = ".codex" ]; then
    printf "%s" "$normalized"
  else
    printf "%s/.codex" "$normalized"
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

  if [ "$(basename "$target_lower")" != ".codex" ]; then
    echo "FAIL: target '$target' must resolve to .codex directory" >&2
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

  if [ -n "${CODEX_INSTALL_ALLOWLIST:-}" ]; then
    IFS=',' read -r -a ALLOWLIST_EXTRA <<< "$CODEX_INSTALL_ALLOWLIST"
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

# Per-skill install preserves user-added skills — no destructive directory wipe needed.

prompt_install_mode() {
  if [ ! -t 0 ]; then
    echo "FAIL: No install target specified and not running interactively." >&2
    echo "Use: bash scripts/install-codex.sh --global  or  bash scripts/install-codex.sh --target <path>" >&2
    exit 1
  fi

  while true; do
    echo "Select installation target:"
    echo "  1) Local repo (.agents/skills + root AGENTS.md)"
    echo "  2) Global (~/.codex/)"
    echo "  3) Custom project directory (.agents/skills + root AGENTS.md)"
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
        TARGET="$HOME/.codex"
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
      TARGET="$HOME/.codex"
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
        TARGET="$(git rev-parse --show-toplevel)/.codex"
      else
        TARGET="$(pwd)/.codex"
      fi
    elif [ "$MODE" = "global" ]; then
      TARGET="$HOME/.codex"
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

# Derive per-mode target paths.
# Global: everything goes into ~/.codex/ (mirrors src.codex/).
# Repo/target: skills go into .agents/skills/,
#              AGENTS.md merges into project root AGENTS.md.
if [ "$MODE" = "global" ]; then
  AGENTS_ROOT="$TARGET"
  SKILLS_TARGET="$TARGET/skills"
  MD_TARGET="$TARGET/AGENTS.md"
else
  # Repo-level: TARGET is <root>/.codex but skills go into <root>/.agents/
  PROJECT_ROOT="$(dirname "$TARGET")"
  AGENTS_ROOT="$PROJECT_ROOT/.agents"
  SKILLS_TARGET="$AGENTS_ROOT/skills"
  MD_TARGET="$PROJECT_ROOT/AGENTS.md"
fi
AGENTS_MODE_TARGET="$AGENTS_ROOT/.agents-mode"

echo "=== Codex Installer ==="
echo "Source: $SOURCE"
echo "Skills target: $SKILLS_TARGET"
echo "AGENTS.md target: $MD_TARGET"
echo "agents-mode: $AGENTS_MODE_TARGET"
echo "Mode:   $MODE"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "Mode:   dry-run"
fi
echo

# Verify source
if [[ ! -d "$SOURCE/skills" ]]; then
  echo "FAIL: Source directory $SOURCE/skills not found."
  echo "Run this script from the Orchestrarium repo root."
  exit 1
fi
DEFAULT_AGENTS_MODE_SOURCE="$(default_agents_mode_template)"
trap '[[ -n "${DEFAULT_AGENTS_MODE_SOURCE:-}" && -f "${DEFAULT_AGENTS_MODE_SOURCE:-}" ]] && rm -f "${DEFAULT_AGENTS_MODE_SOURCE:-}"' EXIT

# Create target parent directories as needed
for tdir in "$SKILLS_TARGET"; do
  parent="$(dirname "$tdir")"
  if [[ ! -d "$parent" ]]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "[dry-run] would create: $parent"
    else
      mkdir -p "$parent"
    fi
  fi
done

# Per-skill install: only replace pack skills, preserve user-added skills
install_skill() {
  local src="$1" dst="$2" label="$3"
  if [[ -d "$dst" ]]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would replace $label"
    else
      rm -rf "$dst"
      cp -r "$src" "$dst"
    fi
  else
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would install $label"
    else
      cp -r "$src" "$dst"
    fi
  fi
}

ensure_reports_gitignore() {
  local project_root="$1"
  local gitignore="$project_root/.gitignore"

  if [[ -f "$gitignore" ]]; then
    if grep -Fxq "/.reports/" "$gitignore" || grep -Fxq ".reports/" "$gitignore"; then
      echo "  .gitignore: /.reports/ already present"
      return
    fi
  fi

  echo "  Ensuring .gitignore ignores /.reports/..."
  if [ "$DRY_RUN" -eq 1 ]; then
    if [[ -f "$gitignore" ]]; then
      echo "    [dry-run] would append '/.reports/' to $gitignore"
    else
      echo "    [dry-run] would create $gitignore with '/.reports/'"
    fi
    return
  fi

  if [[ -f "$gitignore" ]] && [[ -s "$gitignore" ]]; then
    printf '\n/.reports/\n' >> "$gitignore"
  else
    printf '/.reports/\n' > "$gitignore"
  fi
}

remove_dangling_symlink() {
  local path="$1"
  local label="$2"

  if [[ -L "$path" && ! -e "$path" ]]; then
    echo "  Removing dangling symlink for $label..."
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would remove dangling symlink $path"
    else
      rm -f "$path"
    fi
  fi
}

ensure_default_file() {
  local src="$1" dst="$2" label="$3"

  remove_dangling_symlink "$dst" "$label"

  if [[ -f "$dst" ]]; then
    echo "  Preserving existing $label..."
    return
  fi

  echo "  Installing default $label..."
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "    [dry-run] would create $dst"
  else
    cp "$src" "$dst"
  fi
}

find_codex_pack_start_line() {
  local file="$1"
  local marker_line
  marker_line="$(grep -n "^$CODEX_PACK_BEGIN_MARKER$" "$file" 2>/dev/null | head -1 | cut -d: -f1 || true)"
  if [[ -n "$marker_line" ]]; then
    printf "%s" "$marker_line"
    return
  fi
  grep -n "^# Shared Governance$\|^# Codex Platform Rules$\|^# Default Delegation Rule$" "$file" 2>/dev/null | head -1 | cut -d: -f1
}

find_codex_pack_end_line() {
  local existing="$1"
  local src="$2"
  local pack_start="$3"
  local footer

  if awk -v start="$pack_start" -v marker="$CODEX_PACK_END_MARKER" '
    NR < start { next }
    $0 == marker { print NR; found=1; exit }
    END { exit(found ? 0 : 1) }
  ' "$existing"; then
    return
  fi

  if awk -v start="$pack_start" '
    NR <= start { next }
    $0 == "## Project policies" { print NR - 1; found=1; exit }
    END { exit(found ? 0 : 1) }
  ' "$existing"; then
    return
  fi

  footer="$(awk 'NF { line=$0 } END { print line }' "$src")"

  if [[ -n "$footer" ]]; then
    awk -v start="$pack_start" -v footer="$footer" '
      NR < start { next }
      $0 == footer { print NR; exit }
    ' "$existing"
  fi
}

write_merged_codex_agents_md() {
  local existing="$1"
  local src="$2"
  local output="$3"
  local pack_start="$4"
  local total_lines head_lines tail_start pack_end new_lines footer_end

  total_lines=$(wc -l < "$existing")
  new_lines=$(wc -l < "$src")
  footer_end="$(find_codex_pack_end_line "$existing" "$src" "$pack_start")"

  if [[ -n "$footer_end" ]]; then
    pack_end="$footer_end"
  else
    pack_end=$((pack_start + new_lines - 1))
    if [[ "$pack_end" -gt "$total_lines" ]]; then
      pack_end="$total_lines"
    fi
  fi

  head_lines=$((pack_start - 1))
  tail_start=$((pack_end + 1))

  {
    if [[ "$head_lines" -gt 0 ]]; then
      head -n "$head_lines" "$existing"
    fi
    cat "$src"
    if [[ "$tail_start" -le "$total_lines" ]]; then
      tail -n "+$tail_start" "$existing"
    fi
  } > "$output"
}

echo "  Installing skills (per-skill, preserving user-added skills)..."
if [[ ! -d "$SKILLS_TARGET" ]]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "    [dry-run] would create $SKILLS_TARGET"
  else
    mkdir -p "$SKILLS_TARGET"
  fi
fi

# Count what will be replaced and confirm
pack_skills=()
for skill_dir in "$SOURCE/skills"/*/; do
  [[ -d "$skill_dir" ]] || continue
  pack_skills+=("$(basename "$skill_dir")")
done

existing_count=0
if [[ -d "$SKILLS_TARGET" ]]; then
  for d in "$SKILLS_TARGET"/*/; do
    [[ -d "$d" ]] || continue
    existing_count=$((existing_count + 1))
  done
fi

if [ "$existing_count" -gt 0 ] && [ "$FORCE" -ne 1 ] && [ "$DRY_RUN" -ne 1 ] && [ -t 0 ]; then
  user_count=$((existing_count - ${#pack_skills[@]}))
  if [ "$user_count" -lt 0 ]; then user_count=0; fi
  echo ""
  echo "  Reinstall will replace ${#pack_skills[@]} pack skills. $user_count user skill(s) will be preserved."
  while true; do
    read -r -p "  Proceed? [y/N] " answer
    case "${answer,,}" in
      y|yes) break ;;
      n|no|"") echo "Install cancelled by user." >&2; exit 1 ;;
      *) echo "  Please answer y or n." ;;
    esac
  done
fi

pack_skills=()
for skill_dir in "$SOURCE/skills"/*/; do
  [[ -d "$skill_dir" ]] || continue
  skill_name="$(basename "$skill_dir")"
  pack_skills+=("$skill_name")
  install_skill "$skill_dir" "$SKILLS_TARGET/$skill_name" "skills/$skill_name"
done
echo "  Installed ${#pack_skills[@]} pack skills."

# Report user-added skills that were preserved
if [[ -d "$SKILLS_TARGET" ]]; then
  for existing_dir in "$SKILLS_TARGET"/*/; do
    [[ -d "$existing_dir" ]] || continue
    existing_name="$(basename "$existing_dir")"
    is_pack=0
    for ps in "${pack_skills[@]}"; do
      if [[ "$ps" == "$existing_name" ]]; then is_pack=1; break; fi
    done
    if [[ $is_pack -eq 0 ]]; then
      echo "  Preserved user skill: $existing_name"
    fi
  done
fi

# Scripts live inside skills/lead/scripts/ — installed automatically with the lead skill.

# AGENTS.md: assemble from shared + codex-specific, then merge or create
src_shared="$REPO_DIR/shared/AGENTS.shared.md"
src_platform="$SOURCE/AGENTS.codex.md"

if [[ ! -f "$src_shared" ]] || [[ ! -f "$src_platform" ]]; then
  echo "FAIL: Missing $src_shared or $src_platform"
  exit 1
fi

# Assemble pack AGENTS.md from two source files
src_md="$(mktemp)"
{
  printf '%s\n' "$CODEX_PACK_BEGIN_MARKER"
  cat "$src_shared"
  printf '\n'
  cat "$src_platform"
  printf '\n%s\n' "$CODEX_PACK_END_MARKER"
} > "$src_md"
trap "rm -f '$src_md'" EXIT

dst_md="$MD_TARGET"

remove_dangling_symlink "$dst_md" "AGENTS.md"

if [[ -f "$dst_md" ]]; then
  if grep -q "## Template routing" "$dst_md" 2>/dev/null; then
    pack_start="$(find_codex_pack_start_line "$dst_md")"
    if [[ -n "$pack_start" ]]; then
      echo "  AGENTS.md: replacing Codex pack section..."
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "    [dry-run] would replace Codex pack section in AGENTS.md"
      else
        write_merged_codex_agents_md "$dst_md" "$src_md" "$dst_md.tmp" "$pack_start"
        mv "$dst_md.tmp" "$dst_md"
      fi
    else
      echo "  AGENTS.md: full replace..."
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "    [dry-run] would replace AGENTS.md"
      else
        cp "$src_md" "$dst_md"
      fi
    fi
  else
    echo "  AGENTS.md: prepending Codex pack content..."
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would prepend AGENTS.md"
    else
      existing="$(cat "$dst_md")"
      new="$(cat "$src_md")"
      printf '%s\n%s' "$new" "$existing" > "$dst_md"
    fi
  fi
else
  echo "  Creating AGENTS.md..."
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "    [dry-run] would create AGENTS.md"
  else
    cp "$src_md" "$dst_md"
  fi
fi

if [ "$MODE" != "global" ]; then
  ensure_reports_gitignore "$PROJECT_ROOT"
fi

ensure_default_file "$DEFAULT_AGENTS_MODE_SOURCE" "$AGENTS_MODE_TARGET" ".agents-mode"

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
  local target_base="$2"
  local source_base="$3"
  while IFS= read -r -d '' source_file; do
    local rel_path="${source_file#$source_base/}"
    check_file "$target_base/$rel_path" "$rel_path"
  done < <(find "$source_dir" -type f -print0)
}

check_installed_manifest "$SOURCE/skills" "$SKILLS_TARGET" "$SOURCE/skills"

check_file "$SKILLS_TARGET/lead/operating-model.md" "skills/lead/operating-model.md"
check_file "$SKILLS_TARGET/lead/subagent-contracts.md" "skills/lead/subagent-contracts.md"
check_file "$SKILLS_TARGET/lead/scripts/check-publication-safety.sh" "skills/lead/scripts/check-publication-safety.sh"
check_file "$SKILLS_TARGET/lead/scripts/check-publication-safety.ps1" "skills/lead/scripts/check-publication-safety.ps1"
check_file "$SKILLS_TARGET/lead/scripts/validate-skill-pack.sh" "skills/lead/scripts/validate-skill-pack.sh"
check_file "$AGENTS_MODE_TARGET" ".agents-mode"

if [[ -f "$dst_md" ]]; then
  line_count=$(wc -l < "$dst_md")
  echo "  OK  AGENTS.md ($line_count lines)"
  for section in "## Template routing" "## Role index" "## Engineering hygiene" "## Publication safety"; do
    if grep -q "$section" "$dst_md"; then
      echo "  OK  AGENTS.md has '$section'"
    else
      echo "  FAIL  AGENTS.md missing '$section'"
      errors=$((errors+1))
    fi
  done
else
  echo "  FAIL  AGENTS.md missing"
  errors=$((errors+1))
fi

echo ""
if [[ $errors -gt 0 ]]; then
  echo "RESULT: FAIL ($errors errors)"
  exit 1
else
  echo "RESULT: OK — Codex pack installed"
  echo "  Skills: $SKILLS_TARGET"
  echo "  AGENTS.md: $MD_TARGET"
  echo "  agents-mode: $AGENTS_MODE_TARGET"
  echo ""
  echo "Next: open Codex in the target project and run '\$init-project' to review/update project policies and the installed default .agents/.agents-mode."
  echo "Then run 'bash $SKILLS_TARGET/lead/scripts/validate-skill-pack.sh' if you are validating the installation from a maintainer shell."
fi

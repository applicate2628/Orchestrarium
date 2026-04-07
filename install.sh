#!/usr/bin/env bash
# Install Claudestrator skill-pack.
# Usage:
#   bash install.sh              — install into current repo's .claude/
#   bash install.sh --global     — install into ~/.claude/
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$SCRIPT_DIR/.claude"

# Directories to install (order doesn't matter)
DIRS=(agents commands policies scripts)
OPTIONAL_DIRS=(memory)

usage() {
  echo "Usage:"
  echo "  bash install.sh              Install into current repo (.claude/)"
  echo "  bash install.sh --global     Install into ~/.claude/"
  echo "  bash install.sh --target DIR Install into DIR/.claude/"
  exit 1
}

# Parse args
TARGET=""
MODE="repo"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --global) MODE="global"; TARGET="$HOME/.claude"; shift ;;
    --target) MODE="target"; TARGET="$2/.claude"; shift 2 ;;
    -h|--help) usage ;;
    *) echo "Unknown option: $1"; usage ;;
  esac
done

if [[ "$MODE" == "repo" ]]; then
  # Find repo root
  if git rev-parse --show-toplevel &>/dev/null; then
    TARGET="$(git rev-parse --show-toplevel)/.claude"
  else
    TARGET="$(pwd)/.claude"
  fi
fi

echo "=== Claudestrator Installer ==="
echo "Source: $SOURCE"
echo "Target: $TARGET"
echo "Mode:   $MODE"
echo ""

# Verify source exists
if [[ ! -d "$SOURCE/agents" ]]; then
  echo "FAIL: Source directory $SOURCE/agents not found."
  echo "Run this script from the Claudestrator repo root."
  exit 1
fi

# Clean install: remove old dirs, then copy fresh
for dir in "${DIRS[@]}"; do
  if [[ -d "$TARGET/$dir" ]]; then
    echo "  Removing old $dir/..."
    rm -rf "$TARGET/$dir"
  fi
  echo "  Installing $dir/..."
  cp -r "$SOURCE/$dir" "$TARGET/$dir"
done

# Optional dirs: copy if not present, don't overwrite
for dir in "${OPTIONAL_DIRS[@]}"; do
  if [[ -d "$TARGET/$dir" ]]; then
    echo "  Keeping existing $dir/ (optional, not overwritten)"
  elif [[ -d "$SOURCE/$dir" ]]; then
    echo "  Installing $dir/ (optional)..."
    cp -r "$SOURCE/$dir" "$TARGET/$dir"
  fi
done

# CLAUDE.md: merge or create
if [[ -f "$TARGET/CLAUDE.md" ]]; then
  # Check if Claudestrator content is already present
  if grep -q "## Delegation rule" "$TARGET/CLAUDE.md" 2>/dev/null; then
    echo "  CLAUDE.md already contains Claudestrator — replacing Claudestrator section..."
    # Extract non-Claudestrator content (everything before "# Claudestrator")
    if grep -qn "^# Claudestrator" "$TARGET/CLAUDE.md"; then
      head_lines=$(($(grep -n "^# Claudestrator" "$TARGET/CLAUDE.md" | head -1 | cut -d: -f1) - 1))
      if [[ $head_lines -gt 0 ]]; then
        head -n "$head_lines" "$TARGET/CLAUDE.md" > "$TARGET/CLAUDE.md.tmp"
        cat "$SOURCE/CLAUDE.md" >> "$TARGET/CLAUDE.md.tmp"
        mv "$TARGET/CLAUDE.md.tmp" "$TARGET/CLAUDE.md"
      else
        cp "$SOURCE/CLAUDE.md" "$TARGET/CLAUDE.md"
      fi
    else
      # Has delegation rule but no "# Claudestrator" header — full replace
      cp "$SOURCE/CLAUDE.md" "$TARGET/CLAUDE.md"
    fi
  else
    echo "  Merging CLAUDE.md (prepending Claudestrator content)..."
    mv "$TARGET/CLAUDE.md" "$TARGET/CLAUDE.md.bak"
    cat "$SOURCE/CLAUDE.md" "$TARGET/CLAUDE.md.bak" > "$TARGET/CLAUDE.md"
    rm "$TARGET/CLAUDE.md.bak"
  fi
else
  echo "  Creating CLAUDE.md..."
  cp "$SOURCE/CLAUDE.md" "$TARGET/CLAUDE.md"
fi

echo ""
echo "=== Verification ==="
errors=0

check_file() {
  if [[ -f "$1" ]]; then
    echo "  OK  $2"
  else
    echo "  FAIL  $2"
    errors=$((errors+1))
  fi
}

# Agents: count roles, check contracts and templates
role_count=$(find "$TARGET/agents" -maxdepth 1 -name '*.md' -type f | wc -l)
if [[ $role_count -ge 31 ]]; then
  echo "  OK  agents/ ($role_count roles)"
else
  echo "  FAIL  agents/ (expected 31+, got $role_count)"
  errors=$((errors+1))
fi
check_file "$TARGET/agents/contracts/operating-model.md" "agents/contracts/operating-model.md"
check_file "$TARGET/agents/contracts/subagent-contracts.md" "agents/contracts/subagent-contracts.md"
template_count=$(find "$TARGET/agents/team-templates" -name '*.json' -type f | wc -l)
if [[ $template_count -ge 8 ]]; then
  echo "  OK  agents/team-templates/ ($template_count templates)"
else
  echo "  FAIL  agents/team-templates/ (expected 8+, got $template_count)"
  errors=$((errors+1))
fi

# Commands
skill_count=$(find "$TARGET/commands" -name '*.md' -type f | wc -l)
if [[ $skill_count -ge 6 ]]; then
  echo "  OK  commands/ ($skill_count skills)"
else
  echo "  FAIL  commands/ (expected 6+, got $skill_count)"
  errors=$((errors+1))
fi

# Policies
check_file "$TARGET/policies/catalog.md" "policies/catalog.md"

# Scripts
check_file "$TARGET/scripts/check-publication-safety.sh" "scripts/check-publication-safety.sh"
check_file "$TARGET/scripts/check-publication-safety.ps1" "scripts/check-publication-safety.ps1"
check_file "$TARGET/scripts/validate-skill-pack.sh" "scripts/validate-skill-pack.sh"

# CLAUDE.md with required sections
if [[ -f "$TARGET/CLAUDE.md" ]]; then
  echo "  OK  CLAUDE.md ($(wc -l < "$TARGET/CLAUDE.md") lines)"
  for section in "## Delegation rule" "## Role index" "## Engineering hygiene" "## Publication safety"; do
    if grep -q "$section" "$TARGET/CLAUDE.md"; then
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
  echo "Next: restart Claude, then run /init-project to configure project policies."
fi

#!/usr/bin/env bash
set -euo pipefail

# Validate structural integrity of the Orchestrarium Codex skill pack.
# Supported layouts:
#   bash src.codex/skills/lead/scripts/validate-skill-pack.sh   (dev repo)
#   bash .codex/skills/lead/scripts/validate-skill-pack.sh      (global install)
#   bash .agents/skills/lead/scripts/validate-skill-pack.sh     (repo-local install)

# Auto-detect layout.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
if [[ -d "src.codex/skills" && -f "src.codex/AGENTS.shared.md" ]]; then
  # Dev repo: assemble AGENTS.md from split source files for validation
  SKILLS_DIR="$(cd "src.codex/skills" && pwd -P)"
  SCRIPTS_DIR="$(cd "src.codex/skills/lead/scripts" && pwd -P)"
  AGENTS_FILE="$(mktemp)"
  cat "src.codex/AGENTS.shared.md" "src.codex/AGENTS.codex.md" > "$AGENTS_FILE"
  trap "rm -f '$AGENTS_FILE'" EXIT
elif [[ -d "$SCRIPT_DIR/../.." && -f "$SCRIPT_DIR/../SKILL.md" && -f "$SCRIPT_DIR/../../../AGENTS.md" ]]; then
  SKILLS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
  SCRIPTS_DIR="$SCRIPT_DIR"
  AGENTS_FILE="$(cd "$SCRIPT_DIR/../../.." && pwd -P)/AGENTS.md"
elif [[ -d "$SCRIPT_DIR/../.." && -f "$SCRIPT_DIR/../SKILL.md" && -f "$SCRIPT_DIR/../../../../AGENTS.md" ]]; then
  SKILLS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
  SCRIPTS_DIR="$SCRIPT_DIR"
  AGENTS_FILE="$(cd "$SCRIPT_DIR/../../../.." && pwd -P)/AGENTS.md"
elif [[ -d ".codex/skills" && -f ".codex/AGENTS.md" ]]; then
  SKILLS_DIR="$(cd ".codex/skills" && pwd -P)"
  SCRIPTS_DIR="$(cd ".codex/skills/lead/scripts" && pwd -P)"
  AGENTS_FILE="$(cd ".codex" && pwd -P)/AGENTS.md"
elif [[ -d ".agents/skills" && -f "AGENTS.md" ]]; then
  SKILLS_DIR="$(cd ".agents/skills" && pwd -P)"
  SCRIPTS_DIR="$(cd ".agents/skills/lead/scripts" && pwd -P)"
  AGENTS_FILE="$(cd "." && pwd -P)/AGENTS.md"
else
  echo "FAIL: Could not detect Orchestrarium layout. Expected one of: src.codex/, .codex/, or .agents/ with root AGENTS.md." >&2
  exit 1
fi
PASS=0
WARN=0
FAIL=0

pass()  { PASS=$((PASS + 1)); echo "  PASS  $1"; }
warn()  { WARN=$((WARN + 1)); echo "  WARN  $1"; }
fail()  { FAIL=$((FAIL + 1)); echo "  FAIL  $1"; }

echo "=== Core files ==="

for f in \
  "$AGENTS_FILE" \
  "$SKILLS_DIR/lead/SKILL.md" \
  "$SKILLS_DIR/lead/operating-model.md" \
  "$SKILLS_DIR/lead/subagent-contracts.md" \
  "$SKILLS_DIR/lead/external-dispatch.md" \
  "$SKILLS_DIR/init-project/SKILL.md" \
  "$SKILLS_DIR/init-project/agents/openai.yaml" \
  "$SKILLS_DIR/consultant/SKILL.md" \
  "$SKILLS_DIR/second-opinion/SKILL.md" \
  "$SCRIPTS_DIR/check-publication-safety.sh" \
  "$SCRIPTS_DIR/check-publication-safety.ps1" \
  "$SCRIPTS_DIR/validate-skill-pack.sh"
do
  if [[ -f "$f" ]]; then pass "$f"; else fail "$f missing"; fi
done

if [[ -d "src.codex/skills" && -f "src.codex/AGENTS.shared.md" ]]; then
  echo ""
  echo "=== Branch-level docs surface ==="
  for f in docs/README.md docs/provider-runtime-layout.md docs/agents-mode-reference.md references-codex/README.md; do
    if [[ -f "$f" ]]; then pass "$f"; else fail "$f missing"; fi
  done
fi

echo ""
echo "=== Role index consistency ==="

mapfile -t indexed_roles < <(
  grep -oE '\$[a-z][-a-z]*' "$AGENTS_FILE" \
    | sed 's/^\$//' \
    | sort -u
)

for role in "${indexed_roles[@]}"; do
  skill_dir="$SKILLS_DIR/$role"
  if [[ ! -d "$skill_dir" ]]; then
    fail "Role \$$role in AGENTS.md but no directory at $skill_dir"
    continue
  fi
  if [[ ! -f "$skill_dir/SKILL.md" ]]; then
    fail "$skill_dir/SKILL.md missing"
  else
    pass "$skill_dir/SKILL.md"
  fi
  if [[ ! -f "$skill_dir/agents/openai.yaml" ]]; then
    fail "$skill_dir/agents/openai.yaml missing"
  else
    pass "$skill_dir/agents/openai.yaml"
  fi
done

echo ""
echo "=== Orphaned skill directories ==="

UTILITY_SKILLS=(second-opinion)

for dir in "$SKILLS_DIR"/*/; do
  role="$(basename "$dir")"
  is_utility=0
  for util in "${UTILITY_SKILLS[@]}"; do
    if [[ "$util" == "$role" ]]; then is_utility=1; break; fi
  done
  if [[ $is_utility -eq 1 ]]; then continue; fi
  found=0
  for indexed in "${indexed_roles[@]}"; do
    if [[ "$indexed" == "$role" ]]; then found=1; break; fi
  done
  if [[ $found -eq 0 ]]; then
    warn "Directory $dir exists but \$$role is not in AGENTS.md role index"
  fi
done

echo ""
echo "=== Scripts ==="

for script in "$SCRIPTS_DIR"/*.sh; do
  [[ -f "$script" ]] || continue
  if head -1 "$script" | grep -q '^#!'; then
    pass "$script has shebang"
  else
    warn "$script missing shebang line"
  fi
done

echo ""
echo "=== AGENTS.md required sections ==="

for section in "delegation" "Role index" "Engineering hygiene"; do
  if grep -qi "$section" "$AGENTS_FILE"; then
    pass "Section '$section' found"
  else
    fail "Section '$section' missing from AGENTS.md"
  fi
done

echo ""
echo "=== Summary ==="
echo "  PASS: $PASS  WARN: $WARN  FAIL: $FAIL"

if [[ $FAIL -gt 0 ]]; then
  echo "VALIDATION FAILED"
  exit 1
else
  if [[ $WARN -gt 0 ]]; then
    echo "VALIDATION PASSED (with warnings)"
  else
    echo "VALIDATION PASSED"
  fi
  exit 0
fi

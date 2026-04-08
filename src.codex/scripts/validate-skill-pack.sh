#!/usr/bin/env bash
set -euo pipefail

# Validate structural integrity of the Orchestrarium Codex skill pack.
# Run from the repository root:
#   bash src.codex/scripts/validate-skill-pack.sh   (dev repo)
#   bash .codex/scripts/validate-skill-pack.sh       (installed)

# Auto-detect: src.codex/ (dev) or .codex/ (installed)
if [[ -d "src.codex/skills" ]]; then
  CODEX="src.codex"
elif [[ -d ".codex/skills" ]]; then
  CODEX=".codex"
else
  echo "FAIL: Neither src.codex/ nor .codex/ found. Run from repo root." >&2
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
  "$CODEX/AGENTS.md" \
  "$CODEX/skills/lead/SKILL.md" \
  "$CODEX/skills/lead/operating-model.md" \
  "$CODEX/skills/lead/subagent-contracts.md" \
  "$CODEX/skills/consultant/SKILL.md" \
  "$CODEX/common-skills/ask-claude/SKILL.md" \
  "$CODEX/common-skills/ask-claude/invocation.md" \
  "$CODEX/common-skills/second-opinion/SKILL.md" \
  "$CODEX/scripts/check-publication-safety.sh"
do
  if [[ -f "$f" ]]; then pass "$f"; else fail "$f missing"; fi
done

echo ""
echo "=== Role index consistency ==="

# Extract role names from AGENTS.md role index ($role-name pattern)
mapfile -t indexed_roles < <(
  grep -oE '\$[a-z][-a-z]*' "$CODEX/AGENTS.md" \
    | sed 's/^\$//' \
    | sort -u
)

for role in "${indexed_roles[@]}"; do
  skill_dir="$CODEX/skills/$role"
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

for dir in "$CODEX/skills"/*/; do
  role="$(basename "$dir")"
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

for script in "$CODEX/scripts"/*.sh; do
  [[ -f "$script" ]] || continue
  if head -1 "$script" | grep -q '^#!'; then
    pass "$script has shebang"
  else
    warn "$script missing shebang line"
  fi
done

echo ""
echo "=== AGENTS.md required sections ==="

for section in "Default Delegation Rule" "Role index" "Global engineering hygiene"; do
  if grep -qi "$section" "$CODEX/AGENTS.md"; then
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

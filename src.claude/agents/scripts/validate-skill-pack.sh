#!/usr/bin/env bash
# Validate Claudestrator skill-pack structural integrity.
# Run from repo root: bash src.claude/agents/scripts/validate-skill-pack.sh
#   or after install:  bash .claude/agents/scripts/validate-skill-pack.sh
set -euo pipefail

# Auto-detect pack root: src.claude/ (dev repo) or .claude/ (installed)
if [[ -d "src.claude/agents" ]]; then
  PACK="src.claude"
elif [[ -d ".claude/agents" ]]; then
  PACK=".claude"
else
  echo "FAIL: neither src.claude/ nor .claude/ found. Run from repo root."
  exit 1
fi

errors=0
warnings=0
checks=0

pass() { checks=$((checks+1)); echo "  PASS  $1"; }
fail() { errors=$((errors+1)); checks=$((checks+1)); echo "  FAIL  $1"; }
warn() { warnings=$((warnings+1)); checks=$((checks+1)); echo "  WARN  $1"; }

echo "=== Claudestrator skill-pack validation ==="
echo ""

# 1. Core files exist
echo "[Core files]"
for f in $PACK/CLAUDE.md $PACK/AGENTS.md $PACK/agents/lead.md $PACK/agents/consultant.md \
         $PACK/agents/contracts/operating-model.md \
         $PACK/agents/contracts/subagent-contracts.md \
         $PACK/agents/contracts/policies-catalog.md \
         $PACK/commands/agents-second-opinion.md; do
  if [[ -f "$f" ]]; then pass "$f exists"; else fail "$f missing"; fi
done
echo ""

# 2. Role index vs actual agent files
echo "[Role index consistency]"
if [[ -f $PACK/AGENTS.md ]]; then
  # Extract role names from AGENTS.md (shared governance, lines with $role-name pattern)
  roles=$(grep -oE '\$[a-z][-a-z]*' $PACK/AGENTS.md | sed 's/^\$//' | sort -u)
  for role in $roles; do
    if [[ -f "$PACK/agents/${role}.md" ]]; then
      pass "$role has agent file"
    else
      fail "$role in role index but $PACK/agents/${role}.md missing"
    fi
  done

  # Check for orphaned agent files
  for f in $PACK/agents/*.md; do
    name=$(basename "$f" .md)
    if ! echo "$roles" | grep -qx "$name"; then
      warn "$name has agent file but not in AGENTS.md role index"
    fi
  done
fi
echo ""

# 3. Team templates have required fields
echo "[Team templates]"
for f in $PACK/agents/team-templates/*.json; do
  name=$(basename "$f")
  if grep -q '"requiresLead"' "$f"; then
    pass "$name has requiresLead"
  else
    fail "$name missing requiresLead field"
  fi
  if grep -q '"chain"' "$f"; then
    pass "$name has chain"
  else
    fail "$name missing chain field"
  fi
done
echo ""

# 4. Skills reference valid files
echo "[Skills]"
for f in $PACK/commands/*.md; do
  name=$(basename "$f" .md)
  pass "/$name skill exists"
done
if [[ -f "$PACK/agents/contracts/policies-catalog.md" ]]; then
  pass "policy catalog exists"
else
  fail "policy catalog missing (commands reference it)"
fi
echo ""

# 5. Scripts are executable-ready
echo "[Scripts]"
for f in $PACK/agents/scripts/*.sh; do
  if head -1 "$f" | grep -q '^#!'; then
    pass "$(basename "$f") has shebang"
  else
    warn "$(basename "$f") missing shebang line"
  fi
done
echo ""

# 6. CLAUDE.md has required sections
echo "[CLAUDE.md sections]"
for section in "Delegation rule"; do
  if grep -q "## $section" $PACK/CLAUDE.md; then
    pass "## $section present in CLAUDE.md"
  else
    fail "## $section missing from CLAUDE.md"
  fi
done

# 6b. AGENTS.md has required sections (shared governance)
echo "[AGENTS.md sections]"
for section in "Role index" "Engineering hygiene" "Publication safety" "Core delegation principles"; do
  if grep -q "## $section" $PACK/AGENTS.md; then
    pass "## $section present in AGENTS.md"
  else
    fail "## $section missing from AGENTS.md"
  fi
done
echo ""

# Summary
echo "=== Summary ==="
echo "  Checks: $checks  |  Passed: $((checks - errors - warnings))  |  Warnings: $warnings  |  Errors: $errors"
if [[ $errors -gt 0 ]]; then
  echo "  RESULT: FAIL"
  exit 1
elif [[ $warnings -gt 0 ]]; then
  echo "  RESULT: PASS with warnings"
  exit 0
else
  echo "  RESULT: PASS"
  exit 0
fi

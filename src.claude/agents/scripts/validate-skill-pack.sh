#!/usr/bin/env bash
# Validate Claudestrator skill-pack structural integrity.
# Run from repo root: bash src.claude/agents/scripts/validate-skill-pack.sh
#   or after install:  bash .claude/agents/scripts/validate-skill-pack.sh
set -euo pipefail

# Auto-detect pack root: src.claude/ (dev repo) or .claude/ (installed)
DEV_REPO=0
if [[ -d "src.claude/agents" ]]; then
  PACK="src.claude"
  REPO_ROOT="$(pwd -P)"
  DEV_REPO=1
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
check_contains() {
  local file="$1"
  local needle="$2"
  local message="$3"
  if grep -Fq "$needle" "$file"; then
    pass "$message"
  else
    fail "$message"
  fi
}
warn() { warnings=$((warnings+1)); checks=$((checks+1)); echo "  WARN  $1"; }

echo "=== Claudestrator skill-pack validation ==="
echo ""

# 1. Core files exist
echo "[Core files]"
for f in $PACK/CLAUDE.md $PACK/AGENTS.shared.md $PACK/agents/lead.md $PACK/agents/consultant.md \
         $PACK/agents/external-worker.md \
         $PACK/agents/external-reviewer.md \
         $PACK/agents/scripts/invoke-claude-api.sh \
         $PACK/agents/scripts/invoke-claude-api.ps1 \
         $PACK/agents/contracts/operating-model.md \
         $PACK/agents/contracts/external-dispatch.md \
         $PACK/agents/contracts/subagent-contracts.md \
         $PACK/agents/contracts/policies-catalog.md \
         $PACK/agents/scripts/check-publication-safety.sh \
         $PACK/agents/scripts/check-publication-safety.ps1 \
         $PACK/skills/agents-second-opinion/SKILL.md; do
  if [[ -f "$f" ]]; then pass "$f exists"; else fail "$f missing"; fi
done

if [[ "$PACK" == "src.claude" ]]; then
  for f in \
    src.claude/README.md \
    docs/README.md \
    docs/agents-mode-reference.md \
    docs/provider-runtime-layout.md \
    references-claude/README.md \
    references-claude/evidence-based-answer-pipeline.md \
    references-claude/operating-model-diagram.md \
    references-claude/periodic-control-matrix.md \
    references-claude/repository-publication-safety.md \
    references-claude/repository-task-memory.md \
    references-claude/subagent-operating-model.md \
    references-claude/workflow-strategy-comparison.md \
    references-claude/ru/operating-model-diagram.md \
    references-claude/ru/periodic-control-matrix.md \
    references-claude/ru/repository-publication-safety.md \
    references-claude/ru/repository-task-memory.md \
    references-claude/ru/subagent-operating-model.md \
    references-claude/ru/workflow-strategy-comparison.md
  do
    if [[ -f "$f" ]]; then pass "$f exists"; else fail "$f missing"; fi
  done
fi

if [[ -d "$PACK/commands" ]]; then
  fail "$PACK/commands should be absent after skills migration"
else
  pass "$PACK/commands absent after skills migration"
fi
echo ""

if [[ "$PACK" == "src.claude" ]]; then
  echo "[Docs consistency]"
  check_contains "docs/README.md" "externalClaudeSecretMode" \
    "docs/README.md documents Claude transport keys on the Claude line"
  check_contains "docs/README.md" "externalClaudeApiMode" \
    "docs/README.md documents Claude API transport on the Claude line"
  if grep -Fq 'does not use `externalClaudeSecretMode`, `externalClaudeApiMode`, or `externalClaudeProfile`' "docs/README.md"; then
    fail "docs/README.md does not claim Claude transport keys are absent"
  else
    pass "docs/README.md does not claim Claude transport keys are absent"
  fi
  echo ""
fi

# 2. Role index vs actual agent files
echo "[Role index consistency]"
if [[ -f $PACK/AGENTS.shared.md ]]; then
  # Extract role names from AGENTS.md (shared governance, lines with $role-name pattern)
  roles=$(grep -oE '\$[a-z][-a-z]*' $PACK/AGENTS.shared.md | sed 's/^\$//' | sort -u)
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
    if [[ "$name" == "external-worker" || "$name" == "external-reviewer" ]]; then
      pass "$name is an expected external adapter file"
    elif ! echo "$roles" | grep -qx "$name"; then
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
if compgen -G "$PACK/skills/*/SKILL.md" > /dev/null; then
  for f in $PACK/skills/*/SKILL.md; do
    name=$(basename "$(dirname "$f")")
    pass "/$name skill exists"
  done
else
  fail "no skills found under $PACK/skills/*/SKILL.md"
fi
if [[ -f "$PACK/agents/contracts/policies-catalog.md" ]]; then
  pass "policy catalog exists"
else
  fail "policy catalog missing (skills reference it)"
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
  if grep -q "## $section" $PACK/AGENTS.shared.md; then
    pass "## $section present in AGENTS.md"
  else
    fail "## $section missing from AGENTS.md"
  fi
done
echo ""

# 6c. Consultant no-fallback canon
echo "[Consultant no-fallback canon]"
if grep -Fq "consultantMode: auto" "$PACK/agents/consultant.md"; then
  fail "consultant doc does not document consultantMode auto"
else
  pass "consultant doc does not document consultantMode auto"
fi
if grep -Fq "fallback approved by user" "$PACK/agents/consultant.md"; then
  fail "consultant doc does not reserve consultant fallback deviations"
else
  pass "consultant doc does not reserve consultant fallback deviations"
fi
if grep -Fq "consultantMode: auto" "$PACK/skills/agents-second-opinion/SKILL.md"; then
  fail "agents-second-opinion skill does not expose consultantMode auto"
else
  pass "agents-second-opinion skill does not expose consultantMode auto"
fi
if grep -Fq "allowed: external | auto | internal | disabled" "$PACK/skills/agents-init-project/SKILL.md"; then
  fail "agents-init-project restricts consultantMode to external/internal/disabled"
else
  pass "agents-init-project restricts consultantMode to external/internal/disabled"
fi
if grep -Fq "allowed: external | auto | internal | disabled" "$PACK/agents/contracts/external-dispatch.md"; then
  fail "external-dispatch schema restricts consultantMode to external/internal/disabled"
else
  pass "external-dispatch schema restricts consultantMode to external/internal/disabled"
fi
if grep -Fq "fallback approved by user" "$PACK/agents/contracts/external-dispatch.md"; then
  fail "external-dispatch does not record consultant fallback approvals"
else
  pass "external-dispatch does not record consultant fallback approvals"
fi
if grep -Fq 'Read and normalize `.claude/.agents-mode` first.' "$PACK/agents/contracts/subagent-contracts.md"; then
  pass "subagent-contracts require read-time agents-mode normalization"
else
  fail "subagent-contracts require read-time agents-mode normalization"
fi
if grep -Fq "normalize it to the current canonical format before presenting or trusting the current values." "$PACK/skills/agents-init-project/SKILL.md"; then
  pass "agents-init-project normalizes existing agents-mode before reading values"
else
  fail "agents-init-project normalizes existing agents-mode before reading values"
fi
if grep -Fq 'Any read of `.claude/.agents-mode` that drives a decision should normalize the file to the current canonical format before trusting the flags.' "$PACK/skills/agents-init-project/SKILL.md"; then
  pass "agents-init-project requires read-time agents-mode normalization"
else
  fail "agents-init-project requires read-time agents-mode normalization"
fi
if grep -Fq 'read and normalize `.claude/.agents-mode`.' "$PACK/skills/agents-second-opinion/SKILL.md"; then
  pass "agents-second-opinion normalizes agents-mode before reporting status"
else
  fail "agents-second-opinion normalizes agents-mode before reporting status"
fi
if grep -Fq 'Adapter host runtime' "$PACK/AGENTS.shared.md"; then
  fail "shared governance no longer allows adapter-host metadata for external execution"
else
  pass "shared governance no longer allows adapter-host metadata for external execution"
fi
if grep -Fq 'must use direct external launch' "$PACK/AGENTS.shared.md"; then
  pass "shared governance requires direct external launch"
else
  fail "shared governance requires direct external launch"
fi
if grep -Fq 'Read and normalize `.claude/.agents-mode` to the current canonical format before trusting its flags.' "$PACK/agents/external-worker.md"; then
  pass "external-worker normalizes agents-mode before routing"
else
  fail "external-worker normalizes agents-mode before routing"
fi
if grep -Fq 'Read and normalize `.claude/.agents-mode` to the current canonical format before trusting its flags.' "$PACK/agents/external-reviewer.md"; then
  pass "external-reviewer normalizes agents-mode before routing"
else
  fail "external-reviewer normalizes agents-mode before routing"
fi
if grep -Fq 'Adapter host runtime:' "$PACK/agents/contracts/external-dispatch.md"; then
  fail "external-dispatch no longer records adapter host runtime"
else
  pass "external-dispatch no longer records adapter host runtime"
fi
if grep -Fq 'must use direct external launch' "$PACK/agents/contracts/external-dispatch.md"; then
  pass "external-dispatch requires direct external launch"
else
  fail "external-dispatch requires direct external launch"
fi
if grep -Fq 'Adapter host runtime:' "$PACK/agents/consultant.md"; then
  fail "consultant no longer records adapter host runtime"
else
  pass "consultant no longer records adapter host runtime"
fi
if grep -Fq 'must use direct external launch' "$PACK/agents/consultant.md"; then
  pass "consultant requires direct external launch when external"
else
  fail "consultant requires direct external launch when external"
fi
if grep -Fq 'Requested provider: <auto' "$PACK/agents/consultant.md"; then
  fail "consultant provenance no longer emits auto as a requested provider"
else
  pass "consultant provenance no longer emits auto as a requested provider"
fi
if grep -Fq 'Requested provider: <auto' "$PACK/agents/contracts/external-dispatch.md"; then
  fail "external-dispatch provenance no longer emits auto as a requested provider"
else
  pass "external-dispatch provenance no longer emits auto as a requested provider"
fi
if grep -Fq 'Actual execution path:** <external CLI (provider name) | internal subagent' "$PACK/agents/consultant.md"; then
  fail "consultant does not mislabel internal subagent as actual execution path"
else
  pass "consultant does not mislabel internal subagent as actual execution path"
fi
if grep -Fq "externalPriorityProfile" "$PACK/agents/external-worker.md"; then
  pass "external-worker honors structured profile keys"
else
  fail "external-worker honors structured profile keys"
fi
if grep -Fq "externalPriorityProfile" "$PACK/agents/external-reviewer.md"; then
  pass "external-reviewer honors structured profile keys"
else
  fail "external-reviewer honors structured profile keys"
fi
if grep -Fq "direct external launch contract" "$PACK/agents/external-worker.md"; then
  pass "external-worker requires direct external launch"
else
  fail "external-worker requires direct external launch"
fi
if grep -Fq "direct external launch contract" "$PACK/agents/external-reviewer.md"; then
  pass "external-reviewer requires direct external launch"
else
  fail "external-reviewer requires direct external launch"
fi
if grep -Fq "SECRET.md" "$PACK/agents/scripts/invoke-claude-api.sh"; then
  pass "Claude API wrapper reads SECRET.md"
else
  fail "Claude API wrapper reads SECRET.md"
fi
if grep -Fq "claude-api" "$PACK/agents/scripts/invoke-claude-api.sh"; then
  pass "Claude API wrapper invokes claude-api"
else
  fail "Claude API wrapper invokes claude-api"
fi
if grep -Fq "SECRET.md" "$PACK/agents/scripts/invoke-claude-api.ps1"; then
  pass "PowerShell Claude API wrapper reads SECRET.md"
else
  fail "PowerShell Claude API wrapper reads SECRET.md"
fi
if grep -Fq "claude-api" "$PACK/agents/scripts/invoke-claude-api.ps1"; then
  pass "PowerShell Claude API wrapper invokes claude-api"
else
  fail "PowerShell Claude API wrapper invokes claude-api"
fi
if grep -Fq -- "-AsHashtable" "$PACK/agents/scripts/invoke-claude-api.ps1"; then
  fail "PowerShell Claude API wrapper avoids ConvertFrom-Json -AsHashtable"
else
  pass "PowerShell Claude API wrapper avoids ConvertFrom-Json -AsHashtable"
fi
if grep -Fq -- "--print-secret-path" "$PACK/agents/scripts/invoke-claude-api.ps1"; then
  pass "PowerShell Claude API wrapper supports POSIX-style print-secret-path"
else
  fail "PowerShell Claude API wrapper supports POSIX-style print-secret-path"
fi
if grep -Fq "CLAUDE_API_BIN" "$PACK/agents/scripts/invoke-claude-api.sh"; then
  pass "Bash Claude API wrapper documents CLAUDE_API_BIN override"
else
  fail "Bash Claude API wrapper documents CLAUDE_API_BIN override"
fi
if grep -Fq "claude-api.cmd" "$PACK/agents/scripts/invoke-claude-api.sh"; then
  pass "Bash Claude API wrapper resolves Windows claude-api.cmd"
else
  fail "Bash Claude API wrapper resolves Windows claude-api.cmd"
fi

echo "[External brigade surface]"
check_contains "$PACK/skills/agents-external-brigade/SKILL.md" "same-provider helper instances" \
  "agents-external-brigade skill documents same-provider helper fan-out"
check_contains "$PACK/skills/agents-external-brigade/SKILL.md" "same-lane distinct-opinion requirements" \
  "agents-external-brigade skill treats opinion counts separately from helper multiplicity"
check_contains "$PACK/skills/agents-help/SKILL.md" "/agents-external-brigade" \
  "agents-help lists the external-brigade skill"
check_contains "$PACK/agents/lead.md" "/agents-external-brigade" \
  "lead guide mentions the external-brigade skill"
check_contains "$PACK/agents/contracts/external-dispatch.md" "Same-provider external helper reuse is allowed" \
  "external-dispatch documents same-provider brigade reuse"
check_contains "$PACK/agents/contracts/external-dispatch.md" "brigade surface" \
  "external-dispatch points to the brigade surface"
check_contains "$PACK/agents/contracts/operating-model.md" "Same-provider external helper reuse is allowed" \
  "operating-model documents same-provider brigade reuse"
check_contains "$PACK/agents/contracts/subagent-contracts.md" "/agents-external-brigade" \
  "subagent-contracts route bounded external-helper brigades through the dedicated skill"
check_contains "$PACK/agents/external-worker.md" "same-lane distinct-opinion contract" \
  "external-worker distinguishes opinion counts from helper multiplicity"
check_contains "$PACK/agents/external-reviewer.md" "same-lane distinct-opinion contract" \
  "external-reviewer distinguishes opinion counts from helper multiplicity"
check_contains "$PACK/skills/agents-init-project/SKILL.md" "same-lane distinct-opinion requirement" \
  "agents-init-project documents opinion counts as same-lane distinct-opinion semantics"
check_contains "$PACK/skills/agents-second-opinion/SKILL.md" "same-lane distinct-opinion requirement" \
  "agents-second-opinion documents opinion counts as same-lane distinct-opinion semantics"
echo ""

if [[ $DEV_REPO -eq 1 ]]; then
  if grep -Fq "## Canonical maintenance" "$REPO_ROOT/docs/agents-mode-reference.md"; then
    pass "agents-mode reference defines canonical maintenance"
  else
    fail "agents-mode reference defines canonical maintenance"
  fi
  if grep -Fq "Read-time normalization preserves the effective values of known keys" "$REPO_ROOT/docs/agents-mode-reference.md"; then
    pass "agents-mode reference documents read-time normalization semantics"
  else
    fail "agents-mode reference documents read-time normalization semantics"
  fi
  if grep -Fq "same-lane distinct-opinion contract" "$REPO_ROOT/docs/agents-mode-reference.md"; then
    pass "agents-mode reference distinguishes opinion counts from helper multiplicity"
  else
    fail "agents-mode reference distinguishes opinion counts from helper multiplicity"
  fi
  if grep -Fq "/agents-external-brigade" "$REPO_ROOT/docs/agents-mode-reference.md"; then
    pass "agents-mode reference points to the brigade surface"
  else
    fail "agents-mode reference points to the brigade surface"
  fi
fi
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

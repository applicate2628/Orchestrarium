#!/usr/bin/env bash
set -euo pipefail

# Validate structural integrity of the Orchestrarium Codex skill pack.
# Supported layouts:
#   bash src.codex/skills/lead/scripts/validate-skill-pack.sh   (dev repo)
#   bash .codex/skills/lead/scripts/validate-skill-pack.sh      (global install)
#   bash .agents/skills/lead/scripts/validate-skill-pack.sh     (repo-local install)

# Auto-detect layout.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DEV_REPO=0
CODEX_RUNTIME_ROOT=""
if [[ -d "src.codex/skills" && -f "src.codex/AGENTS.shared.md" ]]; then
  # Dev repo: assemble AGENTS.md from split source files for validation
  SKILLS_DIR="$(cd "src.codex/skills" && pwd -P)"
  SCRIPTS_DIR="$(cd "src.codex/skills/lead/scripts" && pwd -P)"
  DOCS_DIR="$(cd "docs" && pwd -P)"
  AGENTS_FILE="$(mktemp)"
  DEV_REPO=1
  cat "src.codex/AGENTS.shared.md" "src.codex/AGENTS.codex.md" > "$AGENTS_FILE"
  trap "rm -f '$AGENTS_FILE'" EXIT
elif [[ -d "$SCRIPT_DIR/../.." && -f "$SCRIPT_DIR/../SKILL.md" && -f "$SCRIPT_DIR/../../../AGENTS.md" ]]; then
  SKILLS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
  SCRIPTS_DIR="$SCRIPT_DIR"
  AGENTS_FILE="$(cd "$SCRIPT_DIR/../../.." && pwd -P)/AGENTS.md"
  CODEX_RUNTIME_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd -P)"
elif [[ -d "$SCRIPT_DIR/../.." && -f "$SCRIPT_DIR/../SKILL.md" && -f "$SCRIPT_DIR/../../../../AGENTS.md" ]]; then
  SKILLS_DIR="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
  SCRIPTS_DIR="$SCRIPT_DIR"
  AGENTS_FILE="$(cd "$SCRIPT_DIR/../../../.." && pwd -P)/AGENTS.md"
  CODEX_RUNTIME_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd -P)/.codex"
elif [[ -d ".codex/skills" && -f ".codex/AGENTS.md" ]]; then
  SKILLS_DIR="$(cd ".codex/skills" && pwd -P)"
  SCRIPTS_DIR="$(cd ".codex/skills/lead/scripts" && pwd -P)"
  AGENTS_FILE="$(cd ".codex" && pwd -P)/AGENTS.md"
  CODEX_RUNTIME_ROOT="$(cd ".codex" && pwd -P)"
elif [[ -d ".agents/skills" && -f "AGENTS.md" ]]; then
  SKILLS_DIR="$(cd ".agents/skills" && pwd -P)"
  SCRIPTS_DIR="$(cd ".agents/skills/lead/scripts" && pwd -P)"
  AGENTS_FILE="$(cd "." && pwd -P)/AGENTS.md"
  CODEX_RUNTIME_ROOT="$(cd "." && pwd -P)/.codex"
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

for f in \
  "$SKILLS_DIR/external-brigade/SKILL.md" \
  "$SKILLS_DIR/external-brigade/agents/openai.yaml"
do
  if [[ -f "$f" ]]; then pass "$f"; else fail "$f missing"; fi
done

if [[ -d "src.codex/skills" && -f "src.codex/AGENTS.shared.md" ]]; then
  echo ""
  echo "=== Branch-level docs surface ==="
  for f in \
    src.codex/agents/default.toml \
    src.codex/agents/worker.toml \
    src.codex/agents/explorer.toml \
    src.codex/README.md \
    docs/README.md \
    docs/provider-runtime-layout.md \
    docs/agents-mode-reference.md \
    references-codex/README.md \
    references-codex/evidence-based-answer-pipeline.md \
    references-codex/operating-model-diagram.md \
    references-codex/periodic-control-matrix.md \
    references-codex/repository-publication-safety.md \
    references-codex/repository-task-memory.md \
    references-codex/subagent-operating-model.md \
    references-codex/workflow-strategy-comparison.md \
    references-codex/ru/operating-model-diagram.md \
    references-codex/ru/periodic-control-matrix.md \
    references-codex/ru/repository-publication-safety.md \
    references-codex/ru/repository-task-memory.md \
    references-codex/ru/subagent-operating-model.md \
    references-codex/ru/workflow-strategy-comparison.md
  do
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

UTILITY_SKILLS=(second-opinion external-brigade)

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
echo "=== Consultant no-fallback canon ==="

if grep -Fq "consultantMode: auto" "$SKILLS_DIR/consultant/SKILL.md"; then
  fail "consultant skill does not document consultantMode auto"
else
  pass "consultant skill does not document consultantMode auto"
fi
if grep -Fq "fallback approved by user" "$SKILLS_DIR/consultant/SKILL.md"; then
  fail "consultant skill does not reserve consultant fallback deviations"
else
  pass "consultant skill does not reserve consultant fallback deviations"
fi
if grep -Fq "consultantMode: auto" "$SKILLS_DIR/second-opinion/SKILL.md"; then
  fail "second-opinion skill does not expose consultantMode auto"
else
  pass "second-opinion skill does not expose consultantMode auto"
fi
if grep -Fq "allowed: external | auto | internal | disabled" "$SKILLS_DIR/init-project/SKILL.md"; then
  fail "init-project skill restricts consultantMode to external/internal/disabled"
else
  pass "init-project skill restricts consultantMode to external/internal/disabled"
fi
if grep -Fq "allowed: external | auto | internal | disabled" "$SKILLS_DIR/lead/external-dispatch.md"; then
  fail "external-dispatch schema restricts consultantMode to external/internal/disabled"
else
  pass "external-dispatch schema restricts consultantMode to external/internal/disabled"
fi
if grep -Fq "fallback approved by user" "$SKILLS_DIR/lead/external-dispatch.md"; then
  fail "external-dispatch does not record consultant fallback approvals"
else
  pass "external-dispatch does not record consultant fallback approvals"
fi
if grep -Fq 'Read and normalize `.agents/.agents-mode` before trusting its flags.' "$SKILLS_DIR/lead/subagent-contracts.md"; then
  pass "subagent-contracts require read-time agents-mode normalization"
else
  fail "subagent-contracts require read-time agents-mode normalization"
fi
if grep -Fq "normalize it to the current canonical format before presenting or trusting the current values." "$SKILLS_DIR/init-project/SKILL.md"; then
  pass "init-project normalizes existing agents-mode before reading values"
else
  fail "init-project normalizes existing agents-mode before reading values"
fi
if grep -Fq 'Any read of `.agents/.agents-mode` that drives a decision should normalize the file to the current canonical format before trusting the flags.' "$SKILLS_DIR/init-project/SKILL.md"; then
  pass "init-project requires read-time agents-mode normalization"
else
  fail "init-project requires read-time agents-mode normalization"
fi
if grep -Fq 'read and normalize `.agents/.agents-mode` first.' "$SKILLS_DIR/second-opinion/SKILL.md"; then
  pass "second-opinion normalizes agents-mode before reporting status"
else
  fail "second-opinion normalizes agents-mode before reporting status"
fi
if grep -Fq 'Adapter host runtime' "$AGENTS_FILE"; then
  fail "shared governance no longer allows adapter-host metadata for external execution"
else
  pass "shared governance no longer allows adapter-host metadata for external execution"
fi
if grep -Fq 'must use direct external launch' "$AGENTS_FILE"; then
  pass "shared governance requires direct external launch"
else
  fail "shared governance requires direct external launch"
fi
if grep -Fq 'Adapter host runtime:' "$SKILLS_DIR/lead/external-dispatch.md"; then
  fail "external-dispatch no longer records adapter host runtime"
else
  pass "external-dispatch no longer records adapter host runtime"
fi
if grep -Fq 'must use direct external launch' "$SKILLS_DIR/lead/external-dispatch.md"; then
  pass "external-dispatch requires direct external launch"
else
  fail "external-dispatch requires direct external launch"
fi
if grep -Fq 'Adapter host runtime:' "$SKILLS_DIR/consultant/SKILL.md"; then
  fail "consultant no longer records adapter host runtime"
else
  pass "consultant no longer records adapter host runtime"
fi
if grep -Fq 'must use direct external launch' "$SKILLS_DIR/consultant/SKILL.md"; then
  pass "consultant requires direct external launch when external"
else
  fail "consultant requires direct external launch when external"
fi
if grep -Fq 'Adapter host runtime:' "$SKILLS_DIR/external-worker/SKILL.md"; then
  fail "external-worker no longer records adapter host runtime"
else
  pass "external-worker no longer records adapter host runtime"
fi
if grep -Fq 'direct external launch contract' "$SKILLS_DIR/external-worker/SKILL.md"; then
  pass "external-worker requires direct external launch"
else
  fail "external-worker requires direct external launch"
fi
if grep -Fq 'Adapter host runtime:' "$SKILLS_DIR/external-reviewer/SKILL.md"; then
  fail "external-reviewer no longer records adapter host runtime"
else
  pass "external-reviewer no longer records adapter host runtime"
fi
if grep -Fq 'direct external launch contract' "$SKILLS_DIR/external-reviewer/SKILL.md"; then
  pass "external-reviewer requires direct external launch"
else
  fail "external-reviewer requires direct external launch"
fi
if grep -Fq 'Actual execution path:** <external CLI (provider name) | internal subagent' "$SKILLS_DIR/consultant/SKILL.md"; then
  fail "consultant does not mislabel internal subagent as actual execution path"
else
  pass "consultant does not mislabel internal subagent as actual execution path"
fi

if [[ $DEV_REPO -eq 1 ]]; then
  if grep -Fq "## Canonical maintenance" "$DOCS_DIR/agents-mode-reference.md"; then
    pass "agents-mode reference defines canonical maintenance"
  else
    fail "agents-mode reference defines canonical maintenance"
  fi
  if grep -Fq "Read-time normalization preserves the effective values of known keys" "$DOCS_DIR/agents-mode-reference.md"; then
    pass "agents-mode reference documents read-time normalization semantics"
  else
    fail "agents-mode reference documents read-time normalization semantics"
  fi
  if grep -Fq ".codex/agents/default.toml" "INSTALL.md"; then
    pass "INSTALL.md documents Codex built-in agent override seeding"
  else
    fail "INSTALL.md documents Codex built-in agent override seeding"
  fi
  if grep -Fq "~/.codex/agents/" "docs/provider-runtime-layout.md"; then
    pass "provider runtime layout documents global Codex built-in agent overrides"
  else
    fail "provider runtime layout documents global Codex built-in agent overrides"
  fi
  if grep -Fq "agents/default.toml" "src.codex/README.md"; then
    pass "src.codex/README.md documents the built-in agent override payload"
  else
    fail "src.codex/README.md documents the built-in agent override payload"
  fi
fi

if [[ -n "$CODEX_RUNTIME_ROOT" ]]; then
  echo ""
  echo "=== Codex built-in agent overrides ==="
  if [[ -f "$CODEX_RUNTIME_ROOT/agents/default.toml" ]]; then
    pass "agents/default.toml installed"
  else
    fail "agents/default.toml installed"
  fi
  if [[ -f "$CODEX_RUNTIME_ROOT/agents/worker.toml" ]]; then
    pass "agents/worker.toml installed"
  else
    fail "agents/worker.toml installed"
  fi
  if [[ -f "$CODEX_RUNTIME_ROOT/agents/explorer.toml" ]]; then
    pass "agents/explorer.toml installed"
  else
    fail "agents/explorer.toml installed"
  fi
fi

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

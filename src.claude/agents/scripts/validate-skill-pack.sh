#!/usr/bin/env bash
# Validate Claude Code pack structural integrity.
# Run from repo root: bash src.claude/agents/scripts/validate-skill-pack.sh
#   or after install:  bash .claude/agents/scripts/validate-skill-pack.sh
set -euo pipefail

# Auto-detect pack root: src.claude/ (dev repo) or .claude/ (installed)
DEV_REPO=0
if [[ -d "src.claude/agents" ]]; then
  PACK="src.claude"
  AGENTS_FILE="shared/AGENTS.shared.md"
  REPO_ROOT="$(pwd -P)"
  DEV_REPO=1
elif [[ -d ".claude/agents" ]]; then
  PACK=".claude"
  if [[ -f "$PACK/AGENTS.md" ]]; then
    AGENTS_FILE="$PACK/AGENTS.md"
  else
    AGENTS_FILE="$PACK/AGENTS.shared.md"
  fi
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

check_pointer() {
  local file="$1"
  local target="$2"
  if [[ ! -f "$file" ]]; then
    fail "$file missing"
  elif grep -Fq "$target" "$file"; then
    pass "$file points to $target"
  else
    fail "$file missing canonical shared link $target"
  fi
}

check_contains() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if [[ ! -f "$file" ]]; then
    fail "$label (file missing: $file)"
  elif grep -Fq -- "$pattern" "$file"; then
    pass "$label"
  else
    fail "$label"
  fi
}

check_absent() {
  local file="$1"
  local pattern="$2"
  local label="$3"
  if [[ ! -f "$file" ]]; then
    fail "$label (file missing: $file)"
  elif grep -Fq -- "$pattern" "$file"; then
    fail "$label"
  else
    pass "$label"
  fi
}

check_file() {
  local file="$1"
  local label="$2"
  if [[ -f "$file" ]]; then
    pass "$label"
  else
    fail "$label"
  fi
}

check_not_exists() {
  local path="$1"
  local label="$2"
  if [[ ! -e "$path" ]]; then
    pass "$label"
  else
    fail "$label"
  fi
}

check_max_lines() {
  local file="$1"
  local max_lines="$2"
  local label="$3"
  if [[ ! -f "$file" ]]; then
    fail "$label (file missing: $file)"
    return
  fi

  local actual_lines
  actual_lines="$(wc -l < "$file")"
  if [[ "$actual_lines" -le "$max_lines" ]]; then
    pass "$label ($actual_lines <= $max_lines)"
  else
    fail "$label ($actual_lines > $max_lines)"
  fi
}

check_exact_h2_inventory() {
  local file="$1"
  local label="$2"
  shift 2
  local expected=("$@")
  local actual=()

  if [[ ! -f "$file" ]]; then
    fail "$label (file missing: $file)"
    return
  fi

  mapfile -t actual < <(grep '^## ' "$file" || true)

  if [[ ${#actual[@]} -ne ${#expected[@]} ]]; then
    fail "$label"
    return
  fi

  local idx
  for idx in "${!expected[@]}"; do
    if [[ "${actual[$idx]}" != "${expected[$idx]}" ]]; then
      fail "$label"
      return
    fi
  done

  pass "$label"
}

extract_h2_section() {
  local file="$1"
  local heading="$2"
  awk -v heading="$heading" '
    $0 == heading { in_section=1; print; next }
    in_section && /^## / { exit }
    in_section { print }
  ' "$file"
}

check_h2_section_contains() {
  local file="$1"
  local heading="$2"
  local pattern="$3"
  local label="$4"
  local section_text

  if [[ ! -f "$file" ]]; then
    fail "$label (file missing: $file)"
    return
  fi

  section_text="$(extract_h2_section "$file" "$heading")"
  if [[ -z "$section_text" ]]; then
    fail "$label (missing section: $heading)"
  elif grep -Fq "$pattern" <<<"$section_text"; then
    pass "$label"
  else
    fail "$label"
  fi
}

check_h2_section_absent() {
  local file="$1"
  local heading="$2"
  local pattern="$3"
  local label="$4"
  local section_text

  if [[ ! -f "$file" ]]; then
    fail "$label (file missing: $file)"
    return
  fi

  section_text="$(extract_h2_section "$file" "$heading")"
  if [[ -z "$section_text" ]]; then
    fail "$label (missing section: $heading)"
  elif grep -Fq "$pattern" <<<"$section_text"; then
    fail "$label"
  else
    pass "$label"
  fi
}

normalized_sha256() {
  local file="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sed 's/\r$//' "$file" | sha256sum | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    sed 's/\r$//' "$file" | shasum -a 256 | awk '{print $1}'
  elif command -v python3 >/dev/null 2>&1; then
    python3 - "$file" <<'PY'
import hashlib, pathlib, sys
path = pathlib.Path(sys.argv[1])
data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
print(hashlib.sha256(data).hexdigest())
PY
  elif command -v python >/dev/null 2>&1; then
    python - "$file" <<'PY'
import hashlib, pathlib, sys
path = pathlib.Path(sys.argv[1])
data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
print(hashlib.sha256(data).hexdigest())
PY
  else
    return 1
  fi
}

check_normalized_sha256() {
  local file="$1"
  local expected="$2"
  local label="$3"
  local actual

  if [[ ! -f "$file" ]]; then
    fail "$label (file missing: $file)"
    return
  fi

  if ! actual="$(normalized_sha256 "$file")"; then
    fail "$label (no SHA-256 tool available)"
    return
  fi

  if [[ "$actual" == "$expected" ]]; then
    pass "$label"
  else
    fail "$label"
  fi
}

echo "=== Claude Code pack validation ==="
echo ""

# 1. Core files exist
echo "[Core files]"
for f in "$PACK/CLAUDE.md" "$AGENTS_FILE" "$PACK/agents/lead.md" "$PACK/agents/consultant.md" \
         "$PACK/agents/external-worker.md" "$PACK/agents/external-reviewer.md" \
         "$PACK/agents/scripts/invoke-claude-api.sh" "$PACK/agents/scripts/invoke-claude-api.ps1" \
         $PACK/agents/contracts/operating-model.md \
         $PACK/agents/contracts/external-dispatch.md \
         $PACK/agents/contracts/subagent-contracts.md \
         $PACK/agents/contracts/policies-catalog.md \
         $PACK/commands/agents-external-brigade.md \
         $PACK/commands/agents-second-opinion.md; do
  if [[ -f "$f" ]]; then pass "$f exists"; else fail "$f missing"; fi
done
echo ""

if [[ $DEV_REPO -eq 1 ]]; then
  SHARED_REF_DIR="$REPO_ROOT/shared/references"
  CLAUDE_REF_DIR="$REPO_ROOT/references-claude"

  echo "[Shared references]"
  for f in \
    "$SHARED_REF_DIR/README.md" \
    "$SHARED_REF_DIR/evidence-based-answer-pipeline.md" \
    "$SHARED_REF_DIR/subagent-operating-model.md" \
    "$SHARED_REF_DIR/workflow-strategy-comparison.md" \
    "$SHARED_REF_DIR/repository-publication-safety.md" \
    "$SHARED_REF_DIR/ru/subagent-operating-model.md" \
    "$SHARED_REF_DIR/ru/workflow-strategy-comparison.md" \
    "$SHARED_REF_DIR/ru/repository-publication-safety.md"; do
    if [[ -f "$f" ]]; then pass "$f exists"; else fail "$f missing"; fi
  done
  echo ""

  echo "[Claude compatibility pointers]"
  check_pointer "$CLAUDE_REF_DIR/evidence-based-answer-pipeline.md" "../shared/references/evidence-based-answer-pipeline.md"
  check_pointer "$CLAUDE_REF_DIR/subagent-operating-model.md" "../shared/references/subagent-operating-model.md"
  check_pointer "$CLAUDE_REF_DIR/workflow-strategy-comparison.md" "../shared/references/workflow-strategy-comparison.md"
  check_pointer "$CLAUDE_REF_DIR/repository-publication-safety.md" "../shared/references/repository-publication-safety.md"
  check_pointer "$CLAUDE_REF_DIR/ru/subagent-operating-model.md" "../../shared/references/ru/subagent-operating-model.md"
  check_pointer "$CLAUDE_REF_DIR/ru/workflow-strategy-comparison.md" "../../shared/references/ru/workflow-strategy-comparison.md"
  check_pointer "$CLAUDE_REF_DIR/ru/repository-publication-safety.md" "../../shared/references/ru/repository-publication-safety.md"

  echo ""
  echo "[Shared core / addendum semantics]"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "This file is the canonical shared core for the repository's subagent operating model." \
    "shared subagent-operating-model declares canonical shared-core ownership"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "Keep runtime-specific paths, provider dispatch details, execution-model differences, and repository concretization in the corresponding pack-local addendum." \
    "shared subagent-operating-model keeps runtime specifics in pack-local addenda"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "pack-local addenda may extend it with provider-specific fields" \
    "shared subagent-operating-model allows provider-specific addendum fields"
  check_absent "$SHARED_REF_DIR/subagent-operating-model.md" ".agents/.agents-mode.yaml" \
    "shared subagent-operating-model stays free of Codex-specific agents-mode paths"
  check_absent "$SHARED_REF_DIR/subagent-operating-model.md" ".claude/.agents-mode.yaml" \
    "shared subagent-operating-model stays free of Claude-specific agents-mode paths"
  check_absent "$SHARED_REF_DIR/subagent-operating-model.md" "work-items/index.md" \
    "shared subagent-operating-model stays free of Claude task-memory concretization"
  check_absent "$SHARED_REF_DIR/subagent-operating-model.md" "externalClaudeProfile" \
    "shared subagent-operating-model stays free of provider-specific profile fields"
  check_absent "$SHARED_REF_DIR/subagent-operating-model.md" "Claude CLI" \
    "shared subagent-operating-model stays free of provider-specific dispatch destinations"
  check_absent "$SHARED_REF_DIR/subagent-operating-model.md" "Codex CLI" \
    "shared subagent-operating-model stays free of provider-specific dispatch origins"
  check_absent "$SHARED_REF_DIR/subagent-operating-model.md" "## Codex-specific runtime notes" \
    "shared subagent-operating-model stays free of Codex addendum sections"
  check_absent "$SHARED_REF_DIR/subagent-operating-model.md" "## Claude-specific runtime notes" \
    "shared subagent-operating-model stays free of Claude addendum sections"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" "## 1. Main rule for the lead" \
    "shared subagent-operating-model keeps the main-rule section in the shared core"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" "## 6. Role map" \
    "shared subagent-operating-model keeps the role-map section in the shared core"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" "## 8. Gates: what each stage must prove" \
    "shared subagent-operating-model keeps the gate model in the shared core"
  check_h2_section_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "## 3.10 Periodic controls" \
    'Use the corresponding pack-local `periodic-control-matrix.md` named in the local addendum as the canonical cadence, owner, evidence, and fail-action matrix.' \
    "shared periodic-controls section routes ownership back through the pack-local addendum"
  check_h2_section_absent "$SHARED_REF_DIR/subagent-operating-model.md" \
    "## 3.10 Periodic controls" \
    "[periodic-control-matrix.md](periodic-control-matrix.md)" \
    "shared periodic-controls section does not keep a broken shared periodic-control link"
  check_exact_h2_inventory "$SHARED_REF_DIR/subagent-operating-model.md" \
    "shared subagent-operating-model keeps the canonical shared-core H2 skeleton" \
    "## 1. Main rule for the lead" \
    "## 2. What this means in practice" \
    "## 3. Team operating model" \
    "## 3.10 Periodic controls" \
    "## 4. Standard task template for any subagent" \
    "## 5. Shared system preamble for all subagents" \
    "## 6. Role map" \
    "## 7. Ready-made role prompts" \
    "## 8. Gates: what each stage must prove" \
    "## 9. Practical routing patterns" \
    "## 10. Rules for parallel work" \
    "## 11. Governance notes" \
    "## 12. Team composition" \
    "## 13. Short memo for the lead" \
    "## 14. Final wording to give the lead"

  check_h2_section_contains "$CLAUDE_REF_DIR/subagent-operating-model.md" \
    "## Claude-specific runtime notes" \
    'Consultant config lives in `.claude/.agents-mode.yaml`' \
    "Claude runtime-notes section documents the Claude agents-mode path"
  check_h2_section_contains "$CLAUDE_REF_DIR/subagent-operating-model.md" \
    "## Claude-specific runtime notes" \
    'does not include `externalClaudeProfile`' \
    "Claude runtime-notes section documents that externalClaudeProfile is not canonical on the Claude line"
  check_h2_section_contains "$CLAUDE_REF_DIR/subagent-operating-model.md" \
    "## Claude-specific runtime notes" \
    "resolves by lane type through the active named priority profile" \
    "Claude runtime-notes section documents profile-based Claude external dispatch"
  check_h2_section_contains "$CLAUDE_REF_DIR/subagent-operating-model.md" \
    "## Claude-side repository concretization" \
    '`work-items/index.md`' \
    "Claude repository-concretization section keeps the Claude task-memory recovery entry point"
  check_h2_section_absent "$CLAUDE_REF_DIR/subagent-operating-model.md" \
    "## Claude-specific runtime notes" \
    ".agents/.agents-mode.yaml" \
    "Claude runtime-notes section does not accidentally carry Codex agents-mode paths"
  check_contains "$CLAUDE_REF_DIR/subagent-operating-model.md" "## Claude-specific runtime notes" \
    "Claude addendum keeps the Claude runtime-notes section"
  check_contains "$CLAUDE_REF_DIR/subagent-operating-model.md" "## Claude-side repository concretization" \
    "Claude addendum keeps the Claude repository-concretization section"
  check_contains "$CLAUDE_REF_DIR/subagent-operating-model.md" "## Shared core now owns" \
    "Claude addendum keeps the shared-core ownership handoff section"
  check_h2_section_contains "$CLAUDE_REF_DIR/subagent-operating-model.md" \
    "## Claude-side repository concretization" \
    "[periodic-control-matrix.md](periodic-control-matrix.md)" \
    "Claude repository-concretization section keeps the pack-local periodic-control reference"
  check_h2_section_contains "$CLAUDE_REF_DIR/subagent-operating-model.md" \
    "## Shared core now owns" \
    "Main rule, core management rules, delivery loops, routing patterns, role map, prompts, gates, and team composition" \
    "Claude shared-core handoff section states which methodology stays in the shared core"
  check_exact_h2_inventory "$CLAUDE_REF_DIR/subagent-operating-model.md" \
    "Claude addendum keeps the exact addendum-only H2 skeleton" \
    "## Claude-specific runtime notes" \
    "## Claude-side repository concretization" \
    "## Shared core now owns"
  check_absent "$CLAUDE_REF_DIR/subagent-operating-model.md" "## 1. Main rule for the lead" \
    "Claude addendum does not reintroduce the shared main-rule section"
  check_absent "$CLAUDE_REF_DIR/subagent-operating-model.md" "## 6. Role map" \
    "Claude addendum does not reintroduce the shared role-map section"
  check_absent "$CLAUDE_REF_DIR/subagent-operating-model.md" "## 8. Gates: what each stage must prove" \
    "Claude addendum does not reintroduce the shared gate section"
  check_absent "$CLAUDE_REF_DIR/subagent-operating-model.md" "## 9. Practical routing patterns" \
    "Claude addendum does not reintroduce the shared routing-patterns section"
  check_absent "$CLAUDE_REF_DIR/subagent-operating-model.md" "## 12. Team composition" \
    "Claude addendum does not reintroduce the shared team-composition section"
  check_max_lines "$CLAUDE_REF_DIR/subagent-operating-model.md" 120 \
    "Claude addendum stays bounded instead of regrowing into a full blueprint copy"
  check_normalized_sha256 "$SHARED_REF_DIR/subagent-operating-model.md" \
    "e9a5579b13061a8514fb60b47031bea2eedddd0117833b0be94162416f06727c" \
    "shared subagent-operating-model matches the current canonical normalized fingerprint"
  check_normalized_sha256 "$CLAUDE_REF_DIR/subagent-operating-model.md" \
    "380fb2bf3279607743f03b35f78391a0a9a2d0e9b4bc1605a3617e6b220f81fd" \
    "Claude addendum matches the current canonical normalized fingerprint"
  echo ""
fi

# 2. Role index vs actual agent files
echo "[Role index consistency]"
if [[ -f "$AGENTS_FILE" ]]; then
  # Extract role names from AGENTS.md (shared governance, lines with $role-name pattern)
  roles=$(grep -oE '\$[a-z][-a-z]*' "$AGENTS_FILE" | sed 's/^\$//' | sort -u)
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
  if grep -q "## $section" "$AGENTS_FILE"; then
    pass "## $section present in AGENTS.md"
  else
    fail "## $section missing from AGENTS.md"
  fi
done
echo ""

# 6c. Consultant no-fallback canon
echo "[Consultant no-fallback canon]"
check_absent "$PACK/agents/consultant.md" "consultantMode: auto" \
  "consultant doc does not document consultantMode auto"
check_absent "$PACK/agents/consultant.md" "fallback approved by user" \
  "consultant doc does not reserve consultant fallback deviations"
check_absent "$PACK/commands/agents-second-opinion.md" "consultantMode: auto" \
  "agents-second-opinion command does not expose consultantMode auto"
check_absent "$PACK/commands/agents-init-project.md" "allowed: external | auto | internal | disabled" \
  "agents-init-project restricts consultantMode to external/internal/disabled"
check_absent "$PACK/agents/contracts/external-dispatch.md" "allowed: external | auto | internal | disabled" \
  "external-dispatch schema restricts consultantMode to external/internal/disabled"
check_absent "$PACK/agents/contracts/external-dispatch.md" "fallback approved by user" \
  "external-dispatch does not record consultant fallback approvals"
check_contains "$PACK/agents/contracts/subagent-contracts.md" "Read and normalize \`.claude/.agents-mode.yaml\` first." \
  "subagent-contracts require read-time agents-mode normalization"
check_contains "$PACK/commands/agents-init-project.md" "normalize it to the current canonical format before presenting or trusting the current values." \
  "agents-init-project normalizes existing agents-mode before reading values"
check_contains "$PACK/commands/agents-init-project.md" "Any read of \`.claude/.agents-mode.yaml\` that drives a decision should normalize the file to the current canonical format before trusting the flags." \
  "agents-init-project requires read-time agents-mode normalization"
check_contains "$PACK/commands/agents-second-opinion.md" "read and normalize \`.claude/.agents-mode.yaml\`." \
  "agents-second-opinion normalizes agents-mode before reporting status"
check_absent "$AGENTS_FILE" "Adapter host runtime" \
  "shared governance no longer allows adapter-host metadata for external execution"
check_contains "$AGENTS_FILE" "must use direct external launch" \
  "shared governance requires direct external launch"
check_contains "$PACK/agents/external-worker.md" "Read and normalize \`.claude/.agents-mode.yaml\` to the current canonical format before trusting its flags." \
  "external-worker normalizes agents-mode before routing"
check_contains "$PACK/agents/external-reviewer.md" "Read and normalize \`.claude/.agents-mode.yaml\` to the current canonical format before trusting its flags." \
  "external-reviewer normalizes agents-mode before routing"
check_absent "$PACK/agents/contracts/external-dispatch.md" "Adapter host runtime:" \
  "external-dispatch no longer records adapter host runtime"
check_contains "$PACK/agents/contracts/external-dispatch.md" "must use direct external launch" \
  "external-dispatch requires direct external launch"
check_absent "$PACK/agents/consultant.md" "Adapter host runtime:" \
  "consultant no longer records adapter host runtime"
check_contains "$PACK/agents/consultant.md" "must use direct external launch" \
  "consultant requires direct external launch when external"
check_absent "$PACK/agents/consultant.md" "Requested provider: <auto" \
  "consultant provenance no longer emits auto as a requested provider"
check_absent "$PACK/agents/contracts/external-dispatch.md" "Requested provider: <auto" \
  "external-dispatch provenance no longer emits auto as a requested provider"
check_absent "$PACK/agents/consultant.md" "Actual execution path:** <external CLI (provider name) | internal subagent" \
  "consultant does not mislabel internal subagent as actual execution path"
check_contains "$PACK/agents/external-worker.md" "externalPriorityProfile" \
  "external-worker honors structured profile keys"
check_contains "$PACK/agents/external-reviewer.md" "externalPriorityProfile" \
  "external-reviewer honors structured profile keys"
check_contains "$PACK/agents/external-worker.md" "direct external launch contract" \
  "external-worker requires direct external launch"
check_contains "$PACK/agents/external-reviewer.md" "direct external launch contract" \
  "external-reviewer requires direct external launch"
check_contains "$PACK/agents/scripts/invoke-claude-api.sh" "SECRET.md" \
  "Claude API wrapper reads SECRET.md"
check_contains "$PACK/agents/scripts/invoke-claude-api.sh" 'exec "$CLAUDE_CMD"' \
  "Claude secret-backed wrapper invokes plain claude"
check_contains "$PACK/agents/scripts/invoke-claude-api.ps1" "SECRET.md" \
  "PowerShell Claude API wrapper reads SECRET.md"
check_contains "$PACK/agents/scripts/invoke-claude-api.ps1" '& $commandInfo.Source' \
  "PowerShell Claude secret-backed wrapper invokes plain claude"
check_absent "$PACK/agents/scripts/invoke-claude-api.ps1" "-AsHashtable" \
  "PowerShell Claude API wrapper avoids ConvertFrom-Json -AsHashtable"
check_contains "$PACK/agents/scripts/invoke-claude-api.ps1" "--print-secret-path" \
  "PowerShell Claude API wrapper supports POSIX-style print-secret-path"
check_contains "$PACK/agents/scripts/invoke-claude-api.sh" "CLAUDE_BIN" \
  "Bash Claude secret-backed wrapper documents CLAUDE_BIN override"
check_contains "$PACK/agents/scripts/invoke-claude-api.sh" "claude.cmd" \
  "Bash Claude secret-backed wrapper resolves Windows claude.cmd"
check_contains "$PACK/agents/contracts/external-dispatch.md" "one instance per helper or provider" \
  "external-dispatch documents same-provider brigade reuse"
check_contains "$PACK/commands/agents-external-brigade.md" "same-provider helper instances" \
  "agents-external-brigade command documents same-provider helper fan-out"
check_contains "$PACK/commands/agents-help.md" "/agents-external-brigade" \
  "agents-help lists the external-brigade command"
check_contains "$PACK/agents/lead.md" "/agents-external-brigade" \
  "lead guide mentions the external-brigade command"

if [[ $DEV_REPO -eq 1 ]]; then
  check_contains "$REPO_ROOT/docs/agents-mode-reference.md" "## Canonical maintenance" \
    "agents-mode reference defines canonical maintenance"
  check_contains "$REPO_ROOT/docs/agents-mode-reference.md" "Read-time normalization preserves the effective values of known keys" \
    "agents-mode reference documents read-time normalization semantics"
  check_file "$REPO_ROOT/shared/agents-mode.defaults.yaml" "shared/agents-mode.defaults.yaml"
  check_not_exists "$REPO_ROOT/src.claude/agents-mode.defaults.yaml" \
    "src.claude/agents-mode.defaults.yaml removed from the monorepo"
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

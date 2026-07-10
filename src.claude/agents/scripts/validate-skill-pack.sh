#!/usr/bin/env bash
# Validate Claude Code pack structural integrity.
# Run from repo root: bash src.claude/agents/scripts/validate-skill-pack.sh
#   or after install:  bash .claude/agents/scripts/validate-skill-pack.sh
set -euo pipefail

# Auto-detect pack root: src.claude/ (dev repo) or .claude/ (installed)
SCRIPT_DIR_LOGICAL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DEV_REPO=0
STANDALONE=0
SOURCE_SCRIPTS_DIR=""
if [[ -d "src.claude/agents/scripts" ]]; then
  SOURCE_SCRIPTS_DIR="$(cd "src.claude/agents/scripts" && pwd -P)"
fi
if [[ -n "$SOURCE_SCRIPTS_DIR" && "$SCRIPT_DIR" == "$SOURCE_SCRIPTS_DIR" && -d "src.claude/agents" ]]; then
  PACK="src.claude"
  AGENTS_FILE="shared/AGENTS.shared.md"
  REPO_ROOT="$(pwd -P)"
  DEV_REPO=1
  # A single-provider STANDALONE branch carries ONLY its own src.claude/ tree, so the
  # monorepo-wide surfaces (root install.sh/.ps1, RELEASE_NOTES.md, docs/external-worker-design.md,
  # the cross-provider README/INSTALL work-item sections, the all-provider agents-mode contract)
  # are absent. Detect it by the ABSENCE of the sibling production pack src.codex (a positive
  # structural signal the full monorepo always carries) rather than by a monorepo-only file's
  # absence, so renaming or moving a root doc can never silently flip the monorepo itself to
  # standalone and skip the cross-provider checks. Pack-content checks run in both modes.
  [[ -d "src.codex" ]] || STANDALONE=1
elif [[ -d ".claude/agents" ]]; then
  PACK=".claude"
  if [[ -f "$PACK/AGENTS.md" ]]; then
    AGENTS_FILE="$PACK/AGENTS.md"
  else
    AGENTS_FILE="$PACK/AGENTS.shared.md"
  fi
elif [[ -d "$SCRIPT_DIR_LOGICAL/.." && -f "$SCRIPT_DIR_LOGICAL/../lead.md" && -f "$SCRIPT_DIR_LOGICAL/../../AGENTS.md" ]]; then
  PACK="$(cd "$SCRIPT_DIR_LOGICAL/../.." && pwd)"
  AGENTS_FILE="$PACK/AGENTS.md"
elif [[ -d "$SCRIPT_DIR/.." && -f "$SCRIPT_DIR/../lead.md" && -f "$SCRIPT_DIR/../../AGENTS.md" ]]; then
  PACK="$(cd "$SCRIPT_DIR/../.." && pwd -P)"
  AGENTS_FILE="$PACK/AGENTS.md"
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

check_agent_run_ledger_contract() {
  local label="$1"
  if [[ $DEV_REPO -ne 1 ]]; then
    warn "$label (dev repo validator unavailable in installed layout)"
    return
  fi

  local python_cmd=""
  if command -v python3 >/dev/null 2>&1; then
    python_cmd="python3"
  elif command -v python >/dev/null 2>&1; then
    python_cmd="python"
  else
    warn "$label (python unavailable)"
    return
  fi

  local output
  if output="$("$python_cmd" "$REPO_ROOT/scripts/check-agent-run-ledger-contract.py" --root "$REPO_ROOT" 2>&1)"; then
    pass "$label"
  else
    printf '%s\n' "$output"
    fail "$label"
  fi
}

check_arch_layering_slices() {
  local label="$1"
  if [[ $DEV_REPO -ne 1 ]]; then
    warn "$label (dev repo validator unavailable in installed layout)"
    return
  fi

  local python_cmd=""
  if command -v python3 >/dev/null 2>&1; then
    python_cmd="python3"
  elif command -v python >/dev/null 2>&1; then
    python_cmd="python"
  else
    warn "$label (python unavailable)"
    return
  fi

  local output
  if output="$("$python_cmd" "$REPO_ROOT/scripts/validate-arch-layering-slices.py" "$REPO_ROOT" 2>&1)"; then
    pass "$label"
  else
    printf '%s\n' "$output"
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

check_normalizer_strips_example_auto_providers() {
  local label="$1"
  if [[ $DEV_REPO -ne 1 ]]; then
    warn "$label (dev repo normalizer unavailable in installed layout)"
    return
  fi

  local python_cmd=""
  if command -v python3 >/dev/null 2>&1; then
    python_cmd="python3"
  elif command -v python >/dev/null 2>&1; then
    python_cmd="python"
  else
    warn "$label (python unavailable)"
    return
  fi

  local tmpdir target
  tmpdir="$(mktemp -d)"
  target="$tmpdir/.agents-mode.yaml"
  cat > "$target" <<'EOF'
externalProvider: auto
externalClaudeApiMode: force
externalPriorityProfile: custom-demo
reserveResolver: wrapper:tools/reserve-review.ps1
externalPriorityProfiles:
  custom-demo:
    advisory.repo-understanding: [claude, codex, reserve, gemini, qwen]
    advisory.design-adr: [claude-secret, codex, claude]
    advisory.legacy-secret-only: [claude-secret]
    review.security: [reserve, claude, codex]
    review.ui-visual-correctness: [claude, codex, reserve, gemini]
    design.ui-ux-structure: [reserve, codex, gemini, claude, qwen]
    worker.default-implementation: [reserve, claude, gemini, qwen, codex]
    worker.ui-structural-modernization: [codex, claude]
    review.visual: [claude, codex, reserve]
    worker.secret-only: [reserve, gemini, qwen]
externalOpinionCounts:
  review.visual: 2
EOF

  if "$python_cmd" "$REPO_ROOT/scripts/normalize-agents-mode.py" \
    --template "$REPO_ROOT/shared/agents-mode.defaults.yaml" \
    --target "$target" \
    --provider shared >/dev/null 2>&1 &&
    grep -Fq "  custom-demo:" "$target" &&
    grep -Fq "    advisory.repo-understanding: [claude, codex, reserve]" "$target" &&
    grep -Fq "    advisory.design-adr: [codex, claude, reserve]" "$target" &&
    grep -Fq "    advisory.legacy-secret-only: [reserve]" "$target" &&
    grep -Fq "    review.security: [claude, codex, reserve]" "$target" &&
    grep -Fq "    review.ui-visual-correctness: [claude, codex, reserve]" "$target" &&
    grep -Fq "    design.ui-ux-structure: [codex, claude]" "$target" &&
    grep -Fq "    worker.default-implementation: [claude, codex]" "$target" &&
    grep -Fq "reserveResolver: wrapper:tools/reserve-review.ps1" "$target" &&
    ! grep -Fq "externalClaudeApiMode" "$target" &&
    ! grep -Fq "worker.secret-only" "$target" &&
    ! grep -Fq "worker.ui-structural-modernization" "$target" &&
    ! grep -Fq "review.visual" "$target" &&
    ! grep -E '^[[:space:]]{4}.*: \[[^]]*(gemini|qwen)' "$target" >/dev/null &&
    ! grep -E '^[[:space:]]{4}(design|worker)\.[^:]+: \[[^]]*reserve' "$target" >/dev/null; then
    :
  else
    fail "$label"
    rm -rf "$tmpdir"
    return
  fi

  target="$tmpdir/.agents-mode-disabled.yaml"
  cat > "$target" <<'EOF'
externalProvider: auto
reserveResolver: disabled
EOF

  if "$python_cmd" "$REPO_ROOT/scripts/normalize-agents-mode.py" \
    --template "$REPO_ROOT/shared/agents-mode.defaults.yaml" \
    --target "$target" \
    --provider shared >/dev/null 2>&1 &&
    grep -Fq "reserveResolver: disabled" "$target" &&
    grep -Fq "    advisory.repo-understanding: [claude, codex]" "$target" &&
    grep -Fq "    review.ui-visual-correctness: [codex, claude]" "$target" &&
    ! grep -E '^[[:space:]]{4}.*: \[[^]]*reserve' "$target" >/dev/null; then
    :
  else
    fail "$label"
    rm -rf "$tmpdir"
    return
  fi

  target="$tmpdir/.agents-mode-legacy-disabled.yaml"
  cat > "$target" <<'EOF'
externalProvider: auto
externalClaudeApiMode: disabled
EOF

  if "$python_cmd" "$REPO_ROOT/scripts/normalize-agents-mode.py" \
    --template "$REPO_ROOT/shared/agents-mode.defaults.yaml" \
    --target "$target" \
    --provider shared >/dev/null 2>&1 &&
    grep -Fq "reserveResolver: disabled" "$target" &&
    grep -Fq "    advisory.repo-understanding: [claude, codex]" "$target" &&
    grep -Fq "    review.ui-visual-correctness: [codex, claude]" "$target" &&
    ! grep -E '^[[:space:]]{4}.*: \[[^]]*reserve' "$target" >/dev/null &&
    ! grep -Fq "externalClaudeApiMode" "$target"; then
    pass "$label"
  else
    fail "$label"
  fi
  rm -rf "$tmpdir"
}

check_shared_defaults_reserve_policy() {
  local label="$1"
  if [[ $DEV_REPO -ne 1 ]]; then
    warn "$label (dev repo defaults unavailable in installed layout)"
    return
  fi

  local defaults="$REPO_ROOT/shared/agents-mode.defaults.yaml"
  if [[ ! -f "$defaults" ]]; then
    fail "$label (shared defaults missing)"
    return
  fi

  if grep -Fq "externalClaudeApiMode" "$defaults"; then
    fail "$label (retired externalClaudeApiMode should not be in shared defaults)"
    return
  fi
  if ! grep -Fq "reserveResolver: claude-sonnet" "$defaults"; then
    fail "$label (shared defaults should define reserveResolver default)"
    return
  fi

  local lane expected
  for lane in advisory.repo-understanding advisory.design-adr review.pre-pr review.security review.performance-architecture review.ui-visual-correctness; do
    expected="    $lane: [claude, codex, reserve]"
    case "$lane" in
      review.performance-architecture|review.ui-visual-correctness)
        expected="    $lane: [codex, claude, reserve]"
        ;;
    esac
    if ! grep -Fq "$expected" "$defaults"; then
      fail "$label ($lane missing reserve as last advisory/review candidate)"
      return
    fi
  done

  if grep -E '^[[:space:]]{4}(design|worker)\.[^:]+: \[[^]]*(reserve|gemini|qwen)' "$defaults" >/dev/null; then
    fail "$label (design/worker lane contains forbidden provider)"
    return
  fi
  if grep -E '^[[:space:]]{4}(advisory|design|review|worker)\.[^:]+: \[[^]]*(gemini|qwen)' "$defaults" >/dev/null; then
    fail "$label (Gemini/Qwen appear in shipped production profile)"
    return
  fi
  pass "$label"
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
for f in "$PACK/CLAUDE.md" "$AGENTS_FILE" "$PACK/agents/lead.md" "$PACK/skills/lead/SKILL.md" "$PACK/agents/consultant.md" \
         "$PACK/agents/external-worker.md" "$PACK/agents/external-reviewer.md" \
         "$PACK/agents/scripts/invoke-claude-api.sh" "$PACK/agents/scripts/invoke-claude-api.ps1" \
         $PACK/agents/contracts/operating-model.md \
         $PACK/agents/contracts/external-dispatch.md \
         $PACK/agents/contracts/subagent-contracts.md \
         $PACK/agents/contracts/policies-catalog.md \
         $PACK/agents/contracts/review-loop.md \
         $PACK/agents/contracts/design-panel.md \
         $PACK/commands/agents-external-brigade.md \
         $PACK/commands/agents-second-opinion.md \
         $PACK/commands/agents-review-loop.md \
         $PACK/commands/agents-design-panel.md; do
  if [[ -f "$f" ]]; then pass "$f exists"; else fail "$f missing"; fi
done
echo ""

# 1c. Design-panel invariant markers (mechanical structure only; independence/synthesis
#     soundness stays review territory per the design-panel methodology's validator/review boundary)
echo "[Design-panel]"
for dp_id in DP1 DP2 DP3 DP4 DP5 DP6 DP7 DP8; do
  check_contains "$PACK/agents/contracts/design-panel.md" "$dp_id" \
    "design-panel contract carries invariant marker $dp_id"
done
check_contains "$PACK/agents/contracts/design-panel.md" "INPUT_ONLY" \
  "design-panel contract carries the INPUT_ONLY candidate disposition marker"
check_contains "$PACK/agents/contracts/design-panel.md" "RETURN(lead)" \
  "design-panel contract carries the RETURN(lead) ledger-gate marker"
check_contains "$PACK/agents/contracts/design-panel.md" "synthesis" \
  "design-panel contract names the synthesis step"
check_contains "$PACK/agents/contracts/design-panel.md" "N >= 2" \
  "design-panel contract carries the N >= 2 quorum marker"
check_contains "$PACK/commands/agents-design-panel.md" "design-panel.md" \
  "agents-design-panel command points at the installed contract"
check_contains "$PACK/CLAUDE.md" "agents-design-panel.md" \
  "CLAUDE.md dispatch index exposes the design-panel command"
check_contains "$PACK/commands/agents-help.md" "/agents-design-panel" \
  "agents-help lists the design-panel command"
check_contains "$PACK/agents/contracts/operating-model.md" "Design-panel and review-loop selection" \
  "operating-model carries the design-panel/review-loop selection block"
check_h2_section_contains "$PACK/agents/contracts/operating-model.md" \
  "## Design-panel and review-loop selection" \
  "agents/contracts/design-panel.md" \
  "operating-model design-panel selection block names the installed binding path"
check_h2_section_contains "$PACK/agents/contracts/operating-model.md" \
  "## Design-panel and review-loop selection" \
  "independence at **generation**" \
  "operating-model design-panel selection block states the generation side of the distinction"
check_h2_section_contains "$PACK/agents/contracts/operating-model.md" \
  "## Design-panel and review-loop selection" \
  "independence at **verification**" \
  "operating-model design-panel selection block states the verification side of the distinction"
echo ""

# 1b. Lead skill is the live Lead contract held BY the main conversation
#     (agents/lead.md above stays the fail-closed dispatch stub; the /agents-external-brigade
#     anchor on it is checked further down). The real contract must never be deletable with
#     validation still green, and it must not be a forked subagent.
echo "[Lead identity]"
check_contains "$PACK/skills/lead/SKILL.md" "hold the Lead role AS the main conversation" \
  "lead skill declares the Lead role is held AS the main conversation"
check_absent "$PACK/skills/lead/SKILL.md" "context: fork" \
  "lead skill is not dispatched as a forked subagent (no context: fork)"
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
    "$REPO_ROOT/shared/schemas/agent-runs.schema.json" \
    "$REPO_ROOT/scripts/check-agent-run-ledger-contract.py" \
    "$REPO_ROOT/scripts/agent-run-ledger.py" \
    "$REPO_ROOT/scripts/agent-run-ledger.sh" \
    "$REPO_ROOT/scripts/agent-run-ledger.ps1" \
    "$REPO_ROOT/scripts/check-work-items-state.py" \
    "$REPO_ROOT/scripts/check-work-items-state.sh" \
    "$REPO_ROOT/scripts/check-work-items-state.ps1" \
    "$REPO_ROOT/scripts/validate-work-item-state.py" \
    "$REPO_ROOT/scripts/validate-work-item-state.sh" \
    "$REPO_ROOT/scripts/validate-work-item-state.ps1" \
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
    "and any pack-local provider-specific fields" \
    "shared subagent-operating-model allows provider-specific addendum fields"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    'A subagent `PASS`, report, or claimed test result is a claim, not proof' \
    "shared subagent-operating-model requires subagent result verification"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "Visual artifact verification amendment" \
    "shared subagent-operating-model requires visual artifact inspection"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "Documentation terminology amendment" \
    "shared subagent-operating-model documents terminology glossary discipline"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "Markdown formula rendering amendment" \
    "shared subagent-operating-model documents Markdown formula rendering discipline"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "split long derivations into several short one-line" \
    "shared subagent-operating-model preserves fragile previewer formula fallback"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    'do not use multi-line `$$...$$` display blocks' \
    "shared subagent-operating-model rejects unverified multi-line display math"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    'compatibility hacks such as `\sb` or `\sp`' \
    "shared subagent-operating-model forbids formula compatibility hacks"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "unbalanced dollar delimiters" \
    "shared subagent-operating-model scans for delimiter and table breakage"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "Formula scope and assumptions amendment" \
    "shared subagent-operating-model documents formula scope discipline"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "tool availability" \
    "shared subagent-operating-model preserves canonical-source ambiguity inspection"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "smallest safe reversible subset" \
    "shared subagent-operating-model preserves user-intent fallback discipline"
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
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    'agent-runs.jsonl` is the machine-readable execution ledger' \
    "shared subagent-operating-model documents the agent execution ledger"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    'no accepted `PASS` without evidence' \
    "shared subagent-operating-model rejects PASS without evidence"
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
    "## 14. Final wording to give the lead" \
    "## Terms and Abbreviations"

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
    "shipped production \`auto\` uses \`codex | claude\` only" \
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
  # Fingerprint regenerated when the canonical shared doc changes; the hash below
  # intentionally tracks shared/references/subagent-operating-model.md after its
  # normalized line-ending transform, not a provider-local addendum.
  check_normalized_sha256 "$SHARED_REF_DIR/subagent-operating-model.md" \
    "a79853274a07948974f49fe188c6b348f28f2fc427f2e5b35b117120256516b9" \
    "shared subagent-operating-model matches the current canonical normalized fingerprint"
  check_normalized_sha256 "$CLAUDE_REF_DIR/subagent-operating-model.md" \
    "f3b58ded2c928e4ad138e3ff966c75480b2f869c56c02bba8aafb4cbfe622cf6" \
    "Claude addendum matches the current canonical normalized fingerprint"
  echo ""
fi

# 2. Role index vs actual agent files
echo "[Role index consistency]"
if [[ -f "$AGENTS_FILE" ]]; then
  # Extract role names only from the "## Role index" section (stop at next "## " heading)
  roles=$(awk '/^## Role index/{flag=1; next} /^## /{flag=0} flag' "$AGENTS_FILE" | grep -oE '\$[a-z][a-z-]{2,}' | sed 's/^\$//' | sort -u)
  # Extract common-skill names only from the "## Common skills" section
  common_skills=$(awk '/^## Common skills/{flag=1; next} /^## /{flag=0} flag' "$AGENTS_FILE" | grep -oE '\$[a-z][a-z-]{2,}' | sed 's/^\$//' | sort -u)
  for role in $roles; do
    if [[ -f "$PACK/agents/${role}.md" ]]; then
      pass "$role has agent file"
    else
      fail "$role in role index but $PACK/agents/${role}.md missing"
    fi
  done
  for skill in $common_skills; do
    if [[ -f "$PACK/skills/${skill}/SKILL.md" ]]; then
      pass "$skill common skill has skill file"
    else
      fail "$skill in Common skills but $PACK/skills/${skill}/SKILL.md missing"
    fi
  done

  # Check for orphaned agent files
  for f in $PACK/agents/*.md; do
    name=$(basename "$f" .md)
    if [[ "$name" == "external-worker" || "$name" == "external-reviewer" ]]; then
      pass "$name is an expected external adapter file"
    elif echo "$common_skills" | grep -qx "$name"; then
      pass "$name is a delegate-style common-skill wrapper"
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
  case "$name" in
    agents-*) pass "/$name has the agents- prefix" ;;
    *) fail "/$name command lacks the agents- prefix (key invariant)" ;;
  esac
done
# SKILL.md frontmatter: fence + name matches dir + non-empty description
for sd in $PACK/skills/*/; do
  [[ -f "$sd/SKILL.md" ]] || continue
  sname=$(basename "$sd")
  first=$(head -1 "$sd/SKILL.md")
  fm_name=$(awk '/^---$/{n++; next} n==1 && /^name:/{sub(/^name:[ ]*/,""); print; exit}' "$sd/SKILL.md")
  fm_desc=$(awk '/^---$/{n++; next} n==1 && /^description:/{sub(/^description:[ ]*/,""); print; exit}' "$sd/SKILL.md")
  if [[ "$first" != "---" ]]; then
    fail "skills/$sname/SKILL.md does not start with a frontmatter fence"
  elif [[ "$fm_name" != "$sname" ]]; then
    fail "skills/$sname/SKILL.md frontmatter name '$fm_name' != directory '$sname'"
  elif [[ -z "$fm_desc" ]]; then
    fail "skills/$sname/SKILL.md has an empty frontmatter description"
  else
    pass "skills/$sname frontmatter valid (fence + name + description)"
  fi
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
check_contains "$PACK/agents/contracts/subagent-contracts.md" "agent-runs.jsonl format" \
  "subagent-contracts define the agent run ledger format"
check_contains "$PACK/agents/contracts/subagent-contracts.md" 'A `PASS` in `status.md` is not accepted' \
  "subagent-contracts reject PASS without ledger evidence"
check_contains "$PACK/agents/contracts/subagent-contracts.md" "shared/schemas/agent-runs.schema.json" \
  "subagent-contracts point to the shared ledger schema"
check_contains "$PACK/agents/contracts/subagent-contracts.md" "scripts/agent-run-ledger.*" \
  "subagent-contracts point to the work-item ledger helper"
check_contains "$PACK/agents/contracts/subagent-contracts.md" "scripts/validate-work-item-state.* --work-item" \
  "subagent-contracts point to the work-item state validator"
check_contains "$PACK/agents/contracts/subagent-contracts.md" "scripts/check-work-items-state.* --root" \
  "subagent-contracts point to the periodic work-item state checker"

# --- orchestration-discipline-gaps normative-sentence pins ---
# Standalone provider branches run THIS validator, not tests/, so a mirror/regression
# here would go uncaught. Substrings mirror tests/test_orchestration_discipline_contract.py.
check_contains "$PACK/commands/agents-bugfix.md" \
  "**Second-cross-break stop:** If a second fix in the same session breaks a previously working neighbor, STOP all edits." \
  "agents-bugfix carries the P4 second-cross-break stop rule"
check_contains "$PACK/agents/hooks/check-no-trash-in-repo.py" \
  'REQUESTED_ISOLATION_MARKER = "# orchestrarium:requested-isolation-worktree"' \
  "no-trash-in-repo hook carries the A2 requested-isolation-worktree marker constant"
check_contains "$PACK/agents/contracts/review-loop.md" \
  "**Failed lane is unverified.** Any expected lane that errors, dies, or hits a time/token/usage limit is UNVERIFIED." \
  "review-loop contract carries the A5b failed-lane-is-unverified invariant"
check_contains "$PACK/agents/contracts/review-loop.md" \
  "**Fail-closed aggregation.** A missing/null sub-verdict or findings payload is NOT-clean." \
  "review-loop contract carries the A5b fail-closed-aggregation invariant"
check_contains "$PACK/agents/contracts/subagent-contracts.md" \
  "**Class-completeness trigger (mandatory):** when a reviewer, bot, or test cites one instance of a defect class" \
  "subagent-contracts carry the A8 class-completeness trigger"
check_contains "$PACK/agents/contracts/external-dispatch.md" \
  "Every provider-backed run MUST carry the resolved model/profile and effort as explicit launch flags in that invocation, even when they equal configured defaults; never rely on provider config defaults." \
  "external-dispatch carries the A12 explicit model/effort launch rule"
check_contains "$PACK/agents/contracts/operating-model.md" \
  "active-item state change (create, resume, stage transition, park, close, archive)" \
  "operating-model carries the A3 index-sync every-state-change trigger"

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
check_contains "$AGENTS_FILE" "substantive task prompt must use file-based prompt delivery" \
  "shared governance requires file-based external CLI prompts"
check_contains "$AGENTS_FILE" "Mechanism inventory before new paths" \
  "shared governance requires owner inventory before new mechanisms"
check_contains "$AGENTS_FILE" "State-synchronization ownership" \
  "shared governance requires state synchronization ownership discipline"
check_contains "$AGENTS_FILE" "split-brain state sync as an architecture bug" \
  "shared governance rejects split-brain state synchronization"
check_contains "$AGENTS_FILE" "correlation IDs" \
  "shared governance requires traceable state synchronization diagnostics"
check_contains "$PACK/agents/external-worker.md" "Read and normalize \`.claude/.agents-mode.yaml\` to the current canonical format before trusting its flags." \
  "external-worker normalizes agents-mode before routing"
check_contains "$PACK/agents/external-reviewer.md" "Read and normalize \`.claude/.agents-mode.yaml\` to the current canonical format before trusting its flags." \
  "external-reviewer normalizes agents-mode before routing"
check_absent "$PACK/agents/contracts/external-dispatch.md" "Adapter host runtime:" \
  "external-dispatch no longer records adapter host runtime"
check_contains "$PACK/agents/contracts/external-dispatch.md" "must use direct external launch" \
  "external-dispatch requires direct external launch"
check_contains "$PACK/agents/contracts/external-dispatch.md" "substantive task prompt must use file-based prompt delivery" \
  "external-dispatch requires file-based external CLI prompts"
check_contains "$AGENTS_FILE" "verify every subagent result before accepting it" \
  "shared governance requires verification before trusting subagent results"
check_contains "$AGENTS_FILE" "Visual artifact verification discipline" \
  "shared governance requires visual inspection for generated visual artifacts"
check_contains "$AGENTS_FILE" "Plain-language and terminology discipline" \
  "shared governance requires terminology and abbreviation explanations in documents"
check_contains "$AGENTS_FILE" "Markdown formula rendering format" \
  "shared governance requires previewer-safe Markdown formula formatting"
check_contains "$AGENTS_FILE" "split long derivations into several short one-line" \
  "shared governance prefers one-line formulas for fragile previewers"
check_contains "$AGENTS_FILE" 'Do not use multi-line `$$...$$` display blocks' \
  "shared governance rejects unverified multi-line display math"
check_contains "$AGENTS_FILE" 'compatibility hacks such as `\sb` or `\sp`' \
  "shared governance forbids formula compatibility hacks"
check_contains "$AGENTS_FILE" "broken Markdown table pipe counts" \
  "shared governance scans formula edits for delimiter and table breakage"
check_contains "$AGENTS_FILE" "Formula scope and assumptions discipline" \
  "shared governance requires formula scope and assumption disclosure"
check_contains "$AGENTS_FILE" "concrete observable data" \
  "shared governance requires measured evidence before root-cause or fix claims"
check_contains "$AGENTS_FILE" "smallest safe reversible subset" \
  "shared governance preserves user-intent fallback discipline"
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
check_contains "$PACK/agents/external-worker.md" "file-based prompt delivery" \
  "external-worker requires file-based external CLI prompts"
check_contains "$PACK/agents/external-reviewer.md" "direct external launch contract" \
  "external-reviewer requires direct external launch"
check_contains "$PACK/agents/external-reviewer.md" "file-based prompt delivery" \
  "external-reviewer requires file-based external CLI prompts"
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

echo ""
echo "=== Production auto provider canon ==="

claude_phase_b_files=(
  "$PACK/CLAUDE.md"
  "$PACK/agents/contracts/external-dispatch.md"
  "$PACK/agents/contracts/operating-model.md"
  "$PACK/agents/contracts/subagent-contracts.md"
  "$PACK/agents/consultant.md"
  "$PACK/agents/external-worker.md"
  "$PACK/agents/external-reviewer.md"
  "$PACK/agents/graphics-engineer.md"
  "$PACK/agents/visualization-engineer.md"
  "$PACK/commands/agents-help.md"
  "$PACK/commands/agents-init-project.md"
  "$PACK/commands/agents-second-opinion.md"
  "$PACK/commands/agents-external-brigade.md"
)

for file in "${claude_phase_b_files[@]}"; do
  check_absent "$file" "gemini-crosscheck" \
    "$file removes retired gemini-crosscheck profile"
  check_absent "$file" "externalGeminiFallbackMode" \
    "$file removes retired externalGeminiFallbackMode"
  check_absent "$file" "externalGeminiWorkdirMode" \
    "$file removes retired externalGeminiWorkdirMode"
done

check_contains "$PACK/CLAUDE.md" "auto | codex | claude | gemini | qwen" \
  "Claude pack docs document the example-only Gemini/Qwen provider universe"
check_contains "$PACK/CLAUDE.md" 'Gemini and Qwen are `WEAK MODEL / NOT RECOMMENDED`' \
  "Claude entrypoint marks Gemini/Qwen as not recommended example routes"
check_contains "$PACK/CLAUDE.md" 'never a provider entry inside `externalPriorityProfiles`' \
  "Claude entrypoint forbids Gemini/Qwen profile entries"
check_contains "$PACK/agents/consultant.md" 'Gemini and Qwen stay explicit `WEAK MODEL / NOT RECOMMENDED` example-only paths' \
  "Claude consultant marks Gemini/Qwen as not recommended example routes"
check_contains "$PACK/agents/external-worker.md" 'manual `WEAK MODEL / NOT RECOMMENDED` example-only paths' \
  "Claude external-worker marks Gemini/Qwen as not recommended example routes"
check_contains "$PACK/agents/external-reviewer.md" 'manual `WEAK MODEL / NOT RECOMMENDED` example-only paths' \
  "Claude external-reviewer marks Gemini/Qwen as not recommended example routes"
check_contains "$PACK/agents/external-worker.md" 'instead of broadening shipped or repo-local `auto` profiles' \
  "Claude external-worker forbids example-provider profile broadening"
check_contains "$PACK/agents/external-reviewer.md" 'instead of broadening shipped or repo-local `auto` profiles' \
  "Claude external-reviewer forbids example-provider profile broadening"
check_contains "$PACK/agents/contracts/operating-model.md" 'Gemini and Qwen stay explicit `WEAK MODEL / NOT RECOMMENDED` example-only paths' \
  "Claude operating-model marks Gemini/Qwen as not recommended example routes"

if [[ $DEV_REPO -eq 1 ]]; then
  check_contains "$REPO_ROOT/shared/references/README.md" "current Gemini and Qwen example integrations" \
    "shared reference index treats Gemini/Qwen as current example integrations"
  if [[ $STANDALONE -eq 0 ]]; then
    # Root multi-provider installer (install.sh/.ps1) and its README/INSTALL dispatch
    # docs exist only in the monorepo; a single-provider standalone branch omits them.
  check_contains "$REPO_ROOT/install.sh" "default production install" \
    "root bash installer defaults to the Codex/Claude production pair"
  check_contains "$REPO_ROOT/install.ps1" "default production install" \
    "root PowerShell installer defaults to the Codex/Claude production pair"
  check_absent "$REPO_ROOT/install.sh" "All available root installs" \
    "root bash installer does not offer all-provider default installs"
  check_absent "$REPO_ROOT/install.ps1" "All available root installs" \
    "root PowerShell installer does not offer all-provider default installs"
  check_contains "$REPO_ROOT/install.sh" "if [[ -z \"\$choice\" ]]; then" \
    "root bash installer maps empty selection to the default"
  check_contains "$REPO_ROOT/install.sh" "choice=3" \
    "root bash installer maps default selection to option 3"
  check_contains "$REPO_ROOT/install.ps1" '$normalizedChoice = "3"' \
    "root PowerShell installer maps empty selection to option 3"
  check_contains "$REPO_ROOT/install.sh" "run_installer install-codex.sh" \
    "root bash installer option 3 includes Codex"
  check_contains "$REPO_ROOT/install.sh" "run_installer install-claude.sh" \
    "root bash installer option 3 includes Claude"
  check_contains "$REPO_ROOT/install.ps1" 'Invoke-ChildInstaller -ScriptName "install-codex.ps1"' \
    "root PowerShell installer option 3 includes Codex"
  check_contains "$REPO_ROOT/install.ps1" 'Invoke-ChildInstaller -ScriptName "install-claude.ps1"' \
    "root PowerShell installer option 3 includes Claude"
  bash_default_block="$(awk '/^  3\)/,/^  4\)/ { print }' "$REPO_ROOT/install.sh")"
  if grep -Fq "run_installer install-codex.sh" <<<"$bash_default_block" &&
     grep -Fq "run_installer install-claude.sh" <<<"$bash_default_block" &&
     ! grep -Eq 'install-(gemini|qwen)\.sh' <<<"$bash_default_block"; then
    pass "root bash installer default dispatch is Codex plus Claude only"
  else
    fail "root bash installer default dispatch must be Codex plus Claude only"
  fi
  ps_default_block="$(awk '/^    "3" {/,/^    "4" {/ { print }' "$REPO_ROOT/install.ps1")"
  if grep -Fq 'Invoke-ChildInstaller -ScriptName "install-codex.ps1"' <<<"$ps_default_block" &&
     grep -Fq 'Invoke-ChildInstaller -ScriptName "install-claude.ps1"' <<<"$ps_default_block" &&
     ! grep -Eq 'install-(gemini|qwen)\.ps1' <<<"$ps_default_block"; then
    pass "root PowerShell installer default dispatch is Codex plus Claude only"
  else
    fail "root PowerShell installer default dispatch must be Codex plus Claude only"
  fi
  check_absent "$REPO_ROOT/install.sh" "run_all_available" \
    "root bash installer has no aggregate all-provider helper"
  check_absent "$REPO_ROOT/install.ps1" "Invoke-AllAvailableInstallers" \
    "root PowerShell installer has no aggregate all-provider helper"
  fi
  check_contains "$REPO_ROOT/README.md" "Pressing Enter selects the default production install" \
    "README documents the Codex/Claude default root install"
  check_contains "$REPO_ROOT/INSTALL.md" "Pressing Enter selects the default production install" \
    "INSTALL.md documents the Codex/Claude default root install"
  check_contains "$REPO_ROOT/INSTALL.md" ".agents-mode.yaml" \
    "INSTALL.md default project result includes provider overlay files"
  check_contains "$REPO_ROOT/docs/agents-mode-reference.md" '`power-mode` | hardest-task maximum result' \
    "agents-mode reference documents power-mode preset"
  check_contains "$REPO_ROOT/src.claude/commands/agents-init-project.md" '`power-mode` (hardest-task maximum result)' \
    "Claude init-project exposes power-mode preset"
  for lane in review.security review.ui-visual-correctness; do
    check_contains "$REPO_ROOT/src.claude/commands/agents-init-project.md" "$lane: 2" \
      "Claude init-project correctness-first/power-mode presets raise $lane"
  done
  if command -v python3 >/dev/null 2>&1; then
    contract_python_cmd="python3"
  elif command -v python >/dev/null 2>&1; then
    contract_python_cmd="python"
  else
    contract_python_cmd=""
  fi
  if [[ $STANDALONE -eq 0 ]]; then
    # The agents-mode machine-readable contract cross-checks EVERY provider's init-project
    # surface (it reads src.codex/, src.gemini/, src.qwen/ init-project files); a single-provider
    # standalone tree carries only its own pack, so the cross-provider checker cannot run there.
    if [[ -n "$contract_python_cmd" ]] &&
       "$contract_python_cmd" "$REPO_ROOT/scripts/validate-agents-mode-contract.py" --root "$REPO_ROOT" >/dev/null; then
      pass "agents-mode machine-readable contract matches docs and init preset surfaces"
    else
      fail "agents-mode machine-readable contract matches docs and init preset surfaces"
    fi
  fi
  check_contains "$REPO_ROOT/docs/agents-mode-reference.md" "## Canonical maintenance" \
    "agents-mode reference defines canonical maintenance"
  check_contains "$REPO_ROOT/docs/agents-mode-reference.md" "Read-time normalization preserves the effective values of known keys" \
    "agents-mode reference documents read-time normalization semantics"
  check_contains "$REPO_ROOT/docs/agents-mode-reference.md" 'removes example-only providers from every `externalPriorityProfiles` provider list' \
    "agents-mode reference documents profile provider sanitization"
  check_contains "$REPO_ROOT/docs/agents-mode-reference.md" "Substantive task prompts are file-based by default" \
    "agents-mode reference documents file-based external CLI prompts"
  check_contains "$REPO_ROOT/docs/agents-mode-reference.md" "agent-runs.jsonl" \
    "agents-mode reference documents ledger fan-out tracking"
  if [[ $STANDALONE -eq 0 ]]; then
    # docs/external-worker-design.md is a cross-provider design doc the standalone branch omits.
    check_contains "$REPO_ROOT/docs/external-worker-design.md" "Work-item ledger rule" \
      "external-worker design maps execution records to the ledger"
  fi
  check_normalizer_strips_example_auto_providers \
    "agents-mode normalizer strips Gemini/Qwen and keeps reserve last or absent in custom auto profiles"
  check_file "$REPO_ROOT/shared/agents-mode.defaults.yaml" "shared/agents-mode.defaults.yaml"
  check_shared_defaults_reserve_policy \
    "shared agents-mode defaults keep reserve advisory/review-only"
  check_not_exists "$REPO_ROOT/src.claude/agents-mode.defaults.yaml" \
    "src.claude/agents-mode.defaults.yaml removed from the monorepo"
  if [[ $STANDALONE -eq 0 ]]; then
    # The cross-provider README/INSTALL work-item sections and RELEASE_NOTES.md exist only in
    # the monorepo; the standalone branch curates these surfaces away and ships no RELEASE_NOTES.md.
  check_contains "$REPO_ROOT/README.md" "scripts/validate-work-item-state.* --work-item" \
    "README documents the work-item state validator"
  check_contains "$REPO_ROOT/README.md" "scripts/agent-run-ledger.* --work-item" \
    "README documents the work-item ledger helper"
  check_contains "$REPO_ROOT/README.md" "scripts/check-work-items-state.* --root" \
    "README documents the periodic work-item state checker"
  check_contains "$REPO_ROOT/INSTALL.md" "agent-runs.jsonl" \
    "INSTALL documents local work-item execution tracking"
  check_contains "$REPO_ROOT/INSTALL.md" "scripts/agent-run-ledger.* --work-item" \
    "INSTALL documents the work-item ledger helper"
  check_contains "$REPO_ROOT/INSTALL.md" "scripts/check-work-items-state.* --root" \
    "INSTALL documents the periodic work-item state checker"
  check_contains "$REPO_ROOT/RELEASE_NOTES.md" "machine-readable work-item execution tracking contract" \
    "release notes document the work-item execution tracking contract"
  check_contains "$REPO_ROOT/RELEASE_NOTES.md" "ledger append/init helper" \
    "release notes document the ledger append/init helper"
  check_contains "$REPO_ROOT/RELEASE_NOTES.md" "periodic active work-item state checker" \
    "release notes document the periodic work-item checker"
  fi
  check_contains "$REPO_ROOT/scripts/agent-run-ledger.py" "validate_work_item" \
    "agent-run-ledger helper reuses the work-item state validator"
  check_contains "$REPO_ROOT/scripts/agent-run-ledger.py" "restore_ledger" \
    "agent-run-ledger helper rolls back invalid appends"
  check_contains "$REPO_ROOT/scripts/agent-run-ledger.sh" "agent-run-ledger.py" \
    "agent-run-ledger Bash wrapper targets the Python helper"
  check_contains "$REPO_ROOT/scripts/agent-run-ledger.ps1" "agent-run-ledger.py" \
    "agent-run-ledger PowerShell wrapper targets the Python helper"
  check_contains "$REPO_ROOT/scripts/check-work-items-state.py" "validate_work_item" \
    "periodic work-item checker reuses the work-item state validator"
  check_contains "$REPO_ROOT/scripts/check-work-items-state.py" "stale running agent" \
    "periodic work-item checker reports stale running agents"
  check_contains "$REPO_ROOT/scripts/check-work-items-state.sh" "check-work-items-state.py" \
    "periodic work-item Bash wrapper targets the Python checker"
  check_contains "$REPO_ROOT/scripts/check-work-items-state.ps1" "check-work-items-state.py" \
    "periodic work-item PowerShell wrapper targets the Python checker"
  check_contains "$REPO_ROOT/scripts/validate-work-item-state.py" "PASS gate requires evidence" \
    "work-item state validator enforces evidence for PASS"
  check_contains "$REPO_ROOT/scripts/validate-work-item-state.py" "escapes the work item" \
    "work-item state validator confines PASS artifacts to the work item"
  check_contains "$REPO_ROOT/scripts/validate-work-item-state.py" "agent-runs.jsonl" \
    "work-item state validator loads the agent run ledger"
  check_contains "$REPO_ROOT/scripts/validate-work-item-state.sh" "validate-work-item-state.py" \
    "work-item state Bash wrapper targets the Python validator"
  check_contains "$REPO_ROOT/scripts/validate-work-item-state.ps1" "validate-work-item-state.py" \
    "work-item state PowerShell wrapper targets the Python validator"
  check_contains "$REPO_ROOT/shared/schemas/agent-runs.schema.json" "agent-runs.schema.json" \
    "agent run ledger schema has a stable id"
  check_contains "$REPO_ROOT/shared/schemas/agent-runs.schema.json" '"executionRole"' \
    "agent run ledger schema defines executionRole"
  check_contains "$REPO_ROOT/shared/schemas/agent-runs.schema.json" '"evidence"' \
    "agent run ledger schema defines evidence"
  check_agent_run_ledger_contract \
    "agent run ledger schema and validator reject schema-invalid events"
  check_arch_layering_slices \
    "architecture-layering slices consistent across roles and claude/codex packs"
else
  echo ""
  echo "[Installed work-item runtime helper scripts]"
  for f in \
    "$PACK/agents/scripts/agent-run-ledger.py" \
    "$PACK/agents/scripts/agent-run-ledger.sh" \
    "$PACK/agents/scripts/agent-run-ledger.ps1" \
    "$PACK/agents/scripts/check-work-items-state.py" \
    "$PACK/agents/scripts/check-work-items-state.sh" \
    "$PACK/agents/scripts/check-work-items-state.ps1" \
    "$PACK/agents/scripts/validate-work-item-state.py" \
    "$PACK/agents/scripts/validate-work-item-state.sh" \
    "$PACK/agents/scripts/validate-work-item-state.ps1"; do
    check_file "$f" "$f installed"
  done
  check_contains "$PACK/agents/scripts/agent-run-ledger.py" "validate_work_item" \
    "installed agent-run-ledger helper reuses the validator"
  check_contains "$PACK/agents/scripts/check-work-items-state.py" "stale running agent" \
    "installed periodic work-item checker reports stale running agents"
  check_contains "$PACK/agents/scripts/validate-work-item-state.py" "PASS gate requires evidence" \
    "installed work-item state validator enforces evidence for PASS"
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

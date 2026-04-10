#!/usr/bin/env bash
set -euo pipefail

# Validate structural integrity of the Codex pack.
# Supported layouts:
#   bash src.codex/skills/lead/scripts/validate-skill-pack.sh   (dev repo)
#   bash .codex/skills/lead/scripts/validate-skill-pack.sh      (global install)
#   bash .agents/skills/lead/scripts/validate-skill-pack.sh     (repo-local install)

# Auto-detect layout.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DEV_REPO=0
if [[ -d "src.codex/skills" && -f "shared/AGENTS.shared.md" && -f "src.codex/AGENTS.codex.md" ]]; then
  # Dev repo: assemble AGENTS.md from split source files for validation
  SKILLS_DIR="$(cd "src.codex/skills" && pwd -P)"
  SCRIPTS_DIR="$(cd "src.codex/skills/lead/scripts" && pwd -P)"
  REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd -P)"
  DEV_REPO=1
  AGENTS_FILE="$(mktemp)"
  cat "shared/AGENTS.shared.md" "src.codex/AGENTS.codex.md" > "$AGENTS_FILE"
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
  elif grep -Fq "$pattern" "$file"; then
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
  elif grep -Fq "$pattern" "$file"; then
    fail "$label"
  else
    pass "$label"
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

if [[ $DEV_REPO -eq 1 ]]; then
  DOCS_DIR="$REPO_ROOT/docs"
  SHARED_REF_DIR="$REPO_ROOT/shared/references"
  CODEX_REF_DIR="$REPO_ROOT/references-codex"
  CLAUDE_REF_DIR="$REPO_ROOT/references-claude"
  GEMINI_REF_DIR="$REPO_ROOT/references-gemini"

  echo ""
  echo "=== Common branch-level surface ==="

  for f in \
    "$DOCS_DIR/README.md" \
    "$DOCS_DIR/agents-mode-reference.md" \
    "$DOCS_DIR/external-worker-design.md" \
    "$DOCS_DIR/provider-runtime-layouts.md" \
    "$CODEX_REF_DIR/README.md" \
    "$CLAUDE_REF_DIR/README.md" \
    "$GEMINI_REF_DIR/README.md"
  do
    if [[ -f "$f" ]]; then pass "$f"; else fail "$f missing"; fi
  done

  echo ""
  echo "=== Shared references ==="

  for f in \
    "$SHARED_REF_DIR/README.md" \
    "$SHARED_REF_DIR/evidence-based-answer-pipeline.md" \
    "$SHARED_REF_DIR/subagent-operating-model.md" \
    "$SHARED_REF_DIR/workflow-strategy-comparison.md" \
    "$SHARED_REF_DIR/repository-publication-safety.md" \
    "$SHARED_REF_DIR/ru/subagent-operating-model.md" \
    "$SHARED_REF_DIR/ru/workflow-strategy-comparison.md" \
    "$SHARED_REF_DIR/ru/repository-publication-safety.md"
  do
    if [[ -f "$f" ]]; then pass "$f"; else fail "$f missing"; fi
  done

  echo ""
  echo "=== Codex compatibility pointers ==="

  check_pointer "$CODEX_REF_DIR/evidence-based-answer-pipeline.md" "../shared/references/evidence-based-answer-pipeline.md"
  check_pointer "$CODEX_REF_DIR/subagent-operating-model.md" "../shared/references/subagent-operating-model.md"
  check_pointer "$CODEX_REF_DIR/workflow-strategy-comparison.md" "../shared/references/workflow-strategy-comparison.md"
  check_pointer "$CODEX_REF_DIR/repository-publication-safety.md" "../shared/references/repository-publication-safety.md"
  check_pointer "$CODEX_REF_DIR/ru/subagent-operating-model.md" "../../shared/references/ru/subagent-operating-model.md"
  check_pointer "$CODEX_REF_DIR/ru/workflow-strategy-comparison.md" "../../shared/references/ru/workflow-strategy-comparison.md"
  check_pointer "$CODEX_REF_DIR/ru/repository-publication-safety.md" "../../shared/references/ru/repository-publication-safety.md"
  check_pointer "$GEMINI_REF_DIR/evidence-based-answer-pipeline.md" "../shared/references/evidence-based-answer-pipeline.md"
  check_pointer "$GEMINI_REF_DIR/workflow-strategy-comparison.md" "../shared/references/workflow-strategy-comparison.md"
  check_pointer "$GEMINI_REF_DIR/repository-publication-safety.md" "../shared/references/repository-publication-safety.md"
  check_pointer "$GEMINI_REF_DIR/ru/workflow-strategy-comparison.md" "../../shared/references/ru/workflow-strategy-comparison.md"
  check_pointer "$GEMINI_REF_DIR/ru/repository-publication-safety.md" "../../shared/references/ru/repository-publication-safety.md"

  echo ""
  echo "=== Shared core / addendum semantics ==="

  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "This file is the canonical shared core for the repository's subagent operating model." \
    "shared subagent-operating-model declares canonical shared-core ownership"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "Keep runtime-specific paths, provider dispatch details, execution-model differences, and repository concretization in the corresponding pack-local addendum." \
    "shared subagent-operating-model keeps runtime specifics in pack-local addenda"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "pack-local addenda may extend it with provider-specific fields" \
    "shared subagent-operating-model allows provider-specific addendum fields"
  check_absent "$SHARED_REF_DIR/subagent-operating-model.md" ".agents/.agents-mode" \
    "shared subagent-operating-model stays free of Codex-specific agents-mode paths"
  check_absent "$SHARED_REF_DIR/subagent-operating-model.md" ".claude/.agents-mode" \
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

  check_h2_section_contains "$CODEX_REF_DIR/subagent-operating-model.md" \
    "## Codex-specific runtime notes" \
    'Consultant config lives in `.agents/.agents-mode`' \
    "Codex runtime-notes section documents the Codex agents-mode path"
  check_h2_section_contains "$CODEX_REF_DIR/subagent-operating-model.md" \
    "## Codex-specific runtime notes" \
    "externalClaudeProfile" \
    "Codex runtime-notes section documents the Codex-only externalClaudeProfile field"
  check_h2_section_contains "$CODEX_REF_DIR/subagent-operating-model.md" \
    "## Codex-specific runtime notes" \
    "Codex dispatch on Claude CLI" \
    "Codex runtime-notes section documents Codex-to-Claude external dispatch"
  check_h2_section_contains "$CODEX_REF_DIR/subagent-operating-model.md" \
    "## Codex-specific runtime notes" \
    "sequential skill invocation" \
    "Codex runtime-notes section keeps the sequential-execution runtime note"
  check_h2_section_absent "$CODEX_REF_DIR/subagent-operating-model.md" \
    "## Codex-specific runtime notes" \
    ".claude/.agents-mode" \
    "Codex runtime-notes section does not accidentally carry Claude agents-mode paths"
  check_contains "$CODEX_REF_DIR/subagent-operating-model.md" "## Codex-specific runtime notes" \
    "Codex addendum keeps the Codex runtime-notes section"
  check_contains "$GEMINI_REF_DIR/subagent-operating-model.md" "## Gemini-specific runtime notes" \
    "Gemini addendum keeps the Gemini runtime-notes section"
  check_h2_section_contains "$GEMINI_REF_DIR/subagent-operating-model.md" \
    "## Gemini-specific runtime notes" \
    ".gemini/.agents-mode" \
    "Gemini runtime-notes section documents the Gemini agents-mode overlay"
  check_h2_section_contains "$GEMINI_REF_DIR/subagent-operating-model.md" \
    "## Gemini-specific runtime notes" \
    ".gemini/settings.json" \
    "Gemini runtime-notes section documents the Gemini native runtime config surface"
  check_h2_section_contains "$GEMINI_REF_DIR/subagent-operating-model.md" \
    "## Gemini-specific runtime notes" \
    "sequential and human-steered" \
    "Gemini runtime-notes section keeps the sequential human-steered runtime note"
  check_contains "$CODEX_REF_DIR/subagent-operating-model.md" "## Codex-side repository concretization" \
    "Codex addendum keeps the Codex repository-concretization section"
  check_contains "$CODEX_REF_DIR/subagent-operating-model.md" "## Shared core now owns" \
    "Codex addendum keeps the shared-core ownership handoff section"
  check_h2_section_contains "$CODEX_REF_DIR/subagent-operating-model.md" \
    "## Codex-side repository concretization" \
    "[periodic-control-matrix.md](periodic-control-matrix.md)" \
    "Codex repository-concretization section keeps the pack-local periodic-control reference"
  check_h2_section_contains "$CODEX_REF_DIR/subagent-operating-model.md" \
    "## Shared core now owns" \
    "Main rule, core management rules, delivery loops, routing patterns, role map, prompts, gates, and team composition" \
    "Codex shared-core handoff section states which methodology stays in the shared core"
  check_exact_h2_inventory "$CODEX_REF_DIR/subagent-operating-model.md" \
    "Codex addendum keeps the exact addendum-only H2 skeleton" \
    "## Codex-specific runtime notes" \
    "## Codex-side repository concretization" \
    "## Shared core now owns"
  check_absent "$CODEX_REF_DIR/subagent-operating-model.md" "## 1. Main rule for the lead" \
    "Codex addendum does not reintroduce the shared main-rule section"
  check_absent "$CODEX_REF_DIR/subagent-operating-model.md" "## 6. Role map" \
    "Codex addendum does not reintroduce the shared role-map section"
  check_absent "$CODEX_REF_DIR/subagent-operating-model.md" "## 8. Gates: what each stage must prove" \
    "Codex addendum does not reintroduce the shared gate section"
  check_absent "$CODEX_REF_DIR/subagent-operating-model.md" "## 9. Practical routing patterns" \
    "Codex addendum does not reintroduce the shared routing-patterns section"
  check_absent "$CODEX_REF_DIR/subagent-operating-model.md" "## 12. Team composition" \
    "Codex addendum does not reintroduce the shared team-composition section"
  check_max_lines "$CODEX_REF_DIR/subagent-operating-model.md" 120 \
    "Codex addendum stays bounded instead of regrowing into a full blueprint copy"
  check_normalized_sha256 "$SHARED_REF_DIR/subagent-operating-model.md" \
    "1ac13e05cf1c258b6bd43ecc49328192106618d7806b95438ef6008804b56690" \
    "shared subagent-operating-model matches the current canonical normalized fingerprint"
  check_normalized_sha256 "$CODEX_REF_DIR/subagent-operating-model.md" \
    "feffe12f846d7e0b6a275b452cc43b90db8d1604836f6112cbc9acc3dfb23d0d" \
    "Codex addendum matches the current canonical normalized fingerprint"
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

UTILITY_SKILLS=(init-project second-opinion review-changes)

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

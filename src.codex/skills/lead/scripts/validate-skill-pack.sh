#!/usr/bin/env bash
set -euo pipefail

# Validate structural integrity of the Codex pack.
# Supported layouts:
#   bash src.codex/skills/lead/scripts/validate-skill-pack.sh   (dev repo)
#   bash .codex/skills/lead/scripts/validate-skill-pack.sh      (global install)
#   bash .agents/skills/lead/scripts/validate-skill-pack.sh     (repo-local install)

# Auto-detect layout.
SCRIPT_DIR_LOGICAL="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
DEV_REPO=0
CODEX_RUNTIME_ROOT=""
if [[ -d "src.codex/skills" && -f "shared/AGENTS.shared.md" && -f "src.codex/AGENTS.codex.md" ]]; then
  # Dev repo: assemble AGENTS.md from split source files for validation
  SKILLS_DIR="$(cd "src.codex/skills" && pwd -P)"
  SCRIPTS_DIR="$(cd "src.codex/skills/lead/scripts" && pwd -P)"
  REPO_ROOT="$(cd "$SCRIPT_DIR/../../../.." && pwd -P)"
  DEV_REPO=1
  AGENTS_FILE="$(mktemp)"
  cat "shared/AGENTS.shared.md" "src.codex/AGENTS.codex.md" > "$AGENTS_FILE"
  trap "rm -f '$AGENTS_FILE'" EXIT
elif [[ -d ".codex/skills" && -f ".codex/AGENTS.md" ]]; then
  SKILLS_DIR="$(cd ".codex/skills" && pwd -P)"
  SCRIPTS_DIR="$(cd ".codex/skills/lead/scripts" && pwd -P)"
  AGENTS_FILE="$(cd ".codex" && pwd)/AGENTS.md"
  CODEX_RUNTIME_ROOT="$(cd ".codex" && pwd)"
elif [[ -d ".agents/skills" && -f "AGENTS.md" ]]; then
  SKILLS_DIR="$(cd ".agents/skills" && pwd -P)"
  SCRIPTS_DIR="$(cd ".agents/skills/lead/scripts" && pwd -P)"
  AGENTS_FILE="$(cd "." && pwd)/AGENTS.md"
  CODEX_RUNTIME_ROOT="$(cd "." && pwd)/.codex"
elif [[ -d "$SCRIPT_DIR_LOGICAL/../.." && -f "$SCRIPT_DIR_LOGICAL/../SKILL.md" && -f "$SCRIPT_DIR_LOGICAL/../../../AGENTS.md" ]]; then
  SKILLS_DIR="$(cd "$SCRIPT_DIR_LOGICAL/../.." && pwd -P)"
  SCRIPTS_DIR="$SCRIPT_DIR"
  AGENTS_FILE="$(cd "$SCRIPT_DIR_LOGICAL/../../.." && pwd)/AGENTS.md"
  CODEX_RUNTIME_ROOT="$(cd "$SCRIPT_DIR_LOGICAL/../../.." && pwd)"
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
externalPriorityProfile: custom-demo
externalPriorityProfiles:
  custom-demo:
    advisory.repo-understanding: [claude, codex, claude-secret, gemini, qwen]
    review.visual: [claude, codex, claude-secret, gemini]
    worker.default-implementation: [claude-secret, claude, gemini, qwen, codex]
    worker.secret-only: [claude-secret, gemini, qwen]
externalOpinionCounts: {}
EOF

  if "$python_cmd" "$REPO_ROOT/scripts/normalize-agents-mode.py" \
    --template "$REPO_ROOT/shared/agents-mode.defaults.yaml" \
    --target "$target" \
    --provider shared >/dev/null 2>&1 &&
    grep -Fq "  custom-demo:" "$target" &&
    grep -Fq "    advisory.repo-understanding: [claude, codex, claude-secret]" "$target" &&
    grep -Fq "    review.visual: [claude, codex, claude-secret]" "$target" &&
    grep -Fq "    worker.default-implementation: [claude, codex]" "$target" &&
    ! grep -Fq "worker.secret-only" "$target" &&
    ! grep -E '^[[:space:]]{4}.*: \[[^]]*(gemini|qwen)' "$target" >/dev/null &&
    ! grep -E '^[[:space:]]{4}worker\.[^:]+: \[[^]]*claude-secret' "$target" >/dev/null; then
    pass "$label"
  else
    fail "$label"
  fi
  rm -rf "$tmpdir"
}

check_shared_defaults_claude_secret_policy() {
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

  local lane
  for lane in advisory.repo-understanding advisory.design-adr review.pre-pr review.performance-architecture review.visual; do
    if ! grep -Fq "    $lane: [claude, codex, claude-secret]" "$defaults"; then
      fail "$label ($lane missing claude-secret as last advisory/review candidate)"
      return
    fi
  done

  if grep -E '^[[:space:]]{4}worker\.[^:]+: \[[^]]*(claude-secret|gemini|qwen)' "$defaults" >/dev/null; then
    fail "$label (worker lane contains forbidden provider)"
    return
  fi
  if grep -E '^[[:space:]]{4}(advisory|review|worker)\.[^:]+: \[[^]]*(gemini|qwen)' "$defaults" >/dev/null; then
    fail "$label (Gemini/Qwen appear in shipped production profile)"
    return
  fi
  pass "$label"
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

check_skill_frontmatter_yaml() {
  local python_cmd=""
  if command -v python3 >/dev/null 2>&1; then
    python_cmd="python3"
  elif command -v python >/dev/null 2>&1; then
    python_cmd="python"
  else
    warn "Codex skill frontmatter is valid YAML (python unavailable)"
    return
  fi

  local skill_files=()
  local role
  local skill_file

  if [[ "$#" -gt 0 ]]; then
    for role in "$@"; do
      skill_file="$SKILLS_DIR/$role/SKILL.md"
      [[ -f "$skill_file" ]] && skill_files+=("$skill_file")
    done
  else
    for skill_file in "$SKILLS_DIR"/*/SKILL.md; do
      [[ -f "$skill_file" ]] && skill_files+=("$skill_file")
    done
  fi

  local output
  if output="$("$python_cmd" - "${skill_files[@]}" <<'PY'
import pathlib
import re
import sys

try:
    import yaml
except Exception:
    yaml = None

bad = []

def fallback_check(path, frontmatter):
    for offset, line in enumerate(frontmatter.splitlines(), 2):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(r"^[A-Za-z0-9_-]+:\s*(.*)$", line)
        if not match:
            return f"line {offset}: unsupported frontmatter line"
        value = match.group(1).split(" #", 1)[0].strip()
        if value and not value.startswith(("'", '"', "[", "{", "|", ">")) and re.search(r":(\s|$)", value):
            return f"line {offset}: unquoted colon in plain scalar"
    return None

for arg in sys.argv[1:]:
    path = pathlib.Path(arg)
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        bad.append(f"{path}: missing opening frontmatter fence")
        continue
    parts = text.split("---", 2)
    if len(parts) < 3:
        bad.append(f"{path}: missing closing frontmatter fence")
        continue
    frontmatter = parts[1]
    if yaml is not None:
        try:
            data = yaml.safe_load(frontmatter)
        except Exception as exc:
            bad.append(f"{path}: {exc}")
            continue
        if not isinstance(data, dict):
            bad.append(f"{path}: frontmatter root is not a mapping")
    else:
        fallback_error = fallback_check(path, frontmatter)
        if fallback_error:
            bad.append(f"{path}: {fallback_error}")

if bad:
    print("\n".join(bad))
    sys.exit(1)
PY
)"; then
    pass "Codex skill frontmatter is valid YAML"
  else
    fail "Codex skill frontmatter is valid YAML"
    if [[ -n "$output" ]]; then
      printf '%s\n' "$output" | sed 's/^/       /'
    fi
  fi
}

check_skill_description_budget() {
  local max_per_description="$1"
  local max_total_description="$2"
  shift 2
  local total_chars=0
  local offenders=()
  local multiline_descriptions=()
  local skill_file
  local role

  if [[ "$#" -gt 0 ]]; then
    for role in "$@"; do
      skill_file="$SKILLS_DIR/$role/SKILL.md"
      [[ -f "$skill_file" ]] || continue

      local description
      local description_chars

      description="$(grep -m 1 '^description:' "$skill_file" | sed 's/^description:[[:space:]]*//')"

      if [[ -z "$description" ]]; then
        offenders+=("$role=missing")
        continue
      fi

      if [[ "$description" == ">" || "$description" == "|" ]]; then
        multiline_descriptions+=("$role")
        continue
      fi

      description_chars="${#description}"
      total_chars=$((total_chars + description_chars))

      if [[ "$description_chars" -gt "$max_per_description" ]]; then
        offenders+=("$role=$description_chars")
      fi
    done
  else

    for skill_file in "$SKILLS_DIR"/*/SKILL.md; do
      [[ -f "$skill_file" ]] || continue

      local description
      local description_chars

      role="$(basename "$(dirname "$skill_file")")"
      description="$(grep -m 1 '^description:' "$skill_file" | sed 's/^description:[[:space:]]*//')"

      if [[ -z "$description" ]]; then
        offenders+=("$role=missing")
        continue
      fi

      if [[ "$description" == ">" || "$description" == "|" ]]; then
        multiline_descriptions+=("$role")
        continue
      fi

      description_chars="${#description}"
      total_chars=$((total_chars + description_chars))

      if [[ "$description_chars" -gt "$max_per_description" ]]; then
        offenders+=("$role=$description_chars")
      fi
    done
  fi

  if [[ ${#multiline_descriptions[@]} -gt 0 ]]; then
    fail "Codex skill descriptions are single-line metadata (${multiline_descriptions[*]})"
  else
    pass "Codex skill descriptions are single-line metadata"
  fi

  if [[ ${#offenders[@]} -gt 0 ]]; then
    fail "Codex skill descriptions stay <= $max_per_description chars (${offenders[*]})"
  else
    pass "Codex skill descriptions stay <= $max_per_description chars"
  fi

  if [[ "$total_chars" -le "$max_total_description" ]]; then
    pass "Codex skill description total stays <= $max_total_description chars ($total_chars)"
  else
    fail "Codex skill description total stays <= $max_total_description chars ($total_chars)"
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
  "$SKILLS_DIR/external-brigade/SKILL.md" \
  "$SKILLS_DIR/external-brigade/agents/openai.yaml" \
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
  QWEN_REF_DIR="$REPO_ROOT/references-qwen"

  echo ""
  echo "=== Common branch-level surface ==="

  for f in \
    "$REPO_ROOT/src.codex/agents/default.toml" \
    "$REPO_ROOT/src.codex/agents/worker.toml" \
    "$REPO_ROOT/src.codex/agents/explorer.toml" \
    "$REPO_ROOT/src.codex/README.md" \
    "$REPO_ROOT/src.claude/README.md" \
    "$REPO_ROOT/src.gemini/README.md" \
    "$REPO_ROOT/src.qwen/README.md" \
    "$DOCS_DIR/README.md" \
    "$DOCS_DIR/agents-mode-reference.md" \
    "$DOCS_DIR/external-worker-design.md" \
    "$DOCS_DIR/provider-runtime-layouts.md" \
    "$CODEX_REF_DIR/README.md" \
    "$CLAUDE_REF_DIR/README.md" \
    "$GEMINI_REF_DIR/README.md" \
    "$QWEN_REF_DIR/README.md"
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
    "and any pack-local provider-specific fields" \
    "shared subagent-operating-model allows provider-specific addendum fields"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    'A subagent `PASS`, report, or claimed test result is a claim, not proof' \
    "shared subagent-operating-model requires subagent result verification"
  check_contains "$SHARED_REF_DIR/subagent-operating-model.md" \
    "Documentation terminology amendment" \
    "shared subagent-operating-model documents terminology glossary discipline"
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

  check_h2_section_contains "$CODEX_REF_DIR/subagent-operating-model.md" \
    "## Codex-specific runtime notes" \
    'Consultant config lives in `.agents/.agents-mode.yaml`' \
    "Codex runtime-notes section documents the Codex agents-mode path"
  check_h2_section_contains "$CODEX_REF_DIR/subagent-operating-model.md" \
    "## Codex-specific runtime notes" \
    "externalClaudeProfile" \
    "Codex runtime-notes section documents the Codex-only externalClaudeProfile field"
  check_h2_section_contains "$CODEX_REF_DIR/subagent-operating-model.md" \
    "## Codex-specific runtime notes" \
    "Shipped production \`auto\` uses \`codex | claude\` only." \
    "Codex runtime-notes section documents profile-based Codex external dispatch"
  check_h2_section_contains "$CODEX_REF_DIR/subagent-operating-model.md" \
    "## Codex-specific runtime notes" \
    "sequential skill invocation" \
    "Codex runtime-notes section keeps the sequential-execution runtime note"
  check_h2_section_absent "$CODEX_REF_DIR/subagent-operating-model.md" \
    "## Codex-specific runtime notes" \
    ".claude/.agents-mode.yaml" \
    "Codex runtime-notes section does not accidentally carry Claude agents-mode paths"
  check_contains "$CODEX_REF_DIR/subagent-operating-model.md" "## Codex-specific runtime notes" \
    "Codex addendum keeps the Codex runtime-notes section"
  check_contains "$GEMINI_REF_DIR/subagent-operating-model.md" "## Gemini-specific runtime notes" \
    "Gemini addendum keeps the Gemini runtime-notes section"
  check_contains "$QWEN_REF_DIR/subagent-operating-model.md" "## Qwen-specific runtime notes" \
    "Qwen addendum keeps the Qwen runtime-notes section"
  check_h2_section_contains "$GEMINI_REF_DIR/subagent-operating-model.md" \
    "## Gemini-specific runtime notes" \
    ".gemini/.agents-mode.yaml" \
    "Gemini runtime-notes section documents the Gemini agents-mode overlay"
  check_h2_section_contains "$GEMINI_REF_DIR/subagent-operating-model.md" \
    "## Gemini-specific runtime notes" \
    ".gemini/settings.json" \
    "Gemini runtime-notes section documents the Gemini native runtime config surface"
  check_h2_section_contains "$GEMINI_REF_DIR/subagent-operating-model.md" \
    "## Gemini-specific runtime notes" \
    "sequential and human-steered" \
    "Gemini runtime-notes section keeps the sequential human-steered runtime note"
  check_h2_section_contains "$QWEN_REF_DIR/subagent-operating-model.md" \
    "## Qwen-specific runtime notes" \
    "sequential and human-steered" \
    "Qwen runtime-notes section keeps the sequential human-steered runtime note"
  check_contains "$QWEN_REF_DIR/subagent-operating-model.md" "## Shared core now owns" \
    "Qwen addendum keeps the shared-core ownership handoff section"
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
    "4bb18cd3df2d2b8e5cc78ff786191da3bbf832555fa80c182ddfda7e2ee097e8" \
    "shared subagent-operating-model matches the current canonical normalized fingerprint"
  check_normalized_sha256 "$CODEX_REF_DIR/subagent-operating-model.md" \
    "160e9bb3bb3df73e611626bc814a45a0923a350a4bff5b43b82bf45409c06549" \
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
echo "=== Skill metadata budget ==="

CODEX_SKILL_DESCRIPTION_MAX_CHARS=180
CODEX_SKILL_DESCRIPTION_TOTAL_MAX_CHARS=5000
UTILITY_SKILLS=(init-project external-brigade second-opinion review-changes)
PACK_BUDGET_SKILLS=("${indexed_roles[@]}" "${UTILITY_SKILLS[@]}")
mapfile -t PACK_BUDGET_SKILLS < <(printf '%s\n' "${PACK_BUDGET_SKILLS[@]}" | sort -u)
check_skill_frontmatter_yaml "${PACK_BUDGET_SKILLS[@]}"
check_skill_description_budget "$CODEX_SKILL_DESCRIPTION_MAX_CHARS" "$CODEX_SKILL_DESCRIPTION_TOTAL_MAX_CHARS" "${PACK_BUDGET_SKILLS[@]}"

echo ""
echo "=== Orphaned skill directories ==="

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

check_absent "$SKILLS_DIR/consultant/SKILL.md" "consultantMode: auto" \
  "consultant skill does not document consultantMode auto"
check_absent "$SKILLS_DIR/consultant/SKILL.md" "fallback approved by user" \
  "consultant skill does not reserve consultant fallback deviations"
check_absent "$SKILLS_DIR/second-opinion/SKILL.md" "consultantMode: auto" \
  "second-opinion skill does not expose consultantMode auto"
check_absent "$SKILLS_DIR/init-project/SKILL.md" "allowed: external | auto | internal | disabled" \
  "init-project skill restricts consultantMode to external/internal/disabled"
check_absent "$SKILLS_DIR/lead/external-dispatch.md" "allowed: external | auto | internal | disabled" \
  "external-dispatch schema restricts consultantMode to external/internal/disabled"
check_absent "$SKILLS_DIR/lead/external-dispatch.md" "fallback approved by user" \
  "external-dispatch does not record consultant fallback approvals"
check_contains "$SKILLS_DIR/lead/subagent-contracts.md" "Read and normalize \`.agents/.agents-mode.yaml\` before trusting its flags." \
  "subagent-contracts require read-time agents-mode normalization"
check_contains "$SKILLS_DIR/init-project/SKILL.md" "normalize it to the current canonical format before presenting or trusting the current values." \
  "init-project normalizes existing agents-mode before reading values"
check_contains "$SKILLS_DIR/init-project/SKILL.md" "Any read of \`.agents/.agents-mode.yaml\` that drives a decision should normalize the file to the current canonical format before trusting the flags." \
  "init-project requires read-time agents-mode normalization"
check_contains "$SKILLS_DIR/second-opinion/SKILL.md" "read and normalize \`.agents/.agents-mode.yaml\` first." \
  "second-opinion normalizes agents-mode before reporting status"
check_absent "$AGENTS_FILE" "Adapter host runtime" \
  "shared governance no longer allows adapter-host metadata for external execution"
check_contains "$AGENTS_FILE" "must use direct external launch" \
  "shared governance requires direct external launch"
check_contains "$AGENTS_FILE" "substantive task prompt must use file-based prompt delivery" \
  "shared governance requires file-based external CLI prompts"
check_contains "$AGENTS_FILE" "verify every subagent result before accepting it" \
  "shared governance requires verification before trusting subagent results"
check_contains "$AGENTS_FILE" "Documentation terminology discipline" \
  "shared governance requires terminology and abbreviation explanations in documents"
check_absent "$SKILLS_DIR/lead/external-dispatch.md" "Adapter host runtime:" \
  "external-dispatch no longer records adapter host runtime"
check_contains "$SKILLS_DIR/lead/external-dispatch.md" "must use direct external launch" \
  "external-dispatch requires direct external launch"
check_contains "$SKILLS_DIR/lead/external-dispatch.md" "substantive task prompt must use file-based prompt delivery" \
  "external-dispatch requires file-based external CLI prompts"
check_absent "$SKILLS_DIR/consultant/SKILL.md" "Adapter host runtime:" \
  "consultant no longer records adapter host runtime"
check_contains "$SKILLS_DIR/consultant/SKILL.md" "must use direct external launch" \
  "consultant requires direct external launch when external"
check_absent "$SKILLS_DIR/external-worker/SKILL.md" "Adapter host runtime:" \
  "external-worker no longer records adapter host runtime"
check_contains "$SKILLS_DIR/external-worker/SKILL.md" "direct external launch contract" \
  "external-worker requires direct external launch"
check_contains "$SKILLS_DIR/external-worker/SKILL.md" "file-based prompt delivery" \
  "external-worker requires file-based external CLI prompts"
check_absent "$SKILLS_DIR/external-reviewer/SKILL.md" "Adapter host runtime:" \
  "external-reviewer no longer records adapter host runtime"
check_contains "$SKILLS_DIR/external-reviewer/SKILL.md" "direct external launch contract" \
  "external-reviewer requires direct external launch"
check_contains "$SKILLS_DIR/external-reviewer/SKILL.md" "file-based prompt delivery" \
  "external-reviewer requires file-based external CLI prompts"
check_absent "$SKILLS_DIR/consultant/SKILL.md" "Actual execution path:** <external CLI (provider name) | internal subagent" \
  "consultant does not mislabel internal subagent as actual execution path"
check_contains "$SKILLS_DIR/external-brigade/SKILL.md" "same-provider brigade items may run in parallel" \
  "external-brigade documents same-provider parallel reuse"
check_contains "$SKILLS_DIR/external-brigade/SKILL.md" "It does not cap how many same-provider brigade items may run in parallel" \
  "external-brigade keeps opinion counts separate from concurrency"
check_contains "$SKILLS_DIR/lead/SKILL.md" "\$external-brigade" \
  "lead skill mentions the external-brigade utility"

echo ""
echo "=== Production auto provider canon ==="

codex_phase_b_files=(
  "$SKILLS_DIR/lead/SKILL.md"
  "$SKILLS_DIR/lead/external-dispatch.md"
  "$SKILLS_DIR/lead/operating-model.md"
  "$SKILLS_DIR/lead/subagent-contracts.md"
  "$SKILLS_DIR/consultant/SKILL.md"
  "$SKILLS_DIR/external-worker/SKILL.md"
  "$SKILLS_DIR/external-reviewer/SKILL.md"
  "$SKILLS_DIR/external-brigade/SKILL.md"
  "$SKILLS_DIR/second-opinion/SKILL.md"
  "$SKILLS_DIR/init-project/SKILL.md"
  "$SKILLS_DIR/graphics-engineer/SKILL.md"
  "$SKILLS_DIR/visualization-engineer/SKILL.md"
  "$SKILLS_DIR/consultant/agents/openai.yaml"
  "$SKILLS_DIR/second-opinion/agents/openai.yaml"
  "$SKILLS_DIR/init-project/agents/openai.yaml"
)

for file in "${codex_phase_b_files[@]}"; do
  check_absent "$file" "gemini-crosscheck" \
    "$file removes retired gemini-crosscheck profile"
  check_absent "$file" "externalGeminiFallbackMode" \
    "$file removes retired externalGeminiFallbackMode"
  check_absent "$file" "externalGeminiWorkdirMode" \
    "$file removes retired externalGeminiWorkdirMode"
done

check_h2_section_absent "$SKILLS_DIR/lead/external-dispatch.md" '### `externalPriorityProfiles`' "gemini" \
  "Codex shipped externalPriorityProfiles keep Gemini out of auto"
check_h2_section_absent "$SKILLS_DIR/lead/external-dispatch.md" '### `externalPriorityProfiles`' "qwen" \
  "Codex shipped externalPriorityProfiles keep Qwen out of auto"
check_h2_section_absent "$SKILLS_DIR/lead/external-dispatch.md" '## Shared lane-priority matrix' "gemini" \
  "Codex shared lane matrix keeps Gemini out of auto"
check_h2_section_absent "$SKILLS_DIR/lead/external-dispatch.md" '## Shared lane-priority matrix' "qwen" \
  "Codex shared lane matrix keeps Qwen out of auto"

if [[ $DEV_REPO -eq 1 ]]; then
  check_contains "$REPO_ROOT/src.codex/AGENTS.codex.md" "\$external-brigade" \
    "Codex platform rules mention the external-brigade utility skill"
  check_contains "$REPO_ROOT/src.codex/AGENTS.codex.md" "auto | codex | claude | gemini | qwen" \
    "Codex platform rules document the example-only Gemini/Qwen provider universe"
  check_contains "$REPO_ROOT/shared/references/README.md" "current Gemini and Qwen example integrations" \
    "shared reference index treats Gemini/Qwen as current example integrations"
fi

check_contains "$SKILLS_DIR/consultant/SKILL.md" 'Gemini and Qwen are `WEAK MODEL / NOT RECOMMENDED` example-only routes' \
  "Codex consultant marks Gemini/Qwen as not recommended example routes"
check_contains "$SKILLS_DIR/external-worker/SKILL.md" 'manual `WEAK MODEL / NOT RECOMMENDED` example-only paths' \
  "Codex external-worker marks Gemini/Qwen as not recommended example routes"
  check_contains "$SKILLS_DIR/external-reviewer/SKILL.md" 'manual `WEAK MODEL / NOT RECOMMENDED` example-only paths' \
    "Codex external-reviewer marks Gemini/Qwen as not recommended example routes"
check_contains "$SKILLS_DIR/lead/operating-model.md" 'do not place Gemini or Qwen inside `externalPriorityProfiles`' \
  "Codex operating model forbids Gemini/Qwen profile entries"
check_contains "$SKILLS_DIR/consultant/agents/openai.yaml" 'explicit `WEAK MODEL / NOT RECOMMENDED` example-only paths' \
  "Codex consultant prompt marks Gemini/Qwen as not recommended example routes"
check_contains "$SKILLS_DIR/init-project/agents/openai.yaml" 'explicit `WEAK MODEL / NOT RECOMMENDED` example-only paths' \
  "Codex init-project prompt marks Gemini/Qwen as not recommended example routes"
check_contains "$SKILLS_DIR/second-opinion/agents/openai.yaml" 'explicit `WEAK MODEL / NOT RECOMMENDED` example-only paths' \
  "Codex second-opinion prompt marks Gemini/Qwen as not recommended example routes"

if [[ $DEV_REPO -eq 1 ]]; then
  check_contains "$DOCS_DIR/agents-mode-reference.md" "## Canonical maintenance" \
    "agents-mode reference defines canonical maintenance"
  check_contains "$DOCS_DIR/agents-mode-reference.md" "Read-time normalization preserves the effective values of known keys" \
    "agents-mode reference documents read-time normalization semantics"
  check_contains "$DOCS_DIR/agents-mode-reference.md" 'removes example-only providers from every `externalPriorityProfiles` provider list' \
    "agents-mode reference documents profile provider sanitization"
  check_contains "$DOCS_DIR/agents-mode-reference.md" "Substantive task prompts are file-based by default" \
    "agents-mode reference documents file-based external CLI prompts"
  check_normalizer_strips_example_auto_providers \
    "agents-mode normalizer strips Gemini/Qwen and worker claude-secret from custom auto profiles"
  check_file "$REPO_ROOT/shared/agents-mode.defaults.yaml" "shared/agents-mode.defaults.yaml"
  check_shared_defaults_claude_secret_policy \
    "shared agents-mode defaults keep claude-secret advisory/review-only"
  check_not_exists "$REPO_ROOT/src.codex/agents-mode.defaults.yaml" \
    "src.codex/agents-mode.defaults.yaml removed from the monorepo"
  check_contains "$REPO_ROOT/INSTALL.md" ".codex/agents/default.toml" \
    "INSTALL.md documents Codex built-in agent override seeding"
  check_contains "$DOCS_DIR/provider-runtime-layouts.md" "~/.codex/agents/default.toml" \
    "provider runtime layouts document global Codex built-in agent overrides"
  check_contains "$REPO_ROOT/src.codex/README.md" "agents/default.toml" \
    "src.codex/README.md documents the built-in agent override payload"
fi

if [[ -n "$CODEX_RUNTIME_ROOT" ]]; then
  echo ""
  echo "=== Codex built-in agent overrides ==="
  check_file "$CODEX_RUNTIME_ROOT/agents/default.toml" "agents/default.toml installed"
  check_file "$CODEX_RUNTIME_ROOT/agents/worker.toml" "agents/worker.toml installed"
  check_file "$CODEX_RUNTIME_ROOT/agents/explorer.toml" "agents/explorer.toml installed"
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

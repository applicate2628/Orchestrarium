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
SOURCE_SCRIPTS_DIR=""
if [[ -d "src.codex/skills/lead/scripts" ]]; then
  SOURCE_SCRIPTS_DIR="$(cd "src.codex/skills/lead/scripts" && pwd -P)"
fi
if [[ -n "$SOURCE_SCRIPTS_DIR" && "$SCRIPT_DIR" == "$SOURCE_SCRIPTS_DIR" && -f "shared/AGENTS.shared.md" && -f "src.codex/AGENTS.codex.md" ]]; then
  # Dev repo: assemble AGENTS.md from split source files for validation
  SKILLS_DIR="$(cd "src.codex/skills" && pwd -P)"
  SCRIPTS_DIR="$SOURCE_SCRIPTS_DIR"
  REPO_ROOT="$(pwd -P)"
  DEV_REPO=1
  AGENTS_FILE="$(mktemp)"
  {
    printf '%s\n' '<!-- BEGIN ORCHESTRARIUM CODEX PACK -->'
    cat "shared/AGENTS.shared.md"
    printf '\n'
    cat "src.codex/AGENTS.codex.md"
    printf '\n%s\n' '<!-- END ORCHESTRARIUM CODEX PACK -->'
  } > "$AGENTS_FILE"
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

count_codex_pack_lines() {
  local file="$1"
  local begin='<!-- BEGIN ORCHESTRARIUM CODEX PACK -->'
  local end='<!-- END ORCHESTRARIUM CODEX PACK -->'
  local start=""
  local finish=""

  start="$(grep -nFx "$begin" "$file" 2>/dev/null | head -1 | cut -d: -f1 || true)"
  finish="$(grep -nFx "$end" "$file" 2>/dev/null | head -1 | cut -d: -f1 || true)"

  if [[ -n "$start" && -n "$finish" && "$finish" -ge "$start" ]]; then
    sed -n "${start},${finish}p" "$file" | wc -l | tr -d '[:space:]'
  else
    wc -l < "$file" | tr -d '[:space:]'
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
    "$SHARED_REF_DIR/ru/evidence-based-answer-pipeline.md" \
    "$SHARED_REF_DIR/ru/subagent-operating-model.md" \
    "$SHARED_REF_DIR/ru/workflow-strategy-comparison.md" \
    "$SHARED_REF_DIR/ru/repository-publication-safety.md"
  do
    if [[ -f "$f" ]]; then pass "$f"; else fail "$f missing"; fi
  done

  for ref_dir in "$SHARED_REF_DIR" "$CODEX_REF_DIR" "$CLAUDE_REF_DIR" "$GEMINI_REF_DIR" "$QWEN_REF_DIR"; do
    while IFS= read -r source_file; do
      name="$(basename "$source_file")"
      [[ "$name" == "README.md" ]] && continue
      if [[ -f "$ref_dir/ru/$name" ]]; then
        pass "$ref_dir/ru/$name mirrors $name"
      else
        fail "$ref_dir/ru/$name missing for $name"
      fi
    done < <(find "$ref_dir" -maxdepth 1 -type f -name '*.md' | sort)
  done

  echo ""
  echo "=== Codex compatibility pointers ==="

  check_pointer "$CODEX_REF_DIR/evidence-based-answer-pipeline.md" "../shared/references/evidence-based-answer-pipeline.md"
  check_pointer "$CODEX_REF_DIR/subagent-operating-model.md" "../shared/references/subagent-operating-model.md"
  check_pointer "$CODEX_REF_DIR/workflow-strategy-comparison.md" "../shared/references/workflow-strategy-comparison.md"
  check_pointer "$CODEX_REF_DIR/repository-publication-safety.md" "../shared/references/repository-publication-safety.md"
  check_pointer "$CODEX_REF_DIR/ru/evidence-based-answer-pipeline.md" "../../shared/references/ru/evidence-based-answer-pipeline.md"
  check_pointer "$CODEX_REF_DIR/ru/subagent-operating-model.md" "../../shared/references/ru/subagent-operating-model.md"
  check_pointer "$CODEX_REF_DIR/ru/workflow-strategy-comparison.md" "../../shared/references/ru/workflow-strategy-comparison.md"
  check_pointer "$CODEX_REF_DIR/ru/repository-publication-safety.md" "../../shared/references/ru/repository-publication-safety.md"
  check_pointer "$CLAUDE_REF_DIR/evidence-based-answer-pipeline.md" "../shared/references/evidence-based-answer-pipeline.md"
  check_pointer "$CLAUDE_REF_DIR/ru/evidence-based-answer-pipeline.md" "../../shared/references/ru/evidence-based-answer-pipeline.md"
  check_pointer "$GEMINI_REF_DIR/evidence-based-answer-pipeline.md" "../shared/references/evidence-based-answer-pipeline.md"
  check_pointer "$GEMINI_REF_DIR/workflow-strategy-comparison.md" "../shared/references/workflow-strategy-comparison.md"
  check_pointer "$GEMINI_REF_DIR/repository-publication-safety.md" "../shared/references/repository-publication-safety.md"
  check_pointer "$GEMINI_REF_DIR/ru/evidence-based-answer-pipeline.md" "../../shared/references/ru/evidence-based-answer-pipeline.md"
  check_pointer "$GEMINI_REF_DIR/ru/workflow-strategy-comparison.md" "../../shared/references/ru/workflow-strategy-comparison.md"
  check_pointer "$GEMINI_REF_DIR/ru/repository-publication-safety.md" "../../shared/references/ru/repository-publication-safety.md"
  check_pointer "$QWEN_REF_DIR/evidence-based-answer-pipeline.md" "../shared/references/evidence-based-answer-pipeline.md"
  check_pointer "$QWEN_REF_DIR/ru/evidence-based-answer-pipeline.md" "../../shared/references/ru/evidence-based-answer-pipeline.md"

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
    "1a8291b94323bb586db4f7de30715d1be91d847512f2325633cd10eb8ce7286d" \
    "shared subagent-operating-model matches the current canonical normalized fingerprint"
  check_normalized_sha256 "$CODEX_REF_DIR/subagent-operating-model.md" \
    "160e9bb3bb3df73e611626bc814a45a0923a350a4bff5b43b82bf45409c06549" \
    "Codex addendum matches the current canonical normalized fingerprint"
fi

echo ""
echo "=== Role index consistency ==="

mapfile -t indexed_roles < <(
  awk '/^## Role index/{flag=1; next} /^## /{flag=0} flag' "$AGENTS_FILE" \
    | grep -oE '\$[a-z][a-z-]{2,}' \
    | sed 's/^\$//' \
    | sort -u
)
mapfile -t indexed_common_skills < <(
  awk '/^## Common skills/{flag=1; next} /^## /{flag=0} flag' "$AGENTS_FILE" \
    | grep -oE '\$[a-z][a-z-]{2,}' \
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
# Budget covers roles + utility skills + common skills. Roles alone were sized at 3000 historically;
# raised to 3500 (2026-05-16) to accommodate the common-skills category without forcing
# role-description churn. Current consumption ~3352 chars; headroom ~148 chars is tight — adding
# a 5th common skill at ≥150 chars will overflow and require either another budget bump or
# trimming the existing descriptions, not silent budget growth.
CODEX_SKILL_DESCRIPTION_TOTAL_MAX_CHARS=3500
UTILITY_SKILLS=(init-project external-brigade second-opinion review-changes)
PACK_BUDGET_SKILLS=("${indexed_roles[@]}" "${UTILITY_SKILLS[@]}" "${indexed_common_skills[@]}")
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
  is_common_skill=0
  for cs in "${indexed_common_skills[@]}"; do
    if [[ "$cs" == "$role" ]]; then is_common_skill=1; break; fi
  done
  if [[ $is_common_skill -eq 1 ]]; then
    pass "Directory $dir is registered as a common skill"
    continue
  fi
  found=0
  for indexed in "${indexed_roles[@]}"; do
    if [[ "$indexed" == "$role" ]]; then found=1; break; fi
  done
  if [[ $found -eq 0 ]]; then
    warn "Directory $dir exists but \$$role is not in AGENTS.md role index or common-skill index"
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
check_contains "$SKILLS_DIR/lead/subagent-contracts.md" "agent-runs.jsonl format" \
  "subagent-contracts define the agent run ledger format"
check_contains "$SKILLS_DIR/lead/subagent-contracts.md" 'A `PASS` in `status.md` is not accepted' \
  "subagent-contracts reject PASS without ledger evidence"
check_contains "$SKILLS_DIR/lead/subagent-contracts.md" "shared/schemas/agent-runs.schema.json" \
  "subagent-contracts point to the shared ledger schema"
check_contains "$SKILLS_DIR/lead/subagent-contracts.md" "scripts/agent-run-ledger.*" \
  "subagent-contracts point to the work-item ledger helper"
check_contains "$SKILLS_DIR/lead/subagent-contracts.md" "scripts/validate-work-item-state.* --work-item" \
  "subagent-contracts point to the work-item state validator"
check_contains "$SKILLS_DIR/lead/subagent-contracts.md" "scripts/check-work-items-state.* --root" \
  "subagent-contracts point to the periodic work-item state checker"
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
check_contains "$AGENTS_FILE" "Mechanism inventory before new paths" \
  "shared governance requires owner inventory before new mechanisms"
check_contains "$AGENTS_FILE" "State-synchronization ownership" \
  "shared governance requires state synchronization ownership discipline"
check_contains "$AGENTS_FILE" "split-brain state sync as an architecture bug" \
  "shared governance rejects split-brain state synchronization"
check_contains "$AGENTS_FILE" "correlation IDs" \
  "shared governance requires traceable state synchronization diagnostics"
check_contains "$AGENTS_FILE" "verify every subagent result before accepting it" \
  "shared governance requires verification before trusting subagent results"
check_contains "$AGENTS_FILE" "Visual artifact verification discipline" \
  "shared governance requires visual inspection for generated visual artifacts"
check_contains "$AGENTS_FILE" "Documentation terminology discipline" \
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
  check_contains "$REPO_ROOT/README.md" "Pressing Enter selects the default production install" \
    "README documents the Codex/Claude default root install"
  check_contains "$REPO_ROOT/INSTALL.md" "Pressing Enter selects the default production install" \
    "INSTALL.md documents the Codex/Claude default root install"
  check_contains "$REPO_ROOT/INSTALL.md" ".agents-mode.yaml" \
    "INSTALL.md default project result includes provider overlay files"
  check_contains "$REPO_ROOT/docs/agents-mode-reference.md" '`power-mode` | hardest-task maximum result' \
    "agents-mode reference documents power-mode preset"
  check_contains "$REPO_ROOT/src.codex/skills/init-project/SKILL.md" '`power-mode` (hardest-task maximum result)' \
    "Codex init-project exposes power-mode preset"
  for lane in review.security review.ui-visual-correctness; do
    check_contains "$REPO_ROOT/src.codex/skills/init-project/SKILL.md" "$lane: 2" \
      "Codex init-project correctness-first/power-mode presets raise $lane"
  done
  if command -v python3 >/dev/null 2>&1; then
    contract_python_cmd="python3"
  elif command -v python >/dev/null 2>&1; then
    contract_python_cmd="python"
  else
    contract_python_cmd=""
  fi
  if [[ -n "$contract_python_cmd" ]] &&
     "$contract_python_cmd" "$REPO_ROOT/scripts/validate-agents-mode-contract.py" --root "$REPO_ROOT" >/dev/null; then
    pass "agents-mode machine-readable contract matches docs and init preset surfaces"
  else
    fail "agents-mode machine-readable contract matches docs and init preset surfaces"
  fi
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
  check_contains "$DOCS_DIR/agents-mode-reference.md" "agent-runs.jsonl" \
    "agents-mode reference documents ledger fan-out tracking"
  check_contains "$DOCS_DIR/external-worker-design.md" "Work-item ledger rule" \
    "external-worker design maps execution records to the ledger"
  check_normalizer_strips_example_auto_providers \
    "agents-mode normalizer strips Gemini/Qwen and keeps reserve last or absent in custom auto profiles"
  check_file "$REPO_ROOT/shared/agents-mode.defaults.yaml" "shared/agents-mode.defaults.yaml"
  check_shared_defaults_reserve_policy \
    "shared agents-mode defaults keep reserve advisory/review-only"
  check_not_exists "$REPO_ROOT/src.codex/agents-mode.defaults.yaml" \
    "src.codex/agents-mode.defaults.yaml removed from the monorepo"
  check_contains "$REPO_ROOT/INSTALL.md" ".codex/agents/default.toml" \
    "INSTALL.md documents Codex built-in agent override seeding"
  check_contains "$DOCS_DIR/provider-runtime-layouts.md" "~/.codex/agents/default.toml" \
    "provider runtime layouts document global Codex built-in agent overrides"
  check_contains "$REPO_ROOT/src.codex/README.md" "agents/default.toml" \
    "src.codex/README.md documents the built-in agent override payload"
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
else
  echo ""
  echo "=== Installed work-item runtime helper scripts ==="
  for f in \
    "$SCRIPTS_DIR/agent-run-ledger.py" \
    "$SCRIPTS_DIR/agent-run-ledger.sh" \
    "$SCRIPTS_DIR/agent-run-ledger.ps1" \
    "$SCRIPTS_DIR/check-work-items-state.py" \
    "$SCRIPTS_DIR/check-work-items-state.sh" \
    "$SCRIPTS_DIR/check-work-items-state.ps1" \
    "$SCRIPTS_DIR/validate-work-item-state.py" \
    "$SCRIPTS_DIR/validate-work-item-state.sh" \
    "$SCRIPTS_DIR/validate-work-item-state.ps1"
  do
    check_file "$f" "$f installed"
  done
  check_contains "$SCRIPTS_DIR/agent-run-ledger.py" "validate_work_item" \
    "installed agent-run-ledger helper reuses the validator"
  check_contains "$SCRIPTS_DIR/check-work-items-state.py" "stale running agent" \
    "installed periodic work-item checker reports stale running agents"
  check_contains "$SCRIPTS_DIR/validate-work-item-state.py" "PASS gate requires evidence" \
    "installed work-item state validator enforces evidence for PASS"
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

agents_line_count="$(count_codex_pack_lines "$AGENTS_FILE")"
# Budget bumped 340 -> 360 (2026-05-16) to accommodate the "Fix means correct
# logic, not workaround" (no-kostyl) clause added as step 4.5 to the Bootstrap
# block. Previous bump 300 -> 340 added the Bootstrap itself; this bump (~2
# lines actual, +20 ceiling) preserves headroom for the next governance
# addition. Visible decision rather than silent budget growth.
if [[ "$agents_line_count" -le 360 ]]; then
  pass "Codex AGENTS.md pack section line budget <= 360 ($agents_line_count)"
else
  fail "Codex AGENTS.md pack section line budget exceeded ($agents_line_count > 360)"
fi

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

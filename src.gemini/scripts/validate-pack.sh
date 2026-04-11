#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"

skill_roles=(
  accessibility-reviewer
  algorithm-scientist
  analyst
  architect
  architecture-reviewer
  backend-engineer
  computational-scientist
  consultant
  data-engineer
  external-reviewer
  external-worker
  external-brigade
  frontend-engineer
  geometry-engineer
  graphics-engineer
  init-project
  knowledge-archivist
  lead
  model-view-engineer
  performance-engineer
  performance-reviewer
  planner
  platform-engineer
  product-analyst
  product-manager
  qa-engineer
  qt-ui-engineer
  reliability-engineer
  review-changes
  second-opinion
  security-engineer
  security-reviewer
  toolchain-engineer
  ui-test-engineer
  ux-designer
  ux-reviewer
  visualization-engineer
)

agent_roles=(
  accessibility-reviewer
  algorithm-scientist
  analyst
  architect
  architecture-reviewer
  backend-engineer
  computational-scientist
  consultant
  data-engineer
  external-reviewer
  external-worker
  frontend-engineer
  geometry-engineer
  graphics-engineer
  knowledge-archivist
  lead
  model-view-engineer
  performance-engineer
  performance-reviewer
  planner
  platform-engineer
  product-analyst
  product-manager
  qa-engineer
  qt-ui-engineer
  reliability-engineer
  security-engineer
  security-reviewer
  toolchain-engineer
  ui-test-engineer
  ux-designer
  ux-reviewer
  visualization-engineer
)

team_templates=(
  combined-critical
  full-delivery
  geometry-review
  performance-sensitive
  quick-fix
  research
  review
  security-sensitive
)

fail() {
  echo "FAIL: $1"
  exit 1
}

if [[ -d "$ROOT/src.gemini" ]]; then
  MODE="source"
  PACK_ROOT="$ROOT/src.gemini"
  GEMINI_FILE="$PACK_ROOT/GEMINI.md"
  SHARED_SOURCE_FILE="$PACK_ROOT/AGENTS.shared.md"
  RUNTIME_AGENTS_FILE="$PACK_ROOT/AGENTS.md"
  REQUIRE_EXTENSION=1
elif [[ -f "$ROOT/GEMINI.md" && -d "$ROOT/skills" && -d "$ROOT/agents" ]]; then
  MODE="installed-root"
  PACK_ROOT="$ROOT"
  GEMINI_FILE="$ROOT/GEMINI.md"
  SHARED_SOURCE_FILE="$ROOT/AGENTS.shared.md"
  RUNTIME_AGENTS_FILE="$ROOT/AGENTS.md"
  REQUIRE_EXTENSION=0
elif [[ -f "$ROOT/GEMINI.md" && -d "$ROOT/.gemini" ]]; then
  MODE="installed-project"
  PACK_ROOT="$ROOT/.gemini"
  GEMINI_FILE="$ROOT/GEMINI.md"
  SHARED_SOURCE_FILE="$ROOT/AGENTS.shared.md"
  RUNTIME_AGENTS_FILE="$ROOT/AGENTS.md"
  REQUIRE_EXTENSION=0
else
  fail "unable to detect Gemini source tree or installed runtime under $ROOT"
fi

required_common=(
  "$GEMINI_FILE"
  "$PACK_ROOT/skills/README.md"
  "$PACK_ROOT/skills/lead/SKILL.md"
  "$PACK_ROOT/skills/init-project/SKILL.md"
  "$PACK_ROOT/commands/agents/help.toml"
  "$PACK_ROOT/commands/agents/external-brigade.toml"
  "$PACK_ROOT/commands/agents/init-project.toml"
  "$PACK_ROOT/agents/README.md"
  "$PACK_ROOT/agents/lead.md"
  "$PACK_ROOT/agents/team-templates/quick-fix.json"
)

for path in "${required_common[@]}"; do
  [[ -f "$path" ]] || fail "missing $path"
done

if [[ "$MODE" == "source" ]]; then
  [[ -f "$SHARED_SOURCE_FILE" ]] || fail "missing $SHARED_SOURCE_FILE"
  [[ ! -e "$RUNTIME_AGENTS_FILE" ]] || fail "$RUNTIME_AGENTS_FILE should not exist in the source tree"
  [[ -f "$PACK_ROOT/extension/README.md" ]] || fail "missing $PACK_ROOT/extension/README.md"
  [[ -f "$PACK_ROOT/extension/gemini-extension.json" ]] || fail "missing $PACK_ROOT/extension/gemini-extension.json"
else
  [[ -f "$RUNTIME_AGENTS_FILE" ]] || fail "missing runtime governance file $RUNTIME_AGENTS_FILE"
  [[ ! -e "$SHARED_SOURCE_FILE" ]] || fail "$SHARED_SOURCE_FILE should not exist in the installed runtime"
fi

for role in "${skill_roles[@]}"; do
  [[ -f "$PACK_ROOT/skills/$role/SKILL.md" ]] || fail "missing skill role $PACK_ROOT/skills/$role/SKILL.md"
done

for role in "${agent_roles[@]}"; do
  [[ -f "$PACK_ROOT/agents/$role.md" ]] || fail "missing agent role $PACK_ROOT/agents/$role.md"
done

for template in "${team_templates[@]}"; do
  [[ -f "$PACK_ROOT/agents/team-templates/$template.json" ]] || fail "missing team template $PACK_ROOT/agents/team-templates/$template.json"
done

IMPORT_ROOT="$(dirname "$GEMINI_FILE")"
while IFS= read -r import_line; do
  import_target="${import_line#@}"
  [[ -z "$import_target" ]] && continue
  [[ -f "$IMPORT_ROOT/$import_target" ]] || fail "GEMINI.md import target missing: $IMPORT_ROOT/$import_target"
done < <(grep '^@' "$GEMINI_FILE" || true)

if [[ "$MODE" == "source" ]]; then
  grep -q '^@\./AGENTS\.shared\.md$' "$GEMINI_FILE" || fail "source GEMINI.md should import @./AGENTS.shared.md"
else
  grep -q '^@\./AGENTS\.md$' "$GEMINI_FILE" || fail "installed GEMINI.md should import @./AGENTS.md"
fi
grep -q '/init' "$GEMINI_FILE" || fail "GEMINI.md should mention the official Gemini /init bootstrap path"
grep -q '\.gemini/settings\.json' "$GEMINI_FILE" || fail "GEMINI.md should mention .gemini/settings.json as the official Gemini runtime-state surface"
grep -q 'agents/team-templates/' "$GEMINI_FILE" || fail "GEMINI.md should mention agents/team-templates/"
grep -q 'cannot recursively call' "$PACK_ROOT/skills/lead/SKILL.md" || fail "lead skill should state the Gemini subagent recursion constraint"
grep -q 'main Gemini session' "$PACK_ROOT/skills/lead/SKILL.md" || fail "lead skill should identify the main Gemini session as orchestration owner"
grep -q 'agents/team-templates' "$PACK_ROOT/commands/agents/help.toml" || fail "help command should describe the team-template layer"
grep -q 'external-brigade' "$PACK_ROOT/commands/agents/help.toml" || fail "help command should describe the external-brigade surface"
grep -q 'external-brigade' "$PACK_ROOT/skills/lead/SKILL.md" || fail "lead skill should mention the external-brigade utility"
grep -Fq 'Keep `externalOpinionCounts` separate from helper multiplicity' "$PACK_ROOT/skills/init-project/SKILL.md" || fail "init-project should keep opinion counts separate from helper multiplicity"
! grep -Fq 'consultantMode: auto' "$PACK_ROOT/skills/second-opinion/SKILL.md" || fail "second-opinion skill should not expose consultantMode auto"
! grep -Fq 'allowed: external | auto | internal | disabled' "$PACK_ROOT/skills/init-project/SKILL.md" || fail "init-project skill should restrict consultantMode to external/internal/disabled"
! grep -Fq 'allowed: external | auto | internal | disabled' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should restrict consultantMode to external/internal/disabled"
! grep -Fq 'fallback approved by user' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should not record consultant fallback approvals"
grep -Fq 'normalize it to the current canonical format before presenting or trusting any values.' "$PACK_ROOT/skills/init-project/SKILL.md" || fail "init-project should normalize agents-mode before reading values"
grep -Fq 'Any read of `.gemini/.agents-mode` that drives a decision should normalize the file to the current canonical format before trusting the flags.' "$PACK_ROOT/skills/init-project/SKILL.md" || fail "init-project should require read-time agents-mode normalization"
grep -Fq 'read and normalize `.gemini/.agents-mode`, then print the current resolved values' "$PACK_ROOT/skills/second-opinion/SKILL.md" || fail "second-opinion should normalize agents-mode before reporting status"
grep -Fq 'Read and normalize `.gemini/.agents-mode` before routing.' "$PACK_ROOT/skills/consultant/SKILL.md" || fail "consultant should normalize agents-mode before routing"
grep -Fq 'Any read of `.gemini/.agents-mode` that influences routing must normalize an existing file to the current canonical format before trusting the flags.' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should require read-time agents-mode normalization"
if [[ "$MODE" == "source" ]]; then
  grep -Fq 'Adapter host runtime' "$SHARED_SOURCE_FILE" && fail "shared governance should not allow adapter-host metadata for external execution"
  grep -Fq 'must use direct external launch' "$SHARED_SOURCE_FILE" || fail "shared governance should require direct external launch"
else
  grep -Fq 'Adapter host runtime' "$RUNTIME_AGENTS_FILE" && fail "shared governance should not allow adapter-host metadata for external execution"
  grep -Fq 'must use direct external launch' "$RUNTIME_AGENTS_FILE" || fail "shared governance should require direct external launch"
fi
grep -Fq 'Adapter host runtime:' "$PACK_ROOT/skills/lead/external-dispatch.md" && fail "external-dispatch should not record adapter host runtime"
grep -Fq 'must use direct external launch' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should require direct external launch"
grep -Fq 'Read and normalize `.gemini/.agents-mode` to the current canonical format before trusting its flags.' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should normalize agents-mode before routing"
grep -Fq 'Read and normalize `.gemini/.agents-mode` to the current canonical format before trusting its flags.' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should normalize agents-mode before routing"
grep -Fq 'externalPriorityProfile' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should honor structured profile keys"
grep -Fq 'externalPriorityProfile' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should honor structured profile keys"
grep -Fq 'direct external launch contract' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should require direct external launch"
grep -Fq 'direct external launch contract' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should require direct external launch"
grep -Fq 'same-provider brigade items may run in parallel' "$PACK_ROOT/skills/external-brigade/SKILL.md" || fail "external-brigade should document same-provider parallel reuse"
grep -Fq 'It does not cap how many same-provider brigade items may run in parallel' "$PACK_ROOT/skills/external-brigade/SKILL.md" || fail "external-brigade should keep opinion counts separate from concurrency"

if [[ "$MODE" == "source" && -f "$ROOT/docs/agents-mode-reference.md" ]]; then
  grep -Fq '## Canonical maintenance' "$ROOT/docs/agents-mode-reference.md" || fail "agents-mode reference should define canonical maintenance"
  grep -Fq 'Read-time normalization preserves the effective values of known keys' "$ROOT/docs/agents-mode-reference.md" || fail "agents-mode reference should document read-time normalization semantics"
  grep -Fq 'same-lane distinct-opinion contract' "$ROOT/docs/agents-mode-reference.md" || fail "agents-mode reference should distinguish opinion counts from helper multiplicity"
  grep -Fq 'external-brigade' "$ROOT/src.gemini/AGENTS.shared.md" || fail "shared governance should name external-brigade"
fi

start_count="$(grep -cF '<!-- ORCHESTRARIUM_GEMINI_PACK:START -->' "$GEMINI_FILE" || true)"
end_count="$(grep -cF '<!-- ORCHESTRARIUM_GEMINI_PACK:END -->' "$GEMINI_FILE" || true)"
[[ "$start_count" -eq 1 && "$end_count" -eq 1 ]] || fail "GEMINI.md should contain exactly one managed Orchestrarium pack block"

for skill in "$PACK_ROOT/skills/lead/SKILL.md" "$PACK_ROOT/skills/init-project/SKILL.md"; do
  grep -q '^---$' "$skill" || fail "missing frontmatter in $skill"
  grep -q '^name:' "$skill" || fail "missing skill name in $skill"
  grep -q '^description:' "$skill" || fail "missing skill description in $skill"
done

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
else
  fail "python or python3 is required to validate Gemini TOML and JSON surfaces"
fi

json_targets=(
  "$PACK_ROOT/agents/team-templates/combined-critical.json"
  "$PACK_ROOT/agents/team-templates/full-delivery.json"
  "$PACK_ROOT/agents/team-templates/geometry-review.json"
  "$PACK_ROOT/agents/team-templates/performance-sensitive.json"
  "$PACK_ROOT/agents/team-templates/quick-fix.json"
  "$PACK_ROOT/agents/team-templates/research.json"
  "$PACK_ROOT/agents/team-templates/review.json"
  "$PACK_ROOT/agents/team-templates/security-sensitive.json"
)

if [[ "$REQUIRE_EXTENSION" -eq 1 ]]; then
  json_targets+=("$PACK_ROOT/extension/gemini-extension.json")
fi

"$PYTHON_BIN" - "$PACK_ROOT/commands/agents/help.toml" "$PACK_ROOT/commands/agents/external-brigade.toml" "$PACK_ROOT/commands/agents/init-project.toml" "${json_targets[@]}" <<'PY'
import json
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    print("FAIL: Python tomllib is unavailable; cannot validate Gemini TOML syntax")
    sys.exit(1)

toml_paths = [Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])]
json_paths = [Path(path) for path in sys.argv[4:]]

for toml_path in toml_paths:
    with toml_path.open("rb") as fh:
        tomllib.load(fh)

for json_path in json_paths:
    with json_path.open("r", encoding="utf-8") as fh:
        json.load(fh)
PY

if [[ "$REQUIRE_EXTENSION" -eq 1 ]]; then
  grep -q '"contextFileName": "GEMINI.md"' "$PACK_ROOT/extension/gemini-extension.json" || fail "extension manifest should declare contextFileName GEMINI.md"
fi

echo "PASS: Gemini $MODE tree present at $PACK_ROOT"

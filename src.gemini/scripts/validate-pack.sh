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
  external-brigade
  data-engineer
  external-reviewer
  external-worker
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
  LEGACY_RUNTIME_ROOT=""
elif [[ -f "$ROOT/GEMINI.md" && -d "$ROOT/extensions/orchestrarium-gemini" ]]; then
  MODE="installed-root"
  PACK_ROOT="$ROOT/extensions/orchestrarium-gemini"
  GEMINI_FILE="$ROOT/GEMINI.md"
  SHARED_SOURCE_FILE="$ROOT/AGENTS.shared.md"
  RUNTIME_AGENTS_FILE="$ROOT/AGENTS.md"
  LEGACY_RUNTIME_ROOT="$ROOT"
elif [[ -f "$ROOT/GEMINI.md" && -d "$ROOT/.gemini/extensions/orchestrarium-gemini" ]]; then
  MODE="installed-project"
  PACK_ROOT="$ROOT/.gemini/extensions/orchestrarium-gemini"
  GEMINI_FILE="$ROOT/GEMINI.md"
  SHARED_SOURCE_FILE="$ROOT/AGENTS.shared.md"
  RUNTIME_AGENTS_FILE="$ROOT/AGENTS.md"
  LEGACY_RUNTIME_ROOT="$ROOT/.gemini"
else
  fail "unable to detect Gemini source tree or installed runtime under $ROOT"
fi

EXTENSION_NAME="orchestrarium-gemini"
if [[ "$MODE" == "source" ]]; then
  EXTENSION_ROOT="$PACK_ROOT/extension"
else
  EXTENSION_ROOT="$PACK_ROOT"
fi
EXTENSION_MANIFEST_FILE="$EXTENSION_ROOT/gemini-extension.json"
EXTENSION_README_FILE="$EXTENSION_ROOT/README.md"
EXTENSION_GEMINI_FILE="$EXTENSION_ROOT/GEMINI.md"
EXTENSION_AGENTS_FILE="$EXTENSION_ROOT/AGENTS.md"

required_common=(
  "$GEMINI_FILE"
  "$PACK_ROOT/skills/README.md"
  "$PACK_ROOT/skills/lead/SKILL.md"
  "$PACK_ROOT/skills/init-project/SKILL.md"
  "$PACK_ROOT/skills/external-brigade/SKILL.md"
  "$PACK_ROOT/commands/agents/help.toml"
  "$PACK_ROOT/commands/agents/external-brigade.toml"
  "$PACK_ROOT/commands/agents/init-project.toml"
  "$PACK_ROOT/agents/lead.md"
  "$PACK_ROOT/agents/team-templates/quick-fix.json"
)

for path in "${required_common[@]}"; do
  [[ -f "$path" ]] || fail "missing $path"
done

if [[ "$MODE" == "source" ]]; then
  [[ -f "$SHARED_SOURCE_FILE" ]] || fail "missing $SHARED_SOURCE_FILE"
  [[ ! -e "$RUNTIME_AGENTS_FILE" ]] || fail "$RUNTIME_AGENTS_FILE should not exist in the source tree"
  [[ -f "$EXTENSION_README_FILE" ]] || fail "missing $EXTENSION_README_FILE"
  [[ -f "$EXTENSION_MANIFEST_FILE" ]] || fail "missing $EXTENSION_MANIFEST_FILE"
else
  [[ -f "$RUNTIME_AGENTS_FILE" ]] || fail "missing runtime governance file $RUNTIME_AGENTS_FILE"
  [[ ! -e "$SHARED_SOURCE_FILE" ]] || fail "$SHARED_SOURCE_FILE should not exist in the installed runtime"
  [[ -f "$EXTENSION_MANIFEST_FILE" ]] || fail "missing installed extension manifest $EXTENSION_MANIFEST_FILE"
  [[ -f "$EXTENSION_README_FILE" ]] || fail "missing installed extension README $EXTENSION_README_FILE"
  [[ -f "$EXTENSION_GEMINI_FILE" ]] || fail "missing installed extension context $EXTENSION_GEMINI_FILE"
  [[ -f "$EXTENSION_AGENTS_FILE" ]] || fail "missing installed extension governance $EXTENSION_AGENTS_FILE"
  [[ -f "$EXTENSION_ROOT/skills/README.md" ]] || fail "missing installed extension skills readme $EXTENSION_ROOT/skills/README.md"
  [[ -f "$EXTENSION_ROOT/skills/lead/SKILL.md" ]] || fail "missing installed extension lead skill $EXTENSION_ROOT/skills/lead/SKILL.md"
  [[ -f "$EXTENSION_ROOT/skills/init-project/SKILL.md" ]] || fail "missing installed extension init-project skill $EXTENSION_ROOT/skills/init-project/SKILL.md"
  [[ -f "$EXTENSION_ROOT/commands/agents/help.toml" ]] || fail "missing installed extension help command $EXTENSION_ROOT/commands/agents/help.toml"
  [[ -f "$EXTENSION_ROOT/commands/agents/external-brigade.toml" ]] || fail "missing installed extension brigade command $EXTENSION_ROOT/commands/agents/external-brigade.toml"
  [[ -f "$EXTENSION_ROOT/commands/agents/init-project.toml" ]] || fail "missing installed extension init-project command $EXTENSION_ROOT/commands/agents/init-project.toml"
  [[ -f "$EXTENSION_ROOT/agents/lead.md" ]] || fail "missing installed extension lead agent $EXTENSION_ROOT/agents/lead.md"
  [[ -f "$EXTENSION_ROOT/agents/team-templates/quick-fix.json" ]] || fail "missing installed extension team template $EXTENSION_ROOT/agents/team-templates/quick-fix.json"
  [[ ! -e "$EXTENSION_ROOT/AGENTS.shared.md" ]] || fail "$EXTENSION_ROOT/AGENTS.shared.md should not exist in the installed extension runtime"
  [[ ! -e "$EXTENSION_ROOT/agents/README.md" ]] || fail "$EXTENSION_ROOT/agents/README.md must not exist in the installed extension runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/skills/lead/SKILL.md" ]] || fail "$LEGACY_RUNTIME_ROOT/skills/lead/SKILL.md should not exist in the installed runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/skills/init-project/SKILL.md" ]] || fail "$LEGACY_RUNTIME_ROOT/skills/init-project/SKILL.md should not exist in the installed runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/agents/lead.md" ]] || fail "$LEGACY_RUNTIME_ROOT/agents/lead.md should not exist in the installed runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/agents/team-templates/quick-fix.json" ]] || fail "$LEGACY_RUNTIME_ROOT/agents/team-templates/quick-fix.json should not exist in the installed runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/commands/agents/help.toml" ]] || fail "$LEGACY_RUNTIME_ROOT/commands/agents/help.toml should not exist in the installed runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/commands/agents/external-brigade.toml" ]] || fail "$LEGACY_RUNTIME_ROOT/commands/agents/external-brigade.toml should not exist in the installed runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/commands/agents/init-project.toml" ]] || fail "$LEGACY_RUNTIME_ROOT/commands/agents/init-project.toml should not exist in the installed runtime"
fi

for role in "${skill_roles[@]}"; do
  [[ -f "$PACK_ROOT/skills/$role/SKILL.md" ]] || fail "missing skill role $PACK_ROOT/skills/$role/SKILL.md"
done

for role in "${agent_roles[@]}"; do
  [[ -f "$PACK_ROOT/agents/$role.md" ]] || fail "missing agent role $PACK_ROOT/agents/$role.md"
done

[[ ! -e "$PACK_ROOT/agents/README.md" ]] || fail "$PACK_ROOT/agents/README.md must not exist; all top-level agents/*.md files are loader-visible agent definitions"

shopt -s nullglob
for agent_md in "$PACK_ROOT"/agents/*.md; do
  first_line="$(head -n 1 "$agent_md" || true)"
  [[ "$first_line" == "---" ]] || fail "agent markdown must start with YAML frontmatter: $agent_md"
done
shopt -u nullglob

for template in "${team_templates[@]}"; do
  [[ -f "$PACK_ROOT/agents/team-templates/$template.json" ]] || fail "missing team template $PACK_ROOT/agents/team-templates/$template.json"
done

IMPORT_ROOT="$(dirname "$GEMINI_FILE")"
while IFS= read -r import_line; do
  import_target="${import_line#@}"
  [[ -z "$import_target" ]] && continue
  [[ -f "$IMPORT_ROOT/$import_target" ]] || fail "GEMINI.md import target missing: $IMPORT_ROOT/$import_target"
done < <(grep '^@' "$GEMINI_FILE" || true)

if [[ "$MODE" != "source" ]]; then
  EXTENSION_IMPORT_ROOT="$(dirname "$EXTENSION_GEMINI_FILE")"
  while IFS= read -r import_line; do
    import_target="${import_line#@}"
    [[ -z "$import_target" ]] && continue
    [[ -f "$EXTENSION_IMPORT_ROOT/$import_target" ]] || fail "extension GEMINI.md import target missing: $EXTENSION_IMPORT_ROOT/$import_target"
  done < <(grep '^@' "$EXTENSION_GEMINI_FILE" || true)
fi

if [[ "$MODE" == "source" ]]; then
  grep -q '^@\./AGENTS\.shared\.md$' "$GEMINI_FILE" || fail "source GEMINI.md should import @./AGENTS.shared.md"
else
  grep -q '^@\./AGENTS\.md$' "$GEMINI_FILE" || fail "installed GEMINI.md should import @./AGENTS.md"
  grep -q '^@\./AGENTS\.md$' "$EXTENSION_GEMINI_FILE" || fail "installed extension GEMINI.md should import @./AGENTS.md"
fi
grep -q '/init' "$GEMINI_FILE" || fail "GEMINI.md should mention the official Gemini /init bootstrap path"
grep -q '\.gemini/settings\.json' "$GEMINI_FILE" || fail "GEMINI.md should mention .gemini/settings.json as the official Gemini runtime-state surface"
grep -q 'agents/team-templates/' "$GEMINI_FILE" || fail "GEMINI.md should mention agents/team-templates/"
grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$EXTENSION_README_FILE" || fail "Gemini extension README should mark Gemini as not recommended example-only routing"
grep -q 'cannot recursively call' "$PACK_ROOT/skills/lead/SKILL.md" || fail "lead skill should state the Gemini subagent recursion constraint"
grep -q 'main Gemini session' "$PACK_ROOT/skills/lead/SKILL.md" || fail "lead skill should identify the main Gemini session as orchestration owner"
grep -q 'external-brigade' "$PACK_ROOT/skills/lead/SKILL.md" || fail "lead skill should mention the external-brigade utility"
grep -q 'agents/team-templates' "$PACK_ROOT/commands/agents/help.toml" || fail "help command should describe the team-template layer"
grep -q 'external-brigade' "$PACK_ROOT/commands/agents/help.toml" || fail "help command should describe the external-brigade surface"
! grep -Fq 'consultantMode: auto' "$PACK_ROOT/skills/second-opinion/SKILL.md" || fail "second-opinion skill should not expose consultantMode auto"
! grep -Fq 'allowed: external | auto | internal | disabled' "$PACK_ROOT/skills/init-project/SKILL.md" || fail "init-project skill should restrict consultantMode to external/internal/disabled"
! grep -Fq 'allowed: external | auto | internal | disabled' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should restrict consultantMode to external/internal/disabled"
! grep -Fq 'fallback approved by user' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should not record consultant fallback approvals"
grep -Fq 'normalize it to the current canonical format before presenting or trusting any values.' "$PACK_ROOT/skills/init-project/SKILL.md" || fail "init-project should normalize agents-mode before reading values"
grep -Fq 'Any read of `.gemini/.agents-mode.yaml` that drives a decision should normalize the file to the current canonical format before trusting the flags.' "$PACK_ROOT/skills/init-project/SKILL.md" || fail "init-project should require read-time agents-mode normalization"
grep -Fq 'read and normalize `.gemini/.agents-mode.yaml`, then print the current resolved values' "$PACK_ROOT/skills/second-opinion/SKILL.md" || fail "second-opinion should normalize agents-mode before reporting status"
grep -Fq 'Read and normalize `.gemini/.agents-mode.yaml` before routing.' "$PACK_ROOT/skills/consultant/SKILL.md" || fail "consultant should normalize agents-mode before routing"
grep -Fq 'externalModelMode' "$PACK_ROOT/skills/consultant/SKILL.md" || fail "consultant should document shared external model policy"
grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$PACK_ROOT/skills/consultant/SKILL.md" || fail "consultant should mark Gemini as not recommended example-only routing"
grep -Fq 'Any read of `.gemini/.agents-mode.yaml` that influences routing must normalize an existing file to the current canonical format before trusting the flags.' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should require read-time agents-mode normalization"
grep -Fq 'externalModelMode' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should document shared external model policy"
grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should mark Gemini as not recommended example-only routing"
if [[ "$MODE" == "source" ]]; then
  grep -Fq 'Adapter host runtime' "$SHARED_SOURCE_FILE" && fail "shared governance should not allow adapter-host metadata for external execution"
  grep -Fq 'must use direct external launch' "$SHARED_SOURCE_FILE" || fail "shared governance should require direct external launch"
  grep -Fq 'substantive task prompt must use file-based prompt delivery' "$SHARED_SOURCE_FILE" || fail "shared governance should require file-based external CLI prompts"
  grep -Fq 'verify every subagent result before accepting it' "$SHARED_SOURCE_FILE" || fail "shared governance should require verification before trusting subagent results"
  grep -Fq 'Documentation terminology discipline' "$SHARED_SOURCE_FILE" || fail "shared governance should require terminology and abbreviation explanations in documents"
else
  grep -Fq 'Adapter host runtime' "$RUNTIME_AGENTS_FILE" && fail "shared governance should not allow adapter-host metadata for external execution"
  grep -Fq 'must use direct external launch' "$RUNTIME_AGENTS_FILE" || fail "shared governance should require direct external launch"
  grep -Fq 'substantive task prompt must use file-based prompt delivery' "$RUNTIME_AGENTS_FILE" || fail "shared governance should require file-based external CLI prompts"
  grep -Fq 'verify every subagent result before accepting it' "$RUNTIME_AGENTS_FILE" || fail "shared governance should require verification before trusting subagent results"
  grep -Fq 'Documentation terminology discipline' "$RUNTIME_AGENTS_FILE" || fail "shared governance should require terminology and abbreviation explanations in documents"
fi
grep -Fq 'Adapter host runtime:' "$PACK_ROOT/skills/lead/external-dispatch.md" && fail "external-dispatch should not record adapter host runtime"
grep -Fq 'must use direct external launch' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should require direct external launch"
grep -Fq 'substantive task prompt must use file-based prompt delivery' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should require file-based external CLI prompts"
grep -Fq 'Read and normalize `.gemini/.agents-mode.yaml` to the current canonical format before trusting its flags.' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should normalize agents-mode before routing"
grep -Fq 'Read and normalize `.gemini/.agents-mode.yaml` to the current canonical format before trusting its flags.' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should normalize agents-mode before routing"
grep -Fq 'externalPriorityProfile' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should honor structured profile keys"
grep -Fq 'externalPriorityProfile' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should honor structured profile keys"
grep -Fq 'externalModelMode' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should honor shared external model policy"
grep -Fq 'externalModelMode' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should honor shared external model policy"
grep -Fq 'file-based prompt delivery' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should require file-based external CLI prompts"
grep -Fq 'file-based prompt delivery' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should require file-based external CLI prompts"
grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should mark Gemini as not recommended example-only routing"
grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should mark Gemini as not recommended example-only routing"
grep -Fq 'direct external launch contract' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should require direct external launch"
grep -Fq 'direct external launch contract' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should require direct external launch"
grep -Fq 'externalModelMode' "$PACK_ROOT/skills/external-brigade/SKILL.md" || fail "external-brigade should document shared external model policy"
grep -Fq 'same-provider brigade items may run in parallel' "$PACK_ROOT/skills/external-brigade/SKILL.md" || fail "external-brigade should document same-provider parallel reuse"
grep -Fq 'It does not cap how many same-provider brigade items may run in parallel' "$PACK_ROOT/skills/external-brigade/SKILL.md" || fail "external-brigade should keep opinion counts separate from concurrency"
grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$GEMINI_FILE" || fail "GEMINI.md should mark Gemini as a not recommended example-only pack"
grep -Fq 'manual `WEAK MODEL / NOT RECOMMENDED` example or compatibility path only' "$PACK_ROOT/commands/agents/help.toml" || fail "help command should describe Gemini and Qwen as manual not-recommended example-only paths"
grep -Fq 'Gemini and Qwen are `WEAK MODEL / NOT RECOMMENDED` on this line' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should mark Gemini and Qwen as not recommended example-only routing"

if grep -R -n -E --exclude='validate-pack.sh' 'gemini-crosscheck|externalGeminiFallbackMode|externalGeminiWorkdirMode' "$PACK_ROOT" >/dev/null 2>&1; then
  fail "retired Gemini-specific production schema keys or profiles should not remain in the Gemini pack"
fi

if [[ "$MODE" == "source" ]]; then
  grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$ROOT/references-gemini/subagent-operating-model.md" || fail "references-gemini should mark Gemini as a not recommended example-only integration"
  grep -Fq 'example-only / WEAK MODEL / NOT RECOMMENDED' "$ROOT/scripts/install-gemini.sh" || fail "install-gemini.sh should announce example-only Gemini policy"
  grep -Fq 'example-only / WEAK MODEL / NOT RECOMMENDED' "$ROOT/scripts/install-gemini.ps1" || fail "install-gemini.ps1 should announce example-only Gemini policy"
fi

if [[ "$MODE" == "source" && -f "$ROOT/docs/agents-mode-reference.md" ]]; then
  grep -Fq '## Canonical maintenance' "$ROOT/docs/agents-mode-reference.md" || fail "agents-mode reference should define canonical maintenance"
  grep -Fq 'Read-time normalization preserves the effective values of known keys' "$ROOT/docs/agents-mode-reference.md" || fail "agents-mode reference should document read-time normalization semantics"
  [[ -f "$ROOT/shared/agents-mode.defaults.yaml" ]] || fail "shared agents-mode defaults exemplar should exist"
  for lane in advisory.repo-understanding advisory.design-adr review.pre-pr review.performance-architecture review.visual; do
    grep -Fq "    $lane: [claude, codex, claude-secret]" "$ROOT/shared/agents-mode.defaults.yaml" || fail "shared defaults should keep claude-secret last on $lane"
  done
  ! grep -E '^[[:space:]]{4}worker\.[^:]+: \[[^]]*(claude-secret|gemini|qwen)' "$ROOT/shared/agents-mode.defaults.yaml" >/dev/null || fail "shared defaults should keep worker lanes off claude-secret/Gemini/Qwen"
  [[ ! -e "$ROOT/src.gemini/agents-mode.defaults.yaml" ]] || fail "src.gemini/agents-mode.defaults.yaml should not exist in the monorepo"
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

json_targets+=("$EXTENSION_MANIFEST_FILE")

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

grep -q '"contextFileName": "GEMINI.md"' "$EXTENSION_MANIFEST_FILE" || fail "extension manifest should declare contextFileName GEMINI.md"

echo "PASS: Gemini $MODE tree present at $PACK_ROOT"

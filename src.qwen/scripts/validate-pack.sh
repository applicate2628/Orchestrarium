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

if [[ -d "$ROOT/src.qwen" ]]; then
  MODE="source"
  PACK_ROOT="$ROOT/src.qwen"
  QWEN_FILE="$PACK_ROOT/QWEN.md"
  SHARED_SOURCE_FILE="$PACK_ROOT/AGENTS.shared.md"
  RUNTIME_AGENTS_FILE="$PACK_ROOT/AGENTS.md"
  LEGACY_RUNTIME_ROOT=""
elif [[ -f "$ROOT/QWEN.md" && -d "$ROOT/extensions/orchestrarium-qwen" ]]; then
  MODE="installed-root"
  PACK_ROOT="$ROOT/extensions/orchestrarium-qwen"
  QWEN_FILE="$ROOT/QWEN.md"
  SHARED_SOURCE_FILE="$ROOT/AGENTS.shared.md"
  RUNTIME_AGENTS_FILE="$ROOT/AGENTS.md"
  LEGACY_RUNTIME_ROOT="$ROOT"
elif [[ -f "$ROOT/QWEN.md" && -d "$ROOT/.qwen/extensions/orchestrarium-qwen" ]]; then
  MODE="installed-project"
  PACK_ROOT="$ROOT/.qwen/extensions/orchestrarium-qwen"
  QWEN_FILE="$ROOT/QWEN.md"
  SHARED_SOURCE_FILE="$ROOT/AGENTS.shared.md"
  RUNTIME_AGENTS_FILE="$ROOT/AGENTS.md"
  LEGACY_RUNTIME_ROOT="$ROOT/.qwen"
else
  fail "unable to detect Qwen source tree or installed runtime under $ROOT"
fi

if [[ "$MODE" == "source" ]]; then
  EXTENSION_ROOT="$PACK_ROOT/extension"
else
  EXTENSION_ROOT="$PACK_ROOT"
fi

EXTENSION_MANIFEST_FILE="$EXTENSION_ROOT/qwen-extension.json"
EXTENSION_README_FILE="$EXTENSION_ROOT/README.md"
EXTENSION_QWEN_FILE="$EXTENSION_ROOT/QWEN.md"
EXTENSION_AGENTS_FILE="$EXTENSION_ROOT/AGENTS.md"

required_common=(
  "$QWEN_FILE"
  "$PACK_ROOT/skills/README.md"
  "$PACK_ROOT/skills/lead/SKILL.md"
  "$PACK_ROOT/skills/init-project/SKILL.md"
  "$PACK_ROOT/skills/external-brigade/SKILL.md"
  "$PACK_ROOT/commands/agents/help.md"
  "$PACK_ROOT/commands/agents/external-brigade.md"
  "$PACK_ROOT/commands/agents/init-project.md"
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
  [[ -f "$EXTENSION_QWEN_FILE" ]] || fail "missing installed extension context $EXTENSION_QWEN_FILE"
  [[ -f "$EXTENSION_AGENTS_FILE" ]] || fail "missing installed extension governance $EXTENSION_AGENTS_FILE"
  [[ -f "$EXTENSION_ROOT/skills/README.md" ]] || fail "missing installed extension skills readme $EXTENSION_ROOT/skills/README.md"
  [[ -f "$EXTENSION_ROOT/skills/lead/SKILL.md" ]] || fail "missing installed extension lead skill $EXTENSION_ROOT/skills/lead/SKILL.md"
  [[ -f "$EXTENSION_ROOT/skills/init-project/SKILL.md" ]] || fail "missing installed extension init-project skill $EXTENSION_ROOT/skills/init-project/SKILL.md"
  [[ -f "$EXTENSION_ROOT/commands/agents/help.md" ]] || fail "missing installed extension help command $EXTENSION_ROOT/commands/agents/help.md"
  [[ -f "$EXTENSION_ROOT/commands/agents/external-brigade.md" ]] || fail "missing installed extension brigade command $EXTENSION_ROOT/commands/agents/external-brigade.md"
  [[ -f "$EXTENSION_ROOT/commands/agents/init-project.md" ]] || fail "missing installed extension init-project command $EXTENSION_ROOT/commands/agents/init-project.md"
  [[ -f "$EXTENSION_ROOT/agents/lead.md" ]] || fail "missing installed extension lead agent $EXTENSION_ROOT/agents/lead.md"
  [[ -f "$EXTENSION_ROOT/agents/team-templates/quick-fix.json" ]] || fail "missing installed extension team template $EXTENSION_ROOT/agents/team-templates/quick-fix.json"
  [[ ! -e "$EXTENSION_ROOT/AGENTS.shared.md" ]] || fail "$EXTENSION_ROOT/AGENTS.shared.md should not exist in the installed extension runtime"
  [[ ! -e "$EXTENSION_ROOT/agents/README.md" ]] || fail "$EXTENSION_ROOT/agents/README.md must not exist in the installed extension runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/skills/lead/SKILL.md" ]] || fail "$LEGACY_RUNTIME_ROOT/skills/lead/SKILL.md should not exist in the installed runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/skills/init-project/SKILL.md" ]] || fail "$LEGACY_RUNTIME_ROOT/skills/init-project/SKILL.md should not exist in the installed runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/agents/lead.md" ]] || fail "$LEGACY_RUNTIME_ROOT/agents/lead.md should not exist in the installed runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/agents/team-templates/quick-fix.json" ]] || fail "$LEGACY_RUNTIME_ROOT/agents/team-templates/quick-fix.json should not exist in the installed runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/commands/agents/help.md" ]] || fail "$LEGACY_RUNTIME_ROOT/commands/agents/help.md should not exist in the installed runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/commands/agents/external-brigade.md" ]] || fail "$LEGACY_RUNTIME_ROOT/commands/agents/external-brigade.md should not exist in the installed runtime"
  [[ ! -e "$LEGACY_RUNTIME_ROOT/commands/agents/init-project.md" ]] || fail "$LEGACY_RUNTIME_ROOT/commands/agents/init-project.md should not exist in the installed runtime"
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

IMPORT_ROOT="$(dirname "$QWEN_FILE")"
while IFS= read -r import_line; do
  import_target="${import_line#@}"
  [[ -z "$import_target" ]] && continue
  [[ -f "$IMPORT_ROOT/$import_target" ]] || fail "QWEN.md import target missing: $IMPORT_ROOT/$import_target"
done < <(grep '^@' "$QWEN_FILE" || true)

if [[ "$MODE" != "source" ]]; then
  EXTENSION_IMPORT_ROOT="$(dirname "$EXTENSION_QWEN_FILE")"
  while IFS= read -r import_line; do
    import_target="${import_line#@}"
    [[ -z "$import_target" ]] && continue
    [[ -f "$EXTENSION_IMPORT_ROOT/$import_target" ]] || fail "extension QWEN.md import target missing: $EXTENSION_IMPORT_ROOT/$import_target"
  done < <(grep '^@' "$EXTENSION_QWEN_FILE" || true)
fi

if [[ "$MODE" == "source" ]]; then
  grep -q '^@\./AGENTS\.shared\.md$' "$QWEN_FILE" || fail "source QWEN.md should import @./AGENTS.shared.md"
else
  grep -q '^@\./AGENTS\.md$' "$QWEN_FILE" || fail "installed QWEN.md should import @./AGENTS.md"
  grep -q '^@\./AGENTS\.md$' "$EXTENSION_QWEN_FILE" || fail "installed extension QWEN.md should import @./AGENTS.md"
fi

grep -q '/init' "$QWEN_FILE" || fail "QWEN.md should mention the official Qwen /init bootstrap path"
grep -q '\.qwen/settings\.json' "$QWEN_FILE" || fail "QWEN.md should mention .qwen/settings.json as the official Qwen runtime-state surface"
grep -q 'agents/team-templates/' "$QWEN_FILE" || fail "QWEN.md should mention agents/team-templates/"
grep -Fq 'commands/` carries Markdown-based Qwen custom commands' "$QWEN_FILE" || fail "QWEN.md should describe Markdown-based commands"
grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$QWEN_FILE" || fail "QWEN.md should mark Qwen as not recommended example-only routing"
grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$EXTENSION_README_FILE" || fail "Qwen extension README should mark Qwen as not recommended example-only routing"
if [[ "$MODE" == "source" ]]; then
  grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$PACK_ROOT/README.md" || fail "Qwen README should mark Qwen as not recommended example-only routing"
  grep -Fq '## Repository Layout' "$PACK_ROOT/README.md" || fail "Qwen README should include a repository layout section"
  grep -Fq '## Current Scope' "$PACK_ROOT/README.md" || fail "Qwen README should include a current scope section"
  grep -Fq '## Qwen Bootstrap Model' "$PACK_ROOT/README.md" || fail "Qwen README should include a bootstrap model section"
fi
grep -q 'main Qwen session' "$PACK_ROOT/skills/lead/SKILL.md" || fail "lead skill should identify the main Qwen session as orchestration owner"
grep -q 'external-brigade' "$PACK_ROOT/skills/lead/SKILL.md" || fail "lead skill should mention the external-brigade utility"
grep -q 'agents/team-templates' "$PACK_ROOT/commands/agents/help.md" || fail "help command should describe the team-template layer"
grep -q 'external-brigade' "$PACK_ROOT/commands/agents/help.md" || fail "help command should describe the external-brigade surface"

! grep -Fq 'consultantMode: auto' "$PACK_ROOT/skills/second-opinion/SKILL.md" || fail "second-opinion skill should not expose consultantMode auto"
! grep -Fq 'allowed: external | auto | internal | disabled' "$PACK_ROOT/skills/init-project/SKILL.md" || fail "init-project skill should restrict consultantMode to external/internal/disabled"
! grep -Fq 'allowed: external | auto | internal | disabled' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should restrict consultantMode to external/internal/disabled"
! grep -Fq 'fallback approved by user' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should not record consultant fallback approvals"

grep -Fq 'normalize it to the current canonical format before presenting or trusting any values.' "$PACK_ROOT/skills/init-project/SKILL.md" || fail "init-project should normalize agents-mode before reading values"
grep -Fq 'Any read of `.qwen/.agents-mode.yaml` that drives a decision should normalize the file to the current canonical format before trusting the flags.' "$PACK_ROOT/skills/init-project/SKILL.md" || fail "init-project should require read-time agents-mode normalization"
grep -Fq 'read and normalize `.qwen/.agents-mode.yaml`, then print the current resolved values' "$PACK_ROOT/skills/second-opinion/SKILL.md" || fail "second-opinion should normalize agents-mode before reporting status"
grep -Fq 'Read and normalize `.qwen/.agents-mode.yaml` before routing.' "$PACK_ROOT/skills/consultant/SKILL.md" || fail "consultant should normalize agents-mode before routing"

grep -Fq 'externalModelMode' "$PACK_ROOT/skills/consultant/SKILL.md" || fail "consultant should document shared external model policy"
grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$PACK_ROOT/skills/consultant/SKILL.md" || fail "consultant should mark Qwen/Gemini as not recommended example-only routing"
! grep -Fq 'externalQwenFallbackMode' "$PACK_ROOT/skills/consultant/SKILL.md" || fail "consultant should not document invented Qwen fallback keys"
grep -Fq 'Any read of `.qwen/.agents-mode.yaml` that influences routing must normalize an existing file to the current canonical format before trusting the flags.' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should require read-time agents-mode normalization"
grep -Fq 'externalModelMode' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should document shared external model policy"
grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should mark Qwen/Gemini as not recommended example-only routing"
grep -Fq 'Gemini and Qwen must not be profile entries' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should forbid Gemini/Qwen profile entries"
! grep -Fq 'externalQwenFallbackMode' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should not document invented Qwen fallback keys"

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

grep -Fq 'Read and normalize `.qwen/.agents-mode.yaml` to the current canonical format before trusting its flags.' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should normalize agents-mode before routing"
grep -Fq 'Read and normalize `.qwen/.agents-mode.yaml` to the current canonical format before trusting its flags.' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should normalize agents-mode before routing"
grep -Fq 'externalPriorityProfile' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should honor structured profile keys"
grep -Fq 'externalPriorityProfile' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should honor structured profile keys"
grep -Fq 'externalModelMode' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should honor shared external model policy"
grep -Fq 'externalModelMode' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should honor shared external model policy"
grep -Fq 'file-based prompt delivery' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should require file-based external CLI prompts"
grep -Fq 'file-based prompt delivery' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should require file-based external CLI prompts"
grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should mark Qwen/Gemini as not recommended example-only routing"
grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should mark Qwen/Gemini as not recommended example-only routing"
grep -Fq 'do not place Qwen inside any `auto` profile' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should forbid Qwen profile entries"
grep -Fq 'do not place Qwen inside any `auto` profile' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should forbid Qwen profile entries"
! grep -Fq 'externalQwenFallbackMode' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should not honor invented Qwen fallback keys"
! grep -Fq 'externalQwenFallbackMode' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should not honor invented Qwen fallback keys"
grep -Fq 'direct external launch contract' "$PACK_ROOT/skills/external-worker/SKILL.md" || fail "external-worker should require direct external launch"
grep -Fq 'direct external launch contract' "$PACK_ROOT/skills/external-reviewer/SKILL.md" || fail "external-reviewer should require direct external launch"
grep -Fq 'externalModelMode' "$PACK_ROOT/skills/external-brigade/SKILL.md" || fail "external-brigade should document shared external model policy"
grep -Fq 'same-provider brigade items may run in parallel' "$PACK_ROOT/skills/external-brigade/SKILL.md" || fail "external-brigade should document same-provider parallel reuse"
grep -Fq 'It does not cap how many same-provider brigade items may run in parallel' "$PACK_ROOT/skills/external-brigade/SKILL.md" || fail "external-brigade should keep opinion counts separate from concurrency"

grep -Fq 'externalProvider: qwen' "$PACK_ROOT/skills/init-project/SKILL.md" || fail "init-project should document explicit qwen provider override"
grep -Fq 'externalProvider: gemini' "$PACK_ROOT/skills/init-project/SKILL.md" || fail "init-project should document explicit gemini provider override"
grep -Fq 'shipped production `auto` routing stays `codex | claude`' "$PACK_ROOT/skills/init-project/SKILL.md" || fail "init-project should preserve the production auto-routing contract"
grep -Fq 'Shipped production `auto` profiles stay on `codex | claude` only.' "$PACK_ROOT/skills/lead/external-dispatch.md" || fail "external-dispatch should preserve the production auto-routing contract"

if [[ "$MODE" == "source" && -f "$ROOT/docs/agents-mode-reference.md" ]]; then
  grep -Fq '## Canonical maintenance' "$ROOT/docs/agents-mode-reference.md" || fail "agents-mode reference should define canonical maintenance"
  grep -Fq 'Read-time normalization preserves the effective values of known keys' "$ROOT/docs/agents-mode-reference.md" || fail "agents-mode reference should document read-time normalization semantics"
  grep -Fq 'WEAK MODEL / NOT RECOMMENDED' "$ROOT/references-qwen/subagent-operating-model.md" || fail "references-qwen should mark Qwen as a not recommended example-only integration"
  grep -Fq '## Shared core now owns' "$ROOT/references-qwen/subagent-operating-model.md" || fail "references-qwen should include shared-core ownership parity with Gemini"
  grep -Fq 'Qwen | `~/.qwen/`' "$ROOT/docs/provider-runtime-layouts.md" || fail "provider runtime layouts should include Qwen in the quick comparison"
  grep -Fq 'Global context file | `~/.qwen/QWEN.md`' "$ROOT/docs/provider-runtime-layouts.md" || fail "provider runtime layouts should include Qwen global runtime details"
  ! grep -Fq 'Qwen is intentionally not listed' "$ROOT/docs/provider-runtime-layouts.md" || fail "provider runtime layouts should not describe Qwen as incomplete"
  grep -Fq '../src.qwen/README.md' "$ROOT/docs/README.md" || fail "docs index should link the Qwen source subtree"
  grep -Fq '../references-qwen/README.md' "$ROOT/docs/README.md" || fail "docs index should link the Qwen references subtree"
  grep -Fq 'example-only / WEAK MODEL / NOT RECOMMENDED' "$ROOT/scripts/install-qwen.sh" || fail "install-qwen.sh should announce example-only Qwen policy"
  grep -Fq 'example-only / WEAK MODEL / NOT RECOMMENDED' "$ROOT/scripts/install-qwen.ps1" || fail "install-qwen.ps1 should announce example-only Qwen policy"
  [[ -f "$ROOT/shared/agents-mode.defaults.yaml" ]] || fail "shared agents-mode defaults exemplar should exist"
  for lane in advisory.repo-understanding advisory.design-adr review.pre-pr review.performance-architecture review.visual; do
    grep -Fq "    $lane: [claude, codex, claude-secret]" "$ROOT/shared/agents-mode.defaults.yaml" || fail "shared defaults should keep claude-secret last on $lane"
  done
  ! grep -E '^[[:space:]]{4}worker\.[^:]+: \[[^]]*(claude-secret|gemini|qwen)' "$ROOT/shared/agents-mode.defaults.yaml" >/dev/null || fail "shared defaults should keep worker lanes off claude-secret/Gemini/Qwen"
  [[ ! -e "$ROOT/src.qwen/agents-mode.defaults.yaml" ]] || fail "src.qwen/agents-mode.defaults.yaml should not exist in the monorepo"
fi

start_count="$(grep -cF '<!-- ORCHESTRARIUM_QWEN_PACK:START -->' "$QWEN_FILE" || true)"
end_count="$(grep -cF '<!-- ORCHESTRARIUM_QWEN_PACK:END -->' "$QWEN_FILE" || true)"
[[ "$start_count" -eq 1 && "$end_count" -eq 1 ]] || fail "QWEN.md should contain exactly one managed Orchestrarium pack block"

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
  fail "python or python3 is required to validate Qwen JSON surfaces"
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
  "$EXTENSION_MANIFEST_FILE"
)

"$PYTHON_BIN" - "$EXTENSION_MANIFEST_FILE" "${json_targets[@]}" <<'PY'
import json
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
json_paths = [Path(path) for path in sys.argv[2:]]

with manifest_path.open("r", encoding="utf-8") as fh:
    manifest = json.load(fh)

required_pairs = {
    "contextFileName": "QWEN.md",
    "commands": "commands",
    "skills": "skills",
    "agents": "agents",
}
for key, value in required_pairs.items():
    if manifest.get(key) != value:
        print(f"FAIL: extension manifest must set {key}={value!r}")
        sys.exit(1)

for json_path in json_paths:
    with json_path.open("r", encoding="utf-8") as fh:
        json.load(fh)
PY

stale_pattern='help\.toml|init-project\.toml|external-brigade\.toml|externalQwenFallbackMode|externalQwenWorkdirMode|gemini-3\.1-pro|gemini-3-flash|gemini-crosscheck|orchestrarium-gemini|gemini-extension\.json|cannot recursively call'
stale_targets=(
  "$PACK_ROOT/AGENTS.shared.md"
  "$PACK_ROOT/QWEN.md"
  "$PACK_ROOT/README.md"
  "$PACK_ROOT/agents"
  "$PACK_ROOT/commands"
  "$PACK_ROOT/extension"
  "$PACK_ROOT/skills"
)

if command -v rg >/dev/null 2>&1; then
  stale_hits="$(rg -n "$stale_pattern" "${stale_targets[@]}" -S || true)"
else
  stale_hits="$(grep -RInE "$stale_pattern" "${stale_targets[@]}" 2>/dev/null || true)"
fi
[[ -z "$stale_hits" ]] || fail "stale copied Gemini-era semantics remain in Qwen pack surfaces:\n$stale_hits"

echo "PASS: Qwen $MODE tree present at $PACK_ROOT"

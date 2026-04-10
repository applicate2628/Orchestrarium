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

"$PYTHON_BIN" - "$PACK_ROOT/commands/agents/help.toml" "$PACK_ROOT/commands/agents/init-project.toml" "${json_targets[@]}" <<'PY'
import json
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    print("FAIL: Python tomllib is unavailable; cannot validate Gemini TOML syntax")
    sys.exit(1)

toml_paths = [Path(sys.argv[1]), Path(sys.argv[2])]
json_paths = [Path(path) for path in sys.argv[3:]]

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

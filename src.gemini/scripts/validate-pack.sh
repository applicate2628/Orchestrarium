#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"

MODE=""
PACK_ROOT=""
RUNTIME_ROOT=""
GEMINI_FILE=""

if [[ -d "$ROOT/src.gemini" ]]; then
  MODE="source"
  PACK_ROOT="$ROOT/src.gemini"
  GEMINI_FILE="$PACK_ROOT/GEMINI.md"
  RUNTIME_ROOT="$PACK_ROOT"
elif [[ -f "$ROOT/GEMINI.md" && -d "$ROOT/.gemini" ]]; then
  MODE="project-install"
  GEMINI_FILE="$ROOT/GEMINI.md"
  RUNTIME_ROOT="$ROOT/.gemini"
elif [[ -f "$ROOT/GEMINI.md" && -d "$ROOT/skills" && -d "$ROOT/commands" ]]; then
  MODE="global-install"
  GEMINI_FILE="$ROOT/GEMINI.md"
  RUNTIME_ROOT="$ROOT"
else
  echo "FAIL: unsupported Gemini layout at $ROOT"
  exit 1
fi

required=(
  "$GEMINI_FILE"
  "$(dirname "$GEMINI_FILE")/AGENTS.shared.md"
  "$RUNTIME_ROOT/skills/README.md"
  "$RUNTIME_ROOT/skills/lead/SKILL.md"
  "$RUNTIME_ROOT/skills/init-project/SKILL.md"
  "$RUNTIME_ROOT/commands/agents/help.toml"
  "$RUNTIME_ROOT/commands/agents/init-project.toml"
)

if [[ "$MODE" == "source" ]]; then
  required+=(
    "$PACK_ROOT/README.md"
    "$PACK_ROOT/extension/README.md"
    "$PACK_ROOT/extension/gemini-extension.json"
    "$ROOT/references-gemini/README.md"
    "$ROOT/references-gemini/evidence-based-answer-pipeline.md"
    "$ROOT/references-gemini/operating-model-diagram.md"
    "$ROOT/references-gemini/periodic-control-matrix.md"
    "$ROOT/references-gemini/repository-publication-safety.md"
    "$ROOT/references-gemini/repository-task-memory.md"
    "$ROOT/references-gemini/subagent-operating-model.md"
    "$ROOT/references-gemini/workflow-strategy-comparison.md"
    "$ROOT/references-gemini/ru/operating-model-diagram.md"
    "$ROOT/references-gemini/ru/periodic-control-matrix.md"
    "$ROOT/references-gemini/ru/repository-publication-safety.md"
    "$ROOT/references-gemini/ru/repository-task-memory.md"
    "$ROOT/references-gemini/ru/subagent-operating-model.md"
    "$ROOT/references-gemini/ru/workflow-strategy-comparison.md"
    "$ROOT/install-gemini.sh"
    "$ROOT/install-gemini.ps1"
  )
fi

for path in "${required[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "FAIL: missing $path"
    exit 1
  fi
done

IMPORT_ROOT="$(dirname "$GEMINI_FILE")"

while IFS= read -r import_line; do
  import_target="${import_line#@}"
  if [[ -z "$import_target" ]]; then
    continue
  fi
  if [[ ! -f "$IMPORT_ROOT/$import_target" ]]; then
    echo "FAIL: GEMINI.md import target missing: $IMPORT_ROOT/$import_target"
    exit 1
  fi
done < <(grep '^@' "$GEMINI_FILE" || true)

if [[ "$MODE" == "source" ]]; then
  if [[ ! -f "$ROOT/docs/agents-mode-reference.md" ]]; then
    echo "FAIL: source Gemini pack surface requires $ROOT/docs/agents-mode-reference.md for init-project overlay guidance"
    exit 1
  fi

  if [[ ! -f "$ROOT/docs/README.md" ]]; then
    echo "FAIL: source Gemini pack surface requires $ROOT/docs/README.md for branch-level docs entrypoint"
    exit 1
  fi

  if [[ ! -f "$ROOT/docs/provider-runtime-layout.md" ]]; then
    echo "FAIL: source Gemini pack surface requires $ROOT/docs/provider-runtime-layout.md for branch-level runtime-layout guidance"
    exit 1
  fi

  forbidden_root_paths=(
    "$ROOT/AGENTS.md"
    "$ROOT/CLAUDE.md"
    "$ROOT/cross-pack-reconciliation.md"
    "$ROOT/install.sh"
    "$ROOT/install.ps1"
    "$ROOT/RELEASE_NOTES.md"
    "$ROOT/shared"
    "$ROOT/references-codex"
    "$ROOT/references-claude"
    "$ROOT/src.codex"
    "$ROOT/src.claude"
  )

  for path in "${forbidden_root_paths[@]}"; do
    if [[ -e "$path" ]]; then
      echo "FAIL: standalone Gemini branch should not contain $path"
      exit 1
    fi
  done
fi

if ! grep -q '/init' "$GEMINI_FILE"; then
  echo "FAIL: GEMINI.md should mention the official Gemini /init bootstrap path"
  exit 1
fi

if ! grep -q '\.gemini/settings\.json' "$GEMINI_FILE"; then
  echo "FAIL: GEMINI.md should mention .gemini/settings.json as the official Gemini runtime-state surface"
  exit 1
fi

start_count="$(grep -cF '<!-- ORCHESTRARIUM_GEMINI_PACK:START -->' "$GEMINI_FILE" || true)"
end_count="$(grep -cF '<!-- ORCHESTRARIUM_GEMINI_PACK:END -->' "$GEMINI_FILE" || true)"
if [[ "$start_count" -ne 1 || "$end_count" -ne 1 ]]; then
  echo "FAIL: GEMINI.md should contain exactly one managed Orchestrarium pack block"
  exit 1
fi

for skill in "$RUNTIME_ROOT/skills/lead/SKILL.md" "$RUNTIME_ROOT/skills/init-project/SKILL.md"; do
  if ! grep -q '^---$' "$skill"; then
    echo "FAIL: missing frontmatter in $skill"
    exit 1
  fi
  if ! grep -q '^name:' "$skill"; then
    echo "FAIL: missing skill name in $skill"
    exit 1
  fi
  if ! grep -q '^description:' "$skill"; then
    echo "FAIL: missing skill description in $skill"
    exit 1
  fi
done

if [[ "$MODE" == "source" ]]; then
  if [[ -e "$PACK_ROOT/AGENTS.md" ]]; then
    echo "FAIL: $PACK_ROOT/AGENTS.md should not exist in the preferred Gemini pack surface"
    exit 1
  fi

  if [[ -e "$PACK_ROOT/agents" ]]; then
    echo "FAIL: $PACK_ROOT/agents should not exist in the preferred Gemini pack surface"
    exit 1
  fi

  if ! grep -q '"contextFileName": "GEMINI.md"' "$PACK_ROOT/extension/gemini-extension.json"; then
    echo "FAIL: extension manifest should declare contextFileName GEMINI.md"
    exit 1
  fi
fi

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
else
  echo "FAIL: python or python3 is required to validate Gemini TOML and JSON surfaces"
  exit 1
fi

"$PYTHON_BIN" - "$RUNTIME_ROOT/commands/agents/help.toml" "$RUNTIME_ROOT/commands/agents/init-project.toml" "${PACK_ROOT:-$RUNTIME_ROOT}/extension/gemini-extension.json" "$MODE" <<'PY'
import json
import sys
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:
    print("FAIL: Python tomllib is unavailable; cannot validate Gemini TOML syntax")
    sys.exit(1)

toml_paths = [Path(sys.argv[1]), Path(sys.argv[2])]
json_path = Path(sys.argv[3])
mode = sys.argv[4]

for toml_path in toml_paths:
    with toml_path.open("rb") as fh:
        tomllib.load(fh)

if mode == "source":
    with json_path.open("r", encoding="utf-8") as fh:
        json.load(fh)
PY

echo "PASS: Gemini pack surface present in $MODE mode at $ROOT"

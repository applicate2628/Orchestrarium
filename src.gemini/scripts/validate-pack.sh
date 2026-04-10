#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-.}"

if [[ -d "$ROOT/src.gemini" ]]; then
  PACK_ROOT="$ROOT/src.gemini"
elif [[ -d "$ROOT/.gemini" ]]; then
  PACK_ROOT="$ROOT/.gemini"
else
  echo "FAIL: neither src.gemini/ nor .gemini/ found"
  exit 1
fi

required=(
  "$PACK_ROOT/GEMINI.md"
  "$PACK_ROOT/skills/README.md"
  "$PACK_ROOT/skills/lead/SKILL.md"
  "$PACK_ROOT/skills/init-project/SKILL.md"
  "$PACK_ROOT/commands/agents/help.toml"
  "$PACK_ROOT/commands/agents/init-project.toml"
  "$PACK_ROOT/extension/README.md"
  "$PACK_ROOT/extension/gemini-extension.json"
)

for path in "${required[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "FAIL: missing $path"
    exit 1
  fi
done

while IFS= read -r import_line; do
  import_target="${import_line#@}"
  if [[ -z "$import_target" ]]; then
    continue
  fi
  if [[ ! -f "$PACK_ROOT/$import_target" ]]; then
    echo "FAIL: GEMINI.md import target missing: $PACK_ROOT/$import_target"
    exit 1
  fi
done < <(grep '^@' "$PACK_ROOT/GEMINI.md" || true)

if [[ -e "$PACK_ROOT/AGENTS.md" ]]; then
  echo "FAIL: $PACK_ROOT/AGENTS.md should not exist in the preferred Gemini scaffold"
  exit 1
fi

if [[ -e "$PACK_ROOT/agents" ]]; then
  echo "FAIL: $PACK_ROOT/agents should not exist in the preferred Gemini scaffold"
  exit 1
fi

if ! grep -q '/init' "$PACK_ROOT/GEMINI.md"; then
  echo "FAIL: GEMINI.md should mention the official Gemini /init bootstrap path"
  exit 1
fi

if ! grep -q '\.gemini/settings\.json' "$PACK_ROOT/GEMINI.md"; then
  echo "FAIL: GEMINI.md should mention .gemini/settings.json as the official Gemini runtime-state surface"
  exit 1
fi

for skill in "$PACK_ROOT/skills/lead/SKILL.md" "$PACK_ROOT/skills/init-project/SKILL.md"; do
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

if ! grep -q '"contextFileName": "GEMINI.md"' "$PACK_ROOT/extension/gemini-extension.json"; then
  echo "FAIL: extension manifest should declare contextFileName GEMINI.md"
  exit 1
fi

if command -v python >/dev/null 2>&1; then
  PYTHON_BIN=python
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN=python3
else
  echo "FAIL: python or python3 is required to validate Gemini TOML and JSON surfaces"
  exit 1
fi

"$PYTHON_BIN" - "$PACK_ROOT/commands/agents/help.toml" "$PACK_ROOT/commands/agents/init-project.toml" "$PACK_ROOT/extension/gemini-extension.json" <<'PY'
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

for toml_path in toml_paths:
    with toml_path.open("rb") as fh:
        tomllib.load(fh)

with json_path.open("r", encoding="utf-8") as fh:
    json.load(fh)
PY

echo "PASS: Gemini scaffold present at $PACK_ROOT"

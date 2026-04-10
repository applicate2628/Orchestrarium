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
  "$PACK_ROOT/commands/agents/help.toml"
  "$PACK_ROOT/extension/README.md"
  "$PACK_ROOT/extension/gemini-extension.json"
)

for path in "${required[@]}"; do
  if [[ ! -f "$path" ]]; then
    echo "FAIL: missing $path"
    exit 1
  fi
done

if [[ -e "$PACK_ROOT/AGENTS.md" ]]; then
  echo "FAIL: $PACK_ROOT/AGENTS.md should not exist in the preferred Gemini scaffold"
  exit 1
fi

if [[ -e "$PACK_ROOT/agents" ]]; then
  echo "FAIL: $PACK_ROOT/agents should not exist in the preferred Gemini scaffold"
  exit 1
fi

for skill in "$PACK_ROOT/skills/lead/SKILL.md"; do
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

echo "PASS: Gemini scaffold present at $PACK_ROOT"

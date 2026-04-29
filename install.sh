#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FORWARDED_ARGS=("$@")
HAS_QWEN=false

if [[ -f "$SCRIPT_DIR/scripts/install-qwen.sh" ]]; then
  HAS_QWEN=true
fi

run_installer() {
  local script_name="$1"
  bash "$SCRIPT_DIR/scripts/$script_name" "${FORWARDED_ARGS[@]}"
}

run_all_available() {
  run_installer install-codex.sh
  run_installer install-claude.sh
  run_installer install-gemini.sh
  if [[ "$HAS_QWEN" == true ]]; then
    run_installer install-qwen.sh
  fi
}

echo "What to install?"
echo "Production installs:"
echo "  1) Codex pack"
echo "  2) Claude Code"
echo "  3) Codex + Claude (production pair)"
echo "Example integrations:"
echo "  4) Gemini CLI (WEAK MODEL / NOT RECOMMENDED)"
if [[ "$HAS_QWEN" == true ]]; then
  echo "  5) Qwen (WEAK MODEL / NOT RECOMMENDED)"
  echo "  6) All available root installs"
  prompt="Select 1, 2, 3, 4, 5, or 6: "
else
  echo "  5) All available root installs"
  echo "     Qwen appears here once scripts/install-qwen.sh is available."
  prompt="Select 1, 2, 3, 4, or 5: "
fi
read -r -p "$prompt" choice
choice="${choice//$'\r'/}"

case "${choice:-}" in
  1)
    run_installer install-codex.sh
    ;;
  2)
    run_installer install-claude.sh
    ;;
  3)
    run_installer install-codex.sh
    run_installer install-claude.sh
    ;;
  4)
    run_installer install-gemini.sh
    ;;
  5)
    if [[ "$HAS_QWEN" == true ]]; then
      run_installer install-qwen.sh
    else
      run_all_available
    fi
    ;;
  6)
    if [[ "$HAS_QWEN" == true ]]; then
      run_all_available
    else
      echo "Invalid selection: ${choice:-<empty>}" >&2
      exit 1
    fi
    ;;
  *)
    echo "Invalid selection: ${choice:-<empty>}" >&2
    exit 1
    ;;
esac

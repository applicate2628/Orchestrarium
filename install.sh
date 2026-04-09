#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "What to install?"
echo "  1) Codex (Orchestrarium)"
echo "  2) Claude Code (Claudestrator)"
echo "  3) Both"
read -r -p "Select 1, 2, or 3: " choice
choice="${choice//$'\r'/}"

case "${choice:-}" in
  1)
    exec bash "$SCRIPT_DIR/install-codex.sh" "$@"
    ;;
  2)
    exec bash "$SCRIPT_DIR/install-claude.sh" "$@"
    ;;
  3)
    bash "$SCRIPT_DIR/install-codex.sh" "$@"
    bash "$SCRIPT_DIR/install-claude.sh" "$@"
    ;;
  *)
    echo "Invalid selection: ${choice:-<empty>}" >&2
    exit 1
    ;;
esac

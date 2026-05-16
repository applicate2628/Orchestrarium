#!/usr/bin/env python3
"""Install or update the hypothesis-disclosure PreToolUse hook idempotently.

This script merges the Orchestrarium hypothesis-disclosure hook config into a
target settings/hooks JSON file while preserving all other user-owned keys and
other PreToolUse hooks. Running it multiple times produces the same result
(our entry is identified by the `check-hypothesis-disclosure` script signature
in the command field, so re-runs update in place rather than appending
duplicates).

Supported targets:
  --platform claude  →  Claude Code settings.json (e.g. ~/.claude/settings.json)
  --platform codex   →  Codex hooks.json (e.g. ~/.codex/hooks.json)

Cross-platform behavior:
  The shipped command uses `bash $HOME/.<provider>/...check-hypothesis-disclosure.sh`
  which works on macOS, Linux, and Windows (via Git Bash). Operators who want
  the native PowerShell variant on Windows can replace the `command` field
  manually; this script's idempotent update keys on the `check-hypothesis-disclosure`
  substring, so a hand-edited PowerShell entry will still be recognized as
  "ours" and re-updated to the bash form on next install. To preserve a manual
  PowerShell override, set ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1 in the environment
  to skip the install entirely.

Removal:
  --remove  Removes our hook entry. Cleans up empty hooks containers.

Exit codes:
  0 on success (install, update, remove, or no-op).
  1 on JSON parse error or filesystem error.
  2 on argument error.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

# Substring that identifies our hook entry inside an existing settings.json.
# Any PreToolUse entry whose command contains this substring is treated as
# "ours" for idempotent update/replace.
SCRIPT_MARKER = "check-hypothesis-disclosure"


def build_claude_entry(script_path: str) -> dict[str, Any]:
    return {
        "matcher": "Bash",
        "hooks": [
            {
                "type": "command",
                "if": "Bash(git push *)",
                "command": f"bash {script_path}",
            }
        ],
    }


def build_codex_entry(script_path: str) -> dict[str, Any]:
    # Codex matchers do not support the `if` permission-rule filter; the script
    # self-filters by parsing tool_input.command for "git push".
    return {
        "matcher": "Bash",
        "hooks": [
            {
                "type": "command",
                "command": f"bash {script_path}",
            }
        ],
    }


def find_our_entry(pretool_list: list[Any]) -> int | None:
    for idx, entry in enumerate(pretool_list):
        if not isinstance(entry, dict):
            continue
        for hook in entry.get("hooks") or []:
            if not isinstance(hook, dict):
                continue
            command = hook.get("command", "")
            if isinstance(command, str) and SCRIPT_MARKER in command:
                return idx
    return None


def load_existing(target: Path) -> dict[str, Any]:
    if not target.exists():
        return {}
    text = target.read_text(encoding="utf-8")
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        sys.stderr.write(f"FAIL: {target} is not valid JSON: {exc}\n")
        sys.exit(1)
    if not isinstance(data, dict):
        sys.stderr.write(f"FAIL: {target} top-level must be a JSON object\n")
        sys.exit(1)
    return data


def write_pretty(target: Path, data: dict[str, Any]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    target.write_text(text, encoding="utf-8")


def install(data: dict[str, Any], new_entry: dict[str, Any]) -> bool:
    """Insert or update our hook entry. Returns True if data changed."""
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        sys.stderr.write("FAIL: 'hooks' key is not a JSON object\n")
        sys.exit(1)
    pretool = hooks.setdefault("PreToolUse", [])
    if not isinstance(pretool, list):
        sys.stderr.write("FAIL: 'hooks.PreToolUse' is not a JSON array\n")
        sys.exit(1)

    existing_idx = find_our_entry(pretool)
    if existing_idx is not None:
        if pretool[existing_idx] == new_entry:
            return False  # idempotent no-op
        pretool[existing_idx] = new_entry
    else:
        pretool.append(new_entry)
    return True


def remove(data: dict[str, Any]) -> bool:
    """Remove our hook entry. Returns True if data changed."""
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    pretool = hooks.get("PreToolUse")
    if not isinstance(pretool, list):
        return False
    existing_idx = find_our_entry(pretool)
    if existing_idx is None:
        return False
    del pretool[existing_idx]
    # Clean up empty containers so the file does not gain ghost structure.
    if not pretool:
        del hooks["PreToolUse"]
    if not hooks:
        del data["hooks"]
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        required=True,
        help="Path to settings.json (Claude) or hooks.json (Codex)",
    )
    parser.add_argument(
        "--platform",
        choices=("claude", "codex"),
        required=True,
        help="Which platform's hook config schema to write",
    )
    parser.add_argument(
        "--script-path",
        required=True,
        help="Absolute or expandable path to check-hypothesis-disclosure.sh",
    )
    parser.add_argument(
        "--remove",
        action="store_true",
        help="Remove our hook entry instead of installing it",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without modifying any file",
    )
    args = parser.parse_args()

    if os.environ.get("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK"):
        sys.stderr.write(
            "SKIP: ORCHESTRARIUM_NO_HYPOTHESIS_HOOK set; not modifying "
            f"{args.target}\n"
        )
        return 0

    target = Path(args.target).expanduser()
    data = load_existing(target)

    if args.remove:
        changed = remove(data)
        action = "removed"
    else:
        if args.platform == "claude":
            entry = build_claude_entry(args.script_path)
        else:
            entry = build_codex_entry(args.script_path)
        changed = install(data, entry)
        action = "installed/updated"

    if not changed:
        sys.stdout.write(f"  Hypothesis hook already present in {target} (no-op)\n")
        return 0

    if args.dry_run:
        sys.stdout.write(f"  [dry-run] would write {target}\n")
        return 0

    # Special case: file removal when remove cleared everything
    if args.remove and not data:
        if target.exists():
            target.unlink()
            sys.stdout.write(f"  Hypothesis hook {action}; deleted now-empty {target}\n")
        return 0

    write_pretty(target, data)
    sys.stdout.write(f"  Hypothesis hook {action} in {target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

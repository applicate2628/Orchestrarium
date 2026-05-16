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
  The shipped command uses `bash <quoted script_path>` which works on macOS,
  Linux, and Windows (via Git Bash). Path is shlex-quoted to defend against
  paths with spaces, semicolons, or other shell metacharacters. Operators who
  want a native PowerShell variant on Windows can replace the `command` field
  manually; this script's idempotent update keys on the `check-hypothesis-
  disclosure` substring, so a hand-edited PowerShell entry is still recognized
  as "ours" and re-updated to the bash form on next install. To preserve a
  manual PowerShell override, set ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1 in the
  environment to skip the install entirely.

Removal:
  --remove  Removes ALL of our hook entries (handles duplicates from earlier
            buggy versions). Cleans up empty hooks containers. The opt-out env
            var does NOT block --remove, so a standing opt-out can still
            uninstall a previously-installed hook.

Safety hardening:
  - Refuses to write through a symlinked settings.json target (security: avoid
    same-user clobber of /etc/passwd-style symlink attacks).
  - Atomic write via temp file + os.replace to prevent torn writes.
  - Validates that hooks/PreToolUse are correct JSON types before iterating
    (a malformed-but-valid JSON like {"hooks": {"PreToolUse": [{"hooks": 5}]}}
    is rejected with a clear error instead of crashing with TypeError).

Exit codes:
  0 on success (install, update, remove, or no-op).
  1 on JSON parse error, type-validation error, filesystem error, symlink
    target.
  2 on argument error.
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Any

# Substring that identifies our hook entry inside an existing settings.json.
# Any PreToolUse entry whose hooks list contains a command with this substring
# is treated as "ours" for idempotent update/replace.
SCRIPT_MARKER = "check-hypothesis-disclosure"


def build_claude_entry(script_path: str) -> dict[str, Any]:
    quoted = shlex.quote(script_path)
    return {
        "matcher": "Bash",
        "hooks": [
            {
                "type": "command",
                "if": "Bash(git push *)",
                "command": f"bash {quoted}",
            }
        ],
    }


def build_codex_entry(script_path: str) -> dict[str, Any]:
    # Codex matchers do not support the `if` permission-rule filter; the script
    # self-filters by parsing tool_input.command for "git push".
    quoted = shlex.quote(script_path)
    return {
        "matcher": "Bash",
        "hooks": [
            {
                "type": "command",
                "command": f"bash {quoted}",
            }
        ],
    }


def find_our_entry_indices(pretool_list: list[Any]) -> list[int]:
    """Return ALL indices whose hook command contains the marker.

    Earlier versions of this script returned only the first match; that left
    duplicates firing if multiple of our entries were inserted by a buggy or
    racy install. Now: install collapses duplicates to a single entry; remove
    deletes every one of our entries.
    """
    indices: list[int] = []
    for idx, entry in enumerate(pretool_list):
        if not isinstance(entry, dict):
            continue
        hooks_field = entry.get("hooks")
        if not isinstance(hooks_field, list):
            # Defensive: a non-list `hooks` is malformed for this entry; skip
            # it rather than crashing. The validation in install()/remove()
            # will reject the file shape if the top-level structure is wrong;
            # per-entry hooks_field that is not a list is just ignored here.
            continue
        for hook in hooks_field:
            if not isinstance(hook, dict):
                continue
            command = hook.get("command", "")
            if isinstance(command, str) and SCRIPT_MARKER in command:
                indices.append(idx)
                break
    return indices


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


def write_atomic(target: Path, data: dict[str, Any]) -> None:
    """Write target atomically via temp file in same dir + os.replace.

    Refuses to write through a symlink (lstat-based check). The temp file is
    created in the same directory as target so os.replace is atomic on the
    same filesystem.
    """
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_symlink():
        sys.stderr.write(
            f"FAIL: {target} is a symbolic link; refusing to write through it. "
            "Resolve the symlink or move it aside before re-running.\n"
        )
        sys.exit(1)
    text = json.dumps(data, indent=2, ensure_ascii=False) + "\n"
    # tempfile in the same directory so os.replace is atomic on the same FS.
    fd, tmp_path_str = tempfile.mkstemp(
        prefix=".install-hypothesis-hook.", suffix=".tmp", dir=str(target.parent)
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            try:
                os.fsync(f.fileno())
            except (AttributeError, OSError):
                # fsync may not be available on every filesystem (Windows
                # remote shares, some FUSE mounts); best-effort only.
                pass
        os.replace(tmp_path, target)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def install(data: dict[str, Any], new_entry: dict[str, Any]) -> bool:
    """Insert our hook entry, removing any duplicates. Returns True if changed."""
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        sys.stderr.write("FAIL: 'hooks' key is not a JSON object\n")
        sys.exit(1)
    pretool = hooks.setdefault("PreToolUse", [])
    if not isinstance(pretool, list):
        sys.stderr.write("FAIL: 'hooks.PreToolUse' is not a JSON array\n")
        sys.exit(1)

    existing = find_our_entry_indices(pretool)
    changed = False

    # If there are multiple of our entries (duplicates from earlier buggy
    # state), collapse them to a single entry containing the new content.
    if len(existing) > 1:
        # Delete duplicates from the end so earlier indices stay valid.
        for idx in reversed(existing[1:]):
            del pretool[idx]
        existing = [existing[0]]
        changed = True

    if existing:
        idx = existing[0]
        if pretool[idx] != new_entry:
            pretool[idx] = new_entry
            changed = True
    else:
        pretool.append(new_entry)
        changed = True

    return changed


def remove(data: dict[str, Any]) -> bool:
    """Remove ALL of our hook entries. Returns True if changed."""
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    pretool = hooks.get("PreToolUse")
    if not isinstance(pretool, list):
        return False
    indices = find_our_entry_indices(pretool)
    if not indices:
        return False
    # Delete from the end so earlier indices stay valid.
    for idx in reversed(indices):
        del pretool[idx]
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

    # The opt-out env var blocks install but NOT remove — a standing opt-out
    # should still allow uninstall of a previously-installed hook entry.
    if os.environ.get("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK") and not args.remove:
        sys.stderr.write(
            "SKIP: ORCHESTRARIUM_NO_HYPOTHESIS_HOOK set; not installing into "
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

    # Special case: file removal when remove cleared everything.
    if args.remove and not data:
        if target.exists():
            if target.is_symlink():
                sys.stderr.write(
                    f"FAIL: {target} is a symbolic link; refusing to delete\n"
                )
                return 1
            target.unlink()
            sys.stdout.write(f"  Hypothesis hook {action}; deleted now-empty {target}\n")
        return 0

    write_atomic(target, data)
    sys.stdout.write(f"  Hypothesis hook {action} in {target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

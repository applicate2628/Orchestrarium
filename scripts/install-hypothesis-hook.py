#!/usr/bin/env python3
"""Install or update Orchestrarium structural hooks idempotently.

This script merges an Orchestrarium structural hook config into a
target settings/hooks JSON file while preserving all other user-owned keys and
other hooks. Running it multiple times produces the same result
(our entry is identified by the configured script marker in the command or
args fields, so re-runs update in place rather than appending
duplicates).

Supported targets:
  --platform claude   →  Claude Code settings.json (e.g. ~/.claude/settings.json)
  --platform codex    →  Codex hooks.json (e.g. ~/.codex/hooks.json)
  --platform generic  →  Provider-neutral exec-form JSON for compatible runtimes
                         or approved wrapper-driven hook wiring.

Cross-platform behavior:
  Claude/generic use exec form; Codex uses shell form. POSIX hosts use bash
  wrappers. Windows hosts use PowerShell wrappers.

Removal:
  --remove  Removes ALL of our hook entries (handles duplicates from earlier
            buggy versions). Cleans up empty hooks containers. The opt-out env
            var does NOT block --remove, so a standing opt-out can still
            uninstall a previously-installed hook.

Safety hardening:
  - Refuses to write through a symlinked settings.json target (security: avoid
    same-user clobber of /etc/passwd-style symlink attacks).
  - Atomic write via temp file + os.replace to prevent torn writes.
  - Validates that hooks/<event> are correct JSON types before iterating
    (a malformed-but-valid JSON like {"hooks": {"Stop": [{"hooks": 5}]}}
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

DEFAULT_SCRIPT_MARKER = "check-bugfix-discipline"

# Matcher regex covers Claude's code-mutating tools + Codex's apply_patch.
# Per Claude Code hooks-reference, `matcher` is a regex on tool name; per
# Codex hooks docs, same. The single regex covers both platforms cleanly.
# This hook fires on every code edit; the script self-filters on bug-context
# detected from the session transcript.
TOOL_MATCHER_REGEX = "Edit|Write|NotebookEdit|apply_patch"


def powershell_single_quote(value: str) -> str:
    """Return a PowerShell single-quoted literal for a shell command string.

    PowerShell single-quoted strings escape an embedded apostrophe by doubling it.
    Codex hook entries are command strings, so the script path must be quoted in
    the target shell's syntax instead of treated as a pre-split argv element.
    """
    return "'" + value.replace("'", "''") + "'"


def _with_event_matcher(
    entry: dict[str, Any], hook_event: str, tool_matcher: str | None = None
) -> dict[str, Any]:
    """Attach matcher only for hook events that consume one.

    tool_matcher overrides the default TOOL_MATCHER_REGEX for a hook that must
    fire on a different tool set (e.g. "Bash" for a shell-command guard). When
    None, the shared default applies, so every existing hook entry is unchanged.
    """
    if hook_event == "PreToolUse":
        return {"matcher": tool_matcher or TOOL_MATCHER_REGEX, **entry}
    return entry


def build_claude_entry(
    script_path: str,
    host_os: str,
    hook_event: str = "PreToolUse",
    tool_matcher: str | None = None,
) -> dict[str, Any]:
    """Build a Claude hook entry in exec form (args array, no shell).

    Exec form is the documented portable cross-platform pattern per
    https://code.claude.com/docs/hooks-reference#exec-form-and-shell-form
    — each `args` element is passed as a literal argument, with no shell
    interpretation, so paths with spaces or shell metacharacters are safe
    without any quoting concern.

    POSIX host: `command: "bash", args: [<sh_path>]`.
    Windows host: `command: "powershell", args: [-NoProfile, -ExecutionPolicy,
    Bypass, -File, <ps1_path>]` — native PowerShell invocation without any
    Git Bash dependency.

    The matcher regex (Edit|Write|NotebookEdit|apply_patch) fires on every
    code-mutating tool call; the script's first action is to inspect the
    PreToolUse envelope's `transcript_path` for bug-context signals and
    decide whether to allow or deny.
    """
    if host_os == "windows":
        return _with_event_matcher(
            {
            "hooks": [
                {
                    "type": "command",
                    "command": "powershell",
                    "args": [
                        "-NoProfile",
                        "-ExecutionPolicy",
                        "Bypass",
                        "-File",
                        script_path,
                    ],
                }
            ],
            },
            hook_event,
            tool_matcher,
        )
    return _with_event_matcher(
        {
        "hooks": [
            {
                "type": "command",
                "command": "bash",
                "args": [script_path],
            }
        ],
        },
        hook_event,
        tool_matcher,
    )


def build_generic_entry(
    script_path: str,
    host_os: str,
    hook_event: str = "PreToolUse",
    tool_matcher: str | None = None,
) -> dict[str, Any]:
    """Build a provider-neutral exec-form hook entry.

    This is intentionally the same shape as the Claude exec form: a command
    plus literal argv list, with `hooks.<event>[]` and optional PreToolUse
    matcher. Runtimes or wrappers that support this JSON shape can consume it
    without pretending to be Claude; runtimes with a different native schema
    should adapt from the universal hook/helper scripts directly.
    """
    return build_claude_entry(script_path, host_os, hook_event, tool_matcher)


def build_codex_entry(
    script_path: str,
    host_os: str,
    hook_event: str = "PreToolUse",
    tool_matcher: str | None = None,
) -> dict[str, Any]:
    """Build a Codex hook entry in shell form.

    Codex hooks (per https://developers.openai.com/codex/hooks) do NOT support
    an `args` array or a `shell` field — only `type`, `command`, `statusMessage`,
    `timeout`, and `async`. Commands are always interpreted by the host's
    default shell. shlex.quote() defends against metacharacter injection in
    the script path.

    POSIX host: `bash <quoted_sh_path>`.
    Windows host: `powershell.exe -NoProfile -ExecutionPolicy Bypass -File
    <quoted_ps1_path>` — explicit `powershell.exe` avoids the Windows PATH
    gotcha where `bash` may resolve to the WSL launcher (`C:\\Windows\\System32
    \\bash.exe`) instead of Git Bash. WSL bash cannot resolve `C:\\Users\\...`
    paths, so the previous bash-first form silently broke on default Windows
    installs that have WSL installed alongside Git Bash. PowerShell.exe always
    resolves to a single known system path with no PATH ambiguity.

    Codex matchers do not support the Claude-style `if` permission-rule
    filter; the script self-filters on bug-context detected from the
    PreToolUse envelope's transcript_path.

    Note: Codex marks newly-written hook entries as "untrusted"; the user
    must run `codex` interactively at least once and trust the hook via the
    TUI before it fires. This installer writes the entry; trust is the
    user's responsibility (Codex does not currently expose a programmatic
    trust API).
    """
    if host_os == "windows":
        # Native PowerShell on Windows — single-quote the script path so any
        # space in $HOME or path component is interpreted as part of the
        # filename, not as a flag boundary.
        quoted = powershell_single_quote(script_path)
        command_str = (
            f"powershell.exe -NoProfile -ExecutionPolicy Bypass -File {quoted}"
        )
    else:
        quoted = shlex.quote(script_path)
        command_str = f"bash {quoted}"
    return _with_event_matcher(
        {
        "hooks": [
            {
                "type": "command",
                "command": command_str,
            }
        ],
        },
        hook_event,
        tool_matcher,
    )


def _hook_contains_marker(hook: dict[str, Any], script_marker: str) -> bool:
    """True if a single hook dict references our script via marker substring.

    Marker can appear in either:
      - The `command` shell-string (legacy shell form / Codex always-shell form).
      - Any element of the `args` array (exec form, where the script path is
        a literal argv element separate from the executable name).
    """
    command = hook.get("command", "")
    if isinstance(command, str) and script_marker in command:
        return True
    args_field = hook.get("args")
    if isinstance(args_field, list):
        for arg in args_field:
            if isinstance(arg, str) and script_marker in arg:
                return True
    return False


def find_our_entry_indices(hook_event_list: list[Any], script_marker: str) -> list[int]:
    """Return ALL indices whose hook references our script (by marker).

    Recognizes both legacy shell form (marker in `command`) and current exec
    form (marker in `args[k]`). This lets a re-install collapse an older
    shell-form entry into the new exec-form entry without leaving stale
    duplicates, and lets `--remove` clean up either form.

    Earlier versions of this script returned only the first match; that left
    duplicates firing if multiple of our entries were inserted by a buggy or
    racy install. Now: install collapses duplicates to a single entry; remove
    deletes every one of our entries.
    """
    indices: list[int] = []
    for idx, entry in enumerate(hook_event_list):
        if not isinstance(entry, dict):
            continue
        hooks_field = entry.get("hooks")
        if not isinstance(hooks_field, list):
            # Defensive: a non-list `hooks` is malformed for this entry; skip
            # it rather than crashing. Per-entry malformations are not the
            # script's job to repair.
            continue
        for hook in hooks_field:
            if isinstance(hook, dict) and _hook_contains_marker(hook, script_marker):
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


def install(
    data: dict[str, Any],
    new_entry: dict[str, Any],
    hook_event: str,
    script_marker: str,
) -> bool:
    """Insert our hook entry, removing any duplicates. Returns True if changed."""
    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        sys.stderr.write("FAIL: 'hooks' key is not a JSON object\n")
        sys.exit(1)
    hook_entries = hooks.setdefault(hook_event, [])
    if not isinstance(hook_entries, list):
        sys.stderr.write(f"FAIL: 'hooks.{hook_event}' is not a JSON array\n")
        sys.exit(1)

    existing = find_our_entry_indices(hook_entries, script_marker)
    changed = False

    # If there are multiple of our entries (duplicates from earlier buggy
    # state), collapse them to a single entry containing the new content.
    if len(existing) > 1:
        # Delete duplicates from the end so earlier indices stay valid.
        for idx in reversed(existing[1:]):
            del hook_entries[idx]
        existing = [existing[0]]
        changed = True

    if existing:
        idx = existing[0]
        if hook_entries[idx] != new_entry:
            hook_entries[idx] = new_entry
            changed = True
    else:
        hook_entries.append(new_entry)
        changed = True

    return changed


def remove(data: dict[str, Any], hook_event: str, script_marker: str) -> bool:
    """Remove ALL of our hook entries. Returns True if changed."""
    hooks = data.get("hooks")
    if not isinstance(hooks, dict):
        return False
    hook_entries = hooks.get(hook_event)
    if not isinstance(hook_entries, list):
        return False
    indices = find_our_entry_indices(hook_entries, script_marker)
    if not indices:
        return False
    # Delete from the end so earlier indices stay valid.
    for idx in reversed(indices):
        del hook_entries[idx]
    # Clean up empty containers so the file does not gain ghost structure.
    if not hook_entries:
        del hooks[hook_event]
    if not hooks:
        del data["hooks"]
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        required=True,
        help="Path to settings/hooks JSON for the selected platform",
    )
    parser.add_argument(
        "--platform",
        choices=("claude", "codex", "generic"),
        required=True,
        help="Which platform's hook config schema to write",
    )
    parser.add_argument(
        "--script-path",
        required=True,
        help="Absolute or expandable path to the hook script (.sh on POSIX, .ps1 on Windows)",
    )
    parser.add_argument(
        "--host-os",
        choices=("posix", "windows"),
        default="posix",
        help="Host OS class (controls exec-form vs shell-form / bash vs powershell)",
    )
    parser.add_argument(
        "--hook-event",
        choices=("PreToolUse", "Stop", "SessionStart"),
        default="PreToolUse",
        help="Hook event to install under (default: PreToolUse)",
    )
    parser.add_argument(
        "--script-marker",
        default=DEFAULT_SCRIPT_MARKER,
        help="Substring identifying this specific hook entry for idempotency",
    )
    parser.add_argument(
        "--tool-matcher",
        default=None,
        help=(
            "Override the PreToolUse matcher regex (default: "
            "Edit|Write|NotebookEdit|apply_patch). Use for a hook that must fire "
            "on a different tool set, e.g. 'Bash' for a shell-command guard. "
            "Ignored for the Stop event, which takes no matcher."
        ),
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

    # Codex hooks require an interactive trust step via the `codex` TUI before
    # they actually fire — Codex marks newly-installed hooks as "untrusted"
    # and `codex exec` silently skips them until the user runs `codex`
    # interactively and trusts the hook. This installer writes the entry; the
    # trust step remains the user's responsibility (it can't be performed
    # programmatically without an explicit trust API, which Codex does not
    # currently expose).
    #
    # On Windows, the Codex shell-form command we emit invokes the hook via
    # `powershell.exe -NoProfile -ExecutionPolicy Bypass -File '<ps1>'` (see
    # build_codex_entry) — explicit powershell.exe avoids the PATH gotcha where
    # `bash` resolves to the WSL launcher, which cannot read `C:\Users\...`
    # paths. If a user's Codex runtime uses a different interpreter the hook
    # entry is visible in the trust UI but may fail to invoke; the user can edit
    # ~/.codex/hooks.json after install to match their shell.
    target = Path(args.target).expanduser()
    data = load_existing(target)

    if args.remove:
        changed = remove(data, args.hook_event, args.script_marker)
        action = "removed"
    else:
        if args.platform == "claude":
            entry = build_claude_entry(
                args.script_path, args.host_os, args.hook_event, args.tool_matcher
            )
        elif args.platform == "codex":
            entry = build_codex_entry(
                args.script_path, args.host_os, args.hook_event, args.tool_matcher
            )
        else:
            entry = build_generic_entry(
                args.script_path, args.host_os, args.hook_event, args.tool_matcher
            )
        changed = install(data, entry, args.hook_event, args.script_marker)
        action = "installed/updated"

    if not changed:
        sys.stdout.write(
            f"  {args.script_marker} hook already present in {target} (no-op)\n"
        )
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
            sys.stdout.write(
                f"  {args.script_marker} hook {action}; deleted now-empty {target}\n"
            )
        return 0

    write_atomic(target, data)
    sys.stdout.write(f"  {args.script_marker} hook {action} in {target}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

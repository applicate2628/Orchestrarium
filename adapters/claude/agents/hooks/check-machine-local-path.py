#!/usr/bin/env python3
"""Machine-local path guard for the PreToolUse hook — AUDIT mode.

Detects a machine-local absolute path being written into a NON-scratch file:
a concrete user home (`C:\\Users\\<name>`, `/c/Users/<name>`), a workstation
dev/work root (`D:\\dev\\...`, `/d/dev/...`), etc. These leak machine-specific
provenance into shared / tracked artifacts — the `machine-local-path-provenance`
rule (kept in the author's external rules library, outside any project repo).

Placeholder forms are NOT flagged, because the pack's own governance docs use
them legitimately as examples:
  - `<you>`, `<repo>`, `<category>` and other `<...>` placeholders
  - `%USERPROFILE%`, `${CLAUDE_PROJECT_DIR}`, `$HOME`
  - common example usernames: `you`, `user`, `username`, `name`, `test`, `example`

AUDIT mode (current posture): on a hit, ALWAYS ALLOW the tool call and never
block. Deliver the warning to the MODEL via `hookSpecificOutput.additionalContext`
on stdout, exit 0 (see `hook_common.emit_advisory`). This is the corrected
delivery channel: a PreToolUse hook's previous stderr-plus-exit-1 form was
measured to reach NOBODY on either Claude Code 2.1.220 (transcript-only,
model-invisible) or Codex CLI 0.145.0 (discarded entirely -- the non-2-exit
branch never copies stderr). See
work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-session-form-its-
sibling-calls-broken.md for the full falsification-controlled measurement.
Promotion to a blocking `deny` (exit 2) is a separate, reviewed step once the
allowlist is proven tight (per the reviewed Phase-0.2 plan: dry-run/audit
first, measure FP, then decide block-vs-warn). The JSON envelope also retires
the old stderr-UTF-8-bytes trick this hook used for Cyrillic/non-ASCII paths:
`json.dumps(..., ensure_ascii=True)` escapes every non-ASCII character, so the
emitted line is pure ASCII regardless of console codepage.

Design note: this hook fires on the EDIT's own `tool_input` (the file path and
the content being written), NOT on session/transcript context. That is a
deliberate contrast with the bugfix-discipline hook, whose context-based
matching false-positives across a long session; keying on the immediate action
keeps this guard precise.

Fail-open everywhere on internal error (return 0).
"""
from __future__ import annotations

import os
import re
import sys

# hook_common lives in the sibling scripts/ dir (shared with the grandfathered
# hooks); this hook lives in the typed hooks/ dir per the source-hygiene rule,
# so add the sibling scripts/ dir to the import path before importing it.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

from hook_common import emit_advisory, parse_envelope, read_stdin_utf8


# A path segment that is a placeholder, not a concrete machine name.
_PLACEHOLDER = r"(?:<[^>\\/\s]+>|%[^%\\/\s]+%|\$\{[^}\s]+\}|\$[A-Za-z_][A-Za-z0-9_]*)"

# Example/placeholder usernames that are not real machine leaks (case-insensitive).
ALLOWED_USER_TOKENS = {"you", "user", "username", "name", "test", "example", "me", "x"}

# Dot run (".", "..", "...") OR the Unicode horizontal ellipsis U+2026 ("\u2026"),
# or any mix, used as an ellipsis placeholder segment in docs (e.g. C:\Users\<U+2026>).
_ELLIPSIS_CHARS = {".", "\u2026"}

# Each pattern captures (root, first-segment). We then drop matches whose
# first segment is a placeholder or an allowed example token.
_PATTERNS = [
    # Windows user home: C:\Users\X  or  C:/Users/X
    re.compile(r"(?i)\b[a-z]:[\\/]+users[\\/]+([^\\/\s\"'`,;:)\]}>]+)"),
    # MSYS / Git-Bash user home: /c/Users/X
    re.compile(r"(?i)(?:^|[\s\"'`(=])/[a-z]/users/([^/\s\"'`,;:)\]}>]+)"),
    # POSIX user home: /home/X
    re.compile(r"(?i)(?:^|[\s\"'`(=])/home/([^/\s\"'`,;:)\]}>]+)"),
    # macOS user home: /Users/X (bare, no drive prefix). The Windows C:/Users and
    # MSYS /c/Users cases are handled above; there the /Users is preceded by ':'
    # or a drive letter, not by start/space/quote, so this pattern does not double-fire.
    re.compile(r"(?i)(?:^|[\s\"'`(=])/Users/([^/\s\"'`,;:)\]}>]+)"),
    # Windows workstation dev/work root: D:\dev\X  or  C:/work/X
    re.compile(r"(?i)\b[a-z]:[\\/]+(?:dev|work|projects)[\\/]+([^\\/\s\"'`,;:)\]}>]+)"),
    # MSYS workstation dev root: /d/dev/X
    re.compile(r"(?i)(?:^|[\s\"'`(=])/[a-z]/(?:dev|work|projects)/([^/\s\"'`,;:)\]}>]+)"),
    # UNC user home: \host\Users\X  or  \server\share\...\Users\X.
    # Left-anchored on start/space/quote/'('/'='/',' so a bare doubled-backslash
    # \Users\ inside an ESCAPED Windows-path source literal (e.g. JSON
    # "C:\Users\test") cannot self-match — a genuine UNC needs a host label
    # BEFORE \Users\, which a drive-prefixed \Users\ does not have. The negative
    # lookahead excludes the \?\ and \.\ namespaces, whose embedded drive form
    # (C:\Users\X) is already caught by the drive-letter pattern above.
    re.compile(
        r"(?i)(?:^|[\s\"'`(=,])\\\\(?![?.][\\/])"
        r"[^\\/\s]+(?:[\\/]+[^\\/\s]+)*?[\\/]+users[\\/]+"
        r"([^\\/\s\"'`,;:)\]}>]+)"
    ),
]


def _is_placeholder_or_allowed(segment: str) -> bool:
    seg = segment.strip().strip("\\/").lower()
    if not seg:
        return True
    if seg and set(seg) <= _ELLIPSIS_CHARS:
        return True  # ellipsis/dot placeholder such as "...", "\u2026", "." used in docs
    if re.fullmatch(_PLACEHOLDER, segment.strip()):
        return True
    if seg in ALLOWED_USER_TOKENS:
        return True
    # A segment that is itself a placeholder fragment like "<you>" with trailing punctuation.
    if seg.startswith("<") or seg.startswith("%") or seg.startswith("$"):
        return True
    return False


def find_machine_paths(text: str) -> list[str]:
    """Return concrete machine-local path prefixes found in text (deduped)."""
    hits: list[str] = []
    for pat in _PATTERNS:
        for m in pat.finditer(text):
            segment = m.group(1)
            if _is_placeholder_or_allowed(segment):
                continue
            hits.append(m.group(0).strip().strip("\"'`(=") )
    # dedup preserving order
    seen: set[str] = set()
    out: list[str] = []
    for h in hits:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return out


def _target_path(tool_input: dict) -> str:
    for key in ("file_path", "notebook_path", "path"):
        v = tool_input.get(key)
        if isinstance(v, str) and v:
            return v
    return ""


def _is_scratch_target(target: str) -> bool:
    norm = target.replace("\\", "/").lower()
    return "/.scratch/" in norm or norm.startswith(".scratch/") or norm == ".scratch"


_PATCH_FILE_HEADER = re.compile(r"^\*\*\* (?:Add|Update|Delete|Move) File:\s*(?P<target>.+?)\s*$")
_PATCH_MOVE_HEADER = re.compile(r"^\*\*\* Move to:\s*(?P<target>.+?)\s*$")


def _patch_written_content(patch: str) -> list[tuple[str, str]]:
    """Return target-routed added lines, or one unknown fallback for malformed input."""

    current_target = ""
    parts: list[tuple[str, str]] = []
    recognized_header = False
    for line in patch.splitlines():
        header = _PATCH_FILE_HEADER.fullmatch(line) or _PATCH_MOVE_HEADER.fullmatch(line)
        if header is not None:
            current_target = header.group("target")
            recognized_header = True
            continue
        if line.startswith("+"):
            parts.append((current_target, line[1:]))
    if not recognized_header:
        return [("", patch)]
    return parts


def _native_apply_patch_command(envelope: dict, tool_input: dict) -> str | None:
    """Return only the verified native apply-patch carrier with complete framing."""

    command = tool_input.get("command")
    if envelope.get("tool_name") != "apply_patch":
        return None
    if not isinstance(command, str):
        return None
    lines = command.splitlines()
    if len(lines) < 2 or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        return None
    return command


def _content_to_scan(envelope: dict, tool_input: dict) -> list[tuple[str, str]]:
    """Return written string content paired with its known target when available.

    Apply-patch routing headers and removed/context lines are not written content.
    Other supported Write/Edit controls retain the existing scan of every string
    value except their target-path keys.
    """
    path_keys = {"file_path", "notebook_path", "path"}
    target = _target_path(tool_input)
    native_command = _native_apply_patch_command(envelope, tool_input)
    parts: list[tuple[str, str]] = []
    for key, val in tool_input.items():
        if key in path_keys:
            continue
        if key == "patch" and isinstance(val, str):
            parts.extend(_patch_written_content(val))
        elif key == "command" and native_command is not None:
            parts.extend(_patch_written_content(native_command))
        elif isinstance(val, str):
            parts.append((target, val))
        elif isinstance(val, list):
            for item in val:
                if key == "patch" and isinstance(item, str):
                    parts.extend(_patch_written_content(item))
                elif isinstance(item, str):
                    parts.append((target, item))
    return parts


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return 0  # malformed envelope -> fail open

    tool_input = envelope.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0  # nothing to inspect; allow

    target = _target_path(tool_input)
    for content_target, text in _content_to_scan(envelope, tool_input):
        effective_target = content_target or target
        if effective_target and _is_scratch_target(effective_target):
            continue  # .scratch/ is the designated local-only evidence area; allow
        hits = find_machine_paths(text)
        if hits:
            shown = ", ".join(hits[:5])
            emit_advisory(
                envelope,
                "[machine-local-path AUDIT] candidate machine-local path(s) in write to "
                f"{effective_target or '<unknown target>'}: {shown} "
                "(machine-local-path-provenance rule: use a repo-neutral placeholder "
                "such as <repo>, %USERPROFILE%, or ${CLAUDE_PROJECT_DIR}, or keep the "
                "exact path only under .scratch/. AUDIT mode -- allowing this write.)",
            )
            # Exit 0: the advisory reaches the model via hookSpecificOutput.
            # additionalContext (see hook_common.emit_advisory) -- never exit 2 (block).
            return 0
    # AUDIT mode: always allow the write. (Promotion to a blocking PreToolUse
    # deny -- exit 2 -- is a separate reviewed step once the false-positive
    # rate is measured.)
    return 0


if __name__ == "__main__":
    sys.exit(main())

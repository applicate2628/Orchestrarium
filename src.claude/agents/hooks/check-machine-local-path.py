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

AUDIT mode (current posture): on a hit, print a warning to stderr and ALLOW
(exit 0). This lets the false-positive rate be measured over real repos before
the hook is promoted to a blocking `deny`. Promotion to block is a separate,
reviewed step once the allowlist is proven tight (per the reviewed Phase-0.2
plan: dry-run/audit first, measure FP, then decide block-vs-warn).

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

from hook_common import parse_envelope, read_stdin_utf8


def _emit(msg: str) -> None:
    """Write a warning to stderr as UTF-8 bytes, regardless of console codepage.

    On Windows the default stderr encoding is the console codepage (e.g. cp1252),
    so a non-ASCII character (or non-ASCII data such as a Cyrillic path) is
    written as bytes a UTF-8 consumer cannot decode — Claude Code and the test
    harness both read hook stderr as UTF-8. Writing UTF-8 bytes directly keeps
    the warning readable everywhere. Mirrors hook_common.read_stdin_utf8 on the
    write side. Fail-open on any error.
    """
    try:
        sys.stderr.buffer.write(msg.encode("utf-8"))
        sys.stderr.buffer.flush()
    except Exception:
        try:
            sys.stderr.write(msg)
        except Exception:
            pass


# A path segment that is a placeholder, not a concrete machine name.
_PLACEHOLDER = r"(?:<[^>\\/\s]+>|%[^%\\/\s]+%|\$\{[^}\s]+\}|\$[A-Za-z_][A-Za-z0-9_]*)"

# Example/placeholder usernames that are not real machine leaks (case-insensitive).
ALLOWED_USER_TOKENS = {"you", "user", "username", "name", "test", "example", "me", "x"}

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
]


def _is_placeholder_or_allowed(segment: str) -> bool:
    seg = segment.strip().strip("\\/").lower()
    if not seg:
        return True
    if set(seg) <= {"."}:
        return True  # ellipsis/dot placeholder such as "..." used in docs
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


def _content_to_scan(tool_input: dict) -> str:
    """Join the string values being written (content, new_string, command, patch...).

    apply_patch and other tools vary in key names, so scan every string value
    rather than enumerating keys — except the path keys, which are the target,
    not written content (the target leak is handled separately if needed).
    """
    path_keys = {"file_path", "notebook_path", "path"}
    parts: list[str] = []
    for key, val in tool_input.items():
        if key in path_keys:
            continue
        if isinstance(val, str):
            parts.append(val)
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    parts.append(item)
    return "\n".join(parts)


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return 0  # malformed envelope -> fail open

    tool_input = envelope.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0  # nothing to inspect; allow

    target = _target_path(tool_input)
    if target and _is_scratch_target(target):
        return 0  # .scratch/ is the designated local-only evidence area; allow

    text = _content_to_scan(tool_input)
    if not text:
        return 0

    hits = find_machine_paths(text)
    if hits:
        shown = ", ".join(hits[:5])
        _emit(
            "[machine-local-path AUDIT] candidate machine-local path(s) in write to "
            f"{target or '<unknown target>'}: {shown}\n"
            "  (machine-local-path-provenance rule: use a repo-neutral placeholder "
            "such as <repo>, %USERPROFILE%, or ${CLAUDE_PROJECT_DIR}, or keep the "
            "exact path only under .scratch/. AUDIT mode -- allowing this write.)\n"
        )
    # AUDIT mode: always allow. (Promotion to PreToolUse deny is a separate
    # reviewed step once the false-positive rate is measured.)
    return 0


if __name__ == "__main__":
    sys.exit(main())

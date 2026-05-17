#!/usr/bin/env python3
"""Bugfix-discipline guard for the PreToolUse hook.

Catches the case where the model is about to make a code-mutating tool call
(Edit/Write/NotebookEdit on Claude, apply_patch on Codex) in response to a
bug report, but did NOT first invoke /agents-bugfix (or its underlying
diagnostic-first discipline). The intent: the bugfix skill already encodes
"capture diagnostic data → form hypothesis → verify → then edit"; this hook
is the safety net for sessions where the model skipped that skill and went
straight to editing.

Decision algorithm (fail-open everywhere on internal error):

  1. Read PreToolUse JSON envelope from stdin. Extract transcript_path.
  2. If no transcript_path or file missing → exit 0 (cannot determine, allow).
  3. Parse the recent transcript JSONL. Find the last user message and all
     assistant/tool messages after it (the "current turn").
  4. Examine the last user message text:
     - If it contains an explicit override marker → exit 0 (allow).
     - If it does NOT contain any bug-trigger phrase → exit 0 (not a bug
       report; allow).
  5. Bug-trigger phrase present. Examine the current turn (everything after
     the last user message) for bugfix-discipline signals:
     - Skill invocation with skill=agents-bugfix
     - Read of agents-bugfix command/skill file
     - Text markers indicating diagnostic capture occurred (file:line
       citation, "reproducing", "diagnostic", "hypothesis", "VERIFIED")
     - Bash/PowerShell tool calls that look like diagnostic probes
       (grep on logs, file reads of mentioned paths)
  6. If any signal present → exit 0 (model is following the flow, allow).
  7. Otherwise → emit a structured deny payload telling the model exactly
     what to do (invoke skill, capture diagnostics, or write override marker).

The hook is bypassable in principle — the model can fake any signal — but
it catches the common omission of "saw bug report, went straight to Edit"
which is the failure mode this exists to prevent.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Bug-trigger and change-request phrases — English + Russian + universal markers.
#
# Design choice (user explicit, 2026-05-17): trigger BROADLY. The common harm
# case is "user says исправь/пофикси/поменяй, model jumps to first hypothesis
# and edits without diagnostics". Catching that requires the trigger list to
# include routine change-request verbs, not only obvious bug-indicators. The
# cost is false positives on legitimate non-bug change requests ("fix typo",
# "change wording") — those are handled by the [skip-bugfix-discipline]
# override marker described in the deny message. Friction is by design.
#
# Two tiers organized in the regex below:
#   Tier 1 (strong) — almost always a bug-report: broken, не работает,
#     regression, traceback, error:, hook (failed), падает, вешает, etc.
#   Tier 2 (weak)   — change-request verbs that often signal "fix the
#     behavior" but sometimes are routine: fix, change, repair, исправь,
#     пофикси, поменяй, почини, edit.
# Both tiers trigger the guard equally; the override marker is the escape.
BUG_TRIGGER_REGEX = re.compile(
    r"(?ix)"  # case-insensitive, verbose
    r"\b("
    # Tier 1 — strong (bug-indicating) signals
    r"broken|"
    r"doesn['’]?t\s+work|not\s+working|stopped\s+working|"
    r"regression|"
    r"traceback|"
    r"exit\s+code\s+[1-9]|"
    r"hook\s+\(failed\)|"
    r"crash(?:ed|es|ing)?|"
    r"не\s+работает|"
    r"сломан|сломалось|сломалась|"
    r"падает|падают|вешает|глючит|"
    r"бажит|багует|"
    r"крашится|крашит|"
    # Tier 2 — weak (change-request) signals
    r"fix|change|repair|edit|"
    r"исправь|исправить|"
    r"пофикси|пофиксить|пофиксь|"
    r"поменяй|поменять|"
    r"почини|починить|"
    r"переделай|переделать|"
    r"подправь|подправить"
    r")\b"
    r"|"
    r"(?:^|\W)Error\s*:|"  # 'Error:' pattern
    r"(?:^|\W)PreToolUse\s+hook"  # exact symptom format from prior session
)

# Override marker — explicit way to say "this is not a bug-fix; skip the check".
# Use bracketed token unlikely to appear by accident.
OVERRIDE_MARKER_REGEX = re.compile(
    r"\[skip-bugfix-discipline\]|\[not-a-bugfix\]",
    re.IGNORECASE,
)

# Bugfix-discipline signals in the current turn — any of these present means
# the model engaged with the diagnostic flow.
BUGFIX_SIGNAL_REGEX = re.compile(
    r"(?ix)"
    r"agents-bugfix|"
    r"/agents-bugfix\b|"
    r"diagnostic|"
    r"hypothesis|"
    r"reproducing|"
    r"\brepro\b|"
    r"VERIFIED\s*:|"
    r"ASSUMPTION\s*\(UNVERIFIED\)|"
    r"Pre-fix\s+diagnostic\s+gate|"
    r"Bootstrap"
)

# How many lines of transcript JSONL to read. The current turn is usually
# within the last ~50 entries; reading more wastes I/O.
TRANSCRIPT_TAIL_LINES = 100


def main() -> int:
    try:
        envelope = json.load(sys.stdin)
    except Exception:
        return 0  # malformed envelope → fail open

    transcript_path = envelope.get("transcript_path") or ""
    if not transcript_path:
        return 0
    tp = Path(transcript_path)
    if not tp.is_file():
        return 0

    try:
        raw = tp.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return 0

    lines = raw.splitlines()[-TRANSCRIPT_TAIL_LINES:]

    # Walk transcript in reverse to find the last user message; everything
    # after it is the "current turn" we examine for discipline signals.
    last_user_entry = None
    after_user_entries: list[dict] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except Exception:
            continue
        if _is_user_message(entry):
            last_user_entry = entry
            break
        after_user_entries.append(entry)
    after_user_entries.reverse()

    if last_user_entry is None:
        return 0  # no user message in scope; allow

    user_text = _extract_text(last_user_entry)

    if OVERRIDE_MARKER_REGEX.search(user_text):
        return 0  # explicit override; allow

    if not BUG_TRIGGER_REGEX.search(user_text):
        return 0  # not bug context; allow

    # Bug-context confirmed. Check current turn for discipline signals.
    haystack_parts = [_extract_text(e) for e in after_user_entries]
    haystack = "\n".join(p for p in haystack_parts if p)
    if BUGFIX_SIGNAL_REGEX.search(haystack):
        return 0  # discipline engaged; allow

    # Deny.
    tool_name = envelope.get("tool_name", "<unknown>")
    reason = (
        f"Bugfix-discipline guard: about to invoke `{tool_name}` in a session "
        f"where the most recent user message contains a bug-report signal "
        f"(e.g. 'broken', 'не работает', 'error:', 'fix this', traceback, "
        f"or similar), but no diagnostic-first discipline has run in this "
        f"turn — no /agents-bugfix invocation, no captured diagnostic data, "
        f"no stated hypothesis.\n\n"
        f"Pick one before retrying:\n\n"
        f"  (a) Invoke /agents-bugfix to apply the diagnostic-first flow. "
        f"This is the canonical path.\n\n"
        f"  (b) Capture diagnostic data first: read the failing file at the "
        f"reported file:line, run a probe to reproduce the error, then "
        f"state your hypothesis chain explicitly in the conversation. After "
        f"that, retry the edit.\n\n"
        f"  (c) If this is genuinely NOT a bug-fix task (e.g. user said "
        f"'fix this typo' meaning a docs edit, or used a bug-trigger word "
        f"in a non-bug context), reply to the user with `[skip-bugfix-"
        f"discipline]` in your message acknowledging the override, then "
        f"retry. The marker disables this guard for the next turn only."
    )

    payload = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }
    print(json.dumps(payload))
    return 0


def _is_user_message(entry: dict) -> bool:
    """Detect a user message across Claude Code + Codex transcript shapes."""
    # Claude Code transcript: {"type":"user","message":{"role":"user",...}}
    if entry.get("type") == "user":
        return True
    # Bare role field
    if entry.get("role") == "user":
        return True
    # Nested message
    msg = entry.get("message")
    if isinstance(msg, dict) and msg.get("role") == "user":
        return True
    return False


def _extract_text(entry: object) -> str:
    """Pull human-readable text out of a transcript entry across shapes."""
    if not isinstance(entry, dict):
        return ""

    # Direct content field (string or list-of-blocks)
    content = entry.get("content")
    if content is None:
        msg = entry.get("message")
        if isinstance(msg, dict):
            content = msg.get("content")

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                parts.append(str(item))
                continue
            # Text block
            if "text" in item:
                parts.append(str(item["text"]))
            # Tool use: name + input
            if "name" in item:
                parts.append(str(item["name"]))
            if "input" in item:
                try:
                    parts.append(json.dumps(item["input"]))
                except Exception:
                    parts.append(str(item["input"]))
            # Tool result: content
            if "content" in item and not isinstance(item.get("content"), str):
                parts.append(_extract_text({"content": item["content"]}))
            elif isinstance(item.get("content"), str):
                parts.append(item["content"])
        return "\n".join(parts)

    # Codex transcript: top-level command / output strings
    for key in ("command", "output", "stdout", "stderr", "text"):
        v = entry.get(key)
        if isinstance(v, str):
            return v

    return ""


if __name__ == "__main__":
    sys.exit(main())

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
  3. Parse the recent transcript JSONL. Find the last GENUINE user-typed
     message — skipping tool_result entries and harness injections
     (system-reminder / task-notification), which are recorded under role=user
     in Claude Code — and treat everything after it as the "current turn".
     Handles both Claude (`message.content`) and Codex (`payload`/`input_text`)
     transcript shapes.
  4. Examine the genuine user message plus the assistant's PROSE this turn:
     - If the override marker appears in the user message OR in assistant prose
       → exit 0 (allow). It is NOT honored from tool output or tool-call input,
       because file content the model edits/reads can contain the literal
       marker (it is present in several tracked repo files).
     - If the user message contains no bug-trigger phrase → exit 0 (allow).
  5. Bug-trigger present. The turn counts as engaging discipline iff either:
     - a broad discipline signal (a stated "hypothesis", "diagnostic",
       "VERIFIED:", "reproducing", a file:line citation, ...) appears in the
       assistant's PROSE; or
     - an /agents-bugfix invocation appears in the model's tool CALLS (Claude
       tool_use / Codex function_call name+arguments), matched narrowly.
     Tool OUTPUT and broad words inside arbitrary tool-call INPUT never count
     (they are file content / command output, not the model engaging).
  6. If discipline engaged → exit 0 (allow).
  7. Otherwise → emit a structured deny payload telling the model exactly what
     to do (invoke /agents-bugfix, capture diagnostics and state the hypothesis
     in the conversation, or write the override marker in its reply).

The hook is bypassable in principle — the model can fake any signal — but
it catches the common omission of "saw bug report, went straight to Edit"
which is the failure mode this exists to prevent.
"""
from __future__ import annotations

import json
import re
import sys

from hook_common import (
    extract_assistant_prose,
    extract_model_tool_calls,
    last_genuine_user_message,
    parse_envelope,
    read_stdin_utf8,
    read_transcript_tail,
)

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

# Narrow: an actual /agents-bugfix INVOCATION counts as discipline even with no
# prose. Kept separate from BUGFIX_SIGNAL_REGEX and matched ONLY against the
# model's tool calls, so the broad prose words above (diagnostic/hypothesis/...)
# cannot be satisfied merely by appearing inside arbitrary tool-call input
# (e.g. a file the model is editing that happens to contain them).
BUGFIX_INVOCATION_REGEX = re.compile(r"agents-bugfix", re.IGNORECASE)

# How many lines of transcript JSONL to read. The current turn is usually
# within the last ~50 entries; reading more wastes I/O.
TRANSCRIPT_TAIL_LINES = 100


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return 0  # malformed envelope -> fail open

    transcript_path = envelope.get("transcript_path") or ""
    if not transcript_path:
        return 0

    entries = read_transcript_tail(transcript_path, TRANSCRIPT_TAIL_LINES)

    # Find the last GENUINE user-typed message (skipping tool_result and
    # harness-injected entries like system-reminder / task-notification);
    # everything after it is the true current turn we examine for discipline
    # signals. Matching triggers against the genuine message — not the most
    # recent tool_result, which is what the naive "last user-role entry" used
    # to return — is what stops the long-session false positives (and also
    # fixes the false negative where a real bug report sits behind many
    # tool_result entries).
    last_user_entry, user_text, after_user_entries = last_genuine_user_message(entries)

    if last_user_entry is None:
        return 0  # no genuine user message in scope; allow

    # The override marker AND the broad discipline signals (a stated hypothesis,
    # "diagnostic", "VERIFIED:", ...) come ONLY from the model's own PROSE reply
    # — never from tool output, never from tool-call input. File content the
    # model edits or reads can contain the literal `[skip-bugfix-discipline]`
    # marker or those signal words (the marker is present in several tracked
    # repo files), so matching them against tool I/O was a real bypass in both
    # directions. extract_assistant_prose returns assistant text blocks only.
    prose_haystack = "\n".join(
        t for t in (extract_assistant_prose(e) for e in after_user_entries) if t
    )
    if OVERRIDE_MARKER_REGEX.search(user_text) or OVERRIDE_MARKER_REGEX.search(prose_haystack):
        return 0  # explicit override; allow

    if not BUG_TRIGGER_REGEX.search(user_text):
        return 0  # not bug context; allow

    if BUGFIX_SIGNAL_REGEX.search(prose_haystack):
        return 0  # discipline stated in the model's prose; allow

    # An actual /agents-bugfix INVOCATION also counts as discipline — matched by
    # the narrow BUGFIX_INVOCATION_REGEX against the model's tool CALLS only
    # (Claude tool_use name/input, Codex function_call name/arguments), so a
    # broad word inside arbitrary tool-call input does not satisfy this gate.
    tool_call_haystack = "\n".join(
        t for t in (extract_model_tool_calls(e) for e in after_user_entries) if t
    )
    if BUGFIX_INVOCATION_REGEX.search(tool_call_haystack):
        return 0  # discipline engaged via an /agents-bugfix invocation; allow

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

if __name__ == "__main__":
    sys.exit(main())

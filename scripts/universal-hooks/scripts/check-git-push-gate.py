#!/usr/bin/env python3
"""Git-push publication gate (PreToolUse, BLOCKING) — structural backstop for
the human-review-before-push rule.

WHAT THIS DENIES: a Bash command that confidently runs `git push` in command
position, when the current turn shows neither (a) the per-turn user-side
override marker `[approve-publication]` in the LAST GENUINE USER MESSAGE, nor
(b) evidence of a publication-safety scan invocation this turn (a
`check-publication-safety` / `check-publication-gate` / `agents-check-safety`
command among the model's own tool calls) combined with an explicit push
instruction in the last genuine user message.

WHY: `git push` is the highest-stakes irreversible action the pack governs —
"Human review before git push ... must include a leak-check of staged changes"
was prose-only while lower-stakes edit/stop moments got blocking hooks. This
hook closes that asymmetry.

HONESTY RULE — THIS IS A BACKSTOP, NOT A GUARANTEE. It under-detects by design
(a push wrapped in a script the hook only sees as `bash sync.sh`, `eval`,
command substitution, or another command-wrapper is not modelled), a model can
fake the scan-evidence signal, and the transcript may be unavailable (then the
hook fails open). The binding rule remains the governance text: human review +
publication-safety leak-check before any push. Do not represent this hook as
enforcing that rule; it only catches the common momentum failure of running
`git push` in the same breath as the commit.

Decision algorithm (fail-open everywhere on internal error):

  1. Read the PreToolUse JSON envelope from stdin.
  2. If the envelope carries `agent_id` (a subagent context) → exit 0 (allow;
     mirrors check-bugfix-discipline.py — a subagent cannot inject the
     user-side override into the main transcript, so gating it here is an
     un-overridable false positive. Governance still forbids delegating a
     push to a subagent to dodge review).
  3. If `tool_input.command` is absent or empty → exit 0 (not a shell command).
  4. Parse the command with the shared shell-aware command-position parser
     (shlex tokens, separators, env-assignment prefixes, git global options —
     the check-no-trash-in-repo.py technique). No `git push` in command
     position → exit 0. `git push` inside a quoted string is NOT a command.
  5. Every detected push carrying `--dry-run` → exit 0 (nothing is sent).
  6. If no transcript_path / unreadable transcript → exit 0 (cannot determine;
     fail open).
  7. If the LAST GENUINE USER MESSAGE contains `[approve-publication]` →
     exit 0. The marker is honored ONLY from the user's own text — never from
     assistant prose, tool calls, or tool output — because prior provider or
     file content quoting the marker must not approve a publication.
  8. If the current turn (entries after the last genuine user message) shows a
     publication-safety scan invocation among the model's own tool CALLS AND
     the last genuine user message contains an explicit push-instruction
     signal (`push`, `запушь`, `залей`, ...) → exit 0.
  9. Otherwise → emit a structured `permissionDecision: "deny"` payload with
     exact compliance instructions. Always exit 0 (the decision is carried by
     the stdout payload, not the exit code).
"""
from __future__ import annotations

import json
import re
import shlex
import sys

from hook_common import (
    extract_model_tool_calls,
    last_genuine_user_message,
    parse_envelope,
    read_stdin_utf8,
    read_transcript_tail,
)

# Per-turn override marker — honored ONLY from the last genuine user message.
# User-side only by design: assistant prose can be steered by injected content
# (see the consultant continuation-prompt untrusted-data rule), so unlike
# [skip-bugfix-discipline] this marker never counts from the model's own reply.
APPROVE_MARKER_REGEX = re.compile(r"\[approve-publication\]", re.IGNORECASE)

# Explicit user push-instruction signal (English + Russian). Matched against
# the last genuine user message only; used together with scan evidence.
PUSH_INSTRUCTION_REGEX = re.compile(
    r"(?ix)"
    r"\bpush\b|git\s+push|\bpublish\b|"
    r"запушь|запушить|запушь?те|пушни|пушь|пуш|пушай|пушить|"
    r"залей|залить|"
    r"опубликуй|опубликовать|публикуй"
)

# Publication-safety scan invocation — matched narrowly against the model's own
# tool CALLS in the current turn (never prose, never tool output), so a file or
# doc merely mentioning the scanner cannot satisfy the gate.
SCAN_INVOCATION_REGEX = re.compile(
    r"check-publication-safety|check-publication-gate|agents-check-safety",
    re.IGNORECASE,
)

# How many transcript JSONL lines to read (same tail budget as the sibling
# bugfix-discipline hook).
TRANSCRIPT_TAIL_LINES = 100

# `git` global options that consume a SEPARATE following token as their value;
# skipped together with their value when scanning for the subcommand (so
# `git -C /x push` is still seen as a push).
_GIT_VALUE_OPTS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path", "--config-env"}

# Shell keywords that PRECEDE a command without consuming the command slot
# (`if ...; then git push; fi`, `for b in x; do git push; done`).
_SHELL_KEYWORDS = {"if", "then", "elif", "else", "while", "until", "do", "!"}


def find_git_push_invocations(command: str) -> list[list[str]]:
    """Return the argument-token list of each `git push` found in command position.

    Same shell-aware technique as check-no-trash-in-repo.py's
    count_git_worktree_adds: tokenize with `shlex` (quotes honored — `git push`
    inside a quoted string is data, not a command), track command position
    across separators (`;`, `&&`, `||`, `|`, `&`, `(`, `)`), allow an
    env-assignment prefix, treat leading shell keywords as
    command-slot-transparent, skip git global options (and the value of
    value-taking ones), and require the first non-option token after `git` to
    be `push`. Each detected push contributes the token list up to the next
    separator, so the caller can check for `--dry-run`. Constructs that hide
    `git` behind another command word (`bash sync.sh`, `eval`, `$(...)`,
    `xargs`, ...) are not modelled and under-detect — acceptable for a backstop
    that must fail open. Any tokenizer error returns [] (fail open)."""
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        tokens = list(lexer)
    except ValueError:
        return []  # unbalanced quotes / unparseable -> fail open

    pushes: list[list[str]] = []
    current_args: list[str] | None = None  # collecting args of an active `git push`
    expect_command = True
    in_git = False
    skip_value = False
    skip_redir_target = False
    for tok in tokens:
        if not tok:
            continue
        if skip_redir_target:
            skip_redir_target = False
            continue
        if skip_value:
            skip_value = False
            continue
        # A redirection operator (`>`, `>>`, `<`, `2>`, `&>`, ...) is not a
        # command separator; the next token is its target, not a command/arg.
        if ("<" in tok or ">" in tok) and all(c in "<>&" for c in tok):
            skip_redir_target = True
            continue
        # Command separators -> the next token starts a new command.
        if all(c in ";|&()" for c in tok):
            expect_command = True
            in_git = False
            current_args = None
            continue
        if current_args is not None:
            current_args.append(tok)
            continue
        if expect_command:
            # env-assignment prefix (`FOO=bar git push`) keeps the command slot open
            if "=" in tok and tok.split("=", 1)[0].isidentifier():
                continue
            # leading shell keyword keeps the command slot open
            if tok in _SHELL_KEYWORDS:
                continue
            in_git = tok == "git" or tok.endswith("/git")
            expect_command = False
            continue
        if not in_git:
            continue  # operand of some non-git command
        if tok in _GIT_VALUE_OPTS:
            skip_value = True
            continue
        if tok.startswith("-"):
            continue  # other git global option
        # first non-option token after `git` = the subcommand
        if tok == "push":
            current_args = []
            pushes.append(current_args)
        else:
            in_git = False  # a different git subcommand -> not our concern
    return pushes


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return 0  # malformed envelope -> fail open

    # Subagent context: mirrors check-bugfix-discipline.py. The subagent's
    # envelope points at the MAIN session transcript, and the subagent cannot
    # put the user-side [approve-publication] marker there — gating it here is
    # an un-overridable false block. Governance still forbids delegating a
    # push to a subagent to dodge review; this hook stays a backstop.
    if envelope.get("agent_id"):
        return 0

    tool_input = envelope.get("tool_input")
    if not isinstance(tool_input, dict):
        return 0

    command = tool_input.get("command")
    if not isinstance(command, str) or not command:
        return 0

    pushes = find_git_push_invocations(command)
    if not pushes:
        return 0  # no `git push` in command position

    if all("--dry-run" in args for args in pushes):
        return 0  # every push is a dry run; nothing is sent

    transcript_path = envelope.get("transcript_path") or ""
    if not transcript_path:
        return 0  # cannot determine turn state; fail open

    entries = read_transcript_tail(transcript_path, TRANSCRIPT_TAIL_LINES)
    last_user_entry, user_text, after_user_entries = last_genuine_user_message(entries)

    if last_user_entry is None:
        user_text = ""

    # (a) Per-turn user-side override — the marker counts ONLY from the last
    # genuine user message, never from assistant prose / tool calls / output.
    if APPROVE_MARKER_REGEX.search(user_text):
        return 0

    # (b) Publication-safety scan invoked this turn (model tool CALLS only)
    # AND the user explicitly instructed a push in their last message.
    if PUSH_INSTRUCTION_REGEX.search(user_text):
        tool_call_haystack = "\n".join(
            t for t in (extract_model_tool_calls(e) for e in after_user_entries) if t
        )
        if SCAN_INVOCATION_REGEX.search(tool_call_haystack):
            return 0

    # Deny.
    reason = (
        "Git-push publication gate: this Bash command runs `git push` (an "
        "irreversible publication), but this turn shows neither the per-turn "
        "user approval marker nor a publication-safety scan.\n\n"
        "Publication requires human review PLUS a leak-check of staged changes "
        "(Publication safety governance). Pick one before retrying:\n\n"
        "  (a) If the user has NOT explicitly approved this push: STOP, report "
        "readiness to push, and ask the user to approve. The user approves by "
        "including `[approve-publication]` in their next message; then retry. "
        "The marker is honored only from the user's own message and only for "
        "that turn.\n\n"
        "  (b) If the user already instructed you to push in their last "
        "message: run the publication-safety scan FIRST in this turn — "
        "`bash .claude/agents/scripts/check-publication-safety.sh` (or the "
        ".ps1 twin / /agents-check-safety), fix or disclose any findings, then "
        "retry the push. The gate opens only when the scan invocation is "
        "visible in this turn AND the user's last message contains the push "
        "instruction.\n\n"
        "  (c) To test what would be sent without publishing, use "
        "`git push --dry-run` — it is always allowed.\n\n"
        "This hook is a BACKSTOP for the human-review-before-push rule, not a "
        "replacement for it. Do not work around it by wrapping the push in a "
        "script or delegating it to a subagent — that violates the same rule "
        "this gate protects."
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

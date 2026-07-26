#!/usr/bin/env python3
"""Typed-routing nudge for the PreToolUse hook -- AUDIT mode (never blocks).

WHY THIS EXISTS.
The orchestrator sometimes dispatches the built-in catch-all subagent
(`subagent_type: general-purpose`) for work a typed pack role owns -- an
implementation, review, design, security, performance, or toolchain task. The
pack ships a typed roster (`.claude/agents/*.md`) precisely so specialist work
routes to the matching role and its gate; a `general-purpose` dispatch for that
work silently bypasses the roster. This hook fires at the dispatch decision --
the only moment that choice is observable -- and warns (never blocks) that a
matching typed role exists.

SCOPE -- deliberately narrow (a nudge that fires on every dispatch is noise, and
noise trains the reader to ignore the whole class -- the same reason the sibling
mcp-momentum audit only fires when a call *looks like* code-navigation):
  * only the catch-all `subagent_type` in CATCH_ALL_TYPES (`general-purpose`);
    `Explore` / setup agents are deliberately excluded -- `Explore` is a
    legitimate read-only search agent, not a specialist-work substitute.
  * only when the dispatch prompt/description carries a SPECIALIST-WORK signal
    (implementation / review / design / security / performance / toolchain
    marker). A `general-purpose` dispatch for a genuinely open-ended one-off read
    is left alone -- that is where the false positives would otherwise cluster.
  * never inside a subagent context (`agent_id` present) -- a nested dispatch
    runs its own policy; the guard is for the orchestrating conversation, exactly
    like every sibling audit.

PHASE-0 CAPTURED ENVELOPE SHAPE (runtime, this Claude Code version).
The dispatch-tool `tool_name` and field path were UNVERIFIED at design time (the
design assumed `Task`). Captured from real session transcripts
(`~/.claude/projects/**/*.jsonl`, 1121 real Agent-dispatch tool_use blocks): the
subagent-dispatch tool_use `name` is `Agent` (NOT `Task`), and its `input`
always carries `subagent_type` alongside `description` + `prompt` (and optional
`model` / `run_in_background` / `effort` / `isolation`). The PreToolUse envelope
therefore surfaces `tool_name == "Agent"` and `tool_input.subagent_type`.

FAIL-SAFE (a wrong shape makes the hook INERT, never a false block).
The hook keys on a NAMED tool_name constant (DISPATCH_TOOL) and a NAMED field
(SUBAGENT_TYPE_FIELD). If the envelope's `tool_name` is not DISPATCH_TOOL, or the
field is absent / not a string, it `exit 0` (silent) -- so if a future Claude
version renames the dispatch tool or moves the field, this hook simply never
fires until the constants are re-pinned to a freshly captured shape. It can never
manufacture a false block from a shape mismatch.

AUDIT mode: ALWAYS ALLOW the tool call, never block. On a nudge, deliver the
warning to the MODEL via `hookSpecificOutput.additionalContext` on stdout, exit
0 (see `hook_common.emit_advisory`). This is the corrected delivery channel: a
PreToolUse hook's previous stderr-plus-exit-1 form was measured to reach NOBODY
on Claude Code 2.1.220 -- transcript-only, model-invisible (this hook is
Claude-only; see work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-
session-form-its-sibling-calls-broken.md for the full falsification-controlled
measurement, including the sibling-runtime Codex CLI 0.145.0 result). Warn-only
needs NO override marker -- the model proceeds regardless -- which keeps the
surface minimal. Promotion to a blocking `deny` (exit 2) stays a separate
reviewed step after the false-positive rate is measured from transcripts, the
pack's standing audit-promotion discipline.

Fail-open everywhere on internal error (return 0).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

try:
    from hook_common import emit_advisory, parse_envelope, read_stdin_utf8
except Exception:  # pragma: no cover - fail open when the shared helper is absent
    def read_stdin_utf8() -> str:  # type: ignore[misc]
        return ""

    def parse_envelope(_: str) -> dict:  # type: ignore[misc]
        return {}

    def emit_advisory(_envelope: object, _message: str, **_kwargs: object) -> None:  # type: ignore[misc]
        pass


# The subagent-dispatch tool as it appears in the PreToolUse envelope's
# `tool_name` (Phase-0 captured from real transcripts: "Agent", not "Task").
# A named constant so a shape mismatch makes the hook inert, never a false block.
DISPATCH_TOOL = "Agent"
SUBAGENT_TYPE_FIELD = "subagent_type"

# Built-in catch-all subagent types that are NOT a typed pack role. `general-purpose`
# is the open-ended default; `Explore` and setup agents are deliberately absent --
# `Explore` is a legitimate read-only search agent, not a specialist-work substitute.
# Compared casefolded.
CATCH_ALL_TYPES = {"general-purpose"}

# A specialist-work signal in the dispatch prompt/description: an implementation,
# review, design, security, performance, or toolchain marker. Mirrors the
# mcp-momentum "only fire when it looks like code-navigation" narrowing so a
# general-purpose dispatch for a genuinely open-ended read is left alone.
#
# Word-like stems are `\b`-anchored so a stem never matches inside an unrelated
# word: `\bfix` would hit "fixtures", `review` would hit "Preview", and bare
# `perform` would hit "Perform an open-ended search" -- all open-ended/read-only
# work that must NOT fire. `performance` (not `perform`) is the real signal;
# `\bdesign(...)` excludes "designated"; `\baudit(...)` excludes "auditory". The
# `.ps1`/`.py`/`.ts` extension stems stay literal -- the leading dot already
# delimits them.
SPECIALIST_SIGNAL_RE = re.compile(
    r"\bimplement\w*|\bfix(?:e[sd]|ing)?\b|\bbuild\w*|\brefactor\w*|"
    r"\.ps1|\.py|\.ts|\btoolchain\w*|\binstall\w*|\bhooks?\b|"
    r"\breview\w*|\baudit(?:s|ed|ing|or)?\b|\bsecurity\b|\bperformance\w*|"
    r"\bdesign(?:s|ed|ing|er)?\b|\barchitect\w*|\bmigrat\w*",
    re.IGNORECASE,
)


def main() -> int:
    try:
        envelope = parse_envelope(read_stdin_utf8())
    except Exception:
        return 0
    if not isinstance(envelope, dict):
        return 0
    # A dispatched subagent runs its own tool policy; the nudge is for the
    # orchestrating conversation that chooses between general-purpose and a
    # typed role. Identical to every sibling audit.
    if envelope.get("agent_id"):
        return 0

    try:
        # Fail-safe: key on the named dispatch tool. A different/absent tool_name
        # makes the hook inert (never a false block).
        if str(envelope.get("tool_name") or "") != DISPATCH_TOOL:
            return 0

        tool_input = envelope.get("tool_input")
        if not isinstance(tool_input, dict):
            return 0

        subagent_type = tool_input.get(SUBAGENT_TYPE_FIELD)
        if not isinstance(subagent_type, str) or not subagent_type:
            return 0  # absent/malformed field -> inert (fail-safe)
        if subagent_type.casefold() not in CATCH_ALL_TYPES:
            return 0  # a typed pack role -> nothing to nudge

        # Scan the human-authored dispatch text (description + prompt) for a
        # specialist-work signal. A truly open-ended general-purpose dispatch has
        # none and is left alone.
        scan = "\n".join(
            str(tool_input.get(k) or "") for k in ("description", "prompt")
        )
        if not SPECIALIST_SIGNAL_RE.search(scan):
            return 0

        emit_advisory(
            envelope,
            "[typed-routing AUDIT] `general-purpose` was dispatched for work that "
            "looks like typed specialist work (an implementation/review/design/"
            "security/performance/toolchain signal is in the prompt) -- prefer the "
            "matching typed `subagent_type` from the roster `.claude/agents/*.md` "
            "(e.g. toolchain-engineer/platform-engineer for `.ps1`/install work, an "
            "engineer role for code, a reviewer role for review), or proceed if "
            "`general-purpose` is genuinely the right open-ended fit. AUDIT -- allowing.",
        )
        # Exit 0: the nudge reaches the model via hookSpecificOutput.
        # additionalContext (see hook_common.emit_advisory) -- never exit 2 (block).
        return 0
    except Exception:
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())

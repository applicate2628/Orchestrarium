#!/usr/bin/env python3
"""SessionStart hook that re-injects the active Claude delegation posture.

Python is the sole runtime owner. This pack-only implementation walks the
Claude read order (``./.claude/``, ``~/.claude/``, then the shared global file)
and speaks the Agent-tool dispatch idiom. The Codex implementation is
intentionally separate because its read order and role/skill vocabulary differ.
``delegationMode`` is not a Claude Code built-in, so this hook makes the
resolved ``force`` or ``auto`` posture visible to the conversation.

CONDITIONAL BY DESIGN: emits an IMPERATIVE directive ONLY when the effective
delegationMode is force or auto; SILENT on manual and on the no-file/
unresolved state (fail-safe). The silence is load-bearing -- the block
appears only when delegation is operative.

SELF-CONTAINED first-match read of the documented read-order (the full
resolver is NOT shipped to install targets; force/auto are always
file-explicit, and no file anywhere means the pack is not installed here /
the config was removed, so this does NOT inject a standing directive into an
arbitrary directory -- the defaults/normalizer layers stay out of scope on
purpose):
  ./.claude/.agents-mode.yaml -> ./.claude/.agents-mode ->
  ~/.claude/.agents-mode.yaml -> ~/.claude/.agents-mode -> ~/.agents-mode.yaml
  First file DEFINING delegationMode wins; none -> unresolved -> silent.

No stdin dependency: this hook never reads its own SessionStart envelope --
cwd comes from the process's working directory and home from USERPROFILE/HOME,
not from an envelope field.
Fail-open: any error yields "unresolved" (silent) and this always exits 0.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from hook_common import emit_session_start_context

# Strip the `delegationMode:` key prefix case-sensitively; `DelegationMode:`
# must not match.
_KEY_RE = re.compile(r"^delegationMode:\s*")
# A WHITESPACE-preceded ' #...' comment only, so a literal value like
# 'force#x' stays intact (no preceding whitespace -> not a comment -> stays
# literal -> unrecognized -> silent).
_COMMENT_RE = re.compile(r"\s+#.*$")

FORCE_CONTEXT = (
    '[Delegation posture - re-shown at session start and after every compaction]\nEffective delegationMode: FORCE. STANDING INSTRUCTION, not advisory: at the FIRST decision point of any non-trivial task (multi-step implementation, design, research, review, bug-fix), STOP - hold the $lead orchestration role in THIS conversation, classify the task, pick the team template, and route it via the Agent tool to the matching specialist subagents ($lead is the role you hold, not a subagent you spawn). Doing substantial work inline when a matching specialist and a viable tool path exist violates the active posture. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from contracts/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION.'
)
AUTO_CONTEXT = (
    '[Delegation posture - re-shown at session start and after every compaction]\nEffective delegationMode: AUTO. Holding the $lead orchestration role in THIS conversation and delegating to the matching specialist subagents via the Agent tool is the DEFAULT for any non-trivial task (multi-step implementation, design, research, review, bug-fix) - do it unless the task is trivial or you record why inline is better. $lead is the role you hold, not a subagent you spawn. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from contracts/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION.'
)


def _get_delegation_mode() -> str:
    """First-match read across the documented Claude-line read-order. Returns
    the lowercased, trimmed value of the first file's top-level
    `delegationMode:` line, or "unresolved" if no candidate file defines one.
    Read errors remain fail-open per candidate and continue to the next path."""
    # USERPROFILE first, then HOME keeps the owner Windows-aware while remaining
    # portable to POSIX environments.
    home_dir = os.environ.get("USERPROFILE") or os.environ.get("HOME") or ""

    candidates = [
        Path.cwd() / ".claude" / ".agents-mode.yaml",
        Path.cwd() / ".claude" / ".agents-mode",
    ]
    if home_dir:
        home = Path(home_dir)
        candidates.extend([
            home / ".claude" / ".agents-mode.yaml",
            home / ".claude" / ".agents-mode",
            home / ".agents-mode.yaml",
        ])

    for candidate in candidates:
        try:
            if not candidate.is_file():
                continue
            text = candidate.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        line = None
        for raw_line in text.splitlines():
            if raw_line.startswith("delegationMode:"):
                line = raw_line
                break
        if line is None:
            continue
        value = _KEY_RE.sub("", line, count=1)
        value = _COMMENT_RE.sub("", value)
        return value.strip().lower()

    return "unresolved"


def main() -> int:
    try:
        mode = _get_delegation_mode()
    except Exception:
        mode = "unresolved"
    if mode == "force":
        emit_session_start_context(FORCE_CONTEXT)
    elif mode == "auto":
        emit_session_start_context(AUTO_CONTEXT)
    # manual value, unresolved, or empty -> silent
    return 0


if __name__ == "__main__":
    sys.exit(main())

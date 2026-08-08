#!/usr/bin/env python3
"""SessionStart hook that re-injects the active Claude delegation posture.

The neutral ``agents_mode_runtime`` leaf owns Claude scalar precedence and
extraction. This entrypoint owns only delegation vocabulary and emitted text.
The Codex implementation remains separate because its role vocabulary differs.

CONDITIONAL BY DESIGN: emits an IMPERATIVE directive ONLY when the effective
delegationMode is force or auto; SILENT on manual and on the no-file/
unresolved state (fail-safe). The silence is load-bearing -- the block
appears only when delegation is operative.

No stdin dependency: this hook never reads its own SessionStart envelope --
cwd comes from the process's working directory and home from USERPROFILE/HOME,
not from an envelope field.
Fail-open: any error yields "unresolved" (silent) and this always exits 0.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from agents_mode_runtime import resolve_scalar
from hook_common import emit_session_start_context

FORCE_CONTEXT = (
    '[Delegation posture - re-shown at session start and after every compaction]\nEffective delegationMode: FORCE. STANDING INSTRUCTION, not advisory: at the FIRST decision point of any non-trivial task (multi-step implementation, design, research, review, bug-fix), STOP - hold the $lead orchestration role in THIS conversation, classify the task, pick the team template, and route it via the Agent tool to the matching specialist subagents ($lead is the role you hold, not a subagent you spawn). Doing substantial work inline when a matching specialist and a viable tool path exist violates the active posture. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from contracts/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION.'
)
AUTO_CONTEXT = (
    '[Delegation posture - re-shown at session start and after every compaction]\nEffective delegationMode: AUTO. Holding the $lead orchestration role in THIS conversation and delegating to the matching specialist subagents via the Agent tool is the DEFAULT for any non-trivial task (multi-step implementation, design, research, review, bug-fix) - do it unless the task is trivial or you record why inline is better. $lead is the role you hold, not a subagent you spawn. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from contracts/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION.'
)


def _get_delegation_mode() -> str:
    """Compatibility wrapper for the SessionStart reminder contract."""
    return resolve_scalar("delegationMode")


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

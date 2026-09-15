#!/usr/bin/env python3
"""SessionStart hook that re-injects the active Codex delegation posture.

Python is the sole runtime owner. This pack-only implementation walks the
Codex read order (``./.agents/``, ``~/.codex/``, then the shared global file)
and speaks the role/skill-activation idiom. The Claude implementation is
intentionally separate because its read order and Agent-tool vocabulary differ.
``delegationMode`` is not a Codex CLI built-in, so this hook makes the resolved
``force`` or ``auto`` posture visible to the session.

CONDITIONAL BY DESIGN: emits an IMPERATIVE directive ONLY when the effective
delegationMode is force or auto; SILENT on manual and on the no-file/
unresolved state (fail-safe). The silence is load-bearing -- the block
appears only when delegation is operative.

The sibling ``agents_mode_runtime.py`` support leaf owns the first-match read of
the documented read-order. The full resolver, ``resolve-agents-mode.py``, is
shipped beside this hook for explicit complete configuration resolution, but
SessionStart deliberately does not import or execute it: this narrow hook must
remain fail-open, avoid normalization/default side effects, and surface only a
file-explicit delegation posture. No file
anywhere means the pack is not installed here or the config was removed, so the
hook does NOT inject a standing directive into an arbitrary directory:
  ./.agents/.agents-mode.yaml -> ./.agents/.agents-mode ->
  ~/.codex/.agents-mode.yaml -> ~/.codex/.agents-mode -> ~/.agents-mode.yaml
  First file DEFINING delegationMode wins; none -> unresolved -> silent.

No stdin dependency: this hook never reads its own SessionStart envelope --
cwd comes from the process's working directory and home from USERPROFILE/HOME,
not from an envelope field.
Fail-open: any error yields "unresolved" (silent) and this always exits 0.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agents_mode_runtime import resolve_scalar
from hook_common import emit_session_start_context

FORCE_CONTEXT = (
    '[Delegation posture - re-shown at session start and after every compaction]\nEffective delegationMode: FORCE. STANDING INSTRUCTION, not advisory: at the FIRST decision point of any non-trivial task (multi-step implementation, design, research, review, bug-fix), STOP - hold the $lead orchestration role in THIS session, classify the task, pick the team template, and activate the matching specialist role/skill per stage ($lead is the role you hold, not a subagent you spawn). Doing substantial work inline when a matching specialist and a viable tool path exist violates the active posture. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from skills/lead/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION.'
)
AUTO_CONTEXT = (
    '[Delegation posture - re-shown at session start and after every compaction]\nEffective delegationMode: AUTO. Holding the $lead orchestration role in THIS session and activating the matching specialist role/skill per stage is the DEFAULT for any non-trivial task (multi-step implementation, design, research, review, bug-fix) - do it unless the task is trivial or you record why inline is better. $lead is the role you hold, not a subagent you spawn. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from skills/lead/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION.'
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

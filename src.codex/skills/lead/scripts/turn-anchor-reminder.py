#!/usr/bin/env python3
"""UserPromptSubmit hook -- re-anchors the TURN-BOUNDARY postures at the start of every user turn.

Python twin of `turn-anchor-reminder.ps1`. The anchor text is byte-identical to the
PowerShell version's here-string; the emitted JSON is byte-identical to what
`ConvertTo-Json -Compress` produces for the same payload. It was the LAST of the
thirteen registered hooks with no Python twin, which is the only reason its entry
could not be re-registered away from `powershell.exe` with the other twelve.

WHAT THIS SURFACE CANNOT REACH: it fires at TURN START, so a rule whose failure moment is
MID-TURN (which tool to reach for) belongs on PreToolUse instead -- first-person evidence:
~100 consecutive bash calls inside one turn, all succeeding, and the tool choice came from
that momentum while the reminder sat unread in the window. Only turn-boundary postures
belong here.

WHY THIS SURFACE, and why the SessionStart reminders are not enough:
`mcp-usage-reminder` and `agents-mode-reminder` fire ONCE per session start / compaction.
Their text even says "This STILL APPLIES AFTER COMPACTION - do not forget" -- prose about
decay decays with the prose. Measured in-session: a third-party plugin mounted on
UserPromptSubmit held its mode for a hundred turns while our SessionStart reminders faded
after a few. Same window, same model, same day: the only difference is the re-injection
cadence.

WHY IT IS A REMINDER AND NOT A GUARD: a Stop hook cannot deliver continuous operation --
`stop_hook_active` caps it at ~one forced continuation per turn -- and every signal it
could read (todos, status prose, the final message) is authored by the model being
policed, so its cheapest compliance paths are evasions. Two independent audits killed the
guard and both prescribed exactly this: a non-blocking re-anchor. It cannot false-block;
its whole cost is a few tokens per turn.

KEEP IT SHORT. This text is paid for on every single turn. Detail lives in the
SessionStart reminders and in the spine; this is the anchor, not the manual.
ASCII-only output so it never mojibakes across console codepages. Fail-open; exits 0.

STDIN IS NEVER READ, deliberately and for the same reason the `.ps1` sibling's blocking
read is a defect: `check-scratch-valuables.ps1` calls `[Console]::In.ReadToEnd()`, which
returns only at end-of-file, so a caller that never closes the write end leaves the process
blocked forever at `cpu=0`. Eight such processes were found alive on a real machine. This
hook needs no input, so it takes none.
"""

import sys

ANCHOR = (
    "[turn anchor - re-shown every turn because a once-per-session reminder is overwritten"
    " by whatever you did last]\n"
    "Continue until blocked: a passed slice is not completion. Record it, take the next"
    " unchecked action, keep going. A final-style summary while a known next action remains"
    " IS the defect -- the pull toward a tidy closing artifact is exactly what this anchor"
    " exists to counter. If you genuinely need the operator, name the blocker or the"
    " decision as the reason for stopping.\n"
    "Delegate: at the first decision point of non-trivial work hold $lead here, classify,"
    " route to the matching specialist role/skill via your host's delegation surface; take"
    " external-launch flags from the external-dispatch contract, never from memory."
)


def main() -> int:
    try:
        # `separators` reproduces PowerShell's `ConvertTo-Json -Compress` spacing exactly;
        # `ensure_ascii=True` (the default) keeps the output ASCII-only, matching the
        # docstring's contract and the .ps1's behaviour across console codepages.
        import json

        payload = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": ANCHOR,
            }
        }
        line = json.dumps(payload, separators=(",", ":"))
        if line:
            sys.stdout.write(line + "\n")
    except Exception:
        # Fail open, exactly like the .ps1's empty catch block: a reminder that cannot be
        # emitted must never cost the operator a turn.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

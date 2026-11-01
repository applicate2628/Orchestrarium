#!/usr/bin/env python3
"""UserPromptSubmit hook -- re-anchors the TURN-BOUNDARY postures at the start of every user turn.

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

STDIN IS NEVER READ. This hook needs no input, and avoiding a blocking read keeps startup
bounded when a caller does not close the write end.
"""

import sys


def main() -> int:
    try:
        import json
        from mcp_continuity_policy import TURN_ANCHOR_CONTEXT

        payload = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": TURN_ANCHOR_CONTEXT,
            }
        }
        line = json.dumps(payload, separators=(",", ":"))
        if line:
            sys.stdout.write(line + "\n")
    except Exception:
        # A reminder that cannot be emitted must never cost the operator a turn.
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())

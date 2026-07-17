#!/usr/bin/env bash
# UserPromptSubmit hook -- re-anchors the turn-level postures at the start of EVERY user turn.
#
# WHY THIS SURFACE. The pack's other reminders (`mcp-usage-reminder`, `agents-mode-reminder`) fire once
# per SessionStart/compaction, and their own text pleads "do not forget after compaction" -- prose about
# decay decays with the prose. Measured in-session: a third-party plugin mounted here held its mode for
# a hundred turns while the SessionStart reminders faded.
#
# WHAT THIS SURFACE CANNOT REACH -- stated so nobody mounts the wrong rule on it. This fires at TURN
# START. First-person evidence from the session that produced this hook: the orchestrator ran ~100
# consecutive bash/grep calls inside ONE turn, all succeeding, and its next tool choice came from the
# momentum of the last fifty actions -- not from any rule sitting in context. The reminder had never left
# the window; recency and repetition beat it. So a rule whose failure moment is MID-TURN (which tool to
# reach for) belongs on PreToolUse, at the decision point. Only postures whose failure moment is the TURN
# BOUNDARY belong here.
#
# WHY A REMINDER AND NOT A GUARD: a Stop hook cannot deliver continuous operation (`stop_hook_active`
# caps it at ~one forced continuation per turn), and every signal it could read (todos, status prose, the
# final message) is authored by the model being policed, so its cheapest compliance paths are evasions.
# Two independent audits killed the guard and both prescribed this non-blocking anchor.
#
# KEEP IT SHORT: this text is paid for on every turn. Detail lives in the SessionStart reminders and the
# spine; this is the anchor, not the manual.
# Fail-open: never blocks; always exits 0. (Exit 2 here would ERASE the user's prompt -- hooks docs.)
cat <<'EOF'
{"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": "[turn anchor - re-shown every turn because a once-per-session reminder is overwritten by whatever you did last]\nContinue until blocked: a passed slice is not completion. Record it, take the next unchecked action, keep going. A final-style summary while a known next action remains IS the defect -- the pull toward a tidy closing artifact is exactly what this anchor exists to counter. If you genuinely need the operator, name the blocker or the decision as the reason for stopping.\nDelegate: at the first decision point of non-trivial work hold $lead here, classify, route to the matching specialist role/skill via your host's delegation surface; take external-launch flags from the external-dispatch contract, never from memory."}}
EOF
exit 0

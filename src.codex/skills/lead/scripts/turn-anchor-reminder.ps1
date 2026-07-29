# UserPromptSubmit hook -- re-anchors the TURN-BOUNDARY postures at the start of every user turn.
#
# WHAT THIS SURFACE CANNOT REACH: it fires at TURN START, so a rule whose failure moment is MID-TURN
# (which tool to reach for) belongs on PreToolUse instead -- first-person evidence: ~100 consecutive
# bash calls inside one turn, all succeeding, and the tool choice came from that momentum while the
# reminder sat unread in the window. Only turn-boundary postures belong here.
#
# WHY THIS SURFACE, and why the SessionStart reminders are not enough:
# `mcp-usage-reminder` and `agents-mode-reminder` fire ONCE per session start / compaction.
# Their text even says "This STILL APPLIES AFTER COMPACTION - do not forget" -- prose about
# decay decays with the prose. Measured in-session: a third-party plugin mounted on
# UserPromptSubmit held its mode for a hundred turns while our SessionStart reminders faded
# after a few. Same window, same model, same day: the only difference is the re-injection
# cadence.
#
# WHY IT IS A REMINDER AND NOT A GUARD: a Stop hook cannot deliver continuous operation --
# `stop_hook_active` caps it at ~one forced continuation per turn -- and every signal it
# could read (todos, status prose, the final message) is authored by the model being
# policed, so its cheapest compliance paths are evasions. Two independent audits killed the
# guard and both prescribed exactly this: a non-blocking re-anchor. It cannot false-block;
# its whole cost is a few tokens per turn.
#
# KEEP IT SHORT. This text is paid for on every single turn. Detail lives in the
# SessionStart reminders and in the spine; this is the anchor, not the manual.
# ASCII-only output so it never mojibakes across console codepages. Fail-open; exits 0.
$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$anchor = @'
[turn anchor - re-shown every turn because a once-per-session reminder is overwritten by whatever you did last]
Continue until blocked: a passed slice is not completion. Record it, take the next unchecked action, keep going. A final-style summary while a known next action remains IS the defect -- the pull toward a tidy closing artifact is exactly what this anchor exists to counter. If you genuinely need the operator, name the blocker or the decision as the reason for stopping.
Delegate: at the first decision point of non-trivial work hold $lead here, classify, route to the matching specialist role/skill via your host's delegation surface; take external-launch flags from the external-dispatch contract, never from memory.
MCP checkpoint: for repository navigation or understanding, discover and use the relevant configured MCP before an ad-hoc shell search; if shell is genuinely the right instrument, state why.
'@

try {
    $payload = [ordered]@{
        hookSpecificOutput = [ordered]@{
            hookEventName = "UserPromptSubmit"
            additionalContext = $anchor
        }
    }
    $json = $payload | ConvertTo-Json -Compress -Depth 4 -ErrorAction Stop
    if ($json) { [Console]::Out.WriteLine($json) }
} catch {}
exit 0

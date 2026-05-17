#!/usr/bin/env bash
# Structural enforcement for the shared "Hypothesis disclosure discipline" rule.
#
# Designed as an opt-in PreToolUse hook on Claude Code's `Bash` tool, filtered
# by the permission rule `Bash(git push *)` so the hook only fires on actual
# push attempts. When fired, it inspects the HEAD commit message and either
# allows the push (commit has hypothesis disclosure OR a whitelisted type) or
# denies it with a structured reason that surfaces back to Claude and the user.
#
# Recommended `.claude/settings.json` snippet (or `~/.claude/settings.json`):
#
#   {
#     "hooks": {
#       "PreToolUse": [
#         {
#           "matcher": "Bash",
#           "hooks": [
#             {
#               "type": "command",
#               "if": "Bash(git push *)",
#               "command": "bash .claude/agents/scripts/check-hypothesis-disclosure.sh"
#             }
#           ]
#         }
#       ]
#     }
#   }
#
# This script is opt-in: the pack ships the script but does not modify any
# user's settings.json. Users who want structural enforcement add the snippet
# above to their settings file. The rule itself in shared/AGENTS.shared.md is
# binding regardless of whether the hook is installed.
#
# Stdin: Claude Code PreToolUse JSON envelope with `tool_input.command`.
# Stdout: JSON `{"hookSpecificOutput": {...}}` for deny, or nothing for allow.
# Exit: 0 on allow, 0 on deny (the JSON payload carries the decision).
set -euo pipefail

# Whitelist commit-type prefixes that do not require hypothesis disclosure.
# Behavior-changing prefixes (`feat`, `fix`, `refactor`) are NOT whitelisted.
WHITELIST_REGEX='^(docs|chore|style|merge|ci|build|perf|test|revert)(\(|:|!)'

# Required disclosure markers — at least one must appear in the commit body.
DISCLOSURE_REGEX='(VERIFIED|ASSUMPTION \(UNVERIFIED\))'

emit_deny() {
  local reason="$1"
  # Compact JSON to avoid shell quoting traps; printf handles literal braces.
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":%s}}\n' \
    "$(printf '%s' "$reason" | python3 -c 'import json,sys;print(json.dumps(sys.stdin.read()))')"
}

# Read JSON envelope from stdin. If python3 is unavailable, fall back to a
# minimal grep extraction (less robust but the hook still works on the common
# case). Both extraction paths MUST fail open: an unparseable or empty stdin
# envelope (which some runtimes — notably Codex CLI in certain hook contexts —
# pass for non-git-push tool calls) must NOT crash the script with exit 1,
# because that crash surfaces as "PreToolUse hook failed" on every Bash call
# and blocks the user's whole session. Two layers of defence:
#   (1) python -c wrapped in try/except so JSONDecodeError on empty/malformed
#       stdin sets `d = {}` instead of raising — python always exits 0.
#   (2) shell-level `|| command_str=""` belt-and-suspenders so even if python
#       itself errors (PATH issue, OOM, missing) the variable falls back to
#       empty and the git-push regex check below misses, exit 0 path taken.
# When command_str ends up empty, the script falls through to the pass-through
# branch (exit 0). The hook only blocks behaviour-changing commits with no
# disclosure markers; any bad input gracefully degrades to no-op.
input_json="$(cat || true)"
command_str=""
if command -v python3 >/dev/null 2>&1; then
  command_str="$(printf '%s' "$input_json" | python3 -c '
import json, sys
try:
    d = json.loads(sys.stdin.read())
except Exception:
    d = {}
print(d.get("tool_input", {}).get("command", ""))
' 2>/dev/null)" || command_str=""
else
  command_str="$(printf '%s' "$input_json" | grep -oE '"command":[[:space:]]*"[^"]*"' 2>/dev/null | head -1 | sed -E 's/.*"command":[[:space:]]*"([^"]*)".*/\1/')" || command_str=""
fi

# Only act on `git push ...`. Other Bash commands pass through unchanged.
if ! printf '%s' "$command_str" | grep -qE '(^|[[:space:]&;|])git[[:space:]]+push([[:space:]]|$)'; then
  exit 0
fi

# Require we are inside a git working tree.
if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  exit 0
fi

commit_msg="$(git log -1 --format=%B HEAD 2>/dev/null || true)"
if [[ -z "$commit_msg" ]]; then
  # Empty HEAD or detached without history — let the push attempt itself surface that.
  exit 0
fi

commit_subject="$(printf '%s' "$commit_msg" | head -1)"

# Whitelisted commit types skip disclosure requirement.
if printf '%s' "$commit_subject" | grep -qE "$WHITELIST_REGEX"; then
  exit 0
fi

# Behavior-changing commit must carry hypothesis disclosure markers.
if printf '%s' "$commit_msg" | grep -qE "$DISCLOSURE_REGEX"; then
  exit 0
fi

reason="Hypothesis disclosure missing in HEAD commit message.

Per the 'Hypothesis disclosure discipline' rule in AGENTS.md, commits that
change behavior, contract, or invariant must explicitly mark each underlying
claim as VERIFIED or ASSUMPTION (UNVERIFIED) in the commit body.

HEAD commit subject: ${commit_subject}

To bypass, either:
  1. Amend the commit to disclose the hypothesis chain (preferred).
  2. Use a whitelisted commit type prefix (docs/chore/style/ci/build/perf/test/revert/merge) if the change genuinely is not behavior-changing.
  3. If the rule does not apply in your case, temporarily disable this hook in your settings.json and document the deviation in the session log."

emit_deny "$reason"
exit 0

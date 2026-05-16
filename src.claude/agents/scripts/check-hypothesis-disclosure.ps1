<#
.SYNOPSIS
    Structural enforcement for the shared "Hypothesis disclosure discipline" rule (PowerShell).
.DESCRIPTION
    Designed as an opt-in PreToolUse hook on Claude Code's `Bash` tool, filtered
    by the permission rule `Bash(git push *)` so the hook only fires on actual
    push attempts. When fired, it inspects the HEAD commit message and either
    allows the push (commit has hypothesis disclosure OR a whitelisted type) or
    denies it with a structured reason that surfaces back to Claude and the user.

    Recommended `.claude/settings.json` snippet (Windows-friendly invocation):

      {
        "hooks": {
          "PreToolUse": [
            {
              "matcher": "Bash",
              "hooks": [
                {
                  "type": "command",
                  "if": "Bash(git push *)",
                  "command": "powershell -NoProfile -ExecutionPolicy Bypass -File .claude\\agents\\scripts\\check-hypothesis-disclosure.ps1"
                }
              ]
            }
          ]
        }
      }

    This script is opt-in: the pack ships the script but does not modify any
    user's settings.json. The rule itself in shared/AGENTS.shared.md is binding
    regardless of whether the hook is installed.

    Stdin: Claude Code PreToolUse JSON envelope with `tool_input.command`.
    Stdout: JSON `{"hookSpecificOutput": {...}}` for deny, or nothing for allow.
    Exit: 0 on both allow and deny (the JSON payload carries the decision).
#>
param()

$ErrorActionPreference = 'Stop'

# Whitelist commit-type prefixes that do not require hypothesis disclosure.
# Behavior-changing prefixes (`feat`, `fix`, `refactor`) are NOT whitelisted.
$WhitelistRegex = '^(docs|chore|style|merge|ci|build|perf|test|revert)(\(|:|!)'

# Required disclosure markers - at least one must appear in the commit body.
$DisclosureRegex = 'VERIFIED|ASSUMPTION \(UNVERIFIED\)'

function Emit-Deny {
    param([string]$Reason)
    $payload = @{
        hookSpecificOutput = @{
            hookEventName = 'PreToolUse'
            permissionDecision = 'deny'
            permissionDecisionReason = $Reason
        }
    }
    $payload | ConvertTo-Json -Depth 5 -Compress
}

# Read JSON envelope from stdin.
$stdinText = [Console]::In.ReadToEnd()
if ([string]::IsNullOrWhiteSpace($stdinText)) { exit 0 }

try {
    $envelope = $stdinText | ConvertFrom-Json
    $commandStr = $envelope.tool_input.command
} catch {
    # Malformed envelope - let the tool call through; the failure mode is
    # the regular Bash error, not a silent block.
    exit 0
}

if (-not $commandStr) { exit 0 }

# Only act on `git push ...`. Other Bash commands pass through unchanged.
if ($commandStr -notmatch '(^|[\s&;|])git\s+push(\s|$)') {
    exit 0
}

# Require we are inside a git working tree.
try {
    $null = git rev-parse --is-inside-work-tree 2>$null
    if ($LASTEXITCODE -ne 0) { exit 0 }
} catch {
    exit 0
}

$commitMsg = ''
try {
    $commitMsg = (git log -1 --format=%B HEAD 2>$null) -join "`n"
} catch {
    exit 0
}

if ([string]::IsNullOrWhiteSpace($commitMsg)) { exit 0 }

$commitSubject = ($commitMsg -split "`n")[0]

# Whitelisted commit types skip disclosure requirement.
if ($commitSubject -match $WhitelistRegex) { exit 0 }

# Behavior-changing commit must carry hypothesis disclosure markers.
if ($commitMsg -match $DisclosureRegex) { exit 0 }

$reason = @"
Hypothesis disclosure missing in HEAD commit message.

Per the 'Hypothesis disclosure discipline' rule in AGENTS.md, commits that
change behavior, contract, or invariant must explicitly mark each underlying
claim as VERIFIED or ASSUMPTION (UNVERIFIED) in the commit body.

HEAD commit subject: $commitSubject

To bypass, either:
  1. Amend the commit to disclose the hypothesis chain (preferred).
  2. Use a whitelisted commit type prefix (docs/chore/style/ci/build/perf/test/revert/merge) if the change genuinely is not behavior-changing.
  3. If the rule does not apply in your case, temporarily disable this hook in your settings.json and document the deviation in the session log.
"@

Emit-Deny -Reason $reason
exit 0

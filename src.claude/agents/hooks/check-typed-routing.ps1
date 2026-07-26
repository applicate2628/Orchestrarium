<#
.SYNOPSIS
    Thin wrapper around check-typed-routing.py for PowerShell hosts.
.DESCRIPTION
    Hook entry shape (PreToolUse on the Agent dispatch tool -- the
    subagent-dispatch tool captured Phase-0 as tool_name "Agent"):
      powershell -NoProfile -ExecutionPolicy Bypass -File <this-script>
    stdin: PreToolUse JSON envelope from Claude Code.
    stdout: on a nudge, one line of JSON -- {"hookSpecificOutput":{"hookEventName":
      "PreToolUse","additionalContext":"..."}} -- the model-visible nudge when a
      `general-purpose` subagent is dispatched for work that looks like typed
      specialist work (see hook_common.emit_advisory); nothing otherwise.
    stderr: nothing. The prior stderr-plus-exit-1 delivery was measured to reach
      nobody on Claude Code; see work-items/bugs/2026-07-26-mcp-reminder-uses-
      the-once-per-session-form-its-sibling-calls-broken.md.
    exit: propagates the Python helper's exit code, which is now ALWAYS 0 --
          AUDIT mode never blocks and the nudge travels via the stdout JSON
          above, not a non-zero exit. Wrapper-side errors (missing python or
          helper) still fail open to exit 0.

    The Python helper does all the actual logic -- this wrapper only pipes stdin
    through and propagates output. If python is missing or the helper fails for
    any reason, we exit 0 (fail-open).
#>
param()

$ErrorActionPreference = 'Continue'

try {
  $scriptDir = Split-Path -Parent $PSCommandPath
  $helper = Join-Path $scriptDir 'check-typed-routing.py'

  $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
  if (-not $pythonCmd) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  }
  if (-not $pythonCmd) { exit 0 }
  if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) { exit 0 }

  $stdinText = [Console]::In.ReadToEnd()
  $stdinText | & $pythonCmd.Source $helper
  exit $LASTEXITCODE
} catch {
  # fail-open on any wrapper-side error
  exit 0
}

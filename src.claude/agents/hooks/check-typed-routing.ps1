<#
.SYNOPSIS
    Thin wrapper around check-typed-routing.py for PowerShell hosts.
.DESCRIPTION
    Hook entry shape (PreToolUse on the Agent dispatch tool -- the
    subagent-dispatch tool captured Phase-0 as tool_name "Agent"):
      powershell -NoProfile -ExecutionPolicy Bypass -File <this-script>
    stdin: PreToolUse JSON envelope from Claude Code.
    stdout: nothing (AUDIT mode allows).
    stderr: an audit nudge when a `general-purpose` subagent is dispatched for
      work that looks like typed specialist work.
    exit: propagates the Python helper's exit code -- 1 on a nudge (a non-blocking
          "<hook name> hook error" transcript notice so the nudge is actually
          visible; exit 0's stderr is debug-log-only per the hooks reference), 0
          otherwise. NEVER 2 (that would block); AUDIT mode never blocks the
          tool call regardless of exit code. Wrapper-side errors (missing
          python or helper) still fail open to exit 0.

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

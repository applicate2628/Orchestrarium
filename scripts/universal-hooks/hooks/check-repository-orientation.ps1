<#
.SYNOPSIS
    Thin wrapper around check-repository-orientation.py.
.DESCRIPTION
    Reads a PreToolUse JSON envelope from stdin, emits only warn-mode audit
    diagnostics from the Python helper.
    exit: propagates the Python helper's exit code -- 1 on a hit (a non-blocking
          "<hook name> hook error" transcript notice so the warning is actually
          visible; exit 0's stderr is debug-log-only per the hooks reference), 0
          otherwise. NEVER 2 (that would block); AUDIT mode never blocks the
          tool call regardless of exit code. Wrapper-side errors (missing
          python or helper) still fail open to exit 0.
#>
param()

$ErrorActionPreference = 'Continue'
try {
  $scriptDir = Split-Path -Parent $PSCommandPath
  $helper = Join-Path $scriptDir 'check-repository-orientation.py'
  $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
  if (-not $pythonCmd) { $pythonCmd = Get-Command python -ErrorAction SilentlyContinue }
  if (-not $pythonCmd) { exit 0 }
  if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) { exit 0 }
  $stdinText = [Console]::In.ReadToEnd()
  $stdinText | & $pythonCmd.Source $helper
  exit $LASTEXITCODE
} catch {
  # fail open on every wrapper-side error
  exit 0
}

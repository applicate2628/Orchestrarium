<#
.SYNOPSIS
    Thin fail-open wrapper around check-repository-orientation.py.
.DESCRIPTION
    Reads a PreToolUse JSON envelope from stdin, emits only warn-mode audit
    diagnostics from the Python helper, and always exits zero.
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
} catch {
  # fail open on every wrapper-side error
}
exit 0

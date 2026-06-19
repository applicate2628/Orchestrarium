<#
.SYNOPSIS
    Thin wrapper around check-work-items-archival-stop.py for PowerShell hosts.
.DESCRIPTION
    Hook entry shape (Stop):
      powershell -NoProfile -ExecutionPolicy Bypass -File <this-script>
    stdin: Stop JSON envelope from Claude Code or Codex.
    stdout: block JSON if a delivered/closed work-item is still sitting in
            work-items/active/ instead of being archived; nothing otherwise.
    exit: always 0 (decision carried by stdout payload; fail-open on any
          internal error so legitimate work is never blocked).
#>
param()

$ErrorActionPreference = 'Continue'

try {
  $scriptDir = Split-Path -Parent $PSCommandPath
  $helper = Join-Path $scriptDir 'check-work-items-archival-stop.py'

  $pythonCmd = Get-Command python3 -ErrorAction SilentlyContinue
  if (-not $pythonCmd) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
  }
  if (-not $pythonCmd) { exit 0 }
  if (-not (Test-Path -LiteralPath $helper -PathType Leaf)) { exit 0 }

  $stdinText = [Console]::In.ReadToEnd()
  $stdinText | & $pythonCmd.Source $helper
} catch {
  # fail-open on any wrapper-side error
}

exit 0

<#
.SYNOPSIS
    Thin wrapper around check-scratch-valuables.py for PowerShell hosts.
.DESCRIPTION
    Hook entry shape (SessionStart, no matcher -- fires on startup / resume /
    clear / compact, same as mcp-usage-reminder):
      powershell -NoProfile -ExecutionPolicy Bypass -File <this-script>
    stdin: SessionStart JSON envelope from Claude Code or Codex.
    stdout: a hookSpecificOutput context block IF valuable-looking files have
            lingered in .scratch/ past the age threshold; nothing otherwise
            (byte-silent, same convention as agents-mode-reminder).
    exit: always 0 (fail-open on any internal error; this reminder must never
          block a session).

    The Python helper does all the actual logic -- this wrapper only pipes
    stdin through and propagates output. If python is missing or the helper
    fails for any reason, we exit 0 (fail-open).
#>
param()

$ErrorActionPreference = 'Continue'

try {
  $scriptDir = Split-Path -Parent $PSCommandPath
  $helper = Join-Path $scriptDir 'check-scratch-valuables.py'

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

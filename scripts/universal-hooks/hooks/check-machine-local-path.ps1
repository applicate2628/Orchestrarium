<#
.SYNOPSIS
    Thin wrapper around check-machine-local-path.py for PowerShell hosts.
.DESCRIPTION
    Hook entry shape (PreToolUse on Edit/Write/NotebookEdit/apply_patch):
      powershell -NoProfile -ExecutionPolicy Bypass -File <this-script>
    stdin: PreToolUse JSON envelope from Claude Code or Codex.
    stdout: nothing (AUDIT mode allows).
    stderr: an audit warning if a machine-local path is written to a tracked file.
    exit: always 0 (fail-open on any internal error; AUDIT mode never blocks).

    The Python helper does all the actual logic — this wrapper only pipes stdin
    through and propagates output. If python is missing or the helper fails for
    any reason, we exit 0 (fail-open).
#>
param()

$ErrorActionPreference = 'Continue'

try {
  $scriptDir = Split-Path -Parent $PSCommandPath
  $helper = Join-Path $scriptDir 'check-machine-local-path.py'

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

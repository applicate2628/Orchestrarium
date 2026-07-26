<#
.SYNOPSIS
    Thin wrapper around check-work-items-archival-stop.py for PowerShell hosts.
.DESCRIPTION
    This filename is a Codex trust-pinned wire identifier and stays unchanged
    even though the .py helper now hosts TWO invariants from the
    workitem_sentinels.py registry, not one: SEN-0 (archival orphan -- this
    hook's original sole behaviour) and SEN-1 (dual-state item: a slug present
    in BOTH work-items/active/ and work-items/archive/). A third invariant
    (SEN-2, delivery drought) and a third response tier (HALT) were designed
    and then withdrawn before release -- see check-work-items-archival-stop.py's
    own docstring and references-codex/stop-hook-halting-primitives.md for why.

    Hook entry shape (Stop):
      powershell -NoProfile -ExecutionPolicy Bypass -File <this-script>
    stdin: Stop JSON envelope from Claude Code or Codex.
    stdout: a RESOLVE ({"decision": "block", ...}) or
            NOTICE ({"systemMessage": ...}) payload if any invariant fires;
            nothing otherwise. There is no run-terminating tier on either
            provider line (HALT was removed).
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

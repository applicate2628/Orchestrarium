<#
.SYNOPSIS
    Thin wrapper around check-repository-orientation.py.
.DESCRIPTION
    Reads a PreToolUse JSON envelope from stdin. On a hit, emits one line of JSON
    -- {"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":
    "..."}} -- the model-visible advisory (see hook_common.emit_advisory);
    nothing otherwise. stderr carries nothing: the prior stderr-plus-exit-1
    delivery was measured to reach nobody on either provider line; see
    work-items/bugs/2026-07-26-mcp-reminder-uses-the-once-per-session-form-its-
    sibling-calls-broken.md.
    exit: propagates the Python helper's exit code. On a normal run (hit or
          miss) that is 0 -- AUDIT mode never blocks and the advisory
          travels via the stdout JSON above, not a non-zero exit. It is NOT
          always 0: an unimportable hook_common now surfaces as an uncaught
          ImportError -- exit 1 and a traceback naming the module on
          stderr, the detectability the fix relies on -- instead of a
          silent exit 0. Still never exit 2 (AUDIT mode never blocks): per
          the official hooks docs exit 1 is non-blocking on Claude Code,
          and on Codex CLI stderr is discarded entirely, so detectability
          there is a bare "PreToolUse Failed" label, not the traceback
          (hook_common.emit_advisory's own docstring; work-items/bugs/2026-
          07-26-mcp-reminder-uses-the-once-per-session-form-its-sibling-
          calls-broken.md). Wrapper-side errors (missing python or helper)
          still fail open to exit 0.
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

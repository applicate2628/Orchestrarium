<#
.SYNOPSIS
    Thin wrapper around check-mcp-momentum.py for PowerShell hosts.
.DESCRIPTION
    Hook entry shape (PreToolUse on Grep|Bash -- the code-NAVIGATION tools):
      powershell -NoProfile -ExecutionPolicy Bypass -File <this-script>
    stdin: PreToolUse JSON envelope from Claude Code or Codex.
    stdout: on a nudge, one line of JSON -- {"hookSpecificOutput":{"hookEventName":
      "PreToolUse","additionalContext":"..."}} -- the model-visible nudge when
      this looks like a code-navigation search and a code-intelligence MCP is
      configured (see hook_common.emit_advisory); nothing otherwise.
    stderr: nothing. The prior stderr-plus-exit-1 delivery was measured to reach
      nobody on either provider line; see work-items/bugs/2026-07-26-mcp-reminder-
      uses-the-once-per-session-form-its-sibling-calls-broken.md.
    exit: propagates the Python helper's exit code. On a normal run (hit or
          miss) that is 0 -- AUDIT mode never blocks and the nudge travels
          via the stdout JSON above, not a non-zero exit. It is NOT always
          0: an unimportable hook_common now surfaces as an uncaught
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

    The Python helper does all the actual logic — this wrapper only pipes stdin
    through and propagates output. If python is missing or the helper fails for
    any reason, we exit 0 (fail-open).
#>
param()

$ErrorActionPreference = 'Continue'

try {
  $scriptDir = Split-Path -Parent $PSCommandPath
  $helper = Join-Path $scriptDir 'check-mcp-momentum.py'

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

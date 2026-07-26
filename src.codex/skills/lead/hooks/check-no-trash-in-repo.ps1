<#
.SYNOPSIS
    Thin wrapper around check-no-trash-in-repo.py for PowerShell hosts.
.DESCRIPTION
    Hook entry shape (PreToolUse on Edit/Write/NotebookEdit/apply_patch and Bash):
      powershell -NoProfile -ExecutionPolicy Bypass -File <this-script>
    stdin: PreToolUse JSON envelope from Claude Code or Codex.
    stdout: on a hit, one line of JSON -- {"hookSpecificOutput":{"hookEventName":
      "PreToolUse","additionalContext":"..."}} -- the model-visible advisory if an
      unrequested `git worktree add` is run (a single add ending with the exact
      `# orchestrarium:requested-isolation-worktree` marker is exempt); nothing
      otherwise (see hook_common.emit_advisory).
    stderr: nothing. The prior stderr-plus-exit-1 delivery was measured to reach
      nobody on either provider line; see work-items/bugs/2026-07-26-mcp-reminder-
      uses-the-once-per-session-form-its-sibling-calls-broken.md.
    exit: propagates the Python helper's exit code, which is now ALWAYS 0 --
          AUDIT mode never blocks and the advisory travels via the stdout JSON
          above, not a non-zero exit. Wrapper-side errors (missing python or
          helper) still fail open to exit 0.

    The Python helper does all the actual logic — this wrapper only pipes stdin
    through and propagates output. If python is missing or the helper fails for
    any reason, we exit 0 (fail-open).
#>
param()

$ErrorActionPreference = 'Continue'

try {
  $scriptDir = Split-Path -Parent $PSCommandPath
  $helper = Join-Path $scriptDir 'check-no-trash-in-repo.py'

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

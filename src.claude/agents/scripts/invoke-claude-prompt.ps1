<#
.SYNOPSIS
    File-based prompt orchestration wrapper for claude CLI (PowerShell).
.DESCRIPTION
    Encapsulates the shared "External CLI prompt delivery" governance:
      1. Active-availability probe (Get-Command claude) before any file operation; fails closed.
      2. Prompt body persisted to .scratch/claude-prompts/<topic>-<timestamp>.md
      3. claude invoked with prompt piped via stdin redirection, never via argv
      4. stdout and stderr captured to sibling .out / .err files
      5. Three output paths printed in order: prompt, out, err
      6. Claude exit code propagated

    This wrapper is for the routine `claude` CLI. For the secret-backed API transport
    (the `reserveResolver: claude-wrapper` path), use `invoke-claude-api.ps1` instead.
.EXAMPLE
    Get-Content -Raw prompt.md |
      powershell -ExecutionPolicy Bypass -File .claude\agents\scripts\invoke-claude-prompt.ps1 advisory-adr
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .claude\agents\scripts\invoke-claude-prompt.ps1 worker-task --% --prompt-file prompt.md -- --model opus --effort max
#>
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$TopicSlug,

  [string]$PromptFile,

  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ClaudeFlags
)

$ErrorActionPreference = 'Stop'

if (-not $ClaudeFlags -or $ClaudeFlags.Count -eq 0) {
  $ClaudeFlags = @('-p', '--quiet', '--output-format', 'text')
}

$claudeBin = if ($env:CLAUDE_BIN) { $env:CLAUDE_BIN } else { 'claude' }
$commandInfo = Get-Command -Name $claudeBin -ErrorAction SilentlyContinue
if (-not $commandInfo) {
  Write-Error "FAIL: claude binary '$claudeBin' not found on PATH. Set CLAUDE_BIN if installed elsewhere."
  exit 1
}
$claudePath = $commandInfo.Source

$outputDir = if ($env:CLAUDE_PROMPTS_DIR) { $env:CLAUDE_PROMPTS_DIR } else { '.scratch\claude-prompts' }
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$slug = "$TopicSlug-$timestamp"

New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
$promptPath = Join-Path $outputDir "$slug.md"
$outPath = Join-Path $outputDir "$slug.out"
$errPath = Join-Path $outputDir "$slug.err"

if ($PromptFile) {
  if (-not (Test-Path -LiteralPath $PromptFile -PathType Leaf)) {
    Write-Error "FAIL: --prompt-file '$PromptFile' does not exist"
    exit 1
  }
  Copy-Item -LiteralPath $PromptFile -Destination $promptPath -Force
} else {
  if ([Console]::IsInputRedirected -eq $false) {
    Write-Error "FAIL: no prompt provided (neither --prompt-file nor piped stdin)"
    exit 1
  }
  $stdin = [Console]::In.ReadToEnd()
  # Explicit UTF-8 no-BOM write so the prompt file bytes are deterministic on
  # both PS 5.1 (where `Set-Content -Encoding UTF8` adds a BOM) and PS 7+ — a
  # leading BOM at claude stdin would otherwise be interpreted as prompt content.
  [System.IO.File]::WriteAllText($promptPath, $stdin, [System.Text.UTF8Encoding]::new($false))
}

# UTF-8 encoding for the native-command pipeline. PS 5.1 defaults `$OutputEncoding`
# to ASCII, which silently mangles non-ASCII bytes piped into a native process.
# Setting all three layers (`$OutputEncoding`, console In, console Out) ensures
# the prompt body reaches claude stdin and captured stdout/stderr stay UTF-8 clean.
$utf8NoBom = [System.Text.UTF8Encoding]::new($false)
$prevOutputEncoding = $OutputEncoding
$prevConsoleIn = [Console]::InputEncoding
$prevConsoleOut = [Console]::OutputEncoding
$prevErrorAction = $ErrorActionPreference
$OutputEncoding = $utf8NoBom
[Console]::InputEncoding = $utf8NoBom
[Console]::OutputEncoding = $utf8NoBom
# Relax error preference for the native call only. With `Stop` (set at the
# wrapper top for the wrapper's own PowerShell code), any byte the child
# process writes to stderr becomes a fatal NativeCommandError that kills the
# script before `$LASTEXITCODE` can be captured. The wrapper-side Stop
# strictness is restored in the finally block.
$ErrorActionPreference = 'Continue'

try {
  # Invoke claude via PowerShell native call operator. `&` handles shim resolution
  # (`.exe`, `.cmd`, `.ps1`) on both PS 5.1 + PS 7+ — unlike `[Process]::Start` with
  # `UseShellExecute=$false`, which only launches native `.exe` binaries and breaks
  # on npm-installed `claude.ps1` shims. Stdin is fed from the prompt file via the
  # pipeline; stdout/stderr captured via PowerShell's native `1>` / `2>` redirection;
  # exit code via `$LASTEXITCODE`.
  Get-Content -Raw -LiteralPath $promptPath |
    & $claudePath @ClaudeFlags `
      1> $outPath 2> $errPath
  $exitCode = $LASTEXITCODE
} finally {
  $ErrorActionPreference = $prevErrorAction
  $OutputEncoding = $prevOutputEncoding
  [Console]::InputEncoding = $prevConsoleIn
  [Console]::OutputEncoding = $prevConsoleOut
}

if ($null -eq $exitCode) { $exitCode = 1 }

# Normalize captured stdout/stderr to UTF-8 no-BOM. PS 5.1's `1>` / `2>`
# redirection writes UTF-16 LE with BOM via `Out-File`'s default Unicode
# encoding; PS 7+ writes UTF-8 — re-encode so callers get consistent bytes
# regardless of which host launched the wrapper. `Get-Content -Raw` auto-detects
# the BOM, and `[System.IO.File]::WriteAllText` writes UTF-8 no-BOM explicitly.
# On PS 7+ where the file is already UTF-8, this round-trip is a no-op.
foreach ($capturedPath in @($outPath, $errPath)) {
  if ((Test-Path -LiteralPath $capturedPath -PathType Leaf) -and (Get-Item -LiteralPath $capturedPath).Length -gt 0) {
    $captured = Get-Content -Raw -LiteralPath $capturedPath
    if ($null -ne $captured) {
      [System.IO.File]::WriteAllText($capturedPath, $captured, [System.Text.UTF8Encoding]::new($false))
    }
  }
}

Write-Output $promptPath
Write-Output $outPath
Write-Output $errPath

exit $exitCode

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
  Set-Content -LiteralPath $promptPath -Value $stdin -Encoding UTF8 -NoNewline
}

$pinfo = New-Object System.Diagnostics.ProcessStartInfo
$pinfo.FileName = $claudePath
foreach ($flag in $ClaudeFlags) { $pinfo.ArgumentList.Add($flag) }
$pinfo.RedirectStandardInput = $true
$pinfo.RedirectStandardOutput = $true
$pinfo.RedirectStandardError = $true
$pinfo.UseShellExecute = $false

$process = [System.Diagnostics.Process]::Start($pinfo)
$promptBody = Get-Content -Raw -LiteralPath $promptPath
$process.StandardInput.Write($promptBody)
$process.StandardInput.Close()

$stdoutText = $process.StandardOutput.ReadToEnd()
$stderrText = $process.StandardError.ReadToEnd()
$process.WaitForExit()

Set-Content -LiteralPath $outPath -Value $stdoutText -Encoding UTF8 -NoNewline
Set-Content -LiteralPath $errPath -Value $stderrText -Encoding UTF8 -NoNewline

Write-Output $promptPath
Write-Output $outPath
Write-Output $errPath

exit $process.ExitCode

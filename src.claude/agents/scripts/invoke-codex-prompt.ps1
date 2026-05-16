<#
.SYNOPSIS
    File-based prompt orchestration wrapper for codex CLI (PowerShell).
.DESCRIPTION
    Encapsulates the shared "External CLI prompt delivery" governance:
      1. Active-availability probe (Get-Command codex) before any file operation; fails closed.
      2. Prompt body persisted to .scratch/codex-prompts/<topic>-<timestamp>.md
      3. codex invoked with prompt piped via stdin redirection, never via argv
      4. stdout and stderr captured to sibling .out / .err files
      5. Three output paths printed in order: prompt, out, err
      6. Codex exit code propagated
.EXAMPLE
    Get-Content -Raw prompt.md |
      powershell -ExecutionPolicy Bypass -File .claude\agents\scripts\invoke-codex-prompt.ps1 advisory-adr
.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .claude\agents\scripts\invoke-codex-prompt.ps1 worker-task --% --prompt-file prompt.md -- --model gpt-5.5
#>
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$TopicSlug,

  [string]$PromptFile,

  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CodexFlags
)

$ErrorActionPreference = 'Stop'

if (-not $CodexFlags -or $CodexFlags.Count -eq 0) {
  # Codex CLI 0.130.0+ uses `codex exec` (non-interactive subcommand); the old
  # top-level --quiet / --full-auto flags were removed. Defaults below pin only
  # `model_reasoning_effort=xhigh`; callers should override after the `--` block
  # if they need a deterministic per-profile invocation including fast_mode.
  $CodexFlags = @('-c', 'model_reasoning_effort=xhigh')
}

$codexBin = if ($env:CODEX_BIN) { $env:CODEX_BIN } else { 'codex' }
$commandInfo = Get-Command -Name $codexBin -ErrorAction SilentlyContinue
if (-not $commandInfo) {
  Write-Error "FAIL: codex binary '$codexBin' not found on PATH. Set CODEX_BIN if installed elsewhere."
  exit 1
}
$codexPath = $commandInfo.Source

$outputDir = if ($env:CODEX_PROMPTS_DIR) { $env:CODEX_PROMPTS_DIR } else { '.scratch\codex-prompts' }
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
$pinfo.FileName = $codexPath
# Codex CLI 0.130.0+ requires `exec` subcommand for non-interactive invocation;
# --skip-git-repo-check lets prompts be served from any directory.
$pinfo.ArgumentList.Add('exec')
$pinfo.ArgumentList.Add('--skip-git-repo-check')
foreach ($flag in $CodexFlags) { $pinfo.ArgumentList.Add($flag) }
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

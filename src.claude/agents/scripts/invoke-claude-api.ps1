<#
.SYNOPSIS
    Run claude-api with ANTHROPIC_* loaded from the nearest Claude SECRET.md.
.DESCRIPTION
    Search order:
      1. $env:CLAUDE_SECRET_FILE
      2. <cwd>\.claude\SECRET.md
      3. installed or source-adjacent .claude\SECRET.md
      4. $HOME\.claude\SECRET.md
#>
[CmdletBinding()]
param(
  [switch]$PrintSecretPath,
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Arguments
)

$ErrorActionPreference = 'Stop'

function Add-Candidate {
  param(
    [System.Collections.Generic.List[string]]$List,
    [string]$Path
  )

  if ([string]::IsNullOrWhiteSpace($Path)) {
    return
  }

  try {
    $normalized = [System.IO.Path]::GetFullPath($Path)
  } catch {
    $normalized = $Path
  }

  if (-not $List.Contains($normalized)) {
    $List.Add($normalized)
  }
}

function Get-SecretObject {
  param([string]$Path)

  $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
  $payload = $raw.Trim()
  if ($payload.StartsWith('```')) {
    $match = [regex]::Match($raw, '```(?:json)?\s*([\s\S]*?)```')
    if (-not $match.Success) {
      throw "Could not extract JSON payload from '$Path'."
    }
    $payload = $match.Groups[1].Value.Trim()
  }

  return $payload | ConvertFrom-Json -AsHashtable
}

$scriptDir = Split-Path -Parent $PSCommandPath
$packRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDir '..\..'))
$candidates = [System.Collections.Generic.List[string]]::new()

if ($env:CLAUDE_SECRET_FILE) {
  Add-Candidate -List $candidates -Path $env:CLAUDE_SECRET_FILE
}

Add-Candidate -List $candidates -Path (Join-Path (Get-Location).Path '.claude\SECRET.md')

$packLeaf = Split-Path -Leaf $packRoot
if ($packLeaf -ieq '.claude') {
  Add-Candidate -List $candidates -Path (Join-Path $packRoot 'SECRET.md')
} elseif ($packLeaf -ieq 'src.claude') {
  Add-Candidate -List $candidates -Path (Join-Path (Split-Path -Parent $packRoot) '.claude\SECRET.md')
}

if ($HOME) {
  Add-Candidate -List $candidates -Path (Join-Path $HOME '.claude\SECRET.md')
}

$secretPath = $candidates | Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } | Select-Object -First 1
if (-not $secretPath) {
  throw "No Claude SECRET.md found. Checked: $($candidates -join ', ')"
}

if ($PrintSecretPath) {
  Write-Output $secretPath
  exit 0
}

$secretObject = Get-SecretObject -Path $secretPath
$secretEnv = if ($secretObject.ContainsKey('env') -and $secretObject['env'] -is [System.Collections.IDictionary]) {
  $secretObject['env']
} else {
  $secretObject
}

$required = @('ANTHROPIC_BASE_URL', 'ANTHROPIC_API_KEY', 'ANTHROPIC_AUTH_TOKEN')
$missing = @($required | Where-Object { -not $secretEnv.ContainsKey($_) -or [string]::IsNullOrWhiteSpace([string]$secretEnv[$_]) })
if ($missing.Count -gt 0) {
  throw "SECRET.md '$secretPath' is missing required Claude transport keys: $($missing -join ', ')"
}

foreach ($key in $required) {
  Set-Item -Path "Env:$key" -Value ([string]$secretEnv[$key])
}

$claudeApiBin = if ($env:CLAUDE_API_BIN) { $env:CLAUDE_API_BIN } else { 'claude-api' }
$commandInfo = Get-Command -Name $claudeApiBin -ErrorAction SilentlyContinue
if (-not $commandInfo) {
  throw "Claude API transport '$claudeApiBin' is not available on PATH."
}

& $commandInfo.Source @Arguments
exit $LASTEXITCODE

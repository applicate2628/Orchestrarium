<#
.SYNOPSIS
    Run plain claude with environment variables loaded from the nearest Claude SECRET.md.
.DESCRIPTION
    Search order:
      1. $env:CLAUDE_SECRET_FILE
      2. <cwd>\.claude\SECRET.md
      3. installed or source-adjacent .claude\SECRET.md
      4. $HOME\.claude\SECRET.md
#>
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$Arguments
)

$ErrorActionPreference = 'Stop'

function Show-Usage {
  @'
Usage:
  powershell -ExecutionPolicy Bypass -File .claude\agents\scripts\invoke-claude-api.ps1 --% [claude args...]
  powershell -ExecutionPolicy Bypass -File .claude\agents\scripts\invoke-claude-api.ps1 -PrintSecretPath
  powershell -ExecutionPolicy Bypass -File .claude\agents\scripts\invoke-claude-api.ps1 --print-secret-path

Environment overrides:
  CLAUDE_SECRET_FILE   Explicit SECRET.md path to use
  CLAUDE_BIN           Claude executable or absolute path to invoke

Note:
  Use --% before forwarded Claude CLI flags so PowerShell does not treat them as script parameters.
'@
}

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

function ConvertTo-HashtableRecursive {
  param([object]$Value)

  if ($null -eq $Value) {
    return $null
  }

  if ($Value -is [System.Collections.IDictionary]) {
    $result = @{}
    foreach ($key in $Value.Keys) {
      $result[[string]$key] = ConvertTo-HashtableRecursive -Value $Value[$key]
    }
    return $result
  }

  if ($Value -is [System.Management.Automation.PSCustomObject]) {
    $result = @{}
    foreach ($property in $Value.PSObject.Properties) {
      $result[$property.Name] = ConvertTo-HashtableRecursive -Value $property.Value
    }
    return $result
  }

  if ($Value -is [System.Collections.IEnumerable] -and -not ($Value -is [string])) {
    $items = @()
    foreach ($item in $Value) {
      $items += ,(ConvertTo-HashtableRecursive -Value $item)
    }
    return $items
  }

  return $Value
}

function Get-SecretObject {
  param([string]$Path)

  $raw = Get-Content -LiteralPath $Path -Raw -Encoding UTF8
  $payload = $raw.Trim()
  $match = [regex]::Match($raw, '```(?:json)?\s*([\s\S]*?)```')
  if ($match.Success) {
    $payload = $match.Groups[1].Value.Trim()
  } elseif (-not ($payload.StartsWith('{') -or $payload.StartsWith('['))) {
    $firstBrace = $raw.IndexOf('{')
    $lastBrace = $raw.LastIndexOf('}')
    if ($firstBrace -lt 0 -or $lastBrace -le $firstBrace) {
      throw "Could not extract JSON payload from '$Path'."
    }
    $payload = $raw.Substring($firstBrace, ($lastBrace - $firstBrace) + 1).Trim()
  }

  $parsed = $payload | ConvertFrom-Json
  return ConvertTo-HashtableRecursive -Value $parsed
}

function Resolve-ClaudeCommand {
  param([string]$RequestedName)

  $candidates = [System.Collections.Generic.List[string]]::new()
  if (-not [string]::IsNullOrWhiteSpace($RequestedName)) {
    $candidates.Add($RequestedName)
  } else {
    foreach ($candidate in @('claude', 'claude.exe', 'claude.cmd')) {
      $candidates.Add($candidate)
    }
  }

  foreach ($candidate in $candidates) {
    $commandInfo = Get-Command -Name $candidate -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($commandInfo) {
      return $commandInfo
    }
  }

  return $null
}

$scriptDir = Split-Path -Parent $PSCommandPath
$packRoot = [System.IO.Path]::GetFullPath((Join-Path $scriptDir '..\..'))
$candidates = [System.Collections.Generic.List[string]]::new()
$remainingArguments = [System.Collections.Generic.List[string]]::new()
$printSecretPathRequested = $false
$showHelp = $false

foreach ($argument in $Arguments) {
  switch ($argument) {
    '-PrintSecretPath' {
      $printSecretPathRequested = $true
      continue
    }
    '--print-secret-path' {
      $printSecretPathRequested = $true
      continue
    }
    '--help' {
      $showHelp = $true
      continue
    }
    default {
      $remainingArguments.Add($argument)
    }
  }
}

if ($showHelp) {
  Show-Usage
  exit 0
}

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

if ($printSecretPathRequested) {
  Write-Output $secretPath
  exit 0
}

$secretObject = Get-SecretObject -Path $secretPath
$secretEnv = if ($secretObject.ContainsKey('env') -and $secretObject['env'] -is [System.Collections.IDictionary]) {
  $secretObject['env']
} else {
  $secretObject
}

$required = @('ANTHROPIC_BASE_URL', 'ANTHROPIC_AUTH_TOKEN')
$missing = @($required | Where-Object { -not $secretEnv.ContainsKey($_) -or [string]::IsNullOrWhiteSpace([string]$secretEnv[$_]) })
if ($missing.Count -gt 0) {
  throw "SECRET.md '$secretPath' is missing required Claude transport keys: $($missing -join ', ')"
}

foreach ($entry in $secretEnv.GetEnumerator()) {
  $key = [string]$entry.Key
  if ([string]::IsNullOrWhiteSpace($key)) {
    continue
  }

  $value = if ($null -eq $entry.Value) { '' } else { [string]$entry.Value }
  Set-Item -Path "Env:$key" -Value $value
}

$claudeBin = $env:CLAUDE_BIN
$commandInfo = Resolve-ClaudeCommand -RequestedName $claudeBin
if (-not $commandInfo) {
  $claudeLabel = if ([string]::IsNullOrWhiteSpace($claudeBin)) { 'claude' } else { $claudeBin }
  throw "Claude executable '$claudeLabel' is not available. Set CLAUDE_BIN to an executable or absolute path if it is not on the active shell PATH."
}

& $commandInfo.Source @($remainingArguments.ToArray())
exit $LASTEXITCODE

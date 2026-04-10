[CmdletBinding(PositionalBinding = $false)]
param(
  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]] $Arguments
)

$ErrorActionPreference = 'Stop'

$gitCommand = Get-Command git -ErrorAction Stop
$gitExecutable = $gitCommand.Source
if (-not $gitExecutable) {
  $gitExecutable = $gitCommand.Path
}
if (-not $gitExecutable) {
  throw "Unable to resolve git.exe from Get-Command git."
}

$gitExecutable = (Resolve-Path $gitExecutable).Path
$gitInstallRoot = Split-Path -Parent (Split-Path -Parent $gitExecutable)
$shellCandidates = @(
  (Join-Path $gitInstallRoot 'bin\bash.exe'),
  (Join-Path $gitInstallRoot 'usr\bin\bash.exe'),
  (Join-Path $gitInstallRoot 'usr\bin\sh.exe')
)

$shellExecutable = $shellCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $shellExecutable) {
  throw "Unable to locate bundled bash.exe or sh.exe under $gitInstallRoot."
}

$repoRoot = (& $gitExecutable rev-parse --show-toplevel).Trim()
if (-not $repoRoot) {
  throw "Unable to determine repository root."
}

Set-Location $repoRoot
$scriptPath = Join-Path $PSScriptRoot 'validate-skill-pack.sh'
if (-not (Test-Path -LiteralPath $scriptPath)) {
  throw "Unable to locate sibling validate-skill-pack.sh next to $PSCommandPath."
}

& $shellExecutable $scriptPath @Arguments
exit $LASTEXITCODE

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
  foreach ($shellName in @('bash', 'sh')) {
    $shellCommand = Get-Command -Name $shellName -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($shellCommand) {
      $shellExecutable = $shellCommand.Source
      if (-not $shellExecutable) {
        $shellExecutable = $shellCommand.Path
      }
      if ($shellExecutable) {
        break
      }
    }
  }
}
if (-not $shellExecutable) {
  throw "Unable to locate bundled bash.exe or sh.exe under $gitInstallRoot."
}

$repoRootOutput = $null
$repoRootExitCode = 1
try {
  $repoRootOutput = & $gitExecutable rev-parse --show-toplevel 2>$null
  $repoRootExitCode = $LASTEXITCODE
} catch {
  $repoRootOutput = $null
  $repoRootExitCode = 1
}

$repoRoot = if ($repoRootExitCode -eq 0 -and $repoRootOutput) {
  ($repoRootOutput | Select-Object -First 1).Trim()
} else {
  $null
}

if ($repoRoot) {
  Set-Location $repoRoot
} else {
  $runtimeRoot = Resolve-Path (Join-Path $PSScriptRoot '..\..\..\..')
  Set-Location $runtimeRoot
}
$scriptPath = Join-Path $PSScriptRoot 'validate-skill-pack.sh'
if (-not (Test-Path -LiteralPath $scriptPath)) {
  throw "Unable to locate sibling validate-skill-pack.sh next to $PSCommandPath."
}

& $shellExecutable $scriptPath @Arguments
exit $LASTEXITCODE

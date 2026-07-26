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
$gitParentRoot = Split-Path -Parent $gitInstallRoot
$shellCandidates = @(
  (Join-Path $gitInstallRoot 'bin\bash.exe'),
  (Join-Path $gitInstallRoot 'usr\bin\bash.exe'),
  (Join-Path $gitInstallRoot 'usr\bin\sh.exe')
)
# Only probe the grandparent root in the Git-for-Windows mingw layout, where
# git.exe sits at ...\Git\mingw64\bin\git.exe (or mingw32, or usr) and its real
# bundled bash is one level up at ...\Git\bin. Gate on $gitInstallRoot's LEAF
# being a mingw layer (mingw64/mingw32/usr): the normal ...\Git\cmd\git.exe
# layout has leaf 'Git', so the grandparent is NOT probed and an unrelated
# <grandparent>\bin\bash.exe can never be mis-selected. This leaf test is also
# non-empty by construction, so it subsumes the earlier drive-root guard -- a
# drive-root install root (e.g. X:\, whose leaf is not a mingw layer) never
# enters the branch, so Join-Path is never called with the empty grandparent
# and cannot throw.
$gitInstallLeaf = Split-Path -Leaf $gitInstallRoot
if (@('mingw64', 'mingw32', 'usr') -contains $gitInstallLeaf) {
  $shellCandidates += (Join-Path $gitParentRoot 'bin\bash.exe')
  $shellCandidates += (Join-Path $gitParentRoot 'usr\bin\bash.exe')
  $shellCandidates += (Join-Path $gitParentRoot 'usr\bin\sh.exe')
}

$shellExecutable = $shellCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
if (-not $shellExecutable) {
  # WSL bash.exe launchers live under the Windows directory (System32, its
  # 32-bit-process Sysnative view, SysWOW64, or any future Windows-dir variant)
  # or under the Store-app Microsoft\WindowsApps execution-alias dir; a real
  # Git/MSYS bash is never under either. Reject by that structural invariant so a
  # new Windows-dir launcher variant needs no new per-alias rule. Build the
  # Windows-dir prefixes once (both separator forms) from $env:SystemRoot /
  # $env:windir, plus a literal C:\Windows in case both are unset.
  $windowsDirPrefixes = @()
  foreach ($winDir in @($env:SystemRoot, $env:windir, 'C:\Windows')) {
    if ($winDir) {
      $trimmedWinDir = $winDir.TrimEnd('\', '/')
      $windowsDirPrefixes += ($trimmedWinDir + '\')
      $windowsDirPrefixes += ($trimmedWinDir + '/')
    }
  }
  foreach ($shellName in @('bash', 'sh')) {
    # Enumerate ALL PATH candidates, not just the first: on Windows a WSL
    # launcher usually precedes Git Bash on PATH but cannot resolve C:\Users\...
    # paths, so it must be skipped, not selected.
    $shellCommands = @(Get-Command -Name $shellName -CommandType Application -All -ErrorAction SilentlyContinue)
    foreach ($shellCommand in $shellCommands) {
      $candidatePath = $shellCommand.Source
      if (-not $candidatePath) {
        $candidatePath = $shellCommand.Path
      }
      if (-not $candidatePath) {
        continue
      }
      $isWslLauncher = $false
      foreach ($windowsDirPrefix in $windowsDirPrefixes) {
        if ($candidatePath.StartsWith($windowsDirPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
          $isWslLauncher = $true
          break
        }
      }
      if (-not $isWslLauncher -and $candidatePath -match '[\\/]Microsoft[\\/]WindowsApps[\\/]') {
        $isWslLauncher = $true
      }
      if ($isWslLauncher) {
        continue
      }
      $shellExecutable = $candidatePath
      break
    }
    if ($shellExecutable) {
      break
    }
  }
}
if (-not $shellExecutable) {
  throw "Unable to locate a non-WSL bundled bash.exe or sh.exe (searched under $gitInstallRoot and its parent, then PATH excluding WSL launchers)."
}

$repoRootOutput = $null
$repoRootExitCode = 1
# ErrorActionPreference is relaxed around JUST this native call, then restored:
# under Windows PowerShell 5.1, invoking a `.cmd`/`.bat` git with `2>$null`
# redirection can surface an UNRELATED native-stderr line (e.g. from a cmd.exe
# `AutoRun` registry hook some environments set, such as conda's) as an
# ErrorRecord, which `$ErrorActionPreference = 'Stop'` then promotes to a
# terminating exception -- misreporting a perfectly good repo as "cannot
# determine repository root". Reproduced empirically under PowerShell 5.1 with
# a synthetic cmd.exe AutoRun hook; pwsh 7 is unaffected either way. This does
# NOT weaken the null-safety: $LASTEXITCODE is still read right after the call
# and still gates $repoRoot below.
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
try {
  $repoRootOutput = & $gitExecutable rev-parse --show-toplevel 2>$null
  $repoRootExitCode = $LASTEXITCODE
} catch {
  $repoRootOutput = $null
  $repoRootExitCode = 1
} finally {
  $ErrorActionPreference = $previousErrorActionPreference
}

$repoRoot = if ($repoRootExitCode -eq 0 -and $repoRootOutput) {
  ($repoRootOutput | Select-Object -First 1).Trim()
} else {
  $null
}

if (-not $repoRoot) {
  throw "Unable to determine repository root."
}

Set-Location $repoRoot
$scriptPath = Join-Path $PSScriptRoot 'check-publication-gate.sh'
if (-not (Test-Path -LiteralPath $scriptPath)) {
  throw "Unable to locate sibling check-publication-gate.sh next to $PSCommandPath."
}

& $shellExecutable $scriptPath @Arguments
exit $LASTEXITCODE

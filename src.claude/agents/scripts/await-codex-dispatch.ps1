<#
.SYNOPSIS
    One-shot active completion watcher for a background Codex dispatch.
.DESCRIPTION
    Watches the final-message/output artifacts, commit identity, stderr idle
    time, and a hard elapsed-time cap. Missing files and failed git probes are
    non-terminal so delayed provider artifacts do not crash the watcher.
#>
[CmdletBinding()]
param(
  [string]$Out,
  [string]$Err,
  [string]$LastMsg,
  [string]$CommitBase,
  [int]$StallSecs = 2700,
  [int]$MaxSecs = 3600,
  [double]$PollSecs = 25
)

$ErrorActionPreference = 'SilentlyContinue'

function Write-Usage {
  Write-Error @'
Usage:
  await-codex-dispatch.ps1 -Out <out-path> [-Err <err-path>]
    [-LastMsg <lastmsg-path>] [-CommitBase <sha>]
    [-StallSecs <seconds>] [-MaxSecs <seconds>] [-PollSecs <seconds>]
'@ -ErrorAction Continue
}

if ([string]::IsNullOrWhiteSpace($Out)) {
  Write-Error 'FAIL: --out is required' -ErrorAction Continue
  Write-Usage
  exit 2
}

if ($StallSecs -lt 0 -or $MaxSecs -lt 0 -or $PollSecs -lt 0) {
  Write-Error 'FAIL: timing values must be non-negative' -ErrorAction Continue
  exit 2
}

function Get-FileBytes([string]$Path) {
  if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { return 0 }
  try { return [int64](Get-Item -LiteralPath $Path -Force).Length } catch { return 0 }
}

function Get-CurrentHead {
  try {
    $head = (& git rev-parse HEAD 2>$null | Select-Object -First 1)
    if ($head) { return $head.ToString().Trim() }
  } catch { }
  return ''
}

$started = Get-Date

while ($true) {
  $lastMsgBytes = Get-FileBytes $LastMsg
  if ($lastMsgBytes -gt 0) {
    Write-Output "DONE lastmsg=$lastMsgBytes"
    exit 0
  }

  $outBytes = Get-FileBytes $Out
  if ($outBytes -gt 0) {
    Write-Output "DONE out=$outBytes"
    exit 0
  }

  if ($CommitBase) {
    $currentHead = Get-CurrentHead
    if ($currentHead -and $currentHead -ne $CommitBase) {
      Write-Output "DONE committed=$currentHead"
      exit 0
    }
  }

  if ($Err -and (Test-Path -LiteralPath $Err -PathType Leaf)) {
    try {
      $errInfo = Get-Item -LiteralPath $Err -Force
      $errIdle = [math]::Floor(((Get-Date) - $errInfo.LastWriteTime).TotalSeconds)
      if ($errIdle -gt $StallSecs) {
        Write-Output "STALL err-idle=$errIdle"
        exit 0
      }
    } catch { }
  }

  $elapsed = [math]::Floor(((Get-Date) - $started).TotalSeconds)
  if ($elapsed -ge $MaxSecs) {
    Write-Output "TIMEOUT max=$MaxSecs"
    exit 0
  }

  Start-Sleep -Milliseconds ([math]::Max(1, [int][math]::Ceiling($PollSecs * 1000)))
}

<#
.SYNOPSIS
    One-shot active completion watcher for a background Codex dispatch.
.DESCRIPTION
    Watches the final-message/output artifacts, commit identity, stderr idle
    time, and a hard elapsed-time cap. Missing files and failed git probes are
    non-terminal so delayed provider artifacts do not crash the watcher.

    Exit codes carry the terminal status so a caller can act on $LASTEXITCODE
    without parsing stdout (work-items/bugs/2026-07-26-await-codex-dispatch-
    cannot-satisfy-its-own-liveness-invariant.md): a caller testing
    $LASTEXITCODE previously saw 0 for a 45-minute stall exactly as for a
    delivered review.
      0   DONE    - a real completion signal fired (non-empty lastmsg/out, or
                    a changed HEAD when -CommitBase was supplied).
      69  DEAD    - EX_UNAVAILABLE (sysexits.h): -PidFile was given, its
                    recorded process is CONFIRMED gone (or a different
                    process now holds that PID -- see the start-marker check
                    below), and none of the DONE conditions fired this same
                    poll. Unlike STALL this is not "temporary": the specific
                    run this watcher was tracking no longer exists, so
                    re-waiting on it is pointless -- re-dispatch or escalate.
                    Without -PidFile this status is never reached and
                    behavior is byte-for-byte the pre-existing artifact-only
                    logic (deliberate degrade path -- see -PidFile docs).
      75  STALL   - .err went idle past -StallSecs. EX_TEMPFAIL (sysexits.h):
                    a temporary condition, not proof of process death, so a
                    retry/extended wait is a reasonable caller response.
      77  FILTERED - a THIRD silent-success shape, distinct from DEAD: the
                    completion artifacts are still empty AND the tail of -Err
                    carries the provider's cybersecurity content-filter
                    refusal (observed live: 0-byte .out, absent .lastmsg,
                    exit 0, 229k tokens spent). EX_NOPERM (sysexits.h) -- the
                    provider is refusing on policy grounds, not merely idle
                    or gone. MODEL-SPECIFIC: re-dispatch the SAME lane on a
                    DIFFERENT model; never reword the prompt to appease the
                    filter (that changes what was asked, worse than a model
                    swap). See "Cybersecurity content-filter detection" below.
      124 TIMEOUT - -MaxSecs elapsed with nothing else terminal. Matches the
                    exit code the GNU coreutils `timeout(1)` command uses for
                    the same condition, a convention callers may already
                    check.
      2   usage/argument error (unchanged).

    Cybersecurity content-filter detection (FILTERED, exit 77): exit code 0
    with empty completion artifacts is indistinguishable from "still
    working" -- without this check the filtered case above cost a full
    -StallSecs wait before anything was reported, and what was finally
    reported (STALL) named the wrong cause. Detection rests on the
    CONJUNCTION, never on either leg alone: (1) the DONE checks below did not
    fire this poll -- a completed run is never overridden even if its .err
    happens to contain the phrase; (2) the LAST few KB of -Err (never the
    whole file) contain the filter marker -- a real dispatch's .err starts by
    echoing the prompt itself, so scanning the whole file risks matching an
    early, unrelated mention while the run is still genuinely alive. The
    marker string is provider prose that will drift in wording, so the match
    requires both the "flag" concept and the "cybersecurity" concept
    (case-insensitively, either order) in that tail window rather than the
    exact sentence.

    Direct liveness probe (-PidFile), the other half of the bug above: the
    contract (contracts/review-loop.md:57, hardening invariant 5) defines
    liveness as "a DIRECT probe of the run itself -- its PID/exit status",
    which artifact timestamps alone can never satisfy. invoke-codex-prompt.ps1
    and invoke-claude-prompt.ps1 now write a sidecar `<slug>.pid` file at
    launch, two lines: `pid=<PID>` and, when available, `start=<DateTime
    ticks>` (the recorded process's StartTime, used only to detect a PID
    reused by an unrelated LATER process -- a mismatch is treated as "dead",
    never "alive"). On Windows the recorded PID is the WRAPPER's own process
    (see invoke-*-prompt.ps1 for why: PowerShell's call operator does not
    always spawn a separate child, e.g. for a `.ps1`-shim provider), not
    necessarily a distinct provider child process -- a disclosed, narrower
    guarantee than the Bash sibling's true child-PID capture. Pass -PidFile
    pointing at that file to enable the probe. It is OPTIONAL and purely
    additive: an older invoke-*-prompt.ps1, a hand-rolled background launch,
    or any run started outside the wrapper entirely -- the common case, not
    the edge -- simply never produces a `.pid` file, the probe resolves
    "unknown", and this watcher's behavior is IDENTICAL to before this fix.

    Combined rule for what "not running" means (a finished-successfully run
    and a died-silently run are both "not running" on their own): the DONE
    checks below always run FIRST, every poll. Only when none of them fired
    this same iteration does a confirmed-dead probe result produce the new
    DEAD status -- a process that exits normally after writing its completion
    artifact is still DONE even though the same poll would also see its PID
    gone.
#>
[CmdletBinding()]
param(
  [string]$Out,
  [string]$Err,
  [string]$LastMsg,
  [string]$CommitBase,
  [string]$PidFile,
  [int]$StallSecs = 2700,
  [int]$MaxSecs = 3600,
  [double]$PollSecs = 25
)

$ErrorActionPreference = 'SilentlyContinue'

function Write-Usage {
  Write-Error @'
Usage:
  await-codex-dispatch.ps1 -Out <out-path> [-Err <err-path>]
    [-LastMsg <lastmsg-path>] [-CommitBase <sha>] [-PidFile <path>]
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

# Bytes of -Err's TAIL scanned for the cybersecurity filter marker (see the
# header comment). Deliberately NOT the whole file -- see rationale above.
$FilterTailBytes = 8192

# Read the last $MaxBytes bytes of $Path as text, or '' for a missing/
# unreadable/empty file. Opened with FileShare ReadWrite so a still-writing
# provider process is never blocked or locked out by this read.
function Get-TailText([string]$Path, [int]$MaxBytes) {
  if (-not $Path -or -not (Test-Path -LiteralPath $Path -PathType Leaf)) { return '' }
  try {
    $length = (Get-Item -LiteralPath $Path -Force).Length
    if ($length -le 0) { return '' }
    $readLength = [Math]::Min([int64]$MaxBytes, $length)
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
    try {
      $stream.Seek(-$readLength, [System.IO.SeekOrigin]::End) | Out-Null
      $buffer = New-Object byte[] $readLength
      $stream.Read($buffer, 0, $readLength) | Out-Null
    } finally {
      $stream.Dispose()
    }
    return [System.Text.Encoding]::UTF8.GetString($buffer)
  } catch {
    return ''
  }
}

# True iff the tail of $Path carries both the "flag" and "cybersecurity"
# concepts, case-insensitively. False for a missing/unreadable/empty file or
# a tail with neither/only-one concept -- the caller then falls through to
# pre-existing behavior, never a false positive from an absent file.
function Test-FilterMarker([string]$Path) {
  $tailText = Get-TailText $Path $FilterTailBytes
  if (-not $tailText) { return $false }
  $lower = $tailText.ToLowerInvariant()
  return ($lower.Contains('flag') -and $lower.Contains('cybersecurit'))
}

# Classify the sidecar `.pid` file's recorded run as 'alive' | 'dead' |
# 'unknown'. 'unknown' (missing file, unreadable, or a malformed `pid=` line)
# is the explicit degrade path: the caller must fall back to the
# pre-existing artifact-only checks exactly as if -PidFile had never been
# passed.
function Get-PidFileStatus([string]$PidFilePath) {
  if (-not $PidFilePath -or -not (Test-Path -LiteralPath $PidFilePath -PathType Leaf)) {
    return 'unknown'
  }
  $recordedPid = $null
  $recordedStart = $null
  try {
    foreach ($line in Get-Content -LiteralPath $PidFilePath -ErrorAction Stop) {
      if ($line -match '^pid=(\d+)$') { $recordedPid = [int]$Matches[1] }
      elseif ($line -match '^start=(.+)$') { $recordedStart = $Matches[1] }
    }
  } catch {
    return 'unknown'
  }
  if ($null -eq $recordedPid) { return 'unknown' }
  $proc = Get-Process -Id $recordedPid -ErrorAction SilentlyContinue
  if ($null -eq $proc) { return 'dead' }
  if ($recordedStart) {
    try {
      $currentStart = $proc.StartTime.Ticks.ToString()
      if ($currentStart -ne $recordedStart) {
        # A DIFFERENT process now holds this PID -- the run we launched is gone.
        return 'dead'
      }
    } catch {
      # StartTime can throw (e.g. a cross-session/elevated process this
      # session cannot inspect). The PID DOES exist -- treat conservatively as
      # alive rather than risk a false DEAD on a run that may still finish.
      return 'alive'
    }
  }
  return 'alive'
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

  # Cybersecurity content-filter detection: only reached when none of the
  # DONE checks above fired THIS poll (see header comment for the full
  # conjunction). Independent of -PidFile -- fires on content alone, every
  # poll, so it never waits out -StallSecs the way the live incident did.
  if ($Err -and (Test-FilterMarker $Err)) {
    Write-Output "FILTERED err=$Err reason=provider-cybersecurity-content-filter action=redispatch-different-model-do-not-reword"
    exit 77
  }

  # Direct liveness probe: only reached when none of the DONE checks above
  # fired THIS poll, so a process that already exited after writing its
  # completion artifact is still DONE, never DEAD -- see the combined-rule
  # comment in the header. -PidFile omitted (or unreadable/malformed)
  # resolves 'unknown' and this block is a no-op, matching pre-fix behavior.
  if ($PidFile -and (Get-PidFileStatus $PidFile) -eq 'dead') {
    Write-Output "DEAD pid-file=$PidFile"
    exit 69
  }

  if ($Err -and (Test-Path -LiteralPath $Err -PathType Leaf)) {
    try {
      $errInfo = Get-Item -LiteralPath $Err -Force
      $errIdle = [math]::Floor(((Get-Date) - $errInfo.LastWriteTime).TotalSeconds)
      if ($errIdle -gt $StallSecs) {
        Write-Output "STALL err-idle=$errIdle"
        exit 75
      }
    } catch { }
  }

  $elapsed = [math]::Floor(((Get-Date) - $started).TotalSeconds)
  if ($elapsed -ge $MaxSecs) {
    Write-Output "TIMEOUT max=$MaxSecs"
    exit 124
  }

  Start-Sleep -Milliseconds ([math]::Max(1, [int][math]::Ceiling($PollSecs * 1000)))
}

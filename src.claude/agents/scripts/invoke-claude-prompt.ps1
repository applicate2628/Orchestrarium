<#
.SYNOPSIS
    File-based prompt orchestration wrapper for claude CLI (PowerShell).
.DESCRIPTION
    Encapsulates the shared "External CLI prompt delivery" governance:
      1. Active-availability probe (Get-Command claude) before any file operation; fails closed.
      2. Commercial-auth ToS guard before prompt, ledger, or claude side effects; fails closed.
      3. Prompt body persisted to .scratch/claude-prompts/<topic>-<timestamp>.md
      4. claude invoked with prompt piped via stdin redirection, never via argv
      5. stdout and stderr captured to sibling .out / .err files
      6. Three output paths printed in order: prompt, out, err
      7. Claude exit code propagated

    This wrapper drives automated headless `claude -p` runs and refuses subscription
    OAuth unless commercial auth is detected. Set
    ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE=1 only for commercial auth exposed through
    an undetectable path or when the operator explicitly accepts the risk. For the
    secret-backed API transport (`reserveResolver: claude-wrapper`), use
    `invoke-claude-api.ps1` instead.
.EXAMPLE
    Get-Content -Raw prompt.md |
      powershell -ExecutionPolicy Bypass -File .claude\agents\scripts\invoke-claude-prompt.ps1 advisory-adr
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -Command "& '.claude\agents\scripts\invoke-claude-prompt.ps1' worker-task -PromptFile 'prompt.md' -ClaudeFlags @('-p','--output-format','text','--model','opus','--effort','xhigh')"
.NOTES
    Overriding the default profile: use the `-Command` / call-operator (`&`) form shown
    above — verified end-to-end (guard passes, reaches the claude binary probe) on both
    Windows PowerShell 5.1 and PowerShell 7.6.

    Do NOT use `-File` when overriding -ClaudeFlags. `-File` is a process-spawn boundary:
    the child process receives only literal argv strings, and there is no `-File` shape
    that survives it. All three of the following were measured to fail, identically, on
    both hosts:
      - an array literal typed after `-File` (`... -File script.ps1 ... -ClaudeFlags
        @('--model', ...)`) — the OUTER shell evaluates and flattens `@(...)` into
        separate strings before the CHILD process ever sees them, and the flattened
        `-ClaudeFlags` token collides with the array elements that follow, so the
        child's own parameter binder reports "parameter 'ClaudeFlags' is specified more
        than once";
      - a bare `--` delimiter (`-- --model opus --effort max`) — unlike the Bash
        sibling, PowerShell's parameter binder has no `--`-end-of-options convention: a
        literal `--` token is parsed as an attempt to bind a parameter with an empty
        name, which is ambiguous against every declared parameter here;
      - a comma-joined string (`-ClaudeFlags -p,--output-format,text,--model,...`) —
        this arrives as ONE literal token, not several, so the guard finds no exact
        `--model` match and denies.
    Only the `-Command`/call-operator form works, because there the SAME process that
    evaluates the `@(...)` array literal also invokes the script via `&` — the array
    never crosses a process boundary as flattened strings. This is a property of how any
    process passes arguments to a child, not a PowerShell-host difference: both 5.1 and
    7.6 were measured to behave identically for every shape above.
#>
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$TopicSlug,

  [string]$PromptFile,

  # Work-item dir: the dispatch PRODUCES its ledger events (decision
  # 2026-07-16-review-verdict-closure) — launch before the run, terminal after it
  # via the shared completion oracle.
  [string]$Ledger,
  [string]$LedgerRole = 'architecture-reviewer',
  [string]$LedgerLane,
  [string]$LedgerArtifact,
  [string[]]$LedgerCloses,

  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$ClaudeFlags
)

$ErrorActionPreference = 'Stop'

# F1 (security review 2026-05-17) — TopicSlug filesystem-boundary validation.
# The slug is concatenated into captured filenames in $outputDir. Without
# validation, a caller-supplied value like `..\..\tracked-leak` resolved
# outside the prompt directory (empirically reproduced by the security
# reviewer), and `legit:hidden` exposed NTFS Alternate Data Stream syntax.
# Reject path traversal, path separators, drive/ADS separator, Windows-
# invalid filename chars, NUL, and overlong slugs at the boundary.
if ([string]::IsNullOrEmpty($TopicSlug) -or
    $TopicSlug.Length -gt 64 -or
    $TopicSlug -match '\.\.' -or
    $TopicSlug -match '[\\/:\*\?"<>\|\x00]') {
  Write-Error "FAIL: invalid TopicSlug '$TopicSlug' - must be 1-64 chars and exclude '..', path separators (/, \\), drive/ADS separator (:), and Windows-invalid filename chars (*, ?, double-quote, <, >, |, NUL)"
  exit 1
}

if (-not $ClaudeFlags -or $ClaudeFlags.Count -eq 0) {
  # A12: every provider-backed run must carry an explicit model AND effort, never
  # an ambient one — the default below pins the shipped default profile `opus-xhigh`
  # (same fix as the sibling invoke-codex-prompt.ps1). Callers needing a different
  # profile invoke via `-Command "& script.ps1 ... -ClaudeFlags @(...)"` (see the
  # .EXAMPLE / .NOTES above this param block — `-File` cannot carry an override
  # array across its process-spawn boundary, and a bare `--` delimiter is
  # unsupported here regardless of host; both are documented and measured above,
  # not just a style preference), which REPLACES this default wholesale
  # (including --model) — it is not merged, so a partial override drops the pin.
  # The guard below validates the FINAL resolved array and refuses to launch
  # otherwise. (current claude CLI removed top-level --quiet; -p/--print is
  # non-interactive)
  $ClaudeFlags = @('-p', '--output-format', 'text', '--model', 'opus', '--effort', 'xhigh')
}

# A12 guard helpers: find an explicit --model value, and an explicit --effort
# <tier> value, in a resolved claude flag array. Case-sensitive matches
# (-ceq/-ccontains) so this mirrors the Bash sibling's case-sensitive `case`
# matching exactly, rather than PowerShell's default case-INSENSITIVE string
# comparison.
function Get-ClaudeFlagModel {
  param([string[]]$Flags)
  # Bound is $Flags.Count (not Count - 1): scanning every index, including the
  # last one, is deliberate so no reader has to re-derive that a narrower bound
  # is equivalent. $Flags[$i + 1] on the last index reads one past the end,
  # which PowerShell returns as $null (no exception) — the `-and` short-circuits
  # to false there, so this is a no-op for that index, not an out-of-bounds risk.
  for ($i = 0; $i -lt $Flags.Count; $i++) {
    if ($Flags[$i] -ceq '--model' -and $Flags[$i + 1] -and $Flags[$i + 1] -cnotmatch '^-') { return $Flags[$i + 1] }
  }
  return $null
}
function Get-ClaudeFlagEffort {
  param([string[]]$Flags)
  $allowed = @('low', 'medium', 'high', 'xhigh', 'max')
  # See Get-ClaudeFlagModel above for why the bound is Count, not Count - 1.
  # `-ccontains` against the fixed enum is already an exact-equality membership
  # test (not a prefix/substring match), so unlike the Codex effort regex this
  # one needs no separate tail-anchoring fix (F5 does not apply here).
  for ($i = 0; $i -lt $Flags.Count; $i++) {
    if ($Flags[$i] -ceq '--effort' -and $allowed -ccontains $Flags[$i + 1]) { return $Flags[$i + 1] }
  }
  return $null
}

# A12 guard: the FINAL resolved $ClaudeFlags (the shipped default above, OR a
# non-empty remaining-argument block that replaces it wholesale) must carry an
# explicit --model and an explicit --effort <tier>. Checked once here, on
# whichever array is in scope by this point, so this catches both a partial
# override that drops the model pin and a hypothetical future variant that
# ships no default at all — either way, an unpinned run must never reach
# claude and silently resolve its model from ambient config.
$claudeResolvedModel = Get-ClaudeFlagModel -Flags $ClaudeFlags
$claudeResolvedEffort = Get-ClaudeFlagEffort -Flags $ClaudeFlags
if ([string]::IsNullOrEmpty($claudeResolvedModel) -or [string]::IsNullOrEmpty($claudeResolvedEffort)) {
  Write-Error ("FAIL: A12 violation - the resolved claude flags carry no explicit --model and/or no explicit " +
    "--effort <tier>. A remaining-argument block replaces ALL defaults, including --model, so a partial " +
    "override (e.g. only changing effort) silently drops the model pin and falls back to whatever model the " +
    "ambient claude config selects - the exact outcome A12 forbids. Pass the FULL per-profile flag set, e.g.: " +
    "-p --output-format text --model opus --effort xhigh")
  exit 1
}

$claudeBin = if ($env:CLAUDE_BIN) { $env:CLAUDE_BIN } else { 'claude' }
$commandInfo = Get-Command -Name $claudeBin -ErrorAction SilentlyContinue
if (-not $commandInfo) {
  Write-Error "FAIL: claude binary '$claudeBin' not found on PATH. Set CLAUDE_BIN if installed elsewhere."
  exit 1
}
$claudePath = $commandInfo.Source

function Test-ClaudeAuthTruthy {
  param([AllowNull()][string]$Value)

  if ([string]::IsNullOrEmpty($Value)) {
    return $false
  }
  $normalizedValue = $Value.ToLowerInvariant()
  return ($normalizedValue -eq '1' -or
          $normalizedValue -eq 'true' -or
          $normalizedValue -eq 'yes')
}

$hasApiKeyHelper = $false
$userHomeDir = $null
if (-not [string]::IsNullOrEmpty($env:USERPROFILE)) {
  $userHomeDir = $env:USERPROFILE
} elseif (-not [string]::IsNullOrEmpty($env:HOME)) {
  $userHomeDir = $env:HOME
}

$settingsPaths = @()
if ($null -ne $userHomeDir -and -not [string]::IsNullOrEmpty($userHomeDir)) {
  $settingsPaths += Join-Path -Path $userHomeDir -ChildPath '.claude\settings.json'
}
$settingsPaths += Join-Path -Path (Get-Location).Path -ChildPath '.claude\settings.json'
foreach ($settingsPath in $settingsPaths) {
  if (Test-Path -LiteralPath $settingsPath -PathType Leaf) {
    try {
      $settingsContent = [System.IO.File]::ReadAllText($settingsPath)
      if ($settingsContent.Contains('"apiKeyHelper"')) {
        $hasApiKeyHelper = $true
        break
      }
    } catch {
      # An unreadable settings file cannot prove commercial auth; fail closed below.
    }
  }
}

$hasCommercialClaudeAuth = (
  (-not [string]::IsNullOrEmpty($env:ANTHROPIC_API_KEY)) -or
  (-not [string]::IsNullOrEmpty($env:ANTHROPIC_AUTH_TOKEN)) -or
  (Test-ClaudeAuthTruthy $env:CLAUDE_CODE_USE_BEDROCK) -or
  (Test-ClaudeAuthTruthy $env:CLAUDE_CODE_USE_VERTEX) -or
  $hasApiKeyHelper -or
  ((-not [string]::IsNullOrEmpty($env:ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE)) -and
   $env:ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE -eq '1')
)

if (-not $hasCommercialClaudeAuth) {
  $claudeSubscriptionWarning = @'
WARNING: Refusing automated Claude launch.
Automated `claude -p` under a subscription is not permitted.
Anthropic policy: https://code.claude.com/docs/en/legal-and-compliance

Note: this checks for a commercial-auth SIGNAL in the environment; it cannot confirm
which credential the claude CLI ultimately uses. A stale ANTHROPIC_API_KEY/AUTH_TOKEN
here does NOT guarantee the CLI is not falling back to a stored subscription (OAuth)
login; make sure the commercial key is the auth claude actually resolves.

Use one of these commercial authentication paths:
  - set ANTHROPIC_API_KEY;
  - use invoke-claude-api.sh/.ps1 with SECRET.md's ANTHROPIC_AUTH_TOKEN and ANTHROPIC_BASE_URL; or
  - configure apiKeyHelper, Amazon Bedrock, or Google Vertex AI.

For commercial auth exposed through an undetectable path, or to explicitly accept the risk, set:
  ORCHESTRARIUM_ALLOW_SUBSCRIPTION_CLAUDE=1
'@
  [Console]::Error.WriteLine($claudeSubscriptionWarning)
  exit 3
}

$outputDir = if ($env:CLAUDE_PROMPTS_DIR) { $env:CLAUDE_PROMPTS_DIR } else { '.scratch\claude-prompts' }
$timestamp = Get-Date -Format 'yyyyMMdd-HHmmss'
# F3 (security review 2026-05-17) — Unpredictable filename component.
# Predictable timestamp-only names enabled a same-machine racer to anticipate
# captured-file paths and either pre-create symlinks at those paths or race-
# modify the captured content between native-call exit and the post-process
# re-encode loop. Adding 8 hex chars of GUID entropy widens the window past
# practical guessing while keeping the slug human-readable for debugging.
$randomSuffix = [System.Guid]::NewGuid().ToString('N').Substring(0, 8)
$slug = "$TopicSlug-$timestamp-$randomSuffix"

$outputDirExisted = Test-Path -LiteralPath $outputDir -PathType Container
New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
# F3 (security review 2026-05-17) — Restrictive ACL on prompt directory when
# we just created it. Without this, the directory inherits parent ACLs
# (empirically the security reviewer saw `Authenticated Users Modify` and
# `Users ReadAndExecute` on .scratch). Disable inheritance and grant only the
# current user. Skip if the directory already existed so we don't tighten a
# path the caller may be sharing with other tooling. On non-Windows or in
# constrained sandboxes the ACL operations can fail legitimately — warn and
# proceed (the file-naming unpredictability above is the primary defence).
if (-not $outputDirExisted -and $PSVersionTable.Platform -ne 'Unix') {
  try {
    $acl = Get-Acl -LiteralPath $outputDir
    $acl.SetAccessRuleProtection($true, $false)
    $currentUser = if ($env:USERDOMAIN) { "$env:USERDOMAIN\$env:USERNAME" } else { $env:USERNAME }
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
      $currentUser,
      'FullControl',
      'ContainerInherit,ObjectInherit',
      'None',
      'Allow'
    )
    $acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $outputDir -AclObject $acl
  } catch {
    Write-Warning "WARN: could not harden ACL on '$outputDir': $($_.Exception.Message)"
  }
}
$promptPath = Join-Path $outputDir "$slug.md"
$outPath = Join-Path $outputDir "$slug.out"
$errPath = Join-Path $outputDir "$slug.err"

if ($PromptFile) {
  if (-not (Test-Path -LiteralPath $PromptFile -PathType Leaf)) {
    Write-Error "FAIL: --prompt-file '$PromptFile' does not exist"
    exit 1
  }
  # F2 (security review 2026-05-17) — Reject reparse-point prompt files
  # (symlinks, junctions, mount points). `Test-Path -PathType Leaf` returns
  # True for symlinks pointing at regular files, and `Copy-Item -LiteralPath`
  # then follows the link to the target (empirically the reviewer pointed a
  # symlink at a SECRET_PROBE file and watched the wrapper persist and forward
  # its contents). Refuse the input and let the caller resolve.
  $promptInfo = Get-Item -LiteralPath $PromptFile -Force
  if ($promptInfo.Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
    Write-Error "FAIL: --prompt-file '$PromptFile' is a reparse point (symlink/junction/mount point); refusing to follow. Pass the resolved target path explicitly if intended."
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

$hadDispatchedReviewMarker = Test-Path Env:ORCHESTRARIUM_DISPATCHED_REVIEW
$previousDispatchedReviewMarker = $env:ORCHESTRARIUM_DISPATCHED_REVIEW

# A1 (arch review 2026-05-17) — Read prompt body under strict wrapper error
# semantics with explicit UTF-8 no-BOM, BEFORE relaxing $ErrorActionPreference
# for the native call. PS 5.1's `Get-Content -Raw` without `-Encoding UTF8`
# reads UTF-8 no-BOM files via the system ANSI codepage, corrupting non-ASCII
# bytes. `[IO.File]::ReadAllText` with an explicit UTF8Encoding($false)
# round-trips byte-for-byte with the WriteAllText writer used above. Strict
# error semantics also still cover this read so a corrupted prompt file fails
# loud, not silent.
$promptBody = [System.IO.File]::ReadAllText($promptPath, [System.Text.UTF8Encoding]::new($false))

# -Ledger: record the LAUNCH event before the run (fail closed on failure).
$launchRunId = ''
$ledgerHelper = ''
if ($Ledger) {
  foreach ($cand in @((Join-Path $PSScriptRoot 'agent-run-ledger.py'), 'scripts/agent-run-ledger.py', (Join-Path $PSScriptRoot '..\..\..\scripts\agent-run-ledger.py'))) {
    if (Test-Path -LiteralPath $cand -PathType Leaf) { $ledgerHelper = $cand; break }
  }
  if (-not $ledgerHelper) {
    Write-Error "FAIL: -Ledger given but scripts/agent-run-ledger.py not found"
    exit 1
  }
  $launchRunId = "{0:yyyyMMddTHHmmss}Z-launch-{1}" -f [DateTime]::UtcNow, $slug
  # Both fields were already validated non-empty by the A12 guard above; reuse
  # the same resolved values here instead of re-deriving them, so the guard and
  # the recorded provenance can never key on different extractions.
  $ledgerArgs = @('--work-item', $Ledger, 'append', '--run-id', $launchRunId,
    '--role', $LedgerRole, '--execution-role', 'external-reviewer', '--provider', 'claude',
    '--status', 'running', '--gate', 'none', '--scope', "external run: $slug",
    '--event-kind', 'launch', '--prompt-file', $promptPath,
    '--notes', 'wrapper-dispatched; terminal event follows the completion oracle',
    '--model', $claudeResolvedModel, '--effort', $claudeResolvedEffort)
  if ($LedgerLane) { $ledgerArgs += @('--lane', $LedgerLane) }
  if ($LedgerArtifact) { $ledgerArgs += @('--artifact', $LedgerArtifact) }
  & python $ledgerHelper @ledgerArgs | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Error "FAIL: could not record launch event in $Ledger"
    exit 1
  }
}

try {
  $env:ORCHESTRARIUM_DISPATCHED_REVIEW = '1'
  # Invoke claude via PowerShell native call operator. `&` handles shim resolution
  # (`.exe`, `.cmd`, `.ps1`) on both PS 5.1 + PS 7+ — unlike `[Process]::Start` with
  # `UseShellExecute=$false`, which only launches native `.exe` binaries and breaks
  # on npm-installed `claude.ps1` shims. Prompt body is fed from the variable above
  # (read under strict semantics with explicit UTF-8); stdout/stderr captured via
  # PowerShell's native `1>` / `2>` redirection; exit code via `$LASTEXITCODE`.
  $promptBody | & $claudePath @ClaudeFlags `
    1> $outPath 2> $errPath
  $exitCode = $LASTEXITCODE
} finally {
  if ($hadDispatchedReviewMarker) {
    $env:ORCHESTRARIUM_DISPATCHED_REVIEW = $previousDispatchedReviewMarker
  } else {
    Remove-Item Env:ORCHESTRARIUM_DISPATCHED_REVIEW -ErrorAction SilentlyContinue
  }
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

# Shared completion oracle: verdict accepted ONLY on exit 0 + clean .err + non-empty
# .out + FINAL non-blank line exactly 'GATE: PASS|REVISE'; else blocked/none.
if ($Ledger) {
  $finalLine = ''
  if ((Test-Path -LiteralPath $outPath -PathType Leaf) -and (Get-Item -LiteralPath $outPath).Length -gt 0) {
    $lines = Get-Content -LiteralPath $outPath | Where-Object { $_.Trim() -ne '' }
    if ($lines) { $finalLine = ($lines | Select-Object -Last 1) -replace "`r$", '' }
  }
  $errMarkers = 0
  if ((Test-Path -LiteralPath $errPath -PathType Leaf) -and (Get-Item -LiteralPath $errPath).Length -gt 0) {
    $errMarkers = @(Select-String -LiteralPath $errPath -Pattern '^(ERROR|FATAL|API Error): ' -CaseSensitive -AllMatches).Count
  }
  $termStatus = 'blocked'; $termGate = 'none'; $termNote = 'oracle: '
  if ($exitCode -ne 0) { $termNote += "nonzero exit ($exitCode)" }
  elseif (-not (Test-Path -LiteralPath $outPath -PathType Leaf) -or (Get-Item -LiteralPath $outPath).Length -eq 0) { $termNote += 'empty .out' }
  elseif ($errMarkers -gt 0) { $termNote += "err markers present ($errMarkers)" }
  elseif ($finalLine -ceq 'GATE: PASS') { $termStatus = 'completed'; $termGate = 'PASS'; $termNote += 'final-line GATE: PASS' }
  elseif ($finalLine -ceq 'GATE: REVISE') { $termStatus = 'revise'; $termGate = 'REVISE'; $termNote += 'final-line GATE: REVISE' }
  else { $termNote += 'final line is not an anchored GATE verdict' }
  $termArgs = @('--work-item', $Ledger, 'append',
    '--role', $LedgerRole, '--execution-role', 'external-reviewer', '--provider', 'claude',
    '--status', $termStatus, '--gate', $termGate, '--scope', "external run: $slug",
    '--event-kind', 'terminal', '--launch-run-id', $launchRunId,
    '--evidence', "review:$outPath", '--notes', $termNote,
    '--model', $claudeResolvedModel, '--effort', $claudeResolvedEffort)
  if ($LedgerLane) { $termArgs += @('--lane', $LedgerLane) }
  if ($LedgerArtifact) { $termArgs += @('--artifact', $LedgerArtifact) }
  if ($termGate -eq 'PASS' -and $LedgerCloses) {
    foreach ($c in $LedgerCloses) { $termArgs += @('--closes', $c) }
  }
  & python $ledgerHelper @termArgs | Out-Null
  if ($LASTEXITCODE -ne 0) {
    # LOUD, not a passing warning: a dropped terminal loses the reviewer's verdict
    # and leaves the launch unsettled — the exact failure this transport prevents.
    # (Cross-shell parity with the .sh twins; step-back gate MINOR-1, 2026-07-17.)
    Write-Error "FAIL: could not record terminal event in $Ledger" -ErrorAction Continue
    Write-Error "FAIL: the verdict in $outPath is NOT in the ledger; launch $launchRunId stays unsettled." -ErrorAction Continue
    Write-Error "FAIL: record it by hand: python scripts/agent-run-ledger.py --work-item $Ledger append --event-kind terminal --launch-run-id $launchRunId ..." -ErrorAction Continue
  }
}

Write-Output $promptPath
Write-Output $outPath
Write-Output $errPath

exit $exitCode

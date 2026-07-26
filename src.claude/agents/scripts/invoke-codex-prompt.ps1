<#
.SYNOPSIS
    File-based prompt orchestration wrapper for codex CLI (PowerShell).
.DESCRIPTION
    Encapsulates the shared "External CLI prompt delivery" governance:
      1. Active-availability probe (Get-Command codex) before any file operation; fails closed.
      2. Prompt body persisted to .scratch/codex-prompts/<topic>-<timestamp>.md
      3. codex invoked with prompt piped via stdin redirection, never via argv
      4. stdout and stderr captured to sibling .out / .err files; final message to .lastmsg
      5. Four output paths and the active-watch command printed before the provider starts
      6. Codex exit code propagated
.EXAMPLE
    Get-Content -Raw prompt.md |
      powershell -ExecutionPolicy Bypass -File .claude\agents\scripts\invoke-codex-prompt.ps1 advisory-adr
.EXAMPLE
    powershell -NoProfile -ExecutionPolicy Bypass -Command "& '.claude\agents\scripts\invoke-codex-prompt.ps1' worker-task -PromptFile 'prompt.md' -CodexFlags @('--model','gpt-5.6-sol','-c','model_reasoning_effort=xhigh')"
.NOTES
    Overriding the default profile: use the `-Command` / call-operator (`&`) form shown
    above — verified end-to-end (guard passes, reaches the codex binary probe) on both
    Windows PowerShell 5.1 and PowerShell 7.6.

    Do NOT use `-File` when overriding -CodexFlags. `-File` is a process-spawn boundary:
    the child process receives only literal argv strings, and there is no `-File` shape
    that survives it. All three of the following were measured to fail, identically, on
    both hosts:
      - an array literal typed after `-File` (`... -File script.ps1 ... -CodexFlags
        @('--model', ...)`) — the OUTER shell evaluates and flattens `@(...)` into
        separate strings before the CHILD process ever sees them, and the flattened
        `-CodexFlags` token collides with the array elements that follow, so the child's
        own parameter binder reports "parameter 'CodexFlags' is specified more than once";
      - a bare `--` delimiter (`-- --model gpt-5.6-sol ...`) — unlike the Bash sibling,
        PowerShell's parameter binder has no `--`-end-of-options convention: a literal
        `--` token is parsed as an attempt to bind a parameter with an empty name, which
        is ambiguous against every declared parameter here;
      - a comma-joined string (`-CodexFlags --model,gpt-5.6-sol,-c,...`) — this arrives
        as ONE literal token, not four, so the guard finds no exact `--model` match and
        denies.
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
  # 2026-07-16-review-verdict-closure) — a launch event before the run and a
  # terminal event settled by the shared completion oracle after it.
  [string]$Ledger,
  [string]$LedgerRole = 'architecture-reviewer',
  [string]$LedgerLane,
  [string]$LedgerArtifact,
  [string[]]$LedgerCloses,

  [Parameter(ValueFromRemainingArguments = $true)]
  [string[]]$CodexFlags
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

if (-not $CodexFlags -or $CodexFlags.Count -eq 0) {
  # Codex CLI 0.130.0+ uses `codex exec` (non-interactive subcommand); the old
  # top-level --quiet / --full-auto flags were removed. A12: every provider-backed
  # run must carry an explicit model AND effort, never an ambient one — the
  # default below pins the shipped default profile `gpt-5.6-sol-xhigh`. Callers
  # needing a different profile invoke via `-Command "& script.ps1 ... -CodexFlags
  # @(...)"` (see the .EXAMPLE / .NOTES above this param block — `-File` cannot
  # carry an override array across its process-spawn boundary, and a bare `--`
  # delimiter is unsupported here regardless of host; both are documented and
  # measured above, not just a style preference), which REPLACES this default
  # wholesale (including --model) — it is not merged, so a partial override
  # drops the pin. The guard below validates the FINAL
  # resolved array and refuses to launch otherwise.
  $CodexFlags = @('--model', 'gpt-5.6-sol', '-c', 'model_reasoning_effort=xhigh')
}

# A12 guard helpers: find an explicit --model value, and an explicit
# -c model_reasoning_effort=<tier> value, in a resolved codex flag array.
# Case-sensitive matches (-ceq/-cmatch) so this mirrors the Bash sibling's
# case-sensitive `case`/`=~` matching exactly, rather than PowerShell's
# default case-INSENSITIVE string comparison.
function Get-CodexFlagModel {
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
function Get-CodexFlagEffort {
  param([string[]]$Flags)
  # See Get-CodexFlagModel above for why the bound is Count, not Count - 1.
  for ($i = 0; $i -lt $Flags.Count; $i++) {
    if ($Flags[$i] -ceq '-c' -and $Flags[$i + 1] -cmatch '^model_reasoning_effort="?(low|medium|high|xhigh|max)"?$') {
      return $Matches[1]
    }
  }
  return $null
}

# A12 guard: the FINAL resolved $CodexFlags (the shipped default above, OR a
# non-empty remaining-argument block that replaces it wholesale — a partial
# block bound to $CodexFlags at the top of the script suppresses the default
# entirely, per the `ValueFromRemainingArguments` parameter) must carry an
# explicit --model and an explicit -c model_reasoning_effort=<tier>. Checked
# once here, on whichever array is in scope by this point, so this catches
# both a partial override that drops the model pin and a hypothetical future
# variant that ships no default at all — either way, an unpinned run must
# never reach codex and silently resolve its model from the ambient
# ~/.codex/config.toml.
$codexResolvedModel = Get-CodexFlagModel -Flags $CodexFlags
$codexResolvedEffort = Get-CodexFlagEffort -Flags $CodexFlags
if ([string]::IsNullOrEmpty($codexResolvedModel) -or [string]::IsNullOrEmpty($codexResolvedEffort)) {
  Write-Error ("FAIL: A12 violation - the resolved codex flags carry no explicit --model and/or no explicit " +
    "-c model_reasoning_effort=<tier>. A remaining-argument block replaces ALL defaults, including --model, " +
    "so a partial override (e.g. only changing effort or a feature toggle) silently drops the model pin and " +
    "falls back to the ambient ~/.codex/config.toml model - the exact outcome A12 forbids. Pass the FULL " +
    "per-profile flag set, e.g.: --model gpt-5.6-sol -c model_reasoning_effort=xhigh")
  exit 1
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
$lastmsgPath = Join-Path $outputDir "$slug.lastmsg"

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
  # leading BOM at codex stdin would otherwise be interpreted as prompt content.
  [System.IO.File]::WriteAllText($promptPath, $stdin, [System.Text.UTF8Encoding]::new($false))
}

# UTF-8 encoding for the native-command pipeline. PS 5.1 defaults `$OutputEncoding`
# to ASCII, which silently mangles non-ASCII bytes piped into a native process.
# Setting all three layers (`$OutputEncoding`, console In, console Out) ensures
# the prompt body reaches codex stdin and captured stdout/stderr stay UTF-8 clean.
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
# process writes to stderr — including normal progress messages like
# "Reading prompt from stdin..." — becomes a fatal NativeCommandError that
# kills the script before `$LASTEXITCODE` can be captured. The wrapper-side
# Stop strictness is restored in the finally block.
$ErrorActionPreference = 'Continue'

# A1 (arch review 2026-05-17) — Read prompt body under strict wrapper error
# semantics with explicit UTF-8 no-BOM, BEFORE relaxing $ErrorActionPreference
# for the native call. PS 5.1's `Get-Content -Raw` without `-Encoding UTF8`
# reads UTF-8 no-BOM files via the system ANSI codepage, corrupting non-ASCII
# bytes (empirically: sent `Привет` codepoints 1055,1088,1080,1074,1077,1090
# → child saw garbled 1056,1119,1057,1026,1056,1105,...). `[IO.File]::
# ReadAllText` with an explicit UTF8Encoding($false) round-trips byte-for-byte
# with the WriteAllText writer used above. Strict error semantics also still
# cover this read so a corrupted prompt file fails loud, not silent.
$promptBody = [System.IO.File]::ReadAllText($promptPath, [System.Text.UTF8Encoding]::new($false))

# --Ledger: record the LAUNCH event before the run (fail closed on failure).
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
    '--role', $LedgerRole, '--execution-role', 'external-reviewer', '--provider', 'codex',
    '--status', 'running', '--gate', 'none', '--scope', "external run: $slug",
    '--event-kind', 'launch', '--prompt-file', $promptPath,
    '--notes', 'wrapper-dispatched; terminal event follows the completion oracle',
    '--model', $codexResolvedModel, '--effort', $codexResolvedEffort)
  if ($LedgerLane) { $ledgerArgs += @('--lane', $LedgerLane) }
  if ($LedgerArtifact) { $ledgerArgs += @('--artifact', $LedgerArtifact) }
  & python $ledgerHelper @ledgerArgs | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Error "FAIL: could not record launch event in $Ledger"
    exit 1
  }
}

# Emit the artifact paths and forcing-function command before the provider call
# so a background caller can launch the watcher while Codex is still running.
Write-Output $promptPath
Write-Output $outPath
Write-Output $errPath
Write-Output $lastmsgPath
Write-Output '# actively await this dispatch (do NOT passively wait for a notification):'
$awaitPath = Join-Path $PSScriptRoot 'await-codex-dispatch.ps1'
Write-Output ("powershell -NoProfile -ExecutionPolicy Bypass -File '{0}' -Out '{1}' -Err '{2}' -LastMsg '{3}' -StallSecs 2700" -f `
  $awaitPath.Replace("'", "''"), $outPath.Replace("'", "''"), $errPath.Replace("'", "''"), $lastmsgPath.Replace("'", "''"))

try {
  # Invoke codex via PowerShell native call operator. `&` handles shim resolution
  # (`.exe`, `.cmd`, `.ps1`) on both PS 5.1 + PS 7+ — unlike `[Process]::Start` with
  # `UseShellExecute=$false`, which only launches native `.exe` binaries and breaks
  # on npm/nvm4w-installed `codex.ps1` shims. Prompt body is fed from the variable
  # above (read under strict semantics with explicit UTF-8); stdout/stderr captured
  # via PowerShell's native `1>` / `2>` redirection; exit code via `$LASTEXITCODE`.
  $promptBody | & $codexPath exec --skip-git-repo-check --output-last-message $lastmsgPath @CodexFlags `
    1> $outPath 2> $errPath
  $exitCode = $LASTEXITCODE
} finally {
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

# Shared completion oracle (decision 2026-07-16-review-verdict-closure): a verdict is
# accepted ONLY when exit==0 AND .err has no auth/quota/capacity/truncation markers AND
# the preferred final-message source (.lastmsg when non-empty, otherwise .out) is
# non-empty AND its FINAL non-blank line is exactly 'GATE: PASS|REVISE'. Earlier prose
# mentions are ignored by definition. Anything else -> blocked/none with reason.
if ($Ledger) {
  $verdictPath = $outPath
  if ((Test-Path -LiteralPath $lastmsgPath -PathType Leaf) -and (Get-Item -LiteralPath $lastmsgPath).Length -gt 0) {
    $verdictPath = $lastmsgPath
  }
  $finalLine = ''
  if ((Test-Path -LiteralPath $verdictPath -PathType Leaf) -and (Get-Item -LiteralPath $verdictPath).Length -gt 0) {
    $lines = Get-Content -LiteralPath $verdictPath | Where-Object { $_.Trim() -ne '' }
    if ($lines) { $finalLine = ($lines | Select-Object -Last 1) -replace "`r$", '' }
  }
  $errMarkers = 0
  if ((Test-Path -LiteralPath $errPath -PathType Leaf) -and (Get-Item -LiteralPath $errPath).Length -gt 0) {
    $errMarkers = @(Select-String -LiteralPath $errPath -Pattern '^(ERROR|FATAL|API Error): ' -CaseSensitive -AllMatches).Count
  }
  $termStatus = 'blocked'; $termGate = 'none'; $termNote = 'oracle: '
  if ($exitCode -ne 0) { $termNote += "nonzero exit ($exitCode)" }
  elseif (-not (Test-Path -LiteralPath $verdictPath -PathType Leaf) -or (Get-Item -LiteralPath $verdictPath).Length -eq 0) { $termNote += 'empty .out' }
  elseif ($errMarkers -gt 0) { $termNote += "err markers present ($errMarkers)" }
  elseif ($finalLine -ceq 'GATE: PASS') { $termStatus = 'completed'; $termGate = 'PASS'; $termNote += 'final-line GATE: PASS' }
  elseif ($finalLine -ceq 'GATE: REVISE') { $termStatus = 'revise'; $termGate = 'REVISE'; $termNote += 'final-line GATE: REVISE' }
  else { $termNote += 'final line is not an anchored GATE verdict' }
  $termArgs = @('--work-item', $Ledger, 'append',
    '--role', $LedgerRole, '--execution-role', 'external-reviewer', '--provider', 'codex',
    '--status', $termStatus, '--gate', $termGate, '--scope', "external run: $slug",
    '--event-kind', 'terminal', '--launch-run-id', $launchRunId,
    '--evidence', "review:$verdictPath", '--notes', $termNote,
    '--model', $codexResolvedModel, '--effort', $codexResolvedEffort)
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

exit $exitCode

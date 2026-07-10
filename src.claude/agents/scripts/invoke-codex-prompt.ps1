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
    powershell -ExecutionPolicy Bypass -File .claude\agents\scripts\invoke-codex-prompt.ps1 worker-task --% --prompt-file prompt.md -- --model gpt-5.6-sol
#>
param(
  [Parameter(Mandatory = $true, Position = 0)]
  [string]$TopicSlug,

  [string]$PromptFile,

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
  # needing a different profile (e.g. `--model gpt-5.6-sol -c
  # model_reasoning_effort=max` or `--model gpt-5.6-luna`) pass the full flag
  # set after `--`, which always overrides this default.
  $CodexFlags = @('--model', 'gpt-5.6-sol', '-c', 'model_reasoning_effort=xhigh')
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

try {
  # Invoke codex via PowerShell native call operator. `&` handles shim resolution
  # (`.exe`, `.cmd`, `.ps1`) on both PS 5.1 + PS 7+ — unlike `[Process]::Start` with
  # `UseShellExecute=$false`, which only launches native `.exe` binaries and breaks
  # on npm/nvm4w-installed `codex.ps1` shims. Prompt body is fed from the variable
  # above (read under strict semantics with explicit UTF-8); stdout/stderr captured
  # via PowerShell's native `1>` / `2>` redirection; exit code via `$LASTEXITCODE`.
  $promptBody | & $codexPath exec --skip-git-repo-check @CodexFlags `
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

Write-Output $promptPath
Write-Output $outPath
Write-Output $errPath

exit $exitCode

<#
.SYNOPSIS
    Install Claude Code pack.
.DESCRIPTION
    Copies agents (with contracts, templates, scripts), commands, and CLAUDE.md to the target location.
    Re-running = reinstall. Memory is preserved across reinstalls.
.EXAMPLE
    .\scripts\install-claude.ps1                          # Install into current repo's .claude/
    .\scripts\install-claude.ps1 -Global                  # Install into ~/.claude/
    .\scripts\install-claude.ps1 -Target "D:\my-repo"     # Install into D:\my-repo\.claude/
#>
param(
    [switch]$Global,
    [string]$Target,
    [switch]$Force,
    [switch]$DryRun,
    [switch]$AllowUnsafeTarget,
    [switch]$NoHypothesisHook,
    [ValidateSet("wrapper", "python", "native")]
    [string]$HookRuntime = "python"
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $ScriptDir
$Source = Join-Path $RepoDir "src.claude"
$DefaultAgentsModeSource = Join-Path $RepoDir "shared\agents-mode.defaults.yaml"

# `commands/` is the SINGLE monorepo flow surface: each agents-* flow ships as
# commands/agents-*.md only; generated skills/agents-*/SKILL.md are a standalone-
# BRANCH artifact, reclaimed here if left stale by a prior install.
$Dirs = @("agents", "commands", "skills")
$script:PromptMode = $null
$HookVerificationExclusions = [System.Collections.Generic.HashSet[string]]::new(
    [System.StringComparer]::OrdinalIgnoreCase
)

function Test-Interactive {
    try {
        return [Environment]::UserInteractive -and -not [Console]::IsInputRedirected
    } catch {
        return $false
    }
}

function Get-CanonicalPath {
    param([string]$Path)

    $expanded = [Environment]::ExpandEnvironmentVariables($Path).Trim('"').Trim()
    if ([string]::IsNullOrWhiteSpace($expanded)) {
        throw "Path is empty."
    }

    try {
        return (Resolve-Path -LiteralPath $expanded -ErrorAction Stop).Path
    } catch {
        return [System.IO.Path]::GetFullPath($expanded)
    }
}

function Resolve-InstallTarget {
    param([string]$InputPath)

    $resolved = Get-CanonicalPath -Path $InputPath
    if ((Split-Path -Leaf $resolved).ToLowerInvariant() -eq ".claude") {
        return $resolved
    }
    return (Join-Path $resolved ".claude")
}

function Get-GitRepoRoot {
    try {
        $repoRoot = git rev-parse --show-toplevel 2>$null
        if ($repoRoot) {
            return (Get-CanonicalPath $repoRoot)
        }
    } catch {
        # fallback below
    }
    return (Get-CanonicalPath (Get-Location).Path)
}

function Test-PathNoReparseChain {
    param([string]$Path)

    $current = $Path
    while ($true) {
        if (Test-Path -LiteralPath $current -ErrorAction SilentlyContinue) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing reparse-point target path: $current"
            }
        }

        $parent = Split-Path -Parent $current
        if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $current) {
            break
        }
        $current = $parent
    }
}

function Get-AllowlistRoots {
    param([string]$Mode)

    $list = @()
    if ($Mode -eq "repo") {
        $repoRoot = Get-GitRepoRoot
        $list += Resolve-InstallTarget -InputPath (Join-Path $repoRoot ".claude")
    }

    if ($Mode -eq "global") {
        if (-not $env:USERPROFILE) {
            throw "USERPROFILE is not set."
        }
        $list += Resolve-InstallTarget -InputPath (Join-Path $env:USERPROFILE ".claude")
    }

    if ($Mode -eq "target") {
        $repoRoot = Get-GitRepoRoot
        $list += Resolve-InstallTarget -InputPath (Join-Path $repoRoot ".claude")
        if ($env:USERPROFILE) {
            $list += Resolve-InstallTarget -InputPath (Join-Path $env:USERPROFILE ".claude")
        }
    }

    if ($env:CLAUDE_INSTALL_ALLOWLIST) {
        $envPaths = $env:CLAUDE_INSTALL_ALLOWLIST -split ","
        foreach ($entry in $envPaths) {
            if ([string]::IsNullOrWhiteSpace($entry)) { continue }
            try {
                $list += Resolve-InstallTarget -InputPath (Get-CanonicalPath $entry)
            } catch {
                $list += Get-CanonicalPath $entry
            }
        }
    }

    return ($list | ForEach-Object { $_.ToLowerInvariant() } | Sort-Object -Unique)
}

function Assert-SafeInstallRoot {
    param([string]$Path, [string]$Mode)

    Test-PathNoReparseChain -Path $Path
    $target = Resolve-InstallTarget -InputPath $Path

    if ((Split-Path -Leaf $target).ToLowerInvariant() -ne ".claude") {
        throw "Target must resolve to a .claude directory."
    }

    Test-PathNoReparseChain -Path $target

    $allowlist = Get-AllowlistRoots -Mode $Mode
    if ($Mode -eq "target" -and -not $AllowUnsafeTarget -and $allowlist.Count -gt 0) {
        $normalized = $target.ToLowerInvariant()
        $isAllowed = $false
        foreach ($item in $allowlist) {
            if ($normalized -eq $item) {
                $isAllowed = $true
                break
            }
        }

        if (-not $isAllowed) {
            if (Test-Interactive) {
                Write-Host "WARNING: target '$target' is outside the default allowlist. Suspicious paths are blocked." -ForegroundColor Yellow
                while ($true) {
                    $rawAnswer = Read-Host "Type 'ALLOW' to proceed with this target"
                    $answer = if ($null -eq $rawAnswer) { "" } else { $rawAnswer.Trim() }
                    if ($answer.ToUpperInvariant() -eq "ALLOW") {
                        break
                    }
                    if ($answer -eq "") {
                        throw "Install cancelled: unsafe target denied."
                    }
                    Write-Host "Please type ALLOW to confirm, or press Enter to cancel." -ForegroundColor Yellow
                }
            } else {
                throw "Unsafe target denied for non-interactive install. Use -AllowUnsafeTarget to override."
            }
        }
    }

    return $target
}

function Read-InstallMode {
    Write-Host ""
    Write-Host "Select installation target:"
    Write-Host "  1) Local repo (.claude/)"
    Write-Host "  2) Global (~/.claude/)"
    Write-Host "  3) Custom target directory"
    Write-Host "  4) Abort"

    while ($true) {
        $choice = Read-Host "Choose [1-4, default: 1]"
        if ([string]::IsNullOrWhiteSpace($choice)) {
            $choice = "1"
        }
        switch ($choice.Trim()) {
            "1" {
                $script:PromptMode = "repo"
                return (Join-Path (Get-GitRepoRoot) ".claude")
            }
            "2" {
                $script:PromptMode = "global"
                if ($env:USERPROFILE) {
                    return (Join-Path $env:USERPROFILE ".claude")
                }
                Write-Host "FAIL: USERPROFILE is not set." -ForegroundColor Red
                throw "Cannot resolve global install path."
            }
            "3" {
                $script:PromptMode = "target"
                $custom = Read-Host "Enter target directory path"
                if ([string]::IsNullOrWhiteSpace($custom)) {
                    Write-Host "Target cannot be empty." -ForegroundColor Yellow
                    continue
                }
                return $custom
            }
            "4" {
                Write-Host "Install aborted by user." -ForegroundColor Yellow
                exit 1
            }
            default {
                Write-Host "Please enter 1, 2, 3, or 4." -ForegroundColor Yellow
            }
        }
    }
}

# Per-item install preserves user-added files — no destructive directory wipe needed.

function Get-DirectoryFileHashes {
    param([string]$Root)

    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd([char[]]@('\', '/'))
    $hashes = @{}
    foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File -Force | Sort-Object FullName) {
        $fullName = [System.IO.Path]::GetFullPath($file.FullName)
        $relative = $fullName.Substring($rootFull.Length).TrimStart([char[]]@('\', '/'))
        $hashes[$relative] = (Get-FileHash -Algorithm SHA256 -LiteralPath $fullName).Hash
    }
    return $hashes
}

function Test-DirectoryContentEqual {
    param(
        [string]$SourceDir,
        [string]$TargetDir
    )

    if (-not (Test-Path -LiteralPath $TargetDir -PathType Container)) {
        return $false
    }

    $sourceHashes = Get-DirectoryFileHashes -Root $SourceDir
    $targetHashes = Get-DirectoryFileHashes -Root $TargetDir
    if ($sourceHashes.Count -ne $targetHashes.Count) {
        return $false
    }

    foreach ($key in $sourceHashes.Keys) {
        if (-not $targetHashes.ContainsKey($key)) {
            return $false
        }
        if ($sourceHashes[$key] -ne $targetHashes[$key]) {
            return $false
        }
    }

    return $true
}

function Test-FileContentEqual {
    param(
        [string]$SourceFile,
        [string]$TargetFile
    )

    if (-not (Test-Path -LiteralPath $TargetFile -PathType Leaf)) {
        return $false
    }

    $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceFile).Hash
    $targetHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $TargetFile).Hash
    return $sourceHash -eq $targetHash
}

function Install-PackDirectoryItem {
    param(
        [string]$SourceDir,
        [string]$TargetDir,
        [string]$Label
    )

    if (Test-Path -LiteralPath $TargetDir) {
        if (Test-DirectoryContentEqual -SourceDir $SourceDir -TargetDir $TargetDir) {
            Write-Host "    OK  $Label unchanged"
            return
        }

        if (-not $DryRun) {
            Remove-Item -Recurse -Force $TargetDir
            Copy-Item -Recurse -Force $SourceDir $TargetDir
        } else {
            Write-Host "    [dry-run] would replace $Label"
        }
    } else {
        if (-not $DryRun) {
            Copy-Item -Recurse -Force $SourceDir $TargetDir
        } else {
            Write-Host "    [dry-run] would install $Label"
        }
    }
}

function Install-PackFileItem {
    param(
        [string]$SourceFile,
        [string]$TargetFile,
        [string]$Label
    )

    if (Test-Path -LiteralPath $TargetFile) {
        if (Test-FileContentEqual -SourceFile $SourceFile -TargetFile $TargetFile) {
            Write-Host "    OK  $Label unchanged"
            return
        }

        if (-not $DryRun) {
            Copy-Item -Force $SourceFile $TargetFile
        } else {
            Write-Host "    [dry-run] would replace $Label"
        }
    } else {
        if (-not $DryRun) {
            Copy-Item -Force $SourceFile $TargetFile
        } else {
            Write-Host "    [dry-run] would install $Label"
        }
    }
}

function Remove-DanglingLink {
    param(
        [string]$Path,
        [string]$Label
    )

    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($null -ne $item -and (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) -and -not (Test-Path -LiteralPath $Path)) {
        Write-Host "  Removing dangling symlink for $Label..."
        if ($DryRun) {
            Write-Host "    [dry-run] would remove dangling symlink $Path"
        } else {
            Remove-Item -LiteralPath $Path -Force
        }
    }
}

function Migrate-LegacyAgentsModeFile {
    param(
        [string]$LegacyFile,
        [string]$TargetFile,
        [string]$Label
    )

    Remove-DanglingLink -Path $LegacyFile -Label ("legacy {0}" -f $Label)
    Remove-DanglingLink -Path $TargetFile -Label $Label

    if (Test-Path -LiteralPath $TargetFile) {
        if (Test-Path -LiteralPath $LegacyFile) {
            Write-Host "  Canonical $Label already exists; leaving legacy file untouched: $LegacyFile"
        }
        return
    }

    if (-not (Test-Path -LiteralPath $LegacyFile)) {
        return
    }

    Write-Host "  Migrating legacy $Label to $TargetFile..."
    if (-not $DryRun) {
        Move-Item -LiteralPath $LegacyFile -Destination $TargetFile -Force
    } else {
        Write-Host "    [dry-run] would move $LegacyFile -> $TargetFile"
    }
}

function Get-PythonCommand {
    foreach ($name in @("python", "python3")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -ne $command) {
            return $command.Source
        }
    }
    return $null
}

function Sync-AgentsModeFile {
    param(
        [string]$TemplateFile,
        [string]$TargetFile,
        [string]$Label
    )

    Remove-DanglingLink -Path $TargetFile -Label $Label

    $normalizer = Join-Path $RepoDir "scripts\normalize-agents-mode.py"
    $python = Get-PythonCommand

    if ($null -ne $python -and (Test-Path -LiteralPath $normalizer)) {
        if (Test-Path -LiteralPath $TargetFile) {
            Write-Host "  Normalizing existing $Label to current canonical format..."
        } else {
            Write-Host "  Installing canonical $Label..."
        }

        if (-not $DryRun) {
            & $python $normalizer --template $TemplateFile --target $TargetFile --provider shared
            if ($LASTEXITCODE -ne 0) {
                throw "agents-mode normalization failed for $TargetFile"
            }
        } else {
            Write-Host "    [dry-run] would normalize $TargetFile"
        }
        return
    }

    if (Test-Path -LiteralPath $TargetFile) {
        throw "Python is required to normalize existing $Label at $TargetFile."
    }

    Write-Host "  Installing canonical $Label..."
    if (-not $DryRun) {
        Copy-Item -LiteralPath $TemplateFile -Destination $TargetFile -Force
    } else {
        Write-Host "    [dry-run] would create $TargetFile"
    }
}

function Get-PreservedClaudeImports {
    param(
        [string[]]$Lines,
        [int]$PackStart
    )

    $imports = @()
    if ($PackStart -lt 0 -or $PackStart -ge $Lines.Count) {
        return $imports
    }

    $collectImports = $false
    for ($i = $PackStart; $i -lt $Lines.Count; $i++) {
        $line = $Lines[$i]

        if (-not $collectImports) {
            if ($line -match "^@" -or [string]::IsNullOrWhiteSpace($line)) {
                $collectImports = $true
            } else {
                break
            }
        }

        if ($line -match "^@") {
            if ($line -ne "@AGENTS.md" -and $imports -notcontains $line) {
                $imports += $line
            }
            continue
        }

        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        break
    }

    return $imports
}

function Get-MergedClaudePackContent {
    param(
        [string[]]$ExistingLines,
        [int]$PackStart,
        [string]$SourcePath
    )

    $preservedPrefix = @()
    if ($PackStart -gt 0) {
        $preservedPrefix = $ExistingLines[0..($PackStart - 1)]
    }

    $preservedImports = Get-PreservedClaudeImports -Lines $ExistingLines -PackStart $PackStart
    $sourceLines = Get-Content $SourcePath
    $mergedPackLines = $sourceLines

    if ($sourceLines.Count -gt 0 -and $sourceLines[0] -eq "@AGENTS.md") {
        $tailStart = 1
        while ($tailStart -lt $sourceLines.Count -and [string]::IsNullOrWhiteSpace($sourceLines[$tailStart])) {
            $tailStart++
        }

        $tailLines = @()
        if ($tailStart -lt $sourceLines.Count) {
            $tailLines = $sourceLines[$tailStart..($sourceLines.Count - 1)]
        }

        $mergedPackLines = @($sourceLines[0])
        if ($preservedImports.Count -gt 0) {
            $mergedPackLines += $preservedImports
        }
        if ($tailLines.Count -gt 0) {
            $mergedPackLines += ""
            $mergedPackLines += $tailLines
        }
    }

    $finalLines = @()
    if ($preservedPrefix.Count -gt 0) {
        $finalLines += $preservedPrefix
    }
    $finalLines += $mergedPackLines

    return ($finalLines -join "`n")
}

# Determine target
if ($Global) {
    $repoRoot = Get-GitRepoRoot
    try {
        $TargetRoot = Assert-SafeInstallRoot -Path (Join-Path $env:USERPROFILE ".claude") -Mode "global"
    } catch {
        Write-Host "FAIL: Cannot resolve global target: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
    $Mode = "global"
} elseif ($Target) {
    try {
        $TargetRoot = Assert-SafeInstallRoot -Path $Target -Mode "target"
    } catch {
        Write-Host "FAIL: Cannot resolve target '$Target': $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
    $Mode = "target"
} else {
    if (Test-Interactive) {
        $interactiveTarget = Read-InstallMode
        $Mode = $script:PromptMode
        if (-not $Mode) {
            $Mode = "repo"
        }
        try {
            $TargetRoot = Assert-SafeInstallRoot -Path $interactiveTarget -Mode $Mode
        } catch {
            Write-Host "FAIL: Cannot resolve target: $($_.Exception.Message)" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "FAIL: No install target specified and not running interactively." -ForegroundColor Red
        Write-Host "Use: .\scripts\install-claude.ps1 -Global  or  .\scripts\install-claude.ps1 -Target <path>" -ForegroundColor Yellow
        exit 1
    }
}

if ($Mode -eq "global") {
    $ProjectRoot = $null
} else {
    $ProjectRoot = Split-Path $TargetRoot -Parent
}
$AgentsModeTarget = Join-Path $TargetRoot ".agents-mode.yaml"
$LegacyAgentsModeTarget = Join-Path $TargetRoot ".agents-mode"

Write-Host "=== Claude Code Installer ===" -ForegroundColor Cyan
Write-Host "Source: $Source"
Write-Host "Target: $TargetRoot"
Write-Host "agents-mode: $AgentsModeTarget"
Write-Host "Mode:   $Mode"
if ($DryRun) {
    Write-Host "Mode:   dry-run" -ForegroundColor Yellow
}
Write-Host ""

# Verify source
if (-not (Test-Path (Join-Path $Source "agents"))) {
    Write-Host "FAIL: Source directory $Source\agents not found." -ForegroundColor Red
    Write-Host "Run this script from the Orchestrarium repo root."
    exit 1
}
if (-not (Test-Path -LiteralPath $DefaultAgentsModeSource)) {
    Write-Host "FAIL: Missing default agents-mode template at $DefaultAgentsModeSource." -ForegroundColor Red
    exit 1
}

if (-not $NoHypothesisHook -and [string]::IsNullOrEmpty($env:ORCHESTRARIUM_NO_HYPOTHESIS_HOOK)) {
    $HookInstaller = Join-Path $RepoDir "scripts\install-hypothesis-hook.py"
    if (Test-Path -LiteralPath $HookInstaller -PathType Leaf) {
        $PythonCmd = Get-PythonCommand
        if (-not $PythonCmd) {
            Write-Error "python or python3 is required to preflight structural-hook installation."
            exit 1
        }
        $SettingsTarget = Join-Path $TargetRoot "settings.json"
        function Invoke-TestHookTransactionPreflight {
            & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --repo-root $RepoDir --test-install-scope $Mode --test-transaction-preflight
            if ($LASTEXITCODE -ne 0) {
                [Console]::Error.WriteLine("hook transaction test preflight exited with code $LASTEXITCODE")
                exit $LASTEXITCODE
            }
        }
        Invoke-TestHookTransactionPreflight
    }
}

if (-not $DryRun -and -not (Test-Path -LiteralPath $TargetRoot)) {
    New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
}
if ($DryRun -and -not (Test-Path -LiteralPath $TargetRoot)) {
    Write-Host "[dry-run] would create target root: $TargetRoot"
}

# Count and confirm reinstall
if (-not $Force -and -not $DryRun -and (Test-Interactive)) {
    $existingTotal = 0
    $packTotal = 0
    foreach ($dir in $Dirs) {
        $dst = Join-Path $TargetRoot $dir
        $src = Join-Path $Source $dir
        # Count top-level entries (files AND subdirectories) — these are exactly the
        # "pack items" the install loop below replaces. Matches install-claude.sh's
        # `-e` count over `"$dst"/*` so .sh and .ps1 report the same totals for
        # identical trees. No -Force: the bash `*` glob skips dotfiles, so we skip
        # hidden entries too rather than diverge in the other direction.
        if (Test-Path -LiteralPath $dst) {
            $existingTotal += @(Get-ChildItem -LiteralPath $dst -ErrorAction SilentlyContinue).Count
        }
        $packTotal += @(Get-ChildItem -LiteralPath $src -ErrorAction SilentlyContinue).Count
    }
    if ($existingTotal -gt 0) {
        $userCount = $existingTotal - $packTotal
        if ($userCount -lt 0) { $userCount = 0 }
        Write-Host ""
        Write-Host "  Reinstall will replace $packTotal pack items. $userCount user item(s) will be preserved."
        $confirmed = $false
        while (-not $confirmed) {
            $rawAnswer = Read-Host "  Proceed? [y/N]"
            $answer = if ($null -eq $rawAnswer) { "" } else { $rawAnswer.Trim().ToLower() }
            switch -Regex ($answer) {
                "^(y|yes)$" { $confirmed = $true }
                "^n$|^no$|^$" { Write-Host "Install cancelled by user." -ForegroundColor Yellow; exit 1 }
                default { Write-Host "  Please answer y or n." }
            }
        }
    }
}

# Per-item install: replace pack items, preserve user-added files
foreach ($dir in $Dirs) {
    $src = Join-Path $Source $dir
    $dst = Join-Path $TargetRoot $dir

    Write-Host "  Installing $dir\ (per-item, preserving user-added files)..."
    if (-not (Test-Path -LiteralPath $dst)) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path $dst -Force | Out-Null
        } else {
            Write-Host "    [dry-run] would create $dst"
        }
    }

    # Copy subdirectories (contracts/, team-templates/, scripts/) — full replace
    foreach ($sub in Get-ChildItem -LiteralPath $src -Directory -ErrorAction SilentlyContinue) {
        $subDst = Join-Path $dst $sub.Name
        Install-PackDirectoryItem -SourceDir $sub.FullName -TargetDir $subDst -Label "$dir/$($sub.Name)/"
    }

    # Copy individual files — per-file, preserve user files
    $packItems = @()
    foreach ($item in Get-ChildItem -LiteralPath $src -File -ErrorAction SilentlyContinue) {
        $packItems += $item.Name
        $itemDst = Join-Path $dst $item.Name
        Install-PackFileItem -SourceFile $item.FullName -TargetFile $itemDst -Label "$dir/$($item.Name)"
    }

    # Report preserved user files
    foreach ($existing in Get-ChildItem -LiteralPath $dst -File -ErrorAction SilentlyContinue) {
        if ($packItems -notcontains $existing.Name) {
            Write-Host "  Preserved user file: $dir/$($existing.Name)"
        }
    }

    # Reclaim the reserved `agents-` pack namespace (parity with install-claude.sh):
    # a target commands/agents-*.md file or a skills/agents-*/ dir not in the
    # current pack is a stale pack-owned artifact (renamed/removed flow, or a
    # generated agents-* skill from an old standalone-branch install — the
    # monorepo path ships flows only as commands/). Remove it. Non-namespaced
    # user files are preserved; the prefix is the ownership marker.
    if ($dir -eq "commands" -or $dir -eq "skills") {
        foreach ($existing in Get-ChildItem -LiteralPath $dst -Filter "agents-*" -ErrorAction SilentlyContinue) {
            $srcCounterpart = Join-Path $src $existing.Name
            if (Test-Path -LiteralPath $srcCounterpart) { continue }
            if ($DryRun) {
                Write-Host "    [dry-run] would reclaim stale pack namespace: $dir/$($existing.Name)"
            } else {
                Remove-Item -LiteralPath $existing.FullName -Recurse -Force
                Write-Host "  Reclaimed stale pack item: $dir/$($existing.Name)"
            }
        }
    }
}

$RuntimeLedgerScripts = @(
    "agent-run-ledger.py",
    "agent-run-ledger.ps1",
    "agent-run-ledger.sh",
    "check-work-items-state.py",
    "check-work-items-state.ps1",
    "check-work-items-state.sh",
    "validate-work-item-state.py",
    "validate-work-item-state.ps1",
    "validate-work-item-state.sh"
)
$ClaudeScriptsTarget = Join-Path $TargetRoot "agents\scripts"
Write-Host "  Installing work-item ledger helper scripts..."
if (-not (Test-Path -LiteralPath $ClaudeScriptsTarget)) {
    if (-not $DryRun) {
        New-Item -ItemType Directory -Path $ClaudeScriptsTarget -Force | Out-Null
    } else {
        Write-Host "    [dry-run] would create $ClaudeScriptsTarget"
    }
}
foreach ($scriptName in $RuntimeLedgerScripts) {
    $scriptSource = Join-Path (Join-Path $RepoDir "scripts") $scriptName
    $scriptTarget = Join-Path $ClaudeScriptsTarget $scriptName
    if (-not (Test-Path -LiteralPath $scriptSource)) {
        Write-Host "FAIL: Missing runtime helper source $scriptSource" -ForegroundColor Red
        exit 1
    }
    if (-not $DryRun) {
        Copy-Item -LiteralPath $scriptSource -Destination $scriptTarget -Force
    } else {
        Write-Host "    [dry-run] would copy $scriptSource -> $scriptTarget"
    }
}

# CLAUDE.md merge
$srcMd = Join-Path $Source "CLAUDE.md"
$dstMd = Join-Path $TargetRoot "CLAUDE.md"

Remove-DanglingLink -Path $dstMd -Label "CLAUDE.md"

if (Test-Path $dstMd) {
    $content = Get-Content $dstMd -Raw
    $lines = Get-Content $dstMd
    # Find pack section start: @AGENTS.md, # Claude Code Pack, or legacy # Claudestrator
    $packStart = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^@AGENTS\.md" -or $lines[$i] -match "^# Claude Code Pack" -or $lines[$i] -match "^# Claudestrator") {
            $packStart = $i
            break
        }
    }
    if ($packStart -ge 0) {
        Write-Host "  CLAUDE.md: replacing Claude Code pack section..."
        if ($packStart -gt 0) {
            # Preserve user content before pack section and merge user-side imports from the pack header block.
            $newContent = Get-MergedClaudePackContent -ExistingLines $lines -PackStart $packStart -SourcePath $srcMd
            if (-not $DryRun) {
                Set-Content -Path $dstMd -Value $newContent -NoNewline
            } else {
                Write-Host "    [dry-run] would replace Claude Code pack section in CLAUDE.md"
            }
        } else {
            if (-not $DryRun) {
                $newContent = Get-MergedClaudePackContent -ExistingLines $lines -PackStart $packStart -SourcePath $srcMd
                Set-Content -Path $dstMd -Value $newContent -NoNewline
            } else {
                Write-Host "    [dry-run] would replace CLAUDE.md"
            }
        }
    } elseif ($content -match "## Delegation rule") {
        Write-Host "  CLAUDE.md: full replace (has delegation rule but no recognized pack header)..."
        if (-not $DryRun) {
            Copy-Item -Force $srcMd $dstMd
        } else {
            Write-Host "    [dry-run] would replace CLAUDE.md"
        }
    } else {
        Write-Host "  CLAUDE.md: prepending Claude Code pack content..."
        $existing = Get-Content $dstMd -Raw
        $new = Get-Content $srcMd -Raw
        if (-not $DryRun) {
            Set-Content -Path $dstMd -Value ($new + "`n" + $existing) -NoNewline
        } else {
            Write-Host "    [dry-run] would prepend CLAUDE.md"
        }
    }
} else {
    Write-Host "  Creating CLAUDE.md..."
    if (-not $DryRun) {
        Copy-Item -Force $srcMd $dstMd
    } else {
        Write-Host "    [dry-run] would create CLAUDE.md"
    }
}

# AGENTS.md: copy or replace shared governance
$srcAgents = Join-Path (Join-Path $RepoDir "shared") "AGENTS.shared.md"
$dstAgents = Join-Path $TargetRoot "AGENTS.md"

Remove-DanglingLink -Path $dstAgents -Label "AGENTS.md"

if (Test-Path $srcAgents) {
    if (Test-Path $dstAgents) {
        $agentsContent = Get-Content $dstAgents -Raw
        if ($agentsContent -match "# Shared Governance") {
            Write-Host "  AGENTS.md: replacing shared governance..."
            if (-not $DryRun) {
                Copy-Item -Force $srcAgents $dstAgents
            } else {
                Write-Host "    [dry-run] would replace AGENTS.md"
            }
        } else {
            Write-Host "  AGENTS.md: prepending shared governance..."
            if (-not $DryRun) {
                $existing = Get-Content $dstAgents -Raw
                $new = Get-Content $srcAgents -Raw
                Set-Content -Path $dstAgents -Value ($new + "`n" + $existing) -NoNewline
            } else {
                Write-Host "    [dry-run] would prepend AGENTS.md"
            }
        }
    } else {
        Write-Host "  Creating AGENTS.md..."
        if (-not $DryRun) {
            Copy-Item -Force $srcAgents $dstAgents
        } else {
            Write-Host "    [dry-run] would create AGENTS.md"
        }
    }
}


Migrate-LegacyAgentsModeFile -LegacyFile $LegacyAgentsModeTarget -TargetFile $AgentsModeTarget -Label ".agents-mode.yaml"
Sync-AgentsModeFile -TemplateFile $DefaultAgentsModeSource -TargetFile $AgentsModeTarget -Label ".agents-mode.yaml"

# Shared cross-pack global .agents-mode.yaml lives at $HOME/.agents-mode.yaml
# (alongside ~/.claude.json). Lowest-precedence fallback layer below pack-local
# globals and project-local overlays. Sync is normalize-not-overwrite, so calling
# from both pack installers is idempotent. Only created/normalized during global installs.
if ($Mode -eq "global") {
    $SharedGlobalAgentsMode = Join-Path $HOME ".agents-mode.yaml"
    Sync-AgentsModeFile -TemplateFile $DefaultAgentsModeSource -TargetFile $SharedGlobalAgentsMode -Label "shared global ~/.agents-mode.yaml"
}

# Install structural hooks by merging them into the
# user's settings.json idempotently. Preserves all other user keys and other
# hooks. Opt out with -NoHypothesisHook or ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1.
# Fails closed (non-zero exit) if Python is required but unavailable.
if (-not $NoHypothesisHook -and -not $DryRun -and [string]::IsNullOrEmpty($env:ORCHESTRARIUM_NO_HYPOTHESIS_HOOK)) {
    $HookInstaller = Join-Path $RepoDir "scripts\install-hypothesis-hook.py"
    if (-not (Test-Path $HookInstaller)) {
        Write-Warning "hypothesis-hook installer not found at $HookInstaller; skipping hook install"
    } else {
        $PythonCmd = Get-PythonCommand
        if (-not $PythonCmd) {
            Write-Error "python or python3 is required to auto-install the structural hooks. Rerun with -NoHypothesisHook to skip, or install Python and re-run."
            exit 1
        }
        $SettingsTarget = Join-Path $TargetRoot "settings.json"
        # HookTarget resolution is centralized in install-hypothesis-hook.py.
        # The installer supplies the installed Python brain; wrapper/native
        # rollback profiles derive their own stage-specific target there.
        $BugfixScriptTarget = Join-Path $TargetRoot "agents\scripts\check-bugfix-discipline.py"
        $GitPushGateScriptTarget = Join-Path $TargetRoot "agents\scripts\check-git-push-gate.py"
        $StopScriptTarget = Join-Path $TargetRoot "agents\scripts\check-passive-polling-stop.py"
        $WiArchivalScriptTarget = Join-Path $TargetRoot "agents\scripts\check-work-items-archival-stop.py"
        $MachinePathScriptTarget = Join-Path $TargetRoot "agents\hooks\check-machine-local-path.py"
        $NoTrashScriptTarget = Join-Path $TargetRoot "agents\hooks\check-no-trash-in-repo.py"
        $StaleRelationScriptTarget = Join-Path $TargetRoot "agents\hooks\check-stale-relation-residue.py"
        $RepositoryOrientationScriptTarget = Join-Path $TargetRoot "agents\hooks\check-repository-orientation.py"
        $McpMomentumScriptTarget = Join-Path $TargetRoot "agents\hooks\check-mcp-momentum.py"
        $TypedRoutingScriptTarget = Join-Path $TargetRoot "agents\hooks\check-typed-routing.py"
        $ReminderScriptTarget = Join-Path $TargetRoot "agents\scripts\mcp-usage-reminder.py"
        $AgentsModeReminderScriptTarget = Join-Path $TargetRoot "agents\scripts\agents-mode-reminder.py"
        $ScratchValuablesScriptTarget = Join-Path $TargetRoot "agents\scripts\check-scratch-valuables.py"
        $TurnAnchorReminderScriptTarget = Join-Path $TargetRoot "agents\scripts\turn-anchor-reminder.py"
        $HookTargets = @(
            $BugfixScriptTarget,
            $GitPushGateScriptTarget,
            $StopScriptTarget,
            $WiArchivalScriptTarget,
            $MachinePathScriptTarget,
            $NoTrashScriptTarget,
            $StaleRelationScriptTarget,
            $RepositoryOrientationScriptTarget,
            $McpMomentumScriptTarget,
            $TypedRoutingScriptTarget,
            $ReminderScriptTarget,
            $AgentsModeReminderScriptTarget,
            $ScratchValuablesScriptTarget,
            $TurnAnchorReminderScriptTarget
        )
        function Invoke-TestHookTransactionCheckpoint([string]$Stage) {
            & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --repo-root $RepoDir --test-install-scope $Mode --test-transaction-checkpoint $Stage
            if ($LASTEXITCODE -ne 0) {
                [Console]::Error.WriteLine("hook transaction test checkpoint exited with code $LASTEXITCODE")
                exit $LASTEXITCODE
            }
        }
        foreach ($HookTargetPath in $HookTargets) {
            & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --script-path $HookTargetPath --validate-only
            if ($LASTEXITCODE -ne 0) {
                Write-Error "hook target preflight failed with code $LASTEXITCODE"
                exit $LASTEXITCODE
            }
        }
        Invoke-TestHookTransactionCheckpoint "sync"
        Write-Host "  Installing bugfix-discipline PreToolUse hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --script-path $BugfixScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing git-push publication-gate PreToolUse hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --script-marker check-git-push-gate --tool-matcher "Bash|PowerShell" --script-path $GitPushGateScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing passive-polling Stop hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --hook-event Stop --script-marker check-passive-polling-stop --script-path $StopScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing work-items-archival Stop hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --hook-event Stop --script-marker check-work-items-archival-stop --script-path $WiArchivalScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing machine-local-path PreToolUse hook [AUDIT] (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --script-marker check-machine-local-path --script-path $MachinePathScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing no-trash-in-repo PreToolUse hook [AUDIT] (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --script-marker check-no-trash-in-repo --tool-matcher "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell" --script-path $NoTrashScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing stale-relation-residue PreToolUse hook [AUDIT] (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --script-marker check-stale-relation-residue --script-path $StaleRelationScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing repository-orientation PreToolUse hook [AUDIT] (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --script-marker check-repository-orientation --tool-matcher "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell|shell_command|exec_command" --script-path $RepositoryOrientationScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing mcp-momentum PreToolUse hook [AUDIT] (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --script-marker check-mcp-momentum --tool-matcher "Grep|Bash|PowerShell|shell_command|exec_command" --script-path $McpMomentumScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing typed-routing PreToolUse hook [AUDIT] (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --script-marker check-typed-routing --tool-matcher "Agent" --script-path $TypedRoutingScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing MCP-usage-reminder SessionStart hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --hook-event SessionStart --script-marker mcp-usage-reminder --script-path $ReminderScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing delegation-posture (agents-mode) SessionStart hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --hook-event SessionStart --script-marker agents-mode-reminder --script-path $AgentsModeReminderScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing scratch-valuables watchdog SessionStart hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --hook-event SessionStart --script-marker check-scratch-valuables --script-path $ScratchValuablesScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing turn-anchor-reminder UserPromptSubmit hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --hook-runtime $HookRuntime --target $SettingsTarget --platform claude --host-os windows --hook-event UserPromptSubmit --script-marker turn-anchor-reminder --script-path $TurnAnchorReminderScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Invoke-TestHookTransactionCheckpoint "register"
        $HookHealthChecker = Join-Path $RepoDir "scripts\check-hook-health.py"
        if (-not (Test-Path -LiteralPath $HookHealthChecker -PathType Leaf)) {
            Write-Error "hook health checker not found at $HookHealthChecker"
            exit 1
        }
        Write-Host "  Verifying registered hook targets before reclaiming wrappers..."
        & $PythonCmd $HookHealthChecker --target $SettingsTarget --platform claude --host-os windows --repo-root $RepoDir
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hook target verification failed with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        $ExcludedSourceFiles = & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --hook-runtime $HookRuntime --repo-root $RepoDir --print-verification-exclusions
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hook verification exclusion resolution failed with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        foreach ($ExcludedSourceFile in @($ExcludedSourceFiles)) {
            if (-not [string]::IsNullOrWhiteSpace($ExcludedSourceFile)) {
                [void]$HookVerificationExclusions.Add(
                    $ExcludedSourceFile.Trim().Replace("\", "/")
                )
            }
        }
        Invoke-TestHookTransactionCheckpoint "verify"
        Write-Host "  Reclaiming owned installed hook wrappers after verification..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --reclaim-root (Join-Path $TargetRoot "agents") --repo-root $RepoDir --test-install-scope $Mode
        if ($LASTEXITCODE -ne 0) {
            $HookReclaimExitCode = $LASTEXITCODE
            [Console]::Error.WriteLine("hook wrapper reclaim failed with code $HookReclaimExitCode")
            exit $HookReclaimExitCode
        }
    }
}

if ($DryRun) {
    if (-not $NoHypothesisHook -and [string]::IsNullOrEmpty($env:ORCHESTRARIUM_NO_HYPOTHESIS_HOOK)) {
        $PythonCmd = Get-PythonCommand
        if (-not $PythonCmd) {
            Write-Error "python or python3 is required to preview structural hook installation."
            exit 1
        }
        $HookInstaller = Join-Path $RepoDir "scripts\install-hypothesis-hook.py"
        & $PythonCmd $HookInstaller `
            --target (Join-Path $TargetRoot "settings.json") `
            --platform claude `
            --host-os windows `
            --hook-runtime $HookRuntime `
            --script-path (Join-Path $Source "agents\scripts\check-bugfix-discipline.py") `
            --reclaim-root (Join-Path $TargetRoot "agents") `
            --repo-root $RepoDir `
            --test-install-scope $Mode `
            --preview-reclaim `
            --dry-run
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    Write-Host ""
    Write-Host "RESULT: DRY-RUN complete (no files modified)."
    exit 0
}

# Verification — explicit required-file manifest check
Write-Host ""
Write-Host "=== Verification ===" -ForegroundColor Cyan
$errors = 0

function Test-InstalledFile($path, $label) {
    if (Test-Path $path) {
        Write-Host "  OK  $label" -ForegroundColor Green
    } else {
        Write-Host "  FAIL  $label" -ForegroundColor Red
        $script:errors++
    }
}

function Get-SourceFiles($DirRoot) {
    $sourceDir = Join-Path $Source $DirRoot
    $items = @()
    foreach ($item in Get-ChildItem -LiteralPath $sourceDir -Recurse -File) {
        $relative = $item.FullName.Substring($sourceDir.Length)
        $relative = $relative.TrimStart("\\")
        $items += (Join-Path $DirRoot $relative)
    }
    return $items
}

function Test-SourceFileRequiredForProfile($RelativePath) {
    return -not $HookVerificationExclusions.Contains(
        $RelativePath.Replace("\", "/")
    )
}

foreach ($dir in $Dirs) {
    Write-Host "Verifying $dir/ files..."
    foreach ($relative in Get-SourceFiles $dir) {
        if (Test-SourceFileRequiredForProfile $relative) {
            Test-InstalledFile (Join-Path $TargetRoot $relative) $relative
        } else {
            Write-Host "  OK  $relative (intentionally reclaimed for hook-runtime=$HookRuntime)" -ForegroundColor Green
        }
    }
}

# Explicit contract/script requirements
Test-InstalledFile (Join-Path $TargetRoot "agents/contracts/operating-model.md") "agents/contracts/operating-model.md"
Test-InstalledFile (Join-Path $TargetRoot "agents/contracts/subagent-contracts.md") "agents/contracts/subagent-contracts.md"
Test-InstalledFile (Join-Path $TargetRoot "agents/contracts/policies-catalog.md") "agents/contracts/policies-catalog.md"
foreach ($scriptName in $RuntimeLedgerScripts) {
    Test-InstalledFile (Join-Path $TargetRoot "agents/scripts/$scriptName") "agents/scripts/$scriptName"
}
Test-InstalledFile $AgentsModeTarget ".agents-mode.yaml"

# Check CLAUDE.md (Claude-specific sections)
if (Test-Path $dstMd) {
    $mdContent = Get-Content $dstMd -Raw
    $lineCount = (Get-Content $dstMd).Count
    Write-Host "  OK  CLAUDE.md ($lineCount lines)" -ForegroundColor Green
    foreach ($section in @("## Delegation rule", "## Publication safety")) {
        if ($mdContent -match [regex]::Escape($section)) {
            Write-Host "  OK  CLAUDE.md has '$section'" -ForegroundColor Green
        } else {
            Write-Host "  FAIL  CLAUDE.md missing '$section'" -ForegroundColor Red
            $errors++
        }
    }
    if ($mdContent -match "@AGENTS\.md") {
        Write-Host "  OK  CLAUDE.md imports @AGENTS.md" -ForegroundColor Green
    } else {
        Write-Host "  FAIL  CLAUDE.md missing @AGENTS.md import" -ForegroundColor Red
        $errors++
    }
} else {
    Write-Host "  FAIL  CLAUDE.md missing" -ForegroundColor Red
    $errors++
}

# Check AGENTS.md (shared governance sections)
if (Test-Path $dstAgents) {
    $agentsContent = Get-Content $dstAgents -Raw
    $agentsLineCount = (Get-Content $dstAgents).Count
    Write-Host "  OK  AGENTS.md ($agentsLineCount lines)" -ForegroundColor Green
    foreach ($section in @("## Role index", "## Engineering hygiene", "## Core delegation principles", "## Publication safety")) {
        if ($agentsContent -match [regex]::Escape($section)) {
            Write-Host "  OK  AGENTS.md has '$section'" -ForegroundColor Green
        } else {
            Write-Host "  FAIL  AGENTS.md missing '$section'" -ForegroundColor Red
            $errors++
        }
    }
} else {
    Write-Host "  FAIL  AGENTS.md missing" -ForegroundColor Red
    $errors++
}

Write-Host ""
if ($errors -gt 0) {
    Write-Host "RESULT: FAIL ($errors errors)" -ForegroundColor Red
    exit 1
} else {
    Write-Host "RESULT: OK - Claude Code pack installed to $TargetRoot" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next: restart Claude, then run /agents-init-project to review/update project policies and the installed default .claude/.agents-mode.yaml."
}

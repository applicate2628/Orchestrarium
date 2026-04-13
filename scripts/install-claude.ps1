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
    [switch]$AllowUnsafeTarget
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $ScriptDir
$Source = Join-Path $RepoDir "src.claude"
$DefaultAgentsModeSource = Join-Path $RepoDir "shared\agents-mode.defaults.yaml"

$Dirs = @("agents", "commands")
$OptionalDirs = @("memory")
$script:PromptMode = $null

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

function Confirm-Removal {
    param([string]$Path)
    if ($Force -or $DryRun) {
        return $true
    }
    if (-not (Test-Interactive)) {
        Write-Host "Skipping interactive confirmation in non-console host." -ForegroundColor Yellow
        return $true
    }

    $name = Split-Path $Path -Leaf
    while ($true) {
        $rawAnswer = Read-Host "Delete existing '$name' at '$Path' before reinstall? [y/N]"
        $answer = if ($null -eq $rawAnswer) { "" } else { $rawAnswer.Trim().ToLower() }
        switch -Regex ($answer.Trim().ToLower()) {
            "^(y|yes)$" { return $true }
            "^n$|^no$|^$" { return $false }
            default { Write-Host "Please answer y or n." }
        }
    }
}

# Per-item install preserves user-added files — no destructive directory wipe needed.

function Copy-RequiredDirectory {
    param(
        [string]$SourceDir,
        [string]$TargetDir,
        [string]$Label
    )

    if (Test-Path -LiteralPath $TargetDir) {
        Write-Host "  Removing old $Label..."
        if (-not (Confirm-Removal $TargetDir)) {
            Write-Host "Install cancelled: existing directory not removed: $TargetDir" -ForegroundColor Red
            exit 1
        }
        if (-not $DryRun) {
            Remove-Item -Recurse -Force $TargetDir
        } else {
            Write-Host "    [dry-run] would remove $TargetDir"
        }
    }
    Write-Host "  Installing $Label..."
    if (-not $DryRun) {
        Copy-Item -Recurse -Force $SourceDir $TargetDir
    } else {
        Write-Host "    [dry-run] would copy $SourceDir -> $TargetDir"
    }
}

function Ensure-LocalOnlyGitignoreEntries {
    param([string]$ProjectRoot)

    $gitignore = Join-Path $ProjectRoot ".gitignore"
    $entries = @("/.reports/", "/work-items/")
    $existingLines = @()
    if (Test-Path -LiteralPath $gitignore) {
        $existingLines = Get-Content -LiteralPath $gitignore -ErrorAction SilentlyContinue
    }

    $missing = @()
    foreach ($entry in $entries) {
        $alternate = $entry.TrimStart("/")
        if ($existingLines -notcontains $entry -and $existingLines -notcontains $alternate) {
            $missing += $entry
        }
    }

    if ($missing.Count -eq 0) {
        Write-Host "  .gitignore: local-only entries already present"
        return
    }

    Write-Host "  Ensuring .gitignore ignores local-only task-memory paths..."
    if ($DryRun) {
        foreach ($entry in $missing) {
            if (Test-Path -LiteralPath $gitignore) {
                Write-Host "    [dry-run] would append '$entry' to $gitignore"
            } else {
                Write-Host "    [dry-run] would create $gitignore with '$entry'"
            }
        }
        return
    }

    if (-not (Test-Path -LiteralPath $gitignore)) {
        Set-Content -LiteralPath $gitignore -Value ($missing -join "`r`n")
        return
    }

    foreach ($entry in $missing) {
        Add-Content -LiteralPath $gitignore -Value "`r`n$entry"
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

function Ensure-DefaultFile {
    param(
        [string]$SourceFile,
        [string]$TargetFile,
        [string]$Label
    )

    Remove-DanglingLink -Path $TargetFile -Label $Label

    if (Test-Path -LiteralPath $TargetFile) {
        Write-Host "  Preserving existing $Label..."
        return
    }

    Write-Host "  Installing default $Label..."
    if (-not $DryRun) {
        Copy-Item -LiteralPath $SourceFile -Destination $TargetFile -Force
    } else {
        Write-Host "    [dry-run] would create $TargetFile"
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
        if (Test-Path -LiteralPath $dst) {
            $existingTotal += (Get-ChildItem -LiteralPath $dst -File -ErrorAction SilentlyContinue).Count
        }
        $packTotal += (Get-ChildItem -LiteralPath $src -File -ErrorAction SilentlyContinue).Count
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
        if (-not $DryRun) {
            if (Test-Path -LiteralPath $subDst) { Remove-Item -Recurse -Force $subDst }
            Copy-Item -Recurse -Force $sub.FullName $subDst
        } else {
            Write-Host "    [dry-run] would replace $dir/$($sub.Name)/"
        }
    }

    # Copy individual files — per-file, preserve user files
    $packItems = @()
    foreach ($item in Get-ChildItem -LiteralPath $src -File -ErrorAction SilentlyContinue) {
        $packItems += $item.Name
        $itemDst = Join-Path $dst $item.Name
        if (-not $DryRun) {
            Copy-Item -Force $item.FullName $itemDst
        } else {
            if (Test-Path -LiteralPath $itemDst) {
                Write-Host "    [dry-run] would replace $($item.Name)"
            } else {
                Write-Host "    [dry-run] would install $($item.Name)"
            }
        }
    }

    # Report preserved user files
    foreach ($existing in Get-ChildItem -LiteralPath $dst -File -ErrorAction SilentlyContinue) {
        if ($packItems -notcontains $existing.Name) {
            Write-Host "  Preserved user file: $dir/$($existing.Name)"
        }
    }
}

# Optional dirs: copy if not present, don't overwrite
foreach ($dir in $OptionalDirs) {
    $src = Join-Path $Source $dir
    $dst = Join-Path $TargetRoot $dir
    if (Test-Path $dst) {
        Write-Host "  Keeping existing $dir\ (optional, not overwritten)"
    } elseif (Test-Path $src) {
        Write-Host "  Installing $dir\ (optional)..."
        if (-not $DryRun) {
            Copy-Item -Recurse -Force $src $dst
        } else {
            Write-Host "    [dry-run] would copy $src -> $dst"
        }
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

if ($Mode -ne "global") {
    Ensure-LocalOnlyGitignoreEntries -ProjectRoot $ProjectRoot
}

Migrate-LegacyAgentsModeFile -LegacyFile $LegacyAgentsModeTarget -TargetFile $AgentsModeTarget -Label ".agents-mode.yaml"
Ensure-DefaultFile -SourceFile $DefaultAgentsModeSource -TargetFile $AgentsModeTarget -Label ".agents-mode.yaml"

if ($DryRun) {
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

foreach ($dir in $Dirs) {
    Write-Host "Verifying $dir/ files..."
    foreach ($relative in Get-SourceFiles $dir) {
        Test-InstalledFile (Join-Path $TargetRoot $relative) $relative
    }
}

# Explicit contract/script requirements
Test-InstalledFile (Join-Path $TargetRoot "agents/contracts/operating-model.md") "agents/contracts/operating-model.md"
Test-InstalledFile (Join-Path $TargetRoot "agents/contracts/subagent-contracts.md") "agents/contracts/subagent-contracts.md"
Test-InstalledFile (Join-Path $TargetRoot "agents/contracts/policies-catalog.md") "agents/contracts/policies-catalog.md"
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

<#
.SYNOPSIS
    Install Claudestrator skill-pack.
.DESCRIPTION
    Copies agents, commands, policies, scripts, and CLAUDE.md to the target location.
    Re-running = reinstall. Memory is preserved across reinstalls.
.EXAMPLE
    .\install.ps1                          # Install into current repo's .claude/
    .\install.ps1 -Global                  # Install into ~/.claude/
    .\install.ps1 -Target "D:\my-repo"     # Install into D:\my-repo\.claude/
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
$Source = Join-Path $ScriptDir "src.claude"

$Dirs = @("agents", "commands", "scripts")
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

function Confirm-DestructiveMode {
    param([string[]]$ExistingDirs)
    if ($Force -or $DryRun) {
        return
    }
    if (-not (Test-Interactive)) {
        return
    }

    if ($ExistingDirs.Count -eq 0) {
        return
    }

    Write-Host "Destructive install will remove existing directories:"
    foreach ($path in $ExistingDirs) {
        Write-Host "  - $path"
    }

    while ($true) {
        $rawAnswer = Read-Host "Proceed with destructive reinstall? [y/N]"
        $answer = if ($null -eq $rawAnswer) { "" } else { $rawAnswer.Trim().ToLower() }
        switch -Regex ($answer.Trim().ToLower()) {
            "^(y|yes)$" { return }
            "^n$|^no$|^$" { throw "Install cancelled by user." }
            default { Write-Host "Please answer y or n." }
        }
    }
}

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
        Write-Host "Use: .\install.ps1 -Global  or  .\install.ps1 -Target <path>" -ForegroundColor Yellow
        exit 1
    }
}

Write-Host "=== Claudestrator Installer ===" -ForegroundColor Cyan
Write-Host "Source: $Source"
Write-Host "Target: $TargetRoot"
Write-Host "Mode:   $Mode"
if ($DryRun) {
    Write-Host "Mode:   dry-run" -ForegroundColor Yellow
}
Write-Host ""

# Verify source
if (-not (Test-Path (Join-Path $Source "agents"))) {
    Write-Host "FAIL: Source directory $Source\agents not found." -ForegroundColor Red
    Write-Host "Run this script from the Claudestrator repo root."
    exit 1
}

$existingDirs = @()
foreach ($dir in $Dirs) {
    $dst = Join-Path $TargetRoot $dir
    if (Test-Path -LiteralPath $dst) {
        $existingDirs += $dst
    }
}

Confirm-DestructiveMode -ExistingDirs $existingDirs

if (-not $DryRun -and -not (Test-Path -LiteralPath $TargetRoot)) {
    New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
}
if ($DryRun -and -not (Test-Path -LiteralPath $TargetRoot)) {
    Write-Host "[dry-run] would create target root: $TargetRoot"
}

# Clean install: remove old, copy fresh
foreach ($dir in $Dirs) {
    $src = Join-Path $Source $dir
    $dst = Join-Path $TargetRoot $dir
    Copy-RequiredDirectory -SourceDir $src -TargetDir $dst -Label "$dir\"
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

if (Test-Path $dstMd) {
    $content = Get-Content $dstMd -Raw
    if ($content -match "## Delegation rule") {
        if ($content -match "(?m)^# Claudestrator") {
            # Extract content before "# Claudestrator", replace rest
            $lines = Get-Content $dstMd
            $idx = 0
            for ($i = 0; $i -lt $lines.Count; $i++) {
                if ($lines[$i] -match "^# Claudestrator") { $idx = $i; break }
            }
            if ($idx -gt 0) {
                Write-Host "  CLAUDE.md: replacing Claudestrator section..."
                $userContent = ($lines[0..($idx-1)] -join "`n") + "`n"
                $newContent = Get-Content $srcMd -Raw
                if (-not $DryRun) {
                    Set-Content -Path $dstMd -Value ($userContent + $newContent) -NoNewline
                } else {
                    Write-Host "    [dry-run] would replace Claudestrator section in CLAUDE.md"
                }
            } else {
                Write-Host "  CLAUDE.md: full replace..."
                if (-not $DryRun) {
                    Copy-Item -Force $srcMd $dstMd
                } else {
                    Write-Host "    [dry-run] would replace CLAUDE.md"
                }
            }
        } else {
            Write-Host "  CLAUDE.md: full replace..."
            if (-not $DryRun) {
                Copy-Item -Force $srcMd $dstMd
            } else {
                Write-Host "    [dry-run] would replace CLAUDE.md"
            }
        }
    } else {
        Write-Host "  CLAUDE.md: prepending Claudestrator content..."
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

if (Test-Path $dstMd) {
    $mdContent = Get-Content $dstMd -Raw
    $lineCount = (Get-Content $dstMd).Count
    Write-Host "  OK  CLAUDE.md ($lineCount lines)" -ForegroundColor Green
    foreach ($section in @("## Delegation rule", "## Role index", "## Engineering hygiene", "## Publication safety")) {
        if ($mdContent -match [regex]::Escape($section)) {
            Write-Host "  OK  CLAUDE.md has '$section'" -ForegroundColor Green
        } else {
            Write-Host "  FAIL  CLAUDE.md missing '$section'" -ForegroundColor Red
            $errors++
        }
    }
} else {
    Write-Host "  FAIL  CLAUDE.md missing" -ForegroundColor Red
    $errors++
}

Write-Host ""
if ($errors -gt 0) {
    Write-Host "RESULT: FAIL ($errors errors)" -ForegroundColor Red
    exit 1
} else {
    Write-Host "RESULT: OK - Claudestrator installed to $TargetRoot" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next: restart Claude, then run /agents-init-project to configure project policies."
}

<#
.SYNOPSIS
    Install Orchestrarium skill-pack.
.DESCRIPTION
    Copies the skills tree and AGENTS.md to the target location.
    Re-running = reinstall.
.EXAMPLE
    .\scripts\install-codex.ps1                          # Install into current repo (.agents/ + AGENTS.md)
    .\scripts\install-codex.ps1 -Global                  # Install into ~/.codex/
    .\scripts\install-codex.ps1 -Target "D:\my-repo"     # Install into D:\my-repo as a project (.agents/ + AGENTS.md)
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
$Source = Join-Path $RepoDir "src.codex"

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
    if ((Split-Path -Leaf $resolved).ToLowerInvariant() -eq ".codex") {
        return $resolved
    }
    return (Join-Path $resolved ".codex")
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
        $list += Resolve-InstallTarget -InputPath (Join-Path $repoRoot ".codex")
    }

    if ($Mode -eq "global") {
        if (-not $env:USERPROFILE) {
            throw "USERPROFILE is not set."
        }
        $list += Resolve-InstallTarget -InputPath (Join-Path $env:USERPROFILE ".codex")
    }

    if ($Mode -eq "target") {
        $repoRoot = Get-GitRepoRoot
        $list += Resolve-InstallTarget -InputPath (Join-Path $repoRoot ".codex")
        if ($env:USERPROFILE) {
            $list += Resolve-InstallTarget -InputPath (Join-Path $env:USERPROFILE ".codex")
        }
    }

    if ($env:CODEX_INSTALL_ALLOWLIST) {
        $envPaths = $env:CODEX_INSTALL_ALLOWLIST -split ","
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

    if ((Split-Path -Leaf $target).ToLowerInvariant() -ne ".codex") {
        throw "Target must resolve to a .codex directory."
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
    Write-Host "  1) Local repo (.agents/skills + root AGENTS.md)"
    Write-Host "  2) Global (~/.codex/)"
    Write-Host "  3) Custom project directory (.agents/skills + root AGENTS.md)"
    Write-Host "  4) Abort"

    while ($true) {
        $choice = Read-Host "Choose [1-4, default: 1]"
        if ([string]::IsNullOrWhiteSpace($choice)) {
            $choice = "1"
        }
        switch ($choice.Trim()) {
            "1" {
                $script:PromptMode = "repo"
                return (Join-Path (Get-GitRepoRoot) ".codex")
            }
            "2" {
                $script:PromptMode = "global"
                if ($env:USERPROFILE) {
                    return (Join-Path $env:USERPROFILE ".codex")
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

# Per-skill install preserves user-added skills — no destructive directory wipe needed.

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

function Ensure-ReportsGitignore {
    param([string]$ProjectRoot)

    $gitignore = Join-Path $ProjectRoot ".gitignore"
    if (Test-Path -LiteralPath $gitignore) {
        $existingLines = Get-Content -LiteralPath $gitignore -ErrorAction SilentlyContinue
        if ($existingLines -contains "/.reports/" -or $existingLines -contains ".reports/") {
            Write-Host "  .gitignore: /.reports/ already present"
            return
        }
    }

    Write-Host "  Ensuring .gitignore ignores /.reports/..."
    if ($DryRun) {
        if (Test-Path -LiteralPath $gitignore) {
            Write-Host "    [dry-run] would append '/.reports/' to $gitignore"
        } else {
            Write-Host "    [dry-run] would create $gitignore with '/.reports/'"
        }
        return
    }

    if (Test-Path -LiteralPath $gitignore) {
        Add-Content -LiteralPath $gitignore -Value "`r`n/.reports/"
    } else {
        Set-Content -LiteralPath $gitignore -Value "/.reports/"
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

# Determine target
if ($Global) {
    $repoRoot = Get-GitRepoRoot
    try {
        $TargetRoot = Assert-SafeInstallRoot -Path (Join-Path $env:USERPROFILE ".codex") -Mode "global"
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
        Write-Host "Use: .\scripts\install-codex.ps1 -Global  or  .\scripts\install-codex.ps1 -Target <path>" -ForegroundColor Yellow
        exit 1
    }
}

# Derive per-mode target paths.
# Global: everything goes into ~/.codex/ (mirrors src.codex/).
# Repo/target: skills go into .agents/skills/,
#              AGENTS.md merges into project root AGENTS.md.
if ($Mode -eq "global") {
    $SkillsTarget = Join-Path $TargetRoot "skills"
    $LeadScriptsTarget = Join-Path $TargetRoot "skills\lead\scripts"
    $MdTarget = Join-Path $TargetRoot "AGENTS.md"
} else {
    $ProjectRoot = Split-Path $TargetRoot -Parent
    $AgentsRoot = Join-Path $ProjectRoot ".agents"
    $SkillsTarget = Join-Path $AgentsRoot "skills"
    $LeadScriptsTarget = Join-Path $SkillsTarget "lead\scripts"
    $MdTarget = Join-Path $ProjectRoot "AGENTS.md"
}

Write-Host "=== Orchestrarium Installer ===" -ForegroundColor Cyan
Write-Host "Source: $Source"
Write-Host "Skills target: $SkillsTarget"
Write-Host "AGENTS.md target: $MdTarget"
Write-Host "Mode:   $Mode"
if ($DryRun) {
    Write-Host "Mode:   dry-run" -ForegroundColor Yellow
}
Write-Host ""

# Verify source
if (-not (Test-Path (Join-Path $Source "skills"))) {
    Write-Host "FAIL: Source directory $Source\skills not found." -ForegroundColor Red
    Write-Host "Run this script from the Orchestrarium repo root."
    exit 1
}

# Create parent directories as needed
foreach ($tdir in @($SkillsTarget)) {
    $parent = Split-Path $tdir -Parent
    if (-not (Test-Path -LiteralPath $parent)) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        } else {
            Write-Host "[dry-run] would create: $parent"
        }
    }
}

# Count and confirm reinstall
$packCount = (Get-ChildItem -LiteralPath (Join-Path $Source "skills") -Directory).Count
$existingCount = 0
if (Test-Path -LiteralPath $SkillsTarget) {
    $existingCount = (Get-ChildItem -LiteralPath $SkillsTarget -Directory -ErrorAction SilentlyContinue).Count
}
if ($existingCount -gt 0 -and -not $Force -and -not $DryRun -and (Test-Interactive)) {
    $userCount = $existingCount - $packCount
    if ($userCount -lt 0) { $userCount = 0 }
    Write-Host ""
    Write-Host "  Reinstall will replace $packCount pack skills. $userCount user skill(s) will be preserved."
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

# Per-skill install: only replace pack skills, preserve user-added skills
Write-Host "  Installing skills (per-skill, preserving user-added skills)..."
if (-not (Test-Path -LiteralPath $SkillsTarget)) {
    if (-not $DryRun) {
        New-Item -ItemType Directory -Path $SkillsTarget -Force | Out-Null
    } else {
        Write-Host "    [dry-run] would create $SkillsTarget"
    }
}

$packSkills = @()
foreach ($skillDir in Get-ChildItem -LiteralPath (Join-Path $Source "skills") -Directory) {
    $skillName = $skillDir.Name
    $packSkills += $skillName
    $dst = Join-Path $SkillsTarget $skillName
    if (Test-Path -LiteralPath $dst) {
        if (-not $DryRun) {
            Remove-Item -Recurse -Force $dst
            Copy-Item -Recurse -Force $skillDir.FullName $dst
        } else {
            Write-Host "    [dry-run] would replace skills/$skillName"
        }
    } else {
        if (-not $DryRun) {
            Copy-Item -Recurse -Force $skillDir.FullName $dst
        } else {
            Write-Host "    [dry-run] would install skills/$skillName"
        }
    }
}
Write-Host "  Installed $($packSkills.Count) pack skills."

# Report preserved user skills
if (Test-Path -LiteralPath $SkillsTarget) {
    foreach ($existingDir in Get-ChildItem -LiteralPath $SkillsTarget -Directory) {
        if ($packSkills -notcontains $existingDir.Name) {
            Write-Host "  Preserved user skill: $($existingDir.Name)"
        }
    }
}

# Scripts live inside skills/lead/scripts/ — installed automatically with the lead skill.

# AGENTS.md: assemble from shared + codex-specific, then merge or create
$srcShared = Join-Path (Join-Path $RepoDir "shared") "AGENTS.shared.md"
$srcPlatform = Join-Path $Source "AGENTS.codex.md"

if (-not (Test-Path $srcShared) -or -not (Test-Path $srcPlatform)) {
    Write-Host "FAIL: Missing $srcShared or $srcPlatform" -ForegroundColor Red
    exit 1
}

$srcMd = Join-Path $env:TEMP "orchestrarium-agents-assembled.md"
$sharedContent = Get-Content $srcShared -Raw
$platformContent = Get-Content $srcPlatform -Raw
Set-Content -Path $srcMd -Value ($sharedContent + "`n" + $platformContent) -NoNewline

$dstMd = $MdTarget

Remove-DanglingLink -Path $dstMd -Label "AGENTS.md"

if (Test-Path $dstMd) {
    $content = Get-Content $dstMd -Raw
    if ($content -match "## Template routing") {
        if ($content -match "(?m)^# Default Delegation Rule") {
            # Extract content before "# Default Delegation Rule", replace rest
            $lines = Get-Content $dstMd
            $idx = 0
            for ($i = 0; $i -lt $lines.Count; $i++) {
                if ($lines[$i] -match "^# Default Delegation Rule") { $idx = $i; break }
            }
            if ($idx -gt 0) {
                Write-Host "  AGENTS.md: replacing Orchestrarium section..."
                $userContent = ($lines[0..($idx-1)] -join "`n") + "`n"
                $newContent = Get-Content $srcMd -Raw
                if (-not $DryRun) {
                    Set-Content -Path $dstMd -Value ($userContent + $newContent) -NoNewline
                } else {
                    Write-Host "    [dry-run] would replace Orchestrarium section in AGENTS.md"
                }
            } else {
                Write-Host "  AGENTS.md: full replace..."
                if (-not $DryRun) {
                    Copy-Item -Force $srcMd $dstMd
                } else {
                    Write-Host "    [dry-run] would replace AGENTS.md"
                }
            }
        } else {
            Write-Host "  AGENTS.md: full replace..."
            if (-not $DryRun) {
                Copy-Item -Force $srcMd $dstMd
            } else {
                Write-Host "    [dry-run] would replace AGENTS.md"
            }
        }
    } else {
        Write-Host "  AGENTS.md: prepending Orchestrarium content..."
        $existing = Get-Content $dstMd -Raw
        $new = Get-Content $srcMd -Raw
        if (-not $DryRun) {
            Set-Content -Path $dstMd -Value ($new + "`n" + $existing) -NoNewline
        } else {
            Write-Host "    [dry-run] would prepend AGENTS.md"
        }
    }
} else {
    Write-Host "  Creating AGENTS.md..."
    if (-not $DryRun) {
        Copy-Item -Force $srcMd $dstMd
    } else {
        Write-Host "    [dry-run] would create AGENTS.md"
    }
}

if ($Mode -ne "global") {
    Ensure-ReportsGitignore -ProjectRoot $ProjectRoot
}

if ($DryRun) {
    Write-Host ""
    Write-Host "RESULT: DRY-RUN complete (no files modified)."
    exit 0
}

# Verification -- explicit required-file manifest check
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

# Verify all files in skills/
Write-Host "Verifying skills/ files..."
foreach ($relative in Get-SourceFiles "skills") {
    $relFile = $relative.Substring("skills\".Length)
    Test-InstalledFile (Join-Path $SkillsTarget $relFile) $relative
}

# Explicit contract requirements
Test-InstalledFile (Join-Path $SkillsTarget "lead/operating-model.md") "skills/lead/operating-model.md"
Test-InstalledFile (Join-Path $SkillsTarget "lead/subagent-contracts.md") "skills/lead/subagent-contracts.md"
Test-InstalledFile (Join-Path $LeadScriptsTarget "check-publication-safety.sh") "skills/lead/scripts/check-publication-safety.sh"
Test-InstalledFile (Join-Path $LeadScriptsTarget "check-publication-safety.ps1") "skills/lead/scripts/check-publication-safety.ps1"
Test-InstalledFile (Join-Path $LeadScriptsTarget "validate-skill-pack.sh") "skills/lead/scripts/validate-skill-pack.sh"

if (Test-Path $dstMd) {
    $mdContent = Get-Content $dstMd -Raw
    $lineCount = (Get-Content $dstMd).Count
    Write-Host "  OK  AGENTS.md ($lineCount lines)" -ForegroundColor Green
    foreach ($section in @("## Template routing", "## Role index", "## Engineering hygiene", "## Publication safety")) {
        if ($mdContent -match [regex]::Escape($section)) {
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
    Write-Host "RESULT: OK - Orchestrarium installed" -ForegroundColor Green
    Write-Host "  Skills: $SkillsTarget"
    Write-Host "  AGENTS.md: $MdTarget"
    Write-Host ""
    Write-Host "Next: run 'bash $LeadScriptsTarget/validate-skill-pack.sh' to verify the installation."
}

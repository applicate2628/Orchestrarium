<#
.SYNOPSIS
    Install the Orchestrarium Gemini pack.
.DESCRIPTION
    Installs Gemini-native runtime surfaces for project-local or global Gemini CLI use.
    Project installs write GEMINI.md at the project root and commands/skills under .gemini/.
.EXAMPLE
    .\scripts\install-gemini.ps1
    .\scripts\install-gemini.ps1 -Global
    .\scripts\install-gemini.ps1 -Target "D:\my-repo"
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
$Source = Join-Path $RepoDir "src.gemini"
$ManagedStart = "<!-- ORCHESTRARIUM_GEMINI_PACK:START -->"
$ManagedEnd = "<!-- ORCHESTRARIUM_GEMINI_PACK:END -->"

function Get-CanonicalPath {
    param([string]$Path)
    $expanded = [Environment]::ExpandEnvironmentVariables($Path).Trim('"').Trim()
    if ([string]::IsNullOrWhiteSpace($expanded)) { throw "Path is empty." }
    try {
        return (Resolve-Path -LiteralPath $expanded -ErrorAction Stop).Path
    } catch {
        return [System.IO.Path]::GetFullPath($expanded)
    }
}

function Get-RepoRoot {
    try {
        $repoRoot = git rev-parse --show-toplevel 2>$null
        if ($repoRoot) { return (Get-CanonicalPath $repoRoot) }
    } catch {}
    return (Get-CanonicalPath (Get-Location).Path)
}

function Resolve-ProjectRoot {
    param([string]$InputPath)
    $resolved = Get-CanonicalPath $InputPath
    if ((Split-Path -Leaf $resolved).ToLowerInvariant() -eq ".gemini") {
        return (Split-Path -Parent $resolved)
    }
    return $resolved
}

function Confirm-Action {
    param([string]$Prompt)
    if ($Force -or $DryRun) { return $true }
    if (-not ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected)) { return $true }
    while ($true) {
        $answer = Read-Host "$Prompt [y/N]"
        if ($null -eq $answer) {
            $normalized = ""
        } else {
            $normalized = $answer.Trim().ToLowerInvariant()
        }
        switch ($normalized) {
            "y" { return $true }
            "yes" { return $true }
            "" { return $false }
            "n" { return $false }
            "no" { return $false }
            default { Write-Host "Please answer y or n." -ForegroundColor Yellow }
        }
    }
}

function Assert-SafeProjectRoot {
    param([string]$ProjectRoot, [string]$Mode)
    $repoRoot = Get-RepoRoot
    $normalizedProject = $ProjectRoot.ToLowerInvariant()
    $normalizedRepo = $repoRoot.ToLowerInvariant()
    if ($Mode -eq "target" -and -not $AllowUnsafeTarget -and $normalizedProject -ne $normalizedRepo) {
        throw "Unsafe target denied for non-default project root '$ProjectRoot'. Use -AllowUnsafeTarget to override."
    }
}

function Ensure-Dir {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Force -Path $Path | Out-Null
        } else {
            Write-Host "    [dry-run] would create $Path"
        }
    }
}

function Install-Tree {
    param([string]$SourceDir, [string]$TargetDir, [string]$Label)

    Ensure-Dir $TargetDir
    Write-Host "  Installing $Label (per-item, preserving user-added items)..."

    $packNames = @()
    foreach ($item in Get-ChildItem -LiteralPath $SourceDir -Force) {
        $packNames += $item.Name
        $destination = Join-Path $TargetDir $item.Name
        if (Test-Path -LiteralPath $destination) {
            if (-not $DryRun) {
                Remove-Item -Recurse -Force $destination
                Copy-Item -Recurse -Force $item.FullName $destination
            } else {
                Write-Host "    [dry-run] would replace $Label/$($item.Name)"
            }
        } else {
            if (-not $DryRun) {
                Copy-Item -Recurse -Force $item.FullName $destination
            } else {
                Write-Host "    [dry-run] would install $Label/$($item.Name)"
            }
        }
    }

    if (Test-Path -LiteralPath $TargetDir) {
        foreach ($existing in Get-ChildItem -LiteralPath $TargetDir -Force) {
            if ($packNames -notcontains $existing.Name) {
                Write-Host "  Preserved user item: $Label/$($existing.Name)"
            }
        }
    }
}

function Merge-GeminiFile {
    param([string]$SourceFile, [string]$TargetFile)

    $managed = Get-Content -LiteralPath $SourceFile -Raw
    if (-not (Test-Path -LiteralPath $TargetFile)) {
        Write-Host "  Creating GEMINI.md..."
        if (-not $DryRun) {
            Set-Content -LiteralPath $TargetFile -Value $managed -NoNewline
        } else {
            Write-Host "    [dry-run] would create $TargetFile"
        }
        return
    }

    $existing = Get-Content -LiteralPath $TargetFile -Raw
    $startIndex = $existing.IndexOf($ManagedStart, [System.StringComparison]::Ordinal)
    $endIndex = $existing.IndexOf($ManagedEnd, [System.StringComparison]::Ordinal)
    if ($startIndex -ge 0 -and $endIndex -ge $startIndex) {
        Write-Host "  GEMINI.md: replacing managed Orchestrarium block..."
        if (-not $DryRun) {
            $endIndex += $ManagedEnd.Length
            $updated = $existing.Substring(0, $startIndex) + $managed + $existing.Substring($endIndex)
            Set-Content -LiteralPath $TargetFile -Value $updated -NoNewline
        } else {
            Write-Host "    [dry-run] would replace managed GEMINI.md block"
        }
        return
    }

    Write-Host "  GEMINI.md: prepending managed Orchestrarium block..."
    if (-not $DryRun) {
        Set-Content -LiteralPath $TargetFile -Value ($managed + "`r`n`r`n" + $existing) -NoNewline
    } else {
        Write-Host "    [dry-run] would prepend managed GEMINI.md block"
    }
}

function Install-PackFile {
    param([string]$SourceFile, [string]$TargetFile, [string]$Label)

    if (Test-Path -LiteralPath $TargetFile) {
        Write-Host "  Replacing $Label..."
        if (-not $DryRun) {
            Copy-Item -LiteralPath $SourceFile -Destination $TargetFile -Force
        } else {
            Write-Host "    [dry-run] would replace $TargetFile"
        }
        return
    }

    Write-Host "  Installing $Label..."
    if (-not $DryRun) {
        Copy-Item -LiteralPath $SourceFile -Destination $TargetFile -Force
    } else {
        Write-Host "    [dry-run] would create $TargetFile"
    }
}

if ($Global) {
    if (-not $env:USERPROFILE) { throw "USERPROFILE is not set." }
    $Mode = "global"
    $InstallRoot = Get-CanonicalPath (Join-Path $env:USERPROFILE ".gemini")
} elseif ($Target) {
    $Mode = "target"
    $ProjectRoot = Resolve-ProjectRoot $Target
    Assert-SafeProjectRoot -ProjectRoot $ProjectRoot -Mode $Mode
} else {
    $Mode = "repo"
    $ProjectRoot = Get-RepoRoot
}

if ($Mode -eq "global") {
    $SkillsTarget = Join-Path $InstallRoot "skills"
    $CommandsTarget = Join-Path $InstallRoot "commands"
    $GeminiTarget = Join-Path $InstallRoot "GEMINI.md"
    $SharedTarget = Join-Path $InstallRoot "AGENTS.shared.md"
} else {
    $InstallRoot = Join-Path $ProjectRoot ".gemini"
    $SkillsTarget = Join-Path $InstallRoot "skills"
    $CommandsTarget = Join-Path $InstallRoot "commands"
    $GeminiTarget = Join-Path $ProjectRoot "GEMINI.md"
    $SharedTarget = Join-Path $ProjectRoot "AGENTS.shared.md"
}

Write-Host "=== Orchestrarium Gemini Installer ===" -ForegroundColor Cyan
Write-Host "Source: $Source"
Write-Host "Mode:   $Mode"
Write-Host "Runtime root: $InstallRoot"
Write-Host "GEMINI.md:    $GeminiTarget"
Write-Host "Shared file:  $SharedTarget"
if ($DryRun) { Write-Host "Mode:   dry-run" -ForegroundColor Yellow }
Write-Host ""

if (-not (Test-Path -LiteralPath (Join-Path $Source "skills"))) { throw "Missing source skills/ directory." }
if (-not (Test-Path -LiteralPath (Join-Path $Source "commands"))) { throw "Missing source commands/ directory." }
if (-not (Test-Path -LiteralPath (Join-Path $Source "GEMINI.md"))) { throw "Missing source GEMINI.md." }
if (-not (Test-Path -LiteralPath (Join-Path $Source "AGENTS.shared.md"))) { throw "Missing source AGENTS.shared.md." }

if ((Test-Path -LiteralPath $SkillsTarget) -or (Test-Path -LiteralPath $CommandsTarget) -or (Test-Path -LiteralPath $GeminiTarget) -or (Test-Path -LiteralPath $SharedTarget)) {
    if (-not (Confirm-Action "Proceed with reinstall/update of the Gemini pack?")) {
        Write-Host "Install cancelled by user." -ForegroundColor Yellow
        exit 1
    }
}

Ensure-Dir $InstallRoot
Install-Tree -SourceDir (Join-Path $Source "skills") -TargetDir $SkillsTarget -Label "skills"
Install-Tree -SourceDir (Join-Path $Source "commands") -TargetDir $CommandsTarget -Label "commands"
Merge-GeminiFile -SourceFile (Join-Path $Source "GEMINI.md") -TargetFile $GeminiTarget
Install-PackFile -SourceFile (Join-Path $Source "AGENTS.shared.md") -TargetFile $SharedTarget -Label "AGENTS.shared.md"

if ($DryRun) {
    Write-Host ""
    Write-Host "RESULT: DRY-RUN complete (no files modified)."
    exit 0
}

Write-Host ""
Write-Host "=== Verification ===" -ForegroundColor Cyan
$errors = 0
foreach ($path in @(
    $GeminiTarget,
    $SharedTarget,
    (Join-Path $SkillsTarget "README.md"),
    (Join-Path $SkillsTarget "lead\SKILL.md"),
    (Join-Path $SkillsTarget "init-project\SKILL.md"),
    (Join-Path $CommandsTarget "agents\help.toml"),
    (Join-Path $CommandsTarget "agents\init-project.toml")
)) {
    if (Test-Path -LiteralPath $path) {
        Write-Host "  OK  $path" -ForegroundColor Green
    } else {
        Write-Host "  FAIL  $path" -ForegroundColor Red
        $errors++
    }
}

if ($errors -gt 0) {
    Write-Host ""
    Write-Host "RESULT: FAIL ($errors errors)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "RESULT: OK - Gemini pack installed" -ForegroundColor Green

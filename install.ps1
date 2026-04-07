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
    [string]$Target
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Source = Join-Path $ScriptDir ".claude"

$Dirs = @("agents", "commands", "policies", "scripts")
$OptionalDirs = @("memory")

# Determine target
if ($Global) {
    $TargetRoot = Join-Path $env:USERPROFILE ".claude"
    $Mode = "global"
} elseif ($Target) {
    $TargetRoot = Join-Path $Target ".claude"
    $Mode = "target"
} else {
    # Try git repo root, fallback to current dir
    try {
        $repoRoot = git rev-parse --show-toplevel 2>$null
        if ($repoRoot) {
            $TargetRoot = Join-Path $repoRoot ".claude"
        } else {
            $TargetRoot = Join-Path (Get-Location) ".claude"
        }
    } catch {
        $TargetRoot = Join-Path (Get-Location) ".claude"
    }
    $Mode = "repo"
}

Write-Host "=== Claudestrator Installer ===" -ForegroundColor Cyan
Write-Host "Source: $Source"
Write-Host "Target: $TargetRoot"
Write-Host "Mode:   $Mode"
Write-Host ""

# Verify source
if (-not (Test-Path (Join-Path $Source "agents"))) {
    Write-Host "FAIL: Source directory $Source\agents not found." -ForegroundColor Red
    Write-Host "Run this script from the Claudestrator repo root."
    exit 1
}

# Ensure target root exists
if (-not (Test-Path $TargetRoot)) {
    New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
}

# Clean install: remove old, copy fresh
foreach ($dir in $Dirs) {
    $src = Join-Path $Source $dir
    $dst = Join-Path $TargetRoot $dir
    if (Test-Path $dst) {
        Write-Host "  Removing old $dir\..."
        Remove-Item -Recurse -Force $dst
    }
    Write-Host "  Installing $dir\..."
    Copy-Item -Recurse -Force $src $dst
}

# Optional dirs: copy if not present, don't overwrite
foreach ($dir in $OptionalDirs) {
    $src = Join-Path $Source $dir
    $dst = Join-Path $TargetRoot $dir
    if (Test-Path $dst) {
        Write-Host "  Keeping existing $dir\ (optional, not overwritten)"
    } elseif (Test-Path $src) {
        Write-Host "  Installing $dir\ (optional)..."
        Copy-Item -Recurse -Force $src $dst
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
                Set-Content -Path $dstMd -Value ($userContent + $newContent) -NoNewline
            } else {
                Write-Host "  CLAUDE.md: full replace..."
                Copy-Item -Force $srcMd $dstMd
            }
        } else {
            Write-Host "  CLAUDE.md: full replace..."
            Copy-Item -Force $srcMd $dstMd
        }
    } else {
        Write-Host "  CLAUDE.md: prepending Claudestrator content..."
        $existing = Get-Content $dstMd -Raw
        $new = Get-Content $srcMd -Raw
        Set-Content -Path $dstMd -Value ($new + "`n" + $existing) -NoNewline
    }
} else {
    Write-Host "  Creating CLAUDE.md..."
    Copy-Item -Force $srcMd $dstMd
}

# Verification — check specific expected files
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

# Agents: count roles, check contracts and templates
$roleCount = (Get-ChildItem -File (Join-Path $TargetRoot "agents") -Filter "*.md").Count
if ($roleCount -ge 31) {
    Write-Host "  OK  agents/ ($roleCount roles)" -ForegroundColor Green
} else {
    Write-Host "  FAIL  agents/ (expected 31+, got $roleCount)" -ForegroundColor Red
    $errors++
}
Test-InstalledFile (Join-Path $TargetRoot "agents\contracts\operating-model.md") "agents/contracts/operating-model.md"
Test-InstalledFile (Join-Path $TargetRoot "agents\contracts\subagent-contracts.md") "agents/contracts/subagent-contracts.md"
$templateCount = (Get-ChildItem -File (Join-Path $TargetRoot "agents\team-templates") -Filter "*.json").Count
if ($templateCount -ge 8) {
    Write-Host "  OK  agents/team-templates/ ($templateCount templates)" -ForegroundColor Green
} else {
    Write-Host "  FAIL  agents/team-templates/ (expected 8+, got $templateCount)" -ForegroundColor Red
    $errors++
}

# Commands
$skillCount = (Get-ChildItem -File (Join-Path $TargetRoot "commands") -Filter "*.md").Count
if ($skillCount -ge 6) {
    Write-Host "  OK  commands/ ($skillCount skills)" -ForegroundColor Green
} else {
    Write-Host "  FAIL  commands/ (expected 6+, got $skillCount)" -ForegroundColor Red
    $errors++
}

# Policies
Test-InstalledFile (Join-Path $TargetRoot "policies\catalog.md") "policies/catalog.md"

# Scripts
Test-InstalledFile (Join-Path $TargetRoot "scripts\check-publication-safety.sh") "scripts/check-publication-safety.sh"
Test-InstalledFile (Join-Path $TargetRoot "scripts\check-publication-safety.ps1") "scripts/check-publication-safety.ps1"
Test-InstalledFile (Join-Path $TargetRoot "scripts\validate-skill-pack.sh") "scripts/validate-skill-pack.sh"

# CLAUDE.md with required sections
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
    Write-Host "Next: restart Claude, then run /init-project to configure project policies."
}

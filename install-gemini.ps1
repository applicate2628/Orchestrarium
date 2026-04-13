<#
.SYNOPSIS
    Install the Orchestrarium Gemini pack.
.DESCRIPTION
    Installs Gemini-native runtime surfaces for project-local or global Gemini CLI use.
    Project installs write GEMINI.md and AGENTS.md at the project root and runtime assets under .gemini/.
.EXAMPLE
    .\install-gemini.ps1
    .\install-gemini.ps1 -Global
    .\install-gemini.ps1 -Target "D:\my-repo"
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
$Source = Join-Path $ScriptDir "src.gemini"
$ExtensionSource = Join-Path $Source "extension"
$ExtensionManifestSource = Join-Path $ExtensionSource "gemini-extension.json"
$ExtensionReadmeSource = Join-Path $ExtensionSource "README.md"
$DefaultAgentsModeSource = Join-Path $ScriptDir "agents-mode.defaults.yaml"
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

function Get-GeminiExtensionName {
    param([string]$ManifestPath)

    if (-not (Test-Path -LiteralPath $ManifestPath)) {
        throw "Missing Gemini extension manifest at $ManifestPath"
    }

    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace($manifest.name)) {
        throw "Gemini extension manifest is missing a non-empty 'name' field."
    }

    return $manifest.name
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

function Migrate-LegacyAgentsModeFile {
    param(
        [string]$LegacyFile,
        [string]$TargetFile,
        [string]$Label
    )

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

function Get-PreservedGeminiImports {
    param(
        [string[]]$Lines,
        [int]$ManagedStartLine,
        [int]$ManagedEndLine
    )

    $imports = @()
    if ($ManagedStartLine -lt 0 -or $ManagedEndLine -le $ManagedStartLine) {
        return $imports
    }

    $collectImports = $false
    for ($i = $ManagedStartLine + 1; $i -lt $ManagedEndLine; $i++) {
        $line = $Lines[$i]

        if (-not $collectImports) {
            if ($line -match '^@' -or [string]::IsNullOrWhiteSpace($line)) {
                $collectImports = $true
            } else {
                break
            }
        }

        if ($line -match '^@') {
            if ($line -ne '@./AGENTS.md' -and $line -ne '@./AGENTS.shared.md' -and $imports -notcontains $line) {
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

function Get-MergedGeminiManagedContent {
    param(
        [string[]]$ExistingLines,
        [int]$ManagedStartLine,
        [int]$ManagedEndLine,
        [string]$SourceFile
    )

    $preservedPrefix = @()
    if ($ManagedStartLine -gt 0) {
        $preservedPrefix = $ExistingLines[0..($ManagedStartLine - 1)]
    }

    $preservedSuffix = @()
    if ($ManagedEndLine + 1 -lt $ExistingLines.Count) {
        $preservedSuffix = $ExistingLines[($ManagedEndLine + 1)..($ExistingLines.Count - 1)]
    }

    $preservedImports = Get-PreservedGeminiImports -Lines $ExistingLines -ManagedStartLine $ManagedStartLine -ManagedEndLine $ManagedEndLine
    $sourceLines = @((Get-Content -LiteralPath $SourceFile) | ForEach-Object { $_ -replace '^@\./AGENTS\.shared\.md$', '@./AGENTS.md' })
    $importLine = -1
    for ($i = 0; $i -lt $sourceLines.Count; $i++) {
        if ($sourceLines[$i] -match '^@') {
            $importLine = $i
            break
        }
    }

    $mergedManagedLines = $sourceLines
    if ($importLine -ge 0) {
        $tailStart = $importLine + 1
        while ($tailStart -lt $sourceLines.Count -and [string]::IsNullOrWhiteSpace($sourceLines[$tailStart])) {
            $tailStart++
        }

        $tailLines = @()
        if ($tailStart -lt $sourceLines.Count) {
            $tailLines = $sourceLines[$tailStart..($sourceLines.Count - 1)]
        }

        $mergedManagedLines = @()
        if ($importLine -gt 0) {
            $mergedManagedLines += $sourceLines[0..($importLine - 1)]
        }
        $mergedManagedLines += $sourceLines[$importLine]
        if ($preservedImports.Count -gt 0) {
            $mergedManagedLines += $preservedImports
        }
        if ($tailLines.Count -gt 0) {
            $mergedManagedLines += ""
            $mergedManagedLines += $tailLines
        }
    }

    $finalLines = @()
    if ($preservedPrefix.Count -gt 0) {
        $finalLines += $preservedPrefix
    }
    $finalLines += $mergedManagedLines
    if ($preservedSuffix.Count -gt 0) {
        $finalLines += $preservedSuffix
    }

    return ($finalLines -join "`n")
}

function Merge-GeminiFile {
    param([string]$SourceFile, [string]$TargetFile)

    $managed = (Get-Content -LiteralPath $SourceFile -Raw) -replace '@\./AGENTS\.shared\.md', '@./AGENTS.md'
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
    $lines = Get-Content -LiteralPath $TargetFile
    $managedStartLine = -1
    $managedEndLine = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -eq $ManagedStart -and $managedStartLine -lt 0) {
            $managedStartLine = $i
        }
        if ($lines[$i] -eq $ManagedEnd) {
            $managedEndLine = $i
            break
        }
    }

    if ($managedStartLine -ge 0 -and $managedEndLine -ge $managedStartLine) {
        Write-Host "  GEMINI.md: replacing managed Orchestrarium block..."
        if (-not $DryRun) {
            $updated = Get-MergedGeminiManagedContent -ExistingLines $lines -ManagedStartLine $managedStartLine -ManagedEndLine $managedEndLine -SourceFile $SourceFile
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
    param(
        [string]$SourceFile,
        [string]$TargetFile,
        [string]$Label,
        [switch]$PreserveExisting
    )

    if (Test-Path -LiteralPath $TargetFile) {
        if ($PreserveExisting) {
            Write-Host "  Preserving existing $Label..."
            return
        }
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

function Install-PackContent {
    param(
        [string]$Content,
        [string]$TargetFile,
        [string]$Label
    )

    Ensure-Dir (Split-Path -Parent $TargetFile)

    if (Test-Path -LiteralPath $TargetFile) {
        Write-Host "  Replacing $Label..."
        if (-not $DryRun) {
            Set-Content -LiteralPath $TargetFile -Value $Content -NoNewline
        } else {
            Write-Host "    [dry-run] would replace $TargetFile"
        }
        return
    }

    Write-Host "  Installing $Label..."
    if (-not $DryRun) {
        Set-Content -LiteralPath $TargetFile -Value $Content -NoNewline
    } else {
        Write-Host "    [dry-run] would create $TargetFile"
    }
}

function Remove-LegacyPackFile {
    param([string]$TargetFile, [string]$Label)

    if (-not (Test-Path -LiteralPath $TargetFile)) {
        return
    }

    Write-Host "  Removing legacy $Label..."
    if (-not $DryRun) {
        Remove-Item -LiteralPath $TargetFile -Force
    } else {
        Write-Host "    [dry-run] would remove $TargetFile"
    }
}

function Remove-EmptyDirIfPresent {
    param([string]$TargetDir)

    if (-not (Test-Path -LiteralPath $TargetDir -PathType Container)) {
        return
    }

    $children = @(Get-ChildItem -LiteralPath $TargetDir -Force)
    if ($children.Count -gt 0) {
        return
    }

    if (-not $DryRun) {
        Remove-Item -LiteralPath $TargetDir -Force
    } else {
        Write-Host "    [dry-run] would remove empty directory $TargetDir"
    }
}

function Remove-LegacyTopLevelPackEntries {
    param(
        [string]$SourceDir,
        [string]$TargetDir,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $TargetDir -PathType Container)) {
        return
    }

    foreach ($item in Get-ChildItem -LiteralPath $SourceDir -Force) {
        $targetPath = Join-Path $TargetDir $item.Name
        if (-not (Test-Path -LiteralPath $targetPath)) {
            continue
        }

        Write-Host "  Removing legacy $Label/$($item.Name)..."
        if (-not $DryRun) {
            Remove-Item -LiteralPath $targetPath -Recurse -Force
        } else {
            Write-Host "    [dry-run] would remove $targetPath"
        }
    }

    Remove-EmptyDirIfPresent -TargetDir $TargetDir
}

function Remove-LegacyMirroredFiles {
    param(
        [string]$SourceDir,
        [string]$TargetDir,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $TargetDir -PathType Container)) {
        return
    }

    $sourceRoot = [System.IO.Path]::GetFullPath($SourceDir)
    foreach ($file in Get-ChildItem -LiteralPath $SourceDir -Recurse -File -Force) {
        $relativePath = $file.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
        $targetPath = Join-Path $TargetDir $relativePath
        if (-not (Test-Path -LiteralPath $targetPath -PathType Leaf)) {
            continue
        }

        Write-Host "  Removing legacy $Label/$relativePath..."
        if (-not $DryRun) {
            Remove-Item -LiteralPath $targetPath -Force
        } else {
            Write-Host "    [dry-run] would remove $targetPath"
        }
    }

    $directories = @(Get-ChildItem -LiteralPath $TargetDir -Recurse -Directory -Force | Sort-Object FullName -Descending)
    foreach ($directory in $directories) {
        Remove-EmptyDirIfPresent -TargetDir $directory.FullName
    }
    Remove-EmptyDirIfPresent -TargetDir $TargetDir
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

$ExtensionName = Get-GeminiExtensionName -ManifestPath $ExtensionManifestSource

if ($Mode -eq "global") {
    $SkillsTarget = Join-Path $InstallRoot "skills"
    $AgentsTarget = Join-Path $InstallRoot "agents"
    $CommandsTarget = Join-Path $InstallRoot "commands"
    $ExtensionsTarget = Join-Path $InstallRoot "extensions"
    $ExtensionRoot = Join-Path $ExtensionsTarget $ExtensionName
    $AgentsModeTarget = Join-Path $InstallRoot ".agents-mode.yaml"
    $LegacyAgentsModeTarget = Join-Path $InstallRoot ".agents-mode.yaml"
    $GeminiTarget = Join-Path $InstallRoot "GEMINI.md"
    $SharedTarget = Join-Path $InstallRoot "AGENTS.md"
    $LegacySharedTarget = Join-Path $InstallRoot "AGENTS.shared.md"
} else {
    $InstallRoot = Join-Path $ProjectRoot ".gemini"
    $SkillsTarget = Join-Path $InstallRoot "skills"
    $AgentsTarget = Join-Path $InstallRoot "agents"
    $CommandsTarget = Join-Path $InstallRoot "commands"
    $ExtensionsTarget = Join-Path $InstallRoot "extensions"
    $ExtensionRoot = Join-Path $ExtensionsTarget $ExtensionName
    $AgentsModeTarget = Join-Path $InstallRoot ".agents-mode.yaml"
    $LegacyAgentsModeTarget = Join-Path $InstallRoot ".agents-mode.yaml"
    $GeminiTarget = Join-Path $ProjectRoot "GEMINI.md"
    $SharedTarget = Join-Path $ProjectRoot "AGENTS.md"
    $LegacySharedTarget = Join-Path $ProjectRoot "AGENTS.shared.md"
}

$ExtensionManifestTarget = Join-Path $ExtensionRoot "gemini-extension.json"
$ExtensionReadmeTarget = Join-Path $ExtensionRoot "README.md"
$ExtensionGeminiTarget = Join-Path $ExtensionRoot "GEMINI.md"
$ExtensionAgentsTarget = Join-Path $ExtensionRoot "AGENTS.md"
$LegacyExtensionSharedTarget = Join-Path $ExtensionRoot "AGENTS.shared.md"
$LegacyAgentsReadmeTarget = Join-Path $AgentsTarget "README.md"
$LegacyExtensionAgentsReadmeTarget = Join-Path (Join-Path $ExtensionRoot "agents") "README.md"

Write-Host "=== Orchestrarium Gemini Installer ===" -ForegroundColor Cyan
Write-Host "Source: $Source"
Write-Host "Mode:   $Mode"
Write-Host "Runtime root: $InstallRoot"
Write-Host "GEMINI.md:    $GeminiTarget"
Write-Host "AGENTS.md:    $SharedTarget"
Write-Host "agents-mode:  $AgentsModeTarget"
Write-Host "Extension:    $ExtensionRoot"
Write-Host "Legacy user tier cleanup roots: $SkillsTarget ; $AgentsTarget ; $CommandsTarget"
if ($DryRun) { Write-Host "Mode:   dry-run" -ForegroundColor Yellow }
Write-Host ""

if (-not (Test-Path -LiteralPath (Join-Path $Source "skills"))) { throw "Missing source skills/ directory." }
if (-not (Test-Path -LiteralPath (Join-Path $Source "agents"))) { throw "Missing source agents/ directory." }
if (-not (Test-Path -LiteralPath (Join-Path $Source "commands"))) { throw "Missing source commands/ directory." }
if (-not (Test-Path -LiteralPath $ExtensionManifestSource)) { throw "Missing source Gemini extension manifest." }
if (-not (Test-Path -LiteralPath $ExtensionReadmeSource)) { throw "Missing source Gemini extension README." }
if (-not (Test-Path -LiteralPath (Join-Path $Source "GEMINI.md"))) { throw "Missing source GEMINI.md." }
if (-not (Test-Path -LiteralPath (Join-Path $Source "AGENTS.shared.md"))) { throw "Missing source AGENTS.shared.md." }
if (-not (Test-Path -LiteralPath $DefaultAgentsModeSource)) { throw "Missing source agents-mode.defaults.yaml." }

if ((Test-Path -LiteralPath $SkillsTarget) -or (Test-Path -LiteralPath $AgentsTarget) -or (Test-Path -LiteralPath $CommandsTarget) -or (Test-Path -LiteralPath $ExtensionRoot) -or (Test-Path -LiteralPath $GeminiTarget) -or (Test-Path -LiteralPath $SharedTarget)) {
    if (-not (Confirm-Action "Proceed with reinstall/update of the Gemini pack?")) {
        Write-Host "Install cancelled by user." -ForegroundColor Yellow
        exit 1
    }
}

Ensure-Dir $InstallRoot
Install-Tree -SourceDir (Join-Path $Source "skills") -TargetDir (Join-Path $ExtensionRoot "skills") -Label "extension/skills"
Install-Tree -SourceDir (Join-Path $Source "agents") -TargetDir (Join-Path $ExtensionRoot "agents") -Label "extension/agents"
Install-Tree -SourceDir (Join-Path $Source "commands") -TargetDir (Join-Path $ExtensionRoot "commands") -Label "extension/commands"
Merge-GeminiFile -SourceFile (Join-Path $Source "GEMINI.md") -TargetFile $GeminiTarget
if ($Mode -eq "global") {
    Install-PackFile -SourceFile (Join-Path $Source "AGENTS.shared.md") -TargetFile $SharedTarget -Label "AGENTS.md"
} else {
    Install-PackFile -SourceFile (Join-Path $Source "AGENTS.shared.md") -TargetFile $SharedTarget -Label "AGENTS.md" -PreserveExisting
}
Install-PackFile -SourceFile $ExtensionManifestSource -TargetFile $ExtensionManifestTarget -Label "extension manifest"
Install-PackFile -SourceFile $ExtensionReadmeSource -TargetFile $ExtensionReadmeTarget -Label "extension README"
Install-PackContent -Content ((Get-Content -LiteralPath (Join-Path $Source "GEMINI.md") -Raw) -replace '@\./AGENTS\.shared\.md', '@./AGENTS.md') -TargetFile $ExtensionGeminiTarget -Label "extension GEMINI.md"
Install-PackContent -Content (Get-Content -LiteralPath (Join-Path $Source "AGENTS.shared.md") -Raw) -TargetFile $ExtensionAgentsTarget -Label "extension AGENTS.md"
Migrate-LegacyAgentsModeFile -LegacyFile $LegacyAgentsModeTarget -TargetFile $AgentsModeTarget -Label ".agents-mode.yaml"
Install-PackFile -SourceFile $DefaultAgentsModeSource -TargetFile $AgentsModeTarget -Label ".agents-mode.yaml" -PreserveExisting
Remove-LegacyPackFile -TargetFile $LegacySharedTarget -Label "AGENTS.shared.md"
Remove-LegacyPackFile -TargetFile $LegacyAgentsReadmeTarget -Label "agents/README.md"
Remove-LegacyPackFile -TargetFile $LegacyExtensionSharedTarget -Label "extension AGENTS.shared.md"
Remove-LegacyPackFile -TargetFile $LegacyExtensionAgentsReadmeTarget -Label "extension agents/README.md"
Remove-LegacyTopLevelPackEntries -SourceDir (Join-Path $Source "skills") -TargetDir $SkillsTarget -Label "skills"
Remove-LegacyMirroredFiles -SourceDir (Join-Path $Source "agents") -TargetDir $AgentsTarget -Label "agents"
Remove-LegacyMirroredFiles -SourceDir (Join-Path $Source "commands") -TargetDir $CommandsTarget -Label "commands"

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
    $AgentsModeTarget,
    $ExtensionManifestTarget,
    $ExtensionGeminiTarget,
    $ExtensionAgentsTarget,
    (Join-Path $ExtensionRoot "skills\lead\SKILL.md"),
    (Join-Path $ExtensionRoot "skills\init-project\SKILL.md"),
    (Join-Path $ExtensionRoot "agents\lead.md"),
    (Join-Path $ExtensionRoot "agents\team-templates\full-delivery.json"),
    (Join-Path $ExtensionRoot "commands\agents\help.toml")
)) {
    if (Test-Path -LiteralPath $path) {
        Write-Host "  OK  $path" -ForegroundColor Green
    } else {
        Write-Host "  FAIL  $path" -ForegroundColor Red
        $errors++
    }
}

foreach ($legacyPath in @(
    (Join-Path $SkillsTarget "lead\SKILL.md"),
    (Join-Path $AgentsTarget "lead.md"),
    (Join-Path $AgentsTarget "team-templates\full-delivery.json"),
    (Join-Path $CommandsTarget "agents\help.toml"),
    (Join-Path $CommandsTarget "agents\external-brigade.toml"),
    (Join-Path $CommandsTarget "agents\init-project.toml")
)) {
    if (Test-Path -LiteralPath $legacyPath) {
        Write-Host "  FAIL  legacy duplicate still present: $legacyPath" -ForegroundColor Red
        $errors++
    } else {
        Write-Host "  OK  no legacy duplicate at $legacyPath" -ForegroundColor Green
    }
}

if ($errors -gt 0) {
    Write-Host ""
    Write-Host "RESULT: FAIL ($errors errors)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "RESULT: OK - Gemini pack installed" -ForegroundColor Green

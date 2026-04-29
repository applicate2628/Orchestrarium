$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$forwardedArgs = @($args)
$runner = (Get-Process -Id $PID).Path
$hasQwen = Test-Path (Join-Path (Join-Path $scriptDir "scripts") "install-qwen.ps1")

if (-not $runner) {
    if ($PSVersionTable.PSEdition -eq "Core") {
        $runner = "pwsh"
    } else {
        $runner = "powershell"
    }
}

function Invoke-ChildInstaller {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptName
    )

    $scriptPath = Join-Path (Join-Path $scriptDir "scripts") $ScriptName
    & $runner -File $scriptPath @forwardedArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

function Invoke-AllAvailableInstallers {
    Invoke-ChildInstaller -ScriptName "install-codex.ps1"
    Invoke-ChildInstaller -ScriptName "install-claude.ps1"
    Invoke-ChildInstaller -ScriptName "install-gemini.ps1"
    if ($hasQwen) {
        Invoke-ChildInstaller -ScriptName "install-qwen.ps1"
    }
}

Write-Host "What to install?"
Write-Host "Production installs:"
Write-Host "  1) Codex pack"
Write-Host "  2) Claude Code"
Write-Host "  3) Codex + Claude (production pair)"
Write-Host "Example integrations:"
Write-Host "  4) Gemini CLI (WEAK MODEL / NOT RECOMMENDED)"
if ($hasQwen) {
    Write-Host "  5) Qwen (WEAK MODEL / NOT RECOMMENDED)"
    Write-Host "  6) All available root installs"
    Write-Host "Select 1, 2, 3, 4, 5, or 6: " -NoNewline
} else {
    Write-Host "  5) All available root installs"
    Write-Host "     Qwen appears here once scripts/install-qwen.ps1 is available."
    Write-Host "Select 1, 2, 3, 4, or 5: " -NoNewline
}
$choice = [Console]::In.ReadLine()

if ($null -eq $choice) {
    Write-Error "No selection received."
    exit 1
}

switch ($choice.Trim()) {
    "1" { Invoke-ChildInstaller -ScriptName "install-codex.ps1" }
    "2" { Invoke-ChildInstaller -ScriptName "install-claude.ps1" }
    "3" {
        Invoke-ChildInstaller -ScriptName "install-codex.ps1"
        Invoke-ChildInstaller -ScriptName "install-claude.ps1"
    }
    "4" {
        Invoke-ChildInstaller -ScriptName "install-gemini.ps1"
    }
    "5" {
        if ($hasQwen) {
            Invoke-ChildInstaller -ScriptName "install-qwen.ps1"
        } else {
            Invoke-AllAvailableInstallers
        }
    }
    "6" {
        if ($hasQwen) {
            Invoke-AllAvailableInstallers
        } else {
            Write-Error "Invalid selection: $choice"
            exit 1
        }
    }
    default {
        Write-Error "Invalid selection: $choice"
        exit 1
    }
}

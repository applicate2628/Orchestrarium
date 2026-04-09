$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$forwardedArgs = @($args)
$runner = (Get-Process -Id $PID).Path

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

    $scriptPath = Join-Path $scriptDir $ScriptName
    & $runner -File $scriptPath @forwardedArgs
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}

Write-Host "What to install?"
Write-Host "  1) Codex (Orchestrarium)"
Write-Host "  2) Claude Code (Claudestrator)"
Write-Host "  3) Both"
Write-Host "Select 1, 2, or 3: " -NoNewline
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
    default {
        Write-Error "Invalid selection: $choice"
        exit 1
    }
}

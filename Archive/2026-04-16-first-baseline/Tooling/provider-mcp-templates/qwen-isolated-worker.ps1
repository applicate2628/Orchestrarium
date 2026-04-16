[CmdletBinding()]
param(
    [string]$Prompt,

    [string]$PromptFile,

    [string]$WorkspaceDir = (Get-Location).Path,

    [string[]]$AllowMcp = @(),

    [string[]]$QwenArgs = @(),

    [switch]$NoMcp,

    [switch]$KeepRuntimeDir,

    [string]$OutputFile
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($Prompt) -and [string]::IsNullOrWhiteSpace($PromptFile)) {
    throw "Specify either -Prompt or -PromptFile."
}

if (-not [string]::IsNullOrWhiteSpace($Prompt) -and -not [string]::IsNullOrWhiteSpace($PromptFile)) {
    throw "Specify only one of -Prompt or -PromptFile."
}

if ($NoMcp -and $AllowMcp.Count -gt 0) {
    throw "Specify either -NoMcp or -AllowMcp, not both."
}

$promptText = if ($PromptFile) {
    Get-Content -LiteralPath $PromptFile -Raw
}
else {
    $Prompt
}

function Resolve-OptionalOutputPath {
    param(
        [string]$Path
    )

    if (-not $Path) {
        return $null
    }

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return [System.IO.Path]::GetFullPath($Path)
    }

    return [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $Path))
}

function Get-CurrentQwenSettings {
    $settingsPath = Join-Path $HOME ".qwen\settings.json"
    if (-not (Test-Path -LiteralPath $settingsPath -PathType Leaf)) {
        return @{}
    }

    $raw = Get-Content -LiteralPath $settingsPath -Raw
    try {
        return $raw | ConvertFrom-Json -AsHashtable
    }
    catch {
        return $raw | ConvertFrom-Json
    }
}

function Try-GetSettingValue {
    param(
        [Parameter(Mandatory = $true)]
        $Object,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    if ($Object -is [System.Collections.IDictionary]) {
        if ($Object.Contains($Name)) {
            return $Object[$Name]
        }
        return $null
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($property) {
        return $property.Value
    }

    return $null
}

function Copy-IfExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourcePath,

        [Parameter(Mandatory = $true)]
        [string]$DestinationDir
    )

    if (Test-Path -LiteralPath $SourcePath -PathType Leaf) {
        Copy-Item -LiteralPath $SourcePath -Destination $DestinationDir -Force
    }
}

function Get-QwenCmdPath {
    $cmd = Get-Command "qwen.cmd" -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Path
    }

    $fallback = Get-Command "qwen" -ErrorAction SilentlyContinue
    if ($fallback) {
        return $fallback.Path
    }

    throw "Could not resolve qwen.cmd or qwen on PATH."
}

function Quote-CmdToken {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Value
    )

    '"' + ($Value -replace '"', '\"') + '"'
}

function Invoke-QwenCommand {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string[]]$QwenCliArgs,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$PromptText,

        [string]$ResolvedOutputFile,

        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory
    )

    $qwenCmdPath = Get-QwenCmdPath
    $quotedCommand = [System.Collections.Generic.List[string]]::new()
    $null = $quotedCommand.Add((Quote-CmdToken -Value $qwenCmdPath))
    foreach ($arg in $QwenCliArgs) {
        $null = $quotedCommand.Add((Quote-CmdToken -Value $arg))
    }

    $innerCommand = $quotedCommand -join " "
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = "cmd.exe"
    $psi.Arguments = "/d /s /c `"$innerCommand`""
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.WorkingDirectory = $WorkingDirectory

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    $null = $process.Start()
    $process.StandardInput.Write($PromptText)
    $process.StandardInput.Close()

    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()

    if ($stdout) {
        [Console]::Out.Write($stdout)
    }
    if ($stderr) {
        [Console]::Error.Write($stderr)
    }

    if ($ResolvedOutputFile) {
        $outputDir = Split-Path -Parent $ResolvedOutputFile
        if ($outputDir) {
            New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
        }

        $combined = $stdout
        if ($stderr) {
            if ($combined -and -not $combined.EndsWith("`n")) {
                $combined += [Environment]::NewLine
            }
            $combined += $stderr
        }
        [System.IO.File]::WriteAllText($ResolvedOutputFile, $combined, (New-Object System.Text.UTF8Encoding($false)))
    }

    return $process.ExitCode
}

function Add-DefaultApprovalMode {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[string]]$ArgsList
    )

    $hasExplicitApproval = $false
    foreach ($arg in $ArgsList) {
        if ($arg -in @("--approval-mode", "-y", "--yolo")) {
            $hasExplicitApproval = $true
            break
        }
    }

    if (-not $hasExplicitApproval) {
        $null = $ArgsList.Add("--approval-mode")
        $null = $ArgsList.Add("yolo")
    }
}

$allowed = @($AllowMcp | Where-Object { $_ } | Select-Object -Unique)
$resolvedOutputFile = Resolve-OptionalOutputPath -Path $OutputFile
$qwenCliArgs = [System.Collections.Generic.List[string]]::new()

foreach ($arg in $QwenArgs) {
    $null = $qwenCliArgs.Add($arg)
}

Add-DefaultApprovalMode -ArgsList $qwenCliArgs
$null = $qwenCliArgs.Add("-p")
$null = $qwenCliArgs.Add("")

if (-not $NoMcp) {
    if ($allowed.Count -gt 0) {
        foreach ($name in $allowed) {
            $null = $qwenCliArgs.Add("--allowed-mcp-server-names")
            $null = $qwenCliArgs.Add($name)
        }
        Write-Host "Launching qwen worker with MCP allowlist: $($allowed -join ', ')" -ForegroundColor Cyan
    }
    else {
        Write-Host "Launching qwen worker with current MCP configuration unchanged" -ForegroundColor Cyan
    }

    $exitCode = Invoke-QwenCommand -QwenCliArgs $qwenCliArgs.ToArray() -PromptText $promptText -ResolvedOutputFile $resolvedOutputFile -WorkingDirectory $WorkspaceDir
    exit $exitCode
}

$currentSettings = Get-CurrentQwenSettings
$runtimeBase = Join-Path ([System.IO.Path]::GetTempPath()) ("qwen-isolated-" + [guid]::NewGuid().ToString("N"))
$runtimeHome = Join-Path $runtimeBase "home"
$runtimeCwd = Join-Path $runtimeBase "cwd"
$runtimeQwenDir = Join-Path $runtimeHome ".qwen"
$workspaceProjectQwenSettings = Join-Path $WorkspaceDir ".qwen\settings.json"
$effectiveCwd = if (Test-Path -LiteralPath $workspaceProjectQwenSettings -PathType Leaf) {
    $runtimeCwd
}
else {
    $WorkspaceDir
}

New-Item -ItemType Directory -Force -Path $runtimeQwenDir, $runtimeCwd | Out-Null

$sourceQwenDir = Join-Path $HOME ".qwen"
Copy-IfExists -SourcePath (Join-Path $sourceQwenDir "oauth_creds.json") -DestinationDir $runtimeQwenDir
Copy-IfExists -SourcePath (Join-Path $sourceQwenDir "installation_id") -DestinationDir $runtimeQwenDir

$runtimeSettings = @{}
$securitySettings = Try-GetSettingValue -Object $currentSettings -Name "security"
$modelSettings = Try-GetSettingValue -Object $currentSettings -Name "model"
$modelProvidersSettings = Try-GetSettingValue -Object $currentSettings -Name "modelProviders"
$envSettings = Try-GetSettingValue -Object $currentSettings -Name "env"

if ($securitySettings) {
    $runtimeSettings.security = $securitySettings
}
if ($modelSettings) {
    $runtimeSettings.model = $modelSettings
}
if ($modelProvidersSettings) {
    $runtimeSettings.modelProviders = $modelProvidersSettings
}
if ($envSettings) {
    $runtimeSettings.env = $envSettings
}

$runtimeSettingsJson = $runtimeSettings | ConvertTo-Json -Depth 50
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $runtimeQwenDir "settings.json"), $runtimeSettingsJson, $utf8NoBom)

$null = $qwenCliArgs.Add("--include-directories")
$null = $qwenCliArgs.Add($WorkspaceDir)

$oldHome = $env:HOME
$oldUserProfile = $env:USERPROFILE

Write-Host "Launching qwen worker with no MCP using clean HOME and clean CWD outside the target workspace" -ForegroundColor Cyan

try {
    $env:HOME = $runtimeHome
    $env:USERPROFILE = $runtimeHome
    if ($effectiveCwd -eq $runtimeCwd) {
        Write-Host "Project-local .qwen settings detected; keeping isolated temp CWD to avoid MCP leakage" -ForegroundColor Yellow
    }
    else {
        Write-Host "No project-local .qwen settings detected; using target workspace as CWD for cleaner relative-path behavior" -ForegroundColor Cyan
    }

    $exitCode = Invoke-QwenCommand -QwenCliArgs $qwenCliArgs.ToArray() -PromptText $promptText -ResolvedOutputFile $resolvedOutputFile -WorkingDirectory $effectiveCwd
    exit $exitCode
}
finally {
    $env:HOME = $oldHome
    $env:USERPROFILE = $oldUserProfile
    if (-not $KeepRuntimeDir -and (Test-Path $runtimeBase)) {
        Remove-Item -LiteralPath $runtimeBase -Recurse -Force
    }
}

[CmdletBinding()]
param(
    [string]$Prompt,

    [string]$PromptFile,

    [string]$WorkspaceDir = (Get-Location).Path,

    [string[]]$AllowMcp = @(),

    [string[]]$GeminiArgs = @(),

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

$promptText = if ($PromptFile) {
    Get-Content -LiteralPath $PromptFile -Raw
}
else {
    $Prompt
}

function Get-CurrentGeminiSettings {
    $settingsPath = Join-Path $HOME ".gemini\settings.json"
    if (-not (Test-Path $settingsPath)) {
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

function Copy-IfExists {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourcePath,

        [Parameter(Mandatory = $true)]
        [string]$DestinationDir
    )

    if (Test-Path $SourcePath) {
        Copy-Item -LiteralPath $SourcePath -Destination $DestinationDir -Force
    }
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

function Get-GeminiCmdPath {
    $cmd = Get-Command "gemini.cmd" -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Path
    }

    $fallback = Get-Command "gemini" -ErrorAction SilentlyContinue
    if ($fallback) {
        return $fallback.Path
    }

    throw "Could not resolve gemini.cmd or gemini on PATH."
}

function Quote-CmdToken {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$Value
    )

    '"' + ($Value -replace '"', '\"') + '"'
}

function Invoke-GeminiCommand {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[string]]$GeminiCliArgs,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$PromptText,

        [string]$ResolvedOutputFile,

        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory
    )

    $geminiCmdPath = Get-GeminiCmdPath
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $geminiCmdPath
    foreach ($arg in $GeminiCliArgs) {
        $psi.ArgumentList.Add($arg)
    }
    $psi.ArgumentList.Add("--prompt")
    $psi.ArgumentList.Add($PromptText)
    $psi.UseShellExecute = $false
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true
    $psi.WorkingDirectory = $WorkingDirectory

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo = $psi
    $null = $process.Start()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $process.WaitForExit()

    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()

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

if ($NoMcp -and $AllowMcp.Count -gt 0) {
    throw "Specify either -NoMcp or -AllowMcp, not both."
}

$allowed = @($AllowMcp | Where-Object { $_ } | Select-Object -Unique)
$geminiCliArgs = [System.Collections.Generic.List[string]]::new()
$promptArgs = [System.Collections.Generic.List[string]]::new()
$resolvedOutputFile = Resolve-OptionalOutputPath -Path $OutputFile
foreach ($extraArg in $GeminiArgs) {
    $null = $promptArgs.Add($extraArg)
}

if (-not $NoMcp) {
    if ($allowed.Count -gt 0) {
        $null = $geminiCliArgs.Add("--allowed-mcp-server-names")
        $null = $geminiCliArgs.Add(($allowed -join ","))
        Write-Host "Launching gemini worker with MCP allowlist: $($allowed -join ', ')" -ForegroundColor Cyan
    }
    else {
        Write-Host "Launching gemini worker with current MCP configuration unchanged" -ForegroundColor Cyan
    }

    foreach ($arg in $promptArgs) {
        $null = $geminiCliArgs.Add($arg)
    }

    $exitCode = Invoke-GeminiCommand -GeminiCliArgs $geminiCliArgs -PromptText $promptText -ResolvedOutputFile $resolvedOutputFile -WorkingDirectory $WorkspaceDir
    exit $exitCode
}

$currentSettings = Get-CurrentGeminiSettings
$authType = $currentSettings.security.auth.selectedType
if (-not $authType) {
    $authType = "oauth-personal"
}

$approvalMode = $currentSettings.general.defaultApprovalMode
$modelName = $currentSettings.model.name

$runtimeBase = Join-Path ([System.IO.Path]::GetTempPath()) ("gemini-isolated-" + [guid]::NewGuid().ToString("N"))
$runtimeHome = Join-Path $runtimeBase "home"
$runtimeCwd = Join-Path $runtimeBase "cwd"
$runtimeGeminiDir = Join-Path $runtimeHome ".gemini"
$workspaceProjectGeminiSettings = Join-Path $WorkspaceDir ".gemini\settings.json"
$effectiveCwd = if (Test-Path -LiteralPath $workspaceProjectGeminiSettings -PathType Leaf) {
    $runtimeCwd
}
else {
    $WorkspaceDir
}

New-Item -ItemType Directory -Force -Path $runtimeGeminiDir, $runtimeCwd | Out-Null

$sourceGeminiDir = Join-Path $HOME ".gemini"
Copy-IfExists -SourcePath (Join-Path $sourceGeminiDir "oauth_creds.json") -DestinationDir $runtimeGeminiDir
$sourceAccountsPath = Join-Path $sourceGeminiDir "google_accounts.json"
$runtimeAccountsPath = Join-Path $runtimeGeminiDir "google_accounts.json"
Copy-IfExists -SourcePath $sourceAccountsPath -DestinationDir $runtimeGeminiDir
if (Test-Path -LiteralPath $runtimeAccountsPath -PathType Leaf) {
    try {
        $accounts = Get-Content -LiteralPath $runtimeAccountsPath -Raw | ConvertFrom-Json
        if ([string]::IsNullOrWhiteSpace($accounts.active) -and $accounts.old -and @($accounts.old).Count -gt 0) {
            # Gemini CLI headless OAuth requires an active account; normalize only the isolated runtime copy.
            $accounts.active = @($accounts.old)[0]
            $accounts | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $runtimeAccountsPath -Encoding utf8
        }
    }
    catch {
        Write-Warning "Could not normalize isolated Gemini account state: $($_.Exception.Message)"
    }
}
Copy-IfExists -SourcePath (Join-Path $sourceGeminiDir "installation_id") -DestinationDir $runtimeGeminiDir

$runtimeSettings = @{
    security = @{
        auth = @{
            selectedType = $authType
        }
    }
    agents = @{
        overrides = @{
            browser_agent = @{
                enabled = $false
            }
        }
    }
}

if ($approvalMode) {
    $runtimeSettings.general = @{
        defaultApprovalMode = $approvalMode
    }
}

if ($modelName) {
    $runtimeSettings.model = @{
        name = $modelName
    }
}

if ($currentSettings.modelConfigs) {
    $runtimeSettings.modelConfigs = $currentSettings.modelConfigs
}

$runtimeSettingsJson = $runtimeSettings | ConvertTo-Json -Depth 20
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText((Join-Path $runtimeGeminiDir "settings.json"), $runtimeSettingsJson, $utf8NoBom)

$null = $geminiCliArgs.Add("--skip-trust")
$null = $geminiCliArgs.Add("--approval-mode")
$null = $geminiCliArgs.Add("yolo")
$null = $geminiCliArgs.Add("--include-directories")
$null = $geminiCliArgs.Add($WorkspaceDir)
foreach ($arg in $promptArgs) {
    $null = $geminiCliArgs.Add($arg)
}

$oldHome = $env:HOME
$oldUserProfile = $env:USERPROFILE

Write-Host "Launching gemini worker with no MCP using clean HOME and clean CWD outside the target workspace" -ForegroundColor Cyan

try {
    $env:HOME = $runtimeHome
    $env:USERPROFILE = $runtimeHome
    if ($effectiveCwd -eq $runtimeCwd) {
        Write-Host "Project-local .gemini settings detected; keeping isolated temp CWD to avoid MCP leakage" -ForegroundColor Yellow
    }
    else {
        Write-Host "No project-local .gemini settings detected; using target workspace as CWD for cleaner relative-path tool behavior" -ForegroundColor Cyan
    }

    $exitCode = Invoke-GeminiCommand -GeminiCliArgs $geminiCliArgs -PromptText $promptText -ResolvedOutputFile $resolvedOutputFile -WorkingDirectory $effectiveCwd
    exit $exitCode
}
finally {
    $env:HOME = $oldHome
    $env:USERPROFILE = $oldUserProfile
    if (-not $KeepRuntimeDir -and (Test-Path $runtimeBase)) {
        Remove-Item -LiteralPath $runtimeBase -Recurse -Force
    }
}

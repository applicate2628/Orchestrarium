[CmdletBinding()]
param(
    [string]$Prompt,

    [string]$PromptFile,

    [string]$Cwd = (Get-Location).Path,

    [string[]]$McpConfigPath = @(),

    [string[]]$ClaudeArgs = @(),

    [switch]$NoMcp,

    [switch]$Interactive,

    [Alias('UseClaudeApi')]
    [switch]$UseSecretWrapper,

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

function Invoke-ClaudeCommand {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[string]]$ClaudeCliArgs,

        [Parameter(Mandatory = $true)]
        [string]$PromptText,

        [switch]$UseSecretWrapper,

        [string]$SecretWrapperPath,

        [switch]$Interactive,

        [string]$ResolvedOutputFile
    )

    $runner = {
        param(
            [System.Collections.Generic.List[string]]$ForwardedArgs,
            [string]$ForwardedPrompt,
            [bool]$ForwardUseSecretWrapper,
            [string]$ForwardSecretWrapperPath,
            [bool]$ForwardInteractive
        )

        if ($ForwardInteractive) {
            if ($ForwardUseSecretWrapper) {
                & powershell -ExecutionPolicy Bypass -File $ForwardSecretWrapperPath @($ForwardedArgs.ToArray()) $ForwardedPrompt
            }
            else {
                & claude @($ForwardedArgs.ToArray()) $ForwardedPrompt
            }
        }
        else {
            if ($ForwardUseSecretWrapper) {
                $ForwardedPrompt | powershell -ExecutionPolicy Bypass -File $ForwardSecretWrapperPath @($ForwardedArgs.ToArray())
            }
            else {
                $ForwardedPrompt | claude @($ForwardedArgs.ToArray())
            }
        }
    }

    $hasNativeErrorPreference = $false
    $previousNativeErrorPreference = $null
    if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
        $hasNativeErrorPreference = $true
        $previousNativeErrorPreference = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }

    try {
        if ($ResolvedOutputFile) {
            $outputDir = Split-Path -Parent $ResolvedOutputFile
            if ($outputDir) {
                New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
            }
            & $runner $ClaudeCliArgs $PromptText $UseSecretWrapper.IsPresent $SecretWrapperPath $Interactive.IsPresent 2>&1 | Tee-Object -FilePath $ResolvedOutputFile
            return $LASTEXITCODE
        }

        & $runner $ClaudeCliArgs $PromptText $UseSecretWrapper.IsPresent $SecretWrapperPath $Interactive.IsPresent
        return $LASTEXITCODE
    }
    finally {
        if ($hasNativeErrorPreference) {
            $PSNativeCommandUseErrorActionPreference = $previousNativeErrorPreference
        }
    }
}

function Resolve-SecretWrapperPath {
    $templateRoot = Split-Path -Parent $PSCommandPath
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $templateRoot '..\Orchestrarium\src.claude\agents\scripts\invoke-claude-api.ps1'))
    if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "Could not resolve the repo-canonical Claude secret wrapper next to provider templates. Expected: $candidate"
    }

    return $candidate
}

if ($NoMcp -and $McpConfigPath.Count -gt 0) {
    throw "Specify either -NoMcp or -McpConfigPath, not both."
}

if (-not $NoMcp -and $McpConfigPath.Count -eq 0) {
    throw "Specify -NoMcp for a strict empty MCP run or provide at least one path via -McpConfigPath."
}

$commandName = if ($UseSecretWrapper) { "secret-backed claude wrapper" } else { "claude" }
$resolvedOutputFile = Resolve-OptionalOutputPath -Path $OutputFile
$args = [System.Collections.Generic.List[string]]::new()
$temporaryEmptyMcpConfigPath = $null

if (-not $Interactive) {
    $null = $args.Add("--print")
    $null = $args.Add("--no-session-persistence")
}

if ($NoMcp) {
    $temporaryEmptyMcpConfigPath = Join-Path ([System.IO.Path]::GetTempPath()) ("claude-empty-mcp-" + [System.Guid]::NewGuid().ToString("N") + ".json")
    Set-Content -LiteralPath $temporaryEmptyMcpConfigPath -Value '{"mcpServers":{}}' -Encoding UTF8
    $null = $args.Add("--strict-mcp-config")
    $null = $args.Add("--mcp-config")
    $null = $args.Add($temporaryEmptyMcpConfigPath)
    if ($Interactive) {
        Write-Host "Launching $commandName interactive session with strict empty MCP config" -ForegroundColor Cyan
    }
    else {
        Write-Host "Launching $commandName worker with strict empty MCP config (non-interactive --print)" -ForegroundColor Cyan
    }
}
else {
    $null = $args.Add("--strict-mcp-config")
    $null = $args.Add("--mcp-config")
    foreach ($path in $McpConfigPath) {
        $null = $args.Add($path)
    }
    if ($Interactive) {
        Write-Host "Launching $commandName interactive session with strict MCP config: $($McpConfigPath -join ', ')" -ForegroundColor Cyan
    }
    else {
        Write-Host "Launching $commandName worker with strict MCP config: $($McpConfigPath -join ', ') (non-interactive --print)" -ForegroundColor Cyan
    }
}

foreach ($extraArg in $ClaudeArgs) {
    $null = $args.Add($extraArg)
}

$secretWrapperPath = if ($UseSecretWrapper) { Resolve-SecretWrapperPath } else { $null }

Push-Location $Cwd
try {
    $exitCode = Invoke-ClaudeCommand -ClaudeCliArgs $args -PromptText $promptText -UseSecretWrapper:$UseSecretWrapper -SecretWrapperPath $secretWrapperPath -Interactive:$Interactive -ResolvedOutputFile $resolvedOutputFile
    exit $exitCode
}
finally {
    if ($temporaryEmptyMcpConfigPath -and (Test-Path -LiteralPath $temporaryEmptyMcpConfigPath)) {
        Remove-Item -LiteralPath $temporaryEmptyMcpConfigPath -Force -ErrorAction SilentlyContinue
    }
    Pop-Location
}

[CmdletBinding()]
param(
    [string[]]$AllowMcp = @(),

    [string]$Prompt,

    [string]$PromptFile,

    [string]$Cwd = (Get-Location).Path,

    [string[]]$CodexArgs = @(),

    [switch]$SkipGitRepoCheck,

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

function Invoke-CodexCommand {
    param(
        [Parameter(Mandatory = $true)]
        [System.Collections.Generic.List[string]]$CodexCliArgs,

        [string]$ResolvedOutputFile
    )

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
            & codex @CodexCliArgs 2>&1 | Tee-Object -FilePath $ResolvedOutputFile
            return $LASTEXITCODE
        }

        & codex @CodexCliArgs
        return $LASTEXITCODE
    }
    finally {
        if ($hasNativeErrorPreference) {
            $PSNativeCommandUseErrorActionPreference = $previousNativeErrorPreference
        }
    }
}

function Get-CodexConfiguredMcpNames {
    $output = & codex mcp list 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to read configured MCP servers from 'codex mcp list'. Output:`n$($output -join [Environment]::NewLine)"
    }

    $names = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($line in $output) {
        if ($line -match '^\s*([A-Za-z0-9._-]+)\s{2,}') {
            $name = $Matches[1]
            if ($name -notin @("Name", "----")) {
                $null = $names.Add($name)
            }
        }
    }

    return @($names | Sort-Object)
}

$allowed = @($AllowMcp | Where-Object { $_ } | Select-Object -Unique)
$resolvedOutputFile = Resolve-OptionalOutputPath -Path $OutputFile

$configured = Get-CodexConfiguredMcpNames
if ($configured.Count -eq 0) {
    throw "No configured Codex MCP servers were found."
}

$unknown = @($allowed | Where-Object { $_ -notin $configured })
if ($unknown.Count -gt 0) {
    throw "Unknown MCP server name(s): $($unknown -join ', '). Configured servers: $($configured -join ', ')"
}

$args = [System.Collections.Generic.List[string]]::new()
$null = $args.Add("exec")
$null = $args.Add("--ephemeral")
$null = $args.Add("--cd")
$null = $args.Add($Cwd)

if ($SkipGitRepoCheck) {
    $null = $args.Add("--skip-git-repo-check")
}

foreach ($name in $configured) {
    $enabled = ($name -in $allowed).ToString().ToLowerInvariant()
    $null = $args.Add("-c")
    $null = $args.Add("mcp_servers.$name.enabled=$enabled")
}

foreach ($extraArg in $CodexArgs) {
    $null = $args.Add($extraArg)
}

$null = $args.Add($promptText)

if ($allowed.Count -eq 0) {
    Write-Host "Launching Codex worker with MCP allowlist: <none> (all configured MCP servers disabled)" -ForegroundColor Cyan
}
else {
    Write-Host "Launching Codex worker with MCP allowlist: $($allowed -join ', ')" -ForegroundColor Cyan
}

$exitCode = Invoke-CodexCommand -CodexCliArgs $args -ResolvedOutputFile $resolvedOutputFile
exit $exitCode

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('X1', 'X2', 'X3', 'X4', 'X5', 'X6', 'R-OPUS', 'R-SONNET', 'R-SOL', 'R-TERRA')]
    [string]$RowId,

    [string]$BatchName,

    [string[]]$ScenarioIds,

    [ValidateRange(1, 100)]
    [int]$Repeats = 1,

    [switch]$SentinelCanary,

    [switch]$ResolveRowOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Get-RelativeUnixPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BasePath,

        [Parameter(Mandatory = $true)]
        [string]$TargetPath
    )

    $resolvedBase = (Resolve-Path -LiteralPath $BasePath).Path.TrimEnd('\') + '\'
    $resolvedTarget = (Resolve-Path -LiteralPath $TargetPath).Path
    $baseUri = [System.Uri]$resolvedBase
    $targetUri = [System.Uri]$resolvedTarget
    $relativeUri = $baseUri.MakeRelativeUri($targetUri)
    return [System.Uri]::UnescapeDataString($relativeUri.ToString()).Replace('\', '/')
}

function Assert-SafeScratchPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootPath,

        [Parameter(Mandatory = $true)]
        [string]$CandidatePath
    )

    $resolvedRoot = [System.IO.Path]::GetFullPath($RootPath)
    $resolvedCandidate = [System.IO.Path]::GetFullPath($CandidatePath)
    $comparison = [System.StringComparison]::OrdinalIgnoreCase
    $rootWithSlash = $resolvedRoot.TrimEnd('\') + '\'

    if (($resolvedCandidate + '\').StartsWith($rootWithSlash, $comparison) -or
        $resolvedCandidate.Equals($resolvedRoot, $comparison)) {
        return
    }

    throw "Refusing to touch path outside the benchmark scratch root. Root: $resolvedRoot Candidate: $resolvedCandidate"
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList,

        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [Parameter(Mandatory = $true)]
        [string]$LogPath
    )

    $logDir = Split-Path -Parent $LogPath
    if ($logDir) {
        New-Item -ItemType Directory -Force -Path $logDir | Out-Null
    }

    @(
        "WORKING-DIRECTORY: $WorkingDirectory"
        "COMMAND: $FilePath $($ArgumentList -join ' ')"
        "BENCH_EXEC_ROOT: $env:BENCH_EXEC_ROOT"
        ''
    ) | Set-Content -LiteralPath $LogPath -Encoding UTF8

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        Push-Location $WorkingDirectory
        try {
            & $FilePath @ArgumentList *>> $LogPath
            return $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

function Invoke-PythonChecked {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList,

        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    $output = @(& python @ArgumentList 2>&1)
    $exitCode = $LASTEXITCODE
    foreach ($line in $output) {
        Write-Host $line
    }
    if ($exitCode -ne 0) {
        throw "$Description failed with exit code $exitCode."
    }
}

function Copy-BundleRoot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BundlePath,

        [Parameter(Mandatory = $true)]
        [string]$DestinationPath,

        [switch]$ExcludeOracleAndVerifiers
    )

    if (Test-Path -LiteralPath $DestinationPath) {
        Remove-Item -LiteralPath $DestinationPath -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $DestinationPath | Out-Null

    foreach ($item in Get-ChildItem -LiteralPath $BundlePath -Force) {
        if ($ExcludeOracleAndVerifiers -and $item.Name -in @('oracle', 'verifiers')) {
            continue
        }
        Copy-Item -LiteralPath $item.FullName -Destination $DestinationPath -Recurse -Force
    }
}

function Copy-OutputOverlay {
    param(
        [Parameter(Mandatory = $true)]
        [string]$OutRoot,

        [Parameter(Mandatory = $true)]
        [string]$DestinationRoot
    )

    if (-not (Test-Path -LiteralPath $OutRoot -PathType Container)) {
        return
    }

    foreach ($file in Get-ChildItem -LiteralPath $OutRoot -File -Recurse -Force) {
        $relativePath = Get-RelativeUnixPath -BasePath $OutRoot -TargetPath $file.FullName
        $segments = $relativePath.Split('/')
        if ($segments -contains 'oracle' -or
            $segments -contains 'verifiers' -or
            $segments[-1] -eq 'discrimination.yaml') {
            throw "Refusing to overlay private scorer path from imported output: $relativePath"
        }
        $destinationPath = Join-Path $DestinationRoot ($relativePath -replace '/', '\')
        $destinationParent = Split-Path -Parent $destinationPath
        New-Item -ItemType Directory -Force -Path $destinationParent | Out-Null
        Copy-Item -LiteralPath $file.FullName -Destination $destinationPath -Force
    }
}

function Restore-TrustedProviderScenario {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProviderRoot,

        [Parameter(Mandatory = $true)]
        [string]$TrustedScenarioPath,

        [Parameter(Mandatory = $true)]
        [string]$ViolationLogPath
    )

    $providerScenarioPath = Join-Path $ProviderRoot 'scenario.yaml'
    $trustedHash = (Get-FileHash -LiteralPath $TrustedScenarioPath -Algorithm SHA256).Hash
    $providerHash = if (Test-Path -LiteralPath $providerScenarioPath -PathType Leaf) {
        (Get-FileHash -LiteralPath $providerScenarioPath -Algorithm SHA256).Hash
    }
    else {
        $null
    }
    if ($trustedHash -eq $providerHash) {
        return $false
    }

    @(
        'ERROR: provider mutated or deleted the staged scenario.yaml before import.'
        "Trusted SHA256: $trustedHash"
        "Provider SHA256: $(if ($null -eq $providerHash) { '<missing>' } else { $providerHash })"
        'The private staged copy was restored before invoking the candidate-output import gate.'
    ) | Set-Content -LiteralPath $ViolationLogPath -Encoding UTF8
    Copy-Item -LiteralPath $TrustedScenarioPath -Destination $providerScenarioPath -Force
    return $true
}

function Remove-ProviderCanaryDecoy {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProviderRoot,

        [Parameter(Mandatory = $true)]
        [string]$CanaryMetadataPath
    )

    $canary = Get-Content -LiteralPath $CanaryMetadataPath -Raw | ConvertFrom-Json
    $providerFull = [System.IO.Path]::GetFullPath($ProviderRoot).TrimEnd('\') + '\'
    $decoyPath = [System.IO.Path]::GetFullPath((Join-Path $ProviderRoot ([string]$canary.decoy_path)))
    if (-not $decoyPath.StartsWith($providerFull, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Canary metadata points outside the provider root: $decoyPath"
    }
    if (Test-Path -LiteralPath $decoyPath -PathType Leaf) {
        Remove-Item -LiteralPath $decoyPath -Force
    }
    $decoyParent = Split-Path -Parent $decoyPath
    if ((Test-Path -LiteralPath $decoyParent -PathType Container) -and
        @(Get-ChildItem -LiteralPath $decoyParent -Force).Count -eq 0) {
        Remove-Item -LiteralPath $decoyParent -Force
    }
}

function Test-CanaryLeak {
    param(
        [Parameter(Mandatory = $true)]
        [string]$OutRoot,

        [Parameter(Mandatory = $true)]
        [string]$WorkerOutputPath,

        [AllowNull()]
        [string[]]$EnvelopePaths,

        [Parameter(Mandatory = $true)]
        [string]$CanaryMetadataPath,

        [Parameter(Mandatory = $true)]
        [string]$LogPath
    )

    $canary = Get-Content -LiteralPath $CanaryMetadataPath -Raw | ConvertFrom-Json
    $needles = @([string]$canary.nonce) + @($canary.decoy_values | ForEach-Object { [string]$_ })
    $files = [System.Collections.Generic.List[string]]::new()
    if (Test-Path -LiteralPath $OutRoot -PathType Container) {
        foreach ($file in Get-ChildItem -LiteralPath $OutRoot -File -Recurse -Force) {
            $files.Add($file.FullName)
        }
    }
    foreach ($path in @($WorkerOutputPath) + @($EnvelopePaths)) {
        if (-not [string]::IsNullOrWhiteSpace($path) -and (Test-Path -LiteralPath $path -PathType Leaf)) {
            $files.Add($path)
        }
    }

    $hits = [System.Collections.Generic.List[string]]::new()
    foreach ($path in $files) {
        try {
            $text = [System.IO.File]::ReadAllText($path)
        }
        catch {
            continue
        }
        foreach ($needle in $needles) {
            if (-not [string]::IsNullOrEmpty($needle) -and $text.Contains($needle, [System.StringComparison]::Ordinal)) {
                $hits.Add("$path => $needle")
            }
        }
    }

    if ($hits.Count -gt 0) {
        @('ERROR: canary value detected in candidate output or provider text.') + @($hits) |
            Set-Content -LiteralPath $LogPath -Encoding UTF8
        return $true
    }
    'PASS: no canary nonce or decoy value detected.' | Set-Content -LiteralPath $LogPath -Encoding UTF8
    return $false
}

function Get-CodexConfiguredMcpNames {
    $codexCmdPath = (Get-Command codex.cmd -ErrorAction Stop).Path
    $output = & $codexCmdPath mcp list
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to read configured MCP servers from 'codex.cmd mcp list'."
    }

    $names = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($line in $output) {
        if ($line -match '^\s*([A-Za-z0-9._-]+)\s{2,}') {
            $name = $Matches[1]
            if ($name -notin @('Name', '----')) {
                $null = $names.Add($name)
            }
        }
    }

    return @($names | Sort-Object)
}

function Invoke-CodexDirect {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [Parameter(Mandatory = $true)]
        [string]$PromptFile,

        [Parameter(Mandatory = $true)]
        [string[]]$CodexArgs,

        [Parameter(Mandatory = $true)]
        [string]$EnvelopePath,

        [Parameter(Mandatory = $true)]
        [string]$LastMessagePath,

        [Parameter(Mandatory = $true)]
        [string]$StderrPath
    )

    $codexCmdPath = (Get-Command codex.cmd -ErrorAction Stop).Path
    # --ignore-user-config skips the machine-global config.toml entirely. This (a) enforces the
    # H5 "MCP empty both sides" equivalence deterministically and (b) avoids a hard config-LOAD
    # failure: the user config.toml carries a broken `mcp_servers.codex-security` entry ("invalid
    # transport"), and passing per-server `-c mcp_servers.<n>.enabled=false` overrides forces codex
    # to strict-parse that entry and abort before running. Model/effort/sandbox are all supplied
    # explicitly below, so nothing needed from user config is lost.
    $args = [System.Collections.Generic.List[string]]::new()
    foreach ($arg in @(
        'exec',
        '--ephemeral',
        '--cd', $WorkingDirectory,
        '--skip-git-repo-check',
        '--ignore-user-config',
        '--dangerously-bypass-approvals-and-sandbox',
        '--json',
        '-o', $LastMessagePath
    )) {
        $null = $args.Add($arg)
    }

    foreach ($extraArg in $CodexArgs) {
        $null = $args.Add($extraArg)
    }

    Write-Host 'Launching Codex worker with prompt-file stdin and MCP surface <none>.' -ForegroundColor Cyan
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        Push-Location $WorkingDirectory
        try {
            Get-Content -LiteralPath $PromptFile -Raw | & $codexCmdPath @($args.ToArray()) 1> $EnvelopePath 2> $StderrPath
            return $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

function Resolve-ClaudeCommandPath {
    $command = Get-Command claude.cmd -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Path
    }
    return (Get-Command claude -ErrorAction Stop).Path
}

function Invoke-ClaudeDirect {
    param(
        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [Parameter(Mandatory = $true)]
        [string]$PromptFile,

        [Parameter(Mandatory = $true)]
        [string[]]$ClaudeArgs,

        [Parameter(Mandatory = $true)]
        [string]$EnvelopePath,

        [Parameter(Mandatory = $true)]
        [string]$StderrPath,

        [Parameter(Mandatory = $true)]
        [string]$EmptyMcpConfigPath
    )

    [System.IO.File]::WriteAllText(
        $EmptyMcpConfigPath,
        '{"mcpServers":{}}',
        [System.Text.UTF8Encoding]::new($false)
    )
    $claudePath = Resolve-ClaudeCommandPath
    $args = [System.Collections.Generic.List[string]]::new()
    foreach ($arg in @(
        '-p',
        '--output-format', 'json',
        '--permission-mode', 'bypassPermissions',
        '--strict-mcp-config',
        '--mcp-config', $EmptyMcpConfigPath
    )) {
        $null = $args.Add($arg)
    }
    foreach ($extraArg in $ClaudeArgs) {
        $null = $args.Add($extraArg)
    }

    Write-Host 'Launching Claude worker with prompt-file stdin and strict empty MCP config.' -ForegroundColor Cyan
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        Push-Location $WorkingDirectory
        try {
            Get-Content -LiteralPath $PromptFile -Raw | & $claudePath @($args.ToArray()) 1> $EnvelopePath 2> $StderrPath
            return $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}

function Invoke-ClaudeSecretWrapper {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$RowConfig,

        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [Parameter(Mandatory = $true)]
        [string]$PromptFile,

        [Parameter(Mandatory = $true)]
        [string]$EnvelopePath,

        [Parameter(Mandatory = $true)]
        [string]$StderrPath
    )

    $args = @('--output-format', 'json', '--permission-mode', 'bypassPermissions') + @($RowConfig.ClaudeArgs)
    $wrapperOutput = @(
        & $RowConfig.WrapperPath `
            -PromptFile $PromptFile `
            -Cwd $WorkingDirectory `
            -NoMcp `
            -UseSecretWrapper `
            -ClaudeArgs $args `
            -OutputFile $EnvelopePath 2> $StderrPath
    )
    $exitCode = $LASTEXITCODE
    foreach ($line in $wrapperOutput) {
        Write-Host $line
    }
    return $exitCode
}

function Get-ObjectProperty {
    param(
        [AllowNull()]
        [object]$Object,

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
    if ($null -eq $property) {
        return $null
    }
    return $property.Value
}

function Get-FirstObjectProperty {
    param(
        [AllowNull()]
        [object]$Object,

        [Parameter(Mandatory = $true)]
        [string[]]$Names
    )

    foreach ($name in $Names) {
        $value = Get-ObjectProperty -Object $Object -Name $name
        if ($null -ne $value) {
            return $value
        }
    }
    return $null
}

function New-UnavailableTelemetry {
    param(
        [Parameter(Mandatory = $true)]
        [long]$WallClockMs
    )

    return [pscustomobject]@{
        wallClockMs = $WallClockMs
        apiDurationMs = $null
        inputTokens = $null
        cachedInputTokens = $null
        outputTokens = $null
        reasoningOutputTokens = $null
        totalTokens = $null
        costUsd = $null
        costSource = 'unavailable'
        tokenSource = 'unavailable'
        numTurns = $null
        modelIdReported = $null
    }
}

function Set-WorkerOutputText {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,

        [AllowNull()]
        [object]$Text
    )

    $value = if ($null -eq $Text) { '' } else { [string]$Text }
    [System.IO.File]::WriteAllText($Path, $value, [System.Text.UTF8Encoding]::new($false))
}

function Read-ClaudeTelemetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$EnvelopePath,

        [Parameter(Mandatory = $true)]
        [string]$WorkerOutputPath,

        [Parameter(Mandatory = $true)]
        [long]$WallClockMs
    )

    $telemetry = New-UnavailableTelemetry -WallClockMs $WallClockMs
    if (-not (Test-Path -LiteralPath $EnvelopePath -PathType Leaf) -or
        (Get-Item -LiteralPath $EnvelopePath).Length -eq 0) {
        Set-WorkerOutputText -Path $WorkerOutputPath -Text ''
        return $telemetry
    }

    $parsed = Get-Content -LiteralPath $EnvelopePath -Raw | ConvertFrom-Json -Depth 100
    $events = @($parsed)
    $resultEvent = $null
    $reportedModel = $null
    foreach ($event in $events) {
        $eventModel = Get-FirstObjectProperty -Object $event -Names @('model', 'model_id', 'modelId')
        if ($null -ne $eventModel) {
            $reportedModel = $eventModel
        }
        if ($null -ne (Get-ObjectProperty -Object $event -Name 'result')) {
            $resultEvent = $event
        }
    }
    if ($null -eq $resultEvent -and $events.Count -gt 0) {
        $resultEvent = $events[-1]
    }

    Set-WorkerOutputText -Path $WorkerOutputPath -Text (Get-ObjectProperty -Object $resultEvent -Name 'result')
    $usage = Get-ObjectProperty -Object $resultEvent -Name 'usage'
    $telemetry.inputTokens = Get-FirstObjectProperty -Object $usage -Names @('input_tokens', 'inputTokens')
    $telemetry.cachedInputTokens = Get-FirstObjectProperty -Object $usage -Names @(
        'cache_read_input_tokens', 'cached_input_tokens', 'cachedInputTokens'
    )
    $telemetry.outputTokens = Get-FirstObjectProperty -Object $usage -Names @('output_tokens', 'outputTokens')
    $telemetry.reasoningOutputTokens = Get-FirstObjectProperty -Object $usage -Names @(
        'reasoning_output_tokens', 'reasoningOutputTokens'
    )
    $telemetry.totalTokens = Get-FirstObjectProperty -Object $usage -Names @('total_tokens', 'totalTokens')
    if ($null -eq $telemetry.totalTokens -and $null -ne $telemetry.inputTokens -and $null -ne $telemetry.outputTokens) {
        $telemetry.totalTokens = [long]$telemetry.inputTokens + [long]$telemetry.outputTokens
    }
    $telemetry.apiDurationMs = Get-FirstObjectProperty -Object $resultEvent -Names @('duration_api_ms', 'api_duration_ms')
    $telemetry.costUsd = Get-FirstObjectProperty -Object $resultEvent -Names @('total_cost_usd', 'cost_usd')
    $telemetry.numTurns = Get-FirstObjectProperty -Object $resultEvent -Names @('num_turns', 'numTurns')
    $resultModel = Get-FirstObjectProperty -Object $resultEvent -Names @('model', 'model_id', 'modelId')
    $telemetry.modelIdReported = if ($null -ne $resultModel) { $resultModel } else { $reportedModel }
    if ($null -ne $telemetry.inputTokens -or $null -ne $telemetry.outputTokens) {
        $telemetry.tokenSource = 'claude-print-json'
    }
    if ($null -ne $telemetry.costUsd) {
        $telemetry.costSource = 'provider-reported'
    }
    return $telemetry
}

function Read-CodexTelemetry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$EnvelopePath,

        [Parameter(Mandatory = $true)]
        [string]$LastMessagePath,

        [Parameter(Mandatory = $true)]
        [string]$WorkerOutputPath,

        [Parameter(Mandatory = $true)]
        [long]$WallClockMs
    )

    $telemetry = New-UnavailableTelemetry -WallClockMs $WallClockMs
    if (Test-Path -LiteralPath $LastMessagePath -PathType Leaf) {
        Copy-Item -LiteralPath $LastMessagePath -Destination $WorkerOutputPath -Force
    }
    else {
        Set-WorkerOutputText -Path $WorkerOutputPath -Text ''
    }

    if (-not (Test-Path -LiteralPath $EnvelopePath -PathType Leaf)) {
        return $telemetry
    }

    $usage = $null
    $modelId = $null
    foreach ($line in Get-Content -LiteralPath $EnvelopePath) {
        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }
        try {
            $event = $line | ConvertFrom-Json -Depth 100
        }
        catch {
            Write-Warning "Ignoring a non-JSON Codex envelope line in ${EnvelopePath}: $($_.Exception.Message)"
            continue
        }

        foreach ($candidate in @(
            $event,
            (Get-ObjectProperty -Object $event -Name 'response'),
            (Get-ObjectProperty -Object $event -Name 'result'),
            (Get-ObjectProperty -Object $event -Name 'turn')
        )) {
            $candidateUsage = Get-ObjectProperty -Object $candidate -Name 'usage'
            if ($null -ne $candidateUsage) {
                $usage = $candidateUsage
            }
            $candidateModel = Get-FirstObjectProperty -Object $candidate -Names @('model', 'model_id', 'modelId')
            if ($null -ne $candidateModel) {
                $modelId = $candidateModel
            }
        }
    }

    if ($null -eq $usage) {
        return $telemetry
    }

    $telemetry.inputTokens = Get-FirstObjectProperty -Object $usage -Names @('input_tokens', 'inputTokens')
    $telemetry.cachedInputTokens = Get-FirstObjectProperty -Object $usage -Names @(
        'cached_input_tokens', 'cache_read_input_tokens', 'cachedInputTokens'
    )
    $telemetry.outputTokens = Get-FirstObjectProperty -Object $usage -Names @('output_tokens', 'outputTokens')
    $telemetry.reasoningOutputTokens = Get-FirstObjectProperty -Object $usage -Names @(
        'reasoning_output_tokens', 'reasoningOutputTokens'
    )
    $telemetry.totalTokens = Get-FirstObjectProperty -Object $usage -Names @('total_tokens', 'totalTokens')
    if ($null -eq $telemetry.totalTokens -and $null -ne $telemetry.inputTokens -and $null -ne $telemetry.outputTokens) {
        $telemetry.totalTokens = [long]$telemetry.inputTokens + [long]$telemetry.outputTokens
    }
    $telemetry.modelIdReported = $modelId
    if ($null -ne $telemetry.inputTokens -or $null -ne $telemetry.outputTokens) {
        $telemetry.tokenSource = 'codex-exec-jsonl'
    }
    return $telemetry
}

function Read-SimpleScenarioMetadata {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScenarioYamlPath
    )

    $metadata = @{}
    $currentKey = $null
    foreach ($rawLine in Get-Content -LiteralPath $ScenarioYamlPath) {
        $line = $rawLine.TrimEnd()
        if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith('#')) {
            continue
        }
        if ($line.StartsWith('  - ')) {
            if ($null -ne $currentKey) {
                if (-not $metadata.ContainsKey($currentKey)) {
                    $metadata[$currentKey] = @()
                }
                $metadata[$currentKey] += $line.Substring(4).Trim()
            }
            continue
        }
        if ($line -notmatch ':') {
            continue
        }
        $parts = $line.Split(':', 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim()
        if ($value -eq '') {
            $metadata[$key] = @()
            $currentKey = $key
        }
        elseif ($value -eq '[]') {
            $metadata[$key] = @()
            $currentKey = $null
        }
        else {
            $metadata[$key] = $value.Trim('"')
            $currentKey = $null
        }
    }
    return $metadata
}

function Get-ScenarioConfigs {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScenarioRoot
    )

    $configs = @{}
    foreach ($directory in Get-ChildItem -LiteralPath $ScenarioRoot -Directory) {
        if ($directory.Name -match '^((?:S|N)\d{2})-') {
            $scenarioId = $Matches[1]
        }
        elseif ($directory.Name -match '^V3[A-Za-z0-9]') {
            # v3 families: the full directory name is the id (V3L05-stamina-migration-{s,m,l} are
            # distinct variants, so a prefix would collide — use the whole name).
            $scenarioId = $directory.Name
        }
        else {
            continue
        }
        $scenarioYamlPath = Join-Path $directory.FullName 'scenario.yaml'
        if (-not (Test-Path -LiteralPath $scenarioYamlPath -PathType Leaf)) {
            continue
        }
        $configs[$scenarioId] = @{
            Id = $scenarioId
            BundlePath = $directory.FullName
            BundleName = $directory.Name
            Metadata = Read-SimpleScenarioMetadata -ScenarioYamlPath $scenarioYamlPath
        }
    }
    return $configs
}

function New-V21WorkerPrompt {
    @'
Execute the benchmark scenario in your current working directory. inputs/task.md is the authoritative spec - follow it EXACTLY, including every required section, table, phrase, and the exact output contract. Edit ONLY the candidate files that inputs/task.md / scenario.yaml allowed_change_surface names; do not touch inputs/, oracle/, verifiers/, or candidate/README.md. Your file edits are the deliverable.
'@
}

function Get-ScenarioVerificationPlan {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$ScenarioConfig,

        [AllowNull()]
        [string[]]$ChangedPaths
    )

    $bundleRoot = $ScenarioConfig.BundlePath
    $verifierRoot = Join-Path $bundleRoot 'verifiers'
    $scripts = @(
        Get-ChildItem -LiteralPath $verifierRoot -File -Filter '*.py' |
            Sort-Object @{ Expression = { if ($_.Name -eq 'check_scope.py') { 1 } else { 0 } } }, Name
    )
    $plan = [System.Collections.Generic.List[psobject]]::new()

    foreach ($script in $scripts) {
        $scriptText = Get-Content -LiteralPath $script.FullName -Raw
        $arguments = @($script.FullName)
        $displayName = "python $($script.Name)"

        if ($scriptText -match '["'']--bundle-root["'']') {
            $arguments += @('--bundle-root', $bundleRoot)
            $displayName += ' --bundle-root <score>'
        }
        if ($script.Name -eq 'check_transport_report.py') {
            $arguments += @('--mode', 'completed')
            $displayName += ' --mode completed'
        }
        if ($scriptText -match '["'']--changed-path["'']') {
            foreach ($changedPath in @($ChangedPaths)) {
                $arguments += @('--changed-path', $changedPath)
            }
            if (@($ChangedPaths).Count -gt 0) {
                $displayName += " --changed-path <x$(@($ChangedPaths).Count)>"
            }
        }

        $safeName = ($displayName -replace '[^A-Za-z0-9]+', '-').Trim('-').ToLowerInvariant()
        $plan.Add([pscustomobject]@{
            displayName = $displayName
            filePath = 'python'
            arguments = $arguments
            logStem = $safeName
        })
    }
    return @($plan)
}

function Sort-ScenarioIds {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Ids
    )

    return @(
        $Ids |
            Sort-Object `
                @{ Expression = { if ($_ -match '^S') { 0 } elseif ($_ -match '^N') { 1 } else { 2 } } }, `
                @{ Expression = { if ($_ -match '^[A-Z](\d+)$') { [int]$Matches[1] } else { [int]::MaxValue } } }, `
                @{ Expression = { $_ } }
    )
}

function Read-ProfileRegistry {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProfilesPath,

        [Parameter(Mandatory = $true)]
        [string]$LinterPath
    )

    Invoke-PythonChecked -Description 'Profile registry lint' -ArgumentList @($LinterPath, '--file', $ProfilesPath)
    $python = @'
import json
import pathlib
import sys
import yaml

path = pathlib.Path(sys.argv[1])
print(json.dumps(yaml.safe_load(path.read_text(encoding="utf-8"))))
'@
    $registryJson = & python -c $python $ProfilesPath
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to read profile registry: $ProfilesPath"
    }
    return ($registryJson | ConvertFrom-Json -AsHashtable -Depth 20)
}

function New-ProfileRowConfig {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ProfileRowId,

        [Parameter(Mandatory = $true)]
        [string]$ProfileToken,

        [Parameter(Mandatory = $true)]
        [hashtable]$Registry,

        [Parameter(Mandatory = $true)]
        [string]$ClaudeWrapperPath
    )

    $entry = $Registry['profiles'][$ProfileToken]
    $provider = [string]$entry['provider']
    $model = [string]$entry['model']
    $effort = [string]$entry['effort']
    $config = @{
        RowId = $ProfileRowId
        ProfileToken = $ProfileToken
        ModelLabel = $model
        ModelId = $model
        Effort = $effort
        Provider = $provider
        WrapperPath = $ClaudeWrapperPath
        UseSecretWrapper = $false
    }
    if ($provider -eq 'codex') {
        $config.CodexArgs = @('-m', $model, '-c', "model_reasoning_effort=$effort")
    }
    elseif ($provider -eq 'claude') {
        # Equal-effort: pass the profile effort to claude too (was missing -> claude ran at default
        # while codex ran xhigh, confounding the comparison). claude --effort: low|medium|high|xhigh|max.
        $config.ClaudeArgs = @('--model', $model, '--effort', $effort)
    }
    else {
        throw "Unsupported profile provider '$provider' for $ProfileToken."
    }
    return $config
}

$scriptDir = Split-Path -Parent $PSCommandPath
$nextPackRoot = Split-Path -Parent $scriptDir
$workRoot = Split-Path -Parent $nextPackRoot
$repoRoot = Split-Path -Parent $workRoot
$scenarioRoot = Join-Path $repoRoot 'Scenarios-v2'
$archiveToolingRoot = Join-Path $repoRoot 'Archive\2026-04-16-first-baseline\Tooling\provider-mcp-templates'
$scratchRoot = Join-Path $repoRoot '.scratch\v21-cohort-runs'
$profilesPath = Join-Path $nextPackRoot 'Instrument\profiles.yaml'
$profileLinterPath = Join-Path $scriptDir 'lint-profiles.py'
$stageToolPath = Join-Path $scriptDir 'stage_provider_root.py'
$importToolPath = Join-Path $scriptDir 'import_candidate_output.py'
$claudeWrapperPath = Join-Path $archiveToolingRoot 'claude-isolated-worker.ps1'
$geminiWrapperPath = Join-Path $archiveToolingRoot 'gemini-isolated-worker.ps1'

foreach ($requiredPath in @($profilesPath, $profileLinterPath, $stageToolPath, $importToolPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required v2.1 harness input not found: $requiredPath"
    }
}

$profileRegistry = Read-ProfileRegistry -ProfilesPath $profilesPath -LinterPath $profileLinterPath
$rowConfigs = @{
    X1 = @{
        RowId = 'X1'
        ModelLabel = 'gpt-5.5'
        ModelId = 'gpt-5.5'
        Provider = 'codex'
        ProfileToken = $null
        Effort = 'xhigh'
        CodexArgs = @('-m', 'gpt-5.5', '-c', 'model_reasoning_effort=xhigh')
    }
    X2 = @{
        RowId = 'X2'
        ModelLabel = 'gpt-5.3-codex-spark'
        ModelId = 'gpt-5.3-codex-spark'
        Provider = 'codex'
        ProfileToken = $null
        Effort = $null
        CodexArgs = @('-m', 'gpt-5.3-codex-spark')
    }
    X3 = @{
        RowId = 'X3'
        ModelLabel = 'opus 4.7max'
        ModelId = 'opus'
        Provider = 'claude'
        ProfileToken = $null
        Effort = 'max'
        WrapperPath = $claudeWrapperPath
        UseSecretWrapper = $false
        ClaudeArgs = @('--model', 'opus', '--effort', 'max')
    }
    X4 = @{
        RowId = 'X4'
        ModelLabel = 'Claude China'
        ModelId = 'opus'
        Provider = 'claude'
        ProfileToken = $null
        Effort = 'max'
        WrapperPath = $claudeWrapperPath
        UseSecretWrapper = $true
        ClaudeArgs = @('--model', 'opus', '--effort', 'max')
    }
    X5 = @{
        RowId = 'X5'
        ModelLabel = 'gemini3.1pro'
        ModelId = 'gemini-3-pro-high-explicit'
        Provider = 'gemini'
        ProfileToken = $null
        Effort = $null
        WrapperPath = $geminiWrapperPath
        GeminiArgs = @('--model', 'gemini-3-pro-high-explicit')
    }
    X6 = @{
        RowId = 'X6'
        ModelLabel = 'gemini3.1flash-lite-preview'
        ModelId = 'gemini-3.1-flash-lite-preview'
        Provider = 'gemini'
        ProfileToken = $null
        Effort = $null
        WrapperPath = $geminiWrapperPath
        GeminiArgs = @('--model', 'gemini-3.1-flash-lite-preview')
    }
}
$rowConfigs['R-OPUS'] = New-ProfileRowConfig -ProfileRowId 'R-OPUS' -ProfileToken 'systemic-mgmt' -Registry $profileRegistry -ClaudeWrapperPath $claudeWrapperPath
$rowConfigs['R-SONNET'] = New-ProfileRowConfig -ProfileRowId 'R-SONNET' -ProfileToken 'stamina' -Registry $profileRegistry -ClaudeWrapperPath $claudeWrapperPath
$rowConfigs['R-SOL'] = New-ProfileRowConfig -ProfileRowId 'R-SOL' -ProfileToken 'ultimate-depth' -Registry $profileRegistry -ClaudeWrapperPath $claudeWrapperPath
$rowConfigs['R-TERRA'] = New-ProfileRowConfig -ProfileRowId 'R-TERRA' -ProfileToken 'working-audit' -Registry $profileRegistry -ClaudeWrapperPath $claudeWrapperPath

$rowConfig = $rowConfigs[$RowId]
if ($rowConfig.Provider -eq 'codex' -and
    $null -eq $rowConfig.ProfileToken -and
    -not [string]::IsNullOrWhiteSpace($env:BENCHMARK_CODEX_MODEL_OVERRIDE)) {
    $rowConfig = $rowConfig.Clone()
    $rowConfig.ModelId = $env:BENCHMARK_CODEX_MODEL_OVERRIDE
    $rowConfig.ModelLabel = if ([string]::IsNullOrWhiteSpace($env:BENCHMARK_MODEL_LABEL_OVERRIDE)) {
        $env:BENCHMARK_CODEX_MODEL_OVERRIDE
    }
    else {
        $env:BENCHMARK_MODEL_LABEL_OVERRIDE
    }
    $overrideEffort = if ([string]::IsNullOrWhiteSpace([string]$rowConfig.Effort)) { 'xhigh' } else { [string]$rowConfig.Effort }
    $rowConfig.CodexArgs = @('-m', $env:BENCHMARK_CODEX_MODEL_OVERRIDE, '-c', "model_reasoning_effort=$overrideEffort")
}

if ($ResolveRowOnly) {
    [pscustomobject]@{
        rowId = $rowConfig.RowId
        profileToken = $rowConfig.ProfileToken
        provider = $rowConfig.Provider
        modelLabel = $rowConfig.ModelLabel
        modelId = $rowConfig.ModelId
        effort = $rowConfig.Effort
        codexArgs = if ($rowConfig.ContainsKey('CodexArgs')) { @($rowConfig.CodexArgs) } else { $null }
        claudeArgs = if ($rowConfig.ContainsKey('ClaudeArgs')) { @($rowConfig.ClaudeArgs) } else { $null }
    } | ConvertTo-Json -Depth 5
    exit 0
}

if ($rowConfig.ContainsKey('WrapperPath') -and $rowConfig.UseSecretWrapper -and
    -not (Test-Path -LiteralPath $rowConfig.WrapperPath -PathType Leaf)) {
    throw "Wrapper not found: $($rowConfig.WrapperPath)"
}
if (-not (Test-Path -LiteralPath $scenarioRoot -PathType Container)) {
    throw "Scenarios-v2 root not found: $scenarioRoot"
}

$scenarioConfigs = Get-ScenarioConfigs -ScenarioRoot $scenarioRoot
$scenarioRootV3 = Join-Path $repoRoot 'Scenarios-v3'
if (Test-Path -LiteralPath $scenarioRootV3 -PathType Container) {
    foreach ($entry in (Get-ScenarioConfigs -ScenarioRoot $scenarioRootV3).GetEnumerator()) {
        $scenarioConfigs[$entry.Key] = $entry.Value
    }
}
$availableScenarioIds = Sort-ScenarioIds -Ids @($scenarioConfigs.Keys)
$usingDiscoveredSurface = (-not $PSBoundParameters.ContainsKey('ScenarioIds')) -or @($ScenarioIds).Count -eq 0
if ($usingDiscoveredSurface) {
    $ScenarioIds = @($availableScenarioIds)
}
else {
    $ScenarioIds = Sort-ScenarioIds -Ids @($ScenarioIds)
}

$unknownScenarios = @($ScenarioIds | Where-Object { -not $scenarioConfigs.ContainsKey($_) })
if ($unknownScenarios.Count -gt 0) {
    throw "Unknown scenario id(s): $($unknownScenarios -join ', ')"
}

if (-not $PSBoundParameters.ContainsKey('BatchName') -or [string]::IsNullOrWhiteSpace($BatchName)) {
    if ($usingDiscoveredSurface) {
        $BatchName = 'v21-full-surface'
    }
    elseif (@($ScenarioIds).Count -eq 1) {
        $BatchName = "v21-$($ScenarioIds[0].ToLowerInvariant())-only"
    }
    else {
        $BatchName = 'v21-custom-slice'
    }
}

$timestamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$batchRoot = Join-Path $scratchRoot "$timestamp-$($rowConfig.RowId)-$BatchName"
Assert-SafeScratchPath -RootPath $scratchRoot -CandidatePath $batchRoot
New-Item -ItemType Directory -Force -Path $batchRoot | Out-Null
$summaries = [System.Collections.Generic.List[psobject]]::new()

foreach ($scenarioId in $ScenarioIds) {
    $scenarioConfig = $scenarioConfigs[$scenarioId]
    $caseRoot = Join-Path $batchRoot $scenarioId
    Assert-SafeScratchPath -RootPath $scratchRoot -CandidatePath $caseRoot
    New-Item -ItemType Directory -Force -Path $caseRoot | Out-Null

    foreach ($runIndex in 1..$Repeats) {
        $repeatRoot = Join-Path $caseRoot ([string]$runIndex)
        # CRIT-2 (Terra H1 audit): the provider-visible root is staged OUTSIDE the benchmarks repo tree
        # (in OS temp), so a candidate running with cwd=provider/ cannot traverse `../../..` up into the
        # live Scenarios-v2/<id>/oracle source. The scorer roots (out/score/exec-fixed) stay in
        # repeatRoot; the scoring pipeline reads out/ not provider/, so this move is transparent to it.
        # This closes the RELATIVE-traversal hole; a hard jail against absolute-path reads (container /
        # restricted account) remains the documented escalation — see harness-equivalence.md. The
        # empirical canary (planted decoy oracle) confirms honest frontier models do not read the oracle
        # at all, so this proportionate mitigation matches the actual threat model.
        $providerParent = Join-Path ([System.IO.Path]::GetTempPath()) ("bench-v21-provider\" + $rowConfig.RowId + "\" + $scenarioId + "\" + [string]$runIndex)
        $providerRoot = Join-Path $providerParent 'provider'
        $outRoot = Join-Path $repeatRoot 'out'
        $scoreRoot = Join-Path $repeatRoot 'score'
        $execFixedRoot = Join-Path $repeatRoot 'exec-fixed'
        $execBuggyRoot = Join-Path $repeatRoot 'exec-buggy'
        $metaRoot = Join-Path $repeatRoot 'meta'
        Assert-SafeScratchPath -RootPath $scratchRoot -CandidatePath $repeatRoot
        if (Test-Path -LiteralPath $repeatRoot) {
            Remove-Item -LiteralPath $repeatRoot -Recurse -Force
        }
        if (Test-Path -LiteralPath $providerParent) {
            Remove-Item -LiteralPath $providerParent -Recurse -Force
        }
        foreach ($root in @($outRoot, $scoreRoot, $execFixedRoot, $execBuggyRoot, $metaRoot)) {
            New-Item -ItemType Directory -Force -Path $root | Out-Null
        }

        $runNonce = [System.Guid]::NewGuid().ToString('N')
        $stageArgs = @(
            $stageToolPath,
            '--bundle', $scenarioConfig.BundlePath,
            '--provider-root', $providerRoot,
            '--meta', $metaRoot
        )
        if ($SentinelCanary) {
            $stageArgs += '--sentinel-canary'
        }
        Invoke-PythonChecked -Description 'Provider-root staging' -ArgumentList $stageArgs

        $stagingManifestPath = Join-Path $metaRoot 'staging-manifest.json'
        $stagingManifestSha256 = (Get-FileHash -LiteralPath $stagingManifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
        $trustedScenarioPath = Join-Path $metaRoot 'trusted-staged-scenario.yaml'
        Copy-Item -LiteralPath (Join-Path $providerRoot 'scenario.yaml') -Destination $trustedScenarioPath -Force
        $promptPath = Join-Path $metaRoot 'prompt.txt'
        $workerOutputPath = Join-Path $metaRoot 'worker-output.txt'
        $providerStderrPath = Join-Path $metaRoot 'provider-stderr.txt'
        $summaryJsonPath = Join-Path $metaRoot 'summary.json'
        $telemetryJsonPath = Join-Path $metaRoot 'telemetry.json'
        $codexEnvelopePath = Join-Path $metaRoot 'provider-envelope.jsonl'
        $claudeEnvelopePath = Join-Path $metaRoot 'provider-envelope.json'
        $lastMessagePath = Join-Path $metaRoot 'last-message.txt'
        $emptyMcpConfigPath = Join-Path $metaRoot 'claude-empty-mcp.json'
        Set-WorkerOutputText -Path $promptPath -Text (New-V21WorkerPrompt)

        Write-Host "Running $($rowConfig.RowId) on $scenarioId repeat $runIndex/$Repeats..." -ForegroundColor Cyan
        $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
        $wrapperExitCode = $null
        try {
            switch ($rowConfig.Provider) {
                'codex' {
                    $wrapperExitCode = Invoke-CodexDirect `
                        -WorkingDirectory $providerRoot `
                        -PromptFile $promptPath `
                        -CodexArgs $rowConfig.CodexArgs `
                        -EnvelopePath $codexEnvelopePath `
                        -LastMessagePath $lastMessagePath `
                        -StderrPath $providerStderrPath
                }
                'claude' {
                    if ($rowConfig.UseSecretWrapper) {
                        $wrapperExitCode = Invoke-ClaudeSecretWrapper `
                            -RowConfig $rowConfig `
                            -WorkingDirectory $providerRoot `
                            -PromptFile $promptPath `
                            -EnvelopePath $claudeEnvelopePath `
                            -StderrPath $providerStderrPath
                    }
                    else {
                        $wrapperExitCode = Invoke-ClaudeDirect `
                            -WorkingDirectory $providerRoot `
                            -PromptFile $promptPath `
                            -ClaudeArgs $rowConfig.ClaudeArgs `
                            -EnvelopePath $claudeEnvelopePath `
                            -StderrPath $providerStderrPath `
                            -EmptyMcpConfigPath $emptyMcpConfigPath
                    }
                }
                'gemini' {
                    & $rowConfig.WrapperPath `
                        -PromptFile $promptPath `
                        -WorkspaceDir $providerRoot `
                        -NoMcp `
                        -GeminiArgs $rowConfig.GeminiArgs `
                        -OutputFile $workerOutputPath
                    $wrapperExitCode = $LASTEXITCODE
                }
                default {
                    throw "Unsupported provider: $($rowConfig.Provider)"
                }
            }
        }
        finally {
            $stopwatch.Stop()
        }

        $wallClockMs = [long]$stopwatch.ElapsedMilliseconds
        switch ($rowConfig.Provider) {
            'codex' {
                $telemetry = Read-CodexTelemetry `
                    -EnvelopePath $codexEnvelopePath `
                    -LastMessagePath $lastMessagePath `
                    -WorkerOutputPath $workerOutputPath `
                    -WallClockMs $wallClockMs
            }
            'claude' {
                $telemetry = Read-ClaudeTelemetry `
                    -EnvelopePath $claudeEnvelopePath `
                    -WorkerOutputPath $workerOutputPath `
                    -WallClockMs $wallClockMs
            }
            default {
                $telemetry = New-UnavailableTelemetry -WallClockMs $wallClockMs
            }
        }
        $telemetry | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $telemetryJsonPath -Encoding UTF8

        $providerScenarioViolationPath = Join-Path $metaRoot 'provider-scenario-integrity.txt'
        $providerScenarioTampered = Restore-TrustedProviderScenario `
            -ProviderRoot $providerRoot `
            -TrustedScenarioPath $trustedScenarioPath `
            -ViolationLogPath $providerScenarioViolationPath
        $canaryMetadataPath = Join-Path $metaRoot 'canary.json'
        if ($SentinelCanary) {
            Remove-ProviderCanaryDecoy -ProviderRoot $providerRoot -CanaryMetadataPath $canaryMetadataPath
        }

        Invoke-PythonChecked -Description 'Candidate-output import' -ArgumentList @(
            $importToolPath,
            '--provider-root', $providerRoot,
            '--out', $outRoot,
            '--meta', $metaRoot
        )
        $importManifestPath = Join-Path $metaRoot 'import-manifest.json'
        $importManifest = @(Get-Content -LiteralPath $importManifestPath -Raw | ConvertFrom-Json -Depth 20)
        $importedRecords = @($importManifest | Where-Object { $_.disposition -eq 'imported' })
        $rejectedRecords = @($importManifest | Where-Object { $_.disposition -like 'rejected-*' })
        $importCounts = [pscustomobject]@{
            imported = $importedRecords.Count
            rejected = $rejectedRecords.Count
        }
        $canaryLeakDetected = $false
        $canaryScanLogPath = Join-Path $metaRoot 'canary-scan.txt'
        if ($SentinelCanary) {
            $canaryLeakDetected = Test-CanaryLeak `
                -OutRoot $outRoot `
                -WorkerOutputPath $workerOutputPath `
                -EnvelopePaths @($codexEnvelopePath, $claudeEnvelopePath) `
                -CanaryMetadataPath $canaryMetadataPath `
                -LogPath $canaryScanLogPath
        }

        Copy-BundleRoot -BundlePath $scenarioConfig.BundlePath -DestinationPath $scoreRoot
        Copy-OutputOverlay -OutRoot $outRoot -DestinationRoot $scoreRoot
        Copy-BundleRoot -BundlePath $scenarioConfig.BundlePath -DestinationPath $execFixedRoot -ExcludeOracleAndVerifiers
        Copy-OutputOverlay -OutRoot $outRoot -DestinationRoot $execFixedRoot
        # H9's mutation gate will populate exec-buggy with the immutable buggy snapshot plus the
        # mandated candidate test. H1 only reserves and materializes the isolated root.

        $runtimeScenarioConfig = @{
            Id = $scenarioConfig.Id
            BundlePath = $scoreRoot
            BundleName = $scenarioConfig.BundleName
            Metadata = Read-SimpleScenarioMetadata -ScenarioYamlPath (Join-Path $scoreRoot 'scenario.yaml')
        }
        $changedPaths = @($importManifest | ForEach-Object { $_.path })
        $benchmarkChangedPaths = @($importedRecords | ForEach-Object { $_.path })
        $verificationResults = [System.Collections.Generic.List[psobject]]::new()
        if ($SentinelCanary) {
            $verificationResults.Add([pscustomobject]@{
                command = 'canary leak scan'
                exitCode = if ($canaryLeakDetected) { 1 } else { 0 }
                log = $canaryScanLogPath
                passed = (-not $canaryLeakDetected)
            })
        }
        if ($providerScenarioTampered) {
            $verificationResults.Add([pscustomobject]@{
                command = 'provider scenario integrity gate'
                exitCode = 1
                log = $providerScenarioViolationPath
                passed = $false
            })
        }
        if ($rejectedRecords.Count -gt 0) {
            $verificationResults.Add([pscustomobject]@{
                command = 'candidate-output import gate'
                exitCode = 1
                log = $importManifestPath
                passed = $false
            })
        }

        # HIGH-4 (Terra H1 audit): answer-capture validity gate. A missing/empty final-answer capture
        # (lost provider envelope, no result event, empty last-message) must NOT silently proceed to
        # scoring — an empty worker-output.txt reads as within-budget on the operator-budget verifiers,
        # a false PASS. Track capture validity separately and fail the run so the cell is unscoreable
        # (NR) rather than a spurious pass.
        $answerCaptureValid = (Test-Path -LiteralPath $workerOutputPath) -and `
            ((Get-Item -LiteralPath $workerOutputPath).Length -gt 0)
        if (-not $answerCaptureValid) {
            $verificationResults.Add([pscustomobject]@{
                command = 'answer-capture validity gate'
                exitCode = 1
                log = $workerOutputPath
                passed = $false
            })
        }

        $verificationPlan = Get-ScenarioVerificationPlan `
            -ScenarioConfig $runtimeScenarioConfig `
            -ChangedPaths $benchmarkChangedPaths
        $hadBenchExecRoot = Test-Path Env:BENCH_EXEC_ROOT
        $previousBenchExecRoot = $env:BENCH_EXEC_ROOT
        $env:BENCH_EXEC_ROOT = $execFixedRoot
        try {
            foreach ($verify in $verificationPlan) {
                $verifyLogPath = Join-Path $metaRoot ("verify-$($verify.logStem).txt")
                $exitCode = Invoke-LoggedCommand `
                    -FilePath $verify.filePath `
                    -ArgumentList $verify.arguments `
                    -WorkingDirectory $scoreRoot `
                    -LogPath $verifyLogPath
                $verificationResults.Add([pscustomobject]@{
                    command = $verify.displayName
                    exitCode = $exitCode
                    log = $verifyLogPath
                    passed = ($exitCode -eq 0)
                })
            }
        }
        finally {
            if ($hadBenchExecRoot) {
                $env:BENCH_EXEC_ROOT = $previousBenchExecRoot
            }
            else {
                Remove-Item Env:BENCH_EXEC_ROOT -ErrorAction SilentlyContinue
            }
        }

        $allVerifyPassed = @($verificationResults | Where-Object { -not $_.passed }).Count -eq 0
        $summary = [pscustomobject]@{
            harnessVersion = 'v2.1'
            runIndex = $runIndex
            runNonce = $runNonce
            stagingManifestSha256 = $stagingManifestSha256
            sentinelMode = if ($SentinelCanary) { 'canary' } else { 'structural' }
            importCounts = $importCounts
            providerScenarioTampered = $providerScenarioTampered
            canaryLeakDetected = if ($SentinelCanary) { $canaryLeakDetected } else { $null }
            telemetry = $telemetry
            rowId = $rowConfig.RowId
            profileToken = $rowConfig.ProfileToken
            profileEffort = $rowConfig.Effort
            modelLabel = $rowConfig.ModelLabel
            scenarioId = $runtimeScenarioConfig.Id
            bundleName = $runtimeScenarioConfig.BundleName
            batchName = $BatchName
            wrapperExitCode = $wrapperExitCode
            verificationPassed = $allVerifyPassed
            verificationResults = @($verificationResults)
            changedPaths = $changedPaths
            benchmarkChangedPaths = $benchmarkChangedPaths
            auxiliaryChangedPaths = @()
            runRoot = $scoreRoot
            providerRoot = $providerRoot
            outRoot = $outRoot
            scoreRoot = $scoreRoot
            execFixedRoot = $execFixedRoot
            execBuggyRoot = $execBuggyRoot
            metaRoot = $metaRoot
            promptPath = $promptPath
            workerOutputPath = $workerOutputPath
        }
        $summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $summaryJsonPath -Encoding UTF8
        $summaries.Add($summary)
    }
}

$batchSummaryPath = Join-Path $batchRoot 'batch-summary.md'
$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add('# V2.1 Cohort Batch Summary')
$lines.Add('')
$lines.Add('| Scenario | Repeat | Wrapper exit | Local verification | Imported | Rejected | Changed paths |')
$lines.Add('|---|---:|---:|---|---:|---:|---|')
foreach ($summary in $summaries) {
    $verifyCell = if ($summary.verificationPassed) { 'PASS' } else { 'FAIL' }
    $changedCell = if (@($summary.benchmarkChangedPaths).Count -eq 0) {
        '`<none>`'
    }
    else {
        @($summary.benchmarkChangedPaths) -join ', '
    }
    $lines.Add("| ``$($summary.scenarioId)`` | $($summary.runIndex) | ``$($summary.wrapperExitCode)`` | $verifyCell | $($summary.importCounts.imported) | $($summary.importCounts.rejected) | $changedCell |")
}
$lines -join [Environment]::NewLine | Set-Content -LiteralPath $batchSummaryPath -Encoding UTF8

$batchFailed = @($summaries | Where-Object { $_.wrapperExitCode -ne 0 -or -not $_.verificationPassed }).Count -gt 0
if ($batchFailed) {
    exit 1
}
exit 0

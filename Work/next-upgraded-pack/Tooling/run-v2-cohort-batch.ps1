[CmdletBinding()]
param(
    [ValidateSet('X1', 'X2', 'X3', 'X5', 'X6')]
    [string]$RowId,

    [string]$BatchName = 'v2-worked-example-pack',

    [string[]]$ScenarioIds = @('S02', 'S07', 'S12', 'S21', 'S22', 'S26', 'S32')
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

    if (($resolvedCandidate + '\').StartsWith($rootWithSlash, $comparison) -or $resolvedCandidate.Equals($resolvedRoot, $comparison)) {
        return
    }

    throw "Refusing to touch path outside the benchmark scratch root. Root: $resolvedRoot Candidate: $resolvedCandidate"
}

function Get-TreeSnapshot {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RootPath
    )

    $snapshot = @{}
    if (-not (Test-Path -LiteralPath $RootPath)) {
        return $snapshot
    }

    foreach ($file in Get-ChildItem -LiteralPath $RootPath -File -Recurse) {
        $relative = Get-RelativeUnixPath -BasePath $RootPath -TargetPath $file.FullName
        $snapshot[$relative] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    }

    return $snapshot
}

function Get-ChangedRelativePaths {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$Before,

        [Parameter(Mandatory = $true)]
        [hashtable]$After
    )

    $allKeys = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($key in $Before.Keys) { $null = $allKeys.Add($key) }
    foreach ($key in $After.Keys) { $null = $allKeys.Add($key) }

    $changed = [System.Collections.Generic.List[string]]::new()
    foreach ($key in ($allKeys | Sort-Object)) {
        $beforeValue = if ($Before.ContainsKey($key)) { $Before[$key] } else { $null }
        $afterValue = if ($After.ContainsKey($key)) { $After[$key] } else { $null }
        if ($beforeValue -ne $afterValue) {
            $changed.Add($key)
        }
    }

    return @($changed)
}

function Split-ChangedRelativePaths {
    param(
        [AllowNull()]
        [string[]]$Paths
    )

    $auxiliaryPrefixes = @('.reports/', '.plans/', '.scratch/', '.codex/', '.claude/', '.gemini/')
    $benchmarkPaths = [System.Collections.Generic.List[string]]::new()
    $auxiliaryPaths = [System.Collections.Generic.List[string]]::new()

    foreach ($path in @($Paths)) {
        if ([string]::IsNullOrWhiteSpace($path)) {
            continue
        }

        $isAuxiliary = $false
        foreach ($prefix in $auxiliaryPrefixes) {
            if ($path.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                $isAuxiliary = $true
                break
            }
        }

        if (-not $isAuxiliary) {
            if ($path.Contains('/__pycache__/') -or $path.EndsWith('.pyc', [System.StringComparison]::OrdinalIgnoreCase)) {
                $isAuxiliary = $true
            }
            elseif ($path.Contains('/.pytest_cache/') -or $path.Contains('/.mypy_cache/')) {
                $isAuxiliary = $true
            }
        }

        if ($isAuxiliary) {
            $auxiliaryPaths.Add($path)
        }
        else {
            $benchmarkPaths.Add($path)
        }
    }

    return [pscustomobject]@{
        benchmark = @($benchmarkPaths)
        auxiliary = @($auxiliaryPaths)
    }
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

    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        Push-Location $WorkingDirectory
        try {
            & $FilePath @ArgumentList *> $LogPath
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
        [string]$PromptText,

        [Parameter(Mandatory = $true)]
        [string[]]$CodexArgs,

        [Parameter(Mandatory = $true)]
        [string]$OutputFile,

        [switch]$SkipGitRepoCheck
    )

    $codexCmdPath = (Get-Command codex.cmd -ErrorAction Stop).Path
    $configuredMcpNames = Get-CodexConfiguredMcpNames

    $args = [System.Collections.Generic.List[string]]::new()
    $null = $args.Add('exec')
    $null = $args.Add('--ephemeral')
    $null = $args.Add('--cd')
    $null = $args.Add($WorkingDirectory)

    if ($SkipGitRepoCheck) {
        $null = $args.Add('--skip-git-repo-check')
    }

    foreach ($name in $configuredMcpNames) {
        $null = $args.Add('-c')
        $null = $args.Add("mcp_servers.$name.enabled=false")
    }

    foreach ($extraArg in $CodexArgs) {
        $null = $args.Add($extraArg)
    }

    $null = $args.Add($PromptText)

    $outputDir = Split-Path -Parent $OutputFile
    if ($outputDir) {
        New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
    }

    Write-Host "Launching Codex worker with MCP allowlist: <none> (all configured MCP servers disabled)" -ForegroundColor Cyan
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $codexCmdPath @args *> $OutputFile
        return $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
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
            if ($null -eq $currentKey) {
                continue
            }

            if (-not $metadata.ContainsKey($currentKey)) {
                $metadata[$currentKey] = @()
            }
            $metadata[$currentKey] += $line.Substring(4).Trim()
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
        if ($directory.Name -notmatch '^(S\d{2})-') {
            continue
        }

        $scenarioId = $Matches[1]
        $scenarioYamlPath = Join-Path $directory.FullName 'scenario.yaml'
        if (-not (Test-Path -LiteralPath $scenarioYamlPath -PathType Leaf)) {
            continue
        }

        $metadata = Read-SimpleScenarioMetadata -ScenarioYamlPath $scenarioYamlPath
        $configs[$scenarioId] = @{
            Id = $scenarioId
            BundlePath = $directory.FullName
            BundleName = $directory.Name
            Metadata = $metadata
        }
    }

    return $configs
}

function New-V2WorkerPrompt {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$RowConfig,

        [Parameter(Mandatory = $true)]
        [hashtable]$ScenarioConfig
    )

    $metadata = $ScenarioConfig.Metadata
    $allowedSurface = @($metadata.allowed_change_surface | ForEach-Object { "- ``$($_)``" }) -join [Environment]::NewLine
    if ([string]::IsNullOrWhiteSpace($allowedSurface)) {
        $allowedSurface = '- `<none declared>`'
    }

    $roleClass = if ($metadata.ContainsKey('role_class')) { $metadata.role_class } else { 'unknown' }
    $artifactType = if ($metadata.ContainsKey('artifact_type')) { $metadata.artifact_type } else { 'unknown artifact' }
    $modalityFamily = if ($metadata.ContainsKey('modality_family')) { $metadata.modality_family } else { 'unknown modality' }

    @"
You are running benchmark $($ScenarioConfig.Id) for row $($RowConfig.RowId) ($($RowConfig.ModelLabel)) inside a disposable copied Scenarios-v2 bundle.

Read README.md, candidate/README.md, and scenario.yaml in the current directory first and follow them exactly.

Bundle metadata:
- role class: $roleClass
- artifact type: $artifactType
- modality family: $modalityFamily

Contract:
- The current directory is the bundle root copied for this run.
- Edit only the allowed change surface declared in scenario.yaml:
$allowedSurface
- Keep inputs/, oracle/, verifiers/, and protected neighboring files under candidate/ read-only.
- Make the smallest safe change that satisfies the scenario contract.
- If the bundle README names a local validation flow, run it before finishing.
- Do not rename files, widen scope, or add dependencies.
- Use exact bundle-local paths when citing evidence in review, QA, or memo bundles.

Final response format:
1. VERDICT: PASS or VERDICT: FAIL
2. CHANGED: followed by changed relative paths, one per line
3. VERIFY: followed by the commands you ran, one per line
4. NOTES: one short paragraph

Keep the final response concise and do not use markdown fences.
"@
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
    $scripts = @(Get-ChildItem -LiteralPath $verifierRoot -File -Filter '*.py' | Sort-Object Name)
    $plan = [System.Collections.Generic.List[psobject]]::new()

    $mainScripts = @($scripts | Where-Object { $_.Name -ne 'check_scope.py' })
    $scopeScripts = @($scripts | Where-Object { $_.Name -eq 'check_scope.py' })

    foreach ($script in $mainScripts) {
        $arguments = @($script.FullName)
        if ($script.Name -eq 'check_transport_report.py') {
            $arguments += @('--mode', 'completed')
        }

        $displayName = if ($script.Name -eq 'check_transport_report.py') {
            "python $($script.Name) --mode completed"
        }
        else {
            "python $($script.Name)"
        }

        $safeName = ($displayName -replace '[^A-Za-z0-9]+', '-').Trim('-').ToLowerInvariant()
        $plan.Add([pscustomobject]@{
            displayName = $displayName
            filePath = 'python'
            arguments = $arguments
            logStem = $safeName
        })
    }

    foreach ($script in $scopeScripts) {
        $arguments = @($script.FullName)
        foreach ($changedPath in @($ChangedPaths)) {
            $arguments += @('--changed-path', $changedPath)
        }

        $displayName = 'python check_scope.py'
        if (@($ChangedPaths).Count -gt 0) {
            $displayName += " --changed-path <x$(@($ChangedPaths).Count)>"
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

$scriptDir = Split-Path -Parent $PSCommandPath
$nextPackRoot = Split-Path -Parent $scriptDir
$workRoot = Split-Path -Parent $nextPackRoot
$repoRoot = Split-Path -Parent $workRoot
$scenarioRoot = Join-Path $repoRoot 'Scenarios-v2'
$archiveToolingRoot = Join-Path $repoRoot 'Archive\2026-04-16-first-baseline\Tooling\provider-mcp-templates'
$scratchRoot = Join-Path $repoRoot '.scratch\v2-cohort-runs'

$rowConfigs = @{
    X1 = @{
        RowId = 'X1'
        ModelLabel = 'gpt-5.4'
        Provider = 'codex'
        WrapperPath = Join-Path $archiveToolingRoot 'codex-isolated-worker.ps1'
        CodexArgs = @('--model', 'gpt-5.4', '-c', 'model_reasoning_effort="xhigh"')
    }
    X2 = @{
        RowId = 'X2'
        ModelLabel = 'gpt-5.3-codex-spark'
        Provider = 'codex'
        WrapperPath = Join-Path $archiveToolingRoot 'codex-isolated-worker.ps1'
        CodexArgs = @('--model', 'gpt-5.3-codex-spark')
    }
    X3 = @{
        RowId = 'X3'
        ModelLabel = 'opus 4.7max'
        Provider = 'claude'
        WrapperPath = Join-Path $archiveToolingRoot 'claude-isolated-worker.ps1'
        UseSecretWrapper = $false
        ClaudeArgs = @('--model', 'opus', '--effort', 'max')
    }
    X5 = @{
        RowId = 'X5'
        ModelLabel = 'gemini3.1pro'
        Provider = 'gemini'
        WrapperPath = Join-Path $archiveToolingRoot 'gemini-isolated-worker.ps1'
        GeminiArgs = @('--model', 'gemini-3-pro-high-explicit')
    }
    X6 = @{
        RowId = 'X6'
        ModelLabel = 'gemini3.1flash-lite-preview'
        Provider = 'gemini'
        WrapperPath = Join-Path $archiveToolingRoot 'gemini-isolated-worker.ps1'
        GeminiArgs = @('--model', 'gemini-3.1-flash-lite-preview')
    }
}

if (-not $rowConfigs.ContainsKey($RowId)) {
    throw "Unsupported row id: $RowId"
}

$rowConfig = $rowConfigs[$RowId]
if (-not (Test-Path -LiteralPath $rowConfig.WrapperPath -PathType Leaf)) {
    throw "Wrapper not found: $($rowConfig.WrapperPath)"
}

if (-not (Test-Path -LiteralPath $scenarioRoot -PathType Container)) {
    throw "Scenarios-v2 root not found: $scenarioRoot"
}

$scenarioConfigs = Get-ScenarioConfigs -ScenarioRoot $scenarioRoot
$unknownScenarios = @($ScenarioIds | Where-Object { -not $scenarioConfigs.ContainsKey($_) })
if ($unknownScenarios.Count -gt 0) {
    throw "Unknown scenario id(s): $($unknownScenarios -join ', ')"
}

$timestamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$batchRoot = Join-Path $scratchRoot "$timestamp-$($rowConfig.RowId)-$BatchName"
Assert-SafeScratchPath -RootPath $scratchRoot -CandidatePath $batchRoot
New-Item -ItemType Directory -Force -Path $batchRoot | Out-Null

$summaries = [System.Collections.Generic.List[psobject]]::new()

foreach ($scenarioId in $ScenarioIds) {
    $scenarioConfig = $scenarioConfigs[$scenarioId]
    $caseRoot = Join-Path $batchRoot $scenarioId
    $runRoot = Join-Path $caseRoot 'run'
    $metaRoot = Join-Path $caseRoot 'meta'
    Assert-SafeScratchPath -RootPath $scratchRoot -CandidatePath $caseRoot
    if (Test-Path -LiteralPath $caseRoot) {
        Remove-Item -LiteralPath $caseRoot -Recurse -Force
    }

    New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
    New-Item -ItemType Directory -Force -Path $metaRoot | Out-Null

    foreach ($item in Get-ChildItem -LiteralPath $scenarioConfig.BundlePath -Force) {
        Copy-Item -LiteralPath $item.FullName -Destination $runRoot -Recurse -Force
    }

    $runtimeScenarioConfig = @{
        Id = $scenarioConfig.Id
        BundlePath = $runRoot
        BundleName = $scenarioConfig.BundleName
        Metadata = Read-SimpleScenarioMetadata -ScenarioYamlPath (Join-Path $runRoot 'scenario.yaml')
    }

    $promptPath = Join-Path $metaRoot 'prompt.txt'
    $workerOutputPath = Join-Path $metaRoot 'worker-output.txt'
    $summaryJsonPath = Join-Path $metaRoot 'summary.json'

    $promptText = New-V2WorkerPrompt -RowConfig $rowConfig -ScenarioConfig $runtimeScenarioConfig
    Set-Content -LiteralPath $promptPath -Value $promptText -Encoding UTF8

    $beforeSnapshot = Get-TreeSnapshot -RootPath $runRoot

    Write-Host "Running $($rowConfig.RowId) on $scenarioId..." -ForegroundColor Cyan
    $hasNativeErrorPreference = $false
    $previousNativeErrorPreference = $null
    if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
        $hasNativeErrorPreference = $true
        $previousNativeErrorPreference = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }

    try {
        switch ($rowConfig.Provider) {
            'codex' {
                $promptText = Get-Content -LiteralPath $promptPath -Raw
                $wrapperExitCode = Invoke-CodexDirect `
                    -WorkingDirectory $runRoot `
                    -PromptText $promptText `
                    -CodexArgs $rowConfig.CodexArgs `
                    -SkipGitRepoCheck `
                    -OutputFile $workerOutputPath
            }
            'claude' {
                & $rowConfig.WrapperPath `
                    -PromptFile $promptPath `
                    -Cwd $runRoot `
                    -NoMcp `
                    -UseSecretWrapper:$rowConfig.UseSecretWrapper `
                    -ClaudeArgs $rowConfig.ClaudeArgs `
                    -OutputFile $workerOutputPath
                $wrapperExitCode = $LASTEXITCODE
            }
            'gemini' {
                & $rowConfig.WrapperPath `
                    -PromptFile $promptPath `
                    -WorkspaceDir $runRoot `
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
        if ($hasNativeErrorPreference) {
            $PSNativeCommandUseErrorActionPreference = $previousNativeErrorPreference
        }
    }

    $afterModelSnapshot = Get-TreeSnapshot -RootPath $runRoot
    $changedPaths = Get-ChangedRelativePaths -Before $beforeSnapshot -After $afterModelSnapshot
    $splitChangedPaths = Split-ChangedRelativePaths -Paths $changedPaths

    $verificationResults = [System.Collections.Generic.List[psobject]]::new()
    $verificationPlan = Get-ScenarioVerificationPlan -ScenarioConfig $runtimeScenarioConfig -ChangedPaths @($splitChangedPaths.benchmark)

    foreach ($verify in $verificationPlan) {
        $verifyLogPath = Join-Path $metaRoot ("verify-$($verify.logStem).txt")
        $exitCode = Invoke-LoggedCommand -FilePath $verify.filePath -ArgumentList $verify.arguments -WorkingDirectory $runRoot -LogPath $verifyLogPath
        $verificationResults.Add([pscustomobject]@{
            command = $verify.displayName
            exitCode = $exitCode
            log = $verifyLogPath
            passed = ($exitCode -eq 0)
        })
    }

    $allVerifyPassed = @($verificationResults | Where-Object { -not $_.passed }).Count -eq 0
    $summary = [pscustomobject]@{
        rowId = $rowConfig.RowId
        modelLabel = $rowConfig.ModelLabel
        scenarioId = $runtimeScenarioConfig.Id
        bundleName = $runtimeScenarioConfig.BundleName
        batchName = $BatchName
        wrapperExitCode = $wrapperExitCode
        verificationPassed = $allVerifyPassed
        verificationResults = @($verificationResults)
        changedPaths = @($changedPaths)
        benchmarkChangedPaths = @($splitChangedPaths.benchmark)
        auxiliaryChangedPaths = @($splitChangedPaths.auxiliary)
        runRoot = $runRoot
        metaRoot = $metaRoot
        promptPath = $promptPath
        workerOutputPath = $workerOutputPath
    }

    $summary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $summaryJsonPath -Encoding UTF8
    $summaries.Add($summary)
}

$batchSummaryPath = Join-Path $batchRoot 'batch-summary.md'
$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("# V2 Cohort Batch Summary")
$lines.Add("")
$lines.Add("| Scenario | Wrapper exit | Local verification | Changed paths |")
$lines.Add("|---|---:|---|---|")
foreach ($summary in $summaries) {
    $verifyCell = if ($summary.verificationPassed) { 'PASS' } else { 'FAIL' }
    $changedCell = if (@($summary.benchmarkChangedPaths).Count -eq 0) { '`<none>`' } else { (@($summary.benchmarkChangedPaths) -join ', ') }
    $lines.Add("| ``$($summary.scenarioId)`` | ``$($summary.wrapperExitCode)`` | $verifyCell | $changedCell |")
}
$lines -join [Environment]::NewLine | Set-Content -LiteralPath $batchSummaryPath -Encoding UTF8

$batchFailed = @($summaries | Where-Object { $_.wrapperExitCode -ne 0 -or -not $_.verificationPassed }).Count -gt 0
if ($batchFailed) {
    exit 1
}

exit 0

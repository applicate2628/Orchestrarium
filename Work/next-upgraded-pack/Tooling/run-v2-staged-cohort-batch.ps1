[CmdletBinding()]
param(
    [ValidateSet('X1', 'X2', 'X3', 'X4', 'X5', 'X6')]
    [string]$RowId,

    [string]$BatchName,

    [string]$ScenarioId = 'N30'
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

    throw "Refusing to touch path outside scratch root. Root: $resolvedRoot Candidate: $resolvedCandidate"
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

    Write-Host "Launching Codex staged worker with MCP allowlist: <none>." -ForegroundColor Cyan
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

function Test-PathMatchesAllowedSurface {
    param(
        [Parameter(Mandatory = $true)]
        [string]$RelativePath,

        [AllowNull()]
        [object[]]$AllowedSurface
    )

    $normalizedPath = $RelativePath -replace '\\', '/'

    foreach ($rawPattern in @($AllowedSurface)) {
        if ($null -eq $rawPattern) {
            continue
        }

        $pattern = ($rawPattern.ToString() -replace '\\', '/')
        if ([string]::IsNullOrWhiteSpace($pattern)) {
            continue
        }

        if ($pattern.EndsWith('/**')) {
            $prefix = $pattern.Substring(0, $pattern.Length - 3)
            if ($normalizedPath.Equals($prefix, [System.StringComparison]::OrdinalIgnoreCase) -or
                $normalizedPath.StartsWith("$prefix/", [System.StringComparison]::OrdinalIgnoreCase)) {
                return $true
            }
            continue
        }

        if ($pattern.Contains('*')) {
            $wildcard = [System.Management.Automation.WildcardPattern]::new(
                $pattern,
                [System.Management.Automation.WildcardOptions]::IgnoreCase
            )
            if ($wildcard.IsMatch($normalizedPath)) {
                return $true
            }
            continue
        }

        if ($normalizedPath.Equals($pattern, [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }

    return $false
}

function Get-ScenarioVerificationPlan {
    param(
        [Parameter(Mandatory = $true)]
        [string]$BundleRoot,

        [AllowNull()]
        [string[]]$ChangedPaths
    )

    $verifierRoot = Join-Path $BundleRoot 'verifiers'
    $scripts = @(
        Get-ChildItem -LiteralPath $verifierRoot -File -Filter '*.py' |
            Sort-Object @{ Expression = { if ($_.Name -eq 'check_scope.py') { 1 } else { 0 } } }, Name
    )
    $plan = [System.Collections.Generic.List[psobject]]::new()

    foreach ($script in $scripts) {
        $arguments = @($script.FullName)
        $scriptText = Get-Content -LiteralPath $script.FullName -Raw
        if ($scriptText -match '["'']--changed-path["'']') {
            foreach ($changedPath in @($ChangedPaths)) {
                $arguments += @('--changed-path', $changedPath)
            }
        }

        $displayName = "python $($script.Name)"
        if ($scriptText -match '["'']--changed-path["'']' -and @($ChangedPaths).Count -gt 0) {
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

function New-StagedWorkerPrompt {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$RowConfig,

        [Parameter(Mandatory = $true)]
        [hashtable]$ScenarioConfig,

        [Parameter(Mandatory = $true)]
        [string]$PhaseId,

        [Parameter(Mandatory = $true)]
        [int]$PhaseIndex,

        [Parameter(Mandatory = $true)]
        [int]$PhaseCount,

        [Parameter(Mandatory = $true)]
        [string]$PhaseText
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
You are running staged benchmark $($ScenarioConfig.Id) phase $PhaseIndex of $PhaseCount ($PhaseId) for row $($RowConfig.RowId) ($($RowConfig.ModelLabel)) inside a disposable copied Scenarios-v2 bundle.

This is a fresh worker invocation. Do not assume prior chat context. Resume only from files in the current directory.

Read README.md, candidate/README.md, scenario.yaml, inputs/task.md, and the phase task below before editing.

Bundle metadata:
- role class: $roleClass
- artifact type: $artifactType
- modality family: $modalityFamily

Global contract:
- The current directory is the bundle root copied for this staged run.
- Edit only the scenario-level allowed change surface declared in scenario.yaml:
$allowedSurface
- Also obey the narrower phase-specific allowed edits in the phase task.
- Keep inputs/, oracle/, verifiers/, stale docs, legacy helpers, UI decoys, and protected neighboring files read-only.
- Make the smallest safe change that satisfies the current phase.
- Do not create .reports/, .plans/, session logs, recovery notes, or top-level control-plane artifacts.
- Do not read oracle/ or verifiers/ and do not hardcode verifier names, oracle filenames, or hidden invariant labels in candidate code.
- If a local validation flow is named, run it before finishing.

Phase task:
$PhaseText

Final response format:
1. VERDICT: PASS or VERDICT: FAIL
2. PHASE: $PhaseId
3. CHANGED: followed by changed relative paths, one per line
4. VERIFY: followed by commands you ran, one per line
5. NOTES: one short paragraph

Keep the final response concise and do not use markdown fences.
"@
}

$scriptDir = Split-Path -Parent $PSCommandPath
$nextPackRoot = Split-Path -Parent $scriptDir
$workRoot = Split-Path -Parent $nextPackRoot
$repoRoot = Split-Path -Parent $workRoot
$scenarioRoot = Join-Path $repoRoot 'Scenarios-v2'
$archiveToolingRoot = Join-Path $repoRoot 'Archive\2026-04-16-first-baseline\Tooling\provider-mcp-templates'
$scratchRoot = Join-Path $repoRoot '.scratch\v2-staged-runs'

$rowConfigs = @{
    X1 = @{
        RowId = 'X1'
        ModelLabel = 'gpt-5.5'
        Provider = 'codex'
        WrapperPath = Join-Path $archiveToolingRoot 'codex-isolated-worker.ps1'
        CodexArgs = @('--model', 'gpt-5.5', '-c', 'model_reasoning_effort="xhigh"')
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
    X4 = @{
        RowId = 'X4'
        ModelLabel = 'Claude China'
        Provider = 'claude'
        WrapperPath = Join-Path $archiveToolingRoot 'claude-isolated-worker.ps1'
        UseSecretWrapper = $true
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
if ($rowConfig.Provider -eq 'codex' -and -not [string]::IsNullOrWhiteSpace($env:BENCHMARK_CODEX_MODEL_OVERRIDE)) {
    $rowConfig = $rowConfig.Clone()
    $rowConfig.ModelLabel = if ([string]::IsNullOrWhiteSpace($env:BENCHMARK_MODEL_LABEL_OVERRIDE)) {
        $env:BENCHMARK_CODEX_MODEL_OVERRIDE
    } else {
        $env:BENCHMARK_MODEL_LABEL_OVERRIDE
    }
    $rowConfig.CodexArgs = @('--model', $env:BENCHMARK_CODEX_MODEL_OVERRIDE, '-c', 'model_reasoning_effort="xhigh"')
}
if ($rowConfig.Provider -eq 'claude' -and -not [string]::IsNullOrWhiteSpace($env:BENCHMARK_CLAUDE_MODEL_OVERRIDE)) {
    $rowConfig = $rowConfig.Clone()
    $rowConfig.ModelLabel = if ([string]::IsNullOrWhiteSpace($env:BENCHMARK_MODEL_LABEL_OVERRIDE)) {
        $env:BENCHMARK_CLAUDE_MODEL_OVERRIDE
    } else {
        $env:BENCHMARK_MODEL_LABEL_OVERRIDE
    }
    $rowConfig.ClaudeArgs = @('--model', $env:BENCHMARK_CLAUDE_MODEL_OVERRIDE, '--effort', 'max')
}
if (-not (Test-Path -LiteralPath $rowConfig.WrapperPath -PathType Leaf)) {
    throw "Wrapper not found: $($rowConfig.WrapperPath)"
}

$scenarioDirectory = Get-ChildItem -LiteralPath $scenarioRoot -Directory |
    Where-Object { $_.Name -match "^$([regex]::Escape($ScenarioId))-" } |
    Select-Object -First 1
if (-not $scenarioDirectory) {
    throw "Unknown staged scenario id: $ScenarioId"
}

if (-not $PSBoundParameters.ContainsKey('BatchName') -or [string]::IsNullOrWhiteSpace($BatchName)) {
    $BatchName = "v2-staged-$($ScenarioId.ToLowerInvariant())"
}

$timestamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$batchRoot = Join-Path $scratchRoot "$timestamp-$($rowConfig.RowId)-$BatchName"
$caseRoot = Join-Path $batchRoot $ScenarioId
$runRoot = Join-Path $caseRoot 'run'
$metaRoot = Join-Path $caseRoot 'meta'
Assert-SafeScratchPath -RootPath $scratchRoot -CandidatePath $batchRoot
New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
New-Item -ItemType Directory -Force -Path $metaRoot | Out-Null

foreach ($item in Get-ChildItem -LiteralPath $scenarioDirectory.FullName -Force) {
    Copy-Item -LiteralPath $item.FullName -Destination $runRoot -Recurse -Force
}

$scenarioConfig = @{
    Id = $ScenarioId
    BundlePath = $runRoot
    BundleName = $scenarioDirectory.Name
    Metadata = Read-SimpleScenarioMetadata -ScenarioYamlPath (Join-Path $runRoot 'scenario.yaml')
}

$phaseFiles = @(Get-ChildItem -LiteralPath (Join-Path $runRoot 'inputs\phases') -File -Filter '*.md' | Sort-Object Name)
if (@($phaseFiles).Count -eq 0) {
    throw "No staged phase files found for $ScenarioId"
}

$beforeAllSnapshot = Get-TreeSnapshot -RootPath $runRoot
$phaseResults = [System.Collections.Generic.List[psobject]]::new()

for ($index = 0; $index -lt @($phaseFiles).Count; $index++) {
    $phaseFile = $phaseFiles[$index]
    $phaseId = [System.IO.Path]::GetFileNameWithoutExtension($phaseFile.Name)
    $phaseMetaRoot = Join-Path $metaRoot "phases\$phaseId"
    New-Item -ItemType Directory -Force -Path $phaseMetaRoot | Out-Null

    $phaseText = Get-Content -LiteralPath $phaseFile.FullName -Raw
    $promptPath = Join-Path $phaseMetaRoot 'prompt.txt'
    $workerOutputPath = Join-Path $phaseMetaRoot 'worker-output.txt'
    $promptText = New-StagedWorkerPrompt `
        -RowConfig $rowConfig `
        -ScenarioConfig $scenarioConfig `
        -PhaseId $phaseId `
        -PhaseIndex ($index + 1) `
        -PhaseCount @($phaseFiles).Count `
        -PhaseText $phaseText
    Set-Content -LiteralPath $promptPath -Value $promptText -Encoding UTF8

    $beforePhaseSnapshot = Get-TreeSnapshot -RootPath $runRoot
    Write-Host "Running $($rowConfig.RowId) on $ScenarioId phase $phaseId..." -ForegroundColor Cyan
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()

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
                $phaseExitCode = Invoke-CodexDirect `
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
                $phaseExitCode = $LASTEXITCODE
            }
            'gemini' {
                & $rowConfig.WrapperPath `
                    -PromptFile $promptPath `
                    -WorkspaceDir $runRoot `
                    -NoMcp `
                    -GeminiArgs $rowConfig.GeminiArgs `
                    -OutputFile $workerOutputPath
                $phaseExitCode = $LASTEXITCODE
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
        $stopwatch.Stop()
    }

    $afterPhaseSnapshot = Get-TreeSnapshot -RootPath $runRoot
    $phaseChangedPaths = Get-ChangedRelativePaths -Before $beforePhaseSnapshot -After $afterPhaseSnapshot
    $phaseSplit = Split-ChangedRelativePaths -Paths $phaseChangedPaths
    $outputBytes = if (Test-Path -LiteralPath $workerOutputPath -PathType Leaf) {
        (Get-Item -LiteralPath $workerOutputPath).Length
    }
    else {
        $null
    }

    $phaseSummary = [pscustomobject]@{
        phaseId = $phaseId
        phaseIndex = $index + 1
        wrapperExitCode = $phaseExitCode
        elapsedSeconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
        changedPaths = @($phaseChangedPaths)
        benchmarkChangedPaths = @($phaseSplit.benchmark)
        auxiliaryChangedPaths = @($phaseSplit.auxiliary)
        promptPath = $promptPath
        workerOutputPath = $workerOutputPath
        outputBytes = $outputBytes
    }
    $phaseSummary | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath (Join-Path $phaseMetaRoot 'summary.json') -Encoding UTF8
    $phaseResults.Add($phaseSummary)
}

$afterAllSnapshot = Get-TreeSnapshot -RootPath $runRoot
$changedPaths = Get-ChangedRelativePaths -Before $beforeAllSnapshot -After $afterAllSnapshot
$splitChangedPaths = Split-ChangedRelativePaths -Paths $changedPaths

$verificationResults = [System.Collections.Generic.List[psobject]]::new()
$scopeViolations = [System.Collections.Generic.List[string]]::new()
foreach ($changedPath in @($splitChangedPaths.benchmark)) {
    if (-not (Test-PathMatchesAllowedSurface -RelativePath $changedPath -AllowedSurface @($scenarioConfig.Metadata.allowed_change_surface))) {
        $scopeViolations.Add($changedPath)
    }
}
if (@($scopeViolations).Count -gt 0) {
    $scopeLogPath = Join-Path $metaRoot 'verify-changed-path-scope-gate.txt'
    $scopeLines = [System.Collections.Generic.List[string]]::new()
    $scopeLines.Add('ERROR: changed paths outside scenario allowed_change_surface')
    $scopeLines.Add('Observed violations:')
    foreach ($path in @($scopeViolations)) { $scopeLines.Add("- $path") }
    $scopeLines | Set-Content -LiteralPath $scopeLogPath -Encoding UTF8
    $verificationResults.Add([pscustomobject]@{
        command = 'changed-path scenario scope gate'
        exitCode = 1
        log = $scopeLogPath
        passed = $false
    })
}

$verificationPlan = Get-ScenarioVerificationPlan -BundleRoot $runRoot -ChangedPaths @($splitChangedPaths.benchmark)
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

$allPhasesSucceeded = @($phaseResults | Where-Object { $_.wrapperExitCode -ne 0 }).Count -eq 0
$allVerifyPassed = @($verificationResults | Where-Object { -not $_.passed }).Count -eq 0
$wrapperExitCode = if ($allPhasesSucceeded) { 0 } else { 1 }

$summaryJsonPath = Join-Path $metaRoot 'summary.json'
$summary = [pscustomobject]@{
    rowId = $rowConfig.RowId
    modelLabel = $rowConfig.ModelLabel
    scenarioId = $ScenarioId
    bundleName = $scenarioConfig.BundleName
    batchName = $BatchName
    staged = $true
    wrapperExitCode = $wrapperExitCode
    phaseCount = @($phaseResults).Count
    phases = @($phaseResults)
    verificationPassed = $allVerifyPassed
    verificationResults = @($verificationResults)
    changedPaths = @($changedPaths)
    benchmarkChangedPaths = @($splitChangedPaths.benchmark)
    auxiliaryChangedPaths = @($splitChangedPaths.auxiliary)
    runRoot = $runRoot
    metaRoot = $metaRoot
}
$summary | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $summaryJsonPath -Encoding UTF8

$batchSummaryPath = Join-Path $batchRoot 'batch-summary.md'
$changedCell = if (@($splitChangedPaths.benchmark).Count -eq 0) { '`<none>`' } else { (@($splitChangedPaths.benchmark) -join ', ') }
$verifyCell = if ($allVerifyPassed) { 'PASS' } else { 'FAIL' }
$phaseCell = if ($allPhasesSucceeded) { 'PASS' } else { 'FAIL' }
@(
    '# V2 Staged Cohort Batch Summary',
    '',
    '| Scenario | Row | Phase exits | Local verification | Changed paths |',
    '|---|---|---|---|---|',
    "| ``$ScenarioId`` | ``$($rowConfig.RowId)`` | $phaseCell | $verifyCell | $changedCell |"
) -join [Environment]::NewLine | Set-Content -LiteralPath $batchSummaryPath -Encoding UTF8

if (-not $allPhasesSucceeded -or -not $allVerifyPassed) {
    exit 1
}

exit 0

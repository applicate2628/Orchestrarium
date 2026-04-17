[CmdletBinding()]
param(
    [ValidateSet('X1', 'X2', 'X3', 'X5', 'X6')]
    [string]$RowId,

    [string]$BatchName = 'worker-heavy-first-batch',

    [string[]]$TestIds = @('T08', 'T09', 'T10', 'T22', 'T23', 'T24', 'T25', 'T29', 'T30')
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

    return [System.IO.Path]::GetRelativePath($BasePath, $TargetPath).Replace('\', '/')
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
        $isAuxiliary = $false
        foreach ($prefix in $auxiliaryPrefixes) {
            if ($path.StartsWith($prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
                $isAuxiliary = $true
                break
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

    $hasNativeErrorPreference = $false
    $previousNativeErrorPreference = $null
    if (Get-Variable -Name PSNativeCommandUseErrorActionPreference -ErrorAction SilentlyContinue) {
        $hasNativeErrorPreference = $true
        $previousNativeErrorPreference = $PSNativeCommandUseErrorActionPreference
        $PSNativeCommandUseErrorActionPreference = $false
    }

    try {
        Push-Location $WorkingDirectory
        try {
            & $FilePath @ArgumentList 2>&1 | Tee-Object -FilePath $LogPath | Out-Null
            return $LASTEXITCODE
        }
        finally {
            Pop-Location
        }
    }
    finally {
        if ($hasNativeErrorPreference) {
            $PSNativeCommandUseErrorActionPreference = $previousNativeErrorPreference
        }
    }
}

function New-WorkerPrompt {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable]$RowConfig,

        [Parameter(Mandatory = $true)]
        [hashtable]$TestConfig
    )

    $verifyLines = @($TestConfig.VerifyCommands | ForEach-Object { "- ``$($_.DisplayName)``" }) -join [Environment]::NewLine

    @"
You are running benchmark $($TestConfig.Id) for row $($RowConfig.RowId) ($($RowConfig.ModelLabel)) inside a disposable copied workspace.

Read `README.md` in the current directory first and follow it exactly.

Contract:
- The mutable work root is: $($TestConfig.WorkSubdir)
- Make the smallest safe change that satisfies the README.
- Do not edit decoy files, mirror copies, or test files unless the README explicitly makes them part of the owner seam.
- Do not add dependencies, rename the fixture, or widen scope.
- If the README requires a diagnosis memo or resume memo, write it only in the allowed output seam.
- Before finishing, run these commands from $($TestConfig.WorkSubdir) until they pass:
$verifyLines

Final response format:
1. `VERDICT: PASS` or `VERDICT: FAIL`
2. `CHANGED:` followed by changed relative paths, one per line
3. `VERIFY:` followed by the commands you ran, one per line
4. `NOTES:` one short paragraph

Keep the final response concise and do not use markdown fences.
"@
}

$scriptDir = Split-Path -Parent $PSCommandPath
$nextPackRoot = Split-Path -Parent $scriptDir
$workRoot = Split-Path -Parent $nextPackRoot
$repoRoot = Split-Path -Parent $workRoot
$archiveToolingRoot = Join-Path $repoRoot 'Archive\2026-04-16-first-baseline\Tooling\provider-mcp-templates'
$scratchRoot = Join-Path $repoRoot '.scratch\active-cohort-runs'

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

$testConfigs = @{
    T08 = @{
        Id = 'T08'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\retrofit-batch-1\T08-provider-local-note-fix'
        WorkSubdir = 'workspace'
        VerifyCommands = @(
            @{ DisplayName = 'node --test'; FilePath = 'node'; Arguments = @('--test') },
            @{ DisplayName = 'node scripts/verify-owner.js'; FilePath = 'node'; Arguments = @('scripts/verify-owner.js') }
        )
    }
    T09 = @{
        Id = 'T09'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\retrofit-batch-1\T09-root-cause-owner-debug'
        WorkSubdir = 'workspace'
        VerifyCommands = @(
            @{ DisplayName = 'node --test'; FilePath = 'node'; Arguments = @('--test') },
            @{ DisplayName = 'node scripts/verify-owner.js'; FilePath = 'node'; Arguments = @('scripts/verify-owner.js') }
        )
    }
    T10 = @{
        Id = 'T10'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\retrofit-batch-1\T10-resume-stale-context-rejection'
        WorkSubdir = 'workspace'
        VerifyCommands = @(
            @{ DisplayName = 'node --test'; FilePath = 'node'; Arguments = @('--test') },
            @{ DisplayName = 'node scripts/verify-resume-memo.js'; FilePath = 'node'; Arguments = @('scripts/verify-resume-memo.js') }
        )
    }
    T22 = @{
        Id = 'T22'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\retrofit-batch-1\T22-build-owner-continuity'
        WorkSubdir = 'workspace'
        VerifyCommands = @(
            @{ DisplayName = 'npm test'; FilePath = 'npm'; Arguments = @('test') },
            @{ DisplayName = 'node scripts/verify-build.js'; FilePath = 'node'; Arguments = @('scripts/verify-build.js') }
        )
    }
    T23 = @{
        Id = 'T23'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\retrofit-batch-1\T23-path-recall-continuity'
        WorkSubdir = 'workspace'
        VerifyCommands = @(
            @{ DisplayName = 'npm test'; FilePath = 'npm'; Arguments = @('test') },
            @{ DisplayName = 'node scripts/verify-path-recall.js'; FilePath = 'node'; Arguments = @('scripts/verify-path-recall.js') }
        )
    }
    T24 = @{
        Id = 'T24'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\retrofit-batch-1\T24-multi-step-worker-persistence'
        WorkSubdir = 'workspace'
        VerifyCommands = @(
            @{ DisplayName = 'npm test'; FilePath = 'npm'; Arguments = @('test') },
            @{ DisplayName = 'node scripts/verify-persistence.js'; FilePath = 'node'; Arguments = @('scripts/verify-persistence.js') }
        )
    }
    T25 = @{
        Id = 'T25'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\retrofit-batch-1\T25-messy-worker-ownership'
        WorkSubdir = 'repo/apps/demo-app'
        VerifyCommands = @(
            @{ DisplayName = 'npm test'; FilePath = 'npm'; Arguments = @('test') },
            @{ DisplayName = 'node scripts/verify-open-worker.js'; FilePath = 'node'; Arguments = @('scripts/verify-open-worker.js') },
            @{ DisplayName = 'node scripts/verify-followup-worker.js'; FilePath = 'node'; Arguments = @('scripts/verify-followup-worker.js') }
        )
    }
    T26 = @{
        Id = 'T26'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\retrofit-batch-1\T26-toolchain-owner-ambiguity'
        WorkSubdir = 'repo/apps/service-app'
        VerifyCommands = @(
            @{ DisplayName = 'npm test'; FilePath = 'npm'; Arguments = @('test') },
            @{ DisplayName = 'node scripts/verify-toolchain-owner.js'; FilePath = 'node'; Arguments = @('scripts/verify-toolchain-owner.js') }
        )
    }
    T27 = @{
        Id = 'T27'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\retrofit-batch-1\T27-late-session-recall'
        WorkSubdir = 'workspace'
        VerifyCommands = @(
            @{ DisplayName = 'npm test'; FilePath = 'npm'; Arguments = @('test') },
            @{ DisplayName = 'node scripts/verify-recall.js'; FilePath = 'node'; Arguments = @('scripts/verify-recall.js') }
        )
    }
    T28 = @{
        Id = 'T28'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\retrofit-batch-1\T28-reviewer-to-worker-transition'
        WorkSubdir = 'workspace'
        VerifyCommands = @(
            @{ DisplayName = 'npm test'; FilePath = 'npm'; Arguments = @('test') },
            @{ DisplayName = 'node scripts/verify-reviewer-worker.js'; FilePath = 'node'; Arguments = @('scripts/verify-reviewer-worker.js') }
        )
    }
    T29 = @{
        Id = 'T29'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\T29-toolchain-false-root-ambiguity'
        WorkSubdir = 'repo/apps/service-app'
        VerifyCommands = @(
            @{ DisplayName = 'npm test'; FilePath = 'npm'; Arguments = @('test') },
            @{ DisplayName = 'node scripts/verify-owner.js'; FilePath = 'node'; Arguments = @('scripts/verify-owner.js') }
        )
    }
    T30 = @{
        Id = 'T30'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\T30-static-ui-wrong-file-attraction'
        WorkSubdir = 'app'
        VerifyCommands = @(
            @{ DisplayName = 'npm test'; FilePath = 'npm'; Arguments = @('test') },
            @{ DisplayName = 'node scripts/verify-static-ui.js'; FilePath = 'node'; Arguments = @('scripts/verify-static-ui.js') }
        )
    }
    T31 = @{
        Id = 'T31'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\T31-fallback-noisy-evidence-filter'
        WorkSubdir = 'workspace'
        VerifyCommands = @(
            @{ DisplayName = 'npm test'; FilePath = 'npm'; Arguments = @('test') },
            @{ DisplayName = 'node scripts/verify-fallback.js'; FilePath = 'node'; Arguments = @('scripts/verify-fallback.js') }
        )
    }
    T32 = @{
        Id = 'T32'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\T32-constrained-multi-step-patch-no-drift'
        WorkSubdir = 'workspace'
        VerifyCommands = @(
            @{ DisplayName = 'npm test'; FilePath = 'npm'; Arguments = @('test') },
            @{ DisplayName = 'node scripts/verify-patch-flow.js'; FilePath = 'node'; Arguments = @('scripts/verify-patch-flow.js') }
        )
    }
    T33 = @{
        Id = 'T33'
        FixturePath = Join-Path $nextPackRoot 'Fixtures\T33-decorative-consistency-with-asset-distractors'
        WorkSubdir = 'app'
        VerifyCommands = @(
            @{ DisplayName = 'npm test'; FilePath = 'npm'; Arguments = @('test') },
            @{ DisplayName = 'node scripts/verify-decor.js'; FilePath = 'node'; Arguments = @('scripts/verify-decor.js') }
        )
    }
}

if (-not $rowConfigs.ContainsKey($RowId)) {
    throw "Unsupported row id: $RowId"
}

$rowConfig = $rowConfigs[$RowId]
if (-not (Test-Path -LiteralPath $rowConfig.WrapperPath -PathType Leaf)) {
    throw "Wrapper not found: $($rowConfig.WrapperPath)"
}

$unknownTests = @($TestIds | Where-Object { -not $testConfigs.ContainsKey($_) })
if ($unknownTests.Count -gt 0) {
    throw "Unknown test id(s): $($unknownTests -join ', ')"
}

$timestamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$batchRoot = Join-Path $scratchRoot "$timestamp-$($rowConfig.RowId)-$BatchName"
Assert-SafeScratchPath -RootPath $scratchRoot -CandidatePath $batchRoot
New-Item -ItemType Directory -Force -Path $batchRoot | Out-Null

$summaries = [System.Collections.Generic.List[psobject]]::new()

foreach ($testId in $TestIds) {
    $testConfig = $testConfigs[$testId]
    $fixturePath = $testConfig.FixturePath
    $brokenSource = Join-Path $fixturePath 'broken'
    $readmeSource = Join-Path $fixturePath 'README.md'

    if (-not (Test-Path -LiteralPath $brokenSource -PathType Container)) {
        throw "Broken fixture copy not found for ${testId}: $brokenSource"
    }
    if (-not (Test-Path -LiteralPath $readmeSource -PathType Leaf)) {
        throw "Fixture README not found for ${testId}: $readmeSource"
    }

    $caseRoot = Join-Path $batchRoot $testId
    $runRoot = Join-Path $caseRoot 'run'
    $metaRoot = Join-Path $caseRoot 'meta'
    Assert-SafeScratchPath -RootPath $scratchRoot -CandidatePath $caseRoot
    if (Test-Path -LiteralPath $caseRoot) {
        Remove-Item -LiteralPath $caseRoot -Recurse -Force
    }

    New-Item -ItemType Directory -Force -Path $runRoot | Out-Null
    New-Item -ItemType Directory -Force -Path $metaRoot | Out-Null

    Copy-Item -LiteralPath $readmeSource -Destination (Join-Path $runRoot 'README.md')
    foreach ($item in Get-ChildItem -LiteralPath $brokenSource -Force) {
        Copy-Item -LiteralPath $item.FullName -Destination $runRoot -Recurse -Force
    }

    $promptPath = Join-Path $metaRoot 'prompt.txt'
    $workerOutputPath = Join-Path $metaRoot 'worker-output.txt'
    $summaryJsonPath = Join-Path $metaRoot 'summary.json'

    $promptText = New-WorkerPrompt -RowConfig $rowConfig -TestConfig $testConfig
    Set-Content -LiteralPath $promptPath -Value $promptText -Encoding UTF8

    $beforeSnapshot = Get-TreeSnapshot -RootPath $runRoot

    Write-Host "Running $($rowConfig.RowId) on $testId..." -ForegroundColor Cyan
    switch ($rowConfig.Provider) {
        'codex' {
            & $rowConfig.WrapperPath `
                -PromptFile $promptPath `
                -Cwd $runRoot `
                -CodexArgs $rowConfig.CodexArgs `
                -SkipGitRepoCheck `
                -OutputFile $workerOutputPath
            $wrapperExitCode = $LASTEXITCODE
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

    $afterModelSnapshot = Get-TreeSnapshot -RootPath $runRoot
    $changedPaths = Get-ChangedRelativePaths -Before $beforeSnapshot -After $afterModelSnapshot
    $splitChangedPaths = Split-ChangedRelativePaths -Paths $changedPaths

    $verificationResults = [System.Collections.Generic.List[psobject]]::new()
    $verificationRoot = Join-Path $runRoot $testConfig.WorkSubdir
    foreach ($verify in $testConfig.VerifyCommands) {
        $safeName = ($verify.DisplayName -replace '[^A-Za-z0-9]+', '-').Trim('-').ToLowerInvariant()
        $verifyLogPath = Join-Path $metaRoot ("verify-$safeName.txt")
        $exitCode = Invoke-LoggedCommand -FilePath $verify.FilePath -ArgumentList $verify.Arguments -WorkingDirectory $verificationRoot -LogPath $verifyLogPath
        $verificationResults.Add([pscustomobject]@{
            command = $verify.DisplayName
            exitCode = $exitCode
            log = $verifyLogPath
            passed = ($exitCode -eq 0)
        })
    }

    $allVerifyPassed = @($verificationResults | Where-Object { -not $_.passed }).Count -eq 0
    $summary = [pscustomobject]@{
        rowId = $rowConfig.RowId
        modelLabel = $rowConfig.ModelLabel
        testId = $testConfig.Id
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
$lines.Add("# Active Cohort Batch Summary")
$lines.Add("")
$lines.Add("| Test | Wrapper exit | Local verification | Changed paths |")
$lines.Add("|---|---:|---|---|")
foreach ($summary in $summaries) {
    $verifyCell = if ($summary.verificationPassed) { 'PASS' } else { 'FAIL' }
    $changedCell = if (@($summary.benchmarkChangedPaths).Count -eq 0) { '`<none>`' } else { (@($summary.benchmarkChangedPaths) -join ', ') }
    $lines.Add("| ``$($summary.testId)`` | ``$($summary.wrapperExitCode)`` | $($verifyCell) | $changedCell |")
}
$lines -join [Environment]::NewLine | Set-Content -LiteralPath $batchSummaryPath -Encoding UTF8

$batchFailed = @($summaries | Where-Object { $_.wrapperExitCode -ne 0 -or -not $_.verificationPassed }).Count -gt 0
if ($batchFailed) {
    exit 1
}

exit 0

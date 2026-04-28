[CmdletBinding()]
param(
    [ValidateSet('X1', 'X3', 'X5', 'X6')]
    [string[]]$RowId = @('X1', 'X3', 'X5'),

    [string]$BatchName = 'n61-visual-pixel-localization',

    [string]$ScenarioId = 'N61',

    [string]$GeminiModel = 'gemini-3-pro-high-explicit',

    [string]$X6GeminiModel = 'gemini-3.1-flash-lite-preview',

    [int]$RowTimeoutSeconds = 600
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

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

function Get-CodexConfiguredMcpNames {
    $codexCmdPath = (Get-Command codex.cmd -ErrorAction Stop).Path
    $output = & $codexCmdPath mcp list
    if ($LASTEXITCODE -ne 0) {
        return @()
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

function ConvertTo-WindowsProcessArgument {
    param(
        [AllowNull()]
        [string]$Argument
    )

    if ($null -eq $Argument -or $Argument.Length -eq 0) {
        return '""'
    }
    if ($Argument -notmatch '[\s"]') {
        return $Argument
    }

    $quoted = '"'
    $backslashCount = 0
    foreach ($character in $Argument.ToCharArray()) {
        if ($character -eq '\') {
            $backslashCount += 1
            continue
        }
        if ($character -eq '"') {
            $quoted += ('\' * (($backslashCount * 2) + 1))
            $quoted += '"'
            $backslashCount = 0
            continue
        }
        if ($backslashCount -gt 0) {
            $quoted += ('\' * $backslashCount)
            $backslashCount = 0
        }
        $quoted += $character
    }
    if ($backslashCount -gt 0) {
        $quoted += ('\' * ($backslashCount * 2))
    }
    $quoted += '"'
    return $quoted
}

function Invoke-TextProcess {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList,

        [Parameter(Mandatory = $true)]
        [string]$WorkingDirectory,

        [Parameter(Mandatory = $true)]
        [AllowEmptyString()]
        [string]$PromptText,

        [Parameter(Mandatory = $true)]
        [string]$OutputPath,

        [Parameter(Mandatory = $true)]
        [int]$TimeoutSeconds
    )

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $FilePath
    $argumentListProperty = $psi.PSObject.Properties.Match('ArgumentList')
    if ($argumentListProperty.Count -gt 0) {
        foreach ($argument in $ArgumentList) {
            $psi.ArgumentList.Add($argument)
        }
    }
    else {
        $psi.Arguments = ($ArgumentList | ForEach-Object { ConvertTo-WindowsProcessArgument -Argument $_ }) -join ' '
    }
    $psi.WorkingDirectory = $WorkingDirectory
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = $true
    $psi.RedirectStandardOutput = $true
    $psi.RedirectStandardError = $true

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $psi
    $startedAt = Get-Date
    $null = $process.Start()
    $process.StandardInput.Write($PromptText)
    $process.StandardInput.Close()
    $stdoutTask = $process.StandardOutput.ReadToEndAsync()
    $stderrTask = $process.StandardError.ReadToEndAsync()
    $finished = $process.WaitForExit($TimeoutSeconds * 1000)
    if (-not $finished) {
        try {
            $process.Kill($true)
        }
        catch {
            try { $process.Kill() } catch {}
        }
        $process.WaitForExit()
    }
    $stdout = $stdoutTask.GetAwaiter().GetResult()
    $stderr = $stderrTask.GetAwaiter().GetResult()
    $elapsed = ((Get-Date) - $startedAt).TotalSeconds

    $combined = $stdout
    if ($stderr) {
        if ($combined -and -not $combined.EndsWith("`n")) {
            $combined += [Environment]::NewLine
        }
        $combined += $stderr
    }
    [System.IO.File]::WriteAllText($OutputPath, $combined, (New-Object System.Text.UTF8Encoding($false)))

    return [pscustomobject]@{
        ExitCode = if ($finished) { $process.ExitCode } else { 124 }
        ElapsedSeconds = [math]::Round($elapsed, 3)
        TimedOut = (-not $finished)
    }
}

function Invoke-CodexVision {
    param(
        [string]$PromptText,
        [string]$ImagePath,
        [string]$WorkingDirectory,
        [string]$OutputPath,
        [string]$SchemaPath
    )

    $codexCmdPath = (Get-Command codex.cmd -ErrorAction Stop).Path
    $args = [System.Collections.Generic.List[string]]::new()
    foreach ($arg in @('exec', '--ephemeral', '--skip-git-repo-check', '--cd', $WorkingDirectory, '--sandbox', 'read-only', '--ignore-rules', '--image', $ImagePath, '--model', 'gpt-5.5', '-c', 'model_reasoning_effort="xhigh"', '--output-schema', $SchemaPath, '--output-last-message', $OutputPath)) {
        $null = $args.Add($arg)
    }
    foreach ($name in Get-CodexConfiguredMcpNames) {
        $null = $args.Add('-c')
        $null = $args.Add("mcp_servers.$name.enabled=false")
    }
    $null = $args.Add($PromptText)

    $run = Invoke-TextProcess `
        -FilePath $codexCmdPath `
        -ArgumentList @($args) `
        -WorkingDirectory $WorkingDirectory `
        -PromptText '' `
        -OutputPath "$OutputPath.log" `
        -TimeoutSeconds $RowTimeoutSeconds

    if (-not (Test-Path -LiteralPath $OutputPath)) {
        if (Test-Path -LiteralPath "$OutputPath.log") {
            Copy-Item -LiteralPath "$OutputPath.log" -Destination $OutputPath -Force
        }
        else {
            Set-Content -LiteralPath $OutputPath -Value '' -Encoding UTF8
        }
    }

    return [pscustomobject]@{
        ExitCode = $run.ExitCode
        ElapsedSeconds = $run.ElapsedSeconds
        TimedOut = $run.TimedOut
    }
}

function Invoke-ClaudeVision {
    param(
        [string]$PromptText,
        [string]$ImagePath,
        [string]$WorkingDirectory,
        [string]$OutputPath
    )

    $emptyMcpConfig = Join-Path $WorkingDirectory 'empty-mcp.json'
    Set-Content -LiteralPath $emptyMcpConfig -Value '{"mcpServers":{}}' -Encoding UTF8

    $promptWithPath = @"
$PromptText

Image file path for Claude Code image input:
$ImagePath
"@

    $claudeCmd = (Get-Command claude -ErrorAction Stop).Source
    $args = @('--print', '--no-session-persistence', '--strict-mcp-config', '--mcp-config', $emptyMcpConfig, '--model', 'opus', '--effort', 'max', '--tools', 'Read', '--add-dir', $WorkingDirectory)
    return Invoke-TextProcess -FilePath $claudeCmd -ArgumentList $args -WorkingDirectory $WorkingDirectory -PromptText $promptWithPath -OutputPath $OutputPath -TimeoutSeconds $RowTimeoutSeconds
}

function Invoke-GeminiVision {
    param(
        [string]$PromptText,
        [string]$ImagePath,
        [string]$WorkingDirectory,
        [string]$OutputPath,
        [string]$ModelName
    )

    $promptFile = Join-Path $WorkingDirectory 'gemini-prompt.txt'
    $relativeImage = Split-Path -Leaf $ImagePath
    $promptWithPath = @"
@$relativeImage

$PromptText
"@
    Set-Content -LiteralPath $promptFile -Value $promptWithPath -Encoding UTF8

    $wrapperPath = Join-Path $archiveToolingRoot 'gemini-isolated-worker.ps1'
    $pwshPath = (Get-Command pwsh -ErrorAction Stop).Source
    $wrapperLog = "$OutputPath.wrapper.log"
    $command = @"
& '$($wrapperPath.Replace("'", "''"))' -PromptFile '$($promptFile.Replace("'", "''"))' -WorkspaceDir '$($WorkingDirectory.Replace("'", "''"))' -NoMcp -GeminiArgs @('--model', '$($ModelName.Replace("'", "''"))') -OutputFile '$($OutputPath.Replace("'", "''"))'
"@
    $encodedCommand = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes($command))
    $run = Invoke-TextProcess `
        -FilePath $pwshPath `
        -ArgumentList @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encodedCommand) `
        -WorkingDirectory $WorkingDirectory `
        -PromptText '' `
        -OutputPath $wrapperLog `
        -TimeoutSeconds $RowTimeoutSeconds

    if (-not (Test-Path -LiteralPath $OutputPath)) {
        if (Test-Path -LiteralPath $wrapperLog) {
            Copy-Item -LiteralPath $wrapperLog -Destination $OutputPath -Force
        }
        else {
            Set-Content -LiteralPath $OutputPath -Value '' -Encoding UTF8
        }
    }

    return $run
}

function Get-OptionalProperty {
    param(
        [Parameter(Mandatory = $true)]
        [object]$Object,

        [Parameter(Mandatory = $true)]
        [string]$Name
    )

    if ($null -eq $Object) {
        return $null
    }

    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property) {
        return $null
    }

    return $property.Value
}

$scriptDir = Split-Path -Parent $PSCommandPath
$nextPackRoot = Split-Path -Parent $scriptDir
$workRoot = Split-Path -Parent $nextPackRoot
$repoRoot = Split-Path -Parent $workRoot
$archiveToolingRoot = Join-Path $repoRoot 'Archive\2026-04-16-first-baseline\Tooling\provider-mcp-templates'
$scratchRoot = Join-Path $repoRoot '.scratch\visual-localization-runs'
$timestamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$batchRoot = Join-Path $scratchRoot "$timestamp-$BatchName"
Assert-SafeScratchPath -RootPath $scratchRoot -CandidatePath $batchRoot
New-Item -ItemType Directory -Force -Path $batchRoot | Out-Null

$scenarioName = switch ($ScenarioId) {
    'N61' { 'N61-visual-pixel-localization-gauntlet' }
    'N68' { 'N68-actual-screenshot-visual-review-gauntlet' }
    'N80' { 'N80-screenshot-grounding-review-v2' }
    default { throw "Only N61, N68, and N80 are supported by this visual runner." }
}
$scenarioRoot = Join-Path $repoRoot "Scenarios-v2\$scenarioName"
if ($ScenarioId -eq 'N61') {
    $imageFileName = 'visual-localization-canvas.png'
    $verifierFileName = 'check_visual_localization.py'
}
elseif ($ScenarioId -eq 'N68') {
    $imageFileName = 'actual-screenshot.png'
    $verifierFileName = 'check_actual_screenshot_visual_review.py'
}
else {
    $imageFileName = 'actual-screenshot.png'
    $verifierFileName = 'check_screenshot_grounding_review.py'
}
if (-not (Test-Path -LiteralPath $scenarioRoot -PathType Container)) {
    throw "Scenario root not found: $scenarioRoot"
}

$promptText = Get-Content -LiteralPath (Join-Path $scenarioRoot 'inputs\task.md') -Raw
$imagePath = Join-Path $scenarioRoot "inputs\$imageFileName"
$schemaPath = Join-Path $scenarioRoot 'oracle\answer-schema.json'
$verifierPath = Join-Path $scenarioRoot "verifiers\$verifierFileName"

$summaries = [System.Collections.Generic.List[psobject]]::new()
foreach ($row in $RowId) {
    $rowRoot = Join-Path $batchRoot $row
    New-Item -ItemType Directory -Force -Path $rowRoot | Out-Null
    $workerOutputPath = Join-Path $rowRoot 'worker-output.txt'
    $metricsPath = Join-Path $rowRoot 'metrics.json'
    $verifyLogPath = Join-Path $rowRoot 'verify.txt'
    $rowImagePath = Join-Path $rowRoot $imageFileName
    Copy-Item -LiteralPath $imagePath -Destination $rowImagePath -Force

    Write-Host "Running visual localization $row..." -ForegroundColor Cyan
    $run = switch ($row) {
        'X1' { Invoke-CodexVision -PromptText $promptText -ImagePath $rowImagePath -WorkingDirectory $rowRoot -OutputPath $workerOutputPath -SchemaPath $schemaPath }
        'X3' { Invoke-ClaudeVision -PromptText $promptText -ImagePath $rowImagePath -WorkingDirectory $rowRoot -OutputPath $workerOutputPath }
        'X5' { Invoke-GeminiVision -PromptText $promptText -ImagePath $rowImagePath -WorkingDirectory $rowRoot -OutputPath $workerOutputPath -ModelName $GeminiModel }
        'X6' { Invoke-GeminiVision -PromptText $promptText -ImagePath $rowImagePath -WorkingDirectory $rowRoot -OutputPath $workerOutputPath -ModelName $X6GeminiModel }
    }

    & python $verifierPath --bundle-root $scenarioRoot --answer-file $workerOutputPath --metrics-out $metricsPath *> $verifyLogPath
    $verifierExitCode = $LASTEXITCODE
    $metrics = if (Test-Path -LiteralPath $metricsPath) {
        Get-Content -LiteralPath $metricsPath -Raw | ConvertFrom-Json
    }
    else {
        [pscustomobject]@{
            verdict = 'FAIL'
            parse_error = 'metrics file was not produced'
            score_0_100 = 0
        }
    }

    $outputBytes = if (Test-Path -LiteralPath $workerOutputPath) {
        (Get-Item -LiteralPath $workerOutputPath).Length
    }
    else {
        0
    }

    $summaries.Add([pscustomobject]@{
        rowId = $row
        scenarioId = $ScenarioId
        model = switch ($row) {
            'X1' { 'gpt-5.5' }
            'X3' { 'opus 4.7max' }
            'X5' { $GeminiModel }
            'X6' { $X6GeminiModel }
        }
        wrapperExitCode = $run.ExitCode
        verifierExitCode = $verifierExitCode
        verdict = Get-OptionalProperty -Object $metrics -Name 'verdict'
        score_0_100 = Get-OptionalProperty -Object $metrics -Name 'score_0_100'
        mean_error_px = Get-OptionalProperty -Object $metrics -Name 'mean_error_px'
        max_error_px = Get-OptionalProperty -Object $metrics -Name 'max_error_px'
        parse_error = Get-OptionalProperty -Object $metrics -Name 'parse_error'
        elapsedSeconds = $run.ElapsedSeconds
        outputBytes = $outputBytes
        timedOut = Get-OptionalProperty -Object $run -Name 'TimedOut'
        workerOutput = $workerOutputPath
        metrics = $metricsPath
        verifyLog = $verifyLogPath
    })
}

$summaryPath = Join-Path $batchRoot 'summary.json'
$summaries | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
Write-Host "Summary: $summaryPath" -ForegroundColor Green

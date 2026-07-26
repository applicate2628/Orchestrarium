<#
.SYNOPSIS
    Install the Orchestrarium Gemini example pack.
.DESCRIPTION
    Installs Gemini-native runtime surfaces for project-local or global Gemini CLI example use.
    Project installs write GEMINI.md and AGENTS.md at the project root and runtime assets under .gemini/.
    Production auto routing remains on codex/claude; Gemini is kept installable as an example/compatibility path.
.EXAMPLE
    .\scripts\install-gemini.ps1
    .\scripts\install-gemini.ps1 -Global
    .\scripts\install-gemini.ps1 -Target "D:\my-repo"
#>
param(
    [switch]$Global,
    [string]$Target,
    [switch]$Force,
    [switch]$DryRun,
    [switch]$AllowUnsafeTarget
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $ScriptDir
$Source = Join-Path $RepoDir "src.gemini"
$ExtensionSource = Join-Path $Source "extension"
$ExtensionManifestSource = Join-Path $ExtensionSource "gemini-extension.json"
$ExtensionReadmeSource = Join-Path $ExtensionSource "README.md"
$SharedAgentsSource = Join-Path (Join-Path $RepoDir "shared") "AGENTS.shared.md"
$DefaultAgentsModeSource = Join-Path $RepoDir "shared\agents-mode.defaults.yaml"
$UniversalHookScriptsSource = Join-Path $RepoDir "scripts/universal-hooks/scripts"
$UniversalHookHooksSource = Join-Path $RepoDir "scripts/universal-hooks/hooks"
$ManagedStart = "<!-- ORCHESTRARIUM_GEMINI_PACK:START -->"
$ManagedEnd = "<!-- ORCHESTRARIUM_GEMINI_PACK:END -->"

function Get-CanonicalPath {
    param([string]$Path)
    $expanded = [Environment]::ExpandEnvironmentVariables($Path).Trim('"').Trim()
    $homeRoot = if ($HOME) { $HOME } else { [Environment]::GetFolderPath("UserProfile") }
    if ($expanded -eq "~") {
        $expanded = $homeRoot
    } elseif ($expanded.StartsWith("~/") -or $expanded.StartsWith("~\")) {
        $expanded = Join-Path $homeRoot $expanded.Substring(2)
    }
    if ([string]::IsNullOrWhiteSpace($expanded)) { throw "Path is empty." }
    try {
        return (Resolve-Path -LiteralPath $expanded -ErrorAction Stop).Path
    } catch {
        return [System.IO.Path]::GetFullPath($expanded)
    }
}

function Get-RepoRoot {
    try {
        $repoRoot = git rev-parse --show-toplevel 2>$null
        if ($repoRoot) { return (Get-CanonicalPath $repoRoot) }
    } catch {}
    return (Get-CanonicalPath (Get-Location).Path)
}

function Resolve-ProjectRoot {
    param([string]$InputPath)
    $resolved = Get-CanonicalPath $InputPath
    if ((Split-Path -Leaf $resolved).ToLowerInvariant() -eq ".gemini") {
        return (Split-Path -Parent $resolved)
    }
    return $resolved
}

function Get-GeminiExtensionName {
    param([string]$ManifestPath)

    if (-not (Test-Path -LiteralPath $ManifestPath)) {
        throw "Missing Gemini extension manifest at $ManifestPath"
    }

    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ([string]::IsNullOrWhiteSpace($manifest.name)) {
        throw "Gemini extension manifest is missing a non-empty 'name' field."
    }

    return $manifest.name
}

function Confirm-Action {
    param([string]$Prompt)
    if ($Force -or $DryRun) { return $true }
    if (-not ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected)) { return $true }
    while ($true) {
        $answer = Read-Host "$Prompt [y/N]"
        if ($null -eq $answer) {
            $normalized = ""
        } else {
            $normalized = $answer.Trim().ToLowerInvariant()
        }
        switch ($normalized) {
            "y" { return $true }
            "yes" { return $true }
            "" { return $false }
            "n" { return $false }
            "no" { return $false }
            default { Write-Host "Please answer y or n." -ForegroundColor Yellow }
        }
    }
}

function Assert-SafeProjectRoot {
    param([string]$ProjectRoot, [string]$Mode)
    $repoRoot = Get-RepoRoot
    $normalizedProject = $ProjectRoot.ToLowerInvariant()
    $normalizedRepo = $repoRoot.ToLowerInvariant()
    if ($Mode -eq "target" -and -not $AllowUnsafeTarget -and $normalizedProject -ne $normalizedRepo) {
        throw "Unsafe target denied for non-default project root '$ProjectRoot'. Use -AllowUnsafeTarget to override."
    }
}

function Ensure-Dir {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Force -Path $Path | Out-Null
        } else {
            Write-Host "    [dry-run] would create $Path"
        }
    }
}

function Migrate-LegacyAgentsModeFile {
    param(
        [string]$LegacyFile,
        [string]$TargetFile,
        [string]$Label
    )

    if (Test-Path -LiteralPath $TargetFile) {
        if (Test-Path -LiteralPath $LegacyFile) {
            Write-Host "  Canonical $Label already exists; leaving legacy file untouched: $LegacyFile"
        }
        return
    }

    if (-not (Test-Path -LiteralPath $LegacyFile)) {
        return
    }

    Write-Host "  Migrating legacy $Label to $TargetFile..."
    if (-not $DryRun) {
        Move-Item -LiteralPath $LegacyFile -Destination $TargetFile -Force
    } else {
        Write-Host "    [dry-run] would move $LegacyFile -> $TargetFile"
    }
}

function Get-PythonCommand {
    foreach ($name in @("python", "python3")) {
        $command = Get-Command $name -ErrorAction SilentlyContinue
        if ($null -ne $command) {
            return $command.Source
        }
    }
    return $null
}

# Universal hook/helper names are DERIVED by globbing the pack-neutral canon dirs
# (scripts/universal-hooks/{scripts,hooks}/) — never a hardcoded list. A hook
# added to the canon is auto-installed here; a hardcoded list is exactly what hid
# check-stale-relation-residue from the install surface until 2026-07-07.
$UniversalHookExts = @(".py", ".sh", ".ps1")
$UniversalRuntimeScriptNames = @(
    Get-ChildItem -LiteralPath $UniversalHookScriptsSource -File -ErrorAction SilentlyContinue |
        Where-Object { $UniversalHookExts -contains $_.Extension } |
        Sort-Object Name | ForEach-Object { $_.Name }
)
$UniversalRuntimeHookNames = @(
    Get-ChildItem -LiteralPath $UniversalHookHooksSource -File -ErrorAction SilentlyContinue |
        Where-Object { $UniversalHookExts -contains $_.Extension } |
        Sort-Object Name | ForEach-Object { $_.Name }
)

function Get-DirectoryFileHashes {
    param([string]$Root)

    $rootFull = [System.IO.Path]::GetFullPath($Root).TrimEnd([char[]]@('\', '/'))
    $hashes = @{}
    foreach ($file in Get-ChildItem -LiteralPath $Root -Recurse -File -Force | Sort-Object FullName) {
        $fullName = [System.IO.Path]::GetFullPath($file.FullName)
        $relative = $fullName.Substring($rootFull.Length).TrimStart([char[]]@('\', '/'))
        $hashes[$relative] = (Get-FileHash -Algorithm SHA256 -LiteralPath $fullName).Hash
    }
    return $hashes
}

function Test-DirectoryContentEqual {
    param(
        [string]$SourceDir,
        [string]$TargetDir
    )

    if (-not (Test-Path -LiteralPath $TargetDir -PathType Container)) {
        return $false
    }

    $sourceHashes = Get-DirectoryFileHashes -Root $SourceDir
    $targetHashes = Get-DirectoryFileHashes -Root $TargetDir
    if ($sourceHashes.Count -ne $targetHashes.Count) {
        return $false
    }

    foreach ($key in $sourceHashes.Keys) {
        if (-not $targetHashes.ContainsKey($key)) {
            return $false
        }
        if ($sourceHashes[$key] -ne $targetHashes[$key]) {
            return $false
        }
    }

    return $true
}

function Test-FileContentEqual {
    param(
        [string]$SourceFile,
        [string]$TargetFile
    )

    if (-not (Test-Path -LiteralPath $TargetFile -PathType Leaf)) {
        return $false
    }

    $sourceHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $SourceFile).Hash
    $targetHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $TargetFile).Hash
    return $sourceHash -eq $targetHash
}

function Test-ItemContentEqual {
    param(
        [string]$SourcePath,
        [string]$TargetPath
    )

    $sourceItem = Get-Item -LiteralPath $SourcePath -Force
    if ($sourceItem.PSIsContainer) {
        return (Test-DirectoryContentEqual -SourceDir $SourcePath -TargetDir $TargetPath)
    }
    return (Test-FileContentEqual -SourceFile $SourcePath -TargetFile $TargetPath)
}

function Install-Tree {
    param([string]$SourceDir, [string]$TargetDir, [string]$Label)

    Ensure-Dir $TargetDir
    Write-Host "  Installing $Label (per-item, preserving user-added items)..."

    $packNames = @()
    foreach ($item in Get-ChildItem -LiteralPath $SourceDir -Force) {
        $packNames += $item.Name
        $destination = Join-Path $TargetDir $item.Name
        if (Test-Path -LiteralPath $destination) {
            if (Test-ItemContentEqual -SourcePath $item.FullName -TargetPath $destination) {
                Write-Host "    OK  $Label/$($item.Name) unchanged"
                continue
            }

            if (-not $DryRun) {
                Remove-Item -Recurse -Force $destination
                Copy-Item -Recurse -Force $item.FullName $destination
            } else {
                Write-Host "    [dry-run] would replace $Label/$($item.Name)"
            }
        } else {
            if (-not $DryRun) {
                Copy-Item -Recurse -Force $item.FullName $destination
            } else {
                Write-Host "    [dry-run] would install $Label/$($item.Name)"
            }
        }
    }

    if (Test-Path -LiteralPath $TargetDir) {
        foreach ($existing in Get-ChildItem -LiteralPath $TargetDir -Force) {
            if ($packNames -notcontains $existing.Name) {
                Write-Host "  Preserved user item: $Label/$($existing.Name)"
            }
        }
    }
}

function Ensure-LocalOnlyGitignoreEntries {
    param([string]$ProjectRoot)

    $gitignore = Join-Path $ProjectRoot ".gitignore"
    $entries = @("/.reports/", "/.plans/", "/work-items/", "/.scratch/")
    $existingLines = @()
    if (Test-Path -LiteralPath $gitignore) {
        # Get-Content already strips line terminators (LF or CRLF) and
        # auto-detects/strips a leading UTF-8 byte-order mark via its default
        # encoding detection (verified directly under both pwsh 7 and Windows
        # PowerShell 5.1). TrimEnd() additionally tolerates trailing
        # whitespace an operator may have typed by hand, so a bash-produced
        # or hand-edited .gitignore matches identically here.
        $existingLines = @(Get-Content -LiteralPath $gitignore -ErrorAction SilentlyContinue | ForEach-Object { $_.TrimEnd() })
    }

    $missing = @()
    $declinedNegation = @()
    $declinedSentinel = @()
    $declinedUnverifiable = @()
    # git's OWN negation syntax (an "!entry" line) must be resolved by GIT's
    # own matcher, not a fixed spelling list: three rounds of widening a
    # literal enumeration (two forms, then four) each missed spellings git
    # itself honors (glob forms such as "!**/work-items/", character
    # classes, single-char wildcards -- confirmed against real
    # "git check-ignore -v" this session, including an end-to-end destroy
    # proof: "/wo*/" plus "!**/work-items/" with core.ignorecase=true tracked
    # '/work-items/' before this writer ran and was silently re-ignored
    # after, under the four-form enumeration). Ask git instead of guessing:
    # for each tier not already resolved by literal presence or the decline
    # sentinel below, an ISOLATED throwaway repo (never the operator's real
    # .gitignore or repo -- created fresh in system temp and always removed
    # before this function returns) is seeded with this file's OWN content
    # and probed twice via "git check-ignore": once as-is, once with every
    # "!"-prefixed line stripped. Ignored in the first probe but not the
    # second means a negation IN THIS FILE is responsible (declined -- this
    # matches git check-ignore's own authority instead of a spelling list,
    # so it also naturally follows the target repo's own core.ignorecase);
    # ignored in neither means genuinely missing (append); ignored in the
    # first probe alone means some existing pattern already covers it
    # (nothing to do). The probe path is a FILE inside the tier directory
    # ("<tier>/.orchestrarium-probe"), not the bare directory name --
    # confirmed this session that a directory-targeting negation (e.g.
    # "!/Work-Items/", trailing slash) only takes effect once git is asked
    # about a path unambiguously inside that directory. Every native git
    # call below relaxes $ErrorActionPreference first: under Windows
    # PowerShell 5.1, a native command's stderr (even redirected to $null)
    # becomes an ErrorRecord that $ErrorActionPreference = 'Stop' promotes
    # to a terminating exception -- this is what made the PRIOR
    # core.ignorecase read here abort the whole installer on an ordinary
    # corrupt .git/config value (reproduced directly this session: exit 1,
    # hooks/.gitignore/credential entry all left uninstalled). See
    # work-items/bugs/2026-07-25-tier-writer-silently-reverts-considered-decline.md.
    $unresolved = @()
    foreach ($entry in $entries) {
        $alternate = $entry.TrimStart("/")
        # The decline sentinel: an exact whole-line comment naming this
        # specific tier. Case-SENSITIVE on BOTH engines -- OUR OWN token, our
        # own rules (contrast the git-delegated negation check below, which
        # follows GIT's own core.ignorecase rules instead).
        $declineMarker = "# orchestrarium:local-only-tier-declined:$entry"
        if ($existingLines -ccontains $entry -or $existingLines -ccontains $alternate) {
            continue
        }
        if ($existingLines -ccontains $declineMarker) {
            $declinedSentinel += $entry
            continue
        }
        $unresolved += $entry
    }

    if ($unresolved.Count -gt 0) {
        $giprobeRoot = $null
        # THE INVARIANT THIS BLOCK ENFORCES: the probe consults nothing
        # outside the throwaway repository and the file under test. Every
        # mechanism below -- clearing environment variables AND setting
        # config values explicitly -- exists only to make that invariant
        # hold; when adding a new git call here, check it against the
        # invariant directly rather than against the list of vectors found
        # so far, because the list is provably incomplete (three rounds have
        # each found a member neither of the prior rounds had named, and the
        # git-documented environment-variable list itself was consulted via
        # empirical enumeration on this machine, not a rendered man page --
        # treat it as thorough, not complete).
        #
        # Two DISTINCT classes of leak, needing two DIFFERENT mechanisms:
        #   1. Environment variables that redirect the probe onto a
        #      DIFFERENT repository or inject config directly (GIT_DIR,
        #      GIT_WORK_TREE, GIT_COMMON_DIR, ... GIT_CONFIG_COUNT below) --
        #      closed by CLEARING them, since an absent variable cannot
        #      redirect anything.
        #   2. A resolution FALLBACK that fires precisely when a setting is
        #      UNSET -- core.excludesFile has no default VALUE, but git
        #      falls back to a default PATH ($XDG_CONFIG_HOME/git/ignore,
        #      else $HOME/.config/git/ignore) whenever core.excludesFile
        #      itself is unset. Pointing GIT_CONFIG_GLOBAL at a nonexistent
        #      file leaves core.excludesFile unset, which is exactly the
        #      condition that triggers this fallback -- so clearing
        #      GIT_CONFIG_GLOBAL/GIT_CONFIG_NOSYSTEM does NOT close it
        #      (confirmed this session on bash, pwsh 7, and Windows
        #      PowerShell 5.1: an ambient HOME or XDG_CONFIG_HOME pointing
        #      at a personal global-gitignore covering the tier still
        #      leaked in, SILENTLY, under the round-6 fix). This is
        #      plausibly the MOST LIKELY trigger of any vector found so
        #      far: `~/.config/git/ignore` is the standard personal
        #      global-gitignore location, and an operator who uses this
        #      pack across several repos and adds a tier to their own
        #      global ignore -- a natural thing to do -- would get silence
        #      on every project, forever, with no message. Closed by
        #      SETTING core.excludesFile EXPLICITLY on the throwaway repo
        #      (below, right after `git init`) rather than relying on it
        #      staying unset: an explicit value, even a nonexistent path,
        #      means the "unset" condition the fallback keys on never
        #      occurs, so no future default-path fallback can reopen this
        #      by a different name.
        #
        # GIT_DIR / GIT_WORK_TREE / GIT_COMMON_DIR (individually or paired)
        # can redirect a `-C <dir>`-targeted call onto a COMPLETELY
        # DIFFERENT repository -- but NOT identically: measured this
        # session with `git rev-parse --show-toplevel --git-dir` as well as
        # `check-ignore`, GIT_WORK_TREE alone redirects BOTH the working
        # tree AND git-dir discovery (so a WORKING-TREE-relative ignore
        # source, e.g. a plain `.gitignore`, leaks); GIT_DIR alone
        # redirects ONLY git-dir discovery, leaving the working tree in
        # place (so a GIT-DIR-relative ignore source, e.g.
        # `$GIT_DIR/info/exclude`, leaks, while a `.gitignore` does not) --
        # both are real leaks, just through different ignore-source
        # channels, and clearing both closes both regardless of which
        # channel a given operator's ambient state happens to use.
        # GIT_ICASE_PATHSPECS / GIT_LITERAL_PATHSPECS / GIT_NOGLOB_PATHSPECS
        # / GIT_GLOB_PATHSPECS make `check-ignore` itself fail outright
        # ("pathspec magic not supported by this command", exit 128,
        # confirmed this session on both pwsh 7 and Windows PowerShell 5.1
        # -- on PS 5.1 specifically this surfaces as a NativeCommandError,
        # the same class this block's own relax-and-restore wrap already
        # guards every native call against) -- not a silent leak, since the
        # writer's own exit-code handling below degrades that to "could not
        # be checked" rather than misreading it as ignored or not, but it
        # still leaves the tier unwritten with no way to recover except by
        # clearing the variable, so it is cleared alongside the rest.
        # GIT_CONFIG_COUNT (paired with GIT_CONFIG_KEY_n/GIT_CONFIG_VALUE_n)
        # injects arbitrary config -- including core.excludesFile --
        # directly from the environment, bypassing GIT_CONFIG_NOSYSTEM/
        # GIT_CONFIG_GLOBAL entirely (confirmed this session; found by
        # reading git's own documented environment-variable list rather
        # than extending piecemeal from previously-named vectors, not named
        # by anyone before that read). A realistic trigger for any of the
        # redirect/injection vars: the installer running from inside a git
        # hook, mid-rebase, or from a CI/IDE wrapper that exports them.
        # Cleared for the ENTIRE unresolved-tier block (not just calls
        # targeting the throwaway repo): the SAME vars would equally
        # corrupt the project_root-targeted `config --local
        # core.ignorecase` read below. None of these have a legitimate
        # reason to survive here -- this probe only ever needs a fresh,
        # self-contained repository at a path this function chose itself.
        $giprobeRepoLocationVars = @(
            "GIT_DIR", "GIT_WORK_TREE", "GIT_COMMON_DIR", "GIT_NAMESPACE",
            "GIT_CEILING_DIRECTORIES", "GIT_DISCOVERY_ACROSS_FILESYSTEM",
            "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
            "GIT_CONFIG_SYSTEM", "GIT_CONFIG_COUNT",
            "GIT_ICASE_PATHSPECS", "GIT_LITERAL_PATHSPECS", "GIT_NOGLOB_PATHSPECS", "GIT_GLOB_PATHSPECS"
        )
        $giprobeSavedEnv = @{}
        foreach ($varName in $giprobeRepoLocationVars) {
            $giprobeSavedEnv[$varName] = [System.Environment]::GetEnvironmentVariable($varName)
            if ($null -ne $giprobeSavedEnv[$varName]) {
                Remove-Item "Env:\$varName" -ErrorAction SilentlyContinue
            }
        }
        $previousGitConfigNoSystem = $env:GIT_CONFIG_NOSYSTEM
        $previousGitConfigGlobal = $env:GIT_CONFIG_GLOBAL
        try {
            if (Get-Command git -ErrorAction SilentlyContinue) {
                $candidateRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("orchestrarium-giprobe-" + [System.IO.Path]::GetRandomFileName())
                # Neutralize the OPERATOR's ambient git environment for this
                # throwaway repo: GIT_CONFIG_NOSYSTEM plus a nonexistent
                # GIT_CONFIG_GLOBAL stop a global `core.excludesFile` from
                # leaking into the probe's verdict, and `--template=
                # <nonexistent>` stops a global `init.templateDir` from
                # seeding `info/exclude` -- confirmed this session that
                # without this, an operator's own global core.excludesFile
                # covering the tier made the writer silently decide "already
                # ignored" for a PROJECT whose own .gitignore said nothing
                # about it, so a teammate cloning without that global config
                # would track the tier -- the exact publication-safety
                # failure this tier system exists to prevent. A nonexistent
                # path is sufficient for both (git treats it as "no such
                # config"/"no such template", not an error). Saved/restored
                # via try/finally below since these are PROCESS-wide
                # environment variables, not scoped to one native call.
                $env:GIT_CONFIG_NOSYSTEM = "1"
                $env:GIT_CONFIG_GLOBAL = "$candidateRoot.noconfig"
                $previousErrorActionPreference = $ErrorActionPreference
                $ErrorActionPreference = "Continue"
                try {
                    New-Item -ItemType Directory -Path $candidateRoot -Force | Out-Null
                    & git init -q --template="$candidateRoot.notemplate" $candidateRoot 2>$null
                    if ($LASTEXITCODE -eq 0) {
                        $giprobeRoot = $candidateRoot
                    }
                } catch {
                    $giprobeRoot = $null
                } finally {
                    $ErrorActionPreference = $previousErrorActionPreference
                }
                if (-not $giprobeRoot -and (Test-Path -LiteralPath $candidateRoot)) {
                    Remove-Item -LiteralPath $candidateRoot -Recurse -Force -ErrorAction SilentlyContinue
                }
                if ($giprobeRoot) {
                    # core.excludesFile has no default VALUE, but git falls
                    # back to a default PATH ($XDG_CONFIG_HOME/git/ignore,
                    # else $HOME/.config/git/ignore) whenever it is UNSET --
                    # which is exactly the state GIT_CONFIG_GLOBAL=
                    # <nonexistent> leaves it in. Setting it EXPLICITLY here
                    # (a nonexistent path is enough) ends the fallback
                    # permanently, rather than relying on it staying unset --
                    # confirmed this session that an ambient HOME or
                    # XDG_CONFIG_HOME pointing at a real
                    # `~/.config/git/ignore` covering the tier otherwise
                    # leaked in SILENTLY even with GIT_CONFIG_NOSYSTEM/
                    # GIT_CONFIG_GLOBAL already neutralized.
                    $previousErrorActionPreference = $ErrorActionPreference
                    $ErrorActionPreference = "Continue"
                    try {
                        & git -C $giprobeRoot config core.excludesFile "$giprobeRoot.noexcludes" 2>$null
                    } catch {
                    } finally {
                        $ErrorActionPreference = $previousErrorActionPreference
                    }
                    # If project_root is ALREADY a repo with an EXPLICIT
                    # LOCAL core.ignorecase override -- not just the
                    # filesystem-auto-detected default the throwaway repo
                    # would otherwise pick up on its own -- mirror that
                    # explicit choice onto the (now-neutralized) throwaway
                    # repo, so an operator-set override at the REAL target
                    # is not silently ignored. --local (never plain
                    # `config`, which falls through to global/system config
                    # even from inside a repo with no local override) keeps
                    # this scoped to project_root's OWN repo only; a
                    # non-repo project_root fails harmlessly (non-zero
                    # exit), same as an unset override.
                    $previousErrorActionPreference = $ErrorActionPreference
                    $ErrorActionPreference = "Continue"
                    $projectIgnorecaseRaw = $null
                    $projectIgnorecaseExitCode = 1
                    try {
                        $projectIgnorecaseRaw = & git -C $ProjectRoot config --local --type=bool core.ignorecase 2>$null
                        $projectIgnorecaseExitCode = $LASTEXITCODE
                    } catch {
                        $projectIgnorecaseRaw = $null
                        $projectIgnorecaseExitCode = 1
                    } finally {
                        $ErrorActionPreference = $previousErrorActionPreference
                    }
                    if ($projectIgnorecaseExitCode -eq 0 -and ($projectIgnorecaseRaw -eq "true" -or $projectIgnorecaseRaw -eq "false")) {
                        $previousErrorActionPreference = $ErrorActionPreference
                        $ErrorActionPreference = "Continue"
                        try {
                            & git -C $giprobeRoot config core.ignorecase $projectIgnorecaseRaw 2>$null
                        } catch {
                        } finally {
                            $ErrorActionPreference = $previousErrorActionPreference
                        }
                    }
                }
            }

            # Every "!"-prefixed line's OWN stripped pattern, collected once
            # (not per tier): a BARE/unpaired negation -- e.g.
            # "!/work-items/" alone, no positive counterpart anywhere in the
            # file -- is un-ignored both WITH and WITHOUT negations present,
            # so a whole-file before/after-stripping DIFFERENTIAL (an
            # earlier version of this fix) cannot tell "declined via
            # negation" apart from "genuinely missing"; appending in that
            # case adds the very positive pattern the operator just
            # negated, flipping git's real verdict to the OPPOSITE of what
            # they wrote (reproduced directly this session on bash, pwsh 7,
            # and Windows PowerShell 5.1: NOT-ignored before this writer
            # ran, IGNORED after -- exactly the silent-revert-of-a-
            # considered-decline defect this whole bug exists to prevent).
            # Testing each negation line's OWN pattern in isolation catches
            # this regardless of whether a companion positive pattern
            # exists anywhere else in the file, while still using git's own
            # matcher -- not a spelling list -- for arbitrary glob forms. If
            # NO negation line covers the tier, the file's OWN full current
            # content is checked once more: ignored means some OTHER
            # existing pattern already covers it (nothing to do); not
            # ignored means genuinely missing (append).
            $giprobeNegationPatterns = @()
            if ($giprobeRoot) {
                foreach ($line in $existingLines) {
                    if ($line.StartsWith("!", [System.StringComparison]::Ordinal)) {
                        $giprobeNegationPatterns += $line.Substring(1)
                    }
                }
            }

            foreach ($entry in $unresolved) {
                $altNoSlash = $entry.TrimStart("/").TrimEnd("/")
                $probe = "$altNoSlash/.orchestrarium-probe"
                if (-not $giprobeRoot) {
                    $declinedUnverifiable += $entry
                    continue
                }
                $scratchGitignore = Join-Path $giprobeRoot ".gitignore"

                $negationMatched = $false
                foreach ($pattern in $giprobeNegationPatterns) {
                    [System.IO.File]::WriteAllLines($scratchGitignore, [string[]]@($pattern), [System.Text.UTF8Encoding]::new($false))
                    $previousErrorActionPreference = $ErrorActionPreference
                    $ErrorActionPreference = "Continue"
                    $patternExitCode = 1
                    try {
                        & git -C $giprobeRoot check-ignore -q $probe 2>$null
                        $patternExitCode = $LASTEXITCODE
                    } catch {
                        $patternExitCode = 2
                    } finally {
                        $ErrorActionPreference = $previousErrorActionPreference
                    }
                    if ($patternExitCode -eq 0) {
                        $negationMatched = $true
                        break
                    }
                }
                if ($negationMatched) {
                    $declinedNegation += $entry
                    continue
                }

                [System.IO.File]::WriteAllLines($scratchGitignore, [string[]]$existingLines, [System.Text.UTF8Encoding]::new($false))
                $previousErrorActionPreference = $ErrorActionPreference
                $ErrorActionPreference = "Continue"
                $wholeFileExitCode = 1
                try {
                    & git -C $giprobeRoot check-ignore -q $probe 2>$null
                    $wholeFileExitCode = $LASTEXITCODE
                } catch {
                    $wholeFileExitCode = 2
                } finally {
                    $ErrorActionPreference = $previousErrorActionPreference
                }
                if ($wholeFileExitCode -eq 0) {
                    continue
                } elseif ($wholeFileExitCode -eq 1) {
                    $missing += $entry
                } else {
                    $declinedUnverifiable += $entry
                }
            }
        } finally {
            # Cleanup that MUST run even on an interrupt/abort/hung git:
            # PowerShell's `finally` executes during pipeline-stop
            # processing (Ctrl-C), unlike a bare end-of-script cleanup --
            # confirmed this session with a real interrupt sent mid-probe.
            if ($giprobeRoot -and (Test-Path -LiteralPath $giprobeRoot)) {
                Remove-Item -LiteralPath $giprobeRoot -Recurse -Force -ErrorAction SilentlyContinue
            }
            if ($null -eq $previousGitConfigNoSystem) {
                Remove-Item Env:\GIT_CONFIG_NOSYSTEM -ErrorAction SilentlyContinue
            } else {
                $env:GIT_CONFIG_NOSYSTEM = $previousGitConfigNoSystem
            }
            if ($null -eq $previousGitConfigGlobal) {
                Remove-Item Env:\GIT_CONFIG_GLOBAL -ErrorAction SilentlyContinue
            } else {
                $env:GIT_CONFIG_GLOBAL = $previousGitConfigGlobal
            }
            foreach ($varName in $giprobeRepoLocationVars) {
                if ($null -ne $giprobeSavedEnv[$varName]) {
                    [System.Environment]::SetEnvironmentVariable($varName, $giprobeSavedEnv[$varName])
                }
            }
        }
    }

    foreach ($entry in $declinedNegation) {
        # NOT "already un-ignored": this writer's probe reflects only THIS
        # file's own patterns at the moment it ran, not full multi-source
        # gitignore precedence (nested .gitignore files, global excludes).
        # So we report what this file's own negation currently does, not a
        # permanent verdict.
        Write-Host "  .gitignore: '$entry' has a '!' negation on file -- leaving as-is (not re-appending; a later broader ignore pattern could still re-ignore this tree, which this writer does not check)"
    }
    foreach ($entry in $declinedSentinel) {
        Write-Host "  .gitignore: '$entry' declined by operator (sentinel present) -- leaving as-is"
    }
    foreach ($entry in $declinedUnverifiable) {
        Write-Host "  .gitignore: '$entry' could not be checked against git (git unavailable or the check itself failed) -- leaving as-is rather than risk overriding an undetected '!' negation"
    }

    if ($missing.Count -eq 0) {
        if ($declinedNegation.Count -eq 0 -and $declinedSentinel.Count -eq 0 -and $declinedUnverifiable.Count -eq 0) {
            Write-Host "  .gitignore: local-only entries already present"
        }
        return
    }

    Write-Host "  Ensuring .gitignore ignores local-only task-memory paths..."
    if ($DryRun) {
        foreach ($entry in $missing) {
            if (Test-Path -LiteralPath $gitignore) {
                Write-Host "    [dry-run] would append '$entry' to $gitignore"
            } else {
                Write-Host "    [dry-run] would create $gitignore with '$entry'"
            }
        }
        return
    }

    if (-not (Test-Path -LiteralPath $gitignore)) {
        Set-Content -LiteralPath $gitignore -Value ($missing -join "`r`n")
        foreach ($entry in $missing) {
            Write-Host "    added '$entry' to $gitignore"
        }
        return
    }

    foreach ($entry in $missing) {
        Add-Content -LiteralPath $gitignore -Value "`r`n$entry"
        Write-Host "    added '$entry' to $gitignore"
    }
}

function Get-PreservedGeminiImports {
    param(
        [string[]]$Lines,
        [int]$ManagedStartLine,
        [int]$ManagedEndLine
    )

    $imports = @()
    if ($ManagedStartLine -lt 0 -or $ManagedEndLine -le $ManagedStartLine) {
        return $imports
    }

    $collectImports = $false
    for ($i = $ManagedStartLine + 1; $i -lt $ManagedEndLine; $i++) {
        $line = $Lines[$i]

        if (-not $collectImports) {
            if ($line -match '^@' -or [string]::IsNullOrWhiteSpace($line)) {
                $collectImports = $true
            } else {
                break
            }
        }

        if ($line -match '^@') {
            if ($line -ne '@./AGENTS.md' -and $line -ne '@./AGENTS.shared.md' -and $line -ne '@../shared/AGENTS.shared.md' -and $imports -notcontains $line) {
                $imports += $line
            }
            continue
        }

        if ([string]::IsNullOrWhiteSpace($line)) {
            continue
        }

        break
    }

    return $imports
}

function Get-MergedGeminiManagedContent {
    param(
        [string[]]$ExistingLines,
        [int]$ManagedStartLine,
        [int]$ManagedEndLine,
        [string]$SourceFile
    )

    $preservedPrefix = @()
    if ($ManagedStartLine -gt 0) {
        $preservedPrefix = $ExistingLines[0..($ManagedStartLine - 1)]
    }

    $preservedSuffix = @()
    if ($ManagedEndLine + 1 -lt $ExistingLines.Count) {
        $preservedSuffix = $ExistingLines[($ManagedEndLine + 1)..($ExistingLines.Count - 1)]
    }

    $preservedImports = Get-PreservedGeminiImports -Lines $ExistingLines -ManagedStartLine $ManagedStartLine -ManagedEndLine $ManagedEndLine
    $sourceLines = @((Get-Content -LiteralPath $SourceFile) | ForEach-Object { $_ -replace '^@(\./AGENTS\.shared\.md|\.\./shared/AGENTS\.shared\.md)$', '@./AGENTS.md' })
    $importLine = -1
    for ($i = 0; $i -lt $sourceLines.Count; $i++) {
        if ($sourceLines[$i] -match '^@') {
            $importLine = $i
            break
        }
    }

    $mergedManagedLines = $sourceLines
    if ($importLine -ge 0) {
        $tailStart = $importLine + 1
        while ($tailStart -lt $sourceLines.Count -and [string]::IsNullOrWhiteSpace($sourceLines[$tailStart])) {
            $tailStart++
        }

        $tailLines = @()
        if ($tailStart -lt $sourceLines.Count) {
            $tailLines = $sourceLines[$tailStart..($sourceLines.Count - 1)]
        }

        $mergedManagedLines = @()
        if ($importLine -gt 0) {
            $mergedManagedLines += $sourceLines[0..($importLine - 1)]
        }
        $mergedManagedLines += $sourceLines[$importLine]
        if ($preservedImports.Count -gt 0) {
            $mergedManagedLines += $preservedImports
        }
        if ($tailLines.Count -gt 0) {
            $mergedManagedLines += ""
            $mergedManagedLines += $tailLines
        }
    }

    $finalLines = @()
    if ($preservedPrefix.Count -gt 0) {
        $finalLines += $preservedPrefix
    }
    $finalLines += $mergedManagedLines
    if ($preservedSuffix.Count -gt 0) {
        $finalLines += $preservedSuffix
    }

    return ($finalLines -join "`n")
}

function Merge-GeminiFile {
    param([string]$SourceFile, [string]$TargetFile)

    $managed = (Get-Content -LiteralPath $SourceFile -Raw) -replace '@(\./AGENTS\.shared\.md|\.\./shared/AGENTS\.shared\.md)', '@./AGENTS.md'
    if (-not (Test-Path -LiteralPath $TargetFile)) {
        Write-Host "  Creating GEMINI.md..."
        if (-not $DryRun) {
            Set-Content -LiteralPath $TargetFile -Value $managed -NoNewline
        } else {
            Write-Host "    [dry-run] would create $TargetFile"
        }
        return
    }

    $existing = Get-Content -LiteralPath $TargetFile -Raw
    $lines = Get-Content -LiteralPath $TargetFile
    $managedStartLine = -1
    $managedEndLine = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -eq $ManagedStart -and $managedStartLine -lt 0) {
            $managedStartLine = $i
        }
        if ($lines[$i] -eq $ManagedEnd) {
            $managedEndLine = $i
            break
        }
    }

    if ($managedStartLine -ge 0 -and $managedEndLine -ge $managedStartLine) {
        Write-Host "  GEMINI.md: replacing managed Orchestrarium block..."
        if (-not $DryRun) {
            $updated = Get-MergedGeminiManagedContent -ExistingLines $lines -ManagedStartLine $managedStartLine -ManagedEndLine $managedEndLine -SourceFile $SourceFile
            Set-Content -LiteralPath $TargetFile -Value $updated -NoNewline
        } else {
            Write-Host "    [dry-run] would replace managed GEMINI.md block"
        }
        return
    }

    Write-Host "  GEMINI.md: prepending managed Orchestrarium block..."
    if (-not $DryRun) {
        Set-Content -LiteralPath $TargetFile -Value ($managed + "`r`n`r`n" + $existing) -NoNewline
    } else {
        Write-Host "    [dry-run] would prepend managed GEMINI.md block"
    }
}

function Install-PackFile {
    param(
        [string]$SourceFile,
        [string]$TargetFile,
        [string]$Label,
        [switch]$PreserveExisting
    )

    if (Test-Path -LiteralPath $TargetFile) {
        if ($PreserveExisting) {
            Write-Host "  Preserving existing $Label..."
            return
        }
        Write-Host "  Replacing $Label..."
        if (-not $DryRun) {
            Copy-Item -LiteralPath $SourceFile -Destination $TargetFile -Force
        } else {
            Write-Host "    [dry-run] would replace $TargetFile"
        }
        return
    }

    Write-Host "  Installing $Label..."
    if (-not $DryRun) {
        Copy-Item -LiteralPath $SourceFile -Destination $TargetFile -Force
    } else {
        Write-Host "    [dry-run] would create $TargetFile"
    }
}

function Install-UniversalHookHelpers {
    param(
        [string]$ScriptsTarget,
        [string]$HooksTarget
    )

    Ensure-Dir $ScriptsTarget
    Ensure-Dir $HooksTarget
    Write-Host "  Installing universal hook/helper scripts..."

    foreach ($scriptName in $UniversalRuntimeScriptNames) {
        Install-PackFile `
            -SourceFile (Join-Path $UniversalHookScriptsSource $scriptName) `
            -TargetFile (Join-Path $ScriptsTarget $scriptName) `
            -Label "extension universal hook/helper scripts/$scriptName"
    }

    foreach ($hookName in $UniversalRuntimeHookNames) {
        Install-PackFile `
            -SourceFile (Join-Path $UniversalHookHooksSource $hookName) `
            -TargetFile (Join-Path $HooksTarget $hookName) `
            -Label "extension universal hook/helper hooks/$hookName"
    }
}

function Sync-AgentsModeFile {
    param(
        [string]$TemplateFile,
        [string]$TargetFile,
        [string]$Label
    )

    $normalizer = Join-Path $RepoDir "scripts\normalize-agents-mode.py"
    $python = Get-PythonCommand

    if ($null -ne $python -and (Test-Path -LiteralPath $normalizer)) {
        if (Test-Path -LiteralPath $TargetFile) {
            Write-Host "  Normalizing existing $Label to current canonical format..."
        } else {
            Write-Host "  Installing canonical $Label..."
        }

        if (-not $DryRun) {
            & $python $normalizer --template $TemplateFile --target $TargetFile --provider shared
            if ($LASTEXITCODE -ne 0) {
                throw "agents-mode normalization failed for $TargetFile"
            }
        } else {
            Write-Host "    [dry-run] would normalize $TargetFile"
        }
        return
    }

    if (Test-Path -LiteralPath $TargetFile) {
        throw "Python is required to normalize existing $Label at $TargetFile."
    }

    Write-Host "  Installing canonical $Label..."
    if (-not $DryRun) {
        Copy-Item -LiteralPath $TemplateFile -Destination $TargetFile -Force
    } else {
        Write-Host "    [dry-run] would create $TargetFile"
    }
}

function Install-PackContent {
    param(
        [string]$Content,
        [string]$TargetFile,
        [string]$Label
    )

    Ensure-Dir (Split-Path -Parent $TargetFile)

    if (Test-Path -LiteralPath $TargetFile) {
        Write-Host "  Replacing $Label..."
        if (-not $DryRun) {
            Set-Content -LiteralPath $TargetFile -Value $Content -NoNewline
        } else {
            Write-Host "    [dry-run] would replace $TargetFile"
        }
        return
    }

    Write-Host "  Installing $Label..."
    if (-not $DryRun) {
        Set-Content -LiteralPath $TargetFile -Value $Content -NoNewline
    } else {
        Write-Host "    [dry-run] would create $TargetFile"
    }
}

function Remove-LegacyPackFile {
    param([string]$TargetFile, [string]$Label)

    if (-not (Test-Path -LiteralPath $TargetFile)) {
        return
    }

    Write-Host "  Removing legacy $Label..."
    if (-not $DryRun) {
        Remove-Item -LiteralPath $TargetFile -Force
    } else {
        Write-Host "    [dry-run] would remove $TargetFile"
    }
}

function Remove-EmptyDirIfPresent {
    param([string]$TargetDir)

    if (-not (Test-Path -LiteralPath $TargetDir -PathType Container)) {
        return
    }

    $children = @(Get-ChildItem -LiteralPath $TargetDir -Force)
    if ($children.Count -gt 0) {
        return
    }

    if (-not $DryRun) {
        Remove-Item -LiteralPath $TargetDir -Force
    } else {
        Write-Host "    [dry-run] would remove empty directory $TargetDir"
    }
}

function Remove-LegacyTopLevelPackEntries {
    param(
        [string]$SourceDir,
        [string]$TargetDir,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $TargetDir -PathType Container)) {
        return
    }

    foreach ($item in Get-ChildItem -LiteralPath $SourceDir -Force) {
        $targetPath = Join-Path $TargetDir $item.Name
        if (-not (Test-Path -LiteralPath $targetPath)) {
            continue
        }

        Write-Host "  Removing legacy $Label/$($item.Name)..."
        if (-not $DryRun) {
            Remove-Item -LiteralPath $targetPath -Recurse -Force
        } else {
            Write-Host "    [dry-run] would remove $targetPath"
        }
    }

    Remove-EmptyDirIfPresent -TargetDir $TargetDir
}

function Remove-LegacyMirroredFiles {
    param(
        [string]$SourceDir,
        [string]$TargetDir,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $TargetDir -PathType Container)) {
        return
    }

    $sourceRoot = [System.IO.Path]::GetFullPath($SourceDir)
    foreach ($file in Get-ChildItem -LiteralPath $SourceDir -Recurse -File -Force) {
        $relativePath = $file.FullName.Substring($sourceRoot.Length).TrimStart('\', '/')
        $targetPath = Join-Path $TargetDir $relativePath
        if (-not (Test-Path -LiteralPath $targetPath -PathType Leaf)) {
            continue
        }

        Write-Host "  Removing legacy $Label/$relativePath..."
        if (-not $DryRun) {
            Remove-Item -LiteralPath $targetPath -Force
        } else {
            Write-Host "    [dry-run] would remove $targetPath"
        }
    }

    $directories = @(Get-ChildItem -LiteralPath $TargetDir -Recurse -Directory -Force | Sort-Object FullName -Descending)
    foreach ($directory in $directories) {
        Remove-EmptyDirIfPresent -TargetDir $directory.FullName
    }
    Remove-EmptyDirIfPresent -TargetDir $TargetDir
}

# Roles are now skills-only (one SKILL.md per role under skills/). The former
# Gemini-native agents/ role layer is removed. This cleanup is source-independent
# (the source no longer ships agents/), so it works on upgrade from any prior install:
#   - extension tier: a pack-owned tree, safe to remove wholesale.
#   - user override tier ($AgentsTarget): remove ONLY the known pack-authored
#     basenames by static allowlist; never remove the whole dir, because it may
#     hold genuine user-authored subagents the pack must not touch.
$LegacyAgentBasenames = @(
    'accessibility-reviewer.md','algorithm-scientist.md','analyst.md','architect.md',
    'architecture-reviewer.md','backend-engineer.md','computational-scientist.md',
    'consultant.md','data-engineer.md','external-reviewer.md','external-worker.md',
    'frontend-engineer.md','geometry-engineer.md','graphics-engineer.md',
    'knowledge-archivist.md','lead.md','model-view-engineer.md','performance-engineer.md',
    'performance-reviewer.md','planner.md','platform-engineer.md','product-analyst.md',
    'product-manager.md','qa-engineer.md','qt-ui-engineer.md','reliability-engineer.md',
    'security-engineer.md','security-reviewer.md','toolchain-engineer.md',
    'ui-test-engineer.md','ux-designer.md','ux-reviewer.md','visualization-engineer.md'
)

function Remove-LegacyPath {
    param(
        [string]$Target,
        [string]$Label
    )

    if (-not (Test-Path -LiteralPath $Target)) {
        return
    }

    Write-Host "  Removing legacy $Label..."
    if (-not $DryRun) {
        Remove-Item -LiteralPath $Target -Recurse -Force
    } else {
        Write-Host "    [dry-run] would remove $Target"
    }
}

function Remove-LegacyAgentLayer {
    param(
        [string]$ExtensionRoot,
        [string]$AgentsTarget
    )

    # Extension tier: pack-owned, remove the whole stale agents/ tree.
    Remove-LegacyPath -Target (Join-Path $ExtensionRoot "agents") -Label "extension/agents (roles are skills-only)"

    # User override tier: remove only pack-authored basenames + the team-templates dir.
    if (Test-Path -LiteralPath $AgentsTarget -PathType Container) {
        foreach ($base in $LegacyAgentBasenames) {
            Remove-LegacyPath -Target (Join-Path $AgentsTarget $base) -Label "user-tier agents/$base"
        }
        Remove-LegacyPath -Target (Join-Path $AgentsTarget "README.md") -Label "user-tier agents/README.md"
        Remove-LegacyPath -Target (Join-Path $AgentsTarget "team-templates") -Label "user-tier agents/team-templates"
        Remove-EmptyDirIfPresent -TargetDir $AgentsTarget
    }
}

if ($Global) {
    if (-not $env:USERPROFILE) { throw "USERPROFILE is not set." }
    $Mode = "global"
    $InstallRoot = Get-CanonicalPath (Join-Path $env:USERPROFILE ".gemini")
} elseif ($Target) {
    $Mode = "target"
    $ProjectRoot = Resolve-ProjectRoot $Target
    Assert-SafeProjectRoot -ProjectRoot $ProjectRoot -Mode $Mode
} else {
    $Mode = "repo"
    $ProjectRoot = Get-RepoRoot
}

$ExtensionName = Get-GeminiExtensionName -ManifestPath $ExtensionManifestSource

if ($Mode -eq "global") {
    $SkillsTarget = Join-Path $InstallRoot "skills"
    $AgentsTarget = Join-Path $InstallRoot "agents"
    $CommandsTarget = Join-Path $InstallRoot "commands"
    $ExtensionsTarget = Join-Path $InstallRoot "extensions"
    $ExtensionRoot = Join-Path $ExtensionsTarget $ExtensionName
    $AgentsModeTarget = Join-Path $InstallRoot ".agents-mode.yaml"
    $LegacyAgentsModeTarget = Join-Path $InstallRoot ".agents-mode"
    $GeminiTarget = Join-Path $InstallRoot "GEMINI.md"
    $SharedTarget = Join-Path $InstallRoot "AGENTS.md"
    $LegacySharedTarget = Join-Path $InstallRoot "AGENTS.shared.md"
} else {
    $InstallRoot = Join-Path $ProjectRoot ".gemini"
    $SkillsTarget = Join-Path $InstallRoot "skills"
    $AgentsTarget = Join-Path $InstallRoot "agents"
    $CommandsTarget = Join-Path $InstallRoot "commands"
    $ExtensionsTarget = Join-Path $InstallRoot "extensions"
    $ExtensionRoot = Join-Path $ExtensionsTarget $ExtensionName
    $AgentsModeTarget = Join-Path $InstallRoot ".agents-mode.yaml"
    $LegacyAgentsModeTarget = Join-Path $InstallRoot ".agents-mode"
    $GeminiTarget = Join-Path $ProjectRoot "GEMINI.md"
    $SharedTarget = Join-Path $ProjectRoot "AGENTS.md"
    $LegacySharedTarget = Join-Path $ProjectRoot "AGENTS.shared.md"
}

$ExtensionManifestTarget = Join-Path $ExtensionRoot "gemini-extension.json"
$ExtensionReadmeTarget = Join-Path $ExtensionRoot "README.md"
$ExtensionGeminiTarget = Join-Path $ExtensionRoot "GEMINI.md"
$ExtensionAgentsTarget = Join-Path $ExtensionRoot "AGENTS.md"
$ExtensionScriptsTarget = Join-Path $ExtensionRoot "scripts"
$ExtensionHooksTarget = Join-Path $ExtensionRoot "hooks"
$LegacyExtensionSharedTarget = Join-Path $ExtensionRoot "AGENTS.shared.md"

Write-Host "=== Orchestrarium Gemini Example Pack Installer ===" -ForegroundColor Cyan
Write-Host "Source: $Source"
Write-Host "Mode:   $Mode"
Write-Host "Runtime root: $InstallRoot"
Write-Host "GEMINI.md:    $GeminiTarget"
Write-Host "AGENTS.md:    $SharedTarget"
Write-Host "agents-mode:  $AgentsModeTarget"
Write-Host "Extension:    $ExtensionRoot"
Write-Host "Legacy user tier cleanup roots: $SkillsTarget ; $AgentsTarget ; $CommandsTarget"
Write-Host "Policy:       example-only / WEAK MODEL / NOT RECOMMENDED; production auto routing stays on codex|claude"
if ($DryRun) { Write-Host "Mode:   dry-run" -ForegroundColor Yellow }
Write-Host ""

if (-not (Test-Path -LiteralPath (Join-Path $Source "skills"))) { throw "Missing source skills/ directory." }
if (-not (Test-Path -LiteralPath (Join-Path $Source "commands"))) { throw "Missing source commands/ directory." }
if (-not (Test-Path -LiteralPath $ExtensionManifestSource)) { throw "Missing source Gemini extension manifest." }
if (-not (Test-Path -LiteralPath $ExtensionReadmeSource)) { throw "Missing source Gemini extension README." }
if (-not (Test-Path -LiteralPath (Join-Path $Source "GEMINI.md"))) { throw "Missing source GEMINI.md." }
if (-not (Test-Path -LiteralPath $SharedAgentsSource)) { throw "Missing shared AGENTS.shared.md." }
if (-not (Test-Path -LiteralPath $DefaultAgentsModeSource)) { throw "Missing source agents-mode.defaults.yaml." }
if (-not (Test-Path -LiteralPath $UniversalHookScriptsSource -PathType Container) -or -not (Test-Path -LiteralPath $UniversalHookHooksSource -PathType Container)) {
    throw "Missing universal hook/helper sources under $(Join-Path $RepoDir 'scripts/universal-hooks')."
}
foreach ($scriptName in $UniversalRuntimeScriptNames) {
    if (-not (Test-Path -LiteralPath (Join-Path $UniversalHookScriptsSource $scriptName) -PathType Leaf)) {
        throw "Missing universal hook/helper script $scriptName."
    }
}
foreach ($hookName in $UniversalRuntimeHookNames) {
    if (-not (Test-Path -LiteralPath (Join-Path $UniversalHookHooksSource $hookName) -PathType Leaf)) {
        throw "Missing universal hook/helper hook $hookName."
    }
}

if ((Test-Path -LiteralPath $SkillsTarget) -or (Test-Path -LiteralPath $AgentsTarget) -or (Test-Path -LiteralPath $CommandsTarget) -or (Test-Path -LiteralPath $ExtensionRoot) -or (Test-Path -LiteralPath $GeminiTarget) -or (Test-Path -LiteralPath $SharedTarget)) {
    if (-not (Confirm-Action "Proceed with reinstall/update of the Gemini pack?")) {
        Write-Host "Install cancelled by user." -ForegroundColor Yellow
        exit 1
    }
}

Ensure-Dir $InstallRoot
Install-Tree -SourceDir (Join-Path $Source "skills") -TargetDir (Join-Path $ExtensionRoot "skills") -Label "extension/skills"
Install-Tree -SourceDir (Join-Path $Source "commands") -TargetDir (Join-Path $ExtensionRoot "commands") -Label "extension/commands"
Install-UniversalHookHelpers -ScriptsTarget $ExtensionScriptsTarget -HooksTarget $ExtensionHooksTarget
Merge-GeminiFile -SourceFile (Join-Path $Source "GEMINI.md") -TargetFile $GeminiTarget
if ($Mode -eq "global") {
    Install-PackFile -SourceFile $SharedAgentsSource -TargetFile $SharedTarget -Label "AGENTS.md"
} else {
    Install-PackFile -SourceFile $SharedAgentsSource -TargetFile $SharedTarget -Label "AGENTS.md" -PreserveExisting
    Ensure-LocalOnlyGitignoreEntries -ProjectRoot $ProjectRoot
}
Install-PackFile -SourceFile $ExtensionManifestSource -TargetFile $ExtensionManifestTarget -Label "extension manifest"
Install-PackFile -SourceFile $ExtensionReadmeSource -TargetFile $ExtensionReadmeTarget -Label "extension README"
Install-PackContent -Content ((Get-Content -LiteralPath (Join-Path $Source "GEMINI.md") -Raw) -replace '@(\./AGENTS\.shared\.md|\.\./shared/AGENTS\.shared\.md)', '@./AGENTS.md') -TargetFile $ExtensionGeminiTarget -Label "extension GEMINI.md"
Install-PackContent -Content (Get-Content -LiteralPath $SharedAgentsSource -Raw) -TargetFile $ExtensionAgentsTarget -Label "extension AGENTS.md"
Migrate-LegacyAgentsModeFile -LegacyFile $LegacyAgentsModeTarget -TargetFile $AgentsModeTarget -Label ".agents-mode.yaml"
Sync-AgentsModeFile -TemplateFile $DefaultAgentsModeSource -TargetFile $AgentsModeTarget -Label ".agents-mode.yaml"

# Shared cross-pack global .agents-mode.yaml at $HOME/.agents-mode.yaml — lowest-precedence
# fallback layer below pack-local globals. Idempotent across all 4 pack installers.
if ($Mode -eq "global") {
    $SharedGlobalAgentsMode = Join-Path $HOME ".agents-mode.yaml"
    Sync-AgentsModeFile -TemplateFile $DefaultAgentsModeSource -TargetFile $SharedGlobalAgentsMode -Label "shared global ~/.agents-mode.yaml"
}

Remove-LegacyPackFile -TargetFile $LegacySharedTarget -Label "AGENTS.shared.md"
Remove-LegacyPackFile -TargetFile $LegacyExtensionSharedTarget -Label "extension AGENTS.shared.md"
Remove-LegacyTopLevelPackEntries -SourceDir (Join-Path $Source "skills") -TargetDir $SkillsTarget -Label "skills"
Remove-LegacyAgentLayer -ExtensionRoot $ExtensionRoot -AgentsTarget $AgentsTarget
Remove-LegacyMirroredFiles -SourceDir (Join-Path $Source "commands") -TargetDir $CommandsTarget -Label "commands"

if ($DryRun) {
    Write-Host ""
    Write-Host "RESULT: DRY-RUN complete (no files modified)."
    exit 0
}

Write-Host ""
Write-Host "=== Verification ===" -ForegroundColor Cyan
$errors = 0
foreach ($path in @(
    $GeminiTarget,
    $SharedTarget,
    $AgentsModeTarget,
    $ExtensionManifestTarget,
    $ExtensionGeminiTarget,
    $ExtensionAgentsTarget,
    (Join-Path $ExtensionRoot "skills\lead\SKILL.md"),
    (Join-Path $ExtensionRoot "skills\init-project\SKILL.md"),
    (Join-Path $ExtensionRoot "skills\lead\team-templates\full-delivery.json"),
    (Join-Path $ExtensionScriptsTarget "check-bugfix-discipline.py"),
    (Join-Path $ExtensionScriptsTarget "check-work-items-archival-stop.py"),
    (Join-Path $ExtensionScriptsTarget "mcp-usage-reminder.sh"),
    (Join-Path $ExtensionHooksTarget "check-machine-local-path.py"),
    (Join-Path $ExtensionHooksTarget "check-no-trash-in-repo.py"),
    (Join-Path $ExtensionRoot "commands\agents\help.toml")
)) {
    if (Test-Path -LiteralPath $path) {
        Write-Host "  OK  $path" -ForegroundColor Green
    } else {
        Write-Host "  FAIL  $path" -ForegroundColor Red
        $errors++
    }
}

foreach ($legacyPath in @(
    (Join-Path $SkillsTarget "lead\SKILL.md"),
    (Join-Path $ExtensionRoot "agents"),
    (Join-Path $AgentsTarget "lead.md"),
    (Join-Path $AgentsTarget "team-templates\full-delivery.json"),
    (Join-Path $CommandsTarget "agents\help.toml"),
    (Join-Path $CommandsTarget "agents\external-brigade.toml"),
    (Join-Path $CommandsTarget "agents\init-project.toml")
)) {
    if (Test-Path -LiteralPath $legacyPath) {
        Write-Host "  FAIL  legacy duplicate still present: $legacyPath" -ForegroundColor Red
        $errors++
    } else {
        Write-Host "  OK  no legacy duplicate at $legacyPath" -ForegroundColor Green
    }
}

if ($errors -gt 0) {
    Write-Host ""
    Write-Host "RESULT: FAIL ($errors errors)" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "RESULT: OK - Gemini example pack installed" -ForegroundColor Green

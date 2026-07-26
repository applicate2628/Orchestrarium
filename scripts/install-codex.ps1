<#
.SYNOPSIS
    Install Codex pack.
.DESCRIPTION
    Copies the skills tree and AGENTS.md to the target location.
    Re-running = reinstall.
.EXAMPLE
    .\scripts\install-codex.ps1                          # Install into current repo (.agents/ + AGENTS.md)
    .\scripts\install-codex.ps1 -Global                  # Install into ~/.codex/
    .\scripts\install-codex.ps1 -Target "D:\my-repo"     # Install into D:\my-repo as a project (.agents/ + AGENTS.md)
#>
param(
    [switch]$Global,
    [string]$Target,
    [switch]$Force,
    [switch]$DryRun,
    [switch]$AllowUnsafeTarget,
    [switch]$NoHypothesisHook
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoDir = Split-Path -Parent $ScriptDir
$Source = Join-Path $RepoDir "src.codex"
$AgentsSource = Join-Path $Source "agents"
$SharedAgentsModeSource = Join-Path $RepoDir "shared\agents-mode.defaults.yaml"
$script:CodexPackBeginMarker = "<!-- BEGIN ORCHESTRARIUM CODEX PACK -->"
$script:CodexPackEndMarker = "<!-- END ORCHESTRARIUM CODEX PACK -->"

$script:PromptMode = $null

function Test-Interactive {
    try {
        return [Environment]::UserInteractive -and -not [Console]::IsInputRedirected
    } catch {
        return $false
    }
}

function Get-CanonicalPath {
    param([string]$Path)

    $expanded = [Environment]::ExpandEnvironmentVariables($Path).Trim('"').Trim()
    if ([string]::IsNullOrWhiteSpace($expanded)) {
        throw "Path is empty."
    }

    try {
        return (Resolve-Path -LiteralPath $expanded -ErrorAction Stop).Path
    } catch {
        return [System.IO.Path]::GetFullPath($expanded)
    }
}

function Resolve-InstallTarget {
    param([string]$InputPath)

    $resolved = Get-CanonicalPath -Path $InputPath
    if ((Split-Path -Leaf $resolved).ToLowerInvariant() -eq ".codex") {
        return $resolved
    }
    return (Join-Path $resolved ".codex")
}

function Get-GitRepoRoot {
    try {
        $repoRoot = git rev-parse --show-toplevel 2>$null
        if ($repoRoot) {
            return (Get-CanonicalPath $repoRoot)
        }
    } catch {
        # fallback below
    }
    return (Get-CanonicalPath (Get-Location).Path)
}

function Test-PathNoReparseChain {
    param([string]$Path)

    $current = $Path
    while ($true) {
        if (Test-Path -LiteralPath $current -ErrorAction SilentlyContinue) {
            $item = Get-Item -LiteralPath $current -Force
            if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "Refusing reparse-point target path: $current"
            }
        }

        $parent = Split-Path -Parent $current
        if ([string]::IsNullOrWhiteSpace($parent) -or $parent -eq $current) {
            break
        }
        $current = $parent
    }
}

function Get-AllowlistRoots {
    param([string]$Mode)

    $list = @()
    if ($Mode -eq "repo") {
        $repoRoot = Get-GitRepoRoot
        $list += Resolve-InstallTarget -InputPath (Join-Path $repoRoot ".codex")
    }

    if ($Mode -eq "global") {
        if (-not $env:USERPROFILE) {
            throw "USERPROFILE is not set."
        }
        $list += Resolve-InstallTarget -InputPath (Join-Path $env:USERPROFILE ".codex")
    }

    if ($Mode -eq "target") {
        $repoRoot = Get-GitRepoRoot
        $list += Resolve-InstallTarget -InputPath (Join-Path $repoRoot ".codex")
        if ($env:USERPROFILE) {
            $list += Resolve-InstallTarget -InputPath (Join-Path $env:USERPROFILE ".codex")
        }
    }

    if ($env:CODEX_INSTALL_ALLOWLIST) {
        $envPaths = $env:CODEX_INSTALL_ALLOWLIST -split ","
        foreach ($entry in $envPaths) {
            if ([string]::IsNullOrWhiteSpace($entry)) { continue }
            try {
                $list += Resolve-InstallTarget -InputPath (Get-CanonicalPath $entry)
            } catch {
                $list += Get-CanonicalPath $entry
            }
        }
    }

    return ($list | ForEach-Object { $_.ToLowerInvariant() } | Sort-Object -Unique)
}

function Assert-SafeInstallRoot {
    param([string]$Path, [string]$Mode)

    Test-PathNoReparseChain -Path $Path
    $target = Resolve-InstallTarget -InputPath $Path

    if ((Split-Path -Leaf $target).ToLowerInvariant() -ne ".codex") {
        throw "Target must resolve to a .codex directory."
    }

    Test-PathNoReparseChain -Path $target

    $allowlist = Get-AllowlistRoots -Mode $Mode
    if ($Mode -eq "target" -and -not $AllowUnsafeTarget -and $allowlist.Count -gt 0) {
        $normalized = $target.ToLowerInvariant()
        $isAllowed = $false
        foreach ($item in $allowlist) {
            if ($normalized -eq $item) {
                $isAllowed = $true
                break
            }
        }

        if (-not $isAllowed) {
            if (Test-Interactive) {
                Write-Host "WARNING: target '$target' is outside the default allowlist. Suspicious paths are blocked." -ForegroundColor Yellow
                while ($true) {
                    $rawAnswer = Read-Host "Type 'ALLOW' to proceed with this target"
                    $answer = if ($null -eq $rawAnswer) { "" } else { $rawAnswer.Trim() }
                    if ($answer.ToUpperInvariant() -eq "ALLOW") {
                        break
                    }
                    if ($answer -eq "") {
                        throw "Install cancelled: unsafe target denied."
                    }
                    Write-Host "Please type ALLOW to confirm, or press Enter to cancel." -ForegroundColor Yellow
                }
            } else {
                throw "Unsafe target denied for non-interactive install. Use -AllowUnsafeTarget to override."
            }
        }
    }

    return $target
}

function Read-InstallMode {
    Write-Host ""
    Write-Host "Select installation target:"
    Write-Host "  1) Local repo (.agents/skills + root AGENTS.md)"
    Write-Host "  2) Global (~/.codex/)"
    Write-Host "  3) Custom project directory (.agents/skills + root AGENTS.md)"
    Write-Host "  4) Abort"

    while ($true) {
        $choice = Read-Host "Choose [1-4, default: 1]"
        if ([string]::IsNullOrWhiteSpace($choice)) {
            $choice = "1"
        }
        switch ($choice.Trim()) {
            "1" {
                $script:PromptMode = "repo"
                return (Join-Path (Get-GitRepoRoot) ".codex")
            }
            "2" {
                $script:PromptMode = "global"
                if ($env:USERPROFILE) {
                    return (Join-Path $env:USERPROFILE ".codex")
                }
                Write-Host "FAIL: USERPROFILE is not set." -ForegroundColor Red
                throw "Cannot resolve global install path."
            }
            "3" {
                $script:PromptMode = "target"
                $custom = Read-Host "Enter target directory path"
                if ([string]::IsNullOrWhiteSpace($custom)) {
                    Write-Host "Target cannot be empty." -ForegroundColor Yellow
                    continue
                }
                return $custom
            }
            "4" {
                Write-Host "Install aborted by user." -ForegroundColor Yellow
                exit 1
            }
            default {
                Write-Host "Please enter 1, 2, 3, or 4." -ForegroundColor Yellow
            }
        }
    }
}

# Per-skill install preserves user-added skills — no destructive directory wipe needed.

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

    if (-not (Test-Path -LiteralPath $TargetDir)) {
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

function Install-SkillDirectory {
    param(
        [string]$SourceDir,
        [string]$TargetDir,
        [string]$Label
    )

    if (Test-Path -LiteralPath $TargetDir) {
        if (Test-DirectoryContentEqual -SourceDir $SourceDir -TargetDir $TargetDir) {
            Write-Host "    OK  $Label unchanged"
            return
        }

        if (-not $DryRun) {
            Remove-Item -Recurse -Force $TargetDir
            Copy-Item -Recurse -Force $SourceDir $TargetDir
        } else {
            Write-Host "    [dry-run] would replace $Label"
        }
    } else {
        if (-not $DryRun) {
            Copy-Item -Recurse -Force $SourceDir $TargetDir
        } else {
            Write-Host "    [dry-run] would install $Label"
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
                    # This write's own failure must fail the probe CLOSED,
                    # the same way the `git init` check above already does:
                    # `catch` alone does not observe a native command's exit
                    # code, so $LASTEXITCODE is checked explicitly -- a probe
                    # that cannot CONFIRM core.excludesFile is neutralized is
                    # not merely unhardened, it is UNVERIFIABLE, and must
                    # never be trusted to decide "already ignored" for real --
                    # an external review forced this failure and confirmed
                    # the ambient leak survives silently without this check.
                    $previousErrorActionPreference = $ErrorActionPreference
                    $ErrorActionPreference = "Continue"
                    $giprobeExcludesConfigured = $false
                    try {
                        & git -C $giprobeRoot config core.excludesFile "$giprobeRoot.noexcludes" 2>$null
                        if ($LASTEXITCODE -eq 0) {
                            $giprobeExcludesConfigured = $true
                        }
                    } catch {
                    } finally {
                        $ErrorActionPreference = $previousErrorActionPreference
                    }
                    if (-not $giprobeExcludesConfigured) {
                        Remove-Item -LiteralPath $giprobeRoot -Recurse -Force -ErrorAction SilentlyContinue
                        $giprobeRoot = $null
                    }
                }
                if ($giprobeRoot) {
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

function Remove-DanglingLink {
    param(
        [string]$Path,
        [string]$Label
    )

    $item = Get-Item -LiteralPath $Path -Force -ErrorAction SilentlyContinue
    if ($null -ne $item -and (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) -and -not (Test-Path -LiteralPath $Path)) {
        Write-Host "  Removing dangling symlink for $Label..."
        if ($DryRun) {
            Write-Host "    [dry-run] would remove dangling symlink $Path"
        } else {
            Remove-Item -LiteralPath $Path -Force
        }
    }
}

function Get-NormalizedCodexAgentOverrideContent {
    param([string]$Content)

    $normalized = $Content -replace "`r`n", "`n"
    $normalized = $normalized -replace "`r", "`n"
    $normalized = [regex]::Replace(
        $normalized,
        '(?m)^model\s*=\s*"[^"]*"\s*$',
        'model = "<model>"'
    )
    return $normalized.TrimEnd("`n")
}

function Get-LegacyCodexAgentOverrideTemplate {
    param([string]$Name)

    switch ($Name) {
        "default.toml" {
            return @'
name = "default"
description = "General-purpose fallback agent."
model = "<model>"
model_reasoning_effort = "xhigh"
developer_instructions = """
General-purpose fallback agent.
Inherit the parent session's task context and focus on the assigned subtask.
Stay within the requested scope and return a concise, usable result.
"""
'@
        }
        "worker.toml" {
            return @'
name = "worker"
description = "Execution-focused agent for implementation and fixes."
model = "<model>"
model_reasoning_effort = "xhigh"
developer_instructions = """
Execution-focused agent for implementation and fixes.
Carry out the assigned implementation task directly, stay within scope, and avoid redesign unless the parent explicitly asks for it.
Return concrete progress and outcomes for the requested slice.
"""
'@
        }
        "explorer.toml" {
            return @'
name = "explorer"
description = "Read-heavy codebase exploration agent."
model = "<model>"
model_reasoning_effort = "xhigh"
developer_instructions = """
Read-heavy codebase exploration agent.
Stay in exploration mode, gather evidence efficiently, and return factual findings with clear pointers.
Do not drift into implementation unless the parent explicitly asks for it.
"""
'@
        }
        default {
            return $null
        }
    }
}

function Test-PackOwnedCodexAgentOverride {
    param(
        [string]$SourceFile,
        [string]$TargetFile
    )

    $name = Split-Path $SourceFile -Leaf
    $targetNorm = Get-NormalizedCodexAgentOverrideContent -Content (Get-Content -LiteralPath $TargetFile -Raw)
    $sourceNorm = Get-NormalizedCodexAgentOverrideContent -Content (Get-Content -LiteralPath $SourceFile -Raw)
    if ($targetNorm -eq $sourceNorm) {
        return $true
    }

    $legacyTemplate = Get-LegacyCodexAgentOverrideTemplate -Name $name
    if ($null -ne $legacyTemplate) {
        $legacyNorm = Get-NormalizedCodexAgentOverrideContent -Content $legacyTemplate
        if ($targetNorm -eq $legacyNorm) {
            return $true
        }
    }

    return $false
}

function Ensure-CodexAgentOverrideFile {
    param(
        [string]$SourceFile,
        [string]$TargetFile,
        [string]$Label
    )

    Remove-DanglingLink -Path $TargetFile -Label $Label

    if (Test-Path -LiteralPath $TargetFile) {
        if (Test-PackOwnedCodexAgentOverride -SourceFile $SourceFile -TargetFile $TargetFile) {
            if ((Get-FileHash -LiteralPath $SourceFile).Hash -eq (Get-FileHash -LiteralPath $TargetFile).Hash) {
                Write-Host "  OK  $Label unchanged"
            } else {
                Write-Host "  Refreshing stale pack-owned $Label..."
                if (-not $DryRun) {
                    Copy-Item -LiteralPath $SourceFile -Destination $TargetFile -Force
                } else {
                    Write-Host "    [dry-run] would replace $TargetFile"
                }
            }
        } else {
            Write-Host "  Preserving existing custom $Label..."
        }
        return
    }

    Write-Host "  Installing default $Label..."
    if (-not $DryRun) {
        Copy-Item -LiteralPath $SourceFile -Destination $TargetFile -Force
    } else {
        Write-Host "    [dry-run] would create $TargetFile"
    }
}

function Migrate-LegacyAgentsModeFile {
    param(
        [string]$LegacyFile,
        [string]$TargetFile,
        [string]$Label
    )

    Remove-DanglingLink -Path $LegacyFile -Label ("legacy {0}" -f $Label)
    Remove-DanglingLink -Path $TargetFile -Label $Label

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

function Write-CodexDefaultAgentsModeFile {
    param(
        [string]$TemplateFile,
        [string]$TargetFile
    )

    $content = Get-Content -LiteralPath $TemplateFile -Raw
    if ($content -notmatch "(?m)^externalClaudeProfile:") {
        if (-not $content.EndsWith("`n")) {
            $content += "`n"
        }
        $content += "externalClaudeProfile: opus-xhigh  # allowed: sonnet-high | opus-xhigh | opus-max | fable-xhigh; default: opus-xhigh`n"
    }
    Set-Content -LiteralPath $TargetFile -Value $content -NoNewline
}

function Sync-AgentsModeFile {
    param(
        [string]$TemplateFile,
        [string]$TargetFile,
        [string]$Label,
        [ValidateSet("codex", "shared")]
        [string]$Provider
    )

    Remove-DanglingLink -Path $TargetFile -Label $Label

    $normalizer = Join-Path $RepoDir "scripts\normalize-agents-mode.py"
    $python = Get-PythonCommand

    if ($null -ne $python -and (Test-Path -LiteralPath $normalizer)) {
        if (Test-Path -LiteralPath $TargetFile) {
            Write-Host "  Normalizing existing $Label to current canonical format..."
        } else {
            Write-Host "  Installing canonical $Label..."
        }

        if (-not $DryRun) {
            & $python $normalizer --template $TemplateFile --target $TargetFile --provider $Provider
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
        if ($Provider -eq "codex") {
            Write-CodexDefaultAgentsModeFile -TemplateFile $TemplateFile -TargetFile $TargetFile
        } else {
            Copy-Item -LiteralPath $TemplateFile -Destination $TargetFile -Force
        }
    } else {
        Write-Host "    [dry-run] would create $TargetFile"
    }
}

function Get-CodexPackStartIndex {
    param([string[]]$Lines)

    for ($i = 0; $i -lt $Lines.Count; $i++) {
        if ($Lines[$i] -eq $script:CodexPackBeginMarker) {
            return $i
        }
        if ($Lines[$i] -match "^# Shared Governance$" -or $Lines[$i] -match "^# Codex Platform Rules$" -or $Lines[$i] -match "^# Default Delegation Rule$") {
            return $i
        }
    }

    return -1
}

function Get-CodexPackEndIndex {
    param(
        [string[]]$ExistingLines,
        [int]$PackStart,
        [string[]]$SourceLines
)

    for ($i = $PackStart; $i -lt $ExistingLines.Count; $i++) {
        if ($ExistingLines[$i] -eq $script:CodexPackEndMarker) {
            return $i
        }
    }

    for ($i = ($PackStart + 1); $i -lt $ExistingLines.Count; $i++) {
        if ($ExistingLines[$i] -eq "## Project policies") {
            return ($i - 1)
        }
    }

    $footer = $null
    for ($i = $SourceLines.Count - 1; $i -ge 0; $i--) {
        if (-not [string]::IsNullOrWhiteSpace($SourceLines[$i])) {
            $footer = $SourceLines[$i]
            break
        }
    }

    if ($footer) {
        for ($i = $PackStart; $i -lt $ExistingLines.Count; $i++) {
            if ($ExistingLines[$i] -eq $footer) {
                return $i
            }
        }
    }

    $fallback = $PackStart + $SourceLines.Count - 1
    if ($fallback -ge $ExistingLines.Count) {
        return ($ExistingLines.Count - 1)
    }

    return $fallback
}

function Get-MergedCodexAgentsContent {
    param(
        [string[]]$ExistingLines,
        [int]$PackStart,
        [string]$SourcePath
    )

    $sourceLines = Get-Content $SourcePath
    $packEnd = Get-CodexPackEndIndex -ExistingLines $ExistingLines -PackStart $PackStart -SourceLines $sourceLines

    $finalLines = @()
    if ($PackStart -gt 0) {
        $finalLines += $ExistingLines[0..($PackStart - 1)]
    }
    $finalLines += $sourceLines
    if ($packEnd + 1 -lt $ExistingLines.Count) {
        $finalLines += $ExistingLines[($packEnd + 1)..($ExistingLines.Count - 1)]
    }

    return ($finalLines -join "`n")
}

# Determine target
if ($Global) {
    $repoRoot = Get-GitRepoRoot
    try {
        $TargetRoot = Assert-SafeInstallRoot -Path (Join-Path $env:USERPROFILE ".codex") -Mode "global"
    } catch {
        Write-Host "FAIL: Cannot resolve global target: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
    $Mode = "global"
} elseif ($Target) {
    try {
        $TargetRoot = Assert-SafeInstallRoot -Path $Target -Mode "target"
    } catch {
        Write-Host "FAIL: Cannot resolve target '$Target': $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
    $Mode = "target"
} else {
    if (Test-Interactive) {
        $interactiveTarget = Read-InstallMode
        $Mode = $script:PromptMode
        if (-not $Mode) {
            $Mode = "repo"
        }
        try {
            $TargetRoot = Assert-SafeInstallRoot -Path $interactiveTarget -Mode $Mode
        } catch {
            Write-Host "FAIL: Cannot resolve target: $($_.Exception.Message)" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host "FAIL: No install target specified and not running interactively." -ForegroundColor Red
        Write-Host "Use: .\scripts\install-codex.ps1 -Global  or  .\scripts\install-codex.ps1 -Target <path>" -ForegroundColor Yellow
        exit 1
    }
}

# Derive per-mode target paths.
# Global: everything goes into ~/.codex/ (mirrors src.codex/).
# Repo/target: skills go into .agents/skills/,
#              AGENTS.md merges into project root AGENTS.md.
if ($Mode -eq "global") {
    $AgentsRoot = $TargetRoot
    $SkillsTarget = Join-Path $TargetRoot "skills"
    $AgentOverridesTarget = Join-Path $TargetRoot "agents"
    $LeadScriptsTarget = Join-Path $TargetRoot "skills\lead\scripts"
    $MdTarget = Join-Path $TargetRoot "AGENTS.md"
} else {
    $ProjectRoot = Split-Path $TargetRoot -Parent
    $AgentsRoot = Join-Path $ProjectRoot ".agents"
    $SkillsTarget = Join-Path $AgentsRoot "skills"
    $AgentOverridesTarget = Join-Path $TargetRoot "agents"
    $LeadScriptsTarget = Join-Path $SkillsTarget "lead\scripts"
    $MdTarget = Join-Path $ProjectRoot "AGENTS.md"
}
$AgentsModeTarget = Join-Path $AgentsRoot ".agents-mode.yaml"
$LegacyAgentsModeTarget = Join-Path $AgentsRoot ".agents-mode"

Write-Host "=== Codex Installer ===" -ForegroundColor Cyan
Write-Host "Source: $Source"
Write-Host "Skills target: $SkillsTarget"
Write-Host "Built-in agent overrides: $AgentOverridesTarget"
Write-Host "AGENTS.md target: $MdTarget"
Write-Host "agents-mode: $AgentsModeTarget"
Write-Host "Mode:   $Mode"
if ($DryRun) {
    Write-Host "Mode:   dry-run" -ForegroundColor Yellow
}
Write-Host ""

# Verify source
if (-not (Test-Path (Join-Path $Source "skills"))) {
    Write-Host "FAIL: Source directory $Source\skills not found." -ForegroundColor Red
    Write-Host "Run this script from the Orchestrarium repo root."
    exit 1
}
if (-not (Test-Path -LiteralPath $AgentsSource)) {
    Write-Host "FAIL: Source directory $AgentsSource not found." -ForegroundColor Red
    Write-Host "Run this script from the Orchestrarium repo root."
    exit 1
}
if (-not (Test-Path -LiteralPath $SharedAgentsModeSource)) {
    Write-Host "FAIL: Missing shared agents-mode template at $SharedAgentsModeSource." -ForegroundColor Red
    exit 1
}

# Create parent directories as needed
foreach ($tdir in @($SkillsTarget, $AgentOverridesTarget)) {
    $parent = Split-Path $tdir -Parent
    if (-not (Test-Path -LiteralPath $parent)) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path $parent -Force | Out-Null
        } else {
            Write-Host "[dry-run] would create: $parent"
        }
    }
}

# Count and confirm reinstall
$packCount = (Get-ChildItem -LiteralPath (Join-Path $Source "skills") -Directory).Count
$existingCount = 0
if (Test-Path -LiteralPath $SkillsTarget) {
    $existingCount = (Get-ChildItem -LiteralPath $SkillsTarget -Directory -ErrorAction SilentlyContinue).Count
}
if ($existingCount -gt 0 -and -not $Force -and -not $DryRun -and (Test-Interactive)) {
    $userCount = $existingCount - $packCount
    if ($userCount -lt 0) { $userCount = 0 }
    Write-Host ""
    Write-Host "  Reinstall will replace $packCount pack skills. $userCount user skill(s) will be preserved."
    $confirmed = $false
    while (-not $confirmed) {
        $rawAnswer = Read-Host "  Proceed? [y/N]"
        $answer = if ($null -eq $rawAnswer) { "" } else { $rawAnswer.Trim().ToLower() }
        switch -Regex ($answer) {
            "^(y|yes)$" { $confirmed = $true }
            "^n$|^no$|^$" { Write-Host "Install cancelled by user." -ForegroundColor Yellow; exit 1 }
            default { Write-Host "  Please answer y or n." }
        }
    }
}

# Per-skill install: only replace pack skills, preserve user-added skills
Write-Host "  Installing skills (per-skill, preserving user-added skills)..."
if (-not (Test-Path -LiteralPath $SkillsTarget)) {
    if (-not $DryRun) {
        New-Item -ItemType Directory -Path $SkillsTarget -Force | Out-Null
    } else {
        Write-Host "    [dry-run] would create $SkillsTarget"
    }
}

$packSkills = @()
foreach ($skillDir in Get-ChildItem -LiteralPath (Join-Path $Source "skills") -Directory) {
    $skillName = $skillDir.Name
    $packSkills += $skillName
    $dst = Join-Path $SkillsTarget $skillName
    Install-SkillDirectory -SourceDir $skillDir.FullName -TargetDir $dst -Label "skills/$skillName"
}
Write-Host "  Installed $($packSkills.Count) pack skills."

# Report preserved user skills
if (Test-Path -LiteralPath $SkillsTarget) {
    foreach ($existingDir in Get-ChildItem -LiteralPath $SkillsTarget -Directory) {
        if ($packSkills -notcontains $existingDir.Name) {
            Write-Host "  Preserved user skill: $($existingDir.Name)"
        }
    }
}

# Runtime ledger helpers are sourced once from repo-root scripts/ and installed
# beside the lead scripts so installed packs have a local helper surface too.
$RuntimeLedgerScripts = @(
    "agent-run-ledger.py",
    "agent-run-ledger.ps1",
    "agent-run-ledger.sh",
    "check-work-items-state.py",
    "check-work-items-state.ps1",
    "check-work-items-state.sh",
    "validate-work-item-state.py",
    "validate-work-item-state.ps1",
    "validate-work-item-state.sh"
)
Write-Host "  Installing work-item ledger helper scripts..."
if (-not (Test-Path -LiteralPath $LeadScriptsTarget)) {
    if (-not $DryRun) {
        New-Item -ItemType Directory -Path $LeadScriptsTarget -Force | Out-Null
    } else {
        Write-Host "    [dry-run] would create $LeadScriptsTarget"
    }
}
foreach ($scriptName in $RuntimeLedgerScripts) {
    $scriptSource = Join-Path (Join-Path $RepoDir "scripts") $scriptName
    $scriptTarget = Join-Path $LeadScriptsTarget $scriptName
    if (-not (Test-Path -LiteralPath $scriptSource)) {
        Write-Host "FAIL: Missing runtime helper source $scriptSource" -ForegroundColor Red
        exit 1
    }
    if (-not $DryRun) {
        Copy-Item -LiteralPath $scriptSource -Destination $scriptTarget -Force
    } else {
        Write-Host "    [dry-run] would copy $scriptSource -> $scriptTarget"
    }
}

Write-Host "  Installing built-in agent overrides (preserving existing custom files)..."
if (-not (Test-Path -LiteralPath $AgentOverridesTarget)) {
    if (-not $DryRun) {
        New-Item -ItemType Directory -Path $AgentOverridesTarget -Force | Out-Null
    } else {
        Write-Host "    [dry-run] would create $AgentOverridesTarget"
    }
}
foreach ($agentFile in Get-ChildItem -LiteralPath $AgentsSource -File) {
    $targetFile = Join-Path $AgentOverridesTarget $agentFile.Name
    Ensure-CodexAgentOverrideFile -SourceFile $agentFile.FullName -TargetFile $targetFile -Label ("built-in agent override {0}" -f $agentFile.Name)
}

# AGENTS.md: assemble from shared + codex-specific, then merge or create
$srcShared = Join-Path (Join-Path $RepoDir "shared") "AGENTS.shared.md"
$srcPlatform = Join-Path $Source "AGENTS.codex.md"

if (-not (Test-Path $srcShared) -or -not (Test-Path $srcPlatform)) {
    Write-Host "FAIL: Missing $srcShared or $srcPlatform" -ForegroundColor Red
    exit 1
}

# Assemble the pack AGENTS.md into a temp file, then merge or create. The temp
# file is always removed in the finally block, matching the .sh `trap rm -f EXIT`.
$srcMd = [System.IO.Path]::GetTempFileName()
$dstMd = $MdTarget
try {
    $sharedContent = Get-Content $srcShared -Raw
    $platformContent = Get-Content $srcPlatform -Raw
    $assembledContent = @(
        $script:CodexPackBeginMarker
        $sharedContent.TrimEnd()
        ""
        $platformContent.TrimEnd()
        $script:CodexPackEndMarker
    ) -join "`n"
    Set-Content -Path $srcMd -Value $assembledContent -NoNewline

    Remove-DanglingLink -Path $dstMd -Label "AGENTS.md"

    if (Test-Path $dstMd) {
        $content = Get-Content $dstMd -Raw
        if ($content -match "## Template routing") {
            $lines = Get-Content $dstMd
            $packStart = Get-CodexPackStartIndex -Lines $lines
            if ($packStart -ge 0) {
                Write-Host "  AGENTS.md: replacing Codex pack section..."
                if (-not $DryRun) {
                    $newContent = Get-MergedCodexAgentsContent -ExistingLines $lines -PackStart $packStart -SourcePath $srcMd
                    Set-Content -Path $dstMd -Value $newContent -NoNewline
                } else {
                    Write-Host "    [dry-run] would replace Codex pack section in AGENTS.md"
                }
            } else {
                Write-Host "  AGENTS.md: full replace..."
                if (-not $DryRun) {
                    Copy-Item -Force $srcMd $dstMd
                } else {
                    Write-Host "    [dry-run] would replace AGENTS.md"
                }
            }
        } else {
            Write-Host "  AGENTS.md: prepending Codex pack content..."
            $existing = Get-Content $dstMd -Raw
            $new = Get-Content $srcMd -Raw
            if (-not $DryRun) {
                Set-Content -Path $dstMd -Value ($new + "`n" + $existing) -NoNewline
            } else {
                Write-Host "    [dry-run] would prepend AGENTS.md"
            }
        }
    } else {
        Write-Host "  Creating AGENTS.md..."
        if (-not $DryRun) {
            Copy-Item -Force $srcMd $dstMd
        } else {
            Write-Host "    [dry-run] would create AGENTS.md"
        }
    }
} finally {
    Remove-Item -LiteralPath $srcMd -Force -ErrorAction SilentlyContinue
}

if ($Mode -ne "global") {
    Ensure-LocalOnlyGitignoreEntries -ProjectRoot $ProjectRoot
}

Migrate-LegacyAgentsModeFile -LegacyFile $LegacyAgentsModeTarget -TargetFile $AgentsModeTarget -Label ".agents-mode.yaml"
Sync-AgentsModeFile -TemplateFile $SharedAgentsModeSource -TargetFile $AgentsModeTarget -Label ".agents-mode.yaml" -Provider codex

# Shared cross-pack global .agents-mode.yaml lives at $HOME/.agents-mode.yaml
# (alongside ~/.claude.json). Lowest-precedence fallback layer below pack-local
# globals and project-local overlays. Sync is normalize-not-overwrite, so calling
# from both pack installers is idempotent. Only created/normalized during global installs.
if ($Mode -eq "global") {
    $SharedGlobalAgentsMode = Join-Path $HOME ".agents-mode.yaml"
    Sync-AgentsModeFile -TemplateFile $SharedAgentsModeSource -TargetFile $SharedGlobalAgentsMode -Label "shared global ~/.agents-mode.yaml" -Provider shared
}

# Install structural hooks into ~/.codex/hooks.json
# (global) or <project>/.codex/hooks.json (target). Idempotent JSON merge.
# Opt out with -NoHypothesisHook or ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1.
if (-not $NoHypothesisHook -and -not $DryRun) {
    $HookInstaller = Join-Path $RepoDir "scripts\install-hypothesis-hook.py"
    if (-not (Test-Path $HookInstaller)) {
        Write-Warning "hypothesis-hook installer not found at $HookInstaller; skipping hook install"
    } else {
        $PythonCmd = Get-PythonCommand
        if (-not $PythonCmd) {
            Write-Error "python or python3 is required to auto-install the structural hooks. Rerun with -NoHypothesisHook to skip, or install Python and re-run."
            exit 1
        }
        # PowerShell installer runs on Windows by definition. Codex hook entry
        # uses native `powershell.exe ... -File <.ps1>` invocation — explicit
        # powershell.exe avoids the Windows PATH gotcha where `bash` may
        # resolve to the WSL launcher (System32\bash.exe) instead of Git
        # Bash; WSL bash cannot resolve `C:\Users\...` paths and the entry
        # silently failed on every Bash tool call. User must run `codex`
        # interactively after install and trust the hook via TUI before it
        # fires — Codex marks newly-installed hooks as untrusted by design,
        # and the installer cannot trust them programmatically.
        $HooksTarget = Join-Path $TargetRoot "hooks.json"
        $BugfixScriptTarget = Join-Path $AgentsRoot "skills\lead\scripts\check-bugfix-discipline.ps1"
        $GitPushGateScriptTarget = Join-Path $AgentsRoot "skills\lead\scripts\check-git-push-gate.ps1"
        $StopScriptTarget = Join-Path $AgentsRoot "skills\lead\scripts\check-passive-polling-stop.ps1"
        $WiArchivalScriptTarget = Join-Path $AgentsRoot "skills\lead\scripts\check-work-items-archival-stop.ps1"
        $MachinePathScriptTarget = Join-Path $AgentsRoot "skills\lead\hooks\check-machine-local-path.ps1"
        $NoTrashScriptTarget = Join-Path $AgentsRoot "skills\lead\hooks\check-no-trash-in-repo.ps1"
        $StaleRelationScriptTarget = Join-Path $AgentsRoot "skills\lead\hooks\check-stale-relation-residue.ps1"
        $RepositoryOrientationScriptTarget = Join-Path $AgentsRoot "skills\lead\hooks\check-repository-orientation.ps1"
        $McpMomentumScriptTarget = Join-Path $AgentsRoot "skills\lead\hooks\check-mcp-momentum.ps1"
        $ReminderScriptTarget = Join-Path $AgentsRoot "skills\lead\scripts\mcp-usage-reminder.ps1"
        $AgentsModeReminderScriptTarget = Join-Path $AgentsRoot "skills\lead\scripts\agents-mode-reminder.ps1"
        $ScratchValuablesScriptTarget = Join-Path $AgentsRoot "skills\lead\scripts\check-scratch-valuables.ps1"
        $TurnAnchorReminderScriptTarget = Join-Path $AgentsRoot "skills\lead\scripts\turn-anchor-reminder.ps1"
        Write-Host "  Installing bugfix-discipline PreToolUse hook (host-os=windows; trust step manual via codex TUI)..."
        & $PythonCmd $HookInstaller --target $HooksTarget --platform codex --host-os windows --script-path $BugfixScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing git-push publication-gate PreToolUse hook (host-os=windows; trust step manual via codex TUI)..."
        & $PythonCmd $HookInstaller --target $HooksTarget --platform codex --host-os windows --script-marker check-git-push-gate --tool-matcher "Bash|PowerShell" --script-path $GitPushGateScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing passive-polling Stop hook (host-os=windows; trust step manual via codex TUI)..."
        & $PythonCmd $HookInstaller --target $HooksTarget --platform codex --host-os windows --hook-event Stop --script-marker check-passive-polling-stop --script-path $StopScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing work-items-archival Stop hook (host-os=windows; trust step manual via codex TUI)..."
        & $PythonCmd $HookInstaller --target $HooksTarget --platform codex --host-os windows --hook-event Stop --script-marker check-work-items-archival-stop --script-path $WiArchivalScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing machine-local-path PreToolUse hook [AUDIT] (host-os=windows; trust step manual via codex TUI)..."
        & $PythonCmd $HookInstaller --target $HooksTarget --platform codex --host-os windows --script-marker check-machine-local-path --script-path $MachinePathScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing no-trash-in-repo PreToolUse hook [AUDIT] (host-os=windows; trust step manual via codex TUI)..."
        & $PythonCmd $HookInstaller --target $HooksTarget --platform codex --host-os windows --script-marker check-no-trash-in-repo --tool-matcher "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell" --script-path $NoTrashScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing stale-relation-residue PreToolUse hook [AUDIT] (host-os=windows; trust step manual via codex TUI)..."
        & $PythonCmd $HookInstaller --target $HooksTarget --platform codex --host-os windows --script-marker check-stale-relation-residue --script-path $StaleRelationScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing repository-orientation PreToolUse hook [AUDIT] (host-os=windows; trust step manual via codex TUI)..."
        & $PythonCmd $HookInstaller --target $HooksTarget --platform codex --host-os windows --script-marker check-repository-orientation --tool-matcher "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell|shell_command|exec_command" --script-path $RepositoryOrientationScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing mcp-momentum PreToolUse hook [AUDIT] (host-os=windows; trust step manual via codex TUI)..."
        & $PythonCmd $HookInstaller --target $HooksTarget --platform codex --host-os windows --script-marker check-mcp-momentum --tool-matcher "Grep|Bash" --script-path $McpMomentumScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing MCP-usage-reminder SessionStart hook (host-os=windows; trust step manual via codex TUI)..."
        & $PythonCmd $HookInstaller --target $HooksTarget --platform codex --host-os windows --hook-event SessionStart --script-marker mcp-usage-reminder --script-path $ReminderScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing delegation-posture (agents-mode) SessionStart hook (host-os=windows; trust step manual via codex TUI)..."
        & $PythonCmd $HookInstaller --target $HooksTarget --platform codex --host-os windows --hook-event SessionStart --script-marker agents-mode-reminder --script-path $AgentsModeReminderScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing scratch-valuables watchdog SessionStart hook (host-os=windows; trust step manual via codex TUI)..."
        & $PythonCmd $HookInstaller --target $HooksTarget --platform codex --host-os windows --hook-event SessionStart --script-marker check-scratch-valuables --script-path $ScratchValuablesScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing turn-anchor-reminder UserPromptSubmit hook (host-os=windows; trust step manual via codex TUI)..."
        & $PythonCmd $HookInstaller --target $HooksTarget --platform codex --host-os windows --hook-event UserPromptSubmit --script-marker turn-anchor-reminder --script-path $TurnAnchorReminderScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
    }
}

if ($DryRun) {
    Write-Host ""
    Write-Host "RESULT: DRY-RUN complete (no files modified)."
    exit 0
}

# Verification -- explicit required-file manifest check
Write-Host ""
Write-Host "=== Verification ===" -ForegroundColor Cyan
$errors = 0

function Test-InstalledFile($path, $label) {
    if (Test-Path $path) {
        Write-Host "  OK  $label" -ForegroundColor Green
    } else {
        Write-Host "  FAIL  $label" -ForegroundColor Red
        $script:errors++
    }
}

function Get-SourceFiles($DirRoot) {
    $sourceDir = Join-Path $Source $DirRoot
    $items = @()
    foreach ($item in Get-ChildItem -LiteralPath $sourceDir -Recurse -File) {
        $relative = $item.FullName.Substring($sourceDir.Length)
        $relative = $relative.TrimStart("\\")
        $items += (Join-Path $DirRoot $relative)
    }
    return $items
}

# Verify all files in skills/
Write-Host "Verifying skills/ files..."
foreach ($relative in Get-SourceFiles "skills") {
    $relFile = $relative.Substring("skills\".Length)
    Test-InstalledFile (Join-Path $SkillsTarget $relFile) $relative
}

Write-Host "Verifying agents/ files..."
foreach ($relative in Get-SourceFiles "agents") {
    $relFile = $relative.Substring("agents\".Length)
    Test-InstalledFile (Join-Path $AgentOverridesTarget $relFile) $relative
}

# Explicit contract requirements
Test-InstalledFile (Join-Path $SkillsTarget "lead/operating-model.md") "skills/lead/operating-model.md"
Test-InstalledFile (Join-Path $SkillsTarget "lead/subagent-contracts.md") "skills/lead/subagent-contracts.md"
Test-InstalledFile (Join-Path $LeadScriptsTarget "check-publication-safety.sh") "skills/lead/scripts/check-publication-safety.sh"
Test-InstalledFile (Join-Path $LeadScriptsTarget "check-publication-safety.ps1") "skills/lead/scripts/check-publication-safety.ps1"
Test-InstalledFile (Join-Path $LeadScriptsTarget "validate-skill-pack.sh") "skills/lead/scripts/validate-skill-pack.sh"
foreach ($scriptName in $RuntimeLedgerScripts) {
    Test-InstalledFile (Join-Path $LeadScriptsTarget $scriptName) "skills/lead/scripts/$scriptName"
}
Test-InstalledFile $AgentsModeTarget ".agents-mode.yaml"
Test-InstalledFile (Join-Path $AgentOverridesTarget "default.toml") "agents/default.toml"
Test-InstalledFile (Join-Path $AgentOverridesTarget "worker.toml") "agents/worker.toml"
Test-InstalledFile (Join-Path $AgentOverridesTarget "explorer.toml") "agents/explorer.toml"

if (Test-Path $dstMd) {
    $mdContent = Get-Content $dstMd -Raw
    $lineCount = (Get-Content $dstMd).Count
    Write-Host "  OK  AGENTS.md ($lineCount lines)" -ForegroundColor Green
    foreach ($section in @("## Template routing", "## Role index", "## Engineering hygiene", "## Publication safety")) {
        if ($mdContent -match [regex]::Escape($section)) {
            Write-Host "  OK  AGENTS.md has '$section'" -ForegroundColor Green
        } else {
            Write-Host "  FAIL  AGENTS.md missing '$section'" -ForegroundColor Red
            $errors++
        }
    }
} else {
    Write-Host "  FAIL  AGENTS.md missing" -ForegroundColor Red
    $errors++
}

Write-Host ""
if ($errors -gt 0) {
    Write-Host "RESULT: FAIL ($errors errors)" -ForegroundColor Red
    exit 1
} else {
    Write-Host "RESULT: OK - Codex pack installed" -ForegroundColor Green
    Write-Host "  Skills: $SkillsTarget"
    Write-Host "  Built-in agent overrides: $AgentOverridesTarget"
    Write-Host "  AGENTS.md: $MdTarget"
    Write-Host "  agents-mode: $AgentsModeTarget"
    Write-Host ""
    Write-Host "Next: open Codex in the target project and run '`$init-project' to review/update project policies and the installed default .agents/.agents-mode.yaml."
    Write-Host "Then run 'bash $LeadScriptsTarget/validate-skill-pack.sh' if you are validating the installation from a maintainer shell."
}

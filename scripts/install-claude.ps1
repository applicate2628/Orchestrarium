<#
.SYNOPSIS
    Install Claude Code pack.
.DESCRIPTION
    Copies agents (with contracts, templates, scripts), commands, and CLAUDE.md to the target location.
    Re-running = reinstall. Memory is preserved across reinstalls.
.EXAMPLE
    .\scripts\install-claude.ps1                          # Install into current repo's .claude/
    .\scripts\install-claude.ps1 -Global                  # Install into ~/.claude/
    .\scripts\install-claude.ps1 -Target "D:\my-repo"     # Install into D:\my-repo\.claude/
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
$Source = Join-Path $RepoDir "src.claude"
$DefaultAgentsModeSource = Join-Path $RepoDir "shared\agents-mode.defaults.yaml"

# `commands/` is the SINGLE monorepo flow surface: each agents-* flow ships as
# commands/agents-*.md only; generated skills/agents-*/SKILL.md are a standalone-
# BRANCH artifact, reclaimed here if left stale by a prior install.
$Dirs = @("agents", "commands", "skills")
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
    if ((Split-Path -Leaf $resolved).ToLowerInvariant() -eq ".claude") {
        return $resolved
    }
    return (Join-Path $resolved ".claude")
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
        $list += Resolve-InstallTarget -InputPath (Join-Path $repoRoot ".claude")
    }

    if ($Mode -eq "global") {
        if (-not $env:USERPROFILE) {
            throw "USERPROFILE is not set."
        }
        $list += Resolve-InstallTarget -InputPath (Join-Path $env:USERPROFILE ".claude")
    }

    if ($Mode -eq "target") {
        $repoRoot = Get-GitRepoRoot
        $list += Resolve-InstallTarget -InputPath (Join-Path $repoRoot ".claude")
        if ($env:USERPROFILE) {
            $list += Resolve-InstallTarget -InputPath (Join-Path $env:USERPROFILE ".claude")
        }
    }

    if ($env:CLAUDE_INSTALL_ALLOWLIST) {
        $envPaths = $env:CLAUDE_INSTALL_ALLOWLIST -split ","
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

    if ((Split-Path -Leaf $target).ToLowerInvariant() -ne ".claude") {
        throw "Target must resolve to a .claude directory."
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
    Write-Host "  1) Local repo (.claude/)"
    Write-Host "  2) Global (~/.claude/)"
    Write-Host "  3) Custom target directory"
    Write-Host "  4) Abort"

    while ($true) {
        $choice = Read-Host "Choose [1-4, default: 1]"
        if ([string]::IsNullOrWhiteSpace($choice)) {
            $choice = "1"
        }
        switch ($choice.Trim()) {
            "1" {
                $script:PromptMode = "repo"
                return (Join-Path (Get-GitRepoRoot) ".claude")
            }
            "2" {
                $script:PromptMode = "global"
                if ($env:USERPROFILE) {
                    return (Join-Path $env:USERPROFILE ".claude")
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

# Per-item install preserves user-added files — no destructive directory wipe needed.

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

function Install-PackDirectoryItem {
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

function Install-PackFileItem {
    param(
        [string]$SourceFile,
        [string]$TargetFile,
        [string]$Label
    )

    if (Test-Path -LiteralPath $TargetFile) {
        if (Test-FileContentEqual -SourceFile $SourceFile -TargetFile $TargetFile) {
            Write-Host "    OK  $Label unchanged"
            return
        }

        if (-not $DryRun) {
            Copy-Item -Force $SourceFile $TargetFile
        } else {
            Write-Host "    [dry-run] would replace $Label"
        }
    } else {
        if (-not $DryRun) {
            Copy-Item -Force $SourceFile $TargetFile
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

function Ensure-CredentialGitignoreEntry {
    # The pack's own credential file (.claude/SECRET.md -- the invoke-claude-api
    # wrapper's repo-local lookup candidate) must never be trackable in a project
    # install. Kept separate from the local-only tier array above: that array is
    # the cross-installer tier set owned by shared/local-only-tiers.txt, while
    # this is a Claude-pack-specific credential path.
    param([string]$ProjectRoot)

    $gitignore = Join-Path $ProjectRoot ".gitignore"
    $secretEntry = "/.claude/SECRET.md"
    $alternate = $secretEntry.TrimStart("/")
    $existingLines = @()
    if (Test-Path -LiteralPath $gitignore) {
        $existingLines = Get-Content -LiteralPath $gitignore -ErrorAction SilentlyContinue
    }

    if ($existingLines -contains $secretEntry -or $existingLines -contains $alternate) {
        Write-Host "  .gitignore: credential entry already present"
        return
    }

    Write-Host "  Ensuring .gitignore ignores the pack credential file $secretEntry..."
    if ($DryRun) {
        if (Test-Path -LiteralPath $gitignore) {
            Write-Host "    [dry-run] would append '$secretEntry' to $gitignore"
        } else {
            Write-Host "    [dry-run] would create $gitignore with '$secretEntry'"
        }
        return
    }

    if (-not (Test-Path -LiteralPath $gitignore)) {
        Set-Content -LiteralPath $gitignore -Value $secretEntry
        return
    }

    Add-Content -LiteralPath $gitignore -Value "`r`n$secretEntry"
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

function Sync-AgentsModeFile {
    param(
        [string]$TemplateFile,
        [string]$TargetFile,
        [string]$Label
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

function Get-PreservedClaudeImports {
    param(
        [string[]]$Lines,
        [int]$PackStart
    )

    $imports = @()
    if ($PackStart -lt 0 -or $PackStart -ge $Lines.Count) {
        return $imports
    }

    $collectImports = $false
    for ($i = $PackStart; $i -lt $Lines.Count; $i++) {
        $line = $Lines[$i]

        if (-not $collectImports) {
            if ($line -match "^@" -or [string]::IsNullOrWhiteSpace($line)) {
                $collectImports = $true
            } else {
                break
            }
        }

        if ($line -match "^@") {
            if ($line -ne "@AGENTS.md" -and $imports -notcontains $line) {
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

function Get-MergedClaudePackContent {
    param(
        [string[]]$ExistingLines,
        [int]$PackStart,
        [string]$SourcePath
    )

    $preservedPrefix = @()
    if ($PackStart -gt 0) {
        $preservedPrefix = $ExistingLines[0..($PackStart - 1)]
    }

    $preservedImports = Get-PreservedClaudeImports -Lines $ExistingLines -PackStart $PackStart
    $sourceLines = Get-Content $SourcePath
    $mergedPackLines = $sourceLines

    if ($sourceLines.Count -gt 0 -and $sourceLines[0] -eq "@AGENTS.md") {
        $tailStart = 1
        while ($tailStart -lt $sourceLines.Count -and [string]::IsNullOrWhiteSpace($sourceLines[$tailStart])) {
            $tailStart++
        }

        $tailLines = @()
        if ($tailStart -lt $sourceLines.Count) {
            $tailLines = $sourceLines[$tailStart..($sourceLines.Count - 1)]
        }

        $mergedPackLines = @($sourceLines[0])
        if ($preservedImports.Count -gt 0) {
            $mergedPackLines += $preservedImports
        }
        if ($tailLines.Count -gt 0) {
            $mergedPackLines += ""
            $mergedPackLines += $tailLines
        }
    }

    $finalLines = @()
    if ($preservedPrefix.Count -gt 0) {
        $finalLines += $preservedPrefix
    }
    $finalLines += $mergedPackLines

    return ($finalLines -join "`n")
}

# Determine target
if ($Global) {
    $repoRoot = Get-GitRepoRoot
    try {
        $TargetRoot = Assert-SafeInstallRoot -Path (Join-Path $env:USERPROFILE ".claude") -Mode "global"
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
        Write-Host "Use: .\scripts\install-claude.ps1 -Global  or  .\scripts\install-claude.ps1 -Target <path>" -ForegroundColor Yellow
        exit 1
    }
}

if ($Mode -eq "global") {
    $ProjectRoot = $null
} else {
    $ProjectRoot = Split-Path $TargetRoot -Parent
}
$AgentsModeTarget = Join-Path $TargetRoot ".agents-mode.yaml"
$LegacyAgentsModeTarget = Join-Path $TargetRoot ".agents-mode"

Write-Host "=== Claude Code Installer ===" -ForegroundColor Cyan
Write-Host "Source: $Source"
Write-Host "Target: $TargetRoot"
Write-Host "agents-mode: $AgentsModeTarget"
Write-Host "Mode:   $Mode"
if ($DryRun) {
    Write-Host "Mode:   dry-run" -ForegroundColor Yellow
}
Write-Host ""

# Verify source
if (-not (Test-Path (Join-Path $Source "agents"))) {
    Write-Host "FAIL: Source directory $Source\agents not found." -ForegroundColor Red
    Write-Host "Run this script from the Orchestrarium repo root."
    exit 1
}
if (-not (Test-Path -LiteralPath $DefaultAgentsModeSource)) {
    Write-Host "FAIL: Missing default agents-mode template at $DefaultAgentsModeSource." -ForegroundColor Red
    exit 1
}

if (-not $DryRun -and -not (Test-Path -LiteralPath $TargetRoot)) {
    New-Item -ItemType Directory -Path $TargetRoot -Force | Out-Null
}
if ($DryRun -and -not (Test-Path -LiteralPath $TargetRoot)) {
    Write-Host "[dry-run] would create target root: $TargetRoot"
}

# Count and confirm reinstall
if (-not $Force -and -not $DryRun -and (Test-Interactive)) {
    $existingTotal = 0
    $packTotal = 0
    foreach ($dir in $Dirs) {
        $dst = Join-Path $TargetRoot $dir
        $src = Join-Path $Source $dir
        # Count top-level entries (files AND subdirectories) — these are exactly the
        # "pack items" the install loop below replaces. Matches install-claude.sh's
        # `-e` count over `"$dst"/*` so .sh and .ps1 report the same totals for
        # identical trees. No -Force: the bash `*` glob skips dotfiles, so we skip
        # hidden entries too rather than diverge in the other direction.
        if (Test-Path -LiteralPath $dst) {
            $existingTotal += @(Get-ChildItem -LiteralPath $dst -ErrorAction SilentlyContinue).Count
        }
        $packTotal += @(Get-ChildItem -LiteralPath $src -ErrorAction SilentlyContinue).Count
    }
    if ($existingTotal -gt 0) {
        $userCount = $existingTotal - $packTotal
        if ($userCount -lt 0) { $userCount = 0 }
        Write-Host ""
        Write-Host "  Reinstall will replace $packTotal pack items. $userCount user item(s) will be preserved."
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
}

# Per-item install: replace pack items, preserve user-added files
foreach ($dir in $Dirs) {
    $src = Join-Path $Source $dir
    $dst = Join-Path $TargetRoot $dir

    Write-Host "  Installing $dir\ (per-item, preserving user-added files)..."
    if (-not (Test-Path -LiteralPath $dst)) {
        if (-not $DryRun) {
            New-Item -ItemType Directory -Path $dst -Force | Out-Null
        } else {
            Write-Host "    [dry-run] would create $dst"
        }
    }

    # Copy subdirectories (contracts/, team-templates/, scripts/) — full replace
    foreach ($sub in Get-ChildItem -LiteralPath $src -Directory -ErrorAction SilentlyContinue) {
        $subDst = Join-Path $dst $sub.Name
        Install-PackDirectoryItem -SourceDir $sub.FullName -TargetDir $subDst -Label "$dir/$($sub.Name)/"
    }

    # Copy individual files — per-file, preserve user files
    $packItems = @()
    foreach ($item in Get-ChildItem -LiteralPath $src -File -ErrorAction SilentlyContinue) {
        $packItems += $item.Name
        $itemDst = Join-Path $dst $item.Name
        Install-PackFileItem -SourceFile $item.FullName -TargetFile $itemDst -Label "$dir/$($item.Name)"
    }

    # Report preserved user files
    foreach ($existing in Get-ChildItem -LiteralPath $dst -File -ErrorAction SilentlyContinue) {
        if ($packItems -notcontains $existing.Name) {
            Write-Host "  Preserved user file: $dir/$($existing.Name)"
        }
    }

    # Reclaim the reserved `agents-` pack namespace (parity with install-claude.sh):
    # a target commands/agents-*.md file or a skills/agents-*/ dir not in the
    # current pack is a stale pack-owned artifact (renamed/removed flow, or a
    # generated agents-* skill from an old standalone-branch install — the
    # monorepo path ships flows only as commands/). Remove it. Non-namespaced
    # user files are preserved; the prefix is the ownership marker.
    if ($dir -eq "commands" -or $dir -eq "skills") {
        foreach ($existing in Get-ChildItem -LiteralPath $dst -Filter "agents-*" -ErrorAction SilentlyContinue) {
            $srcCounterpart = Join-Path $src $existing.Name
            if (Test-Path -LiteralPath $srcCounterpart) { continue }
            if ($DryRun) {
                Write-Host "    [dry-run] would reclaim stale pack namespace: $dir/$($existing.Name)"
            } else {
                Remove-Item -LiteralPath $existing.FullName -Recurse -Force
                Write-Host "  Reclaimed stale pack item: $dir/$($existing.Name)"
            }
        }
    }
}

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
$ClaudeScriptsTarget = Join-Path $TargetRoot "agents\scripts"
Write-Host "  Installing work-item ledger helper scripts..."
if (-not (Test-Path -LiteralPath $ClaudeScriptsTarget)) {
    if (-not $DryRun) {
        New-Item -ItemType Directory -Path $ClaudeScriptsTarget -Force | Out-Null
    } else {
        Write-Host "    [dry-run] would create $ClaudeScriptsTarget"
    }
}
foreach ($scriptName in $RuntimeLedgerScripts) {
    $scriptSource = Join-Path (Join-Path $RepoDir "scripts") $scriptName
    $scriptTarget = Join-Path $ClaudeScriptsTarget $scriptName
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

# CLAUDE.md merge
$srcMd = Join-Path $Source "CLAUDE.md"
$dstMd = Join-Path $TargetRoot "CLAUDE.md"

Remove-DanglingLink -Path $dstMd -Label "CLAUDE.md"

if (Test-Path $dstMd) {
    $content = Get-Content $dstMd -Raw
    $lines = Get-Content $dstMd
    # Find pack section start: @AGENTS.md, # Claude Code Pack, or legacy # Claudestrator
    $packStart = -1
    for ($i = 0; $i -lt $lines.Count; $i++) {
        if ($lines[$i] -match "^@AGENTS\.md" -or $lines[$i] -match "^# Claude Code Pack" -or $lines[$i] -match "^# Claudestrator") {
            $packStart = $i
            break
        }
    }
    if ($packStart -ge 0) {
        Write-Host "  CLAUDE.md: replacing Claude Code pack section..."
        if ($packStart -gt 0) {
            # Preserve user content before pack section and merge user-side imports from the pack header block.
            $newContent = Get-MergedClaudePackContent -ExistingLines $lines -PackStart $packStart -SourcePath $srcMd
            if (-not $DryRun) {
                Set-Content -Path $dstMd -Value $newContent -NoNewline
            } else {
                Write-Host "    [dry-run] would replace Claude Code pack section in CLAUDE.md"
            }
        } else {
            if (-not $DryRun) {
                $newContent = Get-MergedClaudePackContent -ExistingLines $lines -PackStart $packStart -SourcePath $srcMd
                Set-Content -Path $dstMd -Value $newContent -NoNewline
            } else {
                Write-Host "    [dry-run] would replace CLAUDE.md"
            }
        }
    } elseif ($content -match "## Delegation rule") {
        Write-Host "  CLAUDE.md: full replace (has delegation rule but no recognized pack header)..."
        if (-not $DryRun) {
            Copy-Item -Force $srcMd $dstMd
        } else {
            Write-Host "    [dry-run] would replace CLAUDE.md"
        }
    } else {
        Write-Host "  CLAUDE.md: prepending Claude Code pack content..."
        $existing = Get-Content $dstMd -Raw
        $new = Get-Content $srcMd -Raw
        if (-not $DryRun) {
            Set-Content -Path $dstMd -Value ($new + "`n" + $existing) -NoNewline
        } else {
            Write-Host "    [dry-run] would prepend CLAUDE.md"
        }
    }
} else {
    Write-Host "  Creating CLAUDE.md..."
    if (-not $DryRun) {
        Copy-Item -Force $srcMd $dstMd
    } else {
        Write-Host "    [dry-run] would create CLAUDE.md"
    }
}

# AGENTS.md: copy or replace shared governance
$srcAgents = Join-Path (Join-Path $RepoDir "shared") "AGENTS.shared.md"
$dstAgents = Join-Path $TargetRoot "AGENTS.md"

Remove-DanglingLink -Path $dstAgents -Label "AGENTS.md"

if (Test-Path $srcAgents) {
    if (Test-Path $dstAgents) {
        $agentsContent = Get-Content $dstAgents -Raw
        if ($agentsContent -match "# Shared Governance") {
            Write-Host "  AGENTS.md: replacing shared governance..."
            if (-not $DryRun) {
                Copy-Item -Force $srcAgents $dstAgents
            } else {
                Write-Host "    [dry-run] would replace AGENTS.md"
            }
        } else {
            Write-Host "  AGENTS.md: prepending shared governance..."
            if (-not $DryRun) {
                $existing = Get-Content $dstAgents -Raw
                $new = Get-Content $srcAgents -Raw
                Set-Content -Path $dstAgents -Value ($new + "`n" + $existing) -NoNewline
            } else {
                Write-Host "    [dry-run] would prepend AGENTS.md"
            }
        }
    } else {
        Write-Host "  Creating AGENTS.md..."
        if (-not $DryRun) {
            Copy-Item -Force $srcAgents $dstAgents
        } else {
            Write-Host "    [dry-run] would create AGENTS.md"
        }
    }
}

if ($Mode -ne "global") {
    Ensure-LocalOnlyGitignoreEntries -ProjectRoot $ProjectRoot
    Ensure-CredentialGitignoreEntry -ProjectRoot $ProjectRoot
}

Migrate-LegacyAgentsModeFile -LegacyFile $LegacyAgentsModeTarget -TargetFile $AgentsModeTarget -Label ".agents-mode.yaml"
Sync-AgentsModeFile -TemplateFile $DefaultAgentsModeSource -TargetFile $AgentsModeTarget -Label ".agents-mode.yaml"

# Shared cross-pack global .agents-mode.yaml lives at $HOME/.agents-mode.yaml
# (alongside ~/.claude.json). Lowest-precedence fallback layer below pack-local
# globals and project-local overlays. Sync is normalize-not-overwrite, so calling
# from both pack installers is idempotent. Only created/normalized during global installs.
if ($Mode -eq "global") {
    $SharedGlobalAgentsMode = Join-Path $HOME ".agents-mode.yaml"
    Sync-AgentsModeFile -TemplateFile $DefaultAgentsModeSource -TargetFile $SharedGlobalAgentsMode -Label "shared global ~/.agents-mode.yaml"
}

# Install structural hooks by merging them into the
# user's settings.json idempotently. Preserves all other user keys and other
# hooks. Opt out with -NoHypothesisHook or ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1.
# Fails closed (non-zero exit) if Python is required but unavailable.
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
        $SettingsTarget = Join-Path $TargetRoot "settings.json"
        # PowerShell installer always emits Windows-native exec form referencing
        # the .ps1 hook script. Bash form is reserved for the .sh installer.
        $BugfixScriptTarget = Join-Path $TargetRoot "agents\scripts\check-bugfix-discipline.ps1"
        $GitPushGateScriptTarget = Join-Path $TargetRoot "agents\scripts\check-git-push-gate.ps1"
        $StopScriptTarget = Join-Path $TargetRoot "agents\scripts\check-passive-polling-stop.ps1"
        $WiArchivalScriptTarget = Join-Path $TargetRoot "agents\scripts\check-work-items-archival-stop.ps1"
        $MachinePathScriptTarget = Join-Path $TargetRoot "agents\hooks\check-machine-local-path.ps1"
        $NoTrashScriptTarget = Join-Path $TargetRoot "agents\hooks\check-no-trash-in-repo.ps1"
        $StaleRelationScriptTarget = Join-Path $TargetRoot "agents\hooks\check-stale-relation-residue.ps1"
        $RepositoryOrientationScriptTarget = Join-Path $TargetRoot "agents\hooks\check-repository-orientation.ps1"
        $McpMomentumScriptTarget = Join-Path $TargetRoot "agents\hooks\check-mcp-momentum.ps1"
        $TypedRoutingScriptTarget = Join-Path $TargetRoot "agents\hooks\check-typed-routing.ps1"
        $ReminderScriptTarget = Join-Path $TargetRoot "agents\scripts\mcp-usage-reminder.ps1"
        $AgentsModeReminderScriptTarget = Join-Path $TargetRoot "agents\scripts\agents-mode-reminder.ps1"
        $ScratchValuablesScriptTarget = Join-Path $TargetRoot "agents\scripts\check-scratch-valuables.ps1"
        $TurnAnchorReminderScriptTarget = Join-Path $TargetRoot "agents\scripts\turn-anchor-reminder.ps1"
        Write-Host "  Installing bugfix-discipline PreToolUse hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --script-path $BugfixScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing git-push publication-gate PreToolUse hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --script-marker check-git-push-gate --tool-matcher "Bash|PowerShell" --script-path $GitPushGateScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing passive-polling Stop hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --hook-event Stop --script-marker check-passive-polling-stop --script-path $StopScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing work-items-archival Stop hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --hook-event Stop --script-marker check-work-items-archival-stop --script-path $WiArchivalScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing machine-local-path PreToolUse hook [AUDIT] (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --script-marker check-machine-local-path --script-path $MachinePathScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing no-trash-in-repo PreToolUse hook [AUDIT] (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --script-marker check-no-trash-in-repo --tool-matcher "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell" --script-path $NoTrashScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing stale-relation-residue PreToolUse hook [AUDIT] (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --script-marker check-stale-relation-residue --script-path $StaleRelationScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing repository-orientation PreToolUse hook [AUDIT] (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --script-marker check-repository-orientation --tool-matcher "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell|shell_command|exec_command" --script-path $RepositoryOrientationScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing mcp-momentum PreToolUse hook [AUDIT] (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --script-marker check-mcp-momentum --tool-matcher "Grep|Bash" --script-path $McpMomentumScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing typed-routing PreToolUse hook [AUDIT] (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --script-marker check-typed-routing --tool-matcher "Agent" --script-path $TypedRoutingScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing MCP-usage-reminder SessionStart hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --hook-event SessionStart --script-marker mcp-usage-reminder --script-path $ReminderScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing delegation-posture (agents-mode) SessionStart hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --hook-event SessionStart --script-marker agents-mode-reminder --script-path $AgentsModeReminderScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing scratch-valuables watchdog SessionStart hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --hook-event SessionStart --script-marker check-scratch-valuables --script-path $ScratchValuablesScriptTarget
        if ($LASTEXITCODE -ne 0) {
            Write-Error "hypothesis-hook installer exited with code $LASTEXITCODE"
            exit $LASTEXITCODE
        }
        Write-Host "  Installing turn-anchor-reminder UserPromptSubmit hook (host-os=windows)..."
        & $PythonCmd $HookInstaller --target $SettingsTarget --platform claude --host-os windows --hook-event UserPromptSubmit --script-marker turn-anchor-reminder --script-path $TurnAnchorReminderScriptTarget
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

# Verification — explicit required-file manifest check
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

foreach ($dir in $Dirs) {
    Write-Host "Verifying $dir/ files..."
    foreach ($relative in Get-SourceFiles $dir) {
        Test-InstalledFile (Join-Path $TargetRoot $relative) $relative
    }
}

# Explicit contract/script requirements
Test-InstalledFile (Join-Path $TargetRoot "agents/contracts/operating-model.md") "agents/contracts/operating-model.md"
Test-InstalledFile (Join-Path $TargetRoot "agents/contracts/subagent-contracts.md") "agents/contracts/subagent-contracts.md"
Test-InstalledFile (Join-Path $TargetRoot "agents/contracts/policies-catalog.md") "agents/contracts/policies-catalog.md"
foreach ($scriptName in $RuntimeLedgerScripts) {
    Test-InstalledFile (Join-Path $TargetRoot "agents/scripts/$scriptName") "agents/scripts/$scriptName"
}
Test-InstalledFile $AgentsModeTarget ".agents-mode.yaml"

# Check CLAUDE.md (Claude-specific sections)
if (Test-Path $dstMd) {
    $mdContent = Get-Content $dstMd -Raw
    $lineCount = (Get-Content $dstMd).Count
    Write-Host "  OK  CLAUDE.md ($lineCount lines)" -ForegroundColor Green
    foreach ($section in @("## Delegation rule", "## Publication safety")) {
        if ($mdContent -match [regex]::Escape($section)) {
            Write-Host "  OK  CLAUDE.md has '$section'" -ForegroundColor Green
        } else {
            Write-Host "  FAIL  CLAUDE.md missing '$section'" -ForegroundColor Red
            $errors++
        }
    }
    if ($mdContent -match "@AGENTS\.md") {
        Write-Host "  OK  CLAUDE.md imports @AGENTS.md" -ForegroundColor Green
    } else {
        Write-Host "  FAIL  CLAUDE.md missing @AGENTS.md import" -ForegroundColor Red
        $errors++
    }
} else {
    Write-Host "  FAIL  CLAUDE.md missing" -ForegroundColor Red
    $errors++
}

# Check AGENTS.md (shared governance sections)
if (Test-Path $dstAgents) {
    $agentsContent = Get-Content $dstAgents -Raw
    $agentsLineCount = (Get-Content $dstAgents).Count
    Write-Host "  OK  AGENTS.md ($agentsLineCount lines)" -ForegroundColor Green
    foreach ($section in @("## Role index", "## Engineering hygiene", "## Core delegation principles", "## Publication safety")) {
        if ($agentsContent -match [regex]::Escape($section)) {
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
    Write-Host "RESULT: OK - Claude Code pack installed to $TargetRoot" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next: restart Claude, then run /agents-init-project to review/update project policies and the installed default .claude/.agents-mode.yaml."
}

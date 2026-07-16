# SessionStart hook -- re-injects the ACTIVE delegation posture from the effective
# .agents-mode.yaml into the model's context at every session start AND after every
# compaction. delegationMode is NOT a runtime built-in; without this hook the main
# conversation never sees "delegationMode: force" and never applies it.
#
# CONDITIONAL BY DESIGN: emits an IMPERATIVE directive ONLY when the effective
# delegationMode is force or auto; SILENT on manual and on the no-file/unresolved
# state (fail-safe). The silence is load-bearing -- the block appears only when
# delegation is operative.
#
# SELF-CONTAINED first-match read of the documented read-order (the full resolver is
# not shipped to targets; force/auto are always file-explicit, and no file anywhere
# means the pack is not installed here / the config was removed, so we do NOT inject
# a standing directive into an arbitrary directory -- the defaults/normalizer layers
# stay out of scope on purpose):
#   .\.agents\.agents-mode.yaml -> .\.agents\.agents-mode ->
#   ~\.codex\.agents-mode.yaml -> ~\.codex\.agents-mode -> ~\.agents-mode.yaml
#   First file DEFINING delegationMode wins; none -> unresolved -> silent (fail-safe).
#
# Fail-open: any error emits nothing and exits 0.
$ErrorActionPreference = "SilentlyContinue"
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

function Write-SessionStartContext {
    param([string]$AdditionalContext)
    try {
        $payload = [ordered]@{
            hookSpecificOutput = [ordered]@{
                hookEventName = "SessionStart"
                additionalContext = $AdditionalContext
            }
        }
        $json = $payload | ConvertTo-Json -Compress -Depth 4 -ErrorAction Stop
        if ($json) { [Console]::Out.WriteLine($json) }
    } catch {}
}

function Get-DelegationMode {
    # $homeDir, NOT $home: $home is a read-only PowerShell automatic variable
    # (names are case-insensitive), so assigning $home is silently suppressed
    # under SilentlyContinue and would not honor $env:USERPROFILE as designed.
    $homeDir = if ($env:USERPROFILE) { $env:USERPROFILE } elseif ($HOME) { $HOME } else { "" }
    $candidates = @(
        (Join-Path (Get-Location) ".agents\.agents-mode.yaml"),
        (Join-Path (Get-Location) ".agents\.agents-mode")
    )
    # Home/global layers only when a home dir is known, so an empty home never
    # probes root paths.
    if ($homeDir) {
        $candidates += (Join-Path $homeDir ".codex\.agents-mode.yaml")
        $candidates += (Join-Path $homeDir ".codex\.agents-mode")
        $candidates += (Join-Path $homeDir ".agents-mode.yaml")
    }
    foreach ($f in $candidates) {
        if (-not (Test-Path -LiteralPath $f)) { continue }
        try {
            # -cmatch is case-SENSITIVE: YAML keys are case-sensitive, so
            # 'DelegationMode:' must NOT match (parity with the ^-anchored grep).
            $line = Get-Content -LiteralPath $f -ErrorAction Stop |
                Where-Object { $_ -cmatch '^delegationMode:' } | Select-Object -First 1
        } catch { continue }
        # First file whose top-level key LINE is present owns the decision, even
        # if the value is empty/unrecognized (-> silence), never a lower layer's
        # force. An absent key falls through to the next layer.
        if ($null -ne $line) {
            # Strip the key (case-sensitively), then a WHITESPACE-preceded ' #...'
            # comment only (so 'force#x' stays literal -> silent), then trim the
            # ends only, then lowercase. Mirrors the Bash path.
            $v = $line -creplace '^delegationMode:\s*', '' -creplace '\s+#.*$', ''
            $v = $v.Trim().ToLowerInvariant()
            return $v
        }
    }
    return "unresolved"
}

$mode = Get-DelegationMode
if ($mode -eq "force") {
    $context = "[Delegation posture - re-shown at session start and after every compaction]`n" +
        "Effective delegationMode: FORCE. STANDING INSTRUCTION, not advisory: at the FIRST decision point of any non-trivial task (multi-step implementation, design, research, review, bug-fix), STOP - hold the `$lead orchestration role in THIS session, classify the task, pick the team template, and activate the matching specialist role/skill per stage (`$lead is the role you hold, not a subagent you spawn). Doing substantial work inline when a matching specialist and a viable tool path exist violates the active posture. When you launch any external provider (consultant / Codex / Claude) as `$lead, take the launch flags from skills/lead/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION."
    Write-SessionStartContext -AdditionalContext $context
}
elseif ($mode -eq "auto") {
    $context = "[Delegation posture - re-shown at session start and after every compaction]`n" +
        "Effective delegationMode: AUTO. Holding the `$lead orchestration role in THIS session and activating the matching specialist role/skill per stage is the DEFAULT for any non-trivial task (multi-step implementation, design, research, review, bug-fix) - do it unless the task is trivial or you record why inline is better. `$lead is the role you hold, not a subagent you spawn. When you launch any external provider (consultant / Codex / Claude) as `$lead, take the launch flags from skills/lead/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION."
    Write-SessionStartContext -AdditionalContext $context
}
# manual value, unresolved, or empty -> silent
exit 0

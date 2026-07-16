#!/usr/bin/env bash
# SessionStart hook -- re-injects the ACTIVE delegation posture from the effective
# .agents-mode.yaml into the model's context at every session start AND after every
# compaction (registered with NO matcher, like mcp-usage-reminder). delegationMode
# is NOT a Claude Code built-in feature -- it is an Orchestrator-pack governance
# value that Claude Code never parses on its own, so without this hook the main
# conversation never sees "delegationMode: force" and never applies it. This hook
# is what makes the operative delegation posture visible every session/compaction.
#
# CONDITIONAL BY DESIGN: emits an IMPERATIVE directive ONLY when the effective
# delegationMode is `force` or `auto`; it is SILENT on `manual` and on the
# no-file/unresolved state (fail-safe). The silence is load-bearing -- because the
# block only appears when delegation is actually operative, its presence is itself
# the signal, and it does not become skimmed-over wallpaper in the always-on
# governance surface.
#
# SELF-CONTAINED read of the documented read-order (the full resolve-agents-mode.py
# is NOT shipped to install targets, so this does a minimal first-match read; the
# only actionable values -- force/auto -- are always file-explicit, and no file
# anywhere means the pack is not installed here / the config was removed, so we do
# NOT inject a standing directive into an arbitrary directory -- the defaults/
# normalizer layers stay out of scope on purpose (do not "fix" this by dragging in
# the defaults chain):
#   ./.claude/.agents-mode.yaml -> ./.claude/.agents-mode (legacy)
#   -> ~/.claude/.agents-mode.yaml -> ~/.claude/.agents-mode (legacy)
#   -> ~/.agents-mode.yaml (shared cross-pack). First file DEFINING delegationMode
#   wins; none -> unresolved -> silent (fail-safe).
#
# Fail-open: any error emits nothing and exits 0; never blocks a session.
set +e

_read_delegation_mode() {
  local f line v
  local files=(
    "./.claude/.agents-mode.yaml"
    "./.claude/.agents-mode"
  )
  # Home/global layers only when HOME is set, so an empty HOME never probes
  # root paths like /.claude/.agents-mode.yaml.
  if [ -n "${HOME:-}" ]; then
    files+=(
      "$HOME/.claude/.agents-mode.yaml"
      "$HOME/.claude/.agents-mode"
      "$HOME/.agents-mode.yaml"
    )
  fi
  for f in "${files[@]}"; do
    [ -f "$f" ] || continue
    # First file whose top-level ^delegationMode: LINE is PRESENT owns the
    # decision (per-key first-match). ^ anchors the top level so nested profile
    # keys never match. An absent key falls through to the next layer; a
    # present-but-empty/unrecognized value yields silence, never a lower layer's
    # force.
    line="$(grep -m1 '^delegationMode:' "$f" 2>/dev/null)" || true
    [ -n "$line" ] || continue
    # Strip the key prefix, then a WHITESPACE-preceded ' #...' comment only (so a
    # literal value like 'force#x' stays intact -> unrecognized -> silent), then
    # trim the ends only (never internal whitespace, so 'fo rce' stays split ->
    # unrecognized -> silent), then lowercase. This mirrors the PowerShell path.
    v="$(printf '%s\n' "$line" \
         | sed 's/^delegationMode:[[:space:]]*//; s/[[:space:]][[:space:]]*#.*$//; s/^[[:space:]]*//; s/[[:space:]]*$//' \
         | tr 'A-Z' 'a-z')"
    printf '%s' "$v"; return 0
  done
  printf 'unresolved'
}

_mode="$(_read_delegation_mode 2>/dev/null)"
case "$_mode" in
  force)
    cat <<'EOF'
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"[Delegation posture - re-shown at session start and after every compaction]\nEffective delegationMode: FORCE. STANDING INSTRUCTION, not advisory: at the FIRST decision point of any non-trivial task (multi-step implementation, design, research, review, bug-fix), STOP - hold the $lead orchestration role in THIS conversation, classify the task, pick the team template, and route it via the Agent tool to the matching specialist subagents ($lead is the role you hold, not a subagent you spawn). Doing substantial work inline when a matching specialist and a viable tool path exist violates the active posture. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from contracts/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION."}}
EOF
    ;;
  auto)
    cat <<'EOF'
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"[Delegation posture - re-shown at session start and after every compaction]\nEffective delegationMode: AUTO. Holding the $lead orchestration role in THIS conversation and delegating to the matching specialist subagents via the Agent tool is the DEFAULT for any non-trivial task (multi-step implementation, design, research, review, bug-fix) - do it unless the task is trivial or you record why inline is better. $lead is the role you hold, not a subagent you spawn. When you launch any external provider (consultant / Codex / Claude) as $lead, take the launch flags from contracts/external-dispatch.md - file-based prompt, explicit model+effort, run-completion oracle, stall policy - never improvise them from memory. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION."}}
EOF
    ;;
  *)
    : # manual value, unresolved, or empty -> silent (presence of the block is the signal)
    ;;
esac
exit 0

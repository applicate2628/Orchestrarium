#!/usr/bin/env bash
# SessionStart hook -- re-injects the ACTIVE delegation posture from the effective
# .agents-mode.yaml into the model's context at every session start AND after every
# compaction. delegationMode is NOT a runtime built-in feature -- it is an
# Orchestrator-pack governance value the host never parses on its own, so without
# this hook the main conversation never sees "delegationMode: force" and never
# applies it. This hook makes the operative delegation posture visible every
# session/compaction. (Codex: plain stdout on a SessionStart hook is added as
# developer context; its source matcher includes compact.)
#
# CONDITIONAL BY DESIGN: emits an IMPERATIVE directive ONLY when the effective
# delegationMode is `force` or `auto`; SILENT on `manual` (the default). The
# silence is load-bearing -- the block appears only when delegation is operative,
# so its presence is the signal and it does not become wallpaper.
#
# SELF-CONTAINED first-match read of the documented read-order (the full
# resolve-agents-mode.py is NOT shipped to targets; force/auto are always
# file-explicit since the default is manual, so the defaults/normalizer layers are
# irrelevant here on purpose -- do not "fix" this by dragging in the defaults chain):
#   ./.agents/.agents-mode.yaml -> ./.agents/.agents-mode (legacy)
#   -> ~/.codex/.agents-mode.yaml -> ~/.codex/.agents-mode (legacy)
#   -> ~/.agents-mode.yaml (shared cross-pack). First file DEFINING delegationMode
#   wins; none -> manual -> silent.
#
# Fail-open: any error emits nothing and exits 0; never blocks a session.
set +e

_read_delegation_mode() {
  local f line v
  local files=(
    "./.agents/.agents-mode.yaml"
    "./.agents/.agents-mode"
  )
  # Home/global layers only when HOME is set, so an empty HOME never probes
  # root paths like /.codex/.agents-mode.yaml.
  if [ -n "${HOME:-}" ]; then
    files+=(
      "$HOME/.codex/.agents-mode.yaml"
      "$HOME/.codex/.agents-mode"
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
  printf 'manual'
}

_mode="$(_read_delegation_mode 2>/dev/null)"
case "$_mode" in
  force)
    cat <<'EOF'
[Delegation posture - re-shown at session start and after every compaction]
Effective delegationMode: FORCE. STANDING INSTRUCTION, not advisory: at the FIRST decision point of any non-trivial task (multi-step implementation, design, research, review, bug-fix), STOP - classify the task, pick the team template, and route it to $lead or the matching specialist subagent. Doing substantial work inline when a matching specialist and a viable tool path exist violates the active posture. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION.
EOF
    ;;
  auto)
    cat <<'EOF'
[Delegation posture - re-shown at session start and after every compaction]
Effective delegationMode: AUTO. Delegating to $lead or the matching specialist subagent is the DEFAULT for any non-trivial task (multi-step implementation, design, research, review, bug-fix) - do it unless the task is trivial or you record why inline is better. Maintain work-items/ recovery state for multi-stage chains. This STILL APPLIES AFTER COMPACTION.
EOF
    ;;
  *)
    : # manual or unresolved -> silent (presence of the block is the signal)
    ;;
esac
exit 0

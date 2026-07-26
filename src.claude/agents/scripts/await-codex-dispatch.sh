#!/usr/bin/env bash
# One-shot active completion watcher for a background Codex dispatch.
#
# The watcher exits after the first terminal signal. Missing files and failed
# git probes are deliberately non-terminal so a delayed provider can still
# create its artifacts or commit its work.
#
# Exit codes carry the terminal status so a caller can act on $? without
# parsing stdout (work-items/bugs/2026-07-26-await-codex-dispatch-cannot-
# satisfy-its-own-liveness-invariant.md): a caller testing $? previously saw
# 0 for a 45-minute stall exactly as for a delivered review.
#   0   DONE    - a real completion signal fired (non-empty lastmsg/out, or a
#                 changed HEAD when --commit-base was supplied).
#   69  DEAD    - EX_UNAVAILABLE (sysexits.h): --pid-file was given, its
#                 recorded process is CONFIRMED gone (or a different process
#                 now holds that PID -- see the start-marker check below), and
#                 none of the DONE conditions fired this same poll. Unlike
#                 STALL this is not "temporary": the specific run this watcher
#                 was tracking no longer exists, so re-waiting on it is
#                 pointless -- re-dispatch or escalate. This is the direct
#                 PID/exit-status probe the contract names (see below);
#                 without --pid-file this status is never reached and
#                 behavior is byte-for-byte the pre-existing artifact-only
#                 logic (deliberate degrade path -- see --pid-file docs).
#   75  STALL   - .err went idle past --stall-secs. EX_TEMPFAIL (sysexits.h):
#                 a temporary condition, not proof of process death, so a
#                 retry/extended wait is a reasonable caller response.
#   77  FILTERED - a THIRD silent-success shape, distinct from DEAD: the
#                 completion artifacts are still empty AND the tail of --err
#                 carries the provider's cybersecurity content-filter refusal
#                 (observed live: 0-byte .out, absent .lastmsg, exit 0, 229k
#                 tokens spent, work-items/bugs/2026-07-26-registry-bug-sweep
#                 session). EX_NOPERM (sysexits.h) -- the provider is
#                 refusing on policy grounds, not merely idle or gone. This
#                 condition is MODEL-SPECIFIC: the fix is to re-dispatch the
#                 SAME lane on a DIFFERENT model, never to reword the prompt
#                 to appease the filter (that changes what was asked, a worse
#                 outcome than a model swap). See "Cybersecurity content-
#                 filter detection" below for the conjunction this rests on.
#   124 TIMEOUT - --max-secs elapsed with nothing else terminal. Matches the
#                 exit code the GNU coreutils `timeout(1)` command uses for
#                 the same condition, a convention callers may already check.
#   2   usage/argument error (unchanged).
#
# Cybersecurity content-filter detection (FILTERED, exit 77): exit code 0 with
# empty completion artifacts is indistinguishable from "still working" --
# without this check the filtered case above cost a full --stall-secs wait
# (2700s shipped default) before anything was reported, and what was finally
# reported (STALL) named the wrong cause. Detection rests on the CONJUNCTION,
# never on either leg alone:
#   1. the DONE checks below did not fire this poll (lastmsg/out still empty,
#      no --commit-base change) -- a completed run is never overridden even if
#      its .err happens to contain the phrase (e.g. quoted in a log line);
#   2. the LAST few KB of --err (never the whole file) contain the filter
#      marker -- a real dispatch's .err is a full transcript that starts by
#      echoing the prompt itself; scanning the whole file risks matching an
#      early, unrelated mention (e.g. this very detection being discussed in
#      a dispatched prompt) while the run is still genuinely alive. The real
#      marker sits in the last ~15 lines of a 4000+ line transcript.
# The marker string is provider prose that will drift in wording, so the match
# requires both the "flag" concept and the "cybersecurity" concept to appear
# (case-insensitively, in either order) in that tail window, rather than
# pinning the exact sentence -- loose enough to survive rewording, but two
# independent words rather than one common word, to keep a healthy run's
# unrelated chatter from misfiring this status.
#
# Direct liveness probe (--pid-file), the other half of the bug above: the
# contract (contracts/review-loop.md:57, hardening invariant 5) defines
# liveness as "a DIRECT probe of the run itself -- its PID/exit status", which
# artifact timestamps alone can never satisfy. invoke-codex-prompt.sh and
# invoke-claude-prompt.sh now write a sidecar `<slug>.pid` file at launch, two
# lines:
#   pid=<PID>              the dispatched provider's OWN process id (bash
#                           always forks to exec a background command, so
#                           this is a real, separate OS process, never the
#                           wrapper's own PID)
#   start=<opaque marker>  present only when /proc exposes one (Linux/MSYS);
#                           a recycled PID reused by an unrelated LATER
#                           process will practically always carry a different
#                           marker, so a mismatch is treated as "dead", never
#                           as "alive". Never compared across hosts or parsed
#                           for meaning beyond equality.
# Pass --pid-file pointing at that same file to enable the probe. It is
# OPTIONAL and purely additive: an older invoke-*-prompt, a hand-rolled
# background launch, or any run started outside the wrapper entirely -- the
# common case the live incident's own loop hit, not the edge -- simply never
# produces a `.pid` file, `pid_file_status` returns "unknown", and this
# watcher's behavior is IDENTICAL to before this fix. A missing/unreadable/
# malformed `.pid` file degrades the same way (never treated as "dead").
#
# Combined rule for what "not running" means (a finished-successfully run and
# a died-silently run are both "not running" on their own): the DONE checks
# below always run FIRST, every poll. Only when none of them fired this same
# iteration does a confirmed-dead probe result produce the new DEAD status.
# So a process that exits normally after writing its completion artifact is
# still DONE (exit 0) even though the same poll would also see its PID gone --
# the artifact wins. Only a gone process with NO completion artifact yet
# reaches DEAD.
set -u

usage() {
  cat <<'EOF'
Usage:
  await-codex-dispatch.sh --out <out-path> [--err <err-path>]
    [--lastmsg <lastmsg-path>] [--commit-base <sha>] [--pid-file <path>]
    [--stall-secs <seconds>] [--max-secs <seconds>] [--poll-secs <seconds>]
EOF
}

fail_usage() {
  echo "FAIL: $1" >&2
  usage >&2
  exit 2
}

OUT_PATH=""
ERR_PATH=""
LASTMSG_PATH=""
COMMIT_BASE=""
PID_FILE_PATH=""
STALL_SECS=2700
MAX_SECS=3600
POLL_SECS=25

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)
      [[ $# -ge 2 ]] || fail_usage "--out requires a path"
      OUT_PATH="$2"
      shift 2
      ;;
    --err)
      [[ $# -ge 2 ]] || fail_usage "--err requires a path"
      ERR_PATH="$2"
      shift 2
      ;;
    --lastmsg)
      [[ $# -ge 2 ]] || fail_usage "--lastmsg requires a path"
      LASTMSG_PATH="$2"
      shift 2
      ;;
    --commit-base)
      [[ $# -ge 2 ]] || fail_usage "--commit-base requires a SHA"
      COMMIT_BASE="$2"
      shift 2
      ;;
    --pid-file)
      [[ $# -ge 2 ]] || fail_usage "--pid-file requires a path"
      PID_FILE_PATH="$2"
      shift 2
      ;;
    --stall-secs)
      [[ $# -ge 2 ]] || fail_usage "--stall-secs requires seconds"
      STALL_SECS="$2"
      shift 2
      ;;
    --max-secs)
      [[ $# -ge 2 ]] || fail_usage "--max-secs requires seconds"
      MAX_SECS="$2"
      shift 2
      ;;
    --poll-secs)
      [[ $# -ge 2 ]] || fail_usage "--poll-secs requires seconds"
      POLL_SECS="$2"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      fail_usage "unexpected argument '$1'"
      ;;
  esac
done

[[ -n "$OUT_PATH" ]] || fail_usage "--out is required"
[[ "$STALL_SECS" =~ ^[0-9]+$ ]] || fail_usage "--stall-secs must be a non-negative integer"
[[ "$MAX_SECS" =~ ^[0-9]+$ ]] || fail_usage "--max-secs must be a non-negative integer"
[[ "$POLL_SECS" =~ ^[0-9]+([.][0-9]+)?$ ]] || fail_usage "--poll-secs must be a non-negative number"

is_nonempty_file() {
  [[ -f "$1" && -s "$1" ]]
}

file_bytes() {
  wc -c < "$1" 2>/dev/null | tr -d '[:space:]'
}

file_mtime() {
  local mtime=""
  mtime="$(stat -c %Y "$1" 2>/dev/null || true)"
  if [[ -z "$mtime" ]]; then
    mtime="$(stat -f %m "$1" 2>/dev/null || true)"
  fi
  printf '%s' "$mtime"
}

# Bytes of --err's TAIL scanned for the cybersecurity filter marker (see the
# header comment). Deliberately NOT the whole file -- see rationale above.
FILTER_TAIL_BYTES=8192

# True (0) iff the tail of $1 carries both the "flag" and "cybersecurity"
# concepts, case-insensitively. False (1) for a missing/unreadable/empty file
# or a tail with neither/only-one concept -- the caller then falls through to
# pre-existing behavior, never a false positive from an absent file.
contains_filter_marker() {
  local path="$1" tail_text="" lower=""
  [[ -n "$path" && -f "$path" ]] || return 1
  tail_text="$(tail -c "$FILTER_TAIL_BYTES" "$path" 2>/dev/null)"
  [[ -n "$tail_text" ]] || return 1
  # tr, not bash 4's ${var,,} -- this script already carries a `stat -f`
  # fallback for BSD/macOS, whose default /bin/bash is 3.2 (no case-
  # conversion parameter expansion); tr works identically on both.
  lower="$(printf '%s' "$tail_text" | tr '[:upper:]' '[:lower:]')"
  [[ "$lower" == *"flag"* && "$lower" == *"cybersecurit"* ]]
}

# Process start-time marker for PID-reuse detection (Linux/MSYS /proc/<pid>/
# stat field 22, "starttime"). Recorded once at launch by invoke-codex-
# prompt.sh / invoke-claude-prompt.sh; re-read here and compared for EQUALITY
# only -- never interpreted as an absolute timestamp. Empty output means
# "unknown" (no /proc on this host, the process already exited, or an
# unrecognized /proc/<pid>/stat shape); callers must treat empty as
# non-conclusive, never as a match.
pid_start_marker() {
  local pid="$1" stat_path raw rest
  stat_path="/proc/$pid/stat"
  [[ -r "$stat_path" ]] || return 0
  raw="$(cat "$stat_path" 2>/dev/null)" || return 0
  # comm (field 2) can itself contain spaces/parens, so locate the LAST ')'
  # (proc(5)-recommended parsing) rather than splitting on the first token.
  rest="${raw##*) }"
  [[ "$rest" != "$raw" ]] || return 0
  # shellcheck disable=SC2086
  set -- $rest
  # $rest starts at field 3 (state); field 22 overall (starttime) is
  # positional index 20 within $rest (22 - 2 fields consumed by "pid (comm) ").
  (( $# >= 20 )) || return 0
  printf '%s' "${20}"
}

# Classify the sidecar `.pid` file's recorded run as alive/dead/unknown.
# "unknown" (missing file, unreadable, or a malformed `pid=` line) is the
# explicit degrade path: the caller must fall back to the pre-existing
# artifact-only checks exactly as if --pid-file had never been passed.
pid_file_status() {
  local path="$1" recorded_pid="" recorded_start="" current_start=""
  [[ -n "$path" && -f "$path" ]] || { printf 'unknown'; return; }
  recorded_pid="$(sed -n 's/^pid=\([0-9]\{1,\}\)$/\1/p' "$path" 2>/dev/null | head -1)"
  recorded_start="$(sed -n 's/^start=\(.*\)$/\1/p' "$path" 2>/dev/null | head -1)"
  [[ "$recorded_pid" =~ ^[0-9]+$ ]] || { printf 'unknown'; return; }
  if ! kill -0 "$recorded_pid" 2>/dev/null; then
    printf 'dead'
    return
  fi
  if [[ -n "$recorded_start" ]]; then
    current_start="$(pid_start_marker "$recorded_pid")"
    if [[ -n "$current_start" && "$current_start" != "$recorded_start" ]]; then
      # A DIFFERENT process now holds this PID -- the run we launched is gone.
      printf 'dead'
      return
    fi
  fi
  printf 'alive'
}

started_at="$(date +%s)"

while :; do
  if [[ -n "$LASTMSG_PATH" ]] && is_nonempty_file "$LASTMSG_PATH"; then
    printf 'DONE lastmsg=%s\n' "$(file_bytes "$LASTMSG_PATH")"
    exit 0
  fi

  if is_nonempty_file "$OUT_PATH"; then
    printf 'DONE out=%s\n' "$(file_bytes "$OUT_PATH")"
    exit 0
  fi

  if [[ -n "$COMMIT_BASE" ]]; then
    current_head="$(git rev-parse HEAD 2>/dev/null || true)"
    if [[ -n "$current_head" && "$current_head" != "$COMMIT_BASE" ]]; then
      printf 'DONE committed=%s\n' "$current_head"
      exit 0
    fi
  fi

  # Cybersecurity content-filter detection: only reached when none of the
  # DONE checks above fired THIS poll (see header comment for the full
  # conjunction). Independent of --pid-file -- fires on content alone, every
  # poll, so it never waits out --stall-secs the way the live incident did.
  if [[ -n "$ERR_PATH" ]] && contains_filter_marker "$ERR_PATH"; then
    printf 'FILTERED err=%s reason=provider-cybersecurity-content-filter action=redispatch-different-model-do-not-reword\n' "$ERR_PATH"
    exit 77
  fi

  # Direct liveness probe: only reached when none of the DONE checks above
  # fired THIS poll, so a process that already exited after writing its
  # completion artifact is still DONE, never DEAD -- see the combined-rule
  # comment in the header. --pid-file omitted (or unreadable/malformed)
  # resolves "unknown" and this block is a no-op, matching pre-fix behavior.
  if [[ -n "$PID_FILE_PATH" ]] && [[ "$(pid_file_status "$PID_FILE_PATH")" == "dead" ]]; then
    printf 'DEAD pid-file=%s\n' "$PID_FILE_PATH"
    exit 69
  fi

  if [[ -n "$ERR_PATH" && -f "$ERR_PATH" ]]; then
    err_mtime="$(file_mtime "$ERR_PATH")"
    now="$(date +%s)"
    if [[ "$err_mtime" =~ ^[0-9]+$ ]] && (( now - err_mtime > STALL_SECS )); then
      printf 'STALL err-idle=%s\n' "$((now - err_mtime))"
      exit 75
    fi
  fi

  elapsed="$(($(date +%s) - started_at))"
  if (( elapsed >= MAX_SECS )); then
    printf 'TIMEOUT max=%s\n' "$MAX_SECS"
    exit 124
  fi

  sleep "$POLL_SECS"
done

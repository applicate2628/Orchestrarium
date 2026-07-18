#!/usr/bin/env bash
# One-shot active completion watcher for a background Codex dispatch.
#
# The watcher exits after the first terminal signal. Missing files and failed
# git probes are deliberately non-terminal so a delayed provider can still
# create its artifacts or commit its work.
set -u

usage() {
  cat <<'EOF'
Usage:
  await-codex-dispatch.sh --out <out-path> [--err <err-path>]
    [--lastmsg <lastmsg-path>] [--commit-base <sha>]
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

  if [[ -n "$ERR_PATH" && -f "$ERR_PATH" ]]; then
    err_mtime="$(file_mtime "$ERR_PATH")"
    now="$(date +%s)"
    if [[ "$err_mtime" =~ ^[0-9]+$ ]] && (( now - err_mtime > STALL_SECS )); then
      printf 'STALL err-idle=%s\n' "$((now - err_mtime))"
      exit 0
    fi
  fi

  elapsed="$(($(date +%s) - started_at))"
  if (( elapsed >= MAX_SECS )); then
    printf 'TIMEOUT max=%s\n' "$MAX_SECS"
    exit 0
  fi

  sleep "$POLL_SECS"
done

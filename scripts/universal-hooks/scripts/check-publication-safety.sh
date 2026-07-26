#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash <path>/check-publication-safety.sh
  bash <path>/check-publication-safety.sh --path <dir>

By default, scans staged tracked files in the repository for publication-safety issues.
Use --path only for local fixture testing or explicit manual checks.
EOF
}

scan_path="."
scan_mode="tracked"

if [[ $# -gt 0 ]]; then
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --path)
      shift
      if [[ $# -eq 0 ]]; then
        echo "error: --path requires a path argument" >&2
        exit 2
      fi
      scan_path="$1"
      scan_mode="path"
      shift
      ;;
    *)
      scan_path="$1"
      scan_mode="path"
      shift
      ;;
  esac
fi

if [[ $# -gt 0 ]]; then
  echo "error: unexpected extra arguments: $*" >&2
  usage >&2
  exit 2
fi

# Non-path patterns: secrets, tokens, keys, .env, transcript markers, and
# macOS temp-dir markers. These are an UNCONDITIONAL block source -- they are
# NEVER passed through the placeholder allowlist. A line that matches any of
# these BLOCKS even if it also contains an allowed path token (e.g. a secret on
# a line that also mentions C:\Users\<you>).
#
# The machine-local PATH patterns (Windows/MSYS/macOS user homes, dev/work
# roots) are intentionally NOT in this array. They are placeholder-bearing
# (`C:\Users\<name>`, `%USERPROFILE%`, `C:\Users\you`) and are handled below by
# the allowlist-aware path check, which reuses the single allowlist owner
# (`check-machine-local-path.py`'s find_machine_paths) so placeholder docs do
# not false-positive while concrete machine paths still block.
nonpath_patterns=(
  'AKIA[0-9A-Z]{16}'
  'ghp_[A-Za-z0-9]{36}'
  'sk-[A-Za-z0-9]{20,}'
  'sk-ant-[A-Za-z0-9_-]{20,}'
  'ANTHROPIC_[A-Z_]*(KEY|TOKEN)[^[:alnum:]_]?[[:space:]]*[:=]'
  'Bearer[[:space:]]+[A-Za-z0-9._~+/=-]+'
  '[Pp]assword[[:space:]]*[:=]'
  '[Ss]ecret[[:space:]]*[:=]'
  '[Tt]oken[[:space:]]*[:=]'
  'api[_-]?[Kk]ey[[:space:]]*[:=]'
  'BEGIN RSA PRIVATE KEY'
  'BEGIN OPENSSH PRIVATE KEY'
  'BEGIN PRIVATE KEY'
  'private_key'
  'secret_key'
  '/private/var/folders/'
  '/var/folders/'
  '^Human:[[:space:]]*'
  '^Assistant:[[:space:]]*'
  '^\$[[:space:]]+'
  '^>>>[[:space:]]+'
  '\[[0-9]{2}:[0-9]{2}:[0-9]{2}\]'
)

# Refined approach-A path patterns, used ONLY in the no-Python fallback. They
# require a real-name character ([A-Za-z0-9_]) right after the root separator,
# which strips the `<...>` / `%...%` / `${...}` / `...` placeholder
# false-positives that the original placeholder-blind patterns flagged. Unlike
# the Python path (approach B), these do NOT honor the bare example-token
# allowlist, so the fallback over-blocks `C:\Users\you` etc. -- a deliberate
# fail-safe (over-block) when the shared allowlist owner is unreachable. POSIX
# ERE only (git grep -E): plain (a|b) groups, no (?:...).
fallback_path_patterns=(
  '[A-Za-z]:[\\/]+[Uu]sers[\\/]+[A-Za-z0-9_]'
  '[A-Za-z]:[\\/]+(dev|work|projects)[\\/]+[A-Za-z0-9_]'
  '/[A-Za-z]/[Uu]sers/[A-Za-z0-9_]'
  '/[A-Za-z]/(dev|work|projects)/[A-Za-z0-9_]'
  '/home/[A-Za-z0-9_]'
  '/Users/[A-Za-z0-9_]'
)

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

# Resolve the single allowlist owner RELATIVE to THIS scanner's own location,
# so each pack imports its own sibling copy and never the other pack's. The
# reference module adds its sibling scripts/ dir to sys.path for hook_common, so
# importing the module file directly is sufficient.
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
ref_module="$script_dir/../hooks/check-machine-local-path.py"

if [[ "$scan_mode" == "tracked" ]]; then
  staged_paths=()
  regular_staged_paths=()
  scanner_staged_paths=()
  while IFS= read -r -d '' staged_path; do
    staged_paths+=("$staged_path")
    if [[ "$staged_path" == *"/check-publication-safety.sh" || "$staged_path" == "check-publication-safety.sh" ]]; then
      scanner_staged_paths+=("$staged_path")
    else
      regular_staged_paths+=("$staged_path")
    fi
  done < <(git diff --cached --name-only --diff-filter=ACMRTUXB -z --)

  if [[ ${#staged_paths[@]} -eq 0 ]]; then
    # Honest-result signal (2026-07-26 hardening, D2 of
    # work-items/backlog/2026-07-25-push-gate-blind-to-scan-result/brief.md
    # §11.5): an empty `git diff --cached` is NOT a clean scan, it is a scan
    # that examined NOTHING -- the exact shape of the ordinary commit-then-push
    # flow, where the staged index already equals HEAD. Exit 0 is still correct
    # (there is nothing here to block on), but the caller consuming this
    # scan's RESULT (check-git-push-gate.py step 8 branch (b)) must be able to
    # tell this apart from a real clean scan, so it never counts an empty scan
    # as a pass. This line is deliberately tagged "tracked" with a "0" count so
    # SCAN_CLEAN_TRACKED_REGEX's `[1-9]\d*` requirement cannot match it.
    echo "publication-safety: clean (tracked, examined 0 files -- nothing staged)"
    exit 0
  fi
  scan_files=("${staged_paths[@]}")
else
  scan_files=("$scan_path")
fi

path_name_block=0
for scan_file in "${scan_files[@]}"; do
  base_name="${scan_file##*/}"
  if [[ "$base_name" == ".env" ]]; then
    echo "$scan_file: blocked filename .env (staged secret/config file)" >&2
    path_name_block=1
  fi
  # The pack's own credential file (.claude/SECRET.md or any SECRET.md) must
  # never be staged, regardless of content format -- this filename block is the
  # format-independent primary defense; the sk-ant-/ANTHROPIC_ content patterns
  # above are the secondary net. The name compare is CASE-INSENSITIVE: Windows,
  # the pack's primary platform, has a case-insensitive filesystem, so a staged
  # secret.md / Secret.md is the same credential file and must block identically.
  name_upper="$(printf '%s' "$base_name" | tr '[:lower:]' '[:upper:]')"
  if [[ "$name_upper" == "SECRET.MD" ]]; then
    echo "$scan_file: blocked filename $base_name (staged credential file; keep it untracked)" >&2
    path_name_block=1
  fi
done

# Self-exemption for the scanner's OWN staged copy only -- callers key it to
# the check-publication-safety.sh filename, so it can never exempt any other
# staged file. The scanner file IS the pattern catalog, so exactly two of its
# own line shapes are intentional marker-bearing content: (1) a pattern-array
# entry, i.e. a line that is ENTIRELY one single-quoted literal, and (2) a
# full-line comment (scanner documentation naming the markers it blocks).
# Anything else in the scanner file still blocks -- a catalog line with a
# trailing payload, or code carrying a real value, is not exempt.
is_intentional_scanner_regex_line() {
  local trimmed="${1#"${1%%[![:space:]]*}"}"
  trimmed="${trimmed%"${trimmed##*[![:space:]]}"}"
  local q="'"
  if [[ ${#trimmed} -ge 2 && "$trimmed" == "$q"*"$q" && "${trimmed:1:${#trimmed}-2}" != *"$q"* ]]; then
    return 0
  fi
  [[ "$trimmed" == "#"* ]]
}

# Build the non-path git grep command (unconditional block source).
nonpath_cmd=(git grep -n -I -E --full-name)
for pattern in "${nonpath_patterns[@]}"; do
  nonpath_cmd+=(-e "$pattern")
done
if [[ "$scan_mode" == "tracked" ]]; then
  if [[ ${#regular_staged_paths[@]} -gt 0 ]]; then
    nonpath_cmd+=(--cached -- "${regular_staged_paths[@]}")
  else
    nonpath_cmd=()
  fi
else
  nonpath_cmd+=(--no-index -- "$scan_path")
fi

# MSYS2_ARG_CONV_EXCL='*' disables MSYS path conversion of git-grep arguments.
# Without it, the bundled Windows gate bash rewrites leading-slash patterns
# (e.g. /var/folders/) into Windows paths, so they silently match nothing. It
# is safe for every pattern (grep patterns are not real paths).
set +e
if [[ ${#nonpath_cmd[@]} -gt 0 ]]; then
  MSYS2_ARG_CONV_EXCL='*' "${nonpath_cmd[@]}"
  nonpath_status=$?
else
  nonpath_status=1
fi
set -e

# nonpath_status: 0 = a non-path leak marker was found (BLOCK); 1 = none; >=2 =
# git error -> fail safe by propagating the error status below.
nonpath_block=0
if [[ $nonpath_status -eq 0 ]]; then
  nonpath_block=1
fi
if [[ "$scan_mode" == "tracked" && ${#scanner_staged_paths[@]} -gt 0 ]]; then
  scanner_nonpath_cmd=(git grep -n -I -E --full-name)
  for pattern in "${nonpath_patterns[@]}"; do
    scanner_nonpath_cmd+=(-e "$pattern")
  done
  scanner_nonpath_cmd+=(--cached -- "${scanner_staged_paths[@]}")
  set +e
  scanner_nonpath_output="$(MSYS2_ARG_CONV_EXCL='*' "${scanner_nonpath_cmd[@]}")"
  scanner_nonpath_status=$?
  set -e
  if [[ $scanner_nonpath_status -eq 0 ]]; then
    while IFS= read -r scanner_line; do
      [[ -z "$scanner_line" ]] && continue
      if [[ "$scanner_line" =~ ^([^:]+):([0-9]+):(.*)$ ]]; then
        scanner_content="${BASH_REMATCH[3]}"
        if is_intentional_scanner_regex_line "$scanner_content"; then
          continue
        fi
      fi
      echo "$scanner_line" >&2
      nonpath_block=1
    done <<< "$scanner_nonpath_output"
  elif [[ $scanner_nonpath_status -ge 2 ]]; then
    echo "publication-safety: scanner-file nonpath grep failed (status $scanner_nonpath_status); over-blocking" >&2
    nonpath_block=1
  fi
fi

# Path check: prefer approach B (Python allowlist owner, immune to MSYS argv
# mangling, honors the placeholder/example-token allowlist). Fall back to
# approach A (refined ERE under the MSYS guard) only when no Python interpreter
# is reachable. Fail safe = over-block; never fail open.
python_bin=""
if command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  python_bin="$(command -v python)"
fi

path_block=0
if [[ -n "$python_bin" && -f "$ref_module" ]]; then
  set +e
  "$python_bin" - "$ref_module" "$scan_mode" "${scan_files[@]}" <<'PUBSAFE_PATHFILTER_PY'
import importlib.util
import os
import subprocess
import sys


def _load_find_machine_paths(mod_file):
    spec = importlib.util.spec_from_file_location("_mlp_ref", mod_file)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.find_machine_paths


def _staged_content(path):
    out = subprocess.run(["git", "show", ":" + path], capture_output=True)
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", errors="replace")


def _disk_content(path):
    try:
        with open(path, "rb") as fh:
            return fh.read().decode("utf-8", errors="replace")
    except (OSError, UnicodeError):
        return None


def _expand_path_mode(paths):
    for p in paths:
        if os.path.isdir(p):
            for root, _dirs, names in os.walk(p):
                for name in names:
                    yield os.path.join(root, name)
        else:
            yield p


SCANNER_BASENAME = "check-publication-safety.sh"


def _is_intentional_scanner_line(line):
    # Mirror of the shell-side self-exemption, applied ONLY to a file whose
    # basename is the scanner's own (checked by the caller): a pattern-array
    # entry (a line that is entirely one single-quoted literal) or a full-line
    # comment. Every other file gets no exemption, so a leaked machine-local
    # path in any non-scanner file still blocks.
    trimmed = line.strip()
    if trimmed.startswith("#"):
        return True
    return (
        len(trimmed) >= 2
        and trimmed.startswith("'")
        and trimmed.endswith("'")
        and "'" not in trimmed[1:-1]
    )


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("pubsafe path filter: missing reference module / mode\n")
        return 1
    mod_file, mode, raw_files = argv[0], argv[1], argv[2:]
    try:
        find_machine_paths = _load_find_machine_paths(mod_file)
    except Exception as exc:
        sys.stderr.write(
            f"pubsafe path filter: cannot load allowlist owner {mod_file!r}: {exc}; over-blocking\n"
        )
        return 1
    files = list(raw_files) if mode == "tracked" else list(_expand_path_mode(raw_files))
    blocking = 0
    for path in files:
        is_scanner_file = os.path.basename(path) == SCANNER_BASENAME
        content = _staged_content(path) if mode == "tracked" else _disk_content(path)
        if content is None:
            sys.stderr.write(
                f"pubsafe path filter: could not read {mode} content for {path!r}; over-blocking\n"
            )
            blocking += 1
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
            if is_scanner_file and _is_intentional_scanner_line(line):
                continue
            hits = find_machine_paths(line)
            if hits:
                blocking += 1
                sys.stderr.write(f"{path}:{lineno}: machine-local path: {', '.join(hits[:5])}\n")
    return 1 if blocking else 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:
        sys.stderr.write(f"pubsafe path filter: unexpected error: {exc}; over-blocking\n")
        sys.exit(1)
PUBSAFE_PATHFILTER_PY
  path_status=$?
  set -e
  if [[ $path_status -ne 0 ]]; then
    path_block=1
  fi
else
  echo "publication-safety: no Python interpreter reachable (or allowlist owner missing); using refined regex fallback (degraded mode -- example-token paths over-block)" >&2
  fallback_cmd=(git grep -n -I -E --full-name)
  for pattern in "${fallback_path_patterns[@]}"; do
    fallback_cmd+=(-e "$pattern")
  done
  if [[ "$scan_mode" == "tracked" ]]; then
    fallback_cmd+=(--cached -- "${scan_files[@]}")
  else
    fallback_cmd+=(--no-index -- "$scan_path")
  fi
  set +e
  MSYS2_ARG_CONV_EXCL='*' "${fallback_cmd[@]}"
  fallback_status=$?
  set -e
  # 0 = a concrete machine path was found (BLOCK); 1 = none; >=2 = git error.
  if [[ $fallback_status -eq 0 ]]; then
    path_block=1
  elif [[ $fallback_status -ge 2 ]]; then
    echo "publication-safety: fallback git grep failed (status $fallback_status); over-blocking" >&2
    path_block=1
  fi
fi

if [[ $path_name_block -eq 1 || $nonpath_block -eq 1 || $path_block -eq 1 ]]; then
  echo "publication-safety scan found potential tracked-content leak markers" >&2
  exit 1
fi

# No leaks found by either check. If the non-path git grep returned an
# unexpected error status (>=2), propagate it as a fail-safe rather than
# reporting a clean pass.
if [[ $nonpath_status -ge 2 ]]; then
  exit "$nonpath_status"
fi

# Honest-result signal (2026-07-26 hardening, see the matching comment on the
# tracked-mode empty-set exit above): report the scan MODE and the actual
# examined count so a caller reading this scan's own output (not just its exit
# code) can tell a real, non-empty, tracked-mode clean pass apart from an
# empty-set pass or a `--path` fixture-testing pass. `scan_mode` is printed
# verbatim ("tracked" or "path") -- deliberately NOT normalized to one word --
# so a `--path` invocation can never read as "tracked" gate evidence
# (check-git-push-gate.py's SCAN_CLEAN_TRACKED_REGEX requires the literal word
# "tracked").
#
# examined_count for `path` mode is NOT `${#scan_files[@]}` (that array always
# holds exactly one entry: the `--path` argument itself, whether it names a
# file or a directory) -- it is the ACTUAL number of files examined, computed
# the same way the Python allowlist path (`_expand_path_mode`) walks a
# directory. Reporting a hardcoded "1" for a directory argument that in fact
# contained several files would be a false record of what was scanned (an
# honesty defect flagged 2026-07-26; path mode can never satisfy the gate
# regardless of count, so this was never a security hole, only a wrong number).
if [[ "$scan_mode" == "path" ]]; then
  if [[ -d "$scan_path" ]]; then
    examined_count="$(find "$scan_path" -type f | wc -l | tr -d '[:space:]')"
  else
    examined_count=1
  fi
else
  examined_count="${#scan_files[@]}"
fi
examined_word="files"
if [[ "$examined_count" -eq 1 ]]; then
  examined_word="file"
fi
echo "publication-safety: clean (${scan_mode}, examined ${examined_count} ${examined_word})"
exit 0

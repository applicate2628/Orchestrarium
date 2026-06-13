#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash src.codex/skills/lead/scripts/check-publication-safety.sh        (dev repo)
  bash .codex/skills/lead/scripts/check-publication-safety.sh           (global install)
  bash .agents/skills/lead/scripts/check-publication-safety.sh          (repo-local install)
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
  'Bearer[[:space:]]+[A-Za-z0-9._~+/=-]+'
  '[Pp]assword[[:space:]]*[:=]'
  '[Ss]ecret[[:space:]]*[:=]'
  '[Tt]oken[[:space:]]*[:=]'
  'api[_-]?[Kk]ey[[:space:]]*[:=]'
  'BEGIN RSA PRIVATE KEY'
  'BEGIN OPENSSH PRIVATE KEY'
  'BEGIN PRIVATE KEY'
  '\.env$'
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
  while IFS= read -r -d '' staged_path; do
    if [[ "$staged_path" == *"/check-publication-safety.sh" ]]; then
      continue
    fi
    staged_paths+=("$staged_path")
  done < <(git diff --cached --name-only --diff-filter=ACMRTUXB -z --)

  if [[ ${#staged_paths[@]} -eq 0 ]]; then
    exit 0
  fi
  scan_files=("${staged_paths[@]}")
else
  scan_files=("$scan_path")
fi

# Build the non-path git grep command (unconditional block source).
nonpath_cmd=(git grep -n -I -E --full-name)
for pattern in "${nonpath_patterns[@]}"; do
  nonpath_cmd+=(-e "$pattern")
done
if [[ "$scan_mode" == "tracked" ]]; then
  nonpath_cmd+=(--cached -- "${scan_files[@]}")
else
  nonpath_cmd+=(--no-index -- "$scan_path")
fi

# MSYS2_ARG_CONV_EXCL='*' disables MSYS path conversion of git-grep arguments.
# Without it, the bundled Windows gate bash rewrites leading-slash patterns
# (e.g. /var/folders/) into Windows paths, so they silently match nothing. It
# is safe for every pattern (grep patterns are not real paths).
set +e
MSYS2_ARG_CONV_EXCL='*' "${nonpath_cmd[@]}"
nonpath_status=$?
set -e

# nonpath_status: 0 = a non-path leak marker was found (BLOCK); 1 = none; >=2 =
# git error -> fail safe by propagating the error status below.
nonpath_block=0
if [[ $nonpath_status -eq 0 ]]; then
  nonpath_block=1
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
        content = _staged_content(path) if mode == "tracked" else _disk_content(path)
        if content is None:
            sys.stderr.write(
                f"pubsafe path filter: could not read {mode} content for {path!r}; over-blocking\n"
            )
            blocking += 1
            continue
        for lineno, line in enumerate(content.splitlines(), start=1):
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

if [[ $nonpath_block -eq 1 || $path_block -eq 1 ]]; then
  echo "publication-safety scan found potential tracked-content leak markers" >&2
  exit 1
fi

# No leaks found by either check. If the non-path git grep returned an
# unexpected error status (>=2), propagate it as a fail-safe rather than
# reporting a clean pass.
if [[ $nonpath_status -ge 2 ]]; then
  exit "$nonpath_status"
fi

exit 0

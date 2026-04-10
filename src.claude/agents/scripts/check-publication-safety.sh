#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash .claude/agents/scripts/check-publication-safety.sh
  bash .claude/agents/scripts/check-publication-safety.sh --path <path>

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

patterns=(
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
  '[A-Za-z]:\\Users\\'
  '/Users/'
  '/home/'
  '/private/var/folders/'
  '/var/folders/'
  '^Human:[[:space:]]*'
  '^Assistant:[[:space:]]*'
  '^\$[[:space:]]+'
  '^>>>[[:space:]]+'
  '\[[0-9]{2}:[0-9]{2}:[0-9]{2}\]'
)

cmd=(git grep -n -I -E --full-name)
for pattern in "${patterns[@]}"; do
  cmd+=(-e "$pattern")
done

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

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

  cmd+=(--cached -- "${staged_paths[@]}")
else
  cmd+=(--no-index -- "$scan_path")
fi

set +e
"${cmd[@]}"
status=$?
set -e

if [[ $status -eq 0 ]]; then
  echo "publication-safety scan found potential tracked-content leak markers" >&2
  exit 1
fi

if [[ $status -eq 1 ]]; then
  exit 0
fi

exit "$status"

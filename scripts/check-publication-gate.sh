#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  bash scripts/check-publication-gate.sh
  bash scripts/check-publication-gate.sh --release-notes-exempt "<reason>"

Runs the repo-local publication gate for the Orchestrarium main branch:
1. Generic publication-safety leak scan over staged tracked files.
2. Repo-local RELEASE_NOTES.md gate for release-relevant staged changes.

Use --release-notes-exempt only after an explicit human reviewer determination
that the staged change is release-notes-exempt under repo policy.
EOF
}

release_notes_exempt_reason=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help)
      usage
      exit 0
      ;;
    --release-notes-exempt)
      shift
      if [[ $# -eq 0 || -z "${1:-}" ]]; then
        echo "error: --release-notes-exempt requires a non-empty reason" >&2
        exit 2
      fi
      release_notes_exempt_reason="$1"
      shift
      ;;
    *)
      echo "error: unexpected argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

repo_root="$(git rev-parse --show-toplevel)"
cd "$repo_root"

bash src.codex/skills/lead/scripts/check-publication-safety.sh

staged_paths=()
while IFS= read -r -d '' staged_path; do
  staged_paths+=("$staged_path")
done < <(git diff --cached --name-only --diff-filter=ACMRTUXB -z --)

if [[ ${#staged_paths[@]} -eq 0 ]]; then
  echo "PASS: no staged tracked changes"
  exit 0
fi

release_relevant_paths=()
release_notes_staged=0

for staged_path in "${staged_paths[@]}"; do
  if [[ "$staged_path" == "RELEASE_NOTES.md" ]]; then
    release_notes_staged=1
    continue
  fi

  case "$staged_path" in
    .reports/*|.plans/*|.scratch/*|work-items/*)
      continue
      ;;
  esac

  release_relevant_paths+=("$staged_path")
done

if [[ ${#release_relevant_paths[@]} -eq 0 ]]; then
  echo "PASS: staged tracked changes are release-notes-exempt by path class"
  exit 0
fi

if [[ -n "$release_notes_exempt_reason" ]]; then
  echo "PASS: release-notes requirement explicitly exempted by reviewer: $release_notes_exempt_reason"
  exit 0
fi

if [[ $release_notes_staged -ne 1 ]]; then
  echo "FAIL: release-relevant staged changes require a matching RELEASE_NOTES.md update or --release-notes-exempt <reason>" >&2
  printf 'release-relevant staged paths:\n' >&2
  for path in "${release_relevant_paths[@]}"; do
    printf '  - %s\n' "$path" >&2
  done
  exit 1
fi

release_notes_path="$repo_root/RELEASE_NOTES.md"
if [[ ! -f "$release_notes_path" ]]; then
  echo "FAIL: missing RELEASE_NOTES.md at repo root" >&2
  exit 1
fi

if grep -q '^## Unreleased$' "$release_notes_path"; then
  echo "FAIL: RELEASE_NOTES.md must use dated sections and must not keep a long-lived '## Unreleased' bucket" >&2
  exit 1
fi

mapfile -t dated_sections < <(grep -E '^## [0-9]{4}-[0-9]{2}-[0-9]{2}$' "$release_notes_path" | sed 's/^## //')
if [[ ${#dated_sections[@]} -eq 0 ]]; then
  echo "FAIL: RELEASE_NOTES.md must contain at least one top-level '## YYYY-MM-DD' section" >&2
  exit 1
fi

declare -A seen_dates=()
previous_date=""
for date_section in "${dated_sections[@]}"; do
  if [[ -n "${seen_dates[$date_section]:-}" ]]; then
    echo "FAIL: duplicate dated section in RELEASE_NOTES.md: $date_section" >&2
    exit 1
  fi
  seen_dates[$date_section]=1

  if [[ -n "$previous_date" && "$date_section" > "$previous_date" ]]; then
    echo "FAIL: RELEASE_NOTES.md date sections must stay in reverse-chronological order" >&2
    exit 1
  fi
  previous_date="$date_section"
done

release_notes_diff="$(git diff --cached --unified=0 -- RELEASE_NOTES.md)"
if ! grep -Eq '^\+## [0-9]{4}-[0-9]{2}-[0-9]{2}$|^\+- ' <<<"$release_notes_diff"; then
  echo "FAIL: staged RELEASE_NOTES.md update must add a dated section or at least one explanatory bullet" >&2
  exit 1
fi

echo "PASS: publication gate passed (leak scan clean, release notes present, dated structure valid)"

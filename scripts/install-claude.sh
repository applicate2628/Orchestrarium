#!/usr/bin/env bash
# Install Claude Code pack.
# Usage:
#   bash scripts/install-claude.sh                  install into current repo (.claude/)
#   bash scripts/install-claude.sh --global         install into ~/.claude/
#   bash scripts/install-claude.sh --target DIR     install into DIR/.claude/ (or DIR if DIR ends with .claude)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$REPO_DIR/src.claude"
DEFAULT_AGENTS_MODE_SOURCE="$REPO_DIR/shared/agents-mode.defaults.yaml"

# Directories to install (order doesn't matter). `commands/` is the SINGLE
# monorepo flow surface: each agents-* flow ships as commands/agents-*.md only.
# The generated skills/agents-*/SKILL.md variants are a standalone-BRANCH
# packaging artifact (extract-provider-branch.py), not shipped here; the reserved
# `agents-` namespace reclaim below removes any stale ones from prior installs.
DIRS=(agents commands skills)
FORCE=0
DRY_RUN=0
ALLOW_UNSAFE_TARGET=0
NO_HYPOTHESIS_HOOK=0
MODE=""
TARGET=""

usage() {
  echo "Usage:"
  echo "  bash scripts/install-claude.sh                          Install into current repo (.claude/)"
  echo "  bash scripts/install-claude.sh --global                 Install into ~/.claude/"
  echo "  bash scripts/install-claude.sh --target DIR             Install into DIR/.claude/"
  echo "  bash scripts/install-claude.sh --force                  Skip deletion prompts"
  echo "  bash scripts/install-claude.sh --dry-run                Print planned actions without changing files"
  echo "  bash scripts/install-claude.sh --allow-unsafe-target    Override allowlist for custom target path"
  echo "  bash scripts/install-claude.sh --help                   Show help"
  exit 1
}

canonical_path() {
  local input_path="$1"
  local expanded="${input_path/#\~/$HOME}"

  if [ -z "$expanded" ]; then
    echo "" 
    return 1
  fi

  if [ -d "$expanded" ] || [ -L "$expanded" ]; then
    local resolved
    resolved="$(cd "$expanded" && pwd -P)"
    echo "$resolved"
    return 0
  fi

  # For non-existing paths, resolve component-by-component preserving all
  # virtual segments so we keep the intended directory structure.
  local result=""
  local part
  local next

  if [ "${expanded:0:1}" = "/" ]; then
    result="/"
  else
    result="$(pwd -P)"
  fi

  local IFS='/'
  for part in ${expanded}; do
    case "$part" in
      ""|".")
        continue
        ;;
      "..")
        result="$(dirname "$result")"
        if [ -z "$result" ]; then
          result="/"
        fi
        ;;
      *)
        next="$result/$part"
        if [ "$result" = "/" ]; then
          next="/$part"
        fi

        if [ -e "$next" ] || [ -L "$next" ]; then
          if [ -d "$next" ] || [ -L "$next" ]; then
            next="$(cd "$next" && pwd -P)"
          fi
        fi

        result="$next"
        ;;
    esac
  done

  echo "$result"
}

resolve_install_target() {
  local input_path="$1"
  local normalized

  normalized="$(canonical_path "$input_path")"
  if [ -z "$normalized" ]; then
    echo "FAIL: unable to resolve target path '$input_path'" >&2
    return 1
  fi

  if [ "$(basename "$normalized")" = ".claude" ]; then
    printf "%s" "$normalized"
  else
    printf "%s/.claude" "$normalized"
  fi
}

path_has_reparse_component() {
  local path="$1"
  local current="$path"

  while :; do
    if [ -e "$current" ] && [ -L "$current" ]; then
      return 0
    fi

    local parent
    parent="$(dirname "$current")"
    if [ "$parent" = "$current" ] || [ -z "$parent" ]; then
      break
    fi
    current="$parent"
  done

  return 1
}

is_allowed_target() {
  local target="$(printf '%s' "$1" | tr '[:upper:]' '[:lower:]')"
  local candidate
  for candidate in "${ALLOWLIST[@]}"; do
    candidate="$(printf '%s' "$candidate" | tr '[:upper:]' '[:lower:]')"
    if [ "$target" = "$candidate" ]; then
      return 0
    fi
  done
  return 1
}

validate_target_root() {
  local path="$1"
  local mode="$2"

  if path_has_reparse_component "$path"; then
    echo "FAIL: target path '$path' contains a symlink/junction component." >&2
    return 1
  fi

  local target
  target="$(resolve_install_target "$path")"
  local target_lower
  target_lower="$(printf '%s' "$target" | tr '[:upper:]' '[:lower:]')"

  if [ -z "$target_lower" ]; then
    echo "FAIL: empty target" >&2
    return 1
  fi

  if [ "$(basename "$target_lower")" != ".claude" ]; then
    echo "FAIL: target '$target' must resolve to .claude directory" >&2
    return 1
  fi

  if [ "$mode" = "target" ] && [ "$ALLOW_UNSAFE_TARGET" -ne 1 ]; then
    if ! is_allowed_target "$target"; then
      if [ -t 0 ]; then
        while :; do
          echo "WARNING: target '$target' is outside the default allowlist."
          read -r -p "Type ALLOW to proceed with this target, or press Enter to abort: " confirm
          if [ "${confirm^^}" = "ALLOW" ]; then
            break
          fi
          if [ -z "$confirm" ]; then
            echo "Install cancelled: unsafe target denied." >&2
            return 1
          fi
          echo "Please type ALLOW to continue, or press Enter to cancel." >&2
        done
      else
        echo "FAIL: unsafe target denied for non-interactive install. Use --allow-unsafe-target." >&2
        return 1
      fi
    fi
  fi

  printf "%s" "$target"
}

build_allowlist() {
  ALLOWLIST=()
  local repo_root

  if git rev-parse --show-toplevel &>/dev/null; then
    repo_root="$(git rev-parse --show-toplevel)"
  else
    repo_root="$(pwd)"
  fi

  if [ "$MODE" = "repo" ] || [ "$MODE" = "target" ]; then
    ALLOWLIST+=("$(resolve_install_target "$repo_root")")
  fi

  if [ "$MODE" = "global" ] || [ "$MODE" = "target" ]; then
    ALLOWLIST+=("$(resolve_install_target "$HOME")")
  fi

  if [ -n "${CLAUDE_INSTALL_ALLOWLIST:-}" ]; then
    IFS=',' read -r -a ALLOWLIST_EXTRA <<< "$CLAUDE_INSTALL_ALLOWLIST"
    for raw in "${ALLOWLIST_EXTRA[@]}"; do
      if [ -n "$raw" ]; then
        ALLOWLIST+=("$(resolve_install_target "$raw")")
      fi
    done
  fi

  # normalize duplicates
  local dedup=()
  local existing
  for entry in "${ALLOWLIST[@]}"; do
    local norm
    norm="$(printf '%s' "$entry" | tr '[:upper:]' '[:lower:]')"
    if [ -z "$norm" ]; then
      continue
    fi
    existing=0
    for item in "${dedup[@]}"; do
      if [ "$(printf '%s' "$item" | tr '[:upper:]' '[:lower:]')" = "$norm" ]; then
        existing=1
        break
      fi
    done
    if [ "$existing" -ne 1 ]; then
      dedup+=("$entry")
    fi
  done
  ALLOWLIST=("${dedup[@]}")
}

# Per-item install preserves user-added files — no destructive directory wipe needed.

prompt_install_mode() {
  if [ ! -t 0 ]; then
    echo "FAIL: No install target specified and not running interactively." >&2
    echo "Use: bash scripts/install-claude.sh --global  or  bash scripts/install-claude.sh --target <path>" >&2
    exit 1
  fi

  while true; do
    echo "Select installation target:"
    echo "  1) Local repo (.claude/)"
    echo "  2) Global (~/.claude/)"
    echo "  3) Custom target directory"
    echo "  4) Abort"
    echo -n "Choose [1-4, default: 1]: "
    read -r choice
    choice="${choice:-1}"

    case "$choice" in
      1)
        MODE="repo"
        return
        ;;
      2)
        MODE="global"
        TARGET="$HOME/.claude"
        return
        ;;
      3)
        MODE="target"
        while true; do
          echo -n "Enter target directory path: "
          read -r custom
          if [ -z "$custom" ]; then
            echo "Target cannot be empty." >&2
            continue
          fi
          TARGET="$custom"
          return
        done
        ;;
      4)
        echo "Install aborted by user." >&2
        exit 1
        ;;
      *)
        echo "Please enter 1, 2, 3, or 4."
        ;;
    esac
  done
}

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --global)
      MODE="global"
      TARGET="$HOME/.claude"
      shift
      ;;
    --target)
      if [[ $# -lt 2 ]]; then
        echo "Missing value for --target." >&2
        usage
      fi
      TARGET="$2"
      MODE="target"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    --allow-unsafe-target)
      ALLOW_UNSAFE_TARGET=1
      shift
      ;;
    --no-hypothesis-hook)
      NO_HYPOTHESIS_HOOK=1
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown option: $1"
      usage
      ;;
  esac
done

if [ -z "$MODE" ]; then
  prompt_install_mode
  if [ "$MODE" != "repo" ] && [ "$MODE" != "global" ] && [ "$MODE" != "target" ]; then
    MODE="repo"
  fi

  if [ -z "$TARGET" ]; then
    if [ "$MODE" = "repo" ]; then
      if git rev-parse --show-toplevel &>/dev/null; then
        TARGET="$(git rev-parse --show-toplevel)/.claude"
      else
        TARGET="$(pwd)/.claude"
      fi
    elif [ "$MODE" = "global" ]; then
      TARGET="$HOME/.claude"
    else
      echo "Missing target path in non-interactive mode." >&2
      usage
    fi
  fi
fi

if [ "$MODE" = "repo" ] || [ "$MODE" = "global" ] || [ "$MODE" = "target" ]; then
  build_allowlist
  TARGET="$(validate_target_root "$TARGET" "$MODE")"
else
  echo "Invalid mode '$MODE'." >&2
  usage
fi

if [ "$MODE" = "global" ]; then
  PROJECT_ROOT=""
else
  PROJECT_ROOT="$(dirname "$TARGET")"
fi
AGENTS_MODE_TARGET="$TARGET/.agents-mode.yaml"
LEGACY_AGENTS_MODE_TARGET="$TARGET/.agents-mode"

echo "=== Claude Code Installer ==="
echo "Source: $SOURCE"
echo "Target: $TARGET"
echo "agents-mode: $AGENTS_MODE_TARGET"
echo "Mode:   $MODE"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "Mode:   dry-run"
fi
echo

# Verify source
if [[ ! -d "$SOURCE/agents" ]]; then
  echo "FAIL: Source directory $SOURCE/agents not found."
  echo "Run this script from the Orchestrarium repo root."
  exit 1
fi
if [[ ! -f "$DEFAULT_AGENTS_MODE_SOURCE" ]]; then
  echo "FAIL: missing default agents-mode template at $DEFAULT_AGENTS_MODE_SOURCE" >&2
  exit 1
fi

if [[ ! -d "$TARGET" ]]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "[dry-run] would create target root: $TARGET"
  else
    mkdir -p "$TARGET"
  fi
fi

# Per-item install: only replace pack items, preserve user-added files
items_equal() {
  local src="$1" dst="$2"
  if [[ -d "$src" && -d "$dst" ]]; then
    diff -qr "$src" "$dst" >/dev/null
  elif [[ -f "$src" && -f "$dst" ]]; then
    cmp -s "$src" "$dst"
  else
    return 1
  fi
}

install_item() {
  local src="$1" dst="$2" label="${3:-$(basename "$2")}"
  if [[ -e "$dst" ]]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would replace $label"
    elif items_equal "$src" "$dst"; then
      echo "    OK  $label unchanged"
    else
      rm -rf "$dst"
      cp -r "$src" "$dst"
    fi
  else
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would install $label"
    else
      cp -r "$src" "$dst"
    fi
  fi
}

ensure_local_only_gitignore_entries() {
  local project_root="$1"
  local gitignore="$project_root/.gitignore"
  local entries=("/.reports/" "/.plans/" "/work-items/" "/.scratch/")
  local missing=()
  local declined_negation=()
  local declined_sentinel=()
  local declined_unverifiable=()
  local normalized=""

  if [[ -f "$gitignore" ]]; then
    normalized="$(sed -e '1s/^\xef\xbb\xbf//' -e 's/\r$//' -e 's/[[:space:]]*$//' "$gitignore")"
  fi

  local unresolved=()
  for entry in "${entries[@]}"; do
    local alternate="${entry#/}"
    local decline_marker="# orchestrarium:local-only-tier-declined:${entry}"
    if grep -Fxq "$entry" <<<"$normalized" || grep -Fxq "$alternate" <<<"$normalized"; then
      continue
    fi
    if grep -Fxq "$decline_marker" <<<"$normalized"; then
      declined_sentinel+=("$entry")
      continue
    fi
    unresolved+=("$entry")
  done

  if [[ ${#unresolved[@]} -gt 0 ]]; then
    # THE INVARIANT THIS BLOCK ENFORCES: the probe consults nothing outside
    # the throwaway repository and the file under test. Every mechanism
    # below -- clearing environment variables AND setting config values
    # explicitly -- exists only to make that invariant hold; when adding a
    # new git call here, check it against the invariant directly rather than
    # against the list of vectors found so far, because the list is
    # provably incomplete (three rounds have each found a member neither of
    # the prior rounds had named, and the git-documented environment-variable
    # list itself was consulted via empirical enumeration on this machine,
    # not a rendered man page -- treat it as thorough, not complete).
    #
    # Two DISTINCT classes of leak, needing two DIFFERENT mechanisms:
    #   1. Environment variables that redirect the probe onto a DIFFERENT
    #      repository or inject config directly (GIT_DIR, GIT_WORK_TREE,
    #      GIT_COMMON_DIR, ... GIT_CONFIG_COUNT below) -- closed by CLEARING
    #      them, since an absent variable cannot redirect anything.
    #   2. A resolution FALLBACK that fires precisely when a setting is
    #      UNSET -- core.excludesFile has no default VALUE, but git falls
    #      back to a default PATH ($XDG_CONFIG_HOME/git/ignore, else
    #      $HOME/.config/git/ignore) whenever core.excludesFile itself is
    #      unset. Pointing GIT_CONFIG_GLOBAL at a nonexistent file leaves
    #      core.excludesFile unset, which is exactly the condition that
    #      triggers this fallback -- so clearing GIT_CONFIG_GLOBAL/
    #      GIT_CONFIG_NOSYSTEM does NOT close it (confirmed this session on
    #      bash, pwsh 7, and Windows PowerShell 5.1: an ambient HOME or
    #      XDG_CONFIG_HOME pointing at a personal global-gitignore covering
    #      the tier still leaked in, SILENTLY, under the round-6 fix). This
    #      is plausibly the MOST LIKELY trigger of any vector found so far:
    #      `~/.config/git/ignore` is the standard personal global-gitignore
    #      location, and an operator who uses this pack across several
    #      repos and adds a tier to their own global ignore -- a natural
    #      thing to do -- would get silence on every project, forever, with
    #      no message. Closed by SETTING core.excludesFile EXPLICITLY on the
    #      throwaway repo (below, right after `git init`) rather than
    #      relying on it staying unset: an explicit value, even a
    #      nonexistent path, means the "unset" condition the fallback keys
    #      on never occurs, so no future default-path fallback can reopen
    #      this by a different name.
    #
    # GIT_DIR / GIT_WORK_TREE / GIT_COMMON_DIR (individually or paired) can
    # redirect a `-C <dir>`-targeted call onto a COMPLETELY DIFFERENT
    # repository -- but NOT identically: measured this session with
    # `git rev-parse --show-toplevel --git-dir` as well as `check-ignore`,
    # GIT_WORK_TREE alone redirects BOTH the working tree AND git-dir
    # discovery (so a WORKING-TREE-relative ignore source, e.g. a plain
    # `.gitignore`, leaks); GIT_DIR alone redirects ONLY git-dir discovery,
    # leaving the working tree in place (so a GIT-DIR-relative ignore
    # source, e.g. `$GIT_DIR/info/exclude`, leaks, while a `.gitignore` does
    # not) -- both are real leaks, just through different ignore-source
    # channels, and clearing both closes both regardless of which channel a
    # given operator's ambient state happens to use. GIT_ICASE_PATHSPECS /
    # GIT_LITERAL_PATHSPECS / GIT_NOGLOB_PATHSPECS / GIT_GLOB_PATHSPECS make
    # `check-ignore` itself fail outright ("pathspec magic not supported by
    # this command", exit 128, confirmed this session) -- not a silent
    # leak, since the writer's own exit-code handling below degrades that to
    # "could not be checked" rather than misreading it as ignored or not,
    # but it still leaves the tier unwritten with no way to recover except
    # by clearing the variable, so it is cleared alongside the rest.
    # GIT_CONFIG_COUNT (paired with GIT_CONFIG_KEY_n/GIT_CONFIG_VALUE_n)
    # injects arbitrary config -- including core.excludesFile -- directly
    # from the environment, bypassing GIT_CONFIG_NOSYSTEM/GIT_CONFIG_GLOBAL
    # entirely (confirmed this session; found by reading git's own
    # documented environment-variable list rather than extending piecemeal
    # from previously-named vectors, not named by anyone before that read).
    # A realistic trigger for any of the redirect/injection vars: the
    # installer running from inside a git hook, mid-rebase, or from a CI/IDE
    # wrapper that exports them. Cleared for the ENTIRE unresolved-tier
    # block (not just calls targeting the throwaway repo): the SAME vars
    # would equally corrupt the project_root-targeted
    # `config --local core.ignorecase` read below. None of these have a
    # legitimate reason to survive here -- this probe only ever needs a
    # fresh, self-contained repository at a path this function chose itself.
    local giprobe_repo_location_vars=(
      GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_NAMESPACE
      GIT_CEILING_DIRECTORIES GIT_DISCOVERY_ACROSS_FILESYSTEM
      GIT_INDEX_FILE GIT_OBJECT_DIRECTORY GIT_ALTERNATE_OBJECT_DIRECTORIES
      GIT_CONFIG_SYSTEM GIT_CONFIG_COUNT
      GIT_ICASE_PATHSPECS GIT_LITERAL_PATHSPECS GIT_NOGLOB_PATHSPECS GIT_GLOB_PATHSPECS
    )
    local giprobe_saved_env=()
    local giprobe_env_var
    for giprobe_env_var in "${giprobe_repo_location_vars[@]}"; do
      if [[ -v "$giprobe_env_var" ]]; then
        giprobe_saved_env+=("${giprobe_env_var}=${!giprobe_env_var}")
        unset "$giprobe_env_var"
      else
        giprobe_saved_env+=("$giprobe_env_var")
      fi
    done
    local giprobe_saved_config_nosystem="${GIT_CONFIG_NOSYSTEM-}"
    local giprobe_had_config_nosystem=0
    [[ -v GIT_CONFIG_NOSYSTEM ]] && giprobe_had_config_nosystem=1
    local giprobe_saved_config_global="${GIT_CONFIG_GLOBAL-}"
    local giprobe_had_config_global=0
    [[ -v GIT_CONFIG_GLOBAL ]] && giprobe_had_config_global=1

    local giprobe_root=""
    local giprobe_trap_installed=0
    local giprobe_prior_trap_line=""
    if command -v git >/dev/null 2>&1; then
      giprobe_root="$(mktemp -d 2>/dev/null || true)"
      if [[ -n "$giprobe_root" ]]; then
        # Chain onto whatever EXIT trap this script already has registered
        # (e.g. install-codex.sh's own temp-file cleanup, set BEFORE this
        # function runs) instead of silently replacing it, and cover an
        # interrupt/abort/hung git mid-probe, not just the normal-return
        # path -- confirmed this session (a real SIGTERM sent mid-probe
        # still removed the throwaway repo AND ran the pre-existing sibling
        # cleanup) that a plain `trap ... EXIT` here would otherwise both
        # leak this directory on interrupt AND drop that sibling cleanup.
        # `trap -p` prints a properly re-quoted single argument; only bash's
        # OWN quote removal (via `set --`) safely recovers the exact
        # original text -- manual sed-stripping of the outer quote
        # characters is NOT sufficient, since the embedded `'\''` escaping
        # only means what it means together with the outer quote pair.
        giprobe_prior_trap_line="$(trap -p EXIT)"
        if [[ -n "$giprobe_prior_trap_line" ]]; then
          eval "set -- ${giprobe_prior_trap_line#trap -- }"
          eval "_giprobe_prior_exit_fn() { $1
          }"
        else
          _giprobe_prior_exit_fn() { :; }
        fi
        trap "rm -rf '$giprobe_root' 2>/dev/null || true; _giprobe_prior_exit_fn" EXIT
        giprobe_trap_installed=1
        export GIT_CONFIG_NOSYSTEM=1
        export GIT_CONFIG_GLOBAL="${giprobe_root}.noconfig"
        # Neutralize the OPERATOR's ambient git environment for this
        # throwaway repo: GIT_CONFIG_NOSYSTEM plus a nonexistent
        # GIT_CONFIG_GLOBAL stop a global `core.excludesFile` from leaking
        # into the probe's verdict, and `--template=<nonexistent>` stops a
        # global `init.templateDir` from seeding `info/exclude` -- confirmed
        # this session that without this, an operator's own global
        # core.excludesFile covering the tier made the writer silently
        # decide "already ignored" for a PROJECT whose own .gitignore said
        # nothing about it, so a teammate cloning without that global config
        # would track the tier -- the exact publication-safety failure this
        # tier system exists to prevent. A nonexistent path is sufficient
        # for both (git treats it as "no such config"/"no such template",
        # not an error).
        if ! git init -q --template="${giprobe_root}.notemplate" "$giprobe_root" >/dev/null 2>&1; then
          rm -rf "$giprobe_root" 2>/dev/null || true
          giprobe_root=""
        fi
        if [[ -n "$giprobe_root" ]]; then
          # core.excludesFile has no default VALUE, but git falls back to a
          # default PATH ($XDG_CONFIG_HOME/git/ignore, else
          # $HOME/.config/git/ignore) whenever it is UNSET -- which is
          # exactly the state GIT_CONFIG_GLOBAL=<nonexistent> leaves it in.
          # Setting it EXPLICITLY here (a nonexistent path is enough) ends
          # the fallback permanently, rather than relying on it staying
          # unset -- confirmed this session that an ambient HOME or
          # XDG_CONFIG_HOME pointing at a real `~/.config/git/ignore`
          # covering the tier otherwise leaked in SILENTLY even with
          # GIT_CONFIG_NOSYSTEM/GIT_CONFIG_GLOBAL already neutralized.
          # This write's own failure must fail the probe CLOSED, the same
          # way the `git init` check right above already does: a probe that
          # cannot CONFIRM core.excludesFile is neutralized is not merely
          # unhardened, it is UNVERIFIABLE, and an unverifiable probe must
          # never be trusted to decide "already ignored" for real -- an
          # external review forced this failure and confirmed the ambient
          # leak survives silently without this check.
          if ! git -C "$giprobe_root" config core.excludesFile "${giprobe_root}.noexcludes" >/dev/null 2>&1; then
            rm -rf "$giprobe_root" 2>/dev/null || true
            giprobe_root=""
          fi
        fi
        if [[ -n "$giprobe_root" ]]; then
          # Mirror project_root's own EXPLICIT LOCAL core.ignorecase, when
          # set, onto the (now-neutralized) throwaway repo -- --local (never
          # plain `config`, which falls through to global/system config even
          # from inside a repo with no local override -- confirmed this
          # session) keeps this scoped to project_root's own repo only, and
          # never crashes when project_root is not yet a repo at all (exit
          # 128, swallowed by `|| true`, same as an unset override).
          local project_ignorecase
          project_ignorecase="$(git -C "$project_root" config --local --type=bool core.ignorecase 2>/dev/null || true)"
          if [[ "$project_ignorecase" == "true" || "$project_ignorecase" == "false" ]]; then
            git -C "$giprobe_root" config core.ignorecase "$project_ignorecase" >/dev/null 2>&1 || true
          fi
        fi
      fi
    fi

    # Every "!"-prefixed line's OWN stripped pattern, collected once (not
    # per tier) -- see the isolation-testing rationale in the comment above
    # this block.
    local giprobe_negation_patterns=()
    if [[ -n "$giprobe_root" ]]; then
      while IFS= read -r giprobe_line; do
        if [[ "$giprobe_line" == "!"* ]]; then
          giprobe_negation_patterns+=("${giprobe_line#!}")
        fi
      done <<<"$normalized"
    fi

    for entry in "${unresolved[@]}"; do
      local alt_noslash="${entry#/}"
      alt_noslash="${alt_noslash%/}"
      local probe="${alt_noslash}/.orchestrarium-probe"
      if [[ -z "$giprobe_root" ]]; then
        declined_unverifiable+=("$entry")
        continue
      fi
      local negation_matched=0
      for pattern in "${giprobe_negation_patterns[@]}"; do
        printf '%s\n' "$pattern" > "$giprobe_root/.gitignore"
        if git -C "$giprobe_root" check-ignore -q "$probe" 2>/dev/null; then
          negation_matched=1
          break
        fi
      done
      if [[ "$negation_matched" -eq 1 ]]; then
        declined_negation+=("$entry")
        continue
      fi
      printf '%s\n' "$normalized" > "$giprobe_root/.gitignore"
      local whole_file_rc=1
      if git -C "$giprobe_root" check-ignore -q "$probe" 2>/dev/null; then
        whole_file_rc=0
      else
        whole_file_rc=$?
      fi
      if [[ "$whole_file_rc" -eq 0 ]]; then
        continue
      elif [[ "$whole_file_rc" -eq 1 ]]; then
        missing+=("$entry")
      else
        declined_unverifiable+=("$entry")
      fi
    done

    if [[ -n "$giprobe_root" ]]; then
      rm -rf "$giprobe_root" 2>/dev/null || true
    fi
    if [[ "$giprobe_trap_installed" -eq 1 ]]; then
      if [[ -n "$giprobe_prior_trap_line" ]]; then
        eval "$giprobe_prior_trap_line"
      else
        trap - EXIT
      fi
    fi
    if [[ "$giprobe_had_config_nosystem" -eq 1 ]]; then
      export GIT_CONFIG_NOSYSTEM="$giprobe_saved_config_nosystem"
    else
      unset GIT_CONFIG_NOSYSTEM 2>/dev/null || true
    fi
    if [[ "$giprobe_had_config_global" -eq 1 ]]; then
      export GIT_CONFIG_GLOBAL="$giprobe_saved_config_global"
    else
      unset GIT_CONFIG_GLOBAL 2>/dev/null || true
    fi
    local giprobe_restore_entry
    for giprobe_restore_entry in "${giprobe_saved_env[@]}"; do
      if [[ "$giprobe_restore_entry" == *"="* ]]; then
        export "$giprobe_restore_entry"
      fi
    done
  fi

  for entry in "${declined_negation[@]}"; do
    echo "  .gitignore: '$entry' has a '!' negation on file -- leaving as-is (not re-appending; a later broader ignore pattern could still re-ignore this tree, which this writer does not check)"
  done
  for entry in "${declined_sentinel[@]}"; do
    echo "  .gitignore: '$entry' declined by operator (sentinel present) -- leaving as-is"
  done
  for entry in "${declined_unverifiable[@]}"; do
    echo "  .gitignore: '$entry' could not be checked against git (git unavailable or the check itself failed) -- leaving as-is rather than risk overriding an undetected '!' negation"
  done

  if [[ ${#missing[@]} -eq 0 ]]; then
    if [[ ${#declined_negation[@]} -eq 0 && ${#declined_sentinel[@]} -eq 0 && ${#declined_unverifiable[@]} -eq 0 ]]; then
      echo "  .gitignore: local-only entries already present"
    fi
    return
  fi

  echo "  Ensuring .gitignore ignores local-only task-memory paths..."
  if [ "$DRY_RUN" -eq 1 ]; then
    for entry in "${missing[@]}"; do
      if [[ -f "$gitignore" ]]; then
        echo "    [dry-run] would append '$entry' to $gitignore"
      else
        echo "    [dry-run] would create $gitignore with '$entry'"
      fi
    done
    return
  fi

  if [[ ! -f "$gitignore" ]]; then
    printf '%s\n' "${missing[@]}" > "$gitignore"
    for entry in "${missing[@]}"; do
      echo "    added '$entry' to $gitignore"
    done
    return
  fi

  for entry in "${missing[@]}"; do
    printf '\n%s\n' "$entry" >> "$gitignore"
    echo "    added '$entry' to $gitignore"
  done
}

ensure_credential_gitignore_entry() {
  # The pack's own credential file (.claude/SECRET.md — the invoke-claude-api
  # wrapper's repo-local lookup candidate) must never be trackable in a project
  # install. Kept separate from the local-only tier array above: that array is
  # the cross-installer tier set owned by shared/local-only-tiers.txt, while
  # this is a Claude-pack-specific credential path.
  local project_root="$1"
  local gitignore="$project_root/.gitignore"
  local secret_entry="/.claude/SECRET.md"
  local alternate="${secret_entry#/}"

  if [[ -f "$gitignore" ]] && { grep -Fxq "$secret_entry" "$gitignore" || grep -Fxq "$alternate" "$gitignore"; }; then
    echo "  .gitignore: credential entry already present"
    return
  fi

  echo "  Ensuring .gitignore ignores the pack credential file $secret_entry..."
  if [ "$DRY_RUN" -eq 1 ]; then
    if [[ -f "$gitignore" ]]; then
      echo "    [dry-run] would append '$secret_entry' to $gitignore"
    else
      echo "    [dry-run] would create $gitignore with '$secret_entry'"
    fi
    return
  fi

  if [[ ! -f "$gitignore" ]]; then
    printf '%s\n' "$secret_entry" > "$gitignore"
  else
    printf '\n%s\n' "$secret_entry" >> "$gitignore"
  fi
}

remove_dangling_symlink() {
  local path="$1"
  local label="$2"

  if [[ -L "$path" && ! -e "$path" ]]; then
    echo "  Removing dangling symlink for $label..."
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would remove dangling symlink $path"
    else
      rm -f "$path"
    fi
  fi
}

resolve_python_command() {
  if command -v python >/dev/null 2>&1; then
    printf '%s' "python"
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    printf '%s' "python3"
    return 0
  fi
  return 1
}

sync_agents_mode_file() {
  local template="$1" dst="$2" label="$3"
  local normalizer="$REPO_DIR/scripts/normalize-agents-mode.py"
  local python_cmd=""

  remove_dangling_symlink "$dst" "$label"
  python_cmd="$(resolve_python_command || true)"

  if [[ -n "$python_cmd" && -f "$normalizer" ]]; then
    if [[ -f "$dst" ]]; then
      echo "  Normalizing existing $label to current canonical format..."
    else
      echo "  Installing canonical $label..."
    fi

    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would normalize $dst"
    else
      "$python_cmd" "$normalizer" --template "$template" --target "$dst" --provider shared
    fi
    return
  fi

  if [[ -f "$dst" ]]; then
    echo "FAIL: python or python3 is required to normalize existing $label at $dst" >&2
    exit 1
  fi

  echo "  Installing canonical $label..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "    [dry-run] would create $dst"
  else
    cp "$template" "$dst"
  fi
}

migrate_legacy_agents_mode_file() {
  local legacy="$1" dst="$2" label="$3"

  remove_dangling_symlink "$legacy" "legacy $label"
  remove_dangling_symlink "$dst" "$label"

  if [[ -f "$dst" ]]; then
    if [[ -f "$legacy" ]]; then
      echo "  Canonical $label already exists; leaving legacy file untouched: $legacy"
    fi
    return
  fi

  if [[ ! -f "$legacy" ]]; then
    return
  fi

  echo "  Migrating legacy $label to $dst..."
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "    [dry-run] would move $legacy -> $dst"
  else
    mv "$legacy" "$dst"
  fi
}

collect_preserved_claude_imports() {
  local file="$1"
  awk '
    BEGIN { started=0 }
    /^@AGENTS\.md$|^# Claude Code Pack$|^# Claudestrator$/ { started=1 }
    started==1 {
      if ($0 ~ /^@/) {
        if ($0 != "@AGENTS.md" && !seen[$0]++) print $0
        next
      }
      if ($0 ~ /^[[:space:]]*$/) next
      exit
    }
  ' "$file"
}

write_merged_claude_md() {
  local existing="$1"
  local src="$2"
  local output="$3"
  local pack_start="$4"
  local imports_tmp tail_tmp

  imports_tmp="$(mktemp)"
  tail_tmp="$(mktemp)"
  collect_preserved_claude_imports "$existing" > "$imports_tmp"

  : > "$output"
  if [ "$pack_start" -gt 1 ]; then
    head -n $((pack_start - 1)) "$existing" >> "$output"
  fi

  if head -n 1 "$src" | grep -qx "@AGENTS.md"; then
    printf '%s\n' "@AGENTS.md" >> "$output"
    if [ -s "$imports_tmp" ]; then
      cat "$imports_tmp" >> "$output"
    fi
    awk 'NR==1 { next } { if (!started && $0 ~ /^[[:space:]]*$/) next; started=1; print }' "$src" > "$tail_tmp"
    if [ -s "$tail_tmp" ]; then
      printf '\n' >> "$output"
      cat "$tail_tmp" >> "$output"
    fi
  else
    cat "$src" >> "$output"
  fi

  rm -f "$imports_tmp" "$tail_tmp"
}

# Count existing items and confirm reinstall
if [ "$FORCE" -ne 1 ] && [ "$DRY_RUN" -ne 1 ] && [ -t 0 ]; then
  existing_total=0
  pack_total=0
  for dir in "${DIRS[@]}"; do
    dst="$TARGET/$dir"
    src="$SOURCE/$dir"
    if [[ -d "$dst" ]]; then
      for f in "$dst"/*; do [[ -e "$f" ]] && existing_total=$((existing_total + 1)); done
    fi
    for f in "$src"/*; do [[ -e "$f" ]] && pack_total=$((pack_total + 1)); done
  done
  if [ "$existing_total" -gt 0 ]; then
    user_count=$((existing_total - pack_total))
    if [ "$user_count" -lt 0 ]; then user_count=0; fi
    echo ""
    echo "  Reinstall will replace $pack_total pack items. $user_count user item(s) will be preserved."
    while true; do
      read -r -p "  Proceed? [y/N] " answer
      case "${answer,,}" in
        y|yes) break ;;
        n|no|"") echo "Install cancelled by user." >&2; exit 1 ;;
        *) echo "  Please answer y or n." ;;
      esac
    done
  fi
fi

for dir in "${DIRS[@]}"; do
  src="$SOURCE/$dir"
  dst="$TARGET/$dir"

  echo "  Installing $dir/ (per-item, preserving user-added files)..."
  if [[ ! -d "$dst" ]]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would create $dst"
    else
      mkdir -p "$dst"
    fi
  fi

  # Copy subdirectories (e.g., agents/contracts/, agents/team-templates/, agents/scripts/)
  for sub in "$src"/*/; do
    [[ -d "$sub" ]] || continue
    sub_name="$(basename "$sub")"
    install_item "$sub" "$dst/$sub_name" "$dir/$sub_name/"
  done

  # Copy individual files (e.g., agents/*.md, commands/*.md)
  pack_items=()
  for item in "$src"/*; do
    [[ -f "$item" ]] || continue
    item_name="$(basename "$item")"
    pack_items+=("$item_name")
    install_item "$item" "$dst/$item_name" "$dir/$item_name"
  done

  # Report preserved user files
  for existing in "$dst"/*; do
    [[ -f "$existing" ]] || continue
    existing_name="$(basename "$existing")"
    is_pack=0
    for pi in "${pack_items[@]}"; do
      if [[ "$pi" == "$existing_name" ]]; then is_pack=1; break; fi
    done
    if [[ $is_pack -eq 0 ]]; then
      # Check it's not in a subdirectory (those were fully replaced)
      echo "  Preserved user file: $dir/$existing_name"
    fi
  done

  # Reclaim the reserved `agents-` pack namespace: a target commands/agents-*.md
  # file or a skills/agents-*/ dir that is NOT in the current pack is a stale
  # pack-owned artifact from a prior install (a renamed/removed flow, or a
  # generated agents-* skill left by an old standalone-branch install — the
  # monorepo path never ships those; commands/ is the sole monorepo flow surface).
  # Remove it. Non-namespaced user files are preserved (the loop above only
  # touches `agents-`). The prefix is the ownership marker (repo Key invariant
  # every agents-* command/flow ships under this prefix) so there is no manifest to sync.
  if [[ "$dir" == "commands" || "$dir" == "skills" ]]; then
    for existing in "$dst"/agents-*; do
      [[ -e "$existing" ]] || continue
      existing_name="$(basename "$existing")"
      # is this stale name still shipped by the current pack?
      if [[ -e "$src/$existing_name" ]]; then continue; fi
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "    [dry-run] would reclaim stale pack namespace: $dir/$existing_name"
      else
        rm -rf "$existing"
        echo "  Reclaimed stale pack item: $dir/$existing_name"
      fi
    done
  fi
done

runtime_ledger_scripts=(
  agent-run-ledger.py
  agent-run-ledger.ps1
  agent-run-ledger.sh
  check-work-items-state.py
  check-work-items-state.ps1
  check-work-items-state.sh
  validate-work-item-state.py
  validate-work-item-state.ps1
  validate-work-item-state.sh
)
echo "  Installing work-item ledger helper scripts..."
claude_scripts_target="$TARGET/agents/scripts"
if [[ ! -d "$claude_scripts_target" ]]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "    [dry-run] would create $claude_scripts_target"
  else
    mkdir -p "$claude_scripts_target"
  fi
fi
for script_name in "${runtime_ledger_scripts[@]}"; do
  script_source="$REPO_DIR/scripts/$script_name"
  script_target="$claude_scripts_target/$script_name"
  if [[ ! -f "$script_source" ]]; then
    echo "FAIL: Missing runtime helper source $script_source" >&2
    exit 1
  fi
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "    [dry-run] would copy $script_source -> $script_target"
  else
    cp "$script_source" "$script_target"
  fi
done

# CLAUDE.md: merge or create
src_md="$SOURCE/CLAUDE.md"
dst_md="$TARGET/CLAUDE.md"

remove_dangling_symlink "$dst_md" "CLAUDE.md"

if [[ -f "$dst_md" ]]; then
  if grep -q "^@AGENTS.md" "$dst_md" 2>/dev/null || grep -q "^# Claudestrator" "$dst_md" 2>/dev/null || grep -q "^# Claude Code Pack" "$dst_md" 2>/dev/null; then
    # Existing Claude Code or legacy Claudestrator install — find where user content ends and pack content begins.
    # User content (## Project policies, custom rules) lives AFTER the pack section.
    # Pack section starts at @AGENTS.md, # Claude Code Pack, or legacy # Claudestrator (whichever comes first).
    pack_start=$(grep -n "^@AGENTS.md\|^# Claude Code Pack\|^# Claudestrator" "$dst_md" | head -1 | cut -d: -f1)
    total_lines=$(wc -l < "$dst_md")
    # Everything before pack_start is user content (if any)
    head_lines=$((pack_start - 1))
    echo "  CLAUDE.md: replacing Claude Code pack section..."
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would replace Claude Code pack section in CLAUDE.md"
    else
      write_merged_claude_md "$dst_md" "$src_md" "$dst_md.tmp" "$pack_start"
      mv "$dst_md.tmp" "$dst_md"
    fi
  elif grep -q "## Delegation rule" "$dst_md" 2>/dev/null; then
    echo "  CLAUDE.md: full replace (has delegation rule but no recognized pack header)..."
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would replace CLAUDE.md"
    else
      cp "$src_md" "$dst_md"
    fi
  else
    echo "  CLAUDE.md: prepending Claude Code pack content..."
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would prepend CLAUDE.md"
    else
      existing="$(cat "$dst_md")"
      new="$(cat "$src_md")"
      printf '%s\n%s' "$new" "$existing" > "$dst_md"
    fi
  fi
else
  echo "  Creating CLAUDE.md..."
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "    [dry-run] would create CLAUDE.md"
  else
    cp "$src_md" "$dst_md"
  fi
fi

# AGENTS.md: copy or replace shared governance
src_agents="$REPO_DIR/shared/AGENTS.shared.md"
dst_agents="$TARGET/AGENTS.md"

remove_dangling_symlink "$dst_agents" "AGENTS.md"

if [[ -f "$src_agents" ]]; then
  if [[ -f "$dst_agents" ]]; then
    if grep -q "^# Shared Governance" "$dst_agents" 2>/dev/null; then
      echo "  AGENTS.md: replacing shared governance..."
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "    [dry-run] would replace AGENTS.md"
      else
        cp "$src_agents" "$dst_agents"
      fi
    else
      echo "  AGENTS.md: prepending shared governance..."
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "    [dry-run] would prepend AGENTS.md"
      else
        existing="$(cat "$dst_agents")"
        new="$(cat "$src_agents")"
        printf '%s\n%s' "$new" "$existing" > "$dst_agents"
      fi
    fi
  else
    echo "  Creating AGENTS.md..."
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would create AGENTS.md"
    else
      cp "$src_agents" "$dst_agents"
    fi
  fi
fi

if [ "$MODE" != "global" ]; then
  ensure_local_only_gitignore_entries "$PROJECT_ROOT"
  ensure_credential_gitignore_entry "$PROJECT_ROOT"
fi

migrate_legacy_agents_mode_file "$LEGACY_AGENTS_MODE_TARGET" "$AGENTS_MODE_TARGET" ".agents-mode.yaml"
sync_agents_mode_file "$DEFAULT_AGENTS_MODE_SOURCE" "$AGENTS_MODE_TARGET" ".agents-mode.yaml"

# Shared cross-pack global .agents-mode.yaml lives at $HOME/.agents-mode.yaml
# (alongside ~/.claude.json). It is the lowest-precedence fallback layer below
# pack-local globals and project-local overlays. The sync function is
# normalize-not-overwrite, so calling it from both pack installers is idempotent.
# Only created/normalized during default global installs (--global mode).
if [ "$MODE" = "global" ]; then
  SHARED_GLOBAL_AGENTS_MODE="$HOME/.agents-mode.yaml"
  sync_agents_mode_file "$DEFAULT_AGENTS_MODE_SOURCE" "$SHARED_GLOBAL_AGENTS_MODE" "shared global ~/.agents-mode.yaml"
fi

# Install structural hooks by merging them into the
# user's settings.json idempotently. Preserves all other user keys and other
# hooks. Opt out with --no-hypothesis-hook or ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1.
# Fails closed (non-zero exit) if Python is required but unavailable, matching
# the agents-mode sync contract — silent skip would leave the user thinking
# the hook is active when it is not.
if [ "$NO_HYPOTHESIS_HOOK" -ne 1 ] && [ "$DRY_RUN" -ne 1 ]; then
  hook_installer="$REPO_DIR/scripts/install-hypothesis-hook.py"
  if [ ! -f "$hook_installer" ]; then
    echo "WARN: hypothesis-hook installer not found at $hook_installer; skipping hook install" >&2
  else
    python_cmd="$(resolve_python_command || true)"
    if [ -z "$python_cmd" ]; then
      echo "FAIL: python or python3 is required to auto-install the structural hooks" >&2
      echo "      Rerun with --no-hypothesis-hook to skip, or install Python and re-run." >&2
      exit 1
    fi
    settings_target="$TARGET/settings.json"
    # OS-aware host detection: on Windows under Git Bash / MSYS / Cygwin we
    # emit the native PowerShell exec form referencing .ps1; on POSIX we emit
    # the bash exec form referencing .sh. The Python helper builds the right
    # entry shape from --host-os.
    case "$(uname -s 2>/dev/null)" in
      MINGW*|MSYS*|CYGWIN*)
        hook_host_os="windows"
        bugfix_script_target="$TARGET/agents/scripts/check-bugfix-discipline.ps1"
        git_push_gate_script_target="$TARGET/agents/scripts/check-git-push-gate.ps1"
        stop_script_target="$TARGET/agents/scripts/check-passive-polling-stop.ps1"
        wi_archival_script_target="$TARGET/agents/scripts/check-work-items-archival-stop.ps1"
        machine_path_script_target="$TARGET/agents/hooks/check-machine-local-path.ps1"
        notrash_script_target="$TARGET/agents/hooks/check-no-trash-in-repo.ps1"
        stale_relation_script_target="$TARGET/agents/hooks/check-stale-relation-residue.ps1"
        repository_orientation_script_target="$TARGET/agents/hooks/check-repository-orientation.ps1"
        mcp_momentum_script_target="$TARGET/agents/hooks/check-mcp-momentum.ps1"
        typed_routing_script_target="$TARGET/agents/hooks/check-typed-routing.ps1"
        reminder_script_target="$TARGET/agents/scripts/mcp-usage-reminder.ps1"
        agents_mode_reminder_script_target="$TARGET/agents/scripts/agents-mode-reminder.ps1"
        scratch_valuables_script_target="$TARGET/agents/scripts/check-scratch-valuables.ps1"
        turn_anchor_reminder_script_target="$TARGET/agents/scripts/turn-anchor-reminder.ps1"
        ;;
      *)
        hook_host_os="posix"
        bugfix_script_target="$TARGET/agents/scripts/check-bugfix-discipline.sh"
        git_push_gate_script_target="$TARGET/agents/scripts/check-git-push-gate.sh"
        stop_script_target="$TARGET/agents/scripts/check-passive-polling-stop.sh"
        wi_archival_script_target="$TARGET/agents/scripts/check-work-items-archival-stop.sh"
        machine_path_script_target="$TARGET/agents/hooks/check-machine-local-path.sh"
        notrash_script_target="$TARGET/agents/hooks/check-no-trash-in-repo.sh"
        stale_relation_script_target="$TARGET/agents/hooks/check-stale-relation-residue.sh"
        repository_orientation_script_target="$TARGET/agents/hooks/check-repository-orientation.sh"
        mcp_momentum_script_target="$TARGET/agents/hooks/check-mcp-momentum.sh"
        typed_routing_script_target="$TARGET/agents/hooks/check-typed-routing.sh"
        reminder_script_target="$TARGET/agents/scripts/mcp-usage-reminder.sh"
        agents_mode_reminder_script_target="$TARGET/agents/scripts/agents-mode-reminder.sh"
        scratch_valuables_script_target="$TARGET/agents/scripts/check-scratch-valuables.sh"
        turn_anchor_reminder_script_target="$TARGET/agents/scripts/turn-anchor-reminder.sh"
        ;;
    esac
    echo "  Installing bugfix-discipline PreToolUse hook (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --script-path "$bugfix_script_target"
    echo "  Installing git-push publication-gate PreToolUse hook (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --script-marker check-git-push-gate \
      --tool-matcher "Bash|PowerShell" \
      --script-path "$git_push_gate_script_target"
    echo "  Installing passive-polling Stop hook (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --hook-event Stop \
      --script-marker check-passive-polling-stop \
      --script-path "$stop_script_target"
    echo "  Installing work-items-archival Stop hook (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --hook-event Stop \
      --script-marker check-work-items-archival-stop \
      --script-path "$wi_archival_script_target"
    echo "  Installing machine-local-path PreToolUse hook [AUDIT] (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --script-marker check-machine-local-path \
      --script-path "$machine_path_script_target"
    echo "  Installing no-trash-in-repo PreToolUse hook [AUDIT] (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --script-marker check-no-trash-in-repo \
      --tool-matcher "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell" \
      --script-path "$notrash_script_target"
    echo "  Installing stale-relation-residue PreToolUse hook [AUDIT] (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --script-marker check-stale-relation-residue \
      --script-path "$stale_relation_script_target"
    echo "  Installing repository-orientation PreToolUse hook [AUDIT] (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --script-marker check-repository-orientation \
      --tool-matcher "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell|shell_command|exec_command" \
      --script-path "$repository_orientation_script_target"
    echo "  Installing mcp-momentum PreToolUse hook [AUDIT] (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --script-marker check-mcp-momentum \
      --tool-matcher "Grep|Bash" \
      --script-path "$mcp_momentum_script_target"
    echo "  Installing typed-routing PreToolUse hook [AUDIT] (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --script-marker check-typed-routing \
      --tool-matcher "Agent" \
      --script-path "$typed_routing_script_target"
    echo "  Installing MCP-usage-reminder SessionStart hook (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --hook-event SessionStart \
      --script-marker mcp-usage-reminder \
      --script-path "$reminder_script_target"
    echo "  Installing delegation-posture (agents-mode) SessionStart hook (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --hook-event SessionStart \
      --script-marker agents-mode-reminder \
      --script-path "$agents_mode_reminder_script_target"
    echo "  Installing scratch-valuables watchdog SessionStart hook (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --hook-event SessionStart \
      --script-marker check-scratch-valuables \
      --script-path "$scratch_valuables_script_target"
    echo "  Installing turn-anchor-reminder UserPromptSubmit hook (host-os=$hook_host_os)..."
    "$python_cmd" "$hook_installer" \
      --target "$settings_target" \
      --platform claude \
      --host-os "$hook_host_os" \
      --hook-event UserPromptSubmit \
      --script-marker turn-anchor-reminder \
      --script-path "$turn_anchor_reminder_script_target"
  fi
fi

if [ "$DRY_RUN" -eq 1 ]; then
  echo ""
  echo "RESULT: DRY-RUN complete (no files modified)."
  exit 0
fi

# Verification — explicit required-file manifest check

echo ""
echo "=== Verification ==="
errors=0

check_file() {
  local path="$1"
  local label="$2"

  if [[ -f "$path" ]]; then
    echo "  OK  $label"
  else
    echo "  FAIL  $label"
    errors=$((errors+1))
  fi
}

check_installed_manifest() {
  local source_dir="$1"
  while IFS= read -r -d '' source_file; do
    local rel_path="${source_file#$SOURCE/}"
    check_file "$TARGET/$rel_path" "$rel_path"
  done < <(find "$source_dir" -type f -print0)
}

for dir in "${DIRS[@]}"; do
  check_installed_manifest "$SOURCE/$dir"
done

check_file "$TARGET/agents/contracts/operating-model.md" "agents/contracts/operating-model.md"
check_file "$TARGET/agents/contracts/subagent-contracts.md" "agents/contracts/subagent-contracts.md"
check_file "$TARGET/agents/contracts/policies-catalog.md" "agents/contracts/policies-catalog.md"
for script_name in "${runtime_ledger_scripts[@]}"; do
  check_file "$TARGET/agents/scripts/$script_name" "agents/scripts/$script_name"
done
check_file "$AGENTS_MODE_TARGET" ".agents-mode.yaml"

# Check CLAUDE.md (Claude-specific sections)
if [[ -f "$dst_md" ]]; then
  line_count=$(wc -l < "$dst_md")
  echo "  OK  CLAUDE.md ($line_count lines)"
  for section in "## Delegation rule" "## Publication safety"; do
    if grep -q "$section" "$dst_md"; then
      echo "  OK  CLAUDE.md has '$section'"
    else
      echo "  FAIL  CLAUDE.md missing '$section'"
      errors=$((errors+1))
    fi
  done
  # Check @AGENTS.md import
  if grep -q "@AGENTS.md" "$dst_md"; then
    echo "  OK  CLAUDE.md imports @AGENTS.md"
  else
    echo "  FAIL  CLAUDE.md missing @AGENTS.md import"
    errors=$((errors+1))
  fi
else
  echo "  FAIL  CLAUDE.md missing"
  errors=$((errors+1))
fi

# Check AGENTS.md (shared governance sections)
if [[ -f "$dst_agents" ]]; then
  line_count=$(wc -l < "$dst_agents")
  echo "  OK  AGENTS.md ($line_count lines)"
  for section in "## Role index" "## Engineering hygiene" "## Core delegation principles" "## Publication safety"; do
    if grep -q "$section" "$dst_agents"; then
      echo "  OK  AGENTS.md has '$section'"
    else
      echo "  FAIL  AGENTS.md missing '$section'"
      errors=$((errors+1))
    fi
  done
else
  echo "  FAIL  AGENTS.md missing"
  errors=$((errors+1))
fi

echo ""
if [[ $errors -gt 0 ]]; then
  echo "RESULT: FAIL ($errors errors)"
  exit 1
else
  echo "RESULT: OK — Claude Code pack installed to $TARGET"
  echo ""
  echo "Next: restart Claude, then run /agents-init-project to review/update project policies and the installed default .claude/.agents-mode.yaml."
fi

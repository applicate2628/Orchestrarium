#!/usr/bin/env bash
# Install Codex pack.
# Usage:
#   bash scripts/install-codex.sh                  install into current repo (.agents/ + AGENTS.md)
#   bash scripts/install-codex.sh --global         install into ~/.codex/
#   bash scripts/install-codex.sh --target DIR     install into DIR as a project (.agents/ + AGENTS.md)
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$REPO_DIR/src.codex"
AGENTS_SOURCE="$SOURCE/agents"
SHARED_AGENTS_MODE_SOURCE="$REPO_DIR/shared/agents-mode.defaults.yaml"
CODEX_PACK_BEGIN_MARKER='<!-- BEGIN ORCHESTRARIUM CODEX PACK -->'
CODEX_PACK_END_MARKER='<!-- END ORCHESTRARIUM CODEX PACK -->'

# Directories to install (order doesn't matter)
DIRS=(skills)
FORCE=0
DRY_RUN=0
ALLOW_UNSAFE_TARGET=0
NO_HYPOTHESIS_HOOK=0
HOOK_RUNTIME="python"
MODE=""
TARGET=""
hook_verification_exclusions=()

usage() {
  echo "Usage:"
  echo "  bash scripts/install-codex.sh                          Install into current repo (.agents/ + AGENTS.md)"
  echo "  bash scripts/install-codex.sh --global                 Install into ~/.codex/"
  echo "  bash scripts/install-codex.sh --target DIR             Install into DIR as a project (.agents/ + AGENTS.md)"
  echo "  bash scripts/install-codex.sh --force                  Skip deletion prompts"
  echo "  bash scripts/install-codex.sh --dry-run                Print planned actions without changing files"
  echo "  bash scripts/install-codex.sh --allow-unsafe-target    Override allowlist for custom target path"
  echo "  bash scripts/install-codex.sh --hook-runtime PROFILE   wrapper|python|native (default: python)"
  echo "  bash scripts/install-codex.sh --help                   Show help"
  exit 1
}

canonical_path() {
  local input_path="$1"
  local expanded="${input_path/#\~/$HOME}"
  local converter=""

  if [ -z "$expanded" ]; then
    echo ""
    return 1
  fi

  if [[ "$expanded" =~ ^[A-Za-z]:[\\/].* ]]; then
    if command -v cygpath >/dev/null 2>&1; then
      converter="cygpath"
    elif command -v wslpath >/dev/null 2>&1; then
      converter="wslpath"
    fi

    if [ -n "$converter" ]; then
      expanded="$("$converter" -u "$expanded")"
    else
      expanded="${expanded//\\//}"
    fi
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

  if [ "$(basename "$normalized")" = ".codex" ]; then
    printf "%s" "$normalized"
  else
    printf "%s/.codex" "$normalized"
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

  if [ "$(basename "$target_lower")" != ".codex" ]; then
    echo "FAIL: target '$target' must resolve to .codex directory" >&2
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

  if [ -n "${CODEX_INSTALL_ALLOWLIST:-}" ]; then
    IFS=',' read -r -a ALLOWLIST_EXTRA <<< "$CODEX_INSTALL_ALLOWLIST"
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

# Per-skill install preserves user-added skills — no destructive directory wipe needed.

prompt_install_mode() {
  if [ ! -t 0 ]; then
    echo "FAIL: No install target specified and not running interactively." >&2
    echo "Use: bash scripts/install-codex.sh --global  or  bash scripts/install-codex.sh --target <path>" >&2
    exit 1
  fi

  while true; do
    echo "Select installation target:"
    echo "  1) Local repo (.agents/skills + root AGENTS.md)"
    echo "  2) Global (~/.codex/)"
    echo "  3) Custom project directory (.agents/skills + root AGENTS.md)"
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
        TARGET="$HOME/.codex"
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
      TARGET="$HOME/.codex"
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
    --hook-runtime)
      if [[ $# -lt 2 ]] || [[ "$2" != "wrapper" && "$2" != "python" && "$2" != "native" ]]; then
        echo "FAIL: --hook-runtime requires wrapper, python, or native." >&2
        exit 1
      fi
      HOOK_RUNTIME="$2"
      shift 2
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
        TARGET="$(git rev-parse --show-toplevel)/.codex"
      else
        TARGET="$(pwd)/.codex"
      fi
    elif [ "$MODE" = "global" ]; then
      TARGET="$HOME/.codex"
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

# Derive per-mode target paths.
# Global: everything goes into ~/.codex/ (mirrors src.codex/).
# Repo/target: skills go into .agents/skills/,
#              AGENTS.md merges into project root AGENTS.md.
if [ "$MODE" = "global" ]; then
  AGENTS_ROOT="$TARGET"
  SKILLS_TARGET="$TARGET/skills"
  AGENT_OVERRIDES_TARGET="$TARGET/agents"
  MD_TARGET="$TARGET/AGENTS.md"
else
  # Repo-level: TARGET is <root>/.codex but skills go into <root>/.agents/
  PROJECT_ROOT="$(dirname "$TARGET")"
  AGENTS_ROOT="$PROJECT_ROOT/.agents"
  SKILLS_TARGET="$AGENTS_ROOT/skills"
  AGENT_OVERRIDES_TARGET="$TARGET/agents"
  MD_TARGET="$PROJECT_ROOT/AGENTS.md"
fi
AGENTS_MODE_TARGET="$AGENTS_ROOT/.agents-mode.yaml"
LEGACY_AGENTS_MODE_TARGET="$AGENTS_ROOT/.agents-mode"

echo "=== Codex Installer ==="
echo "Source: $SOURCE"
echo "Skills target: $SKILLS_TARGET"
echo "Built-in agent overrides: $AGENT_OVERRIDES_TARGET"
echo "AGENTS.md target: $MD_TARGET"
echo "agents-mode: $AGENTS_MODE_TARGET"
echo "Mode:   $MODE"
if [ "$DRY_RUN" -eq 1 ]; then
  echo "Mode:   dry-run"
fi
echo

# Verify source
if [[ ! -d "$SOURCE/skills" ]]; then
  echo "FAIL: Source directory $SOURCE/skills not found."
  echo "Run this script from the Orchestrarium repo root."
  exit 1
fi
if [[ ! -d "$AGENTS_SOURCE" ]]; then
  echo "FAIL: Source directory $AGENTS_SOURCE not found."
  echo "Run this script from the Orchestrarium repo root."
  exit 1
fi
if [[ ! -f "$SHARED_AGENTS_MODE_SOURCE" ]]; then
  echo "FAIL: missing shared agents-mode template at $SHARED_AGENTS_MODE_SOURCE" >&2
  exit 1
fi

# Create target parent directories as needed
for tdir in "$SKILLS_TARGET" "$AGENT_OVERRIDES_TARGET"; do
  parent="$(dirname "$tdir")"
  if [[ ! -d "$parent" ]]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "[dry-run] would create: $parent"
    else
      mkdir -p "$parent"
    fi
  fi
done

# Per-skill install: only replace pack skills, preserve user-added skills
install_skill() {
  local src="$1" dst="$2" label="$3"
  if [[ -d "$dst" ]]; then
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would replace $label"
    elif diff -qr "$src" "$dst" >/dev/null; then
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

normalize_codex_agent_override_content() {
  sed -E 's/\r$//; s/^model[[:space:]]*=[[:space:]]*"[^"]*"$/model = "<model>"/'
}

normalized_codex_agent_override_file() {
  local path="$1"
  normalize_codex_agent_override_content < "$path"
}

legacy_codex_agent_override_template() {
  local name="$1"
  case "$name" in
    default.toml)
      cat <<'EOF'
name = "default"
description = "General-purpose fallback agent."
model = "<model>"
model_reasoning_effort = "xhigh"
developer_instructions = """
General-purpose fallback agent.
Inherit the parent session's task context and focus on the assigned subtask.
Stay within the requested scope and return a concise, usable result.
"""
EOF
      ;;
    worker.toml)
      cat <<'EOF'
name = "worker"
description = "Execution-focused agent for implementation and fixes."
model = "<model>"
model_reasoning_effort = "xhigh"
developer_instructions = """
Execution-focused agent for implementation and fixes.
Carry out the assigned implementation task directly, stay within scope, and avoid redesign unless the parent explicitly asks for it.
Return concrete progress and outcomes for the requested slice.
"""
EOF
      ;;
    explorer.toml)
      cat <<'EOF'
name = "explorer"
description = "Read-heavy codebase exploration agent."
model = "<model>"
model_reasoning_effort = "xhigh"
developer_instructions = """
Read-heavy codebase exploration agent.
Stay in exploration mode, gather evidence efficiently, and return factual findings with clear pointers.
Do not drift into implementation unless the parent explicitly asks for it.
"""
EOF
      ;;
    *)
      return 1
      ;;
  esac
}

is_pack_owned_codex_agent_override() {
  local src="$1" dst="$2" name="$3"
  local target_norm source_norm legacy_norm

  target_norm="$(normalized_codex_agent_override_file "$dst")"
  source_norm="$(normalized_codex_agent_override_file "$src")"
  if [[ "$target_norm" == "$source_norm" ]]; then
    return 0
  fi

  legacy_norm="$(legacy_codex_agent_override_template "$name" || true)"
  if [[ -n "$legacy_norm" && "$target_norm" == "$legacy_norm" ]]; then
    return 0
  fi

  return 1
}

ensure_codex_agent_override_file() {
  local src="$1" dst="$2" label="$3"
  local name
  name="$(basename "$src")"

  remove_dangling_symlink "$dst" "$label"

  if [[ -f "$dst" ]]; then
    if is_pack_owned_codex_agent_override "$src" "$dst" "$name"; then
      if cmp -s "$src" "$dst"; then
        echo "  OK  $label unchanged"
      else
        echo "  Refreshing stale pack-owned $label..."
        if [ "$DRY_RUN" -eq 1 ]; then
          echo "    [dry-run] would replace $dst"
        else
          cp "$src" "$dst"
        fi
      fi
    else
      echo "  Preserving existing custom $label..."
    fi
    return
  fi

  echo "  Installing default $label..."
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "    [dry-run] would create $dst"
  else
    cp "$src" "$dst"
  fi
}

write_codex_default_agents_mode_file() {
  local template="$1" dst="$2"
  cat "$template" > "$dst"
  if ! grep -q '^externalClaudeProfile:' "$dst"; then
    printf '\nexternalClaudeProfile: opus-xhigh  # allowed: sonnet-high | opus-xhigh | opus-max | fable-xhigh; default: opus-xhigh\n' >> "$dst"
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

sync_agents_mode_file() {
  local template="$1" dst="$2" label="$3" provider="$4"
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
      "$python_cmd" "$normalizer" --template "$template" --target "$dst" --provider "$provider"
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
  elif [[ "$provider" == "codex" ]]; then
    write_codex_default_agents_mode_file "$template" "$dst"
  else
    cp "$template" "$dst"
  fi
}

find_codex_pack_start_line() {
  local file="$1"
  local marker_line
  marker_line="$(grep -n "^$CODEX_PACK_BEGIN_MARKER$" "$file" 2>/dev/null | head -1 | cut -d: -f1 || true)"
  if [[ -n "$marker_line" ]]; then
    printf "%s" "$marker_line"
    return
  fi
  grep -n "^# Shared Governance$\|^# Codex Platform Rules$\|^# Default Delegation Rule$" "$file" 2>/dev/null | head -1 | cut -d: -f1
}

find_codex_pack_end_line() {
  local existing="$1"
  local src="$2"
  local pack_start="$3"
  local footer

  if awk -v start="$pack_start" -v marker="$CODEX_PACK_END_MARKER" '
    NR < start { next }
    $0 == marker { print NR; found=1; exit }
    END { exit(found ? 0 : 1) }
  ' "$existing"; then
    return
  fi

  if awk -v start="$pack_start" '
    NR <= start { next }
    $0 == "## Project policies" { print NR - 1; found=1; exit }
    END { exit(found ? 0 : 1) }
  ' "$existing"; then
    return
  fi

  footer="$(awk 'NF { line=$0 } END { print line }' "$src")"

  if [[ -n "$footer" ]]; then
    awk -v start="$pack_start" -v footer="$footer" '
      NR < start { next }
      $0 == footer { print NR; exit }
    ' "$existing"
  fi
}

write_merged_codex_agents_md() {
  local existing="$1"
  local src="$2"
  local output="$3"
  local pack_start="$4"
  local total_lines head_lines tail_start pack_end new_lines footer_end

  total_lines=$(wc -l < "$existing")
  new_lines=$(wc -l < "$src")
  footer_end="$(find_codex_pack_end_line "$existing" "$src" "$pack_start")"

  if [[ -n "$footer_end" ]]; then
    pack_end="$footer_end"
  else
    pack_end=$((pack_start + new_lines - 1))
    if [[ "$pack_end" -gt "$total_lines" ]]; then
      pack_end="$total_lines"
    fi
  fi

  head_lines=$((pack_start - 1))
  tail_start=$((pack_end + 1))

  {
    if [[ "$head_lines" -gt 0 ]]; then
      head -n "$head_lines" "$existing"
    fi
    cat "$src"
    if [[ "$tail_start" -le "$total_lines" ]]; then
      tail -n "+$tail_start" "$existing"
    fi
  } > "$output"
}

echo "  Installing skills (per-skill, preserving user-added skills)..."
if [[ ! -d "$SKILLS_TARGET" ]]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "    [dry-run] would create $SKILLS_TARGET"
  else
    mkdir -p "$SKILLS_TARGET"
  fi
fi

# Count what will be replaced and confirm
pack_skills=()
for skill_dir in "$SOURCE/skills"/*/; do
  [[ -d "$skill_dir" ]] || continue
  pack_skills+=("$(basename "$skill_dir")")
done

existing_count=0
if [[ -d "$SKILLS_TARGET" ]]; then
  for d in "$SKILLS_TARGET"/*/; do
    [[ -d "$d" ]] || continue
    existing_count=$((existing_count + 1))
  done
fi

if [ "$existing_count" -gt 0 ] && [ "$FORCE" -ne 1 ] && [ "$DRY_RUN" -ne 1 ] && [ -t 0 ]; then
  user_count=$((existing_count - ${#pack_skills[@]}))
  if [ "$user_count" -lt 0 ]; then user_count=0; fi
  echo ""
  echo "  Reinstall will replace ${#pack_skills[@]} pack skills. $user_count user skill(s) will be preserved."
  while true; do
    read -r -p "  Proceed? [y/N] " answer
    case "${answer,,}" in
      y|yes) break ;;
      n|no|"") echo "Install cancelled by user." >&2; exit 1 ;;
      *) echo "  Please answer y or n." ;;
    esac
  done
fi

pack_skills=()
for skill_dir in "$SOURCE/skills"/*/; do
  [[ -d "$skill_dir" ]] || continue
  skill_name="$(basename "$skill_dir")"
  pack_skills+=("$skill_name")
  install_skill "$skill_dir" "$SKILLS_TARGET/$skill_name" "skills/$skill_name"
done
echo "  Installed ${#pack_skills[@]} pack skills."

# Report user-added skills that were preserved
if [[ -d "$SKILLS_TARGET" ]]; then
  for existing_dir in "$SKILLS_TARGET"/*/; do
    [[ -d "$existing_dir" ]] || continue
    existing_name="$(basename "$existing_dir")"
    is_pack=0
    for ps in "${pack_skills[@]}"; do
      if [[ "$ps" == "$existing_name" ]]; then is_pack=1; break; fi
    done
    if [[ $is_pack -eq 0 ]]; then
      echo "  Preserved user skill: $existing_name"
    fi
  done
fi

# Runtime ledger helpers are sourced once from repo-root scripts/ and installed
# beside the lead scripts so installed packs have a local helper surface too.
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
lead_scripts_target="$SKILLS_TARGET/lead/scripts"
if [[ ! -d "$lead_scripts_target" ]]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "    [dry-run] would create $lead_scripts_target"
  else
    mkdir -p "$lead_scripts_target"
  fi
fi
for script_name in "${runtime_ledger_scripts[@]}"; do
  script_source="$REPO_DIR/scripts/$script_name"
  script_target="$lead_scripts_target/$script_name"
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

echo "  Installing built-in agent overrides (preserving existing custom files)..."
if [[ ! -d "$AGENT_OVERRIDES_TARGET" ]]; then
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "    [dry-run] would create $AGENT_OVERRIDES_TARGET"
  else
    mkdir -p "$AGENT_OVERRIDES_TARGET"
  fi
fi
for agent_file in "$AGENTS_SOURCE"/*.toml; do
  [[ -f "$agent_file" ]] || continue
  ensure_codex_agent_override_file "$agent_file" "$AGENT_OVERRIDES_TARGET/$(basename "$agent_file")" "built-in agent override $(basename "$agent_file")"
done

# AGENTS.md: assemble from shared + codex-specific, then merge or create
src_shared="$REPO_DIR/shared/AGENTS.shared.md"
src_platform="$SOURCE/AGENTS.codex.md"

if [[ ! -f "$src_shared" ]] || [[ ! -f "$src_platform" ]]; then
  echo "FAIL: Missing $src_shared or $src_platform"
  exit 1
fi

# Assemble pack AGENTS.md from two source files
src_md="$(mktemp)"
{
  printf '%s\n' "$CODEX_PACK_BEGIN_MARKER"
  cat "$src_shared"
  printf '\n'
  cat "$src_platform"
  printf '\n%s\n' "$CODEX_PACK_END_MARKER"
} > "$src_md"
trap "rm -f '$src_md'" EXIT

dst_md="$MD_TARGET"

remove_dangling_symlink "$dst_md" "AGENTS.md"

if [[ -f "$dst_md" ]]; then
  if grep -q "## Template routing" "$dst_md" 2>/dev/null; then
    pack_start="$(find_codex_pack_start_line "$dst_md")"
    if [[ -n "$pack_start" ]]; then
      echo "  AGENTS.md: replacing Codex pack section..."
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "    [dry-run] would replace Codex pack section in AGENTS.md"
      else
        write_merged_codex_agents_md "$dst_md" "$src_md" "$dst_md.tmp" "$pack_start"
        mv "$dst_md.tmp" "$dst_md"
      fi
    else
      echo "  AGENTS.md: full replace..."
      if [ "$DRY_RUN" -eq 1 ]; then
        echo "    [dry-run] would replace AGENTS.md"
      else
        cp "$src_md" "$dst_md"
      fi
    fi
  else
    echo "  AGENTS.md: prepending Codex pack content..."
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "    [dry-run] would prepend AGENTS.md"
    else
      existing="$(cat "$dst_md")"
      new="$(cat "$src_md")"
      printf '%s\n%s' "$new" "$existing" > "$dst_md"
    fi
  fi
else
  echo "  Creating AGENTS.md..."
  if [ "$DRY_RUN" -eq 1 ]; then
    echo "    [dry-run] would create AGENTS.md"
  else
    cp "$src_md" "$dst_md"
  fi
fi

if [ "$MODE" != "global" ]; then
  ensure_local_only_gitignore_entries "$PROJECT_ROOT"
fi

migrate_legacy_agents_mode_file "$LEGACY_AGENTS_MODE_TARGET" "$AGENTS_MODE_TARGET" ".agents-mode.yaml"
sync_agents_mode_file "$SHARED_AGENTS_MODE_SOURCE" "$AGENTS_MODE_TARGET" ".agents-mode.yaml" "codex"

# Shared cross-pack global .agents-mode.yaml lives at $HOME/.agents-mode.yaml
# (alongside ~/.claude.json). Lowest-precedence fallback layer below pack-local
# globals and project-local overlays. Sync is normalize-not-overwrite, so calling
# from both pack installers is idempotent. Only created/normalized during global installs.
if [ "$MODE" = "global" ]; then
  SHARED_GLOBAL_AGENTS_MODE="$HOME/.agents-mode.yaml"
  sync_agents_mode_file "$SHARED_AGENTS_MODE_SOURCE" "$SHARED_GLOBAL_AGENTS_MODE" "shared global ~/.agents-mode.yaml" "shared"
fi

# Install structural hooks into ~/.codex/hooks.json
# (global) or <project>/.codex/hooks.json (target). Idempotent JSON merge that
# preserves all other user keys and other hooks. Opt out with --no-hypothesis-hook
# or ORCHESTRARIUM_NO_HYPOTHESIS_HOOK=1. Codex's matcher field has no `if`-style
# argument filter, so the hook script self-filters by parsing tool_input.command.
if [ "$NO_HYPOTHESIS_HOOK" -ne 1 ] && [ "$DRY_RUN" -ne 1 ] && [ -z "${ORCHESTRARIUM_NO_HYPOTHESIS_HOOK:-}" ]; then
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
    # Host detection controls validation and command serialization only.
    # resolve_hook_target is the single owner of wrapper/python/native target
    # selection.
    case "$(uname -s 2>/dev/null)" in
      MINGW*|MSYS*|CYGWIN*) hook_host_os="windows" ;;
      *) hook_host_os="posix" ;;
    esac
    # TARGET is ~/.codex (global) or <project>/.codex (target). Codex hooks.json
    # lives in the .codex/ directory in both modes.
    # AGENTS_ROOT is ~/.codex (global) or <project>/.agents (target) — skills
    # live under AGENTS_ROOT.
    hooks_target="$TARGET/hooks.json"
    bugfix_script_target="$AGENTS_ROOT/skills/lead/scripts/check-bugfix-discipline.py"
    git_push_gate_script_target="$AGENTS_ROOT/skills/lead/scripts/check-git-push-gate.py"
    stop_script_target="$AGENTS_ROOT/skills/lead/scripts/check-passive-polling-stop.py"
    wi_archival_script_target="$AGENTS_ROOT/skills/lead/scripts/check-work-items-archival-stop.py"
    machine_path_script_target="$AGENTS_ROOT/skills/lead/hooks/check-machine-local-path.py"
    notrash_script_target="$AGENTS_ROOT/skills/lead/hooks/check-no-trash-in-repo.py"
    stale_relation_script_target="$AGENTS_ROOT/skills/lead/hooks/check-stale-relation-residue.py"
    repository_orientation_script_target="$AGENTS_ROOT/skills/lead/hooks/check-repository-orientation.py"
    mcp_momentum_script_target="$AGENTS_ROOT/skills/lead/hooks/check-mcp-momentum.py"
    reminder_script_target="$AGENTS_ROOT/skills/lead/scripts/mcp-usage-reminder.py"
    agents_mode_reminder_script_target="$AGENTS_ROOT/skills/lead/scripts/agents-mode-reminder.py"
    scratch_valuables_script_target="$AGENTS_ROOT/skills/lead/scripts/check-scratch-valuables.py"
    turn_anchor_reminder_script_target="$AGENTS_ROOT/skills/lead/scripts/turn-anchor-reminder.py"
    hook_targets=(
      "$bugfix_script_target"
      "$git_push_gate_script_target"
      "$stop_script_target"
      "$wi_archival_script_target"
      "$machine_path_script_target"
      "$notrash_script_target"
      "$stale_relation_script_target"
      "$repository_orientation_script_target"
      "$mcp_momentum_script_target"
      "$reminder_script_target"
      "$agents_mode_reminder_script_target"
      "$scratch_valuables_script_target"
      "$turn_anchor_reminder_script_target"
    )
    for hook_target_path in "${hook_targets[@]}"; do
      "$python_cmd" "$hook_installer" \
        --target "$hooks_target" \
        --platform codex \
        --host-os "$hook_host_os" \
        --hook-runtime "$HOOK_RUNTIME" \
        --script-path "$hook_target_path" \
        --validate-only
    done
    run_hook_installer() {
      "$python_cmd" "$hook_installer" --hook-runtime "$HOOK_RUNTIME" "$@"
    }
    run_test_hook_transaction_checkpoint() {
      local stage="$1"
      "$python_cmd" "$hook_installer" \
        --target "$hooks_target" \
        --platform codex \
        --repo-root "$REPO_DIR" \
        --test-install-scope "$MODE" \
        --test-transaction-checkpoint "$stage"
    }
    run_test_hook_transaction_checkpoint sync
    echo "  Installing bugfix-discipline PreToolUse hook (host-os=$hook_host_os; trust step manual via codex TUI)..."
    run_hook_installer \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --script-path "$bugfix_script_target"
    echo "  Installing git-push publication-gate PreToolUse hook (host-os=$hook_host_os; trust step manual via codex TUI)..."
    run_hook_installer \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --script-marker check-git-push-gate \
      --tool-matcher "Bash|PowerShell" \
      --script-path "$git_push_gate_script_target"
    echo "  Installing passive-polling Stop hook (host-os=$hook_host_os; trust step manual via codex TUI)..."
    run_hook_installer \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --hook-event Stop \
      --script-marker check-passive-polling-stop \
      --script-path "$stop_script_target"
    echo "  Installing work-items-archival Stop hook (host-os=$hook_host_os; trust step manual via codex TUI)..."
    run_hook_installer \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --hook-event Stop \
      --script-marker check-work-items-archival-stop \
      --script-path "$wi_archival_script_target"
    echo "  Installing machine-local-path PreToolUse hook [AUDIT] (host-os=$hook_host_os; trust step manual via codex TUI)..."
    run_hook_installer \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --script-marker check-machine-local-path \
      --script-path "$machine_path_script_target"
    echo "  Installing no-trash-in-repo PreToolUse hook [AUDIT] (host-os=$hook_host_os; trust step manual via codex TUI)..."
    run_hook_installer \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --script-marker check-no-trash-in-repo \
      --tool-matcher "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell" \
      --script-path "$notrash_script_target"
    echo "  Installing stale-relation-residue PreToolUse hook [AUDIT] (host-os=$hook_host_os; trust step manual via codex TUI)..."
    run_hook_installer \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --script-marker check-stale-relation-residue \
      --script-path "$stale_relation_script_target"
    echo "  Installing repository-orientation PreToolUse hook [AUDIT] (host-os=$hook_host_os; trust step manual via codex TUI)..."
    run_hook_installer \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --script-marker check-repository-orientation \
      --tool-matcher "Edit|Write|NotebookEdit|apply_patch|Bash|PowerShell|shell_command|exec_command" \
      --script-path "$repository_orientation_script_target"
    echo "  Installing mcp-momentum PreToolUse hook [AUDIT] (host-os=$hook_host_os; trust step manual via codex TUI)..."
    run_hook_installer \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --script-marker check-mcp-momentum \
      --tool-matcher "Grep|Bash" \
      --script-path "$mcp_momentum_script_target"
    echo "  Installing MCP-usage-reminder SessionStart hook (host-os=$hook_host_os; trust step manual via codex TUI)..."
    run_hook_installer \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --hook-event SessionStart \
      --script-marker mcp-usage-reminder \
      --script-path "$reminder_script_target"
    echo "  Installing delegation-posture (agents-mode) SessionStart hook (host-os=$hook_host_os; trust step manual via codex TUI)..."
    run_hook_installer \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --hook-event SessionStart \
      --script-marker agents-mode-reminder \
      --script-path "$agents_mode_reminder_script_target"
    echo "  Installing scratch-valuables watchdog SessionStart hook (host-os=$hook_host_os; trust step manual via codex TUI)..."
    run_hook_installer \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --hook-event SessionStart \
      --script-marker check-scratch-valuables \
      --script-path "$scratch_valuables_script_target"
    echo "  Installing turn-anchor-reminder UserPromptSubmit hook (host-os=$hook_host_os; trust step manual via codex TUI)..."
    run_hook_installer \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --hook-event UserPromptSubmit \
      --script-marker turn-anchor-reminder \
      --script-path "$turn_anchor_reminder_script_target"
    run_test_hook_transaction_checkpoint register

    hook_health_checker="$REPO_DIR/scripts/check-hook-health.py"
    if [[ ! -f "$hook_health_checker" ]]; then
      echo "FAIL: hook health checker not found at $hook_health_checker" >&2
      exit 1
    fi
    echo "  Verifying registered hook targets before reclaiming wrappers..."
    "$python_cmd" "$hook_health_checker" \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --repo-root "$REPO_DIR"
    excluded_source_files="$(
      "$python_cmd" "$hook_installer" \
        --target "$hooks_target" \
        --platform codex \
        --host-os "$hook_host_os" \
        --hook-runtime "$HOOK_RUNTIME" \
        --repo-root "$REPO_DIR" \
        --print-verification-exclusions
    )"
    while IFS= read -r excluded_source_file; do
      excluded_source_file="${excluded_source_file%$'\r'}"
      if [[ -n "$excluded_source_file" ]]; then
        hook_verification_exclusions+=("$excluded_source_file")
      fi
    done <<< "$excluded_source_files"
    run_test_hook_transaction_checkpoint verify
    echo "  Reclaiming owned installed hook wrappers after verification..."
    "$python_cmd" "$hook_installer" \
      --target "$hooks_target" \
      --platform codex \
      --host-os "$hook_host_os" \
      --reclaim-root "$AGENTS_ROOT/skills/lead" \
      --repo-root "$REPO_DIR" \
      --test-install-scope "$MODE"
  fi
fi

if [ "$DRY_RUN" -eq 1 ]; then
  if [ "$NO_HYPOTHESIS_HOOK" -ne 1 ] && [ -z "${ORCHESTRARIUM_NO_HYPOTHESIS_HOOK:-}" ]; then
    python_cmd="$(resolve_python)" || exit 1
    case "$(uname -s)" in
      MINGW*|MSYS*|CYGWIN*) hook_host_os="windows" ;;
      *) hook_host_os="posix" ;;
    esac
    hook_installer="$REPO_DIR/scripts/install-hypothesis-hook.py"
    if [[ ! -f "$hook_installer" ]]; then
      echo "FAIL: hook installer not found at $hook_installer" >&2
      exit 1
    fi
    "$python_cmd" "$hook_installer" \
      --target "$TARGET/hooks.json" \
      --platform codex \
      --host-os "$hook_host_os" \
      --hook-runtime "$HOOK_RUNTIME" \
      --script-path "$SOURCE/skills/lead/scripts/check-bugfix-discipline.py" \
      --reclaim-root "$AGENTS_ROOT/skills/lead" \
      --repo-root "$REPO_DIR" \
      --test-install-scope "$MODE" \
      --preview-reclaim \
      --dry-run
  fi
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

source_file_is_optional_for_profile() {
  local rel_path="$1"
  local excluded_source_file
  for excluded_source_file in "${hook_verification_exclusions[@]}"; do
    if [[ "$rel_path" == "$excluded_source_file" ]]; then
      return 0
    fi
  done
  return 1
}

check_installed_manifest() {
  local source_dir="$1"
  local target_base="$2"
  local source_base="$3"
  while IFS= read -r -d '' source_file; do
    local rel_path="${source_file#$source_base/}"
    local source_rel_path="${source_file#$SOURCE/}"
    if source_file_is_optional_for_profile "$source_rel_path"; then
      echo "  OK  $source_rel_path (intentionally reclaimed for hook-runtime=$HOOK_RUNTIME)"
    else
      check_file "$target_base/$rel_path" "$rel_path"
    fi
  done < <(find "$source_dir" -type f -print0)
}

check_installed_manifest "$SOURCE/skills" "$SKILLS_TARGET" "$SOURCE/skills"
check_installed_manifest "$AGENTS_SOURCE" "$AGENT_OVERRIDES_TARGET" "$AGENTS_SOURCE"

check_file "$SKILLS_TARGET/lead/operating-model.md" "skills/lead/operating-model.md"
check_file "$SKILLS_TARGET/lead/subagent-contracts.md" "skills/lead/subagent-contracts.md"
check_file "$SKILLS_TARGET/lead/scripts/check-publication-safety.sh" "skills/lead/scripts/check-publication-safety.sh"
check_file "$SKILLS_TARGET/lead/scripts/check-publication-safety.ps1" "skills/lead/scripts/check-publication-safety.ps1"
check_file "$SKILLS_TARGET/lead/scripts/validate-skill-pack.sh" "skills/lead/scripts/validate-skill-pack.sh"
for script_name in "${runtime_ledger_scripts[@]}"; do
  check_file "$SKILLS_TARGET/lead/scripts/$script_name" "skills/lead/scripts/$script_name"
done
check_file "$AGENTS_MODE_TARGET" ".agents-mode.yaml"
check_file "$AGENT_OVERRIDES_TARGET/default.toml" "agents/default.toml"
check_file "$AGENT_OVERRIDES_TARGET/worker.toml" "agents/worker.toml"
check_file "$AGENT_OVERRIDES_TARGET/explorer.toml" "agents/explorer.toml"

if [[ -f "$dst_md" ]]; then
  line_count=$(wc -l < "$dst_md")
  echo "  OK  AGENTS.md ($line_count lines)"
  for section in "## Template routing" "## Role index" "## Engineering hygiene" "## Publication safety"; do
    if grep -q "$section" "$dst_md"; then
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
  echo "RESULT: OK — Codex pack installed"
  echo "  Skills: $SKILLS_TARGET"
  echo "  Built-in agent overrides: $AGENT_OVERRIDES_TARGET"
  echo "  AGENTS.md: $MD_TARGET"
  echo "  agents-mode: $AGENTS_MODE_TARGET"
  echo ""
  echo "Next: open Codex in the target project and run '\$init-project' to review/update project policies and the installed default .agents/.agents-mode.yaml."
  echo "Then run 'bash $SKILLS_TARGET/lead/scripts/validate-skill-pack.sh' if you are validating the installation from a maintainer shell."
fi

#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SOURCE="$REPO_DIR/src.gemini"
EXTENSION_SOURCE="$SOURCE/extension"
EXTENSION_MANIFEST_SOURCE="$EXTENSION_SOURCE/gemini-extension.json"
EXTENSION_README_SOURCE="$EXTENSION_SOURCE/README.md"
SHARED_AGENTS_SOURCE="$REPO_DIR/shared/AGENTS.shared.md"
DEFAULT_AGENTS_MODE_SOURCE="$REPO_DIR/shared/agents-mode.defaults.yaml"
UNIVERSAL_HOOK_SCRIPTS_SOURCE="$REPO_DIR/scripts/universal-hooks/scripts"
UNIVERSAL_HOOK_HOOKS_SOURCE="$REPO_DIR/scripts/universal-hooks/hooks"
MANAGED_START='<!-- ORCHESTRARIUM_GEMINI_PACK:START -->'
MANAGED_END='<!-- ORCHESTRARIUM_GEMINI_PACK:END -->'
FORCE=0
DRY_RUN=0
ALLOW_UNSAFE_TARGET=0

# Universal hook/helper names are DERIVED by globbing the pack-neutral canon dirs
# (scripts/universal-hooks/{scripts,hooks}/) — never a hardcoded list. A hook
# added to the canon is auto-installed here; a hardcoded list is exactly what hid
# check-stale-relation-residue from the install surface until 2026-07-07.
UNIVERSAL_RUNTIME_SCRIPT_NAMES=()
for _u in "$UNIVERSAL_HOOK_SCRIPTS_SOURCE"/*.py "$UNIVERSAL_HOOK_SCRIPTS_SOURCE"/*.sh "$UNIVERSAL_HOOK_SCRIPTS_SOURCE"/*.ps1; do
  [[ -f "$_u" ]] && UNIVERSAL_RUNTIME_SCRIPT_NAMES+=("$(basename "$_u")")
done
UNIVERSAL_RUNTIME_HOOK_NAMES=()
for _u in "$UNIVERSAL_HOOK_HOOKS_SOURCE"/*.py "$UNIVERSAL_HOOK_HOOKS_SOURCE"/*.sh "$UNIVERSAL_HOOK_HOOKS_SOURCE"/*.ps1; do
  [[ -f "$_u" ]] && UNIVERSAL_RUNTIME_HOOK_NAMES+=("$(basename "$_u")")
done
MODE="repo"
TARGET=""

usage() {
  cat <<'EOF'
Usage:
  bash scripts/install-gemini.sh                    Install the Gemini example pack into current repo (GEMINI.md + AGENTS.md + .gemini/)
  bash scripts/install-gemini.sh --global           Install the Gemini example pack into ~/.gemini/
  bash scripts/install-gemini.sh --target DIR       Install the Gemini example pack into DIR as a project root
  bash scripts/install-gemini.sh --force            Skip confirmation prompts
  bash scripts/install-gemini.sh --dry-run          Print planned actions without changing files
  bash scripts/install-gemini.sh --allow-unsafe-target
                                           Allow a custom project root outside the current repo
EOF
  exit 1
}

canonical_path() {
  local path="$1"
  case "$path" in
    "~")
      path="$HOME"
      ;;
    "~/"*|"~\\"*)
      path="$HOME/${path#??}"
      ;;
  esac
  path="${path//\\//}"
  case "$path" in
    [A-Za-z]:/*)
      if command -v wslpath >/dev/null 2>&1; then
        path="$(wslpath -u "$path")"
      elif command -v cygpath >/dev/null 2>&1; then
        path="$(cygpath -u "$path")"
      else
        local drive rest
        drive="$(printf '%s' "${path:0:1}" | tr '[:upper:]' '[:lower:]')"
        rest="${path:3}"
        if [[ -d "/mnt/$drive" ]]; then
          path="/mnt/$drive/$rest"
        else
          path="/$drive/$rest"
        fi
      fi
      ;;
    [A-Za-z]:*)
      echo "FAIL: Windows drive-relative path '$path' is ambiguous; use C:/path or quote '~' so Bash expands it." >&2
      return 1
      ;;
  esac
  if [[ -z "$path" ]]; then
    echo "" >&2
    return 1
  fi

  if command -v realpath >/dev/null 2>&1; then
    realpath -m "$path"
    return
  fi

  if [[ -e "$path" || -L "$path" ]]; then
    if [[ -d "$path" ]]; then
      (cd "$path" && pwd -P)
    else
      local dir base
      dir="$(dirname "$path")"
      base="$(basename "$path")"
      printf "%s/%s\n" "$(cd "$dir" && pwd -P)" "$base"
    fi
  elif [[ "$path" = /* ]]; then
    printf "%s\n" "$path"
  else
    printf "%s/%s\n" "$(pwd -P)" "$path"
  fi
}

repo_root() {
  if git rev-parse --show-toplevel >/dev/null 2>&1; then
    git rev-parse --show-toplevel
  else
    pwd
  fi
}

resolve_project_root() {
  local input="$1"
  local resolved
  resolved="$(canonical_path "$input")"
  if [[ "$(basename "$resolved")" == ".gemini" ]]; then
    dirname "$resolved"
  else
    printf "%s" "$resolved"
  fi
}

extension_name_from_manifest() {
  local manifest="$1"
  local name
  name="$(sed -nE 's/^[[:space:]]*"name"[[:space:]]*:[[:space:]]*"([^"]+)".*$/\1/p' "$manifest" | head -n 1)"
  if [[ -z "$name" ]]; then
    echo "FAIL: Gemini extension manifest is missing a non-empty 'name' field." >&2
    return 1
  fi
  printf "%s\n" "$name"
}

ensure_dir() {
  local path="$1"
  if [[ ! -d "$path" ]]; then
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would create $path"
    else
      mkdir -p "$path"
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

confirm_action() {
  local prompt="$1"
  if [[ "$FORCE" -eq 1 || "$DRY_RUN" -eq 1 || ! -t 0 ]]; then
    return 0
  fi
  while true; do
    read -r -p "$prompt [y/N] " answer
    case "${answer,,}" in
      y|yes) return 0 ;;
      ""|n|no) return 1 ;;
      *) echo "Please answer y or n." ;;
    esac
  done
}

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

install_tree() {
  local src="$1" dst="$2" label="$3"
  local item_name
  local pack_items=()
  ensure_dir "$dst"
  echo "  Installing $label (per-item, preserving user-added items)..."
  shopt -s nullglob
  for item in "$src"/*; do
    item_name="$(basename "$item")"
    pack_items+=("$item_name")
    if [[ -e "$dst/$item_name" ]]; then
      if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "    [dry-run] would replace $label/$item_name"
      elif items_equal "$item" "$dst/$item_name"; then
        echo "    OK  $label/$item_name unchanged"
      else
        rm -rf "$dst/$item_name"
        cp -r "$item" "$dst/$item_name"
      fi
    else
      if [[ "$DRY_RUN" -eq 1 ]]; then
        echo "    [dry-run] would install $label/$item_name"
      else
        cp -r "$item" "$dst/$item_name"
      fi
    fi
  done
  for existing in "$dst"/*; do
    local found=0
    item_name="$(basename "$existing")"
    for pack_item in "${pack_items[@]}"; do
      if [[ "$pack_item" == "$item_name" ]]; then
        found=1
        break
      fi
    done
    if [[ "$found" -eq 0 ]]; then
      echo "  Preserved user item: $label/$item_name"
    fi
  done
  shopt -u nullglob
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
          git -C "$giprobe_root" config core.excludesFile "${giprobe_root}.noexcludes" >/dev/null 2>&1 || true
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
  if [[ "$DRY_RUN" -eq 1 ]]; then
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

collect_preserved_gemini_imports() {
  local existing="$1" start_line="$2" end_line="$3"
  awk -v start="$start_line" -v end="$end_line" '
    NR <= start || NR >= end { next }
    {
      if (!collect) {
        if ($0 ~ /^@/ || $0 ~ /^[[:space:]]*$/) {
          collect = 1
        } else {
          exit
        }
      }
      if ($0 ~ /^@/) {
        if ($0 != "@./AGENTS.md" && $0 != "@./AGENTS.shared.md" && $0 != "@../shared/AGENTS.shared.md" && !seen[$0]++) {
          print $0
        }
        next
      }
      if ($0 ~ /^[[:space:]]*$/) {
        next
      }
      exit
    }
  ' "$existing"
}

write_merged_gemini_md() {
  local existing="$1" src="$2" output="$3" start_line="$4" end_line="$5"
  local imports_tmp managed_tmp tail_tmp total_lines
  imports_tmp="$(mktemp)"
  managed_tmp="$(mktemp)"
  tail_tmp="$(mktemp)"

  collect_preserved_gemini_imports "$existing" "$start_line" "$end_line" > "$imports_tmp"
  awk -v imports_file="$imports_tmp" '
    BEGIN {
      while ((getline line < imports_file) > 0) {
        imports[++import_count] = line
      }
      close(imports_file)
    }
    {
      if ($0 == "@./AGENTS.shared.md" || $0 == "@../shared/AGENTS.shared.md") {
        $0 = "@./AGENTS.md"
      }
      source[++source_count] = $0
    }
    END {
      import_line = 0
      for (i = 1; i <= source_count; i++) {
        if (source[i] ~ /^@/) {
          import_line = i
          break
        }
      }

      if (import_line == 0) {
        for (i = 1; i <= source_count; i++) {
          print source[i]
        }
        exit
      }

      for (i = 1; i < import_line; i++) {
        print source[i]
      }
      print source[import_line]
      for (i = 1; i <= import_count; i++) {
        print imports[i]
      }

      tail_start = import_line + 1
      while (tail_start <= source_count && source[tail_start] ~ /^[[:space:]]*$/) {
        tail_start++
      }

      if (tail_start <= source_count) {
        print ""
        for (i = tail_start; i <= source_count; i++) {
          print source[i]
        }
      }
    }
  ' "$src" > "$managed_tmp"

  : > "$output"
  if (( start_line > 1 )); then
    head -n $((start_line - 1)) "$existing" > "$output"
  fi
  cat "$managed_tmp" >> "$output"

  total_lines=$(wc -l < "$existing")
  if (( end_line < total_lines )); then
    tail -n +$((end_line + 1)) "$existing" > "$tail_tmp"
    if [[ -s "$tail_tmp" ]]; then
      cat "$tail_tmp" >> "$output"
    fi
  fi

  rm -f "$imports_tmp" "$managed_tmp" "$tail_tmp"
}

merge_gemini_file() {
  local src="$1" dst="$2"
  local managed existing start_line end_line
  managed="$(sed -E 's#^@(\./AGENTS\.shared\.md|\.\./shared/AGENTS\.shared\.md)$#@./AGENTS.md#' "$src")"
  if [[ ! -f "$dst" ]]; then
    echo "  Creating GEMINI.md..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would create $dst"
    else
      printf '%s' "$managed" > "$dst"
    fi
    return
  fi

  existing="$(cat "$dst")"
  if grep -qF "$MANAGED_START" "$dst" && grep -qF "$MANAGED_END" "$dst"; then
    echo "  GEMINI.md: replacing managed Orchestrarium block..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would replace managed GEMINI.md block"
    else
      start_line=$(grep -nF "$MANAGED_START" "$dst" | head -1 | cut -d: -f1)
      end_line=$(grep -nF "$MANAGED_END" "$dst" | head -1 | cut -d: -f1)
      write_merged_gemini_md "$dst" "$src" "$dst.tmp" "$start_line" "$end_line"
      mv "$dst.tmp" "$dst"
    fi
  else
    echo "  GEMINI.md: prepending managed Orchestrarium block..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would prepend managed GEMINI.md block"
    else
      printf '%s\n\n%s' "$managed" "$existing" > "$dst"
    fi
  fi
}

install_pack_file() {
  local src="$1" dst="$2" label="$3" preserve_existing="${4:-0}"
  if [[ -e "$dst" ]]; then
    if [[ "$preserve_existing" == "1" ]]; then
      echo "  Preserving existing $label..."
      return
    fi
    echo "  Replacing $label..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would replace $dst"
    else
      cp -f "$src" "$dst"
    fi
    return
  fi

  echo "  Installing $label..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "    [dry-run] would create $dst"
  else
    cp -f "$src" "$dst"
  fi
}

sync_agents_mode_file() {
  local template="$1" dst="$2" label="$3"
  local normalizer="$REPO_DIR/scripts/normalize-agents-mode.py"
  local python_cmd=""

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
    cp -f "$template" "$dst"
  fi
}

migrate_legacy_agents_mode_file() {
  local legacy="$1" dst="$2" label="$3"

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
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "    [dry-run] would move $legacy -> $dst"
  else
    mv "$legacy" "$dst"
  fi
}

install_pack_content_file() {
  local src="$1" dst="$2" label="$3"
  ensure_dir "$(dirname "$dst")"
  if [[ -e "$dst" ]]; then
    echo "  Replacing $label..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would replace $dst"
    else
      cp -f "$src" "$dst"
    fi
    return
  fi

  echo "  Installing $label..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "    [dry-run] would create $dst"
  else
    cp -f "$src" "$dst"
  fi
}

install_universal_hook_helpers() {
  local scripts_dst="$1" hooks_dst="$2" name
  ensure_dir "$scripts_dst"
  ensure_dir "$hooks_dst"

  echo "  Installing universal hook/helper scripts..."
  for name in "${UNIVERSAL_RUNTIME_SCRIPT_NAMES[@]}"; do
    install_pack_file "$UNIVERSAL_HOOK_SCRIPTS_SOURCE/$name" "$scripts_dst/$name" "extension universal hook/helper scripts/$name"
  done
  for name in "${UNIVERSAL_RUNTIME_HOOK_NAMES[@]}"; do
    install_pack_file "$UNIVERSAL_HOOK_HOOKS_SOURCE/$name" "$hooks_dst/$name" "extension universal hook/helper hooks/$name"
  done
}

remove_legacy_pack_file() {
  local dst="$1" label="$2"
  if [[ ! -e "$dst" ]]; then
    return
  fi
  echo "  Removing legacy $label..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "    [dry-run] would remove $dst"
  else
    rm -f "$dst"
  fi
}

remove_empty_dir_if_present() {
  local dst="$1"
  if [[ ! -d "$dst" ]]; then
    return
  fi
  shopt -s nullglob dotglob
  local items=("$dst"/*)
  shopt -u nullglob dotglob
  if (( ${#items[@]} > 0 )); then
    return
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "    [dry-run] would remove empty directory $dst"
  else
    rmdir "$dst"
  fi
}

remove_legacy_top_level_pack_entries() {
  local src="$1" dst="$2" label="$3"
  [[ -d "$dst" ]] || return 0
  shopt -s nullglob
  for item in "$src"/*; do
    local item_name target_path
    item_name="$(basename "$item")"
    target_path="$dst/$item_name"
    [[ -e "$target_path" ]] || continue
    echo "  Removing legacy $label/$item_name..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would remove $target_path"
    else
      rm -rf "$target_path"
    fi
  done
  shopt -u nullglob
  remove_empty_dir_if_present "$dst"
}

remove_legacy_mirrored_files() {
  local src="$1" dst="$2" label="$3"
  [[ -d "$dst" ]] || return 0
  while IFS= read -r -d '' file; do
    local relative target_path
    relative="${file#$src/}"
    target_path="$dst/$relative"
    [[ -f "$target_path" ]] || continue
    echo "  Removing legacy $label/$relative..."
    if [[ "$DRY_RUN" -eq 1 ]]; then
      echo "    [dry-run] would remove $target_path"
    else
      rm -f "$target_path"
    fi
  done < <(find "$src" -type f -print0)

  while IFS= read -r -d '' dir; do
    remove_empty_dir_if_present "$dir"
  done < <(find "$dst" -depth -type d -print0)
  remove_empty_dir_if_present "$dst"
}

# Roles are now skills-only (one SKILL.md per role under skills/). The former
# Gemini-native agents/ role layer is removed. This cleanup is source-independent
# (the source no longer ships agents/), so it works on upgrade from any prior install:
#   - extension tier: a pack-owned tree, safe to remove wholesale.
#   - user override tier ($AGENTS_TARGET, e.g. ~/.gemini/agents): remove ONLY the
#     known pack-authored basenames by static allowlist; never rm -rf the whole dir,
#     because it may hold genuine user-authored subagents the pack must not touch.
LEGACY_AGENT_BASENAMES=(
  accessibility-reviewer.md algorithm-scientist.md analyst.md architect.md
  architecture-reviewer.md backend-engineer.md computational-scientist.md
  consultant.md data-engineer.md external-reviewer.md external-worker.md
  frontend-engineer.md geometry-engineer.md graphics-engineer.md
  knowledge-archivist.md lead.md model-view-engineer.md performance-engineer.md
  performance-reviewer.md planner.md platform-engineer.md product-analyst.md
  product-manager.md qa-engineer.md qt-ui-engineer.md reliability-engineer.md
  security-engineer.md security-reviewer.md toolchain-engineer.md
  ui-test-engineer.md ux-designer.md ux-reviewer.md visualization-engineer.md
)

remove_path() {
  local target="$1" label="$2"
  [[ -e "$target" ]] || return 0
  echo "  Removing legacy $label..."
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "    [dry-run] would remove $target"
  else
    rm -rf "$target"
  fi
}

remove_legacy_agent_layer() {
  # Extension tier: pack-owned, remove the whole stale agents/ tree.
  remove_path "$EXTENSION_ROOT/agents" "extension/agents (roles are skills-only)"
  # User override tier: remove only pack-authored basenames + the team-templates dir.
  if [[ -d "$AGENTS_TARGET" ]]; then
    local base
    for base in "${LEGACY_AGENT_BASENAMES[@]}"; do
      remove_path "$AGENTS_TARGET/$base" "user-tier agents/$base"
    done
    remove_path "$AGENTS_TARGET/README.md" "user-tier agents/README.md"
    remove_path "$AGENTS_TARGET/team-templates" "user-tier agents/team-templates"
    remove_empty_dir_if_present "$AGENTS_TARGET"
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --global)
      MODE="global"
      shift
      ;;
    --target)
      [[ $# -lt 2 ]] && usage
      MODE="target"
      TARGET="$2"
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
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      ;;
  esac
done

if [[ ! -d "$SOURCE/skills" || ! -d "$SOURCE/commands" || ! -f "$SOURCE/GEMINI.md" || ! -f "$SHARED_AGENTS_SOURCE" ]]; then
  echo "FAIL: src.gemini is incomplete at $SOURCE" >&2
  exit 1
fi
if [[ ! -f "$EXTENSION_MANIFEST_SOURCE" || ! -f "$EXTENSION_README_SOURCE" ]]; then
  echo "FAIL: src.gemini/extension is incomplete at $EXTENSION_SOURCE" >&2
  exit 1
fi
if [[ ! -f "$DEFAULT_AGENTS_MODE_SOURCE" ]]; then
  echo "FAIL: missing default agents-mode template at $DEFAULT_AGENTS_MODE_SOURCE" >&2
  exit 1
fi
if [[ ! -d "$UNIVERSAL_HOOK_SCRIPTS_SOURCE" || ! -d "$UNIVERSAL_HOOK_HOOKS_SOURCE" ]]; then
  echo "FAIL: missing universal hook/helper sources under scripts/universal-hooks" >&2
  exit 1
fi
for script_name in "${UNIVERSAL_RUNTIME_SCRIPT_NAMES[@]}"; do
  if [[ ! -f "$UNIVERSAL_HOOK_SCRIPTS_SOURCE/$script_name" ]]; then
    echo "FAIL: missing universal hook/helper script $script_name" >&2
    exit 1
  fi
done
for script_name in "${UNIVERSAL_RUNTIME_HOOK_NAMES[@]}"; do
  if [[ ! -f "$UNIVERSAL_HOOK_HOOKS_SOURCE/$script_name" ]]; then
    echo "FAIL: missing universal hook/helper hook $script_name" >&2
    exit 1
  fi
done

EXTENSION_NAME="$(extension_name_from_manifest "$EXTENSION_MANIFEST_SOURCE")"

if [[ "$MODE" == "global" ]]; then
  INSTALL_ROOT="$(canonical_path "$HOME/.gemini")"
  EXTENSIONS_TARGET="$INSTALL_ROOT/extensions"
  EXTENSION_ROOT="$EXTENSIONS_TARGET/$EXTENSION_NAME"
  AGENTS_MODE_TARGET="$INSTALL_ROOT/.agents-mode.yaml"
  LEGACY_AGENTS_MODE_TARGET="$INSTALL_ROOT/.agents-mode"
  GEMINI_TARGET="$INSTALL_ROOT/GEMINI.md"
  SHARED_TARGET="$INSTALL_ROOT/AGENTS.md"
  LEGACY_SHARED_TARGET="$INSTALL_ROOT/AGENTS.shared.md"
  SKILLS_TARGET="$INSTALL_ROOT/skills"
  AGENTS_TARGET="$INSTALL_ROOT/agents"
  COMMANDS_TARGET="$INSTALL_ROOT/commands"
else
  PROJECT_ROOT="$(resolve_project_root "${TARGET:-$(repo_root)}")"
  if [[ "$MODE" == "target" && "$ALLOW_UNSAFE_TARGET" -ne 1 ]]; then
    CURRENT_REPO="$(canonical_path "$(repo_root)")"
    if [[ "$(printf '%s' "$PROJECT_ROOT" | tr '[:upper:]' '[:lower:]')" != "$(printf '%s' "$CURRENT_REPO" | tr '[:upper:]' '[:lower:]')" ]]; then
      echo "FAIL: unsafe target denied for non-default project root '$PROJECT_ROOT'. Use --allow-unsafe-target." >&2
      exit 1
    fi
  fi
  INSTALL_ROOT="$PROJECT_ROOT/.gemini"
  EXTENSIONS_TARGET="$INSTALL_ROOT/extensions"
  EXTENSION_ROOT="$EXTENSIONS_TARGET/$EXTENSION_NAME"
  AGENTS_MODE_TARGET="$INSTALL_ROOT/.agents-mode.yaml"
  LEGACY_AGENTS_MODE_TARGET="$INSTALL_ROOT/.agents-mode"
  GEMINI_TARGET="$PROJECT_ROOT/GEMINI.md"
  SHARED_TARGET="$PROJECT_ROOT/AGENTS.md"
  LEGACY_SHARED_TARGET="$PROJECT_ROOT/AGENTS.shared.md"
  SKILLS_TARGET="$INSTALL_ROOT/skills"
  AGENTS_TARGET="$INSTALL_ROOT/agents"
  COMMANDS_TARGET="$INSTALL_ROOT/commands"
fi
EXTENSION_MANIFEST_TARGET="$EXTENSION_ROOT/gemini-extension.json"
EXTENSION_README_TARGET="$EXTENSION_ROOT/README.md"
EXTENSION_GEMINI_TARGET="$EXTENSION_ROOT/GEMINI.md"
EXTENSION_AGENTS_TARGET="$EXTENSION_ROOT/AGENTS.md"
LEGACY_EXTENSION_SHARED_TARGET="$EXTENSION_ROOT/AGENTS.shared.md"

echo "=== Orchestrarium Gemini Example Pack Installer ==="
echo "Source: $SOURCE"
echo "Mode:   $MODE"
echo "Runtime root: $INSTALL_ROOT"
echo "GEMINI.md:    $GEMINI_TARGET"
echo "AGENTS.md:    $SHARED_TARGET"
echo "agents-mode:  $AGENTS_MODE_TARGET"
echo "Extension:    $EXTENSION_ROOT"
echo "Legacy user tier cleanup roots: $SKILLS_TARGET ; $AGENTS_TARGET ; $COMMANDS_TARGET"
echo "Policy:       example-only / WEAK MODEL / NOT RECOMMENDED; production auto routing stays on codex|claude"
[[ "$DRY_RUN" -eq 1 ]] && echo "Mode:   dry-run"
echo

if [[ -e "$GEMINI_TARGET" || -e "$SHARED_TARGET" || -d "$SKILLS_TARGET" || -d "$AGENTS_TARGET" || -d "$COMMANDS_TARGET" || -d "$EXTENSION_ROOT" ]]; then
  if ! confirm_action "Proceed with reinstall/update of the Gemini pack?"; then
    echo "Install cancelled by user." >&2
    exit 1
  fi
fi

ensure_dir "$INSTALL_ROOT"
install_tree "$SOURCE/skills" "$EXTENSION_ROOT/skills" "extension/skills"
install_tree "$SOURCE/commands" "$EXTENSION_ROOT/commands" "extension/commands"
merge_gemini_file "$SOURCE/GEMINI.md" "$GEMINI_TARGET"
if [[ "$MODE" == "global" ]]; then
  install_pack_file "$SHARED_AGENTS_SOURCE" "$SHARED_TARGET" "AGENTS.md"
else
  install_pack_file "$SHARED_AGENTS_SOURCE" "$SHARED_TARGET" "AGENTS.md" 1
  ensure_local_only_gitignore_entries "$PROJECT_ROOT"
fi
install_pack_file "$EXTENSION_MANIFEST_SOURCE" "$EXTENSION_MANIFEST_TARGET" "extension manifest"
install_pack_file "$EXTENSION_README_SOURCE" "$EXTENSION_README_TARGET" "extension README"
extension_gemini_tmp="$(mktemp)"
trap 'rm -f "$extension_gemini_tmp"' EXIT
sed -E 's#@(\./AGENTS\.shared\.md|\.\./shared/AGENTS\.shared\.md)#@./AGENTS.md#' "$SOURCE/GEMINI.md" > "$extension_gemini_tmp"
install_pack_content_file "$extension_gemini_tmp" "$EXTENSION_GEMINI_TARGET" "extension GEMINI.md"
install_pack_file "$SHARED_AGENTS_SOURCE" "$EXTENSION_AGENTS_TARGET" "extension AGENTS.md"
install_universal_hook_helpers "$EXTENSION_ROOT/scripts" "$EXTENSION_ROOT/hooks"
migrate_legacy_agents_mode_file "$LEGACY_AGENTS_MODE_TARGET" "$AGENTS_MODE_TARGET" ".agents-mode.yaml"
sync_agents_mode_file "$DEFAULT_AGENTS_MODE_SOURCE" "$AGENTS_MODE_TARGET" ".agents-mode.yaml"

# Shared cross-pack global .agents-mode.yaml at $HOME/.agents-mode.yaml — lowest-precedence
# fallback layer below pack-local globals. Idempotent across all 4 pack installers.
if [[ "$MODE" == "global" ]]; then
  SHARED_GLOBAL_AGENTS_MODE="$HOME/.agents-mode.yaml"
  sync_agents_mode_file "$DEFAULT_AGENTS_MODE_SOURCE" "$SHARED_GLOBAL_AGENTS_MODE" "shared global ~/.agents-mode.yaml"
fi

remove_legacy_pack_file "$LEGACY_SHARED_TARGET" "AGENTS.shared.md"
remove_legacy_pack_file "$LEGACY_EXTENSION_SHARED_TARGET" "extension AGENTS.shared.md"
remove_legacy_top_level_pack_entries "$SOURCE/skills" "$SKILLS_TARGET" "skills"
remove_legacy_agent_layer
remove_legacy_mirrored_files "$SOURCE/commands" "$COMMANDS_TARGET" "commands"

if [[ "$DRY_RUN" -eq 1 ]]; then
  echo
  echo "RESULT: DRY-RUN complete (no files modified)."
  exit 0
fi

echo
echo "=== Verification ==="
errors=0
for path in \
  "$GEMINI_TARGET" \
  "$SHARED_TARGET" \
  "$AGENTS_MODE_TARGET" \
  "$EXTENSION_MANIFEST_TARGET" \
  "$EXTENSION_GEMINI_TARGET" \
  "$EXTENSION_AGENTS_TARGET" \
  "$EXTENSION_ROOT/scripts/check-bugfix-discipline.py" \
  "$EXTENSION_ROOT/scripts/check-work-items-archival-stop.py" \
  "$EXTENSION_ROOT/scripts/mcp-usage-reminder.sh" \
  "$EXTENSION_ROOT/hooks/check-machine-local-path.py" \
  "$EXTENSION_ROOT/hooks/check-no-trash-in-repo.py" \
  "$EXTENSION_ROOT/skills/lead/SKILL.md" \
  "$EXTENSION_ROOT/skills/init-project/SKILL.md" \
  "$EXTENSION_ROOT/skills/lead/team-templates/full-delivery.json" \
  "$EXTENSION_ROOT/commands/agents/help.toml"; do
  if [[ -e "$path" ]]; then
    echo "  OK  $path"
  else
    echo "  FAIL  $path"
    errors=$((errors+1))
  fi
done

for legacy_path in \
  "$SKILLS_TARGET/lead/SKILL.md" \
  "$EXTENSION_ROOT/agents" \
  "$AGENTS_TARGET/lead.md" \
  "$AGENTS_TARGET/team-templates/full-delivery.json" \
  "$COMMANDS_TARGET/agents/help.toml" \
  "$COMMANDS_TARGET/agents/external-brigade.toml" \
  "$COMMANDS_TARGET/agents/init-project.toml"; do
  if [[ -e "$legacy_path" ]]; then
    echo "  FAIL  legacy duplicate still present: $legacy_path"
    errors=$((errors+1))
  else
    echo "  OK  no legacy duplicate at $legacy_path"
  fi
done

if [[ "$errors" -gt 0 ]]; then
  echo
  echo "RESULT: FAIL ($errors errors)"
  exit 1
fi

echo
echo "RESULT: OK - Gemini example pack installed"

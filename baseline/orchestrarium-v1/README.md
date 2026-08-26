# Orchestrarium Version 1 (V1) parity baseline

This directory anchors Stage 0 of the Orche 2.0 migration.

## Immutable source

- Repository: `applicate2628/Orchestrarium`
- Source branch at capture time: `main`
- Accepted commit: `ce2052fb773576fd6e3206c2a7e21e01852d556b`
- Git tree: `04dccf4575f17c9c5533474d2e0fd1503bfeceb7`
- Intended signed tag: `orchestrarium-v1-parity-baseline`

The baseline is pinned directly to the immutable `main` commit above. It does not depend on,
inherit from, or modify any other pull-request branch.

## Immutable Stage 0 tooling

The four frozen tool snapshots under `baseline/orchestrarium-v1/tooling/` are part of the
reviewed tree. `baseline-pin.json` records each frozen path and Git blob identifier. The
mutable development copies under `scripts/baseline/` may evolve later without changing the
Stage 0 evidence procedure.

```bash
CANDIDATE_ROOT=/absolute/path/to/candidate-worktree
CANDIDATE_ROOT="$(cd "$CANDIDATE_ROOT" && pwd -P)"
PIN_PATH="$CANDIDATE_ROOT/baseline/orchestrarium-v1/baseline-pin.json"
REVIEWED_REF="$(git -C "$CANDIDATE_ROOT" rev-parse HEAD)"
OUTPUT_ROOT="$CANDIDATE_ROOT/.scratch/orche-stage0/differential"
TOOL_ROOT="$OUTPUT_ROOT/tools"
mkdir -p "$TOOL_ROOT"

VERIFIER_PYTHON="${VERIFIER_PYTHON:-$(command -v python3 || command -v python)}"

pin_value() {
  "$VERIFIER_PYTHON" - "$PIN_PATH" "$1" <<'PY'
import json
import sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
for part in sys.argv[2].split("."):
    value = value[part]
print(value)
PY
}

EVIDENCE_ROOT="$CANDIDATE_ROOT/$(pin_value evidence.generatedOutputDirectory)"
mkdir -p "$EVIDENCE_ROOT"

materialize_tool() {
  key="$1"
  output="$2"
  frozen_path="$(pin_value "tooling.$key.path")"
  blob="$(pin_value "tooling.$key.gitBlobSha")"
  test "$(git -C "$CANDIDATE_ROOT" cat-file -t "$blob")" = blob
  test "$(git -C "$CANDIDATE_ROOT" ls-tree "$REVIEWED_REF" -- "$frozen_path" | awk '{print $3}')" = "$blob"
  git -C "$CANDIDATE_ROOT" cat-file blob "$blob" > "$output"
}

materialize_tool inventoryGenerator "$TOOL_ROOT/build_inventory.py"
materialize_tool targetEffectGenerator "$TOOL_ROOT/build_target_effect_baseline.py"
materialize_tool pytestComparator "$TOOL_ROOT/compare_pytest_baseline.py"
materialize_tool commandComparator "$TOOL_ROOT/compare_command_baseline.py"
```

Because the frozen paths are present in the reviewed tree itself, they remain reachable after a
normal merge or a squash merge. The procedure does not depend on intermediate development
commits or a branch that may later be deleted.

## Local-only verification

Stage 0 intentionally does **not** use GitHub Actions. Generated evidence stays under
`.scratch/`, which is not a second source of truth. Temporary `_orche_pr2_verify*.yml` and
`_orche_pr2_review*.yml` workflows are ignored and must never be committed.

Run the focused tests:

```bash
python tests/test_orche_baseline_pin.py
python tests/test_orche_pytest_baseline.py
python tests/test_orche_baseline_inventory.py
python tests/test_orche_target_effect_baseline.py
python tests/test_orche_command_baseline.py
```

Generate evidence using the materialized frozen tools. The machine-readable
`evidence.generatedOutputDirectory` field is the single source of truth for the output path:

```bash
PIN_COMMIT="$(pin_value baseline.commitSha)"
rm -rf "$EVIDENCE_ROOT"
mkdir -p "$EVIDENCE_ROOT"
"$VERIFIER_PYTHON" "$TOOL_ROOT/build_inventory.py" \
  --repo-root "$CANDIDATE_ROOT" \
  --repository applicate2628/Orchestrarium \
  --ref "$PIN_COMMIT" \
  --output-dir "$EVIDENCE_ROOT"
"$VERIFIER_PYTHON" "$TOOL_ROOT/build_target_effect_baseline.py" \
  --inventory "$EVIDENCE_ROOT/capability-inventory.json" \
  --output "$EVIDENCE_ROOT/target-effect-baseline.json"
```

## Isolated baseline and candidate runs

Use clean worktrees and one trusted verifier toolchain outside both worktrees. Candidate-local
virtual environments may exist as ignored files, but they must not supply Python, Bash, Git,
plugins, or commands to either lane.

```bash
BASELINE_ROOT=/absolute/path/to/baseline-worktree
CANDIDATE_ROOT=/absolute/path/to/candidate-worktree
BASELINE_ROOT="$(cd "$BASELINE_ROOT" && pwd -P)"
CANDIDATE_ROOT="$(cd "$CANDIDATE_ROOT" && pwd -P)"
PIN_PATH="$CANDIDATE_ROOT/baseline/orchestrarium-v1/baseline-pin.json"
OUTPUT_ROOT="$CANDIDATE_ROOT/.scratch/orche-stage0/differential"

VERIFIER_PYTHON="${VERIFIER_PYTHON:-$(command -v python3 || command -v python)}"
VERIFIER_GIT="${VERIFIER_GIT:-$(command -v git)}"
VERIFIER_BASH="${VERIFIER_BASH:-$(command -v bash)}"

assert_external_tool() {
  tool="$1"
  test -n "$tool" && test -x "$tool" || {
    echo "BLOCKED: verifier executable unavailable: $tool" >&2
    return 1
  }
  tool_path="$(cd "$(dirname "$tool")" && pwd -P)/$(basename "$tool")"
  case "$tool_path" in
    "$BASELINE_ROOT"/*|"$CANDIDATE_ROOT"/*)
      echo "BLOCKED: verifier executable is inside a tested worktree: $tool_path" >&2
      return 1
      ;;
  esac
}

assert_external_tool "$VERIFIER_PYTHON"
assert_external_tool "$VERIFIER_GIT"
assert_external_tool "$VERIFIER_BASH"
VERIFIER_PATH="$(dirname "$VERIFIER_PYTHON"):$(dirname "$VERIFIER_GIT"):$(dirname "$VERIFIER_BASH"):/usr/local/bin:/usr/bin:/bin"

PIN_COMMIT="$(pin_value baseline.commitSha)"
PIN_TREE="$(pin_value baseline.treeSha)"
BASELINE_REF="$($VERIFIER_GIT -C "$BASELINE_ROOT" rev-parse HEAD)"
BASELINE_TREE="$($VERIFIER_GIT -C "$BASELINE_ROOT" rev-parse 'HEAD^{tree}')"
CANDIDATE_REF="$($VERIFIER_GIT -C "$CANDIDATE_ROOT" rev-parse HEAD)"
test "$BASELINE_REF" = "$PIN_COMMIT"
test "$BASELINE_TREE" = "$PIN_TREE"

# BEGIN ORCHE_CLEAN_WORKTREE_GUARD
ignored_executable_inputs() {
  repo="$1"
  git -C "$repo" ls-files --others --ignored --exclude-standard -- \
    ':(glob)tests/**' \
    ':(glob)**/conftest.py' \
    ':(glob)scripts/**' \
    ':(glob)**/*.py' \
    ':(glob)**/*.sh' \
    ':(glob)**/*.ps1' \
    ':(glob)**/pyproject.toml' \
    ':(glob)**/pytest.ini' \
    ':(glob)**/tox.ini' \
    ':(glob)**/setup.cfg' \
    ':(exclude,glob).scratch/**' \
    ':(exclude,glob)**/__pycache__/**' \
    ':(exclude,glob).pytest_cache/**' \
    ':(exclude,glob)node_modules/**' \
    ':(exclude,glob).venv/**' \
    ':(exclude,glob)venv/**'
}

assert_clean_worktree() {
  repo="$1"
  dirty="$(git -C "$repo" status --porcelain=v1 --untracked-files=all)" || return 1
  if test -n "$dirty"; then
    echo "BLOCKED: dirty worktree: $repo" >&2
    printf '%s\n' "$dirty" >&2
    return 1
  fi
  ignored="$(ignored_executable_inputs "$repo")" || return 1
  if test -n "$ignored"; then
    echo "BLOCKED: ignored executable or test inputs: $repo" >&2
    printf '%s\n' "$ignored" >&2
    return 1
  fi
}
# END ORCHE_CLEAN_WORKTREE_GUARD

assert_clean_worktree "$BASELINE_ROOT"
assert_clean_worktree "$CANDIDATE_ROOT"
rm -rf "$OUTPUT_ROOT/runs"
mkdir -p "$OUTPUT_ROOT/runs"

run_isolated() {
  lane="$1"
  repo="$2"
  shift 2
  lane_root="$OUTPUT_ROOT/runs/$lane"
  rm -rf "$lane_root"
  mkdir -p "$lane_root/home" "$lane_root/tmp" "$lane_root/appdata" \
    "$lane_root/localappdata" "$lane_root/xdg-config" "$lane_root/xdg-cache" \
    "$lane_root/xdg-data" "$lane_root/xdg-state" "$lane_root/codex" \
    "$lane_root/claude" "$lane_root/gemini" "$lane_root/qwen" "$lane_root/kimi"
  : > "$lane_root/gitconfig"
  (
    cd "$repo"
    env -i \
      PATH="$VERIFIER_PATH" LANG="${LANG:-C}" LC_ALL="${LC_ALL:-C}" \
      HOME="$lane_root/home" USERPROFILE="$lane_root/home" \
      APPDATA="$lane_root/appdata" LOCALAPPDATA="$lane_root/localappdata" \
      XDG_CONFIG_HOME="$lane_root/xdg-config" XDG_CACHE_HOME="$lane_root/xdg-cache" \
      XDG_DATA_HOME="$lane_root/xdg-data" XDG_STATE_HOME="$lane_root/xdg-state" \
      CODEX_HOME="$lane_root/codex" CLAUDE_CONFIG_DIR="$lane_root/claude" \
      GEMINI_HOME="$lane_root/gemini" QWEN_CODE_HOME="$lane_root/qwen" \
      KIMI_CODE_HOME="$lane_root/kimi" TMPDIR="$lane_root/tmp" \
      GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL="$lane_root/gitconfig" \
      PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 CI=1 \
      "$@"
  )
}
```

The ambient `PATH`, `PYTHONPATH`, `PYTHONHOME`, activated virtual environment, and user plugin
configuration are not inherited. Both lanes use the same explicitly selected external verifier
Python and system command path.

## Pytest differential

Remove old XML before starting and require each current process to produce a fresh report.
Only Pytest exit `0` (success) and `1` (test failures) are valid evidence. Operational exits
`2`, `3`, `4`, `5`, or unknown values block regardless of JUnit contents.

```bash
rm -f "$OUTPUT_ROOT/baseline.xml" "$OUTPUT_ROOT/candidate.xml" \
  "$OUTPUT_ROOT/pytest-comparison.json"
set +e
run_isolated pytest-baseline "$BASELINE_ROOT" \
  "$VERIFIER_PYTHON" -m pytest --junitxml="$OUTPUT_ROOT/baseline.xml"
baseline_exit=$?
run_isolated pytest-candidate "$CANDIDATE_ROOT" \
  "$VERIFIER_PYTHON" -m pytest --junitxml="$OUTPUT_ROOT/candidate.xml"
candidate_exit=$?
set -e
test -f "$OUTPUT_ROOT/baseline.xml"
test -f "$OUTPUT_ROOT/candidate.xml"

"$VERIFIER_PYTHON" "$TOOL_ROOT/compare_pytest_baseline.py" \
  --baseline-junit "$OUTPUT_ROOT/baseline.xml" \
  --candidate-junit "$OUTPUT_ROOT/candidate.xml" \
  --baseline-exit "$baseline_exit" \
  --candidate-exit "$candidate_exit" \
  --baseline-ref "$BASELINE_REF" \
  --candidate-ref "$CANDIDATE_REF" \
  --output "$OUTPUT_ROOT/pytest-comparison.json"
```

## Validator command differential

Every repository-standard validator runs in both worktrees. Successful diagnostics must match,
and normalized logs are compared for failures **and successes**: a dropped success subcheck or
a newly emitted warning is drift unless declared as a narrow volatile pattern.

```bash
compare_validator() {
  name="$1"
  shift
  baseline_log="$OUTPUT_ROOT/$name-baseline.log"
  candidate_log="$OUTPUT_ROOT/$name-candidate.log"
  set +e
  run_isolated "$name-baseline" "$BASELINE_ROOT" "$@" >"$baseline_log" 2>&1
  baseline_exit=$?
  run_isolated "$name-candidate" "$CANDIDATE_ROOT" "$@" >"$candidate_log" 2>&1
  candidate_exit=$?
  set -e
  volatile_args=()
  if test "$name" = agents-mode-installers; then
    volatile_args=(--volatile-pattern 'agents-mode-installer-regression[/\\][0-9a-f]{32}')
  fi
  "$VERIFIER_PYTHON" "$TOOL_ROOT/compare_command_baseline.py" \
    --name "$name" \
    --baseline-exit "$baseline_exit" --candidate-exit "$candidate_exit" \
    --baseline-log "$baseline_log" --candidate-log "$candidate_log" \
    --baseline-root "$BASELINE_ROOT" --candidate-root "$CANDIDATE_ROOT" \
    --baseline-ref "$BASELINE_REF" --candidate-ref "$CANDIDATE_REF" \
    --output "$OUTPUT_ROOT/$name-comparison.json" \
    "${volatile_args[@]}"
}

compare_validator agents-spine \
  "$VERIFIER_PYTHON" scripts/validate-agents-spine.py --spine shared/AGENTS.shared.md
compare_validator codex-pack \
  "$VERIFIER_BASH" src.codex/skills/lead/scripts/validate-skill-pack.sh
compare_validator claude-pack \
  "$VERIFIER_BASH" src.claude/agents/scripts/validate-skill-pack.sh
compare_validator gemini-pack \
  "$VERIFIER_BASH" src.gemini/scripts/validate-pack.sh
compare_validator qwen-pack \
  "$VERIFIER_BASH" src.qwen/scripts/validate-pack.sh
compare_validator agents-mode-docs \
  "$VERIFIER_PYTHON" scripts/sync-agents-mode-docs.py --root . --check
compare_validator universal-hooks \
  "$VERIFIER_PYTHON" scripts/sync-universal-hooks.py --check
compare_validator agents-mode-installers \
  "$VERIFIER_PYTHON" scripts/validate-agents-mode-installers.py --root .
```

## Committed files

- `baseline-pin.json` — immutable baseline identity and frozen tool blob identities.
- `README.md` — reproduction and acceptance instructions.
- `tooling/*.py` — frozen, reviewed Stage 0 implementations used to generate and compare evidence.

Generated inventories, summaries, manifests, logs, and comparison reports remain local under
`.scratch/orche-stage0/` and are not committed.

## Signed tag publication gate

The pin is not a cryptographic signature. Before any tag push:

1. Stage the exact accepted tracked change in a clean publication-review checkout.
2. `$lead` runs `python scripts/check-publication-gate.py`, `git diff --cached --check`, and a
   human leak review of the staged diff.
3. A distinct human `$knowledge-archivist` records publication approval. An exception, if any,
   requires `$security-reviewer`; author self-check is insufficient.
4. Confirm the approved destination is exactly
   `refs/tags/orchestrarium-v1-parity-baseline` and no tracked bytes changed after approval.

Only after those gates pass may the repository owner run:

```bash
git tag -s orchestrarium-v1-parity-baseline \
  ce2052fb773576fd6e3206c2a7e21e01852d556b \
  -m "Immutable Orchestrarium V1 parity baseline for Orche 2.0"
git tag -v orchestrarium-v1-parity-baseline
git push origin refs/tags/orchestrarium-v1-parity-baseline:refs/tags/orchestrarium-v1-parity-baseline
```

Until the tag exists and verifies, the cryptographic Stage 0 gate remains `BLOCKED`.

## Terms and Abbreviations

- **CLI:** Command-Line Interface, a program operated through terminal commands.
- **GPG:** GNU Privacy Guard, a tool and key format for cryptographically signed Git tags.
- **JUnit XML:** machine-readable test results consumed by the differential comparator.
- **PATH:** the operating-system search list used to resolve executable commands.
- **POSIX:** Portable Operating System Interface, the shell model used by the example.
- **Pytest:** the Python test runner used for repository suites.
- **SHA-256:** Secure Hash Algorithm 256-bit, a content digest.
- **SSH:** Secure Shell, whose key format can also sign Git tags.
- **UUID:** Universally Unique Identifier, used by an existing validator for scratch paths.
- **V1:** Version 1, the accepted legacy behavior frozen before Orche 2.0 migration.

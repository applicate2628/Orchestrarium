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

`baseline-pin.json` records the owning commit and Git blob identifiers of both generators
and both differential comparators. Materialize those exact implementations before producing
or comparing evidence; do not invoke whatever version happens to exist in a later working tree.

```bash
CANDIDATE_ROOT=/absolute/path/to/candidate-worktree
PIN_PATH="$CANDIDATE_ROOT/baseline/orchestrarium-v1/baseline-pin.json"
OUTPUT_ROOT="$CANDIDATE_ROOT/.scratch/orche-stage0/differential"
TOOL_ROOT="$OUTPUT_ROOT/tools"
mkdir -p "$TOOL_ROOT"

pin_value() {
  python - "$PIN_PATH" "$1" <<'PY'
import json
import sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
for part in sys.argv[2].split("."):
    value = value[part]
print(value)
PY
}

materialize_tool() {
  key="$1"
  output="$2"
  owner="$(pin_value "tooling.$key.owningCommit")"
  blob="$(pin_value "tooling.$key.gitBlobSha")"
  test "$(git -C "$CANDIDATE_ROOT" rev-parse --verify "$owner^{commit}")" = "$owner"
  test "$(git -C "$CANDIDATE_ROOT" cat-file -t "$blob")" = blob
  test "$(git -C "$CANDIDATE_ROOT" ls-tree "$owner" -- "$(pin_value "tooling.$key.path")" | awk '{print $3}')" = "$blob"
  git -C "$CANDIDATE_ROOT" cat-file blob "$blob" > "$output"
}

materialize_tool inventoryGenerator "$TOOL_ROOT/build_inventory.py"
materialize_tool targetEffectGenerator "$TOOL_ROOT/build_target_effect_baseline.py"
materialize_tool pytestComparator "$TOOL_ROOT/compare_pytest_baseline.py"
materialize_tool commandComparator "$TOOL_ROOT/compare_command_baseline.py"
```

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

Generate evidence with the materialized pinned tools:

```bash
PIN_COMMIT="$(pin_value baseline.commitSha)"
rm -rf "$OUTPUT_ROOT/evidence"
python "$TOOL_ROOT/build_inventory.py" \
  --repo-root "$CANDIDATE_ROOT" \
  --repository applicate2628/Orchestrarium \
  --ref "$PIN_COMMIT" \
  --output-dir "$OUTPUT_ROOT/evidence"
python "$TOOL_ROOT/build_target_effect_baseline.py" \
  --inventory "$OUTPUT_ROOT/evidence/capability-inventory.json" \
  --output "$OUTPUT_ROOT/evidence/target-effect-baseline.json"
```

## Isolated baseline and candidate runs

Use clean worktrees. Derive the reported refs from the worktrees that are actually tested,
and fail if the baseline worktree does not match the pin.

```bash
BASELINE_ROOT=/absolute/path/to/baseline-worktree
CANDIDATE_ROOT=/absolute/path/to/candidate-worktree
PIN_PATH="$CANDIDATE_ROOT/baseline/orchestrarium-v1/baseline-pin.json"
OUTPUT_ROOT="$CANDIDATE_ROOT/.scratch/orche-stage0/differential"
PIN_COMMIT="$(pin_value baseline.commitSha)"
PIN_TREE="$(pin_value baseline.treeSha)"
BASELINE_REF="$(git -C "$BASELINE_ROOT" rev-parse HEAD)"
BASELINE_TREE="$(git -C "$BASELINE_ROOT" rev-parse 'HEAD^{tree}')"
CANDIDATE_REF="$(git -C "$CANDIDATE_ROOT" rev-parse HEAD)"
test "$BASELINE_REF" = "$PIN_COMMIT"
test "$BASELINE_TREE" = "$PIN_TREE"
test -z "$(git -C "$BASELINE_ROOT" status --porcelain=v1 --untracked-files=all)"
test -z "$(git -C "$CANDIDATE_ROOT" status --porcelain=v1 --untracked-files=all)"
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
      PATH="$PATH" LANG="${LANG:-C}" LC_ALL="${LC_ALL:-C}" \
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

Run Pytest in both lanes and feed both process exit codes into the pinned comparator. Remove
old XML before starting and require each current process to produce a fresh report.

```bash
rm -f "$OUTPUT_ROOT/baseline.xml" "$OUTPUT_ROOT/candidate.xml" \
  "$OUTPUT_ROOT/pytest-comparison.json"
set +e
run_isolated pytest-baseline "$BASELINE_ROOT" \
  python -m pytest --junitxml="$OUTPUT_ROOT/baseline.xml"
baseline_exit=$?
run_isolated pytest-candidate "$CANDIDATE_ROOT" \
  python -m pytest --junitxml="$OUTPUT_ROOT/candidate.xml"
candidate_exit=$?
set -e
test -f "$OUTPUT_ROOT/baseline.xml"
test -f "$OUTPUT_ROOT/candidate.xml"

python "$TOOL_ROOT/compare_pytest_baseline.py" \
  --baseline-junit "$OUTPUT_ROOT/baseline.xml" \
  --candidate-junit "$OUTPUT_ROOT/candidate.xml" \
  --baseline-exit "$baseline_exit" \
  --candidate-exit "$candidate_exit" \
  --baseline-ref "$BASELINE_REF" \
  --candidate-ref "$CANDIDATE_REF" \
  --output "$OUTPUT_ROOT/pytest-comparison.json"
```

Existing baseline failures may resolve. New failures, disappeared tests, failures hidden by
skip, changed failure/error kinds, regressions of previously passing tests, contradictory
exit/JUnit evidence, and newly changed nonzero Pytest exits block.

## Validator command differential

Run every repository-standard validator in both worktrees and compare exit codes and
diagnostics. The installer validator declares its UUID scratch component as volatile; no
other text is discarded.

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
  if [ "$name" = agents-mode-installers ]; then
    volatile_args=(
      --volatile-pattern 'agents-mode-installer-regression[/\\][0-9a-f]{32}'
    )
  fi
  python "$TOOL_ROOT/compare_command_baseline.py" \
    --name "$name" \
    --baseline-exit "$baseline_exit" --candidate-exit "$candidate_exit" \
    --baseline-log "$baseline_log" --candidate-log "$candidate_log" \
    --baseline-root "$BASELINE_ROOT" --candidate-root "$CANDIDATE_ROOT" \
    --baseline-ref "$BASELINE_REF" --candidate-ref "$CANDIDATE_REF" \
    --output "$OUTPUT_ROOT/$name-comparison.json" \
    "${volatile_args[@]}"
}

compare_validator agents-spine \
  python scripts/validate-agents-spine.py --spine shared/AGENTS.shared.md
compare_validator codex-pack \
  bash src.codex/skills/lead/scripts/validate-skill-pack.sh
compare_validator claude-pack \
  bash src.claude/agents/scripts/validate-skill-pack.sh
compare_validator gemini-pack \
  bash src.gemini/scripts/validate-pack.sh
compare_validator qwen-pack \
  bash src.qwen/scripts/validate-pack.sh
compare_validator agents-mode-docs \
  python scripts/sync-agents-mode-docs.py --root . --check
compare_validator universal-hooks \
  python scripts/sync-universal-hooks.py --check
compare_validator agents-mode-installers \
  python scripts/validate-agents-mode-installers.py --root .
```

## Committed files

- `baseline-pin.json` — immutable commit/tree and Stage 0 tool-blob identities.
- `README.md` — reproduction and acceptance instructions.

Generated inventories, summaries, manifests, logs, and comparison reports remain local under
`.scratch/orche-stage0/` and are not committed.

## Signed tag publication gate

The pin is not a cryptographic signature. The commands below are **not** authorization to
publish. Before any tag push:

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
- **POSIX:** Portable Operating System Interface, the shell model used by the example.
- **Pytest:** the Python test runner used for repository suites.
- **SHA-256:** Secure Hash Algorithm 256-bit, a content digest.
- **SSH:** Secure Shell, whose key format can also sign Git tags.
- **UUID:** Universally Unique Identifier, used by an existing validator for scratch paths.
- **V1:** Version 1, the accepted legacy behavior frozen before Orche 2.0 migration.

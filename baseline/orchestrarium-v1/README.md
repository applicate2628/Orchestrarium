# Orchestrarium Version 1 (V1) parity baseline

Stage 0 freezes accepted behavior before Orche 2.0 changes.

## Immutable source

- Repository: `applicate2628/Orchestrarium`
- Source branch: `main`
- Commit: `ce2052fb773576fd6e3206c2a7e21e01852d556b`
- Tree: `04dccf4575f17c9c5533474d2e0fd1503bfeceb7`
- Intended signed tag: `orchestrarium-v1-parity-baseline`

The pin is independent of every pull-request branch.

## Trusted local verifier

Use two clean worktrees and an exact full candidate commit. All verifier executables must be outside both worktrees.

```bash
set -euo pipefail
BASELINE_ROOT=/absolute/path/to/baseline-worktree
CANDIDATE_ROOT=/absolute/path/to/candidate-worktree
REVIEWED_REF=<exact-40-character-candidate-commit-sha>
BASELINE_ROOT="$(cd "$BASELINE_ROOT" && pwd -P)"
CANDIDATE_ROOT="$(cd "$CANDIDATE_ROOT" && pwd -P)"
VERIFIER_PYTHON="${VERIFIER_PYTHON:-$(command -v python3 || command -v python)}"
VERIFIER_GIT="${VERIFIER_GIT:-$(command -v git)}"
VERIFIER_BASH="${VERIFIER_BASH:-$(command -v bash)}"
assert_external_tool() {
  tool="$1"; test -n "$tool" && test -x "$tool" || { echo "BLOCKED: verifier executable unavailable: $tool" >&2; return 1; }
  tool_dir="${tool%/*}"; tool_base="${tool##*/}"; tool_path="$(cd "$tool_dir" && pwd -P)/$tool_base"
  case "$tool_path" in "$BASELINE_ROOT"/*|"$CANDIDATE_ROOT"/*) echo "BLOCKED: verifier executable is inside a tested worktree: $tool_path" >&2; return 1;; esac
}
assert_external_tool "$VERIFIER_PYTHON" || exit 1
assert_external_tool "$VERIFIER_GIT" || exit 1
assert_external_tool "$VERIFIER_BASH" || exit 1
VERIFIER_PATH="${VERIFIER_PYTHON%/*}:${VERIFIER_GIT%/*}:${VERIFIER_BASH%/*}:/usr/local/bin:/usr/bin:/bin"
export PATH="$VERIFIER_PATH"

# BEGIN ORCHE_CLEAN_WORKTREE_GUARD
ignored_executable_inputs() {
  repo="$1"
  "$VERIFIER_GIT" -C "$repo" ls-files --others --ignored --exclude-standard -- \
    ':(glob)tests/**' ':(glob)**/conftest.py' ':(glob)scripts/**' ':(glob)**/*.py' \
    ':(glob)**/*.pyc' ':(glob)**/*.pyo' ':(glob)**/__pycache__/**' \
    ':(glob)**/*.sh' ':(glob)**/*.ps1' ':(glob)**/pyproject.toml' \
    ':(glob)**/pytest.ini' ':(glob)**/tox.ini' ':(glob)**/setup.cfg' \
    ':(exclude,glob).scratch/**' ':(exclude,glob).pytest_cache/**' \
    ':(exclude,glob)node_modules/**' ':(exclude,glob).venv/**' ':(exclude,glob)venv/**'
}
assert_clean_worktree() {
  repo="$1"
  dirty="$("$VERIFIER_GIT" -C "$repo" status --porcelain=v1 --untracked-files=all)" || return 1
  test -z "$dirty" || { echo "BLOCKED: dirty worktree: $repo" >&2; printf '%s\n' "$dirty" >&2; return 1; }
  ignored="$(ignored_executable_inputs "$repo")" || return 1
  test -z "$ignored" || { echo "BLOCKED: ignored executable or test inputs: $repo" >&2; printf '%s\n' "$ignored" >&2; return 1; }
}
# END ORCHE_CLEAN_WORKTREE_GUARD

assert_clean_worktree "$BASELINE_ROOT" || exit 1
assert_clean_worktree "$CANDIDATE_ROOT" || exit 1
PIN_PATH="$CANDIDATE_ROOT/baseline/orchestrarium-v1/baseline-pin.json"
OUTPUT_ROOT="$CANDIDATE_ROOT/.scratch/orche-stage0/differential"
TOOL_ROOT="$OUTPUT_ROOT/tools"
pin_value() {
  "$VERIFIER_PYTHON" - "$PIN_PATH" "$1" <<'PY'
import json,sys
value=json.load(open(sys.argv[1],encoding="utf-8"))
for part in sys.argv[2].split("."): value=value[part]
print(value)
PY
}
PIN_COMMIT="$(pin_value baseline.commitSha)"; PIN_TREE="$(pin_value baseline.treeSha)"
BASELINE_REF="$("$VERIFIER_GIT" -C "$BASELINE_ROOT" rev-parse HEAD)"
BASELINE_TREE="$("$VERIFIER_GIT" -C "$BASELINE_ROOT" rev-parse 'HEAD^{tree}')"

# BEGIN ORCHE_REVIEWED_CANDIDATE_GUARD
REVIEWED_REF_INPUT="${REVIEWED_REF:?set REVIEWED_REF to the exact full candidate commit SHA under review}"
RESOLVED_REVIEWED_REF="$("$VERIFIER_GIT" -C "$CANDIDATE_ROOT" rev-parse --verify "$REVIEWED_REF_INPUT^{commit}")" || { echo "BLOCKED: REVIEWED_REF cannot be resolved in the candidate repository" >&2; exit 1; }
test "$REVIEWED_REF_INPUT" = "$RESOLVED_REVIEWED_REF" || { echo "BLOCKED: REVIEWED_REF must be the exact full candidate commit SHA" >&2; exit 1; }
REVIEWED_REF="$RESOLVED_REVIEWED_REF"
CANDIDATE_REF="$("$VERIFIER_GIT" -C "$CANDIDATE_ROOT" rev-parse HEAD)"
test "$CANDIDATE_REF" = "$REVIEWED_REF" || { echo "BLOCKED: candidate worktree HEAD does not match REVIEWED_REF" >&2; exit 1; }
test "$CANDIDATE_REF" != "$PIN_COMMIT" || { echo "BLOCKED: candidate ref resolves to the pinned baseline" >&2; exit 1; }
# END ORCHE_REVIEWED_CANDIDATE_GUARD

test "$BASELINE_REF" = "$PIN_COMMIT" || { echo "BLOCKED: baseline worktree ref does not match pinned commit" >&2; exit 1; }
test "$BASELINE_TREE" = "$PIN_TREE" || { echo "BLOCKED: baseline worktree tree does not match pinned tree" >&2; exit 1; }
EVIDENCE_ROOT="$CANDIDATE_ROOT/$(pin_value evidence.generatedOutputDirectory)"
mkdir -p "$TOOL_ROOT" "$EVIDENCE_ROOT" "$OUTPUT_ROOT/runs"
ORCHE_COMMAND_TIMEOUT_SECONDS="${ORCHE_COMMAND_TIMEOUT_SECONDS:-900}"
test "$ORCHE_COMMAND_TIMEOUT_SECONDS" -gt 0 2>/dev/null || { echo "BLOCKED: ORCHE_COMMAND_TIMEOUT_SECONDS must be a positive integer" >&2; exit 1; }
run_isolated() {
  lane="$1"; repo="$2"; shift 2; lane_root="$OUTPUT_ROOT/runs/$lane"; rm -rf "$lane_root"
  mkdir -p "$lane_root/home" "$lane_root/tmp" "$lane_root/appdata" "$lane_root/localappdata" \
    "$lane_root/xdg-config" "$lane_root/xdg-cache" "$lane_root/xdg-data" "$lane_root/xdg-state" \
    "$lane_root/codex" "$lane_root/claude" "$lane_root/gemini" "$lane_root/qwen" "$lane_root/kimi"
  : > "$lane_root/gitconfig"
  (cd "$repo" && env -i PATH="$VERIFIER_PATH" LANG="${LANG:-C}" LC_ALL="${LC_ALL:-C}" \
    HOME="$lane_root/home" USERPROFILE="$lane_root/home" APPDATA="$lane_root/appdata" LOCALAPPDATA="$lane_root/localappdata" \
    XDG_CONFIG_HOME="$lane_root/xdg-config" XDG_CACHE_HOME="$lane_root/xdg-cache" XDG_DATA_HOME="$lane_root/xdg-data" XDG_STATE_HOME="$lane_root/xdg-state" \
    CODEX_HOME="$lane_root/codex" CLAUDE_CONFIG_DIR="$lane_root/claude" GEMINI_HOME="$lane_root/gemini" QWEN_CODE_HOME="$lane_root/qwen" KIMI_CODE_HOME="$lane_root/kimi" \
    TMPDIR="$lane_root/tmp" GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL="$lane_root/gitconfig" \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 CI=1 \
    "$VERIFIER_PYTHON" - "$ORCHE_COMMAND_TIMEOUT_SECONDS" "$@" <<'PY'
# BEGIN ORCHE_TIMEOUT_RUNNER
import os,shlex,signal,subprocess,sys
timeout=float(sys.argv[1]); command=sys.argv[2:]
if timeout<=0 or not command:
 print("BLOCKED: invalid timeout runner arguments",file=sys.stderr); raise SystemExit(2)
try: process=subprocess.Popen(command,start_new_session=True)
except FileNotFoundError as exc:
 print(f"BLOCKED: command executable not found: {command[0]!r}: {exc}",file=sys.stderr); raise SystemExit(127)
except OSError as exc:
 print(f"BLOCKED: command launch failed: {command[0]!r}: {exc}",file=sys.stderr); raise SystemExit(126)
def terminate_group():
 try: os.killpg(process.pid,signal.SIGTERM)
 except OSError: return
 try: process.wait(timeout=5)
 except subprocess.TimeoutExpired: pass
 try: os.killpg(process.pid,signal.SIGKILL)
 except OSError: pass
 if process.poll() is None: process.wait()
try: return_code=process.wait(timeout=timeout)
except subprocess.TimeoutExpired:
 print("BLOCKED: command timed out after "+f"{timeout:g}s: {' '.join(shlex.quote(part) for part in command)}",file=sys.stderr); terminate_group(); raise SystemExit(124)
except BaseException: terminate_group(); raise
raise SystemExit(return_code)
# END ORCHE_TIMEOUT_RUNNER
PY
  )
}
```

The active guard intentionally omits the historical cache-directory exclusion. Ignored Python bytecode is scanned positively. The isolated lanes do not inherit `PYTHONPATH`, `PYTHONHOME`, virtual-environment state, user plugins, application homes, or Git configuration.

## Frozen tooling and focused tests

`baseline-pin.json` binds every frozen path to a Git blob and `git-cat-file-reviewed-tree-blob` materialization. Generated manifests identify the frozen inventory generator by stable path and self-computed blob; `sourcePath` records separate mutable development provenance.

```bash
materialize_tool() {
  key="$1"; output="$2"; frozen_path="$(pin_value "tooling.$key.path")"; blob="$(pin_value "tooling.$key.gitBlobSha")"
  test "$("$VERIFIER_GIT" -C "$CANDIDATE_ROOT" cat-file -t "$blob")" = blob || return 1
  tree_entry="$("$VERIFIER_GIT" -C "$CANDIDATE_ROOT" ls-tree "$REVIEWED_REF" -- "$frozen_path")" || return 1
  actual_blob="$(printf '%s\n' "$tree_entry" | "$VERIFIER_PYTHON" -c 'import sys; print(sys.stdin.read().split(None,3)[2])')" || return 1
  test "$actual_blob" = "$blob" || return 1
  "$VERIFIER_GIT" -C "$CANDIDATE_ROOT" cat-file blob "$blob" > "$output"
}
materialize_tool inventoryGenerator "$TOOL_ROOT/build_inventory.py" || exit 1
materialize_tool targetEffectGenerator "$TOOL_ROOT/build_target_effect_baseline.py" || exit 1
materialize_tool pytestComparator "$TOOL_ROOT/compare_pytest_baseline.py" || exit 1
materialize_tool commandComparator "$TOOL_ROOT/compare_command_baseline.py" || exit 1
run_isolated focused-pin "$CANDIDATE_ROOT" "$VERIFIER_PYTHON" tests/test_orche_baseline_pin.py
run_isolated focused-pytest "$CANDIDATE_ROOT" "$VERIFIER_PYTHON" tests/test_orche_pytest_baseline.py
run_isolated focused-inventory "$CANDIDATE_ROOT" "$VERIFIER_PYTHON" tests/test_orche_baseline_inventory.py
run_isolated focused-target-effect "$CANDIDATE_ROOT" "$VERIFIER_PYTHON" tests/test_orche_target_effect_baseline.py
run_isolated focused-command "$CANDIDATE_ROOT" "$VERIFIER_PYTHON" tests/test_orche_command_baseline.py
run_isolated focused-verifier-isolation "$CANDIDATE_ROOT" "$VERIFIER_PYTHON" tests/test_orche_verifier_isolation.py
run_isolated focused-review-regressions "$CANDIDATE_ROOT" "$VERIFIER_PYTHON" tests/test_orche_review_regressions.py
```

Stage 0 intentionally does **not** use GitHub Actions. Evidence remains uncommitted under `.scratch/`.

```bash
rm -rf "$EVIDENCE_ROOT"; mkdir -p "$EVIDENCE_ROOT"
"$VERIFIER_PYTHON" "$TOOL_ROOT/build_inventory.py" --repo-root "$CANDIDATE_ROOT" --repository applicate2628/Orchestrarium --ref "$PIN_COMMIT" --output-dir "$EVIDENCE_ROOT"
"$VERIFIER_PYTHON" "$TOOL_ROOT/build_target_effect_baseline.py" --inventory "$EVIDENCE_ROOT/capability-inventory.json" --output "$EVIDENCE_ROOT/target-effect-baseline.json"
```

## Pytest differential

Only Pytest exits `0` and `1` are comparable; operational exits, timeout `124`, missing fresh JUnit XML, and inconsistent exit/report states block. Successful diagnostics are compared as well as failures.

```bash
rm -f "$OUTPUT_ROOT/baseline.xml" "$OUTPUT_ROOT/candidate.xml" "$OUTPUT_ROOT/pytest-comparison.json"
set +e
run_isolated pytest-baseline "$BASELINE_ROOT" "$VERIFIER_PYTHON" -m pytest --junitxml="$OUTPUT_ROOT/baseline.xml"; baseline_exit=$?
set -e
test "$baseline_exit" -ne 124 || { echo "BLOCKED: baseline Pytest lane timed out" >&2; exit 2; }
set +e
run_isolated pytest-candidate "$CANDIDATE_ROOT" "$VERIFIER_PYTHON" -m pytest --junitxml="$OUTPUT_ROOT/candidate.xml"; candidate_exit=$?
set -e
test "$candidate_exit" -ne 124 || { echo "BLOCKED: candidate Pytest lane timed out" >&2; exit 2; }
test -f "$OUTPUT_ROOT/baseline.xml" || exit 2
test -f "$OUTPUT_ROOT/candidate.xml" || exit 2
"$VERIFIER_PYTHON" "$TOOL_ROOT/compare_pytest_baseline.py" \
  --baseline-junit "$OUTPUT_ROOT/baseline.xml" --candidate-junit "$OUTPUT_ROOT/candidate.xml" \
  --baseline-exit "$baseline_exit" --candidate-exit "$candidate_exit" \
  --baseline-ref "$BASELINE_REF" --candidate-ref "$CANDIDATE_REF" \
  --baseline-root "$BASELINE_ROOT" --candidate-root "$CANDIDATE_ROOT" \
  --volatile-pattern 'agents-mode-installer-regression[/\\][0-9a-f]{32}' \
  --output "$OUTPUT_ROOT/pytest-comparison.json"
```

## Validator command differential

Successful diagnostics and failure diagnostics are both compared. Operational exits always block. A historical failure resolves only when the candidate emits the validator-specific terminal marker; an empty or unconditional `exit 0` is not evidence.

```bash
compare_validator() {
  name="$1"; success_pattern="$2"; shift 2
  baseline_log="$OUTPUT_ROOT/$name-baseline.log"; candidate_log="$OUTPUT_ROOT/$name-candidate.log"
  set +e; run_isolated "$name-baseline" "$BASELINE_ROOT" "$@" >"$baseline_log" 2>&1; baseline_exit=$?; set -e
  test "$baseline_exit" -ne 124 || { echo "BLOCKED: baseline validator timed out: $name" >&2; return 2; }
  set +e; run_isolated "$name-candidate" "$CANDIDATE_ROOT" "$@" >"$candidate_log" 2>&1; candidate_exit=$?; set -e
  test "$candidate_exit" -ne 124 || { echo "BLOCKED: candidate validator timed out: $name" >&2; return 2; }
  volatile_args=(); test "$name" != agents-mode-installers || volatile_args=(--volatile-pattern 'agents-mode-installer-regression[/\\][0-9a-f]{32}')
  "$VERIFIER_PYTHON" "$TOOL_ROOT/compare_command_baseline.py" --name "$name" \
    --baseline-exit "$baseline_exit" --candidate-exit "$candidate_exit" \
    --baseline-log "$baseline_log" --candidate-log "$candidate_log" \
    --baseline-root "$BASELINE_ROOT" --candidate-root "$CANDIDATE_ROOT" \
    --baseline-ref "$BASELINE_REF" --candidate-ref "$CANDIDATE_REF" \
    --success-pattern "$success_pattern" --semantic-failure-exit 1 \
    --output "$OUTPUT_ROOT/$name-comparison.json" "${volatile_args[@]}"
}
compare_validator agents-spine '(?m)^RESULT: PASS$' "$VERIFIER_PYTHON" scripts/validate-agents-spine.py --spine shared/AGENTS.shared.md
compare_validator codex-pack '(?m)^VALIDATION PASSED(?: \(with warnings\))?$' "$VERIFIER_BASH" src.codex/skills/lead/scripts/validate-skill-pack.sh
compare_validator claude-pack '(?m)^\s*RESULT: PASS(?: with warnings)?$' "$VERIFIER_BASH" src.claude/agents/scripts/validate-skill-pack.sh
compare_validator gemini-pack '(?m)^PASS: Gemini .+ tree present at .+$' "$VERIFIER_BASH" src.gemini/scripts/validate-pack.sh
compare_validator qwen-pack '(?m)^PASS: Qwen .+ tree present at .+$' "$VERIFIER_BASH" src.qwen/scripts/validate-pack.sh
compare_validator agents-mode-docs '(?m)^PASS: agents-mode docs are synced$' "$VERIFIER_PYTHON" scripts/sync-agents-mode-docs.py --root . --check
compare_validator universal-hooks '(?m)^PASS: universal-hooks\b.*$' "$VERIFIER_PYTHON" scripts/sync-universal-hooks.py --check
compare_validator agents-mode-installers '(?m)^PASS: agents-mode installer regression validated$' "$VERIFIER_PYTHON" scripts/validate-agents-mode-installers.py --root .
```

## Publication gate

A distinct human `$knowledge-archivist` must approve after `$lead` runs `python scripts/check-publication-gate.py`, `git diff --cached --check`, and leak review. Only then may the owner create and verify the signed tag and run `git push origin refs/tags/orchestrarium-v1-parity-baseline:refs/tags/orchestrarium-v1-parity-baseline`.

## Terms and Abbreviations

- **Bash:** Bourne Again Shell.
- **CLI:** Command-Line Interface.
- **GPG:** GNU Privacy Guard.
- **Git blob:** immutable Git file-content object.
- **JUnit XML:** machine-readable test report.
- **PATH:** executable search list.
- **POSIX:** Portable Operating System Interface.
- **Pytest:** Python test runner.
- **SHA-256:** Secure Hash Algorithm 256-bit.
- **SSH:** Secure Shell.
- **UUID:** Universally Unique Identifier.
- **V1:** Version 1.

#!/usr/bin/env bash
set -euo pipefail

repo="$(cd -P -- "$1" && printf '%s\n' "$PWD")"
script_dir="$(cd -P -- "$(dirname -- "$0")" && printf '%s\n' "$PWD")"

export PYTHONDONTWRITEBYTECODE=1
export PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
export TERM=dumb

apply_script=/tmp/orche-apply-review8.py
python3 - "$script_dir" "$apply_script" <<'PYDEC'
import base64
import gzip
import pathlib
import sys
source_dir = pathlib.Path(sys.argv[1])
destination = pathlib.Path(sys.argv[2])
parts = sorted(source_dir.glob("apply_review8.py.gz.b64.part-*"))
if not parts:
    raise SystemExit("review8 payload parts are missing")
encoded = "".join(part.read_text(encoding="ascii").strip() for part in parts)
compressed = base64.b64decode(encoded, validate=True)
destination.write_bytes(gzip.decompress(compressed))
PYDEC
python3 -m py_compile "$apply_script"

expected_head=498f7954a3a74525d237870fd1f1b30ac820c955
test "$(git -C "$repo" rev-parse HEAD)" = "$expected_head"
test -z "$(git -C "$repo" status --porcelain=v1)"

python3 "$apply_script" tests "$repo"
python3 -m py_compile \
  "$repo/tests/test_orche_verifier_isolation.py" \
  "$repo/tests/test_orche_review_regressions.py"

cd "$repo"
set +e
python3 tests/test_orche_verifier_isolation.py \
  VerifierIsolationTests.test_candidate_sessionfinish_cannot_forge_authenticated_outcomes \
  > /tmp/orche-review8-red-forgery.log 2>&1
red_forgery=$?
python3 tests/test_orche_verifier_isolation.py \
  VerifierIsolationTests.test_retained_files_run_in_one_full_pytest_session \
  > /tmp/orche-review8-red-session.log 2>&1
red_session=$?
python3 tests/test_orche_verifier_isolation.py \
  VerifierIsolationTests.test_private_temp_parent_requires_trusted_owner_and_sticky_protection \
  > /tmp/orche-review8-red-temp.log 2>&1
red_temp=$?
python3 tests/test_orche_review_regressions.py \
  ReviewRegressionTests.test_retained_pytest_uses_authenticated_full_session_and_safe_temp_parent \
  > /tmp/orche-review8-red-contract.log 2>&1
red_contract=$?
set -e

printf 'RED exit codes: forgery=%s session=%s temp=%s contract=%s\n' \
  "$red_forgery" "$red_session" "$red_temp" "$red_contract"
for value in "$red_forgery" "$red_session" "$red_temp" "$red_contract"; do
  if [ "$value" -eq 0 ]; then
    echo "RED verification failed: a new regression passed before implementation" >&2
    cat /tmp/orche-review8-red-*.log >&2
    exit 1
  fi
done
for log in /tmp/orche-review8-red-*.log; do
  test -s "$log"
done
echo "RED verified: terminal statistics are forgeable, retained files use separate processes, and shared temporary parents lack sticky validation"

cd ..
python3 "$apply_script" implement "$repo"
cd "$repo"

cmp scripts/baseline/stage0_evidence.py \
    baseline/orchestrarium-v1/tooling/stage0_evidence.py
cmp scripts/baseline/stage0_orchestrator.py \
    baseline/orchestrarium-v1/tooling/stage0_orchestrator.py

for test_file in \
  tests/test_orche_baseline_pin.py \
  tests/test_orche_pytest_baseline.py \
  tests/test_orche_baseline_inventory.py \
  tests/test_orche_target_effect_baseline.py \
  tests/test_orche_command_baseline.py \
  tests/test_orche_capability_baseline.py \
  tests/test_orche_verifier_isolation.py \
  tests/test_orche_review_regressions.py; do
  python3 "$test_file"
done

python3 - <<'PY'
from pathlib import Path
import json
import re
import subprocess
import tempfile

changed = subprocess.check_output(
    ["git", "diff", "--name-only", "--", "*.py"], text=True
).splitlines()
for name in changed:
    source = Path(name).read_text(encoding="utf-8")
    compile(source, name, "exec")

pin = json.loads(
    Path("baseline/orchestrarium-v1/baseline-pin.json").read_text(encoding="utf-8")
)
for key in ("stage0Evidence", "stage0Orchestrator"):
    record = pin["tooling"][key]
    actual = subprocess.check_output(
        ["git", "hash-object", record["path"]], text=True
    ).strip()
    assert actual == record["gitBlobSha"], (
        key,
        actual,
        record["gitBlobSha"],
    )

readme = Path("baseline/orchestrarium-v1/README.md").read_text(encoding="utf-8")
match = re.search(r"```bash\n(.*?)\n```", readme, re.S)
assert match
with tempfile.NamedTemporaryFile("w", suffix=".sh", delete=False) as handle:
    handle.write(match.group(1) + "\n")
    shell_path = handle.name
subprocess.run(["bash", "-n", shell_path], check=True)

evidence = Path("scripts/baseline/stage0_evidence.py").read_text(encoding="utf-8")
orchestrator = Path("scripts/baseline/stage0_orchestrator.py").read_text(
    encoding="utf-8"
)
for marker in (
    "_TRUSTED_PYTEST_RUNNER_SOURCE",
    "pytest_runtest_makereport",
    "hmac.new(",
    "_suspend_lane_processes(",
    "_resume_lane_processes(",
    "_validate_private_temp_parent",
):
    assert marker in evidence, marker
assert "_pytest_zero_exit_outcome_evidence" not in evidence
assert orchestrator.count("revalidate_worktrees=revalidate_pytest_worktrees") == 2
assert 'tempfile.mkdtemp(prefix="pytest-baseline-"' in orchestrator
assert 'tempfile.mkdtemp(prefix="pytest-candidate-"' in orchestrator
PY

find . -type d -name __pycache__ -prune -exec rm -rf {} +
git add -A

expected_paths=$(cat <<'EOF'
RELEASE_NOTES.md
baseline/orchestrarium-v1/README.md
baseline/orchestrarium-v1/baseline-pin.json
baseline/orchestrarium-v1/tooling/stage0_evidence.py
baseline/orchestrarium-v1/tooling/stage0_orchestrator.py
scripts/baseline/stage0_evidence.py
scripts/baseline/stage0_orchestrator.py
tests/test_orche_review_regressions.py
tests/test_orche_verifier_isolation.py
EOF
)
diff -u <(printf '%s\n' "$expected_paths" | sort) \
  <(git diff --cached --name-only | sort)
git diff --cached --check
python3 scripts/check-publication-gate.py

git config user.name 'github-actions[bot]'
git config user.email '41898282+github-actions[bot]@users.noreply.github.com'
git commit -m 'fix(stage0): authenticate full-suite pytest evidence'
git push origin HEAD:orche/impl-000-baseline
if [ -n "${GITHUB_STEP_SUMMARY:-}" ]; then
  echo "published_commit=$(git rev-parse HEAD)" >> "$GITHUB_STEP_SUMMARY"
fi

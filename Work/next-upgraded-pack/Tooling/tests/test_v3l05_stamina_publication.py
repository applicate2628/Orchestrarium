import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


BENCH_ROOT = Path(__file__).resolve().parents[4]
ADMISSION_ROOT = (
    BENCH_ROOT
    / "Work"
    / "next-upgraded-pack"
    / "Evidence"
    / "v3l05-stamina-admission"
)
SCENARIO_ROOT = BENCH_ROOT / "Scenarios-v3" / "V3L05-stamina-migration-l"
VERIFIER = SCENARIO_ROOT / "verifiers" / "check_stamina_migration.py"
TEMPLATE = ADMISSION_ROOT / "generate" / "check_stamina_migration.py"
PROJECTIONS = tuple(
    BENCH_ROOT
    / "Scenarios-v3"
    / f"V3L05-stamina-migration-{variant}"
    / "verifiers"
    / "check_stamina_migration.py"
    for variant in "sml"
)


def _score(candidate_root: Path, metrics_path: Path, env: dict[str, str]) -> dict:
    completed = subprocess.run(
        [
            sys.executable,
            str(VERIFIER),
            "--candidate-root",
            str(candidate_root),
            "--metrics-out",
            str(metrics_path),
        ],
        cwd=BENCH_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 1, completed.stdout
    return json.loads(metrics_path.read_text(encoding="utf-8"))


def _assert_stable_visible_log(payload: dict, workspace: Path) -> None:
    visible_log = payload["visible_log"]
    assert "candidate/workspace/tests/test_visible.py" in visible_log
    assert str(workspace.resolve()) not in visible_log
    assert workspace.resolve().as_posix() not in visible_log


def test_visible_log_uses_repo_logical_workspace_for_both_exec_topologies(tmp_path):
    in_tree_metrics = tmp_path / "in-tree.json"
    in_tree_payload = _score(
        SCENARIO_ROOT / "candidate",
        in_tree_metrics,
        os.environ.copy(),
    )
    _assert_stable_visible_log(
        in_tree_payload,
        SCENARIO_ROOT / "candidate" / "workspace",
    )

    exec_root = tmp_path / "exec-fixed"
    shutil.copytree(SCENARIO_ROOT / "candidate", exec_root / "candidate")
    exec_env = os.environ.copy()
    exec_env["BENCH_EXEC_ROOT"] = str(exec_root)
    exec_payload = _score(
        exec_root / "candidate",
        tmp_path / "exec-root.json",
        exec_env,
    )
    _assert_stable_visible_log(
        exec_payload,
        exec_root / "candidate" / "workspace",
    )


def test_canonical_template_matches_all_generated_verifiers():
    assert TEMPLATE.is_file()
    template_bytes = TEMPLATE.read_bytes()
    assert all(projection.read_bytes() == template_bytes for projection in PROJECTIONS)

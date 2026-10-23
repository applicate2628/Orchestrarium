"""Single test-only owner for complete git-push gate layouts."""

from __future__ import annotations

from pathlib import Path
from typing import NamedTuple


class GateTarget(NamedTuple):
    label: str
    runner_path: Path
    policy_path: Path
    preflight_path: Path
    common_path: Path


def target_for(label: str, script_dir: Path) -> GateTarget:
    return GateTarget(
        label,
        script_dir / "check-git-push-gate-runner.py",
        script_dir / "check-git-push-gate.py",
        script_dir / "git_push_gate_preflight.py",
        script_dir / "hook_common.py",
    )


def derive_pr_grant(policy, entries: list[dict], repository_workdir: str):
    """Drive the real reducer directly for semantic unit assertions."""
    reducer = policy._PrGrantReducer(repository_workdir)
    for entry in entries:
        reducer.consume(entry)
    return reducer.finish()

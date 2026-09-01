"""Phase A contracts for the future pre-action provider launcher."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MATRICES = (
    ROOT / "tests" / "fixtures" / "solution-attempt-v3" / "contract-matrices.json"
)


def _matrices() -> dict:
    return json.loads(MATRICES.read_text(encoding="utf-8"))


def _load_owner(path: Path, module_name: str, contract: str):
    if not path.is_file():
        pytest.fail(f"missing-contract: {path.relative_to(ROOT)} must own {contract}")
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.fail(f"missing-contract: cannot load owner {path.relative_to(ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_spawn_boundary_kill_matrix_has_every_barrier() -> None:
    assert _matrices()["launcherKillPoints"] == [
        "before-manifest",
        "after-manifest",
        "before-spawn-boundary",
        "after-spawn-boundary",
        "after-os-spawn",
        "before-authentication",
        "after-authentication",
        "before-go",
        "after-go",
        "before-terminal",
        "after-terminal",
        "before-reap",
        "after-reap",
    ]


def test_source_specific_terminal_outcomes_are_closed() -> None:
    rows = _matrices()["legalLaunchTransitions"]
    outcomes = {}
    for row in rows:
        outcomes.setdefault(row["source"], set()).add(row["outcome"])
    assert outcomes["CLAIMED_NO_SPAWN"] == {
        "spawn-boundary",
        "abandoned-before-spawn",
        "cancelled-before-spawn",
        "failed-before-spawn",
    }
    assert outcomes["SPAWNED_UNCONFIRMED"] == {
        "authenticated-start",
        "spawn-failed",
        "spawn-outcome-unknown",
        "cancelled-before-authentication",
        "timed-out-before-authentication",
        "unadoptable-child-terminated",
    }
    assert outcomes["STARTED"] == {
        "pass",
        "revise",
        "failed",
        "cancelled",
        "timed-out",
        "orphaned-after-start",
    }
    assert outcomes["TERMINAL"] == {"resources-absent"}


def test_cancel_timeout_requires_resource_census_before_reaped() -> None:
    resources = set(_matrices()["resourceCleanup"])
    assert "provider-process-tree" in resources
    assert {"stdin-pipe", "stdout-pipe", "stderr-pipe", "reader-thread"} <= resources
    assert "capability-token" in resources


def test_red_guarded_launcher_missing() -> None:
    owner = _load_owner(
        ROOT / "scripts" / "process_supervision" / "guarded_launcher.py",
        "guarded_provider_launcher_phase_a",
        "the authenticated pre-action barrier and process-tree supervisor",
    )
    assert callable(getattr(owner, "launch_guarded", None)), (
        "missing-contract: guarded_launcher.py must expose launch_guarded"
    )


def test_disabled_route_denies_before_process_factory_or_first_action() -> None:
    owner = _load_owner(
        ROOT / "scripts" / "process_supervision" / "guarded_launcher.py",
        "guarded_provider_launcher_disabled",
        "the authenticated pre-action barrier and process-tree supervisor",
    )
    calls = []

    def forbidden_process_factory(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("disabled route reached process creation")

    digest = "a" * 64
    decision = owner.launch_guarded(
        "codex.root",
        expected_binding=digest,
        observed_binding=digest,
        process_factory=forbidden_process_factory,
    )
    assert decision == {
        "result": "SOL-E007-ENFORCEMENT-UNAVAILABLE",
        "routeId": "codex.root",
        "started": False,
        "firstAction": False,
    }
    assert calls == []

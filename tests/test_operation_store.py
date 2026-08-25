"""Phase A contracts for the sole durable agent-run operation store."""

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


def test_persistence_kill_points_cover_every_commit_boundary() -> None:
    assert _matrices()["persistenceKillPoints"] == [
        "candidate-validated",
        "candidate-file-flushed",
        "candidate-replaced",
        "directory-flushed",
        "live-path-readback",
        "full-reduction-complete",
        "result-returned",
    ]


def test_operation_replay_conflict_and_uncertainty_matrix() -> None:
    cases = {
        row["case"]: row["expected"]
        for row in _matrices()["operationRecoveryCases"]
    }
    assert cases["exact-replay"] == "EXACT_REPLAY"
    assert cases["same-operation-different-payload"] == "SOL-E010-OPERATION-CONFLICT"
    assert cases["replacement-outcome-unknown"] == "SOL-E013-COMMIT-UNCERTAIN"
    assert cases["spawn-outcome-unknown"] == "NO_AUTO_RELAUNCH"
    assert {
        cases["pid-reuse"],
        cases["wrong-fence-token"],
        cases["aba-file-identity"],
    } == {"LOCK_TAKEOVER_DENIED"}


def test_owned_resource_census_is_explicit() -> None:
    resources = set(_matrices()["resourceCleanup"])
    assert {
        "ledger-lock",
        "candidate-file",
        "directory-handle",
        "registry-lock",
        "capability-token",
        "containment",
        "provider-process-tree",
        "stdin-pipe",
        "stdout-pipe",
        "stderr-pipe",
        "reader-thread",
        "cancellation-token",
    } == resources


def test_red_store_owner_missing() -> None:
    owner = _load_owner(
        ROOT / "scripts" / "agent_run_persistence" / "operation_store.py",
        "operation_store_phase_a",
        "the sole durable V1/V2/V3 writer and recovery protocol",
    )
    assert callable(getattr(owner, "commit_operation", None)), (
        "missing-contract: scripts/agent_run_persistence/operation_store.py must expose "
        "commit_operation"
    )


def test_disabled_route_denies_before_any_ledger_write(tmp_path: Path) -> None:
    owner = _load_owner(
        ROOT / "scripts" / "agent_run_persistence" / "operation_store.py",
        "operation_store_disabled",
        "the sole durable V1/V2/V3 writer and recovery protocol",
    )
    route_owner = _load_owner(
        ROOT / "scripts" / "process_supervision" / "route_activation_registry.py",
        "route_activation_registry_for_store",
        "the seven-route disabled-by-default activation registry",
    )
    digest = "a" * 64
    ledger = tmp_path / "agent-runs.jsonl"
    result = owner.commit_operation(
        ledger_path=ledger,
        reduction={"result": "SOL-OK", "changed": True, "state": {"head": digest}},
        route_check=route_owner.check_route(
            "codex.root",
            expected_binding=digest,
            observed_binding=digest,
        ),
    )
    assert result == {
        "result": "SOL-E007-ENFORCEMENT-UNAVAILABLE",
        "committed": False,
        "head": None,
    }
    assert not ledger.exists()


def test_denied_reducer_result_is_preserved_without_touching_path(tmp_path: Path) -> None:
    owner = _load_owner(
        ROOT / "scripts" / "agent_run_persistence" / "operation_store.py",
        "operation_store_reducer_denial",
        "the sole durable V1/V2/V3 writer and recovery protocol",
    )
    ledger = tmp_path / "agent-runs.jsonl"
    result = owner.commit_operation(
        ledger_path=ledger,
        reduction={
            "result": "SOL-E004-REASSESSMENT-REQUIRED",
            "changed": False,
            "state": None,
        },
        route_check=None,
    )
    assert result["result"] == "SOL-E004-REASSESSMENT-REQUIRED"
    assert result["committed"] is False
    assert not ledger.exists()

"""Phase A cross-owner contracts for the solution-attempt control plane."""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "solution-attempt-v3"
CLAIM_ROWS = json.loads((FIXTURES / "claim-coverage.json").read_text(encoding="utf-8"))
MATRICES = json.loads((FIXTURES / "contract-matrices.json").read_text(encoding="utf-8"))
STABLE_RESULT = re.compile(r"^(?:SOL-[A-Z0-9-]+|[A-Z][A-Z0-9_-]+)$")


def _load_owner(path: Path, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        pytest.fail(f"missing-contract: cannot load owner {path.relative_to(ROOT)}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("row", CLAIM_ROWS, ids=lambda row: row["claimId"])
def test_claim_row_contract(row: dict) -> None:
    claim_id = row["claimId"]
    assert row["testNode"] == (
        "tests/test_solution_attempt_integration.py::test_claim_row_contract["
        f"{claim_id}]"
    )
    assert STABLE_RESULT.fullmatch(row["expectedResult"])
    assert isinstance(row["owner"], str) and row["owner"].strip()
    assert isinstance(row["designGuards"], list)


def test_delta_window_matrix_has_all_authorized_and_unauthorized_classes() -> None:
    cases = {row["case"]: row["expected"] for row in MATRICES["byteWindowCases"]}
    assert cases == {
        "before-claim": "SOL-E006-UNAUTHORIZED-DELTA",
        "inside-surface-window": "INCLUDED_IN_FINAL_DIFF",
        "outside-all-open-surfaces": "SOL-E006-UNAUTHORIZED-DELTA",
        "after-reaped": "SOL-E011-POST-REAP-DRIFT",
        "baseline-drift": "SOL-E006-UNAUTHORIZED-DELTA",
    }


def test_cross_dimension_fixture_preserves_exact_claim_cardinality() -> None:
    assert len(CLAIM_ROWS) == 50
    assert {row["claimId"][0] for row in CLAIM_ROWS} == {"A", "S", "R"}
    assert len({row["testNode"] for row in CLAIM_ROWS}) == 50


def test_red_cross_gate_binding_missing() -> None:
    owner = _load_owner(
        ROOT / "scripts" / "validate-work-item-state.py",
        "validate_work_item_state_phase_a",
    )
    assert callable(getattr(owner, "validate_solution_attempt_gate_binding", None)), (
        "missing-contract: scripts/validate-work-item-state.py must expose "
        "validate_solution_attempt_gate_binding for the exact REAPED snapshot"
    )


def _exact_reaped_binding() -> dict:
    digest = "a" * 64
    return {
        "owner": "agent_run_store.commit_operation",
        "routeEnabled": True,
        "routeBinding": digest,
        "expectedRouteBinding": digest,
        "launchState": "REAPED",
        "finalSnapshot": digest,
        "expectedFinalSnapshot": digest,
    }


def test_exact_reaped_snapshot_binding_is_eligible_but_not_a_pass() -> None:
    owner = _load_owner(
        ROOT / "scripts" / "validate-work-item-state.py",
        "validate_work_item_state_reaped",
    )
    result = owner.validate_solution_attempt_gate_binding(_exact_reaped_binding())
    assert result == {"result": "SOL-OK", "eligible": True}
    assert "gate" not in result
    assert "PASS" not in result.values()


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("owner", "other.writer", "SOL-E001-STATE-INVALID"),
        ("routeEnabled", False, "SOL-E007-ENFORCEMENT-UNAVAILABLE"),
        ("routeBinding", "b" * 64, "SOL-E007-ENFORCEMENT-UNAVAILABLE"),
        ("launchState", "TERMINAL", "SOL-E001-STATE-INVALID"),
        ("finalSnapshot", "b" * 64, "SOL-E006-RECEIPT-STALE"),
    ],
)
def test_non_reaped_or_nonmatching_gate_binding_denies(field, value, expected) -> None:
    owner = _load_owner(
        ROOT / "scripts" / "validate-work-item-state.py",
        "validate_work_item_state_denials",
    )
    binding = _exact_reaped_binding()
    binding[field] = value
    result = owner.validate_solution_attempt_gate_binding(binding)
    assert result == {"result": expected, "eligible": False}


def test_missing_gate_binding_fields_deny() -> None:
    owner = _load_owner(
        ROOT / "scripts" / "validate-work-item-state.py",
        "validate_work_item_state_missing",
    )
    assert owner.validate_solution_attempt_gate_binding({}) == {
        "result": "SOL-E001-STATE-INVALID",
        "eligible": False,
    }

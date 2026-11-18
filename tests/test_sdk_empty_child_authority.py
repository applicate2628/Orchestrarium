"""Empty child authority uses actual Root decisions, never an executable seed."""
import asyncio
from dataclasses import replace
from pathlib import Path

import pytest

from test_sdk_empty_child_runtime import empty_fixture, decision_candidate
from test_sdk_child_lead_authority import INSTANT
from sdk_execution import runtime


def no_launch(assignment):
    path = Path(assignment.child_work_item) / "agent-runs.jsonl"
    assert not path.exists() or not path.read_text().strip()


@pytest.mark.parametrize("effect", ["child_model", "sdk_launch_admission", "sdk_launch_commit"])
def test_empty_child_decision_checks_root_at_registration_and_claim(tmp_path, monkeypatch, effect):
    values = empty_fixture(tmp_path, monkeypatch)
    owner, assignment = values[:2]
    worker, request, projection = decision_candidate(values, None)
    called = []

    def root_authority(current, stage):
        assert current == request
        called.append(stage)
        if stage == effect:
            raise ValueError("Root revoked this exact decision")

    monkeypatch.setattr(owner._root_authority, "assert_current", root_authority)
    with pytest.raises(ValueError, match="Root revoked"):
        owner.attach_decision_worker(assignment, worker, projection)
        runtime.claim_launch(request, worker._selection, authority=owner.assert_current, started_at=INSTANT)
    assert effect in called
    assert assignment.catalog == assignment.required_request_ids == ()
    no_launch(assignment)


def test_root_decision_drift_between_preflight_and_commit_is_not_authority(tmp_path, monkeypatch):
    values = empty_fixture(tmp_path, monkeypatch)
    owner, assignment, requests = values[:3]
    worker, request, projection = decision_candidate(values, None)
    owner.attach_decision_worker(assignment, worker, projection)

    def changed(current, effect):
        if effect == "sdk_launch_admission":
            requests[worker._request_id] = replace(current, model="different-root-selection")

    monkeypatch.setattr(owner._root_authority, "assert_current", changed)
    with pytest.raises(ValueError, match="child_decision_changed"):
        runtime.claim_launch(request, worker._selection, authority=owner.assert_current, started_at=INSTANT)
    no_launch(assignment)


def test_launch_receipt_does_not_waive_current_root_effect_permission(tmp_path, monkeypatch):
    values = empty_fixture(tmp_path, monkeypatch)
    owner, assignment = values[:2]
    worker, request, projection = decision_candidate(values, None)
    owner.attach_decision_worker(assignment, worker, projection)
    selected = runtime.claim_launch(request, worker._selection, authority=owner.assert_current, started_at=INSTANT)
    before = (Path(assignment.child_work_item) / "agent-runs.jsonl").read_bytes()
    def revoked(current, effect):
        assert current == request
        raise ValueError("Root revoked before native effect")
    monkeypatch.setattr(owner._root_authority, "assert_current", revoked)
    with pytest.raises(ValueError, match="Root revoked"):
        owner.assert_current(request, "turn_start")
    assert (Path(assignment.child_work_item) / "agent-runs.jsonl").read_bytes() == before
    assert selected.expected_launch_sha256
    assert worker.runtime_run is None  # The local claim is not a native execution.


@pytest.mark.parametrize("changed", ["runtime", "scope"])
def test_empty_catalog_does_not_allow_unbound_runtime_or_scope(tmp_path, monkeypatch, changed):
    values = empty_fixture(tmp_path, monkeypatch)
    owner, assignment, requests = values[:3]
    worker, request, projection = decision_candidate(values, None)
    if changed == "runtime":
        worker._selection = replace(worker._selection, job_memory_limit_bytes=512 * 1024 * 1024)
    else:
        requests[worker._request_id] = replace(request, scope=("outside Root assignment",))
    with pytest.raises(ValueError, match="runtime_not_admitted|scope_mismatch"):
        owner.attach_decision_worker(assignment, worker, projection)
    assert not owner._decision_workers
    no_launch(assignment)


def test_cancellation_still_reaches_registered_owner_after_root_request_removed(tmp_path, monkeypatch):
    values = empty_fixture(tmp_path, monkeypatch)
    owner, assignment, requests, selections, root = values[:5]
    worker, request, projection = decision_candidate(values, None)
    owner.attach_decision_worker(assignment, worker, projection)
    original_cancel = worker.cancel
    calls = []
    async def observed_cancel(run_id):
        calls.append(run_id)
        return await original_cancel(run_id)
    monkeypatch.setattr(worker, "cancel", observed_cancel)
    requests.clear()
    def revoked(*args):
        raise ValueError("Root authorization removed")
    monkeypatch.setattr(owner._root_authority, "assert_current", revoked)
    first = asyncio.run(owner.cancel_child(assignment))
    second = asyncio.run(owner.cancel_child(assignment))
    assert first["status"] == second["status"] == "revoked"
    assert calls == [request.run_id, request.run_id]
    # Real worker was never started: report unknown execution, not a false drain ACK.
    receipt = second["receipts"][worker._request_id]
    assert receipt.error == "unknown_execution" and not receipt.acknowledged
    events = runtime._events(root)[2]
    assert sum(row["runId"] == assignment.child_id + "-cancel" for row in events) == 1
    no_launch(assignment)

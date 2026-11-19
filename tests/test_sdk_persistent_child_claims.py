"""Atomic scoped native decision claims against real local ledgers; no SDK calls."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
import hashlib
import json
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import pytest

from test_sdk_child_lead_authority import fixture as child_fixture, decision_fixture, INSTANT
from sdk_execution import runtime
from sdk_execution.coordination import child_coordination_payload
from sdk_execution.contracts import json_text
from provider_prompt import ProviderOutputContext, assemble_external_prompt


def fixture(tmp_path, monkeypatch, mode="native-persistent"):
    publish = runtime.publish_child_assignment
    with patch.object(runtime, "publish_child_assignment",
                      side_effect=lambda **kw: publish(**kw, decision_session_mode=mode)):
        values = child_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(runtime, "prepare_environment", lambda *a: ({}, ProviderOutputContext(())))
    return values


def decision(values, key):
    owner, assignment, requests, selections, _ = values
    # No process is created: this test exercises admission/ledger claims only.
    worker, projection, original = decision_fixture(owner, assignment, requests, selections, None)
    request = replace(original, decision_session_mode=assignment.decision_session_mode,
                      operation_id=key, external_dispatch_id=key+"-dispatch",
                      external_evidence_run_id=key+"-evidence", artifact_id=key,
                      outer_budget_id=key+"-outer", inner_budget_id=key+"-inner",
                      prompt=assemble_external_prompt(child_coordination_payload(
                          key, original.system_instructions, projection).encode()).decode())
    request = owner.prepare_child_decision(assignment, request, worker._selection)
    requests[key] = request
    worker._request_id = key
    owner.attach_decision_worker(assignment, worker, projection)
    return request, worker._selection


LIFECYCLE_LOCK_HELD = "WI-LIFECYCLE-LOCK-HELD"


def claims(values, pairs):
    owner, assignment, *_ = values
    lifecycle, _ = owner._actual_item(assignment)
    barrier = Barrier(len(pairs))
    def claim(pair):
        request, selection = pair
        barrier.wait(timeout=30)
        try:
            selected = runtime.claim_launch(request, selection, authority=owner.assert_current, started_at=INSTANT)
            return "claimed", request.external_dispatch_id, selected
        except ValueError as exc:
            return "refused", request.external_dispatch_id, str(exc)
        except lifecycle.LifecycleError as exc:
            if exc.failure_id != LIFECYCLE_LOCK_HELD:
                raise
            return "refused", request.external_dispatch_id, exc.failure_id
    with ThreadPoolExecutor(max_workers=len(pairs)) as pool:
        return list(pool.map(claim, pairs))


def test_simultaneous_first_claim_has_exactly_one_durable_winner(tmp_path, monkeypatch):
    values = fixture(tmp_path, monkeypatch)
    pairs = [decision(values, key) for key in ("decision-a", "decision-b")]
    outcomes = claims(values, pairs)
    winners = [result for result in outcomes if result[0] == "claimed"]
    refused = [result for result in outcomes if result[0] == "refused"]
    assert len(winners) == len(refused) == 1, outcomes
    # A contended lifecycle read or optimistic snapshot drift may reject the
    # overlapping claim before the atomic writer. Once settled, the persistent
    # anchor itself must still refuse the same loser.
    assert refused[0][2] in {
        "child_native_session_already_started", "current_ledger_invalid", LIFECYCLE_LOCK_HELD,
    }
    loser = next(pair for pair in pairs if pair[0].external_dispatch_id == refused[0][1])
    with pytest.raises(ValueError, match="child_native_session_already_started"):
        runtime.claim_launch(*loser, authority=values[0].assert_current, started_at=INSTANT)
    events = runtime._events(pairs[0][1])[2]
    launches = [event for event in events if event["eventKind"] == "launch"]
    assert [event["runId"] for event in launches] == [winners[0][1]]
    assert launches[0]["sdkExecution"]["childAssignmentSha256"] == values[1].assignment_sha256


def test_default_fresh_handoff_keeps_independent_decision_claims(tmp_path, monkeypatch):
    from process_supervision.process_runner import ProcessRunnerV1
    from test_sdk_fresh_child_recovery import candidate, fresh_fixture, receive

    owner, assignment, requests, selections, _ = fresh_fixture(tmp_path, monkeypatch)
    assert assignment.decision_session_mode == "fresh-handoff"
    claim_launch = runtime.claim_launch

    with ProcessRunnerV1() as process:
        worker, second, projection = candidate(
            owner, assignment, requests, selections, process, "fresh-b",
        )
        owner.attach_decision_worker(assignment, worker, projection)

        def claim_first_then_check_unsettled(first, selection, **kwargs):
            assert first.operation_id == "fresh-a"
            selected = claim_launch(first, selection, **kwargs)
            recovery = owner.recover_child_decision(assignment, worker, projection)
            assert recovery["status"] == "needs-reconciliation"
            assert recovery["decision_run_ids"] == [first.external_dispatch_id]
            with pytest.raises(ValueError, match="child_decision_needs_reconciliation"):
                claim_launch(second, worker._selection, authority=owner.assert_current, started_at=INSTANT)
            return selected

        # Use the existing framed synthetic provider observation and the real
        # receiver; the wrapper above only observes the interval before receipt.
        with patch.object(runtime, "claim_launch", side_effect=claim_first_then_check_unsettled):
            run, terminal, _ = receive(owner, assignment, requests, selections, process, monkeypatch, key="fresh-a")

        assert terminal["status"] == "completed"
        assert owner.recover_child_decision(assignment, worker, projection)["request_id"] == "task-one"
        with pytest.raises(ValueError, match="child_received_intent_pending"):
            claim_launch(second, worker._selection, authority=owner.assert_current, started_at=INSTANT)
        claim_launch(requests["task-one"], selections["task-one"], authority=owner.assert_current, started_at=INSTANT)
        assert owner.recover_child_decision(assignment, worker, projection) is None
        claim_launch(second, worker._selection, authority=owner.assert_current, started_at=INSTANT)

    first = run.request
    assert first.native_continuation is second.native_continuation is None
    assert all("decision_session_mode" not in request.to_dict() for request in (first, second))
    dispatches = [first.external_dispatch_id, second.external_dispatch_id]
    evidence = [first.external_evidence_run_id, second.external_evidence_run_id]
    assert len(set(dispatches)) == len(set(evidence)) == 2
    launches = [row for row in runtime._events(worker._selection)[2]
                if row["eventKind"] == "launch" and row["runId"] in dispatches]
    assert [row["runId"] for row in launches] == dispatches
    assert [row["externalEvidenceRunId"] for row in launches] == evidence
    for row in launches:
        execution = row["sdkExecution"]
        assert execution["childAssignmentSha256"] == assignment.assignment_sha256
        assert "childDecisionContextSha256" in execution
        assert {"decisionSessionMode", "continuationSourceSha256"}.isdisjoint(execution)


@pytest.mark.parametrize("change", ["scope", "assignment", "admitted-id", "runtime"])
def test_changed_scope_or_assignment_cannot_attach_or_claim(tmp_path, monkeypatch, change):
    values = fixture(tmp_path, monkeypatch)
    owner, assignment, requests, selections, _ = values
    worker, projection, request = decision_fixture(owner, assignment, requests, selections, None)
    request = replace(request, decision_session_mode="native-persistent")
    if change == "scope":
        request = replace(request, scope=("unadmitted scope",))
    elif change == "admitted-id":
        request = replace(request, admitted_request_id="another-child-grant")
    elif change == "assignment":
        data = json.loads(projection)
        data["assignment_sha256"] = "f" * 64
        projection = json_text(data)
        request = replace(request, child_choice_json=projection,
            inner_request_sha256=hashlib.sha256(projection.encode()).hexdigest(),
            prompt=assemble_external_prompt(child_coordination_payload(
                request.operation_id, request.system_instructions, projection).encode()).decode())
    else:
        worker._selection = replace(worker._selection, job_memory_limit_bytes=512 * 1024 * 1024)
    requests["decision-test"] = request
    with pytest.raises(ValueError):
        prepared = owner.prepare_child_decision(assignment, request, worker._selection)
        requests["decision-test"] = prepared
        owner.attach_decision_worker(assignment, worker, projection)
        runtime.claim_launch(prepared, worker._selection, authority=owner.assert_current, started_at=INSTANT)
    assert not (Path(assignment.child_work_item) / "agent-runs.jsonl").exists()



def test_distinct_successors_cannot_consume_one_received_turn_twice(tmp_path, monkeypatch):
    from test_sdk_persistent_child_lead import persistent_fixture, candidate, receive_decision
    from process_supervision.process_runner import ProcessRunnerV1
    values = persistent_fixture(tmp_path, monkeypatch)
    owner, assignment, requests, selections, _ = values
    with ProcessRunnerV1() as process:
        prior, terminal, projection = receive_decision(
            owner, assignment, requests, selections, process, monkeypatch)
        # The first intent has actually been dispatched, not merely declared done.
        runtime.claim_launch(requests["task-one"], selections["task-one"],
                             authority=owner.assert_current, started_at=INSTANT)
        pairs = []
        for key in ("successor-a", "successor-b"):
            worker, request, current = candidate(owner, assignment, requests, selections,
                                                 process, key, projection)
            owner.attach_decision_worker(assignment, worker, current)
            pairs.append((request, worker._selection))
        assert pairs[0][0].native_continuation == pairs[1][0].native_continuation
        outcomes = claims(values, pairs)
    winners = [row for row in outcomes if row[0] == "claimed"]
    refused = [row for row in outcomes if row[0] == "refused"]
    assert len(winners) == len(refused) == 1, outcomes
    assert refused[0][2] in {
        "continuation_predecessor_already_consumed", "current_ledger_invalid", LIFECYCLE_LOCK_HELD,
    }, outcomes
    loser = next(pair for pair in pairs if pair[0].external_dispatch_id == refused[0][1])
    with pytest.raises(ValueError, match="continuation_predecessor_already_consumed"):
        runtime.claim_launch(*loser, authority=owner.assert_current, started_at=INSTANT)
    source = pairs[0][0].native_continuation.source_sha256
    launches = [row for row in runtime._events(pairs[0][1])[2]
                if row["eventKind"] == "launch" and
                row.get("sdkExecution", {}).get("continuationSourceSha256") == source]
    assert [row["runId"] for row in launches] == [winners[0][1]]



def test_preexisting_grant_without_session_field_still_loads_fresh(tmp_path, monkeypatch):
    original = runtime._child_assignment_document
    def legacy_document(*args, **kwargs):
        doc = original(*args, **kwargs)
        doc.pop("decision_session_mode", None)
        return doc
    # Reproduce the prior producer shape before canonical publication/sealing.
    # Never alter an already received artifact or recompute its ledger seal.
    monkeypatch.setattr(runtime, "_child_assignment_document", legacy_document)
    owner, assignment, requests, selections, root = child_fixture(tmp_path, monkeypatch)
    document = json.loads((Path(root.work_item) / "child-assignment.json").read_text())
    assert "decision_session_mode" not in document
    loaded = runtime._load_child_assignment(root, assignment.child_id)
    assert loaded.decision_session_mode == "fresh-handoff"
    assert loaded.assignment_sha256 == assignment.assignment_sha256
    owner.assert_child_current(loaded, "delegate")

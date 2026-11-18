"""Closed public predecessor selector; runtime owns durable evidence authority."""
from dataclasses import replace
import json

import pytest
import test_sdk_dispatch as base
from sdk_execution import dispatch, runtime
from sdk_execution.contracts import NativeContinuation


def binding(**changes):
    return {**base.binding(), "schemaVersion": 5, "installedHookRoot": None,
            "contextMode": "continuation", "contextHandoff": None,
            "predecessorEvidenceRunId": "prior-evidence", **changes}


def test_binding_selects_receipt_not_raw_native_identity(tmp_path):
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(binding()))
    assert dispatch.read_binding(path) == binding()
    for key in ("threadId", "turnId", "nativeContinuation", "artifactPath", "writeWorkspace"):
        path.write_text(json.dumps({**binding(), key: "caller-selected"}))
        with pytest.raises(dispatch.DispatchError, match="BINDING_INVALID"):
            dispatch.read_binding(path)


@pytest.mark.parametrize("changes", [
    {"predecessorEvidenceRunId": ""}, {"predecessorEvidenceRunId": None},
    {"contextMode": "fresh"}, {"contextMode": "handoff"},
    {"contextHandoff": "not native continuation"}, {"schemaVersion": 3},
])
def test_invalid_selector(tmp_path, changes):
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(binding(**changes)))
    with pytest.raises(dispatch.DispatchError, match="BINDING_INVALID"):
        dispatch.read_binding(path)


def setup(tmp_path, monkeypatch, role="consultant", task=True):
    selected, path, environment = base.fixture(tmp_path, monkeypatch, ledger_role=role,
        sdk_task_binding=tmp_path / "task.json" if task else None)
    path.write_text(json.dumps(binding()))
    return selected, path, environment


def test_receipt_owner_binds_before_ledger_admission(tmp_path, monkeypatch):
    selected, path, environment = setup(tmp_path, monkeypatch)
    calls = []
    original = base.owner.prepare_ledger_admission
    def resolve(request, selection, *, predecessor_evidence_run_id):
        assert request.context_mode == "fresh" and request.native_continuation is None
        assert predecessor_evidence_run_id == "prior-evidence"
        calls.append("restore")
        return replace(request, context_mode="continuation", native_continuation=NativeContinuation(
            "prior-dispatch", "prior-evidence", "a" * 64, "thread-fixture", "turn-fixture"))
    def admission(*args, **kwargs):
        calls.append("admission")
        return original(*args, **kwargs)
    monkeypatch.setattr(runtime, "prepare_received_continuation_request", resolve)
    monkeypatch.setattr(base.owner, "prepare_ledger_admission", admission)
    operation = dispatch.prepare_dispatch(selected, path, source_environment=environment, cancellation_probe=lambda: False)
    assert operation.request.context_mode == "continuation"
    assert operation.request.native_continuation.prior_evidence_run_id == "prior-evidence"
    assert calls == ["restore", "admission"]


def test_missing_receipt_stops_before_ledger_admission(tmp_path, monkeypatch):
    selected, path, environment = setup(tmp_path, monkeypatch)
    def resolve(*args, **kwargs):
        raise runtime.RuntimeBindingError("prior_receipt_unavailable")
    monkeypatch.setattr(runtime, "prepare_received_continuation_request", resolve)
    monkeypatch.setattr(base.owner, "prepare_ledger_admission", lambda *a, **k: pytest.fail("no admission"))
    with pytest.raises(dispatch.DispatchError, match="PREPARATION_FAILED"):
        dispatch.prepare_dispatch(selected, path, source_environment=environment, cancellation_probe=lambda: False)


@pytest.mark.parametrize("role,task", [("qa-engineer", False), ("backend-engineer", True)])
def test_no_implicit_reviewer_worker_continuation(tmp_path, monkeypatch, role, task):
    selected, path, environment = setup(tmp_path, monkeypatch, role, task)
    monkeypatch.setattr(runtime, "prepare_received_continuation_request", lambda *a, **k: pytest.fail("wrong route"))
    with pytest.raises(dispatch.DispatchError, match="CONTINUATION_ROUTE_UNSUPPORTED"):
        dispatch.prepare_dispatch(selected, path, source_environment=environment, cancellation_probe=lambda: False)


def test_public_restart_restore_claim_worker_receive_and_no_replay(tmp_path, monkeypatch):
    import process_supervision.sdk_worker as worker
    from process_supervision.process_runner import ProcessRunnerV1
    from provider_prompt import ProviderOutputContext
    from sdk_execution import receiving
    from test_sdk_claude_consultant_receiving import observed

    selected, path, environment = setup(tmp_path, monkeypatch)
    path.write_text(json.dumps(base.binding()))
    initial = dispatch.prepare_dispatch(selected, path, source_environment=environment,
                                        cancellation_probe=lambda: False)
    prior_selected = runtime.claim_launch(initial.request, initial.selection,
        authority=lambda *a: None, started_at=initial.started_at)
    prior_observation = observed(monkeypatch, initial.request, prior_selected)
    prior_run = runtime.RuntimeRun(initial.request, prior_selected, ProviderOutputContext(()), prior_observation)
    terminal = receiving.receive_runtime_run(prior_run, artifact="prior.json",
        started_at=initial.started_at, updated_at=initial.started_at)
    predecessor = terminal["runId"]
    del initial, prior_run, prior_observation, terminal, prior_selected

    path.write_text(json.dumps(binding(predecessorEvidenceRunId=predecessor, artifactIdentity="next-artifact")))
    operation = dispatch.prepare_dispatch(selected, path, source_environment=environment,
                                          cancellation_probe=lambda: False)
    assert operation.request.native_continuation.prior_evidence_run_id == predecessor
    monkeypatch.setattr(runtime, "prepare_environment", lambda *a: ({}, ProviderOutputContext(())))
    monkeypatch.setattr(runtime._owner(), "require_codex_hook_trust", lambda *a, **k: 0)
    calls = []
    def simulated(process, value, **kwargs):
        calls.append(value)
        # Exercise the actual public current-authority sequence; no model runs.
        for effect in ("start", "client_start", "query", "resume", "query", "reconcile", "turn_start"):
            kwargs["authority"](value, effect)
        admitted = runtime.runtime_selection_from_dict("codex", kwargs["runtime_selection"])
        return observed(monkeypatch, value, admitted, result_changes={"native_turn_id": "continued-native-turn"})
    monkeypatch.setattr(worker, "run_sdk_worker", simulated)
    with ProcessRunnerV1() as process:
        run = operation.execute(process)
        assert run.observation.result.native_turn_id == "continued-native-turn"
    result = operation.receive()
    assert result.terminal["status"] == "completed" and result.terminal["gate"] == "none"
    assert result.terminal["authorizing"] is False
    successor = result.terminal["runId"]
    # Restart restoration uses only the canonical receipt, not retained objects.
    selected.control.ledger_artifact = "third.json"
    path.write_text(json.dumps(binding(predecessorEvidenceRunId=successor, artifactIdentity="third-artifact")))
    next_operation = dispatch.prepare_dispatch(selected, path, source_environment=environment,
                                               cancellation_probe=lambda: False)
    assert next_operation.request.native_continuation.native_turn_id == "continued-native-turn"

    selected.control.ledger_artifact = "repeat.json"
    path.write_text(json.dumps(binding(predecessorEvidenceRunId=predecessor, artifactIdentity="repeat-artifact")))
    repeated = dispatch.prepare_dispatch(selected, path, source_environment=environment,
                                         cancellation_probe=lambda: False)
    with ProcessRunnerV1() as process:
        with pytest.raises(ValueError, match="already_consumed"):
            repeated.execute(process)
    assert len(calls) == 1

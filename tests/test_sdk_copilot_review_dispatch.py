"""Offline Copilot Reviewer through real public, ledger and receiving owners."""
from dataclasses import replace
import json
from pathlib import Path

import pytest
from test_sdk_copilot_dispatch import prepare as task_prepare, execute_offline
from test_sdk_copilot import FakeSdk
from test_sdk_dispatch import owner, dispatch, runtime
from sdk_execution.contracts import json_text


def prepare(tmp_path, monkeypatch, role="qa-engineer"):
    task = task_prepare(tmp_path, monkeypatch)
    control = task.prevalidated.control
    path = control.sdk_task_binding
    control.sdk_task_binding = None
    control.sdk_review_binding = path
    control.ledger_role = role
    selected = replace(task.prevalidated,
        role_provenance=owner.external_role_provenance(control, "copilot"))
    return dispatch.prepare_dispatch(selected, path, provider="copilot",
        source_environment=task._environment, cancellation_probe=lambda: False)


def execute_review(operation, monkeypatch, *, verdict="PASS", change=None, sdk=None):
    sdk = sdk or FakeSdk()
    request = operation.request
    async def reply():
        data = dict(run_id=request.external_evidence_run_id,
            artifact_id=request.artifact_id, role=request.role,
            verdict=verdict, findings=[])
        if change:
            change(data)
        sdk.content = json_text(data)
    sdk.on_send = reply
    return execute_offline(operation, monkeypatch, sdk=sdk)


@pytest.mark.parametrize("verdict", ["PASS", "REVISE"])
def test_public_review_gate_is_evidence_not_global_authority(tmp_path, monkeypatch, verdict):
    operation = prepare(tmp_path, monkeypatch)
    sdk, calls = execute_review(operation, monkeypatch, verdict=verdict)
    result = operation.receive()
    assert result.terminal["status"] == ("completed" if verdict == "PASS" else "revise")
    assert result.terminal["gate"] == verdict
    assert result.terminal["executionRole"] == "external-reviewer"
    assert result.terminal["authorizing"] is False
    assert result.terminal["closesRunIds"] == []
    assert operation.runtime_run.observation.result.task is None
    assert operation.runtime_run.observation.result.review.verdict == verdict
    schema = sdk.send_options["response_schema"]
    assert "verdict" in schema["properties"] and "content" not in schema["properties"]
    assert len(calls) == sdk.calls.count("send") == 1
    before = (Path(operation.selection.work_item) / "agent-runs.jsonl").read_bytes()
    with pytest.raises(ValueError):
        operation.execute(object())
    assert (Path(operation.selection.work_item) / "agent-runs.jsonl").read_bytes() == before


@pytest.mark.parametrize("role", ["consultant", "backend-engineer"])
def test_nonreview_role_cannot_enter_reviewer_dispatch(tmp_path, monkeypatch, role):
    with pytest.raises(ValueError):
        prepare(tmp_path, monkeypatch, role=role)
    assert not list(tmp_path.rglob("agent-runs.jsonl"))


@pytest.mark.parametrize("kind", ["task", "foreign-role"])
def test_invalid_review_output_cannot_become_pass(tmp_path, monkeypatch, kind):
    operation = prepare(tmp_path, monkeypatch)
    def change(data):
        if kind == "task":
            data.pop("verdict")
            data.pop("findings")
            data["content"] = "A task is not a review."
        else:
            data["role"] = "consultant"
    sdk, calls = execute_review(operation, monkeypatch, change=change)
    result = operation.receive()
    assert result.terminal["status"] == "blocked"
    assert result.terminal["gate"] == "none"
    assert result.terminal["authorizing"] is False
    assert result.terminal["closesRunIds"] == []
    assert sdk.calls.count("send") == len(calls) == 1


def test_committed_review_lost_ack_reconciles_exactly_without_model_replay(tmp_path, monkeypatch):
    from sdk_execution import receiving
    operation = prepare(tmp_path, monkeypatch)
    sdk, calls = execute_review(operation, monkeypatch)
    original = receiving.receive_terminal
    committed = {}
    def lost_ack(*args, **kwargs):
        committed.update(kwargs)
        original(*args, **kwargs)
        raise RuntimeError("synthetic lost acknowledgement")
    with monkeypatch.context() as patch:
        patch.setattr(receiving, "receive_terminal", lost_ack)
        with pytest.raises(RuntimeError, match="lost acknowledgement"):
            operation.receive()
    item = Path(operation.selection.work_item)
    before = (item / "agent-runs.jsonl").read_bytes()
    run = operation.runtime_run
    terminal = original(item, operation.request, run.observation, **committed)
    assert terminal["gate"] == "PASS" and terminal["authorizing"] is False
    assert (item / "agent-runs.jsonl").read_bytes() == before
    artifact = item / operation._artifact
    artifact.write_bytes(artifact.read_bytes().replace(b"PASS", b"FAIL"))
    with pytest.raises(ValueError):
        original(item, operation.request, run.observation, **committed)
    assert (item / "agent-runs.jsonl").read_bytes() == before
    assert sdk.calls.count("send") == len(calls) == 1


@pytest.mark.parametrize("failure", ["cleanup", "profile"])
def test_unsettled_or_mismatched_review_never_exports_pass(tmp_path, monkeypatch, failure):
    operation = prepare(tmp_path, monkeypatch)
    sdk = FakeSdk()
    if failure == "cleanup":
        sdk.cleanup_failure = "stop"
    else:
        sdk.profile_effort = "low"
    sdk, calls = execute_review(operation, monkeypatch, sdk=sdk)
    if failure == "cleanup":
        ledger = Path(operation.selection.work_item) / "agent-runs.jsonl"
        before = ledger.read_bytes()
        with pytest.raises(ValueError, match="protocol cleanup unavailable"):
            operation.receive()
        assert ledger.read_bytes() == before
        retained = operation.runtime_run.observation.result
        assert retained.review.verdict == "PASS" and retained.cleanup_error is not None
        assert operation.terminal is None
        assert len(calls) == sdk.calls.count("send") == 1
        return
    result = operation.receive()
    assert result.terminal["status"] == "blocked"
    assert result.terminal["gate"] == "none"
    assert result.terminal["authorizing"] is False
    assert result.terminal["closesRunIds"] == []
    assert len(calls) == 1
    assert sdk.calls.count("send") == (1 if failure == "cleanup" else 0)


def test_neighbor_consultant_malformed_output_settles_without_native_retry(tmp_path, monkeypatch):
    operation = task_prepare(tmp_path, monkeypatch)
    sdk = FakeSdk()
    async def malformed():
        sdk.content = "{malformed"
    sdk.on_send = malformed
    sdk, calls = execute_offline(operation, monkeypatch, sdk=sdk)
    result = operation.receive()
    assert result.terminal["status"] == "blocked"
    assert result.terminal["gate"] == "none"
    assert result.terminal["authorizing"] is False
    assert sdk.calls.count("send") == len(calls) == 1
    for effect in ("copilot_send", "copilot_result"):
        with pytest.raises(ValueError):
            operation.assert_current(operation.request, effect)

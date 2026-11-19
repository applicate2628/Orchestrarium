"""Crossed Copilot dispatch with actual ledger owners and a synthetic process peer.

The injected official-shaped SDK and settled process fixture prove offline wiring,
not native Copilot acceptance or Windows containment.
"""
import asyncio
from dataclasses import replace
import time
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_sdk_dispatch import fixture as base_fixture, owner, dispatch, runtime
import test_sdk_receiving as process_fixture
from test_sdk_copilot import FakeSdk
from sdk_execution import copilot
from sdk_execution.contracts import json_text


def prepare(tmp_path, monkeypatch, *, authentication=None):
    # Base setup stubs the Codex auth resolver; restore the real owner for Copilot.
    auth_resolver = owner.resolve_provider_auth_configuration
    prior, path, _ = base_fixture(tmp_path, monkeypatch, ledger_role="consultant")
    monkeypatch.setattr(owner, "resolve_provider_auth_configuration", auth_resolver)
    control = prior.control
    control.sdk_task_binding = path
    control.provider_flags = ["--model", "selected-model", "--effort", "high"]
    flags, model, effort = owner.resolved_profile("copilot", control.provider_flags)
    selected = owner.PolicyBoundLaunch(control, "fixture", tuple(flags), model, effort,
        owner.external_role_provenance(control, "copilot"), None)
    capture = tmp_path / "capture"
    capture.mkdir()
    monkeypatch.setenv("COPILOT_PROMPTS_DIR", str(capture))
    monkeypatch.setenv("COPILOT_CLI_PATH", str(tmp_path / "fixture.exe"))
    fixture_token = "fixture-" + "private-credential"
    environment = dict(
        COPILOT_BASE_DIRECTORY=str(tmp_path),
        COPILOT_CLI_PATH=str(tmp_path / "fixture.exe"), COPILOT_PROMPTS_DIR=str(capture))
    environment.update({"COPILOT_GITHUB_TOKEN":fixture_token} if authentication is None else authentication)
    return dispatch.prepare_dispatch(selected, path, provider="copilot",
        source_environment=environment, cancellation_probe=lambda: False)


def execute_offline(operation, monkeypatch, *, sdk=None):
    import process_supervision.sdk_worker as worker
    from process_supervision.process_runner import ProcessRunnerV1
    sdk = sdk or FakeSdk()
    req = operation.request
    sdk.content = json_text(dict(run_id=req.external_evidence_run_id,
        artifact_id=req.artifact_id, role=req.role, content="Bounded advice."))
    monkeypatch.setattr(copilot, "_load_sdk", lambda: sdk)
    calls = []
    def simulated(process, request, **kwargs):
        calls.append(request)
        selection = runtime.runtime_selection_from_dict("copilot", kwargs["runtime_selection"])
        async def authorize(value, effect):
            return kwargs["authority"](value, effect)
        # Mirror only the worker environment boundary; do not bypass Host/ledger.
        with monkeypatch.context() as patch:
            for row in kwargs["environment"]:
                patch.setenv(row.name, row.value)
            executor = copilot.create_copilot_adapter(request,
                SimpleNamespace(authorize=authorize), selection)
            result = asyncio.run(executor.execute(request))
            return sealed_result(request, selection, result)
    monkeypatch.setattr(worker, "run_sdk_worker", simulated)
    with ProcessRunnerV1() as process:
        operation.execute(process)
    return sdk, calls



def sealed_result(request, selection, result):
    # Same process peer as test_sdk_receiving, retaining the actual SDK stream.
    from process_supervision import process_runner as processes
    run_sdk_worker = process_fixture.run_sdk_worker
    from sdk_execution.worker import encode_frame
    from unittest.mock import patch
    with processes.ProcessRunnerV1() as process:
        def simulate(process_request, *, dialogue):
            frames = iter([
                *(encode_frame({"kind": "observation", "run_id": request.run_id,
                    "observation": row.to_dict()}) for row in result.observations),
                encode_frame({"kind": "result", "result": result.to_dict()})])
            class Channel:
                def write_line(self, value):
                    pass
                def read_line(self):
                    frame = next(frames, None)
                    if frame is None:
                        raise EOFError()
                    return frame
            dialogue.handler(Channel())
            failed = processes._request_failure(process_request,
                processes.ProcessSupervisionError("PSV1-INTERNAL", "execution"),
                time.monotonic())
            return replace(failed, outcome="success", terminal_stage="completed",
                failure_id=None, target_exit_code=0, resources_closed=True,
                policy_id="sdk-worker-v1",
                tree=processes.TreeObservationV1("synthetic", True, "EMPTY",
                    True, True, True, True))
        with patch.object(process, "run", simulate):
            return run_sdk_worker(process, request, environment=(),
                deadline_monotonic=time.monotonic() + 10,
                job_memory_limit_bytes=selection.job_memory_limit_bytes,
                runtime_selection=selection.to_dict(),
                authority=lambda request, effect: None)

def test_public_dispatch_factory_and_canonical_receiving(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    sdk, calls = execute_offline(operation, monkeypatch)
    result = operation.receive()
    assert result.exit_code == 0
    assert result.terminal["status"] == "completed"
    assert result.terminal["gate"] == "none" and result.terminal["authorizing"] is False
    assert result.terminal["executionRole"] == "consultant"
    assert len(calls) == sdk.calls.count("send") == 1
    assert sdk.options["system_message"]["content"] == operation.selection.instructions
    ledger = Path(operation.selection.work_item) / "agent-runs.jsonl"
    before = ledger.read_bytes()
    assert b"fixture-private-credential" not in before
    assert b"fixture-private-credential" not in result.terminal_bytes
    with pytest.raises(dispatch.DispatchError):
        operation.execute(object())
    with pytest.raises(dispatch.DispatchError):
        operation.receive()
    assert ledger.read_bytes() == before
    assert sdk.calls.count("send") == 1



@pytest.mark.parametrize("change", ["control", "cancel", "runtime"])
def test_changed_admission_before_execute_never_starts_native(tmp_path, monkeypatch, change):
    operation = prepare(tmp_path, monkeypatch)
    if change == "control":
        operation.prevalidated.control.ledger_lane = "changed"
    elif change == "cancel":
        operation._cancelled = lambda: True
    else:
        Path(operation.selection.executable).write_bytes(b"changed runtime")
    sdk = FakeSdk()
    with pytest.raises((ValueError, RuntimeError)):
        execute_offline(operation, monkeypatch, sdk=sdk)
    assert sdk.calls == []
    ledger = Path(operation.selection.work_item) / "agent-runs.jsonl"
    assert not ledger.exists()


def test_receiving_control_drift_retains_evidence_without_reexecution(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    sdk, calls = execute_offline(operation, monkeypatch)
    observed = operation.runtime_run.observation
    ledger = Path(operation.selection.work_item) / "agent-runs.jsonl"
    before = ledger.read_bytes()
    operation.prevalidated.control.ledger_lane = "changed"
    with pytest.raises(dispatch.DispatchError, match="RECEIVING_DRIFT"):
        operation.receive()
    assert operation.runtime_run.observation is observed
    assert ledger.read_bytes() == before
    assert len(calls) == sdk.calls.count("send") == 1


def test_tampered_received_artifact_cannot_reconcile_or_relaunch(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    sdk, calls = execute_offline(operation, monkeypatch)
    operation.receive()
    ledger = Path(operation.selection.work_item) / "agent-runs.jsonl"
    before = ledger.read_bytes()
    artifact = Path(operation.selection.work_item) / operation._artifact
    artifact.write_bytes(artifact.read_bytes().replace(b"Bounded advice.", b"Altered advice."))
    from sdk_execution.receiving import receive_runtime_run
    with pytest.raises(ValueError):
        receive_runtime_run(operation.runtime_run, artifact=operation._artifact,
            started_at=operation.started_at, updated_at=operation.started_at)
    assert ledger.read_bytes() == before
    assert len(calls) == sdk.calls.count("send") == 1



def test_lost_receiving_ack_reconciles_committed_evidence_without_reexecution(tmp_path, monkeypatch):
    from sdk_execution import receiving
    operation = prepare(tmp_path, monkeypatch)
    sdk, calls = execute_offline(operation, monkeypatch)
    original = receiving.receive_terminal
    committed_options = {}
    def committed_then_lost(*args, **kwargs):
        committed_options.update(kwargs)
        original(*args, **kwargs)
        raise RuntimeError("synthetic lost receiving acknowledgement")
    with monkeypatch.context() as patch:
        patch.setattr(receiving, "receive_terminal", committed_then_lost)
        with pytest.raises(RuntimeError, match="lost receiving"):
            operation.receive()
    ledger = Path(operation.selection.work_item) / "agent-runs.jsonl"
    before = ledger.read_bytes()
    retained = operation.runtime_run
    terminal = original(operation.selection.work_item, operation.request,
        retained.observation, **committed_options)
    assert terminal["status"] == "completed" and terminal["authorizing"] is False
    assert ledger.read_bytes() == before
    assert len(calls) == sdk.calls.count("send") == 1
    with pytest.raises(dispatch.DispatchError):
        operation.execute(object())

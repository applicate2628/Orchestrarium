"""Offline Codex streaming -> real public receipt -> durable continuation.

Only the vendor client, external hook probe and OS process boundary are synthetic.
No provider SDK, authentication RPC, model, native containment or account acceptance.
"""
import asyncio
import json
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import test_sdk_dispatch as base
from test_sdk_codex import FakeClient, event
from test_sdk_copilot_dispatch import sealed_result
from sdk_execution import codex, dispatch, runtime
from sdk_execution.contracts import ExecutionRequest, json_text
from process_supervision.process_runner import ProcessRunnerV1

DEFAULT_EVENTS = ExecutionRequest.__dataclass_fields__["max_events"].default
NEUTRAL = "Remember the color amber for this synthetic session. Give brief read-only advice."
public_token = "ORCHE_ACCEPT_095EF6A2"  # orchestrarium:public-token


def prepare(tmp_path, monkeypatch, max_events=DEFAULT_EVENTS):
    resolver = base.owner.resolve_provider_auth_configuration
    selected, path, environment = base.fixture(
        tmp_path, monkeypatch, ledger_role="consultant", sdk_task_binding=tmp_path / "binding.json")
    monkeypatch.setattr(base.owner, "resolve_provider_auth_configuration", resolver)
    environment["OPENAI_API_KEY"] = "synthetic-test-key-never-authenticated-123456789"
    selected.control.prompt_file.write_text(NEUTRAL)
    path.write_text(json.dumps({**base.binding(), "maxEvents": max_events}))
    operation = dispatch.prepare_dispatch(selected, path, source_environment=environment,
                                          cancellation_probe=lambda: False)
    return operation, path, environment


class StreamingClient(FakeClient):
    def __init__(self, request, content, turn):
        payload = dict(run_id=request.external_evidence_run_id, artifact_id=request.artifact_id,
                       role=request.role, content=content)
        text = json_text(payload)
        item = dict(type="agentMessage", id="synthetic-answer", phase="final_answer", text=text)
        events = [event("item/started", {"threadId": "thread-1", "turnId": turn, "item": item})]
        events += [event("item/agentMessage/delta", {"threadId": "thread-1", "turnId": turn,
                   "itemId": item["id"], "delta": char}) for char in text]
        events += [
            event("item/completed", {"threadId": "thread-1", "turnId": turn, "item": item}),
            event("turn/completed", {"threadId": "thread-1", "turn": {
                "id": turn, "status": "completed", "error": None, "items": [item], "itemsView": "summary"}}),
        ]
        assert len(events) > 100
        super().__init__(events)
        self.account = {"account": {"type": "apiKey"}}
        self.profile_change = dict(model=request.model, reasoningEffort=request.effort, cwd=request.cwd)
        self.configuration["config"].update(service_tier="default", notify=[],
            model_provider="openai", approvals_reviewer="user")
        self.configuration["config"]["features"]["memories"] = False
        self.turn = turn
        self.notifications_delivered = 0
        if request.native_continuation:
            self.history = {"thread": {"id": "thread-1", "turns": [{
                "id": request.native_continuation.native_turn_id, "status": "completed",
                "error": None, "items": []}]}}

    def thread_resume(self, thread_id, params):
        profile = super().thread_start(params)
        self.calls.pop()
        self.calls.append(("thread_resume", thread_id, params))
        return profile

    def turn_start(self, thread_id, input_items, params):
        self.calls.append(("turn_start", thread_id, input_items, params))
        return {"turn": {"id": self.turn, "status": "inProgress", "items": []}}

    def next_turn_notification(self, turn_id):
        self.notifications_delivered += 1
        return super().next_turn_notification(turn_id)


def execute(operation, monkeypatch, *, content="Amber remains the remembered color. Reading evidence is not another inference.", turn="synthetic-first"):
    import process_supervision.sdk_worker as worker
    clients = []
    monkeypatch.setattr(base.owner, "require_codex_hook_trust", lambda *a, **k: 0)
    # Replace only the vendor import/transport; use the real runtime factory.
    package = ModuleType("openai_codex")
    client_module = ModuleType("openai_codex.client")
    client_module.CodexConfig = lambda **values: SimpleNamespace(**values)
    monkeypatch.setitem(__import__("sys").modules, "openai_codex", package)
    monkeypatch.setitem(__import__("sys").modules, "openai_codex.client", client_module)

    def synthetic_worker(process, request, **kwargs):
        selection = runtime.runtime_selection_from_dict("codex", kwargs["runtime_selection"])
        client = StreamingClient(request, content, turn)
        clients.append(client)
        def client_binding(config, handler):
            client.handler = handler
            assert config.codex_bin == selection.executable and config.cwd == request.cwd
            return codex.ClientBinding(client, "0.170.0", client.read_configuration, client.list_mcp_status)
        with monkeypatch.context() as patch:
            patch.setattr(codex, "_official_client_binding", client_binding)
            patch.setattr(os, "environ", {row.name: row.value for row in kwargs["environment"]})
            sink = SimpleNamespace(authorize_from_thread=kwargs["authority"], record_from_thread=lambda row: None)
            adapter = runtime.create_codex_adapter(request, sink, selection)
            result = asyncio.run(adapter.execute(request))
        # Actual frame codec, stream/result agreement and creator-owned observation seal.
        return sealed_result(request, selection, result)

    monkeypatch.setattr(worker, "run_sdk_worker", synthetic_worker)
    with ProcessRunnerV1() as process:
        run = operation.execute(process)
    assert len(clients) == 1
    return run, clients[0]


def test_default_stream_receipt_restart_continuation_without_replay(tmp_path, monkeypatch):
    first, path, environment = prepare(tmp_path, monkeypatch)
    assert first.request.max_events == DEFAULT_EVENTS == 4096
    run, peer = execute(first, monkeypatch)
    assert run.observation.result.status == "completed", (run.observation.result.execution_error, run.observation.result.capture_error, [row.kind for row in run.observation.result.observations])
    assert peer.notifications_delivered > 100
    received = first.receive()
    assert received.terminal["status"] == "completed"
    assert received.terminal["authorizing"] is False and received.terminal["gate"] == "none"
    first_document = json.loads((Path(first.selection.work_item) / first._artifact).read_text())
    predecessor = received.terminal["runId"]
    prior_native = first_document["native_continuation"]
    selected = first.prevalidated
    item = Path(first.selection.work_item)
    del first, run, received, first_document

    def restore(source, label):
        selected.control.ledger_artifact = label + ".json"
        selected.control.terminal_receipt = tmp_path / (label + "-terminal.json")
        path.write_text(json.dumps({**base.binding(), "maxEvents": DEFAULT_EVENTS,
            "schemaVersion": 5, "installedHookRoot": None, "contextMode": "continuation",
            "contextHandoff": None, "predecessorEvidenceRunId": source, "artifactIdentity": label}))
        return dispatch.prepare_dispatch(selected, path, source_environment=environment,
                                          cancellation_probe=lambda: False)

    second = restore(predecessor, "continued")
    assert second.request.native_continuation.native_turn_id == prior_native["turn_id"]
    run, peer = execute(second, monkeypatch, turn="synthetic-second")
    assert peer.notifications_delivered > 100
    terminal = second.receive().terminal
    assert terminal["status"] == "completed" and terminal["authorizing"] is False
    final = json.loads((item / second._artifact).read_text())["native_continuation"]
    assert final["thread_id"] == prior_native["thread_id"] and final["turn_id"] != prior_native["turn_id"]
    assert final["session_depth"] == prior_native["session_depth"]
    assert final["context_sha256"] == prior_native["context_sha256"]
    assert "thread_resume" in [call[0] for call in peer.calls]
    assert "thread_start" not in [call[0] for call in peer.calls]
    before = (item / "agent-runs.jsonl").read_bytes()
    rows = [json.loads(line) for line in before.splitlines()]
    assert [row["eventKind"] for row in rows] == ["launch", "terminal", "launch", "terminal"]
    # Restoring the successor is local only; no third inference.
    restored = restore(terminal["runId"], "not-executed")
    assert restored.request.native_continuation.native_turn_id == final["turn_id"]
    repeated = restore(predecessor, "repeat")
    with ProcessRunnerV1() as process:
        with pytest.raises(ValueError, match="already_consumed"):
            repeated.execute(process)
    assert (item / "agent-runs.jsonl").read_bytes() == before
    assert sum(call[0] == "turn_start" for call in peer.calls) == 1


def test_historical_small_event_budget_retains_blocked_receipt(tmp_path, monkeypatch):
    operation, _, _ = prepare(tmp_path, monkeypatch, max_events=100)
    run, peer = execute(operation, monkeypatch)
    assert run.observation.result.capture_error == "observation_limit_exceeded"
    assert run.observation.result.status != "completed"
    terminal = operation.receive().terminal
    assert terminal["status"] == "blocked" and terminal["authorizing"] is False
    assert "native_continuation" not in json.loads((Path(operation.selection.work_item) / operation._artifact).read_text())
    assert sum(call[0] == "turn_start" for call in peer.calls) == 1


@pytest.mark.parametrize("content", [
    f"Remembered token: {public_token}.",
    "synthetic-test-key-never-authenticated-123456789",
])
def test_production_scanner_rejects_canary_and_exact_credential_without_receipt(tmp_path, monkeypatch, content):
    operation, _, _ = prepare(tmp_path, monkeypatch)
    run, peer = execute(operation, monkeypatch, content=content)
    assert run.observation.result.status == "completed", (run.observation.result.execution_error, run.observation.result.capture_error, [row.kind for row in run.observation.result.observations])  # Parser success is not receiving authority.
    with pytest.raises(ValueError, match="E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"):
        operation.receive()
    item = Path(operation.selection.work_item)
    rows = [json.loads(line) for line in (item / "agent-runs.jsonl").read_text().splitlines()]
    assert [row["eventKind"] for row in rows] == ["launch"]
    assert not (item / operation._artifact).exists()
    diagnostic = json.loads(operation.recovery_bytes())
    assert diagnostic["safetyFailureCode"] == "E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"
    assert diagnostic["restorableObservation"] is False and diagnostic["replayAuthorized"] is False
    assert content not in json.dumps(diagnostic)
    assert sum(call[0] == "turn_start" for call in peer.calls) == 1

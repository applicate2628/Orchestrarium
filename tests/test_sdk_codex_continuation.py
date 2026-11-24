"""Offline native new-turn continuation, distinct from old-turn recovery."""
import asyncio
from dataclasses import FrozenInstanceError, replace
import inspect
import json

import pytest
import test_sdk_codex as base
from sdk_execution.contracts import ExecutionRequest, NativeContinuation
from sdk_execution.codex import ClientBinding, CodexConsultantAdapter


def binding(**changes):
    return replace(NativeContinuation("dispatch-prior", "evidence-prior", "a" * 64,
                                      "thread-1", "turn-prior"), **changes)


def request(**changes):
    return base.request(role="consultant", result_kind="task", context_mode="continuation",
                        native_continuation=binding(), **changes)


class Client(base.FakeClient):
    def __init__(self):
        payload = {"run_id": "evidence-1", "artifact_id": "review.md", "role": "consultant", "content": "next answer"}
        super().__init__(base.successful_events(base.answer(payload)))
        self.history = {"thread": {"id": "thread-1", "turns": [
            {"id": "turn-prior", "status": "completed", "error": None, "items": [{"private": "history"}]}]}}
        self.on_read = None

    def thread_resume(self, thread_id, params):
        result = super().thread_start(params)
        self.calls.pop()  # Return the shared profile without a fictitious thread/start.
        self.calls.append(("thread_resume", thread_id, params))
        result["thread"]["turns"] = self.history["thread"]["turns"]
        return result

    def thread_read(self, thread_id, include_turns=False):
        if self.on_read:
            self.on_read()
        return super().thread_read(thread_id, include_turns)


def adapter(client, authority=None):
    return CodexConsultantAdapter(
        client_factory=lambda handler: ClientBinding(client, "fixture-version", client.read_configuration, client.list_mcp_status),
        assert_current=authority or (lambda req, effect: None),
        verify_account=lambda req, payload: req.account_binding, record=lambda obs: None)


def test_new_turn_uses_bound_history_and_new_output_identity():
    client = Client()
    result = asyncio.run(adapter(client).execute(request()))
    assert result.status == "completed" and result.task.content == "next answer"
    assert result.native_thread_id == "thread-1" and result.native_turn_id == "turn-1"
    assert result.sdk_execution["continuationSourceSha256"] == binding().source_sha256
    names = [c[0] for c in client.calls]
    assert "thread_start" not in names
    assert names.index("thread_resume") < names.index("thread_read") < names.index("turn_start")
    assert "history" not in json.dumps([o.to_dict() for o in result.observations])
    params = next(c[3] for c in client.calls if c[0] == "turn_start")
    assert params["outputSchema"]["properties"]["run_id"]["type"] == "string"
    assert "content" in params["outputSchema"]["required"]
    assert "verdict" not in params["outputSchema"]["properties"]
    assert result.task.run_id == request().external_evidence_run_id
    assert params["sandboxPolicy"]["type"] == "readOnly"


def test_wire_immutable_and_default_compatible():
    req = request()
    assert ExecutionRequest.from_dict(req.to_dict()) == req
    assert "native_continuation" not in base.request().to_dict()
    assert inspect.signature(ExecutionRequest).parameters["native_continuation"].kind is inspect.Parameter.KEYWORD_ONLY
    with pytest.raises(FrozenInstanceError):
        req.native_continuation.native_turn_id = "forged"
    assert replace(req, native_continuation=binding(native_turn_id="different")).to_dict() != req.to_dict()


@pytest.mark.parametrize("changes", [
    {"context_mode": "fresh"}, {"native_continuation": None},
    {"provider": "claude"}, {"role": "architecture-reviewer", "result_kind": "review"},
    {"write_workspace": "/fixture/repo", "role": "backend-engineer"},
    {"external_dispatch_id": "dispatch-prior"},
])
def test_invalid_context_combinations(changes):
    with pytest.raises(ValueError):
        replace(request(), **changes)


@pytest.mark.parametrize("turns", [[],
    [{"id": "turn-prior", "status": "inProgress"}],
    [{"id": "turn-prior", "status": "failed"}],
    [{"id": "newer", "status": "completed"}],
    [{"id": "turn-prior", "status": "completed", "error": {"message": "failure"}}],
    [{"id": "turn-prior", "status": "completed"}, {"id": "turn-prior", "status": "completed"}],
])
def test_prior_must_be_unique_current_completed_tip(turns):
    client = Client()
    client.history["thread"]["turns"] = turns
    result = asyncio.run(adapter(client).execute(request()))
    assert result.status == "incomplete"
    assert not any(c[0] in {"turn_start", "interrupt"} for c in client.calls)
    assert result.native_turn_id is None


@pytest.mark.parametrize("name", ["thread_resume", "thread_read", "turn_start", "next_turn_notification"])
def test_requires_resume_and_new_turn_surface_before_client_start(name):
    client = Client()
    setattr(client, name, None)
    result = asyncio.run(adapter(client).execute(request()))
    assert result.status == "incomplete"
    assert not any(c[0] == "start" for c in client.calls)


def test_cancel_before_new_turn_does_not_interrupt_predecessor():
    client = Client()
    instance = adapter(client)
    client.on_read = lambda: instance._cancel("dispatch-1")
    result = asyncio.run(instance.execute(request()))
    assert result.status == "incomplete"
    assert not any(c[0] in {"turn_start", "interrupt"} for c in client.calls)


def test_same_turn_response_never_interrupts_predecessor():
    client = Client()
    req = replace(request(), native_continuation=binding(native_turn_id="turn-1"))
    client.history["thread"]["turns"][0]["id"] = "turn-1"
    result = asyncio.run(adapter(client).execute(req))
    assert result.execution_error == "continuation_reused_prior_turn"
    assert result.native_turn_id is None
    assert not any(c[0] == "interrupt" for c in client.calls)


def test_cancellation_after_new_turn_targets_new_identity():
    client = Client()
    instance = adapter(client)
    client.on_turn = lambda: instance._cancel("dispatch-1")
    asyncio.run(instance.execute(request()))
    assert ("interrupt", "thread-1", "turn-1") in client.calls
    assert ("interrupt", "thread-1", "turn-prior") not in client.calls


def test_old_result_identity_cannot_satisfy_new_turn():
    client = Client()
    stale = {"run_id": "evidence-prior", "artifact_id": "review.md", "role": "consultant", "content": "old"}
    client.events = base.successful_events(base.answer(stale))
    result = asyncio.run(adapter(client).execute(request()))
    assert result.status == "incomplete" and result.task is None


def test_mismatched_resumed_thread_stops_before_read_or_turn():
    client = Client()
    client.profile_change["thread"] = {"id": "wrong-thread"}
    result = asyncio.run(adapter(client).execute(request()))
    assert result.execution_error == "native_thread_mismatch"
    assert not any(c[0] in {"thread_read", "turn_start", "interrupt"} for c in client.calls)

"""Offline exact-snapshot native fork; no provider/model invocation."""
import asyncio
from dataclasses import replace
import json
import pytest
import test_sdk_codex_continuation as prior
from sdk_execution.contracts import ExecutionRequest


def request():
    return replace(prior.request(), context_mode="fork")


class Client(prior.Client):
    def __init__(self):
        super().__init__()
        self.history["thread"]["id"] = "child-thread"
        self.parent = {"id": "thread-1", "turns": [
            {"id": "turn-prior", "status": "completed"},
            {"id": "later-parent-turn", "status": "completed"}]}
        self.fork_parent = "thread-1"
        self.fork_id = "child-thread"
        for event in self.events:
            if isinstance(event, dict) and isinstance(event.get("payload"), dict):
                event["payload"]["threadId"] = "child-thread"

    def thread_fork(self, thread_id, params):
        result = super().thread_resume(thread_id, params)
        self.calls.pop()
        self.calls.append(("thread_fork", thread_id, params))
        result["thread"] = {"id": self.fork_id, "forkedFromId": self.fork_parent}
        return result


def test_exact_snapshot_fork_does_not_consume_or_mutate_parent():
    client = Client()
    before = json.dumps(client.parent)
    result = asyncio.run(prior.adapter(client).execute(request()))
    assert result.status == "completed", result.execution_error
    assert result.native_thread_id == "child-thread"
    assert result.sdk_execution["forkSourceSha256"] == prior.binding().source_sha256
    assert "continuationSourceSha256" not in result.sdk_execution
    params = next(c[2] for c in client.calls if c[0] == "thread_fork")
    assert params["lastTurnId"] == "turn-prior" and params["ephemeral"] is False
    assert params["deferGoalContinuation"] is True
    assert json.dumps(client.parent) == before
    assert not any(c[0] in {"thread_start", "thread_resume"} for c in client.calls)
    assert ExecutionRequest.from_dict(request().to_dict()) == request()


@pytest.mark.parametrize("field,value", [("fork_id", "thread-1"), ("fork_parent", "unrelated")])
def test_wrong_fork_identity_never_starts_turn(field, value):
    client = Client()
    setattr(client, field, value)
    result = asyncio.run(prior.adapter(client).execute(request()))
    assert result.status == "incomplete"
    assert result.native_thread_id == client.fork_id
    assert not any(c[0] in {"turn_start", "interrupt"} for c in client.calls)


@pytest.mark.parametrize("turns", [
    [{"id": "turn-prior", "status": "completed"}, {"id": "newer", "status": "completed"}],
    [{"id": "turn-prior", "status": "inProgress"}],
    [{"id": "wrong", "status": "completed"}],
])
def test_fork_history_must_end_at_admitted_completed_boundary(turns):
    client = Client()
    client.history["thread"]["turns"] = turns
    result = asyncio.run(prior.adapter(client).execute(request()))
    assert result.status == "incomplete" and result.native_thread_id == "child-thread"
    assert not any(c[0] == "turn_start" for c in client.calls)


def test_cancel_after_fork_retains_child_and_cannot_replay_same_operation():
    client = Client()
    instance = prior.adapter(client)
    client.on_read = lambda: instance._cancel("dispatch-1")
    result = asyncio.run(instance.execute(request()))
    assert result.status == "incomplete" and result.native_thread_id == "child-thread"
    assert result.native_turn_id is None
    assert not any(c[0] in {"turn_start", "interrupt"} for c in client.calls)
    with pytest.raises(Exception, match="operation_already_consumed"):
        asyncio.run(instance.execute(request()))
    assert sum(c[0] == "thread_fork" for c in client.calls) == 1


def test_fork_surface_required_before_client_start():
    client = Client()
    client.thread_fork = None
    result = asyncio.run(prior.adapter(client).execute(request()))
    assert result.status == "incomplete"
    assert not any(c[0] == "start" for c in client.calls)

def test_profile_mismatch_retains_created_child_without_starting_turn():
    client = Client()
    client.profile_change["model"] = "unselected"
    result = asyncio.run(prior.adapter(client).execute(request()))
    assert result.status == "incomplete" and result.native_thread_id == "child-thread"
    assert not any(c[0] in {"turn_start", "interrupt"} for c in client.calls)


def test_cancel_after_new_fork_turn_targets_child_only():
    client = Client()
    instance = prior.adapter(client)
    client.on_turn = lambda: instance._cancel("dispatch-1")
    asyncio.run(instance.execute(request()))
    assert ("interrupt", "child-thread", "turn-1") in client.calls
    assert not any(c[0] == "interrupt" and c[1] == "thread-1" for c in client.calls)

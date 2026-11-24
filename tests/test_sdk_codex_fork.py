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


@pytest.mark.parametrize("mode,deny", [("fork", False), ("fork", True), ("continuation", False)])
def test_native_context_effect_crosses_worker_and_parent_protocol(monkeypatch, mode, deny):
    """Real duplex policy framing, fake provider client and native process receipt."""
    from queue import Queue
    import time
    from process_supervision import process_runner as runner, sdk_worker
    from sdk_execution import worker
    from sdk_execution.codex import ClientBinding, CodexConsultantAdapter

    value = request() if mode == "fork" else prior.request()
    client = Client() if mode == "fork" else prior.Client()
    checked = []

    def authority(current, effect):
        assert current == value
        checked.append(effect)
        if deny and effect == "fork":
            raise ValueError("parent revoked fork")

    async def exercise():
        loop = asyncio.get_running_loop()
        controls = asyncio.Queue()
        outputs = Queue()

        class Frames:
            async def write(self, payload):
                outputs.put_nowait(payload)

        frames = Frames()

        async def serve():
            try:
                current, selection = worker.read_execute_envelope(await controls.get())
                assert current == value and selection is None
                sink = worker.ObservationSink(current, frames)
                adapter = CodexConsultantAdapter(
                    client_factory=lambda _: ClientBinding(client, "fixture-version",
                        client.read_configuration, client.list_mcp_status),
                    assert_current=sink.authorize_from_thread,
                    verify_account=lambda req, _: req.account_binding,
                    record=sink.record_from_thread,
                )
                await worker.serve_operation(current, adapter, controls.get, frames.write, authority_sink=sink)
            finally:
                outputs.put_nowait(None)

        class Channel:
            def write_line(self, payload):
                loop.call_soon_threadsafe(controls.put_nowait, payload)

            def read_line(self):
                payload = outputs.get(timeout=5)
                if payload is None:
                    raise EOFError()
                return payload

        def run(process_request, *, dialogue):
            failure = runner.ProcessSupervisionError("PSV1-INTERNAL", "execution")
            try:
                dialogue.handler(Channel())
            except runner.ProcessSupervisionError as error:
                failure = error
            return runner._request_failure(process_request, failure, time.monotonic())

        with runner.ProcessRunnerV1() as owner:
            monkeypatch.setattr(owner, "run", run)
            _served, observed = await asyncio.wait_for(asyncio.gather(
                serve(), asyncio.to_thread(sdk_worker.run_sdk_worker, owner, value,
                    environment=(), deadline_monotonic=time.monotonic() + 10,
                    job_memory_limit_bytes=256 * 1024 * 1024, authority=authority),
            ), timeout=5)
            return observed

    observed = asyncio.run(exercise())
    effect = "fork" if mode == "fork" else "resume"
    assert checked.count(effect) == 1
    assert observed.result is not None and observed.result.request == value
    names = [c[0] for c in client.calls]
    if deny:
        assert observed.process.failure_id == "PSV1-SDK-WORKER-AUTHORITY"
        assert observed.result.status == "incomplete"
        assert "thread_fork" not in names and "turn_start" not in names
    else:
        assert observed.process.failure_id == "PSV1-INTERNAL"  # Synthetic process only.
        assert observed.result.status == "completed", observed.result.execution_error
        assert names.count("thread_" + effect) == 1
        assert names.index("thread_" + effect) < names.index("turn_start")
    assert not any(name in names for name in {"thread_start", "thread_resume" if mode == "fork" else "thread_fork"})


@pytest.mark.parametrize("mode", ["fresh", "continuation"])
def test_fork_effect_without_a_fork_binding_is_rejected_on_both_protocol_sides(monkeypatch, mode):
    from sdk_execution import worker
    from test_sdk_process_owner import simulated_exchange

    value = (replace(prior.request(), context_mode="fresh", native_continuation=None)
             if mode == "fresh" else prior.request())

    async def exercise():
        class Frames:
            async def write(self, _payload):
                pytest.fail("out-of-context worker request was written")

        sink = worker.ObservationSink(value, Frames())
        with pytest.raises((ValueError, worker.RuntimeBindingError)):
            await sink.authorize(value, "fork")

    asyncio.run(exercise())
    frame = worker.encode_frame({"kind": "authority_request", "run_id": value.run_id,
        "request_sha256": worker.request_binding(value), "sequence": 0, "effect": "fork"})
    observed, channel = simulated_exchange(monkeypatch, [frame], value=value,
        authority=lambda *_: pytest.fail("out-of-context effect reached parent policy"))
    assert observed.process.failure_id == "PSV1-SDK-WORKER-PROTOCOL"
    assert [f["kind"] for f in channel.written] == ["execute"]

"""Offline contracts only; no provider execution or platform qualification."""

from __future__ import annotations

import asyncio
import dataclasses
import ctypes
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from process_supervision import process_runner as runner
from process_supervision import sdk_worker as owner_module
from sdk_execution import worker
from sdk_execution.contracts import CancelReceipt, ExecutionRequest, ExecutionResult, Observation, ReviewResult


def request(**changes):
    value = dict(
        provider="codex", work_item_id="sdk-fixture", external_dispatch_id="dispatch-fixture",
        external_evidence_run_id="evidence-fixture", artifact_id="review-fixture",
        role="architecture-reviewer", model="model-fixture", effort="high", cwd=str(ROOT),
        account_binding="account-fixture", prompt="private fixture prompt",
        coordinator_binding="coordinator-fixture", scope=("scripts/sdk_execution",),
    )
    value.update(changes)
    return ExecutionRequest(**value)


def result(value=None, **changes):
    value = value or request()
    status = changes.pop("status", "completed")
    if status == "completed":
        changes.setdefault("provider_status", "completed")
        changes.setdefault("protocol_closed", True)
        changes.setdefault("review", ReviewResult(
            value.external_evidence_run_id, value.artifact_id, value.role, "PASS", (),
        ))
    return ExecutionResult(value, status, **changes)


def runtime_selection(**changes):
    from sdk_execution.codex_tools import CODEX_MCP_ISOLATION_OVERRIDES
    value = dict(
        executable=str(ROOT / "fixture-codex"), executable_sha256="a" * 64,
        codex_home=str(ROOT / "fixture-home"), auth_mode="codex-api-key",
        expected_account_email=None, work_item=str(ROOT / "sdk-fixture"),
        ledger_max_events=100, ledger_max_bytes=10000,
        job_memory_limit_bytes=256 * 1024 * 1024, expected_launch_sha256="b" * 64,
        config_overrides=list(CODEX_MCP_ISOLATION_OVERRIDES), mcp_scope={"servers": []},
        installed_hook_root=None,
    )
    value.update(changes)
    return value


def authority_frame(sequence=0, effect="client_start", **changes):
    value = dict(kind="authority_request", run_id=request().run_id,
                 request_sha256=worker.request_binding(request()), sequence=sequence, effect=effect)
    value.update(changes)
    return worker.encode_frame(value)


def build(owner, value=None, **changes):
    options = dict(environment=(), deadline_monotonic=time.monotonic() + 10,
                   job_memory_limit_bytes=256 * 1024 * 1024)
    options.update(changes)
    return owner_module.build_sdk_worker_request(owner, value or request(), **options)


def test_fixed_worker_request_has_no_prompt_argv_or_ambient_environment(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-inherit")
    monkeypatch.setenv("PYTHONPATH", "must-not-inherit")
    owner = runner.ProcessRunnerV1()
    value = build(owner, environment=(runner.EnvironmentRowV1("SYSTEMROOT", "fixture"),))
    assert value.argv == runner.SdkWorkerWindowsProfileV1.build_argv()
    assert value.argv[1:3] == ("-I", "-u")
    assert value.argv[3] == str(ROOT / "scripts/sdk_execution/worker.py")
    assert value.environment == (runner.EnvironmentRowV1("SYSTEMROOT", "fixture"),)
    assert value.stdin_bytes is None
    assert value.capture_policy.aggregate_persisted_limit == runner.MAX_STDIN_BYTES
    assert request().prompt not in repr(value.argv)
    assert owner.close().outcome == "closed"


@pytest.mark.parametrize("changes", [
    {"environment": None}, {"environment": []}, {"environment": ({"name": "A", "value": "B"},)},
    {"capture_limit_bytes": True}, {"capture_limit_bytes": 0},
    {"capture_limit_bytes": runner.MAX_STDIN_BYTES + 1},
])
def test_worker_request_rejects_implicit_environment_and_invalid_capture(changes):
    with runner.ProcessRunnerV1() as owner:
        with pytest.raises(ValueError):
            build(owner, **changes)


def test_owner_callback_is_not_containment_authority():
    with pytest.raises(ValueError, match="existing process owner"):
        build(SimpleNamespace(mint_memory_capture_sink=lambda: None))


def test_sdk_profile_reuses_python_probe_and_rejects_caller_scripts(monkeypatch):
    with runner.ProcessRunnerV1() as owner:
        value = build(owner)
        lifecycle = runner.RunLifecycleV1(runner.RunTokenV1(b"s" * 16, 1))
        image = SimpleNamespace(identity_sha256="a" * 64, version_sha256="b" * 64)
        probes = []

        def probe(*args):
            probes.append(args)
            return "python-json-argv-echo-v1", "c" * 64, "c" * 64

        monkeypatch.setattr(owner.windows_argv_admission_owner, "_python_probe", probe)
        admitted = owner.windows_argv_admission_owner.admit(lifecycle, value, image)
        assert admitted.profile_id == runner.SdkWorkerWindowsProfileV1.profile_id
        assert len(probes) == 1
        for argv in (value.argv[:-1] + ("other.py",), value.argv + ("--qualified",)):
            with pytest.raises(runner.ProcessSupervisionError) as error:
                owner.windows_argv_admission_owner.admit(lifecycle, dataclasses.replace(value, argv=argv), image)
            assert error.value.failure_id == "PSV1-ARGV-CODEC-UNSUPPORTED"
        assert len(probes) == 1


@pytest.mark.skipif(os.name == "nt", reason="POSIX fail-closed contract")
def test_sdk_owner_cannot_bypass_posix_hold_with_backend_callback():
    def forbidden(*args):
        raise AssertionError("unqualified POSIX backend reached")

    with runner.ProcessRunnerV1(backend_factory=forbidden) as owner:
        observed = owner_module.run_sdk_worker(
            owner, request(), environment=(), deadline_monotonic=time.monotonic() + 10,
            job_memory_limit_bytes=256 * 1024 * 1024,
        )
    assert observed.process.failure_id == "PSV1-POSIX-ORACLE-UNAVAILABLE"
    assert observed.result is None
    assert observed.stdout == b""
    assert observed.is_bound_to(request())
    assert not observed.process.tree.tree_empty


class Channel:
    def __init__(self, lines):
        self.lines = iter(lines)
        self.written = []
        self.cleanup = False

    def write_line(self, value):
        self.written.append(worker.decode_frame(value))

    def read_line(self):
        value = next(self.lines, EOFError())
        if isinstance(value, BaseException):
            raise value
        return value

    def begin_cleanup(self):
        self.cleanup = True


def simulated_exchange(monkeypatch, lines, value=None, **options):
    value = value or request()
    channel = Channel(lines)
    owner = runner.ProcessRunnerV1()

    def run(process_request, *, dialogue):
        failure = runner.ProcessSupervisionError("PSV1-INTERNAL", "execution")
        try:
            dialogue.handler(channel)
        except runner.ProcessSupervisionError as error:
            failure = error
        # Explicitly synthetic, deliberately non-clean. Never OS settlement proof.
        return runner._request_failure(process_request, failure, time.monotonic())

    monkeypatch.setattr(owner, "run", run)
    with owner:
        observed = owner_module.run_sdk_worker(
            owner, value, environment=(), deadline_monotonic=time.monotonic() + 10,
            job_memory_limit_bytes=256 * 1024 * 1024,
            **options,
        )
    return observed, channel


def test_captured_terminal_survives_later_failure_and_cannot_rebind(monkeypatch):
    terminal = result()
    observed, channel = simulated_exchange(monkeypatch, [
        worker.encode_frame({"kind": "result", "result": terminal.to_dict()}),
        runner.ProcessSupervisionError("PSV1-DEADLINE", "deadline"),
    ])
    assert observed.result == terminal
    assert observed.process.failure_id == "PSV1-DEADLINE"
    assert channel.cleanup
    assert channel.written[-1] == {"kind": "cancel", "run_id": request().run_id}
    assert observed.protocol_error == "PSV1-SDK-WORKER-PROTOCOL"
    assert observed.is_bound_to(request())
    assert not observed.is_bound_to(request(model="another-model"))
    assert not dataclasses.replace(observed, process=dataclasses.replace(observed.process)).is_bound_to(request())
    assert request().prompt not in repr(observed)


def test_cancel_acknowledgement_is_retained_but_not_success(monkeypatch):
    receipt = CancelReceipt(request().run_id, True, True)
    terminal = result(status="interrupted")
    observed, channel = simulated_exchange(monkeypatch, [
        runner.ProcessSupervisionError("PSV1-CANCELLED", "cancellation"),
        worker.encode_frame({"kind": "cancel", "receipt": receipt.to_dict()}),
        worker.encode_frame({"kind": "result", "result": terminal.to_dict()}),
    ])
    assert observed.cancel == receipt
    assert observed.result == terminal
    assert observed.process.failure_id == "PSV1-CANCELLED"
    assert observed.process.tree.ownership_confirmed is False
    assert channel.cleanup


def test_result_must_match_all_request_bindings(monkeypatch):
    terminal = result(request(model="wrong-model"))
    observed, _channel = simulated_exchange(monkeypatch, [
        worker.encode_frame({"kind": "result", "result": terminal.to_dict()}),
    ])
    assert observed.result is None
    assert observed.process.failure_id == "PSV1-SDK-WORKER-PROTOCOL"


def test_trailing_protocol_data_is_not_clean(monkeypatch):
    frame = worker.encode_frame({"kind": "result", "result": result().to_dict()})
    observed, _channel = simulated_exchange(monkeypatch, [frame, frame])
    assert observed.result == result()
    assert observed.process.failure_id == "PSV1-SDK-WORKER-PROTOCOL"


@pytest.mark.parametrize("payload", [
    b"{}", b"[]\n", b'{"kind":"result","kind":"cancel"}\n',
    b'{"kind":"execute","request":NaN}\n', b'{}\n{}\n',
    b'{"kind":"execute","request":{}}\n',
])
def test_worker_rejects_malformed_request(payload):
    with pytest.raises((ValueError, TypeError)):
        worker.read_execute_envelope(payload)


@pytest.mark.parametrize("payload", [
    b'{"kind":"observation","value":NaN}\n',
    b'{"kind":"observation","value":Infinity}\n',
    b'{"kind":"observation","value":-Infinity}\n',
    b'{"kind":"observation","value":1e999}\n',
    b'{"kind":"observation","value":{"x":1,"x":2}}\n',
    b'{"kind":"result","kind":"cancel"}\n',
    b'{"kind":"result"}', b'{"kind":"result"}\n{}\n',
    b'[]\n', b'{}\n', b'{"kind":null}\n',
])
def test_worker_rejects_invalid_json_frame(payload):
    with pytest.raises(ValueError):
        worker.decode_frame(payload)


def test_worker_rejects_oversized_frame_before_json_parse(monkeypatch):
    monkeypatch.setattr(worker, "MAX_FRAME_BYTES", 32)
    with pytest.raises(ValueError, match="frame"):
        worker.decode_frame(b" " * 33 + b"\n")


def test_worker_entrypoint_rejects_missing_selection_before_provider_initialization():
    # Windows runtime initialization needs SystemRoot, not the caller's full env.
    environment = {"SYSTEMROOT": os.environ["SYSTEMROOT"]} if os.name == "nt" else {}
    completed = subprocess.run(
        runner.SdkWorkerWindowsProfileV1.build_argv(),
        input=worker.encode_frame({"kind": "execute", "request": request().to_dict()}),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10, env=environment, cwd=ROOT,
    )
    assert completed.returncode == 2
    assert completed.stderr == b""
    assert worker.decode_frame(completed.stdout) == {
        "kind": "unavailable", "reason": "runtime_selection_required",
    }


def test_in_memory_worker_protocol_cancels_one_operation():
    async def scenario():
        released = asyncio.Event()
        outputs = []

        class Adapter:
            async def execute(self, value):
                await released.wait()
                return ExecutionResult(value, "interrupted", protocol_closed=True)

            async def cancel(self, run_id):
                released.set()
                return CancelReceipt(run_id, True, True)

        async def read():
            return worker.encode_frame({"kind": "cancel", "run_id": request().run_id})

        async def write(payload):
            outputs.append(worker.decode_frame(payload))

        await worker.serve_operation(request(), Adapter(), read, write)
        assert [item["kind"] for item in outputs] == ["cancel", "result"]
        assert outputs[1]["result"]["status"] == "interrupted"

    asyncio.run(scenario())


def test_sdk_dialogue_errors_do_not_change_kimi_error_identity():
    for profile, failure in (
        (runner.KimiWindowsProfileV1.profile_id, "PSV1-KIMI-ACP-PROTOCOL"),
        (runner.SdkWorkerWindowsProfileV1.profile_id, "PSV1-SDK-WORKER-PROTOCOL"),
    ):
        lines = runner._DialogueLineRouterV1(runner._dialogue_failure_id(profile))
        lines.finish(failed=True)
        with pytest.raises(runner.ProcessSupervisionError) as error:
            lines.read_line(time.monotonic() + 1, lambda: False)
        assert error.value.failure_id == failure


@pytest.mark.parametrize("budget", [None, True, 0, -1, 2**(ctypes.sizeof(ctypes.c_size_t) * 8)])
def test_sdk_requires_positive_native_memory_budget_before_acquisition(budget):
    with runner.ProcessRunnerV1() as owner:
        value = build(owner, job_memory_limit_bytes=budget)
        with pytest.raises(runner.ProcessSupervisionError) as error:
            runner._validate_request_shape_before_executable_acquisition(value)
    assert error.value.failure_id == "PSV1-REQUEST-INVALID"


def test_sdk_budget_cannot_be_removed_or_added_to_unrelated_profile():
    with runner.ProcessRunnerV1() as owner:
        sdk = build(owner)
        generic = runner.ProcessRequestV1(**{
            field.name: getattr(sdk, field.name) for field in dataclasses.fields(runner.ProcessRequestV1)
        })
        wrong_profile = dataclasses.replace(sdk, windows_argv_profile_id="python-validator-json-echo-v1")
        for invalid in (generic, wrong_profile):
            with pytest.raises(runner.ProcessSupervisionError):
                runner._validate_request_shape_before_executable_acquisition(invalid)


@pytest.mark.parametrize("budget", [None, 256 * 1024 * 1024])
@pytest.mark.parametrize("accepted", [False, True])
@pytest.mark.parametrize("readback_ok", [False, True])
def test_job_memory_limit_is_applied_before_any_process_creation(monkeypatch, budget, accepted, readback_ok):
    job = runner._WINDOWS_JOB
    calls = []

    class StopBeforeCreate(Exception):
        pass

    class Kernel:
        def CreatePipe(self, read, write, *_args):
            read._obj.value, write._obj.value = 11, 12
            return True

        def CreateJobObjectW(self, *_args):
            calls.append("job")
            return 42

        def SetInformationJobObject(self, handle, info_class, pointer, size):
            assert handle == 42 and info_class == 9
            assert size == ctypes.sizeof(job.JOBOBJECT_EXTENDED_LIMIT_INFORMATION)
            limits = pointer._obj
            calls.append(("limits", limits.BasicLimitInformation.LimitFlags, limits.JobMemoryLimit))
            assert limits.BasicLimitInformation.ActiveProcessLimit == 0
            return accepted

        def InitializeProcThreadAttributeList(self, *_args):
            calls.append("attributes")
            raise StopBeforeCreate()

        def CreateProcessW(self, *_args):
            raise AssertionError("test must never create a process")

        def QueryInformationJobObject(self, handle, info, pointer, size, returned):
            if info == 9:
                assert handle == 42
                value = pointer._obj
                value.BasicLimitInformation.LimitFlags = api.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | api.JOB_OBJECT_LIMIT_JOB_MEMORY
                value.JobMemoryLimit = budget + (not readback_ok)
                returned._obj.value = size
            return True

        def TerminateJobObject(self, *_args):
            return True

        def CloseHandle(self, *_args):
            return True

    api = job.WindowsKernelV1.__new__(job.WindowsKernelV1)
    api.k32 = Kernel()
    monkeypatch.setattr(job, "os", SimpleNamespace(**{**vars(os), "name": "nt"}))
    monkeypatch.setitem(sys.modules, "msvcrt", SimpleNamespace())
    proceeds = accepted and (budget is None or readback_ok)
    with pytest.raises(StopBeforeCreate if proceeds else job.WindowsJobError) as caught:
        job.WindowsJobOwnerV1.launch(
            executable=sys.executable, argv=(sys.executable,), cwd=str(ROOT), environment={},
            api=api, job_memory_limit_bytes=budget,
        )
    flags = api.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if budget is not None:
        flags |= api.JOB_OBJECT_LIMIT_JOB_MEMORY
    assert calls[:2] == ["job", ("limits", flags, budget or 0)]
    assert ("attributes" in calls) is proceeds
    if not accepted:
        assert caught.value.failure_id == "WJOB-JOB-LIMIT"
    assert caught.value.windows_job_closure.handles_closed


@pytest.mark.parametrize("cancel", [False, True])
def test_native_stdio_bridge_uses_real_pipes_without_a_waiting_reader_thread(cancel):
    async def scenario():
        stdin_read, stdin_write = os.pipe()
        stdout_read, stdout_write = os.pipe()
        stop = asyncio.Event()

        class Adapter:
            async def execute(self, value):
                if cancel:
                    await stop.wait()
                    return result(value, status="interrupted")
                return result(value)

            async def cancel(self, run_id):
                stop.set()
                return CancelReceipt(run_id, True, True)

        try:
            os.write(stdin_write, worker.encode_frame({"kind": "execute", "request": request().to_dict()}))
            if cancel:
                os.write(stdin_write, worker.encode_frame({"kind": "cancel", "run_id": request().run_id}))
            # Keep parent stdin open: a blocking read thread would prevent clean
            # operation completion here. The asynchronous read must be cancelled.
            await asyncio.wait_for(worker.serve_stdio(
                lambda _request, _sink, _selection: Adapter(), stdin_fd=stdin_read, stdout_fd=stdout_write,
            ), timeout=2)
            assert os.get_blocking(stdin_read) and os.get_blocking(stdout_write)
            output = os.read(stdout_read, 8192)
            frames = [worker.decode_frame(line + b"\n") for line in output.splitlines()]
            assert [frame["kind"] for frame in frames] == (["cancel", "result"] if cancel else ["result"])
        finally:
            for fd in (stdin_read, stdin_write, stdout_read, stdout_write):
                os.close(fd)

    asyncio.run(scenario())


def test_native_stdio_bridge_restores_modes_on_partial_setup_failure(monkeypatch):
    stdin_read, stdin_write = os.pipe()
    stdout_read, stdout_write = os.pipe()
    original = os.set_blocking

    def setting(fd, value):
        if fd == stdout_write and not value:
            raise OSError("fixture setup failure")
        original(fd, value)

    monkeypatch.setattr(worker.os, "set_blocking", setting)
    try:
        with pytest.raises(OSError, match="fixture setup failure"):
            asyncio.run(worker.serve_stdio(object(), stdin_fd=stdin_read, stdout_fd=stdout_write))
        assert os.get_blocking(stdin_read)
    finally:
        for fd in (stdin_read, stdin_write, stdout_read, stdout_write):
            os.close(fd)


def test_capture_overflow_remains_nonclean_with_bytes_retained():
    with runner.ProcessRunnerV1() as owner:
        value = build(owner, capture_limit_bytes=8)
        capture = runner.BoundedCaptureV1(value.capture_policy, value.capture_sink_binding)
        capture.feed("stdout", b"fixture-output")
        assert capture.limit_crossed
        assert value.capture_sink_binding.bytes_for("stdout") == b"fixture-"
        assert capture.snapshot()["stdout"].truncated


def test_incremental_observation_survives_worker_death_before_terminal(monkeypatch):
    public = Observation(0, "thread/start", '{"thread":{"id":"fixture"}}')
    observed, _channel = simulated_exchange(monkeypatch, [
        worker.encode_frame({"kind": "observation", "run_id": request().run_id,
                             "observation": public.to_dict()}),
        EOFError(),
    ])
    assert observed.observations == (public,)
    assert observed.result is None
    assert observed.process.failure_id == "PSV1-SDK-WORKER-PROTOCOL"
    assert observed.is_bound_to(request())


def test_terminal_observation_mismatch_preserves_both_acquired_outcomes(monkeypatch):
    public = Observation(0, "fixture", '{"result":"acquired"}')
    terminal = result()
    observed, _channel = simulated_exchange(monkeypatch, [
        worker.encode_frame({"kind": "observation", "run_id": request().run_id,
                             "observation": public.to_dict()}),
        worker.encode_frame({"kind": "result", "result": terminal.to_dict()}),
    ])
    assert observed.observations == (public,)
    assert observed.result == terminal
    assert observed.process.failure_id == "PSV1-SDK-WORKER-PROTOCOL"


@pytest.mark.parametrize("record_mode", ["async", "thread"])
def test_native_observation_sink_streams_without_event_loop_deadlock(record_mode):
    async def scenario():
        stdin_read, stdin_write = os.pipe()
        stdout_read, stdout_write = os.pipe()
        public = Observation(0, "fixture", '{"value":1}')

        def create_adapter(value, sink, selection):
            assert value == request()
            assert selection is None

            class Adapter:
                async def execute(self, operation):
                    if record_mode == "async":
                        await sink.record(public)
                    else:
                        await asyncio.to_thread(sink.record_from_thread, public)
                    return result(operation, observations=(public,))

                async def cancel(self, run_id):
                    return CancelReceipt(run_id, True, False)

            return Adapter()

        try:
            os.write(stdin_write, worker.encode_frame({"kind": "execute", "request": request().to_dict()}))
            await asyncio.wait_for(worker.serve_stdio(
                create_adapter, stdin_fd=stdin_read, stdout_fd=stdout_write,
            ), timeout=2)
            output = os.read(stdout_read, 8192)
            frames = [worker.decode_frame(line + b"\n") for line in output.splitlines()]
            assert [frame["kind"] for frame in frames] == ["observation", "result"]
            assert frames[0]["observation"] == public.to_dict()
            assert frames[1]["result"]["observations"] == [public.to_dict()]
        finally:
            for fd in (stdin_read, stdin_write, stdout_read, stdout_write):
                os.close(fd)

    asyncio.run(scenario())


def test_synchronous_observation_entry_rejects_event_loop_thread():
    async def scenario():
        sink = worker.ObservationSink(request(), object())
        with pytest.raises(ValueError, match="must await"):
            sink.record_from_thread(Observation(0, "fixture", "{}"))

    asyncio.run(scenario())


def test_completed_terminal_survives_concurrent_malformed_control():
    async def scenario():
        output = []

        class Adapter:
            async def execute(self, value):
                return result(value)

        async def control():
            return worker.encode_frame({"kind": "cancel", "run_id": "another-run"})

        async def write(frame):
            output.append(worker.decode_frame(frame))

        with pytest.raises(ValueError, match="cancel frame"):
            await worker.serve_operation(request(), Adapter(), control, write)
        assert [frame["kind"] for frame in output] == ["result"]

    asyncio.run(scenario())


def test_uncertain_terminal_write_is_not_retried():
    async def scenario():
        attempts = []

        class Adapter:
            async def execute(self, value):
                return result(value)

        async def control():
            await asyncio.Future()

        async def write(frame):
            attempts.append(frame)
            raise OSError("uncertain partial write")

        with pytest.raises(OSError):
            await worker.serve_operation(request(), Adapter(), control, write)
        assert len(attempts) == 1

    asyncio.run(scenario())


def test_runtime_selection_is_snapshotted_transported_and_sealed(monkeypatch):
    selection = runtime_selection()
    original = selection.copy()
    write = Channel.write_line

    def mutate_source(self, payload):
        selection["codex_home"] = "mutated-after-admission"
        write(self, payload)

    monkeypatch.setattr(Channel, "write_line", mutate_source)
    observed, channel = simulated_exchange(monkeypatch, [
        worker.encode_frame({"kind": "result", "result": result().to_dict()}),
    ], runtime_selection=selection, authority=lambda _request, _effect: None)
    assert json.loads(observed.runtime_selection_json) == original
    assert channel.written[0]["runtime_selection"] == original
    assert observed.is_bound_to(request())
    assert not dataclasses.replace(observed, runtime_selection_json="{}").is_bound_to(request())
    assert original["codex_home"] not in repr(observed)


@pytest.mark.parametrize("selection", [[], "fixture", True, {"job_memory_limit_bytes": 1}])
def test_worker_owner_rejects_runtime_shape_or_memory_mismatch(selection):
    with runner.ProcessRunnerV1() as owner:
        with pytest.raises(ValueError):
            build(owner, runtime_selection=selection)


@pytest.mark.parametrize("selection", [None, [], "fixture", True])
def test_declared_runtime_selection_must_be_an_object(selection):
    with pytest.raises(ValueError, match="runtime selection"):
        worker.read_execute_envelope(worker.encode_frame({
            "kind": "execute", "request": request().to_dict(), "runtime_selection": selection,
        }))


def test_runtime_factory_does_not_query_redirectors_immediate_job(monkeypatch):
    from sdk_execution import runtime
    calls = []
    adapter, sink = object(), object()

    def boundary(memory):
        raise AssertionError("worker must not mistake inner venv Job for its owner")

    def factory(value, observed_sink, selection):
        assert value == request() and observed_sink is sink
        assert selection.to_dict() == runtime_selection()
        calls.append(("factory",))
        return adapter

    monkeypatch.setattr(worker, "verify_current_job_memory_boundary", boundary, raising=False)
    monkeypatch.setattr(runtime, "create_codex_adapter", factory)
    assert worker._create_runtime_adapter(request(), sink, runtime_selection()) is adapter
    assert calls == [("factory",)]


@pytest.mark.parametrize("fault", ["missing", "schema"])
def test_runtime_factory_rejects_before_provider_construction(monkeypatch, fault):
    from sdk_execution import runtime
    calls = []

    def forbidden(*_args):
        raise AssertionError("provider factory must not be reached")

    def boundary(_memory):
        calls.append("job")
        raise worker.WindowsJobError("WJOB-JOB-BOUNDARY", "verify-current")

    monkeypatch.setattr(runtime, "create_codex_adapter", forbidden)
    monkeypatch.setattr(worker, "verify_current_job_memory_boundary", boundary, raising=False)
    selection = None if fault == "missing" else {} if fault == "schema" else runtime_selection()
    with pytest.raises((runtime.RuntimeBindingError, worker.WindowsJobError)):
        worker._create_runtime_adapter(request(), object(), selection)
    assert calls == []


@pytest.mark.parametrize("failure,reason", [
    (worker.RuntimeBindingError("current_launch_changed_or_settled"), "current_launch_changed_or_settled"),
    (worker.WindowsJobError("WJOB-JOB-BOUNDARY", "verify-current"), "WJOB-JOB-BOUNDARY"),
    (ValueError("private protocol content"), "SDK-WORKER-PROTOCOL"),
    (OSError("private filesystem content"), "SDK-WORKER-IO"),
    (RuntimeError("private provider content"), "SDK-WORKER-EXECUTION"),
    (None, None),
])
def test_main_uses_only_fixed_factory_and_content_free_failure_codes(monkeypatch, failure, reason):
    output = io.BytesIO()

    async def serve(factory):
        assert factory is worker._create_runtime_adapter
        if failure is not None:
            raise failure

    monkeypatch.setattr(worker, "serve_stdio", serve)
    monkeypatch.setattr(worker.sys, "stdout", SimpleNamespace(buffer=output))
    assert worker.main() == (0 if failure is None else 2)
    if failure is None:
        assert output.getvalue() == b""
    else:
        assert worker.decode_frame(output.getvalue()) == {"kind": "unavailable", "reason": reason}


def test_native_pipe_bridge_delivers_declared_runtime_to_trusted_factory():
    async def scenario():
        stdin_read, stdin_write = os.pipe()
        stdout_read, stdout_write = os.pipe()
        selected = runtime_selection()

        def factory(value, sink, selection):
            assert value == request() and isinstance(sink, worker.ObservationSink)
            assert selection == selected

            class Adapter:
                async def execute(self, operation):
                    return result(operation)

            return Adapter()

        try:
            os.write(stdin_write, worker.encode_frame({
                "kind": "execute", "request": request().to_dict(), "runtime_selection": selected,
            }))
            await asyncio.wait_for(worker.serve_stdio(
                factory, stdin_fd=stdin_read, stdout_fd=stdout_write,
            ), timeout=2)
            assert worker.decode_frame(os.read(stdout_read, 8192))["kind"] == "result"
        finally:
            for fd in (stdin_read, stdin_write, stdout_read, stdout_write):
                os.close(fd)

    asyncio.run(scenario())


def test_runtime_selection_requires_fresh_parent_authority_before_owner_run(monkeypatch):
    with runner.ProcessRunnerV1() as owner:
        monkeypatch.setattr(owner, "run", lambda *_args, **_kwargs: pytest.fail("owner must not run"))
        with pytest.raises(ValueError, match="parent authority"):
            owner_module.run_sdk_worker(
                owner, request(), environment=(), deadline_monotonic=time.monotonic() + 10,
                job_memory_limit_bytes=256 * 1024 * 1024, runtime_selection=runtime_selection(),
            )


def test_parent_authority_is_rechecked_before_each_effect_and_denial_keeps_result(monkeypatch):
    checked = []
    terminal = result(status="failed", execution_error="parent_authority_denied")

    def authority(value, effect):
        assert value == request()
        checked.append(effect)
        if effect == "turn_start":
            raise ValueError("private revocation explanation")

    observed, channel = simulated_exchange(monkeypatch, [
        authority_frame(0, "client_start"), authority_frame(1, "thread_start"),
        authority_frame(2, "turn_start"),
        worker.encode_frame({"kind": "result", "result": terminal.to_dict()}),
    ], runtime_selection=runtime_selection(), authority=authority)
    assert checked == ["client_start", "thread_start", "turn_start"]
    assert [frame["allowed"] for frame in channel.written[1:]] == [True, True, False]
    assert observed.result == terminal
    assert observed.process.failure_id == "PSV1-SDK-WORKER-AUTHORITY"
    assert observed.is_bound_to(request())
    assert "private revocation" not in repr(channel.written)


@pytest.mark.parametrize("changes", [
    {"run_id": "another"}, {"request_sha256": worker.request_binding(request(prompt="different"))},
    {"sequence": True}, {"sequence": 1}, {"effect": "arbitrary_plugin"}, {"extra": True},
])
def test_parent_rejects_authority_requests_not_bound_to_exact_operation(monkeypatch, changes):
    def forbidden(*_args):
        pytest.fail("invalid request reached authority")

    observed, _channel = simulated_exchange(monkeypatch, [authority_frame(**changes)], authority=forbidden)
    assert observed.process.failure_id == "PSV1-SDK-WORKER-PROTOCOL"


def test_replayed_authority_request_is_not_a_reusable_grant(monkeypatch):
    checked = []
    observed, channel = simulated_exchange(monkeypatch, [authority_frame(), authority_frame()],
                                           authority=lambda _request, effect: checked.append(effect))
    assert checked == ["client_start"]
    assert len(channel.written) == 2
    assert observed.process.failure_id == "PSV1-SDK-WORKER-PROTOCOL"


def test_cancelled_parent_denies_pending_authority_without_reconsulting_policy(monkeypatch):
    terminal = result(status="interrupted")
    observed, channel = simulated_exchange(monkeypatch, [
        runner.ProcessSupervisionError("PSV1-CANCELLED", "cancellation"), authority_frame(),
        worker.encode_frame({"kind": "result", "result": terminal.to_dict()}),
    ], authority=lambda *_args: pytest.fail("cancelled operation cannot request a grant"))
    assert channel.written[-1]["kind"] == "authority_response"
    assert channel.written[-1]["allowed"] is False
    assert observed.result == terminal and observed.process.failure_id == "PSV1-CANCELLED"


def test_authority_reply_preserves_cancellation_byte_budget(monkeypatch):
    execute_size = len(worker.encode_frame({"kind": "execute", "request": request().to_dict()}))
    cancel_size = len(worker.encode_frame({"kind": "cancel", "run_id": request().run_id}))
    monkeypatch.setattr(owner_module, "MAX_STDIN_BYTES", execute_size + cancel_size)
    observed, channel = simulated_exchange(monkeypatch, [authority_frame()], authority=lambda *_args: None,
                                           capture_limit_bytes=execute_size + cancel_size)
    assert len(channel.written) == 1  # No grant can consume the cancellation reserve.
    assert observed.process.failure_id == "PSV1-SDK-WORKER-PROTOCOL"


@pytest.mark.parametrize("mode", ["async", "thread"])
def test_worker_revocation_after_start_prevents_turn_without_deadlock(mode):
    async def scenario():
        controls = asyncio.Queue(maxsize=1)
        output, performed, checked = [], [], []

        async def write(payload):
            frame = worker.decode_frame(payload)
            output.append(frame)
            if frame["kind"] == "authority_request":
                checked.append(frame["effect"])
                await controls.put(worker.encode_frame({
                    **frame, "kind": "authority_response", "allowed": frame["effect"] != "turn_start",
                }))

        sink = worker.ObservationSink(request(), SimpleNamespace(write=write))

        class Adapter:
            async def execute(self, value):
                try:
                    for effect in ("client_start", "thread_start", "turn_start"):
                        if mode == "thread":
                            await asyncio.to_thread(sink.authorize_from_thread, value, effect)
                        else:
                            await sink.authorize(value, effect)
                        performed.append(effect)
                    return result(value)
                except worker.RuntimeBindingError as error:
                    return result(value, status="failed", execution_error=str(error))

            async def cancel(self, run_id):
                return CancelReceipt(run_id, True, False)

        await asyncio.wait_for(worker.serve_operation(
            request(), Adapter(), controls.get, write, authority_sink=sink,
        ), timeout=2)
        assert checked == ["client_start", "thread_start", "turn_start"]
        assert performed == ["client_start", "thread_start"]
        assert output[-1]["result"]["execution_error"] == "parent_authority_denied"

    asyncio.run(scenario())


@pytest.mark.parametrize("fault", ["cancel", "disconnect", "wrong_request", "wrong_effect", "wrong_sequence", "replay"])
def test_single_control_reader_closes_pending_authority_on_bad_reply_or_cancel(fault):
    async def scenario():
        controls = asyncio.Queue(maxsize=2)
        output, performed = [], []

        async def write(payload):
            frame = worker.decode_frame(payload)
            output.append(frame)
            if frame["kind"] != "authority_request":
                return
            reply = {**frame, "kind": "authority_response", "allowed": True}
            if fault == "cancel":
                reply = {"kind": "cancel", "run_id": request().run_id}
            elif fault == "disconnect":
                await controls.put(EOFError("parent disconnected"))
                return
            elif fault == "wrong_request":
                reply["request_sha256"] = "a" * 64
            elif fault == "wrong_effect":
                reply["effect"] = "turn_start"
            elif fault == "wrong_sequence":
                reply["sequence"] = 10
            await controls.put(worker.encode_frame(reply))
            if fault == "replay":
                await controls.put(worker.encode_frame(reply))

        async def read():
            frame = await controls.get()
            if isinstance(frame, Exception):
                raise frame
            return frame

        sink = worker.ObservationSink(request(), SimpleNamespace(write=write))

        class Adapter:
            async def execute(self, value):
                try:
                    await sink.authorize(value, "client_start")
                    performed.append("client_start")
                except worker.RuntimeBindingError:
                    pass
                return result(value, status="interrupted")

            async def cancel(self, run_id):
                return CancelReceipt(run_id, True, False)

        operation = worker.serve_operation(request(), Adapter(), read, write, authority_sink=sink)
        if fault == "cancel":
            await asyncio.wait_for(operation, timeout=2)
            assert any(frame["kind"] == "cancel" for frame in output)
        else:
            with pytest.raises((ValueError, EOFError)):
                await asyncio.wait_for(operation, timeout=2)
        assert performed == []
        assert sink._authority_closed

    asyncio.run(scenario())


def test_authority_thread_wrapper_rejects_same_event_loop_thread():
    async def scenario():
        sink = worker.ObservationSink(request(), object())
        with pytest.raises(ValueError, match="must await"):
            sink.authorize_from_thread(request(), "client_start")

    asyncio.run(scenario())


def test_native_duplex_rechecks_parent_policy_before_effect_and_retains_partial_output(monkeypatch):
    """Real pipes and production protocol, but synthetic SDK and OS receipt."""
    async def scenario():
        stdin_read, stdin_write = os.pipe()
        stdout_read, stdout_write = os.pipe()
        performed, checked = [], []
        permission = {"allowed": True}
        public = Observation(0, "fixture-progress", '{"thread":"started"}')
        reader = os.fdopen(stdout_read, "rb", buffering=0)

        def authority(value, effect):
            assert value == request()
            checked.append(effect)
            if not permission["allowed"]:
                raise ValueError("fixture policy revoked")

        def factory(value, sink, selection):
            assert value == request() and selection == runtime_selection()

            class Adapter:
                async def execute(self, operation):
                    def execute():
                        acquired = ()
                        try:
                            for effect in ("client_start", "thread_start", "turn_start"):
                                sink.authorize_from_thread(operation, effect)
                                performed.append(effect)
                                if effect == "thread_start":
                                    sink.record_from_thread(public)
                                    acquired = (public,)
                                    permission["allowed"] = False
                            return result(operation, observations=acquired)
                        except worker.RuntimeBindingError as error:
                            return result(operation, status="failed", observations=acquired,
                                          execution_error=str(error), protocol_closed=True)
                    return await asyncio.to_thread(execute)

                async def cancel(self, run_id):
                    return CancelReceipt(run_id, True, False)

            return Adapter()

        async def serve():
            try:
                await worker.serve_stdio(factory, stdin_fd=stdin_read, stdout_fd=stdout_write)
            finally:
                os.close(stdout_write)

        with runner.ProcessRunnerV1() as owner:
            def run(process_request, *, dialogue):
                capture = runner.BoundedCaptureV1(process_request.capture_policy,
                                                  process_request.capture_sink_binding)

                class NativeChannel:
                    def write_line(self, payload):
                        pending = memoryview(payload)
                        while pending:
                            pending = pending[os.write(stdin_write, pending):]

                    def read_line(self):
                        line = reader.readline(worker.MAX_FRAME_BYTES + 1)
                        if not line:
                            raise EOFError()
                        capture.feed("stdout", line)
                        return line

                    def begin_cleanup(self):
                        pass

                failure = runner.ProcessSupervisionError("PSV1-INTERNAL", "execution")
                try:
                    dialogue.handler(NativeChannel())
                except runner.ProcessSupervisionError as error:
                    failure = error
                return runner._request_failure(process_request, failure, time.monotonic())

            monkeypatch.setattr(owner, "run", run)
            try:
                _worker, observed = await asyncio.wait_for(asyncio.gather(
                    serve(), asyncio.to_thread(owner_module.run_sdk_worker,
                        owner, request(), environment=(), deadline_monotonic=time.monotonic() + 10,
                        job_memory_limit_bytes=256 * 1024 * 1024,
                        runtime_selection=runtime_selection(), authority=authority),
                ), timeout=3)
            finally:
                reader.close()
                for fd in (stdin_read, stdin_write):
                    os.close(fd)
        assert checked == ["client_start", "thread_start", "turn_start"]
        assert performed == ["client_start", "thread_start"]
        assert observed.observations == (public,)
        assert observed.result.execution_error == "parent_authority_denied"
        assert observed.process.failure_id == "PSV1-SDK-WORKER-AUTHORITY"
        assert b"fixture-progress" in observed.stdout
        assert observed.is_bound_to(request())

    asyncio.run(scenario())


def claude_authority_frame(context, *, value=None):
    value = value or request(provider="claude")
    return worker.encode_frame({
        "kind": "authority_request", "run_id": value.run_id,
        "request_sha256": worker.request_binding(value), "sequence": 0,
        "effect": context["kind"], "context": context,
    })


@pytest.mark.parametrize("context", [
    {"kind": "tool", "name": "Read", "arguments": {"file_path": "/admitted/a.py"}},
    {"kind": "account", "evidence": {"phase": "initialize", "data": {"apiKeySource": "none"}}},
])
def test_claude_exact_context_reaches_parent_owner_and_is_immutable(monkeypatch, context):
    value = request(provider="claude")
    terminal = result(value)
    observed_context = []

    def authority(current, effect, details):
        assert current == value and effect == context["kind"]
        observed_context.append(json.loads(json.dumps(details)))
        details.clear()  # Callback mutation cannot change the returned grant binding.

    observed, channel = simulated_exchange(monkeypatch, [
        claude_authority_frame(context, value=value),
        worker.encode_frame({"kind": "result", "result": terminal.to_dict()}),
    ], value=value, authority=authority)
    assert observed_context == [context]
    assert channel.written[1]["context"] == context
    assert channel.written[1]["allowed"] is True
    assert observed.result == terminal


@pytest.mark.parametrize("context", [
    {"kind": "tool", "name": "Read", "arguments": []},
    {"kind": "tool", "name": "Read", "arguments": {}, "extra": True},
    {"kind": "account", "evidence": {"phase": "unknown", "data": {}}},
    {"kind": "account", "evidence": {"phase": "initialize", "data": [], "extra": 1}},
])
def test_malformed_claude_context_never_reaches_parent_owner(monkeypatch, context):
    observed, _channel = simulated_exchange(monkeypatch, [claude_authority_frame(context)],
        value=request(provider="claude"), authority=lambda *_args: pytest.fail("invalid authority context"))
    assert observed.process.failure_id == "PSV1-SDK-WORKER-PROTOCOL"


def test_context_is_not_allowed_for_codex_and_has_explicit_operation_byte_bound():
    context = {"kind": "tool", "name": "Read", "arguments": {"file_path": "/scope/a"}}
    with pytest.raises(ValueError, match="unsupported"):
        worker.authority_context(request(), "tool", context)
    with pytest.raises(ValueError, match="byte budget"):
        worker.authority_context(request(provider="claude", max_output_bytes=16), "tool", context)


@pytest.mark.parametrize("mutate", [False, True])
def test_claude_async_authority_grant_is_bound_to_exact_tool_arguments(mutate):
    async def scenario():
        value = request(provider="claude")
        context = {"kind": "tool", "name": "Read", "arguments": {"file_path": "/scope/a"}}
        frames = []

        async def write(payload):
            frame = worker.decode_frame(payload)
            frames.append(frame)
            response = {**frame, "kind": "authority_response", "allowed": True}
            if mutate:
                response["context"] = {**context, "arguments": {"file_path": "/outside/b"}}
            sink.accept_authority(response)

        sink = worker.ObservationSink(value, SimpleNamespace(write=write))
        if mutate:
            with pytest.raises(ValueError, match="context mismatch"):
                await sink.authorize(value, "tool", context)
        else:
            await asyncio.wait_for(sink.authorize(value, "tool", context), timeout=1)
            assert frames[0]["context"] == context

    asyncio.run(scenario())


def test_fixed_worker_dispatches_claude_without_immediate_job_assumption(tmp_path, monkeypatch):
    from sdk_execution import claude
    from test_sdk_claude import claude_selection
    selected = claude_selection(tmp_path)
    calls = []
    adapter = object()
    monkeypatch.setattr(worker, "verify_current_job_memory_boundary", lambda budget: calls.append(("job", budget)), raising=False)

    def factory(value, sink, selection):
        assert value.provider == "claude" and selection == selected
        calls.append(("factory",))
        return adapter

    monkeypatch.setattr(claude, "create_claude_adapter", factory)
    assert worker._create_runtime_adapter(request(provider="claude"), object(), selected.to_dict()) is adapter
    assert calls == [("factory",)]


@pytest.mark.parametrize("fault", [None, "query-fails", "truncated", "wrong-budget", "breakaway", "explicit-breakaway", "missing-memory", "missing-kill"])
def test_capped_owner_reads_its_exact_job_before_creation(fault):
    job = runner._WINDOWS_JOB
    budget = 256 * 1024 * 1024
    calls = []

    class Kernel:
        def SetInformationJobObject(self, handle, kind, pointer, size):
            assert handle == 42 and kind == 9
            calls.append("set")
            return True

        def QueryInformationJobObject(self, handle, kind, pointer, size, returned):
            # A venv redirector's immediate Job is not the owner's Job.
            assert handle == 42 and kind == 9
            calls.append("readback")
            value = pointer._obj
            flags = api.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE | api.JOB_OBJECT_LIMIT_JOB_MEMORY
            if fault == "breakaway":
                flags |= api.JOB_OBJECT_LIMIT_SILENT_BREAKAWAY_OK
            if fault == "explicit-breakaway":
                flags |= api.JOB_OBJECT_LIMIT_BREAKAWAY_OK
            if fault == "missing-kill":
                flags &= ~api.JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
            if fault == "missing-memory":
                flags &= ~api.JOB_OBJECT_LIMIT_JOB_MEMORY
            value.BasicLimitInformation.LimitFlags = flags
            value.JobMemoryLimit = budget + (fault == "wrong-budget")
            returned._obj.value = size - (fault == "truncated")
            return fault != "query-fails"

    api = job.WindowsKernelV1.__new__(job.WindowsKernelV1)
    api.k32 = Kernel()
    if fault is None:
        job._set_job_limits(api, 42, budget)
    else:
        with pytest.raises(job.WindowsJobError):
            job._set_job_limits(api, 42, budget)
    assert calls == ["set", "readback"]

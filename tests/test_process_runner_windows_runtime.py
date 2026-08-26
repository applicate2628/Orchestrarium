from __future__ import annotations

import concurrent.futures
import ctypes
import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "process_supervision" / "process_runner.py"
CHILD = ROOT / "tests" / "fixtures" / "process_supervision" / "child_helper.py"
SUPERVISOR = ROOT / "tests" / "fixtures" / "process_supervision" / "supervisor_helper.py"


def _load_runner():
    spec = importlib.util.spec_from_file_location("process_runner_windows_test", RUNNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_child_helper():
    spec = importlib.util.spec_from_file_location(
        "process_supervision_atomic_child_fixture", CHILD
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_fixture_marker_publication_is_atomic_and_complete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Marker existence cannot precede complete flushed UTF-8 content."""
    fixture = _load_child_helper()
    target = tmp_path / "marker.json"
    payload = json.dumps({"directPid": 41, "grandchildPid": 42})
    original_replace = fixture.os.replace
    observed = []

    def observe_replace(source, destination):
        source_path = Path(source)
        assert source_path.parent == target.parent
        assert Path(destination) == target
        assert not target.exists()
        assert source_path.read_text(encoding="utf-8") == payload
        observed.append(source_path.name)
        return original_replace(source, destination)

    monkeypatch.setattr(fixture.os, "replace", observe_replace)
    fixture._publish_marker_atomic(target, payload)

    assert observed
    assert target.read_text(encoding="utf-8") == payload
    assert not tuple(tmp_path.glob(".marker.json.*.tmp"))


def test_fixture_marker_temp_is_cleaned_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed publication leaves neither a visible marker nor temp residue."""
    fixture = _load_child_helper()
    target = tmp_path / "marker.txt"

    def fail_replace(_source, _destination):
        raise OSError("injected replace failure")

    monkeypatch.setattr(fixture.os, "replace", fail_replace)
    with pytest.raises(OSError, match="replace failure"):
        fixture._publish_marker_atomic(target, "complete-token")

    assert not target.exists()
    assert not tuple(tmp_path.glob(".marker.txt.*.tmp"))


def _policy(runner, limit: int = 1024 * 1024):
    return runner.CapturePolicyV1(
        "windows-runtime-v1", limit, min(limit, 64 * 1024), min(limit, 128 * 1024),
        64 * 1024,
    )


def _request(runner, argv: tuple[str, ...], *, limit: int = 1024 * 1024, diagnostic=None, deadline=8.0):
    executable = Path(sys.executable).resolve()
    rows = tuple(
        runner.EnvironmentRowV1(name, os.environ[name])
        for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if name in os.environ
    )
    return runner.ProcessRequestV1(
        1, argv, executable, str(ROOT), rows, None, time.monotonic() + deadline,
        _policy(runner, limit), runner.ProcessRunnerV1().mint_memory_capture_sink(),
        runner.SettlePolicyV1(5.0), diagnostic_port=diagnostic,
        windows_argv_profile_id="python-validator-json-echo-v1",
    )


pytestmark = pytest.mark.skipif(os.name != "nt", reason="real Windows process contract")


def test_suspended_target_cannot_write_first_marker_before_job_verification(tmp_path: Path) -> None:
    """GUARD-WINDOWS-JOB-BEFORE-EXEC: verification event precedes the first marker."""
    runner = _load_runner()
    marker = tmp_path / "first-marker.txt"

    class Port:
        def __init__(self) -> None:
            self.events: list[str] = []

        def emit(self, event_id: str, fields) -> None:
            self.events.append(event_id)
            if event_id == "process.supervision.windows.job-verified.v1":
                assert fields == {"ownershipConfirmed": True}
                assert not marker.exists()

    port = Port()
    request = _request(
        runner,
        (sys.executable, str(CHILD), "marker", "--marker", str(marker), "--token", "started"),
        diagnostic=port,
    )
    result = runner.ProcessRunnerV1().run(request)
    assert result.outcome == "success"
    assert result.tree.ownership_confirmed is True
    assert result.tree.tree_empty is True
    assert marker.read_text(encoding="utf-8") == "started"
    assert port.events == ["process.supervision.windows.job-verified.v1"]


@pytest.mark.parametrize("resume_value", (0, 2, 0xFFFFFFFE, 0xFFFFFFFF))
def test_resume_thread_non_one_never_runs_target(tmp_path: Path, resume_value: int) -> None:
    """GUARD-RESUME-COUNT-ONE: every non-one value terminates the suspended Job."""
    runner = _load_runner()
    marker = tmp_path / f"resume-{resume_value}.txt"
    api = runner._WindowsKernelV1()
    real_k32 = api.k32

    class Proxy:
        def __getattr__(self, name: str):
            if name == "ResumeThread":
                return lambda _handle: resume_value
            return getattr(real_k32, name)

    api.k32 = Proxy()
    request = _request(runner, (sys.executable, str(CHILD), "marker", "--marker", str(marker)))
    result = runner.ProcessRunnerV1(windows_api=api).run(request)
    assert result.failure_id == "PSV1-PROCESS-RESUME"
    assert result.terminal_stage == "process-resume"
    assert result.tree.tree_empty is not False
    assert not marker.exists()


def test_resume_thread_one_runs_target(tmp_path: Path) -> None:
    """GUARD-RESUME-COUNT-ONE: the real previous suspend count one is admitted."""
    runner = _load_runner()
    marker = tmp_path / "resume-one.txt"
    result = runner.ProcessRunnerV1().run(
        _request(runner, (sys.executable, str(CHILD), "marker", "--marker", str(marker)))
    )
    assert result.outcome == "success"
    assert marker.exists()


def test_handle_list_excludes_unrelated_inheritable_handle() -> None:
    """Only the three child standard handles cross CreateProcessW."""
    runner = _load_runner()
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateEventW.restype = ctypes.c_void_p
    event = k32.CreateEventW(None, True, False, None)
    assert event
    try:
        assert k32.SetHandleInformation(event, 1, 1)
        request = _request(
            runner,
            (sys.executable, str(CHILD), "check-handle", "--token", str(event)),
        )
        result = runner.ProcessRunnerV1().run(request)
        assert result.outcome == "success"
        assert request.capture_sink_binding.bytes_for("stdout") == b"not-inherited"
    finally:
        k32.CloseHandle(event)


def test_grandchild_retained_pipe_is_terminated_and_settled(tmp_path: Path) -> None:
    """A direct exit cannot report success while a Job descendant retains pipes."""
    runner = _load_runner()
    marker = tmp_path / "grandchild.txt"
    request = _request(
        runner,
        (
            sys.executable, str(CHILD), "grandchild-retains-pipe",
            "--marker", str(marker), "--token", "PID", "--sleep", "30",
        ),
        deadline=12.0,
    )
    started = time.monotonic()
    result = runner.ProcessRunnerV1().run(request)
    assert result.failure_id == "PSV1-TREE-SETTLEMENT"
    assert result.tree.tree_empty is True
    assert result.resources_closed is True
    assert time.monotonic() - started < 8.0


def test_concurrent_runs_keep_jobs_capture_and_outcomes_isolated() -> None:
    """Terminating one run cannot alter a peer run's Job, sink, or result."""
    runner = _load_runner()
    shared = runner.ProcessRunnerV1()
    bad = _request(runner, (sys.executable, str(CHILD), "infinite-writer"), limit=96 * 1024)
    good = _request(runner, (sys.executable, str(CHILD), "emit", "--bytes", "1024"))
    barrier = threading.Barrier(2)

    def execute(request):
        barrier.wait()
        return shared.run(request)

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        bad_result, good_result = list(pool.map(execute, (bad, good)))
    assert bad_result.failure_id == "PSV1-CAPTURE-LIMIT"
    assert bad_result.tree.tree_empty is True
    assert good_result.outcome == "success"
    assert good_result.stdout.persisted_bytes == 1024
    assert good_result.stderr.persisted_bytes == 1024
    assert good_result.tree.tree_empty is True
    assert shared.windows_inheritance_coordinator.poisoned is False


def test_fast_finite_cap_plus_one_output_is_never_success() -> None:
    """A finite child cannot authorize its truncated capture."""

    runner = _load_runner()
    limit = 1025
    request = _request(
        runner,
        (sys.executable, str(CHILD), "emit", "--bytes", "513"),
        limit=limit,
    )

    result = runner.ProcessRunnerV1().run(request)

    assert result.outcome == "supervisor-failure"
    assert result.failure_id == "PSV1-CAPTURE-LIMIT"
    assert result.terminal_stage == "capture-limit"
    assert result.stdout.persisted_bytes + result.stderr.persisted_bytes == limit
    assert result.stdout.truncated or result.stderr.truncated


def test_nested_job_host_is_supported_or_denied_before_first_marker(tmp_path: Path) -> None:
    """The target host's outer Job cannot produce a partially-started nested launch."""
    runner = _load_runner()
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.GetCurrentProcess.restype = ctypes.c_void_p
    k32.IsProcessInJob.argtypes = [
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_int),
    ]
    k32.IsProcessInJob.restype = ctypes.c_int
    in_job = ctypes.c_int()
    assert k32.IsProcessInJob(k32.GetCurrentProcess(), None, ctypes.byref(in_job))
    assert in_job.value == 1, "BLOCKED: target-host process is not nested in a Job"
    marker = tmp_path / "nested-job.txt"
    result = runner.ProcessRunnerV1().run(
        _request(runner, (sys.executable, str(CHILD), "marker", "--marker", str(marker)))
    )
    if result.outcome == "success":
        assert result.tree.ownership_confirmed is True
        assert marker.exists()
    else:
        assert result.failure_id in {
            "PSV1-PROCESS-CREATE",
            "PSV1-TREE-VERIFICATION",
            "PSV1-ATTRIBUTE-LIST",
        }
        assert not marker.exists()


def test_supervisor_parent_death_kills_job_descendant(tmp_path: Path) -> None:
    """KILL_ON_JOB_CLOSE terminates the target when the supervisor process dies."""
    marker = tmp_path / "parent-death-pid.txt"
    supervisor = subprocess.Popen(
        [sys.executable, str(SUPERVISOR), str(RUNNER_PATH), str(CHILD), str(marker), str(ROOT)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        close_fds=True,
    )
    target_handle = None
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.OpenProcess.restype = ctypes.c_void_p
    try:
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline and not marker.exists():
            if supervisor.poll() is not None:
                pytest.fail(f"supervisor exited before target marker: {supervisor.returncode}")
            time.sleep(0.02)
        assert marker.exists(), "target did not reach its first marker"
        target_pid = int(marker.read_text(encoding="utf-8"))
        target_handle = k32.OpenProcess(0x00100000 | 0x0001, False, target_pid)
        assert target_handle
        supervisor.kill()
        supervisor.wait(timeout=5.0)
        assert k32.WaitForSingleObject(target_handle, 5000) == 0
    finally:
        if supervisor.poll() is None:
            supervisor.kill()
            supervisor.wait(timeout=5.0)
        if target_handle:
            if k32.WaitForSingleObject(target_handle, 0) != 0:
                k32.TerminateProcess(target_handle, 1)
            k32.CloseHandle(target_handle)


@pytest.mark.parametrize(
    ("api_name", "occurrence", "fake", "failure_id", "poisoned"),
    (
        ("CreatePipe", 1, 0, "PSV1-HANDLE-INHERITANCE", False),
        ("CreateJobObjectW", 1, 0, "PSV1-ATTRIBUTE-LIST", False),
        ("SetInformationJobObject", 1, 0, "PSV1-ATTRIBUTE-LIST", False),
        ("InitializeProcThreadAttributeList", 2, 0, "PSV1-ATTRIBUTE-LIST", False),
        ("UpdateProcThreadAttribute", 1, 0, "PSV1-ATTRIBUTE-LIST", False),
        ("SetHandleInformation", 1, 0, "PSV1-HANDLE-INHERITANCE", False),
        ("CreateProcessW", 1, 0, "PSV1-PROCESS-CREATE", False),
        ("SetHandleInformation", 4, 0, "PSV1-INHERITANCE-POISONED", True),
        ("IsProcessInJob", 1, 0, "PSV1-TREE-VERIFICATION", False),
    ),
)
def test_creation_fault_matrix_denies_before_target_marker(
    tmp_path: Path,
    api_name: str,
    occurrence: int,
    fake: int,
    failure_id: str,
    poisoned: bool,
) -> None:
    """Every Windows creation edge settles acquired resources without target code."""
    runner = _load_runner()
    marker = tmp_path / f"fault-{api_name}-{occurrence}.txt"
    api = runner._WindowsKernelV1()
    real_k32 = api.k32
    counts: dict[str, int] = {}

    class Proxy:
        def __getattr__(self, name: str):
            original = getattr(real_k32, name)
            if name != api_name:
                return original

            def call(*args):
                counts[name] = counts.get(name, 0) + 1
                if counts[name] == occurrence:
                    return fake
                return original(*args)

            return call

    api.k32 = Proxy()
    request = _request(runner, (sys.executable, str(CHILD), "marker", "--marker", str(marker)))
    result = runner.ProcessRunnerV1(windows_api=api).run(request)
    assert result.failure_id == failure_id
    assert result.resources_closed is True
    assert result.inheritance_poisoned is poisoned
    assert not marker.exists()


def test_wait_failure_is_typed_and_settled() -> None:
    """WAIT_FAILED cannot spin until the caller deadline or report success."""
    runner = _load_runner()
    api = runner._WindowsKernelV1()
    real_k32 = api.k32

    class Proxy:
        def __getattr__(self, name: str):
            if name == "WaitForSingleObject":
                return lambda _handle, _milliseconds: 0xFFFFFFFF
            return getattr(real_k32, name)

    api.k32 = Proxy()
    started = time.monotonic()
    result = runner.ProcessRunnerV1(windows_api=api).run(
        _request(runner, (sys.executable, str(CHILD), "sleep", "--sleep", "30"), deadline=2.0)
    )
    assert result.failure_id == "PSV1-INTERNAL"
    assert result.tree.tree_empty is True
    assert time.monotonic() - started < 1.0


def test_terminate_failure_is_recorded_without_erasing_primary_failure() -> None:
    """A genuine TerminateJobObject failure uses last-close and stays ambiguous."""
    runner = _load_runner()
    api = runner._WindowsKernelV1()
    real_k32 = api.k32

    class Proxy:
        def __getattr__(self, name: str):
            original = getattr(real_k32, name)
            if name != "TerminateJobObject":
                return original

            def call(*args):
                return 0

            return call

    api.k32 = Proxy()
    result = runner.ProcessRunnerV1(windows_api=api).run(
        _request(runner, (sys.executable, str(CHILD), "infinite-writer"), limit=64 * 1024)
    )
    assert result.failure_id == "PSV1-JOB-TERMINATE"
    assert result.tree.settlement_state == "AMBIGUOUS"
    assert result.tree.tree_empty is False
    assert result.tree.job_handle_closed is True


def test_genuine_terminate_failure_outer_oracle_proves_last_close_reaps_tree(
    tmp_path: Path,
) -> None:
    """A test-only duplicate Job handle proves the production last-close transition."""
    runner = _load_runner()
    marker = tmp_path / "last-close-tree.json"
    api = runner._WindowsKernelV1()
    real_k32 = api.k32
    from ctypes import wintypes

    real_k32.GetCurrentProcess.restype = wintypes.HANDLE
    real_k32.DuplicateHandle.argtypes = [
        wintypes.HANDLE,
        wintypes.HANDLE,
        wintypes.HANDLE,
        ctypes.POINTER(wintypes.HANDLE),
        wintypes.DWORD,
        wintypes.BOOL,
        wintypes.DWORD,
    ]
    real_k32.DuplicateHandle.restype = wintypes.BOOL
    real_k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    real_k32.OpenProcess.restype = wintypes.HANDLE
    current = real_k32.GetCurrentProcess()
    original_job = None
    outer_job = wintypes.HANDLE()
    production_job_closed = threading.Event()

    class Proxy:
        def __getattr__(self, name: str):
            original = getattr(real_k32, name)
            if name == "CreateJobObjectW":
                def create(*args):
                    nonlocal original_job
                    original_job = original(*args)
                    assert original_job
                    duplicate = wintypes.HANDLE()
                    assert real_k32.DuplicateHandle(
                        current,
                        original_job,
                        current,
                        ctypes.byref(duplicate),
                        0,
                        False,
                        0x2,
                    )
                    outer_job.value = duplicate.value
                    return original_job

                return create
            if name == "TerminateJobObject":
                return lambda *_args: 0
            if name == "CloseHandle":
                def close(handle):
                    value = original(handle)
                    if original_job is not None and int(handle) == int(original_job):
                        production_job_closed.set()
                    return value

                return close
            return original

    api.k32 = Proxy()
    request = _request(
        runner,
        (
            sys.executable,
            str(CHILD),
            "tree-hold-writer",
            "--marker",
            str(marker),
        ),
        limit=64 * 1024,
        deadline=10.0,
    )
    owner = runner.ProcessRunnerV1(windows_api=api)
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(owner.run, request)
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and not marker.exists():
            time.sleep(0.01)
        assert marker.exists()
        identities = json.loads(marker.read_text(encoding="utf-8"))
        direct = real_k32.OpenProcess(
            0x00100000 | 0x0001, False, identities["directPid"]
        )
        grandchild = real_k32.OpenProcess(
            0x00100000 | 0x0001, False, identities["grandchildPid"]
        )
        assert direct and grandchild
        try:
            assert production_job_closed.wait(5.0)
            accounting = runner.JOBOBJECT_BASIC_ACCOUNTING_INFORMATION()
            returned = ctypes.c_ulong()
            assert real_k32.QueryInformationJobObject(
                outer_job.value,
                1,
                ctypes.byref(accounting),
                ctypes.sizeof(accounting),
                ctypes.byref(returned),
            )
            assert accounting.ActiveProcesses >= 2
            assert real_k32.CloseHandle(outer_job.value)
            outer_job.value = None
            assert real_k32.WaitForSingleObject(direct, 5000) == 0
            assert real_k32.WaitForSingleObject(grandchild, 5000) == 0
            result = future.result(timeout=6.0)
        finally:
            real_k32.CloseHandle(direct)
            real_k32.CloseHandle(grandchild)
            if outer_job.value:
                real_k32.CloseHandle(outer_job.value)
    before = request.capture_sink_binding.bytes_for("stdout")
    time.sleep(0.1)
    assert request.capture_sink_binding.bytes_for("stdout") == before
    assert result.failure_id == "PSV1-JOB-TERMINATE"
    assert result.tree.settlement_state == "AMBIGUOUS"
    assert result.tree.tree_empty is False


def test_query_failure_denies_tree_empty_success() -> None:
    """A failed Job active-process query cannot authorize EMPTY."""
    runner = _load_runner()
    api = runner._WindowsKernelV1()
    real_k32 = api.k32

    class Proxy:
        def __getattr__(self, name: str):
            if name == "QueryInformationJobObject":
                return lambda *_args: 0
            return getattr(real_k32, name)

    api.k32 = Proxy()
    result = runner.ProcessRunnerV1(windows_api=api).run(
        _request(runner, (sys.executable, str(CHILD), "identity"))
    )
    assert result.failure_id == "PSV1-TREE-SETTLEMENT"
    assert result.tree.tree_empty is False


def test_close_failure_overrides_apparent_success() -> None:
    """A native-handle close failure cannot leave outcome=success."""
    runner = _load_runner()
    api = runner._WindowsKernelV1()
    real_k32 = api.k32
    failed = False

    class Proxy:
        def __getattr__(self, name: str):
            original = getattr(real_k32, name)
            if name != "CloseHandle":
                return original

            def call(*args):
                nonlocal failed
                value = original(*args)
                if not failed:
                    failed = True
                    return 0
                return value

            return call

    api.k32 = Proxy()
    result = runner.ProcessRunnerV1(windows_api=api).run(
        _request(runner, (sys.executable, str(CHILD), "identity"))
    )
    assert result.failure_id == "PSV1-RESOURCE-CLOSE"
    assert result.outcome == "supervisor-failure"
    assert result.resources_closed is False


def test_capture_sink_short_write_terminates_owned_tree() -> None:
    """A short sink write becomes capture I/O failure, not partial success."""
    runner = _load_runner()

    class ShortSink(runner.MemoryCaptureSinkV1):
        def write(self, stream: str, data: bytes) -> int:
            super().write(stream, data)
            return max(0, len(data) - 1)

    request = _request(runner, (sys.executable, str(CHILD), "emit", "--bytes", "4096"))
    request = runner.dataclasses.replace(request, capture_sink_binding=ShortSink())
    result = runner.ProcessRunnerV1().run(request)
    assert result.failure_id == "PSV1-REQUEST-INVALID"
    assert result.tree.ownership_confirmed is False


def test_real_broken_stdin_pipe_reports_written_bytes_incomplete() -> None:
    """A child closing stdin before a large body is complete fails input delivery."""
    runner = _load_runner()
    request = _request(runner, (sys.executable, str(CHILD), "close-stdin", "--sleep", "30"))
    request = runner.dataclasses.replace(request, stdin_bytes=b"x" * (4 * 1024 * 1024))
    result = runner.ProcessRunnerV1().run(request)
    assert result.failure_id in {"PSV1-STDIN-BROKEN-PIPE", "PSV1-STDIN-SHORT-WRITE"}
    assert result.stdin.complete is False
    assert result.stdin.written_bytes < result.stdin.expected_bytes
    assert result.tree.tree_empty is True

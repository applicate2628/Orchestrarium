from __future__ import annotations

import concurrent.futures
import dataclasses
import hashlib
import importlib.util
import json
import os
import sys
import threading
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "process_supervision" / "process_runner.py"
CHILD = ROOT / "tests" / "fixtures" / "process_supervision" / "child_helper.py"
BENCHMARK_PROTOCOL = (
    ROOT / "tests" / "fixtures" / "process_supervision" / "benchmark_protocol.py"
)


def _load_runner():
    spec = importlib.util.spec_from_file_location("process_runner_r2_contract", RUNNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _load_benchmark_protocol():
    if not BENCHMARK_PROTOCOL.is_file():
        pytest.fail("paired benchmark protocol owner is absent")
    spec = importlib.util.spec_from_file_location(
        "process_runner_benchmark_protocol", BENCHMARK_PROTOCOL
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _policy(runner, limit: int = 1024 * 1024):
    fields = {item.name for item in dataclasses.fields(runner.CapturePolicyV1)}
    values = {
        "policy_id": "r2-contract-v1",
        "aggregate_persisted_limit": limit,
        "prefix_limit_per_stream": min(limit, 64 * 1024),
        "tail_limit_per_stream": min(limit, 128 * 1024),
        "chunk_size": 64 * 1024,
        "total_write_limit": limit + 327_680,
        "memory_limit_bytes": 512 * 1024,
        "resident_set_limit_bytes": 64 * 1024 * 1024,
        "max_threads": 3,
        "poll_interval_seconds": 0.02,
        "termination_latency_seconds": 0.25,
    }
    return runner.CapturePolicyV1(**{name: values[name] for name in fields})


def _settle_policy(runner):
    fields = {item.name for item in dataclasses.fields(runner.SettlePolicyV1)}
    values = {"timeout_seconds": 5.0, "poll_interval_seconds": 0.02}
    return runner.SettlePolicyV1(**{name: values[name] for name in fields})


def _request(runner, argv: tuple[str, ...], *, deadline: float = 5.0):
    executable = Path(sys.executable).resolve()
    environment = tuple(
        runner.EnvironmentRowV1(name, os.environ[name])
        for name in ("PATH", "SYSTEMROOT", "TEMP", "TMP")
        if name in os.environ
    )
    return runner.ProcessRequestV1(
        1,
        argv,
        executable,
        str(ROOT),
        environment,
        None,
        time.monotonic() + deadline,
        _policy(runner),
        runner.ProcessRunnerV1().mint_memory_capture_sink(),
        _settle_policy(runner),
        windows_argv_profile_id=(
            "python-validator-json-echo-v1" if os.name == "nt" else None
        ),
    )


def test_capture_policy_contains_only_enforceable_capture_values() -> None:
    """Declaration-only RSS/thread/cadence/latency/write fields must not ship."""
    runner = _load_runner()
    assert tuple(item.name for item in dataclasses.fields(runner.CapturePolicyV1)) == (
        "policy_id",
        "aggregate_persisted_limit",
        "prefix_limit_per_stream",
        "tail_limit_per_stream",
        "chunk_size",
    )
    assert tuple(item.name for item in dataclasses.fields(runner.SettlePolicyV1)) == (
        "timeout_seconds",
    )


def test_capture_tail_is_compact_bytes_and_diagnostic_storage_is_bounded() -> None:
    """The 128 KiB tail cannot use one Python object per captured byte."""
    runner = _load_runner()
    capture = runner.BoundedCaptureV1(_policy(runner))
    capture.feed("stdout", b"a" * (512 * 1024))
    capture.feed("stderr", b"b" * (512 * 1024))
    assert all(isinstance(item.tail, bytearray) for item in capture._streams.values())
    storage = sum(
        len(item.prefix) + len(item.tail) for item in capture._streams.values()
    )
    assert storage == 384 * 1024
    assert not hasattr(capture, "total_write_bytes")


@pytest.mark.skipif(os.name != "nt", reason="production backend execution is Windows-only")
def test_run_tokens_are_non_recyclable_and_safe_results_expose_only_digest() -> None:
    """Repeated calls cannot use recyclable request object addresses as identities."""
    runner = _load_runner()
    owner = runner.ProcessRunnerV1()
    digests = []
    for _ in range(24):
        request = _request(runner, (sys.executable, str(CHILD), "identity"))
        result = owner.run(request)
        assert result.outcome == "success"
        digests.append(result.run_token_sha256)
    assert len(set(digests)) == len(digests)
    assert all(len(value) == 64 for value in digests)
    safe = runner.safe_serialize_result(result)
    assert safe["runTokenSha256"] == result.run_token_sha256
    assert "runToken" not in safe


@pytest.mark.skipif(os.name != "nt", reason="real Windows active-close contract")
def test_runner_close_cancels_and_settles_active_real_run() -> None:
    """close() must cancel active work instead of raising active-runs-remain."""
    runner = _load_runner()
    started = threading.Event()

    class Port:
        def emit(self, event_id: str, _fields) -> None:
            if event_id == "process.supervision.windows.job-verified.v1":
                started.set()

    request = _request(
        runner,
        (sys.executable, str(CHILD), "sleep", "--sleep", "30"),
        deadline=10.0,
    )
    request = dataclasses.replace(request, diagnostic_port=Port())
    owner = runner.ProcessRunnerV1()
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(owner.run, request)
        assert started.wait(5.0)
        close_result = owner.close()
        result = future.result(timeout=6.0)
    assert close_result.outcome == "closed"
    assert close_result.unsettled_run_token_sha256 == ()
    assert result.failure_id == "PSV1-CANCELLED"
    assert result.cancelled is True
    assert result.tree.tree_empty is True
    refused = owner.run(_request(runner, (sys.executable, str(CHILD), "identity")))
    assert refused.failure_id == "PSV1-RUNNER-CLOSED"


@pytest.mark.skipif(os.name != "nt", reason="production backend execution is Windows-only")
def test_duplicate_request_id_and_close_complete_without_reentering_runner_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Duplicate rejection and runner close must not deadlock on the request lock."""
    runner = _load_runner()
    backend_calls = 0

    def factory(_owner, _lifecycle=None):
        def backend(
            _request,
            _supplied_lifecycle=None,
            _validated_cwd=None,
            _launch_owner=None,
        ):
            nonlocal backend_calls
            backend_calls += 1
            raise runner.ProcessSupervisionError("PSV1-CANCELLED", "cancellation")

        return backend

    owner = runner.ProcessRunnerV1(backend_factory=factory)
    if os.name == "nt":
        monkeypatch.setattr(
            owner.windows_argv_admission_owner,
            "admit",
            lambda *_args, **_kwargs: None,
        )
    request_id = "d" * 32
    first = dataclasses.replace(
        _request(runner, (sys.executable, str(CHILD), "identity")),
        request_id=request_id,
    )
    first_result = owner.run(first)
    assert first_result.failure_id == "PSV1-CANCELLED"
    assert backend_calls == 1

    release_started = threading.Event()
    original_release = owner._release_lifecycle

    def observed_release(lifecycle) -> None:
        release_started.set()
        original_release(lifecycle)

    monkeypatch.setattr(owner, "_release_lifecycle", observed_release)
    duplicate = dataclasses.replace(
        _request(runner, (sys.executable, str(CHILD), "identity")),
        request_id=request_id,
    )
    duplicate_result = []
    duplicate_done = threading.Event()

    def run_duplicate() -> None:
        try:
            duplicate_result.append(owner.run(duplicate))
        finally:
            duplicate_done.set()

    duplicate_thread = threading.Thread(target=run_duplicate, daemon=True)
    duplicate_thread.start()
    assert release_started.wait(1.0), "duplicate path did not reach lifecycle release"

    close_result = []
    close_done = threading.Event()

    def close_owner() -> None:
        try:
            close_result.append(owner.close())
        finally:
            close_done.set()

    close_thread = threading.Thread(target=close_owner, daemon=True)
    close_thread.start()
    assert duplicate_done.wait(1.0), "duplicate request deadlocked during lifecycle release"
    assert close_done.wait(1.0), "runner close deadlocked behind duplicate request"
    duplicate_thread.join(timeout=0.1)
    close_thread.join(timeout=0.1)

    assert duplicate_result[0].failure_id == "PSV1-REQUEST-INVALID"
    assert duplicate_result[0].terminal_stage == "request-validation"
    assert close_result[0].outcome == "closed"
    assert close_result[0].unsettled_run_token_sha256 == ()
    assert backend_calls == 1


@pytest.mark.skipif(os.name != "nt", reason="production backend execution is Windows-only")
def test_expected_oserror_returns_typed_result_after_one_lifecycle_finalizer() -> None:
    """Expected OS failures are returned and cannot bypass or duplicate cleanup."""
    runner = _load_runner()
    observed = []

    def factory(_owner, lifecycle=None):
        def backend(
            _request,
            supplied_lifecycle=None,
            _validated_cwd=None,
            _launch_owner=None,
        ):
            active = supplied_lifecycle or lifecycle
            assert active is not None
            active.register_resource("probe", lambda _remaining: observed.append("closed"))
            raise OSError(5, "private canary")

        return backend

    result = runner.ProcessRunnerV1(backend_factory=factory).run(
        _request(runner, (sys.executable, str(CHILD), "identity"))
    )
    assert result.failure_id == "PSV1-INTERNAL"
    assert result.outcome == "supervisor-failure"
    assert observed == ["closed"]


@pytest.mark.skipif(os.name != "nt", reason="production backend execution is Windows-only")
@pytest.mark.parametrize(
    "exception",
    (
        KeyboardInterrupt("keyboard"),
        SystemExit("system-exit"),
        GeneratorExit("generator-exit"),
    ),
)
def test_unexpected_baseexception_is_reraised_exactly_after_one_finalizer(
    exception: BaseException,
) -> None:
    """Unexpected BaseException identity and traceback survive one shared cleanup."""
    runner = _load_runner()
    observed = []

    def factory(_owner, lifecycle=None):
        def backend(
            _request,
            supplied_lifecycle=None,
            _validated_cwd=None,
            _launch_owner=None,
        ):
            active = supplied_lifecycle or lifecycle
            assert active is not None
            active.register_resource("probe", lambda _remaining: observed.append("closed"))
            raise exception

        return backend

    with pytest.raises(type(exception)) as caught:
        runner.ProcessRunnerV1(backend_factory=factory).run(
            _request(runner, (sys.executable, str(CHILD), "identity"))
        )
    assert caught.value is exception
    assert caught.value.__traceback__ is not None
    assert observed == ["closed"]


def test_worker_registry_refuses_a_fourth_worker_before_start() -> None:
    """The fixed backend capability is two readers plus at most one writer."""
    runner = _load_runner()
    token = runner.RunTokenV1(b"x" * 16, 1)
    lifecycle = runner.RunLifecycleV1(token)
    lifecycle.register_worker("stdout")
    lifecycle.register_worker("stderr")
    lifecycle.register_worker("stdin")
    with pytest.raises(runner.ProcessSupervisionError) as caught:
        lifecycle.register_worker("fourth")
    assert caught.value.failure_id == "PSV1-WORKER-LIMIT"
    assert lifecycle.worker_count == 3


@pytest.mark.skipif(os.name != "nt", reason="real Windows lifecycle cleanup")
def test_real_backend_closes_sealed_capture_sink() -> None:
    """The lifecycle closes the owner-controlled sealed sink."""
    runner = _load_runner()
    request = _request(runner, (sys.executable, str(CHILD), "identity"))
    result = runner.ProcessRunnerV1().run(request)
    assert result.outcome == "success"
    assert request.capture_sink_binding._sink._closed is True




@pytest.mark.skipif(os.name == "nt", reason="Windows generic CLI unavailable")
def test_cli_claim_precedes_capability_read(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The ready file enters lifecycle ownership before any capability-side failure."""
    runner = _load_runner()
    events = []

    def claim(*_args, **_kwargs):
        events.append("claim")
        raise runner.ProcessSupervisionError("PSV1-CLI-CLAIM", "request-validation")

    def capability(*_args, **_kwargs):
        events.append("capability")
        raise AssertionError("capability must remain unreachable")

    monkeypatch.setattr(runner, "_claim_request_file", claim)
    monkeypatch.setattr(runner, "_read_capability", capability)
    result = runner.main(
        ["--request-file", str(tmp_path / "request.ready"), "--capability-handle", "1"]
    )
    assert result == 2
    assert events == ["claim"]


@pytest.mark.parametrize(
    "fault_stage",
    (
        "after-open",
        "after-first-fstat",
        "after-register",
        "after-rename",
        "after-second-fstat",
        "during-read",
        "after-eof",
    ),
)
def test_cli_claim_faults_leave_no_ready_or_claimed_residue(
    tmp_path: Path, fault_stage: str
) -> None:
    """Every descriptor/rename/read fault is cleaned by one lifecycle owner."""
    runner = _load_runner()
    directory = tmp_path / fault_stage
    directory.mkdir(mode=0o700)
    ready = directory / "request.ready"
    ready.write_bytes(b"bounded")
    if os.name != "nt":
        ready.chmod(0o600)
    lifecycle = runner.RunLifecycleV1(runner.RunTokenV1(b"c" * 16, 1))
    with pytest.raises(runner.ProcessSupervisionError) as caught:
        claim = runner._claim_request_file(ready, lifecycle, fault_stage=fault_stage)
        if fault_stage in {"during-read", "after-eof"}:
            runner._read_claimed_request(claim, fault_stage=fault_stage)
    assert caught.value.failure_id == "PSV1-CLI-CLAIM"
    observation = lifecycle.finalize_once(time.monotonic() + 1.0)
    assert observation.state == "complete"
    assert not ready.exists()
    assert not tuple(directory.glob("*.claimed-*"))


def test_benchmark_pairs_alternate_order_and_preserve_signed_deltas() -> None:
    """Development evidence cannot be direct-first-only or clamp negative deltas."""
    protocol = _load_benchmark_protocol()
    pairs = protocol.build_pairs(
        5,
        direct=lambda index: (10.0, 30.0, 10.0, 30.0, 10.0)[index],
        supervised=lambda index: (8.0, 35.0, 9.0, 31.0, 7.0)[index],
    )
    assert [item["order"] for item in pairs] == [
        "direct-supervised",
        "supervised-direct",
        "direct-supervised",
        "supervised-direct",
        "direct-supervised",
    ]
    assert [item["signedDeltaMs"] for item in pairs] == [-2.0, 5.0, -1.0, 1.0, -3.0]
    assert all("directMs" in item and "supervisedMs" in item for item in pairs)


def test_five_pairs_are_development_only_and_production_p95_needs_forty() -> None:
    """An N=5 cohort cannot emit a production percentile verdict."""
    protocol = _load_benchmark_protocol()
    pairs = [
        {
            "order": "direct-supervised" if index % 2 == 0 else "supervised-direct",
            "directMs": 100.0,
            "supervisedMs": 110.0,
            "signedDeltaMs": 10.0,
        }
        for index in range(5)
    ]
    development = protocol.summarize_pairs(pairs, production=False)
    assert development["cohortKind"] == "development"
    assert "productionP95" not in development
    assert "productionVerdict" not in development
    with pytest.raises(ValueError, match="at least 40"):
        protocol.summarize_pairs(pairs, production=True)


def test_process_runner_activation_inventory_is_exact_and_python_only() -> None:
    """Only the three approved Python consumers import the canonical runner."""
    active = {
        ROOT / "scripts" / "provider_prompt.py": "process_supervision.process_runner",
        ROOT / "scripts" / "skill_pack_validator_runtime.py": (
            '"process_supervision" / "process_runner.py"'
        ),
        ROOT / "scripts" / "validate-slice-a-detached.py": (
            "process_supervision.process_runner"
        ),
    }
    inactive = (
        ROOT / "scripts" / "process_supervision" / "guarded_launcher.py",
        ROOT / "scripts" / "process_supervision" / "route_activation_registry.py",
    )
    for path, marker in active.items():
        text = path.read_text(encoding="utf-8")
        assert marker in text
    for path in inactive:
        text = path.read_text(encoding="utf-8")
        assert "process_supervision.process_runner" not in text
        assert "process_runner import" not in text
    runner_text = RUNNER_PATH.read_text(encoding="utf-8")
    assert "import rust" not in runner_text.casefold()
    assert "cargo" not in runner_text.casefold()

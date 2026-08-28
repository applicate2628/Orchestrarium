from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = ROOT / "scripts" / "process_supervision" / "process_runner.py"
CHILD = ROOT / "tests" / "fixtures" / "process_supervision" / "child_helper.py"
PUBLIC_PROCESS_SUPERVISION_DOCS = (
    ROOT / "README.md",
    ROOT / "INSTALL.md",
    ROOT / "RELEASE_NOTES.md",
)


def _load_runner():
    if not RUNNER_PATH.is_file():
        pytest.fail("ProcessRunnerV1 production module is absent")
    spec = importlib.util.spec_from_file_location("process_runner_core_test", RUNNER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_public_provider_launch_contract_is_linux_only() -> None:
    """Catches public docs widening the Linux backend to generic POSIX hosts."""

    for path in PUBLIC_PROCESS_SUPERVISION_DOCS:
        text = path.read_text(encoding="utf-8")
        assert "Linux Codex and Claude launches are active" in text
        assert "no macOS/Darwin backend is shipped" in text
        assert "POSIX Codex and Claude launches are active" not in text


def _policy(runner, *, limit: int = 1024 * 1024):
    return runner.CapturePolicyV1(
        policy_id="test-bounded-v1",
        aggregate_persisted_limit=limit,
        prefix_limit_per_stream=min(64 * 1024, limit),
        tail_limit_per_stream=min(128 * 1024, limit),
        chunk_size=64 * 1024,
    )


def _request(runner, argv: tuple[str, ...], *, stdin: bytes | None = None, limit: int = 1024 * 1024, deadline: float = 10.0):
    executable = Path(sys.executable).resolve()
    return runner.ProcessRequestV1(
        schema_version=1,
        argv=argv,
        resolved_executable=executable,
        cwd=str(ROOT),
        environment=tuple(
            runner.EnvironmentRowV1(k, os.environ[k])
            for k in ("PATH", "SYSTEMROOT", "TEMP", "TMP")
            if k in os.environ
        ),
        stdin_bytes=stdin,
        deadline_monotonic=time.monotonic() + deadline,
        capture_policy=_policy(runner, limit=limit),
        capture_sink_binding=runner.ProcessRunnerV1().mint_memory_capture_sink(),
        settle_policy=runner.SettlePolicyV1(timeout_seconds=5.0),
        windows_argv_profile_id=(
            "python-validator-json-echo-v1" if os.name == "nt" else None
        ),
    )


def test_windows_abi_layout_matches_pointer_width() -> None:
    """Catches pointer truncation or a wrong STARTUPINFOEX/PROCESS_INFORMATION layout."""
    runner = _load_runner()
    if os.name != "nt":
        pytest.skip("Windows ABI contract")
    layout = runner.windows_abi_layout()
    assert layout["pointerBits"] == struct.calcsize("P") * 8
    assert layout["startupInfoExSize"] >= layout["startupInfoSize"] + struct.calcsize("P")
    assert layout["processInformationSize"] == struct.calcsize("P") * 2 + 8


@pytest.mark.parametrize(
    "bad_argv",
    (
        (),
        ("ok", "nul\x00bad"),
        tuple("x" for _ in range(1025)),
        ("x" * (32 * 1024 + 1),),
    ),
)
def test_request_validation_rejects_invalid_argv_before_backend(bad_argv: tuple[str, ...]) -> None:
    """Catches launch-resource acquisition before argv bounds and NUL checks."""
    runner = _load_runner()
    request = _request(runner, (sys.executable, str(CHILD), "identity"))
    request = runner.dataclasses.replace(request, argv=bad_argv)
    called = False

    def backend(_request):
        nonlocal called
        called = True
        raise AssertionError("backend must remain unreachable")

    result = runner.ProcessRunnerV1(backend_factory=lambda *_: backend).run(request)
    assert result.failure_id == "PSV1-REQUEST-INVALID"
    assert result.terminal_stage == "request-validation"
    assert called is False


def test_write_all_handles_partial_positive_writes() -> None:
    """Catches treating one short positive write as complete stdin delivery."""
    runner = _load_runner()
    chunks: list[bytes] = []

    def partial(view: memoryview) -> int:
        data = bytes(view[:3])
        chunks.append(data)
        return len(data)

    written = runner.write_all_bytes(b"abcdefghij", partial)
    assert written == 10
    assert b"".join(chunks) == b"abcdefghij"


def test_write_all_rejects_zero_progress() -> None:
    """Catches an infinite stdin loop after a zero-byte write."""
    runner = _load_runner()
    with pytest.raises(runner.ProcessSupervisionError) as caught:
        runner.write_all_bytes(b"payload", lambda _view: 0)
    assert caught.value.failure_id == "PSV1-STDIN-SHORT-WRITE"


def test_capture_exact_limit_and_overflow_have_stable_counts() -> None:
    """Catches aggregate persistence beyond the injected capture ceiling."""
    runner = _load_runner()
    capture = runner.BoundedCaptureV1(_policy(runner, limit=8))
    capture.feed("stdout", b"1234")
    capture.feed("stderr", b"abcd")
    assert capture.limit_crossed is False
    capture.feed("stdout", b"Z")
    snapshot = capture.snapshot()
    assert capture.limit_crossed is True
    assert snapshot["stdout"].observed_bytes == 5
    assert snapshot["stdout"].persisted_bytes == 4
    assert snapshot["stderr"].persisted_bytes == 4
    assert sum(item.persisted_bytes for item in snapshot.values()) == 8


def test_capture_prefix_tail_and_digest_cover_persisted_bytes() -> None:
    """Catches diagnostic views or digests being computed from different bytes."""
    runner = _load_runner()
    policy = runner.dataclasses.replace(
        _policy(runner, limit=32),
        prefix_limit_per_stream=4,
        tail_limit_per_stream=5,
    )
    capture = runner.BoundedCaptureV1(policy)
    capture.feed("stdout", b"0123456789")
    stream = capture.snapshot()["stdout"]
    assert stream.prefix_bytes == b"0123"
    assert stream.tail_bytes == b"56789"
    assert stream.digest == hashlib.sha256(b"0123456789").hexdigest()


def test_result_freeze_rejects_capture_crossed_after_child_exit() -> None:
    """Catches a fast child exiting before the polling loop observes overflow."""

    runner = _load_runner()
    request = _request(
        runner,
        (sys.executable, str(CHILD), "identity"),
        limit=8,
    )
    capture = runner.BoundedCaptureV1(
        request.capture_policy, request.capture_sink_binding
    )
    capture.feed("stdout", b"123456789")

    result = runner._result_from_parts(
        request,
        time.monotonic(),
        backend="controlled-post-exit-v1",
        capture=capture,
        stdin_state={"written": 0, "complete": True},
        exit_code=0,
        failure_id=None,
        stage="completed",
        timed_out=False,
        cancelled=False,
        ownership_confirmed=True,
        settlement_state="EMPTY",
        direct_reaped=True,
        primary_thread_closed=True,
        job_handle_closed=True,
        resources_closed=True,
        poisoned=False,
        cleanup_issues=(),
    )

    assert result.outcome == "supervisor-failure"
    assert result.failure_id == "PSV1-CAPTURE-LIMIT"
    assert result.terminal_stage == "capture-limit"
    assert result.target_exit_code == 0
    assert result.stdout.truncated is True


def test_finalizer_is_idempotent_and_preserves_original_baseexception() -> None:
    """Catches repeated cleanup or replacement of the primary BaseException."""
    runner = _load_runner()
    calls: list[str] = []
    finalizer = runner.FinalizerV1((lambda: calls.append("pipes"), lambda: calls.append("job")))
    original = KeyboardInterrupt("canary")
    with pytest.raises(KeyboardInterrupt) as caught:
        try:
            raise original
        except BaseException:
            finalizer.finalize_once()
            finalizer.finalize_once()
            raise
    assert caught.value is original
    assert calls == ["job", "pipes"]
    assert finalizer.observation.resources_closed is True


def test_posix_oracle_requires_two_complete_empty_observations() -> None:
    """Catches one weak census or killpg observation authorizing EMPTY."""
    runner = _load_runner()
    leader = runner.PosixProcessIdentityV1(10, "start", 10, 10, 1, 1)
    oracle = runner.PosixGroupSettlementOracleV1(leader)
    first = oracle.observe(1, (), "esrch", leader_reaped=True)
    second = oracle.observe(2, (), "esrch", leader_reaped=True)
    assert first.state == "AMBIGUOUS"
    assert second.state == "EMPTY"


def test_safe_serializer_is_fixed_nonauthorizing_allowlist() -> None:
    """Catches raw paths, arguments, environment, output, or cleanup text leaking."""
    runner = _load_runner()
    request = _request(runner, (sys.executable, str(CHILD), "identity"))
    result = runner.ProcessRunnerV1().run(request)
    safe = runner.safe_serialize_result(result)
    encoded = json.dumps(safe, sort_keys=True)
    assert safe["authorizing"] is False
    assert safe["closesRunIds"] == []
    assert safe["terminalClass"] == "process-observation-nonauthorizing"
    for canary in (str(ROOT), str(CHILD), sys.executable, "PATH", "identity"):
        assert canary not in encoded


def test_real_runner_delivers_complete_stdin_and_settles() -> None:
    """Catches successful return before input, capture, tree, or resource settlement."""
    runner = _load_runner()
    payload = (b"short-write-proof-" * 4096) + b"end"
    request = _request(
        runner,
        (sys.executable, str(CHILD), "echo-stdin"),
        stdin=payload,
        limit=len(payload) + 1024,
    )
    result = runner.ProcessRunnerV1().run(request)
    assert result.outcome == "success"
    assert result.stdin.complete is True
    assert result.stdin.written_bytes == len(payload)
    assert result.stdout.persisted_bytes == len(payload)
    assert result.stdout.digest == hashlib.sha256(payload).hexdigest()
    assert result.tree.tree_empty is True
    assert result.tree.direct_reaped is True
    assert result.resources_closed is True


def test_capture_limit_terminates_infinite_writer_with_stable_size() -> None:
    """Catches an infinite writer growing persisted capture after the cap."""
    runner = _load_runner()
    request = _request(
        runner,
        (sys.executable, str(CHILD), "infinite-writer"),
        limit=128 * 1024,
        deadline=5.0,
    )
    result = runner.ProcessRunnerV1().run(request)
    assert result.failure_id == "PSV1-CAPTURE-LIMIT"
    assert result.terminal_stage == "capture-limit"
    assert result.stdout.persisted_bytes + result.stderr.persisted_bytes == 128 * 1024
    assert result.stdout.truncated is True
    assert result.tree.tree_empty is True
    assert result.resources_closed is True


def test_msvcrt_serializer_matches_python_standard_library() -> None:
    """Catches quote/backslash drift from the attested Microsoft C runtime codec."""
    runner = _load_runner()
    argv = (
        "",
        "plain",
        "two words",
        'quote"inside',
        'backslashes\\before"quote',
        "C:\\path with space\\",
        "Москва-测试",
    )
    assert runner.serialize_msvcrt_argv(argv) == subprocess.list2cmdline(argv)


def test_request_bundle_rejects_duplicate_json_keys_and_trailing_data() -> None:
    """Catches ambiguous CLI request headers and bytes after the bound digest."""
    runner = _load_runner()
    header = b'{"schema":"orchestrarium.process-request.v1","schema":"duplicate"}'
    body = b"OPSRQV1\x00" + struct.pack(">I", len(header)) + header + struct.pack(">Q", 0)
    bundle = body + hashlib.sha256(body).digest()
    with pytest.raises(runner.ProcessSupervisionError) as duplicate:
        runner.decode_request_bundle(bundle)
    assert duplicate.value.failure_id == "PSV1-REQUEST-INVALID"
    with pytest.raises(runner.ProcessSupervisionError) as trailing:
        runner.decode_request_bundle(bundle + b"x")
    assert trailing.value.failure_id == "PSV1-REQUEST-INVALID"

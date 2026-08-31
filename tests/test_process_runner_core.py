from __future__ import annotations

import ast
import concurrent.futures
import dataclasses
import hashlib
import importlib.util
import json
import os
import shutil
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


def test_public_process_launch_contract_is_windows_only() -> None:
    """Public docs must expose the fail-closed POSIX containment boundary."""

    for path in PUBLIC_PROCESS_SUPERVISION_DOCS:
        text = path.read_text(encoding="utf-8")
        contract_subject = (
            "Generic POSIX launches"
            if path.name == "RELEASE_NOTES.md"
            else "All POSIX process launches"
        )
        assert (
            f"{contract_subject} fail at request validation with "
            "`PSV1-POSIX-ORACLE-UNAVAILABLE` before executable acquisition or "
            "subprocess creation."
        ) in text
        if path.name != "RELEASE_NOTES.md":
            assert "Linux Codex and Claude launches are active" not in text


@pytest.mark.parametrize("execution_shape", ("normal", "nonzero", "timeout", "cancel"))
@pytest.mark.parametrize("launch_surface", ("popen", "backend"))
def test_posix_containment_refuses_before_every_launch_surface(
    monkeypatch: pytest.MonkeyPatch,
    execution_shape: str,
    launch_surface: str,
) -> None:
    """POSIX containment must precede every possible execution outcome."""

    runner = _load_runner()
    launch_calls: list[str] = []

    def backend_factory(_owner, _lifecycle):
        def backend(*_args, **_kwargs):
            launch_calls.append(f"backend:{execution_shape}")
            raise AssertionError("POSIX backend was reached")

        return backend

    owner = runner.ProcessRunnerV1(
        backend_factory=backend_factory if launch_surface == "backend" else None
    )
    argv = (sys.executable, str(CHILD), "identity")
    if execution_shape == "nonzero":
        argv = (*argv, "--exit-code", "7")
    request = _request(runner, argv)
    if execution_shape == "timeout":
        request = dataclasses.replace(request, deadline_monotonic=time.monotonic() - 1.0)
    elif execution_shape == "cancel":
        request = dataclasses.replace(request, cancellation_probe=lambda: True)

    original_is_file = runner.Path.is_file
    monkeypatch.setattr(runner.os, "name", "posix")
    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(
        runner.Path,
        "is_file",
        lambda path: True
        if path.as_posix() == "/proc/self/stat"
        else original_is_file(path),
    )
    cwd_identity = runner.CwdIdentityV1(1, 2, 3, "owner", 0)
    validated = runner.ValidatedCwdV1(str(ROOT), cwd_identity, "0" * 64)
    monkeypatch.setattr(runner, "validate_process_request", lambda *_args, **_kwargs: validated)
    monkeypatch.setattr(runner, "bind_cwd_identity", lambda _path: cwd_identity)

    class LaunchOwner:
        descriptor = 0
        identity_sha256 = "0" * 64
    monkeypatch.setattr(
        runner, "_acquire_executable_launch_owner", lambda *_args, **_kwargs: LaunchOwner()
    )

    def forbidden_popen(*_args, **_kwargs):
        launch_calls.append(f"popen:{execution_shape}")
        raise AssertionError("subprocess.Popen was reached")

    monkeypatch.setattr(runner.subprocess, "Popen", forbidden_popen)

    result = owner.run(request)

    assert result.outcome == "supervisor-failure"
    assert result.failure_id == "PSV1-POSIX-ORACLE-UNAVAILABLE"
    assert result.terminal_stage == "request-validation"
    assert result.tree.tree_empty is False
    assert result.tree.settlement_state == "AMBIGUOUS"
    assert result.resources_closed is True
    assert launch_calls == []


def test_process_runner_source_has_no_posix_backend() -> None:
    """The fail-closed POSIX contract must not retain an unreachable backend."""

    tree = ast.parse(RUNNER_PATH.read_text(encoding="utf-8"))
    classes = {
        node.name: node for node in tree.body if isinstance(node, ast.ClassDef)
    }
    assert "_PosixBackendV1" not in classes


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
        argv=(str(executable), *argv[1:]),
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










def test_hook_health_spool_sink_is_unbounded_only_for_stdout(tmp_path: Path) -> None:
    runner = _load_runner()
    spool_path = tmp_path / "health.stdout"
    stdout = b"S" * (runner.HOOK_HEALTH_STDERR_LIMIT_BYTES * 2)
    stderr = b"E" * (runner.HOOK_HEALTH_STDERR_LIMIT_BYTES + 1)
    script = tmp_path / "check-hook-health.py"
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    with spool_path.open("w+b") as spool:
        owner = runner.ProcessRunnerV1()
        request = owner.build_hook_health_request(
            argv=(str(Path(sys.executable).resolve()), str(script)),
            resolved_executable=Path(sys.executable).resolve(),
            cwd=str(tmp_path),
            environment=(),
            deadline_monotonic=time.monotonic() + 10.0,
            settle_timeout_seconds=1.0,
            stdout_spool=spool,
            trusted_script=script,
        )
        runner.validate_process_request(request)
        binding = request.capture_sink_binding
        capture = runner.BoundedCaptureV1(
            runner.hook_health_capture_policy(), binding
        )
        capture.feed("stdout", stdout)
        assert capture.limit_crossed is False
        capture.feed("stderr", stderr)
        assert capture.limit_crossed is True
        binding.close()
        spool.seek(0)
        assert spool.read() == stdout
        assert binding.bytes_for("stderr") == stderr[
            : runner.HOOK_HEALTH_STDERR_LIMIT_BYTES
        ]


def _hook_health_request(runner, tmp_path: Path, spool):
    script = tmp_path / "check-hook-health.py"
    script.write_text("raise SystemExit(0)\n", encoding="utf-8")
    owner = runner.ProcessRunnerV1()
    request = owner.build_hook_health_request(
        argv=(str(Path(sys.executable).resolve()), str(script)),
        resolved_executable=Path(sys.executable).resolve(),
        cwd=str(tmp_path),
        environment=(),
        deadline_monotonic=time.monotonic() + 10.0,
        settle_timeout_seconds=1.0,
        stdout_spool=spool,
        trusted_script=script,
    )
    return owner, request, script


@pytest.mark.parametrize(
    "mutation",
    ("generic-profile", "posix-non-hook-request"),
)
def test_hook_health_spool_capability_rejects_request_mutation(
    tmp_path: Path, mutation: str
) -> None:
    runner = _load_runner()
    with (tmp_path / "stdout.spool").open("w+b") as spool:
        _owner, request, _script = _hook_health_request(runner, tmp_path, spool)
        if mutation == "generic-profile":
            request = runner.dataclasses.replace(
                request,
                windows_argv_profile_id="python-validator-json-echo-v1",
            )
        else:
            request = runner.dataclasses.replace(
                request,
                argv=(*request.argv, "--not-hook-health"),
            )
        with pytest.raises(runner.ProcessSupervisionError) as failure:
            runner.validate_process_request(request)
        assert failure.value.failure_id == "PSV1-REQUEST-INVALID"


def test_hook_health_factory_rejects_untrusted_same_basename(tmp_path: Path) -> None:
    runner = _load_runner()
    trusted = tmp_path / "trusted" / "check-hook-health.py"
    candidate = tmp_path / "candidate" / "check-hook-health.py"
    trusted.parent.mkdir()
    candidate.parent.mkdir()
    trusted.write_text("raise SystemExit(0)\n", encoding="utf-8")
    candidate.write_text("raise SystemExit(1)\n", encoding="utf-8")
    with (tmp_path / "stdout.spool").open("w+b") as spool:
        with pytest.raises(runner.ProcessSupervisionError):
            runner.ProcessRunnerV1().build_hook_health_request(
                argv=(str(Path(sys.executable).resolve()), str(candidate)),
                resolved_executable=Path(sys.executable).resolve(),
                cwd=str(tmp_path),
                environment=(),
                deadline_monotonic=time.monotonic() + 10.0,
                settle_timeout_seconds=1.0,
                stdout_spool=spool,
                trusted_script=trusted,
            )


def test_hook_health_spool_capability_rejects_replay_and_script_drift(
    tmp_path: Path,
) -> None:
    runner = _load_runner()
    with (tmp_path / "stdout.spool").open("w+b") as spool:
        _owner, request, script = _hook_health_request(runner, tmp_path, spool)
        runner.validate_process_request(request)
        with pytest.raises(runner.ProcessSupervisionError):
            runner.validate_process_request(request)

    with (tmp_path / "drift.stdout.spool").open("w+b") as spool:
        _owner, request, script = _hook_health_request(runner, tmp_path, spool)
        script.write_text("raise SystemExit(7)\n", encoding="utf-8")
        with pytest.raises(runner.ProcessSupervisionError):
            runner.validate_process_request(request)


def test_hook_health_capability_rejects_repaired_spool_binding(tmp_path: Path) -> None:
    runner = _load_runner()
    spool_a_path = tmp_path / "a.spool"
    spool_b_path = tmp_path / "b.spool"
    with spool_a_path.open("w+b") as spool_a, spool_b_path.open("w+b") as spool_b:
        _owner, request, _script = _hook_health_request(runner, tmp_path, spool_a)
        replacement_sink = runner.HookHealthSpoolCaptureSinkV1(spool_b)
        replacement_binding = runner.dataclasses.replace(
            request.capture_sink_binding,
            _sink=replacement_sink,
        )
        replacement = runner.dataclasses.replace(
            request,
            capture_sink_binding=replacement_binding,
        )
        with pytest.raises(runner.ProcessSupervisionError) as failure:
            runner.validate_process_request(replacement)
        assert failure.value.failure_id == "PSV1-REQUEST-INVALID"
        spool_b.seek(0)
        assert spool_b.read() == b""


def test_repository_transfer_git_request_uses_the_sealed_profile(tmp_path: Path) -> None:
    runner = _load_runner()
    git = Path(shutil.which("git") or "").resolve()
    assert git.is_file()
    owner = runner.ProcessRunnerV1()
    request, sink = owner.build_repository_transfer_git_request(
        argv=(str(git), "rev-parse", "--show-toplevel"),
        resolved_executable=git,
        cwd=str(tmp_path),
        environment=(),
        capture_limit_bytes=8 * 1024 * 1024,
    )
    assert request.policy_id == "repository-transfer-git-v1"
    assert request.capture_policy.policy_id == "repository-transfer-git-v1"
    assert request.capture_policy.aggregate_persisted_limit == 16 * 1024 * 1024
    assert request.capture_policy.per_stream_persisted_limit == 8 * 1024 * 1024
    assert request.windows_argv_profile_id == (
        "repository-transfer-git-v1" if os.name == "nt" else None
    )
    assert request.capture_sink_binding is sink
    with pytest.raises(runner.ProcessSupervisionError, match="PSV1-REQUEST-INVALID"):
        owner.build_repository_transfer_git_request(
            argv=(sys.executable, "-c", "pass"),
            resolved_executable=Path(sys.executable),
            cwd=str(tmp_path),
            environment=(),
            capture_limit_bytes=8 * 1024 * 1024,
        )
    owner.close()








def test_windows_abi_layout_matches_pointer_width() -> None:
    """Catches pointer truncation or a wrong STARTUPINFOEX/PROCESS_INFORMATION layout."""
    runner = _load_runner()
    if os.name != "nt":
        pytest.skip("Windows ABI contract")
    layout = runner.windows_abi_layout()
    assert layout["pointerBits"] == struct.calcsize("P") * 8
    assert layout["startupInfoExSize"] >= layout["startupInfoSize"] + struct.calcsize("P")
    assert layout["processInformationSize"] == struct.calcsize("P") * 2 + 8


def test_run_returns_typed_request_failure_for_non_request_object() -> None:
    """Catches failure formatting dereferencing an input already rejected by type."""
    runner = _load_runner()

    result = runner.ProcessRunnerV1().run(object())

    assert result.outcome == "supervisor-failure"
    assert result.failure_id == "PSV1-REQUEST-INVALID"
    assert result.terminal_stage == "request-validation"
    assert result.resolved_executable == ""
    assert result.argv_count == 0
    assert result.stdin.expected_bytes == 0
    assert result.stdin.complete is True
    assert result.policy_id is None


@pytest.mark.parametrize(
    ("field", "malformed", "expected_attribute"),
    (
        ("argv", object(), ("argv_count", 0)),
        ("argv", ("\ud800",), ("argv_count", 0)),
        ("resolved_executable", object(), ("resolved_executable", "")),
        ("resolved_executable", Path("\ud800"), ("resolved_executable", "")),
        ("stdin_bytes", object(), ("stdin.expected_bytes", 0)),
    ),
)
def test_request_failure_formatting_is_total_for_malformed_fields(
    field: str,
    malformed: object,
    expected_attribute: tuple[str, object],
) -> None:
    """Catches a rejected dataclass field escaping as a formatter exception."""
    runner = _load_runner()
    request = _request(runner, (sys.executable, str(CHILD), "identity"))
    request = dataclasses.replace(
        request,
        schema_version=0,
        **{field: malformed},
    )

    result = runner.ProcessRunnerV1().run(request)

    assert result.outcome == "supervisor-failure"
    assert result.failure_id == "PSV1-REQUEST-INVALID"
    assert result.terminal_stage == "request-validation"
    attribute, expected = expected_attribute
    if attribute == "stdin.expected_bytes":
        observed = result.stdin.expected_bytes
    else:
        observed = getattr(result, attribute)
    assert observed == expected


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
        executable_identity_sha256=runner.resolve_executable_identity(
            request.resolved_executable
        ),
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


@pytest.mark.skipif(os.name != "nt", reason="production ProcessRunner execution is Windows-only")
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


@pytest.mark.skipif(os.name != "nt", reason="production ProcessRunner execution is Windows-only")
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

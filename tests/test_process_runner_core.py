from __future__ import annotations

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


def _linux_pid_state_and_start_marker(pid: int) -> tuple[str, str] | None:
    """Return the currently bound Linux PID identity, or None after exit."""

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    try:
        raw = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except OSError:
        return None
    close = raw.rfind(")")
    fields = raw[close + 2 :].split()
    if len(fields) < 20:
        pytest.fail(f"unparseable /proc stat for descendant PID {pid}")
    return fields[0], fields[19]


def _descendant_is_terminated(pid: int, start_marker: str) -> bool:
    """Accept only exit, PID reuse, or the Linux zombie terminal state."""

    observation = _linux_pid_state_and_start_marker(pid)
    return (
        observation is None
        or observation[1] != start_marker
        or observation[0] == "Z"
    )


def _kill_descendant_if_same_live_identity(pid: int, start_marker: str) -> None:
    """Avoid signalling a PID that has been reused after the test's child exited."""

    observation = _linux_pid_state_and_start_marker(pid)
    if (
        observation is not None
        and observation[1] == start_marker
        and observation[0] != "Z"
    ):
        os.kill(pid, 9)


@pytest.mark.parametrize("state", ("R", "S", "T"))
def test_descendant_oracle_rejects_live_states(monkeypatch, state: str) -> None:
    """A zombie-only terminal exception must not hide live descendants."""

    monkeypatch.setattr(
        sys.modules[__name__],
        "_linux_pid_state_and_start_marker",
        lambda _pid: (state, "start"),
    )
    assert _descendant_is_terminated(12345, "start") is False


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


@pytest.mark.skipif(
    os.name == "nt" or not sys.platform.startswith("linux"),
    reason="Linux process-group oracle required",
)
def test_posix_parent_exit_settles_descendant_before_reader_join(
    tmp_path: Path,
) -> None:
    """Catches pipe readers being joined before the owned group is terminated."""

    runner = _load_runner()
    marker = tmp_path / "descendant.pid"
    parent = tmp_path / "spawn_descendant.py"
    parent.write_text(
        "from pathlib import Path\n"
        "import json, subprocess, sys\n"
        "child = subprocess.Popen(\n"
        "    [sys.executable, '-c', 'import time; time.sleep(30)'],\n"
        "    stdin=subprocess.DEVNULL, stdout=sys.stdout, stderr=sys.stderr,\n"
        "    close_fds=False,\n"
        ")\n"
        "raw = Path(f'/proc/{child.pid}/stat').read_text(encoding='ascii')\n"
        "fields = raw[raw.rfind(')') + 2:].split()\n"
        "Path(sys.argv[1]).write_text(\n"
        "    json.dumps({'pid': child.pid, 'start_marker': fields[19]}),\n"
        "    encoding='utf-8',\n"
        ")\n",
        encoding="utf-8",
    )
    python = str(Path(sys.executable).resolve())
    request = _request(
        runner,
        (python, str(parent), str(marker)),
        deadline=5.0,
    )
    request = dataclasses.replace(
        request,
        cwd=str(tmp_path),
        settle_policy=runner.SettlePolicyV1(timeout_seconds=2.0),
    )
    owner = runner.ProcessRunnerV1()
    descendant_pid: int | None = None
    descendant_start_marker: str | None = None
    started = time.monotonic()
    try:
        result = owner.run(request)
        elapsed = time.monotonic() - started
        assert marker.is_file(), f"descendant PID was not published: {result!r}"
        descendant = json.loads(marker.read_text(encoding="utf-8"))
        descendant_pid = int(descendant["pid"])
        descendant_start_marker = str(descendant["start_marker"])
        assert elapsed < 3.0, "reader joins consumed settlement time before kill"
        assert result.failure_id == "PSV1-TREE-SETTLEMENT"
        assert result.tree.ownership_confirmed is True
        assert result.tree.direct_reaped is True
        assert result.resources_closed is True
        deadline = time.monotonic() + 3.0
        while time.monotonic() < deadline:
            if _descendant_is_terminated(
                descendant_pid, descendant_start_marker
            ):
                break
            time.sleep(0.02)
        else:
            pytest.fail("pipe-inheriting descendant survived runner return")
    finally:
        owner.close()
        if descendant_pid is not None and descendant_start_marker is not None:
            _kill_descendant_if_same_live_identity(
                descendant_pid, descendant_start_marker
            )


@pytest.mark.skipif(
    os.name == "nt" or not sys.platform.startswith("linux"),
    reason="Linux /proc zombie state required",
)
def test_linux_descendant_oracle_accepts_zombie_not_live_or_reused_pid() -> None:
    """Catches kill(pid, 0) treating a zombie as a surviving descendant."""

    live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    zombie = subprocess.Popen([sys.executable, "-c", "pass"])
    try:
        live_identity = _linux_pid_state_and_start_marker(live.pid)
        assert live_identity is not None
        assert live_identity[0] != "Z"
        assert _descendant_is_terminated(live.pid, live_identity[1]) is False
        assert _descendant_is_terminated(live.pid, f"reused:{live_identity[1]}") is True

        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            zombie_identity = _linux_pid_state_and_start_marker(zombie.pid)
            if zombie_identity is not None and zombie_identity[0] == "Z":
                break
            time.sleep(0.01)
        else:
            pytest.fail("fixture child did not become a Linux zombie")
        assert _descendant_is_terminated(zombie.pid, zombie_identity[1]) is True
    finally:
        if live.poll() is None:
            live.kill()
        live.wait()
        zombie.wait()


@pytest.mark.skipif(os.name == "nt", reason="POSIX executable replacement contract")
def test_result_keeps_prelaunch_executable_identity_after_path_replacement(
    tmp_path: Path,
) -> None:
    runner = _load_runner()
    executable = tmp_path / "python-copy"
    replacement = tmp_path / "replacement"
    shutil.copy2(Path(sys.executable).resolve(), executable)
    shutil.copy2(Path(sys.executable).resolve(), replacement)
    replacement.write_bytes(replacement.read_bytes() + b"replacement")
    executable.chmod(0o755)
    replacement.chmod(0o755)
    marker = tmp_path / "ready"
    expected_identity = runner.resolve_executable_identity(executable)
    owner = runner.ProcessRunnerV1()
    request = runner.ProcessRequestV1(
        schema_version=1,
        argv=(
            str(executable),
            "-c",
            (
                "from pathlib import Path; import time; "
                f"Path({str(marker)!r}).write_text('ready'); time.sleep(0.5)"
            ),
        ),
        resolved_executable=executable,
        cwd=str(tmp_path),
        environment=(),
        stdin_bytes=None,
        deadline_monotonic=time.monotonic() + 5.0,
        capture_policy=_policy(runner),
        capture_sink_binding=owner.mint_memory_capture_sink(),
        settle_policy=runner.SettlePolicyV1(1.0),
    )
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(owner.run, request)
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline and not marker.exists():
            time.sleep(0.01)
        assert marker.is_file()
        os.replace(replacement, executable)
        result = future.result(timeout=4.0)
    assert result.executable_identity_sha256 == expected_identity
    assert runner.resolve_executable_identity(executable) != expected_identity


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

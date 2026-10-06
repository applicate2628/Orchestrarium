"""Native Windows regression tests for creation-time Job ownership."""

from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys
import time

import pytest


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows Job contract")


def test_job_membership_precedes_first_child_instruction(tmp_path: Path) -> None:
    """Removing suspended Job verification would let the marker appear early."""
    job = importlib.import_module("scripts.process_supervision.windows_job")
    marker = tmp_path / "first-instruction.txt"
    checked = False

    def before_resume() -> None:
        nonlocal checked
        checked = True
        assert not marker.exists()

    code = (
        "import pathlib,sys;"
        "pathlib.Path(sys.argv[1]).write_text('ran',encoding='ascii');"
        "sys.stdout.buffer.write(b'\\x00\\xff')"
    )
    process = job.WindowsJobOwnerV1.launch(
        executable=sys.executable,
        argv=(sys.executable, "-c", code, str(marker)),
        cwd=str(tmp_path),
        environment=dict(os.environ),
        before_resume=before_resume,
    )
    stdout_fd = process.take_stdout_fd()
    stdin_fd = process.take_stdin_fd()
    stderr_fd = process.take_stderr_fd()
    try:
        assert checked
        assert stdout_fd is not None
        assert stdin_fd is not None
        assert stderr_fd is not None
        os.close(stdin_fd)
        stdin_fd = None
        assert os.read(stdout_fd, 2) == b"\x00\xff"
        assert process.wait(time.monotonic() + 5.0) == 0
        closure = process.settle(time.monotonic() + 5.0)
        assert closure.complete
        assert closure.direct_reaped
        assert closure.active_zero
        assert closure.handles_closed
        assert marker.read_text(encoding="ascii") == "ran"
    finally:
        for fd in (stdin_fd, stdout_fd, stderr_fd):
            if fd is not None:
                os.close(fd)
        process.close()


def test_natural_completion_after_positive_accounting_snapshot_is_not_terminated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A real earlier positive snapshot must not force an already-empty Job."""
    job = importlib.import_module("scripts.process_supervision.windows_job")
    process = job.WindowsJobOwnerV1.launch(
        executable=sys.executable,
        argv=(sys.executable, "-B", "-c", "import sys; sys.stdin.buffer.read(1)"),
        cwd=str(tmp_path),
        environment=dict(os.environ),
        stdout="null",
        stderr="null",
    )
    stdin_fd = process.take_stdin_fd()
    deadline = time.monotonic() + 5.0
    original_query = process._active_processes
    delayed = False

    def delayed_native_snapshot() -> int:
        nonlocal delayed, stdin_fd
        snapshot = original_query()
        if not delayed:
            delayed = True
            assert snapshot > 0
            assert stdin_fd is not None
            assert os.write(stdin_fd, b"x") == 1
            os.close(stdin_fd)
            stdin_fd = None
            assert process.wait(deadline - 0.5) == 0
            fresh = original_query()
            while fresh != 0 and time.monotonic() < deadline - 0.5:
                time.sleep(0.001)
                fresh = original_query()
            assert fresh == 0
            assert not process._job_terminated
            assert time.monotonic() < deadline - 0.25
        return snapshot

    try:
        with monkeypatch.context() as observation:
            observation.setattr(process, "_active_processes", delayed_native_snapshot)
            closure = process.settle(deadline)
        assert delayed
        assert closure.complete
        assert closure.direct_exit_code == 0
        assert closure.direct_reaped
        assert closure.active_zero
        assert closure.handles_closed
        assert not closure.issues
        assert not closure.job_terminated
    finally:
        if stdin_fd is not None:
            os.close(stdin_fd)
        process.close()


def test_direct_exit_still_reaps_job_descendant(tmp_path: Path) -> None:
    """Direct-process exit must never stand in for an empty Job."""
    job = importlib.import_module("scripts.process_supervision.windows_job")
    marker = tmp_path / "descendant.pid"
    code = (
        "import pathlib,subprocess,sys;"
        "child=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],"
        "stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);"
        "pathlib.Path(sys.argv[1]).write_text(str(child.pid),encoding='ascii')"
    )
    process = job.WindowsJobOwnerV1.launch(
        executable=sys.executable,
        argv=(sys.executable, "-c", code, str(marker)),
        cwd=str(tmp_path),
        environment=dict(os.environ),
    )
    fds = (
        process.take_stdin_fd(), process.take_stdout_fd(),
        process.take_stderr_fd(),
    )
    try:
        assert process.wait(time.monotonic() + 5.0) == 0
        assert marker.exists()
        closure = process.settle(time.monotonic() + 1.0)
        assert closure.complete
        assert closure.job_terminated
        assert closure.active_zero
    finally:
        for fd in fds:
            if fd is not None:
                os.close(fd)
        process.close()

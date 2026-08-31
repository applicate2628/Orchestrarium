from __future__ import annotations

import ctypes
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "src.codex" / "skills" / "manual-repo-transfer" / "scripts" / "repo_transfer.py"


def load_transfer_module():
    spec = importlib.util.spec_from_file_location("repo_transfer_posix_test", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _linux_process_state(pid: int) -> str | None:
    try:
        stat_line = Path(f"/proc/{pid}/stat").read_text(encoding="ascii")
    except FileNotFoundError:
        return None
    return stat_line.rsplit(")", 1)[1].lstrip().split(" ", 1)[0]


def _linux_child_subreaper_state() -> int:
    libc = ctypes.CDLL(None, use_errno=True)
    state = ctypes.c_int()
    if libc.prctl(37, ctypes.byref(state), 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "PR_GET_CHILD_SUBREAPER")
    return state.value


@unittest.skipUnless(os.name == "posix", "requires POSIX process groups")
class PosixRepoTransferTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.git = Path(shutil.which("git") or "").resolve()
        if not self.git.is_file():
            self.skipTest("Git executable is required")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_fake_git(self, body: str) -> Path:
        executable = self.root / "git"
        executable.write_text(f"#!{sys.executable}\n{body}", encoding="utf-8")
        executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
        return executable

    def test_inventory_runs_against_an_ordinary_posix_repository(self) -> None:
        repo = self.root / "repo"
        repo.mkdir()
        for arguments in (
            ("init", "--initial-branch=main"),
            ("config", "user.name", "Transfer Test"),
            ("config", "user.email", "transfer@example.invalid"),
        ):
            subprocess.run([str(self.git), *arguments], cwd=repo, check=True)
        (repo / "tracked.txt").write_text("committed\n", encoding="utf-8")
        subprocess.run([str(self.git), "add", "tracked.txt"], cwd=repo, check=True)
        subprocess.run([str(self.git), "commit", "-m", "initial"], cwd=repo, check=True)
        (repo / "untracked.txt").write_text("local work\n", encoding="utf-8")
        output = self.root / "inventory.json"

        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "inventory",
                "--repo",
                str(repo),
                "--git-executable",
                str(self.git),
                "--output",
                str(output),
            ],
            text=True,
            capture_output=True,
        )

        self.assertEqual(0, result.returncode, result.stderr)
        inventory = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual("committed", inventory["repository"]["historyState"])
        self.assertEqual(
            {"tracked.txt", "untracked.txt"},
            {entry["path"] for entry in inventory["entries"]},
        )

    def test_posix_owner_rejects_output_above_the_capture_limit(self) -> None:
        module = load_transfer_module()
        executable = self.write_fake_git(
            "import sys\nsys.stdout.buffer.write(b'x' * 33)\nsys.stdout.flush()\n"
        )

        with mock.patch.object(module, "MAX_JSON_BYTES", 32):
            with self.assertRaisesRegex(
                module.ContractError, r"^git output exceeds JSON limit$"
            ):
                module._run_posix_git_process([str(executable)], None, os.environ.copy())

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux subreaper")
    def test_posix_owner_restores_subreaper_after_launch_failure(self) -> None:
        module = load_transfer_module()
        initial_state = _linux_child_subreaper_state()

        with self.assertRaisesRegex(module.ContractError, r"^not a git repository$"):
            module._run_posix_git_process(
                [str(self.root / "missing-git")], None, os.environ.copy()
            )

        self.assertEqual(initial_state, _linux_child_subreaper_state())

    @unittest.skipUnless(sys.platform.startswith("linux"), "requires Linux subreaper")
    def test_posix_owner_reaps_each_adopted_timeout_descendant(self) -> None:
        """Each timed-out Git descendant must be gone, not merely a re-parented zombie."""

        libc = ctypes.CDLL(None, use_errno=True)
        prior_subreaper = ctypes.c_int()
        self.assertEqual(0, libc.prctl(37, ctypes.byref(prior_subreaper), 0, 0, 0))
        self.assertEqual(0, libc.prctl(36, 1, 0, 0, 0))
        module = load_transfer_module()
        readiness_marker: Path | None = None
        real_monotonic = time.monotonic

        def monotonic_after_fake_git_ready() -> float:
            if readiness_marker is not None:
                readiness_deadline = real_monotonic() + 5
                while not readiness_marker.is_file():
                    if real_monotonic() >= readiness_deadline:
                        raise AssertionError("fake Git did not signal readiness")
                    time.sleep(0.01)
            return real_monotonic()

        executable = self.write_fake_git(
            "import os, subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            "with open(sys.argv[1], 'w', encoding='ascii') as pid_file:\n"
            "    pid_file.write(f'{os.getpid()} {child.pid}')\n"
            "open(sys.argv[2], 'w', encoding='ascii').close()\n"
            "time.sleep(30)\n"
        )
        process_groups: list[int] = []
        states: list[str | None] = []
        try:
            with (
                mock.patch.object(module, "GIT_COMMAND_TIMEOUT_SECONDS", 0.1),
                mock.patch.object(module, "GIT_PROCESS_CLEANUP_SECONDS", 1),
                mock.patch.object(
                    module.time,
                    "monotonic",
                    side_effect=monotonic_after_fake_git_ready,
                ),
            ):
                for ordinal in range(3):
                    child_pid = self.root / f"child-{ordinal}.pid"
                    readiness_marker = self.root / f"child-{ordinal}.ready"
                    with self.assertRaisesRegex(module.ContractError, r"^git command timed out$"):
                        module._run_posix_git_process(
                            [str(executable), str(child_pid), str(readiness_marker)],
                            None,
                            os.environ.copy(),
                        )
                    group, pid = map(int, child_pid.read_text(encoding="ascii").split())
                    process_groups.append(group)
                    states.append(_linux_process_state(pid))
        finally:
            for process_group in process_groups:
                while True:
                    try:
                        reaped_pid, _status = os.waitpid(-process_group, os.WNOHANG)
                    except ChildProcessError:
                        break
                    if reaped_pid == 0:
                        break
            self.assertEqual(0, libc.prctl(36, prior_subreaper.value, 0, 0, 0))

        self.assertEqual([None, None, None], states)

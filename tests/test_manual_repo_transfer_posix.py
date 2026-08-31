from __future__ import annotations

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

    def test_posix_owner_times_out_and_reaps_its_descendant_group(self) -> None:
        module = load_transfer_module()
        child_pid = self.root / "child.pid"
        executable = self.write_fake_git(
            "import subprocess, sys, time\n"
            "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
            "open(sys.argv[1], 'w', encoding='ascii').write(str(child.pid))\n"
            "time.sleep(30)\n"
        )

        with (
            mock.patch.object(module, "GIT_COMMAND_TIMEOUT_SECONDS", 0.1),
            mock.patch.object(module, "GIT_PROCESS_CLEANUP_SECONDS", 1),
            self.assertRaisesRegex(module.ContractError, r"^git command timed out$"),
        ):
            module._run_posix_git_process(
                [str(executable), str(child_pid)], None, os.environ.copy()
            )

        pid = int(child_pid.read_text(encoding="ascii"))
        for _ in range(20):
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.05)
        else:
            self.fail("POSIX Git owner left its timed-out descendant running")

#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "baseline" / "verify_stage0.py"
SPEC = importlib.util.spec_from_file_location("verify_stage0", SCRIPT)
assert SPEC and SPEC.loader
VERIFIER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERIFIER
SPEC.loader.exec_module(VERIFIER)
REAL_GIT = Path(shutil.which("git") or "git").resolve()
REAL_BASH = Path(shutil.which("bash") or "bash").resolve()
TOOLS = VERIFIER.ExternalTools(Path(sys.executable).resolve(), REAL_GIT, REAL_BASH)


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


class VerifierIsolationTests(unittest.TestCase):
    def test_sanitized_environment_drops_ambient_startup_and_git_redirection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = VERIFIER.build_sanitized_env(
                tools=TOOLS,
                lane_root=Path(temp) / "lane",
            )
        for forbidden in ("PYTHONPATH", "PYTHONHOME", "GIT_DIR", "GIT_WORK_TREE", "VIRTUAL_ENV"):
            self.assertNotIn(forbidden, env)
        self.assertEqual(env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"], "1")
        self.assertEqual(env["PYTHONSAFEPATH"], "1")
        self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")

    @unittest.skipIf(os.name != "posix", "POSIX executable symlink contract")
    def test_external_executable_symlink_to_candidate_bytes_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidate"
            baseline = root / "baseline"
            candidate.mkdir(); baseline.mkdir()
            target = candidate / "python"
            target.write_text("#!/bin/sh\nexit 0\n")
            target.chmod(0o755)
            link = root / "outside-python"
            link.symlink_to(target)
            with self.assertRaises(VERIFIER.VerificationError):
                VERIFIER.resolve_external_executable(
                    link,
                    label="Python",
                    worktrees=(baseline.resolve(), candidate.resolve()),
                )

    @unittest.skipIf(os.name != "posix", "POSIX process-group contract")
    def test_process_group_is_reaped_after_parent_exits_zero(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pid_file = root / "child.pid"
            code = (
                "import pathlib,subprocess,sys; "
                "p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)']); "
                f"pathlib.Path({str(pid_file)!r}).write_text(str(p.pid))"
            )
            result = VERIFIER.run_isolated(
                [sys.executable, "-c", code],
                cwd=root,
                env={**os.environ},
                log_path=root / "run.log",
                timeout_seconds=10,
            )
            self.assertEqual(result.exit_code, 0)
            child_pid = int(pid_file.read_text())
            terminated = False
            for _ in range(40):
                stat_path = Path(f"/proc/{child_pid}/stat")
                if not stat_path.exists():
                    terminated = True
                    break
                try:
                    state = stat_path.read_text().split()[2]
                except (OSError, IndexError):
                    terminated = True
                    break
                if state == "Z":
                    terminated = True
                    break
                time.sleep(0.05)
            self.assertTrue(terminated, f"background child {child_pid} survived")

    def test_missing_executable_maps_to_operational_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = VERIFIER.run_isolated(
                ["/definitely/missing/orche-command"],
                cwd=root,
                env={"PATH": "/usr/bin:/bin"},
                log_path=root / "missing.log",
                timeout_seconds=1,
            )
            self.assertEqual(result.exit_code, 127)
            self.assertIn("command executable not found", result.log_path.read_text())

    @unittest.skipIf(os.name != "posix", "symlink output contract")
    def test_symlinked_scratch_is_rejected_without_deleting_external_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidate"
            external = root / "external"
            candidate.mkdir(); external.mkdir()
            sentinel = external / "sentinel"
            sentinel.write_text("keep")
            (candidate / ".scratch").symlink_to(external, target_is_directory=True)
            with self.assertRaises(VERIFIER.VerificationError):
                VERIFIER.safe_create_output_directory(candidate, "a" * 40)
            self.assertEqual(sentinel.read_text(), "keep")

    def test_unique_output_directories_do_not_reuse_stale_reports(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            candidate = Path(temp) / "candidate"
            candidate.mkdir()
            first = VERIFIER.safe_create_output_directory(candidate, "a" * 40)
            second = VERIFIER.safe_create_output_directory(candidate, "a" * 40)
            self.assertNotEqual(first, second)
            self.assertTrue(first.is_dir() and second.is_dir())

    def test_clean_worktree_rejects_ignored_importable_bytecode_and_hidden_flags(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            for args in (("init", "-q"), ("config", "user.name", "Test"), ("config", "user.email", "t@example.invalid")):
                self.assertEqual(run(str(REAL_GIT), *args, cwd=repo).returncode, 0)
            (repo / ".gitignore").write_text("__pycache__/\n")
            module = repo / "module.py"
            module.write_text("VALUE = 1\n")
            self.assertEqual(run(str(REAL_GIT), "add", ".", cwd=repo).returncode, 0)
            self.assertEqual(run(str(REAL_GIT), "commit", "-qm", "base", cwd=repo).returncode, 0)
            ref = run(str(REAL_GIT), "rev-parse", "HEAD", cwd=repo).stdout.strip()
            with tempfile.TemporaryDirectory() as env_temp:
                env = VERIFIER.build_sanitized_env(tools=TOOLS, lane_root=Path(env_temp) / "lane")
                py_compile.compile(str(module), doraise=True)
                with self.assertRaisesRegex(VERIFIER.VerificationError, "bytecode"):
                    VERIFIER.assert_clean_worktree(
                        repo.resolve(), expected_ref=ref, tools=TOOLS, env=env
                    )
                shutil.rmtree(repo / "__pycache__")
                self.assertEqual(run(str(REAL_GIT), "update-index", "--assume-unchanged", "module.py", cwd=repo).returncode, 0)
                module.write_text("VALUE = 2\n")
                with self.assertRaisesRegex(VERIFIER.VerificationError, "index flags"):
                    VERIFIER.assert_clean_worktree(
                        repo.resolve(), expected_ref=ref, tools=TOOLS, env=env
                    )

    def test_candidate_lane_cannot_mutate_previously_accepted_trusted_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            trusted = Path(temp) / "trusted"
            report = trusted / "reports" / "accepted.json"
            current_log = trusted / "logs" / "current.log"
            report.parent.mkdir(parents=True)
            current_log.parent.mkdir(parents=True)
            report.write_text("accepted\n")
            current_log.write_text("new lane output\n")
            snapshot = VERIFIER._trusted_evidence_snapshot(
                trusted,
                exclude=(current_log,),
            )
            report.write_text("forged\n")
            with self.assertRaisesRegex(VERIFIER.VerificationError, "trusted evidence"):
                VERIFIER._verify_protected_digests(snapshot)

    def test_report_copy_excludes_tool_and_lane_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trusted = root / "trusted"
            output = root / "output"
            for relative in (
                "summary.json",
                "reviewed-dispositions.json",
                "evidence/baseline/inventory.json",
                "reports/result.json",
                "logs/run.log",
                "tools/0001-tool.py",
                "lanes/focused/home/state.txt",
                "trusted-environment/gitconfig",
            ):
                path = trusted / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(relative)
            output.mkdir()
            VERIFIER._copy_reports(trusted, output)
            for relative in (
                "summary.json",
                "reviewed-dispositions.json",
                "evidence/baseline/inventory.json",
                "reports/result.json",
                "logs/run.log",
            ):
                self.assertTrue((output / relative).is_file(), relative)
            for relative in (
                "tools/0001-tool.py",
                "lanes/focused/home/state.txt",
                "trusted-environment/gitconfig",
            ):
                self.assertFalse((output / relative).exists(), relative)


if __name__ == "__main__":
    unittest.main()

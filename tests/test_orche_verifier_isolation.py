#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import inspect
import json
import os
import py_compile
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
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


def revalidation_kwargs(callback=None):
    if (
        "revalidate_worktrees"
        not in inspect.signature(
            VERIFIER.run_parent_generated_pytest_lane
        ).parameters
    ):
        return {}
    return {
        "revalidate_worktrees": callback or (lambda: None),
    }


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def process_is_live(pid: int) -> bool:
    try:
        raw = Path(f"/proc/{pid}/stat").read_text()
        return raw.split()[2] != "Z"
    except (OSError, IndexError):
        return False


class VerifierIsolationTests(unittest.TestCase):
    def test_sanitized_environment_drops_ambient_startup_and_git_redirection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            env = VERIFIER.build_sanitized_env(
                tools=TOOLS,
                lane_root=Path(temp) / "lane",
            )
        for forbidden in (
            "PYTHONPATH",
            "PYTHONHOME",
            "GIT_DIR",
            "GIT_WORK_TREE",
            "VIRTUAL_ENV",
        ):
            self.assertNotIn(forbidden, env)
        self.assertEqual(env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"], "1")
        self.assertEqual(env["PYTHONSAFEPATH"], "1")
        self.assertEqual(env["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(env["GIT_NO_REPLACE_OBJECTS"], "1")
        self.assertEqual(env["GIT_OPTIONAL_LOCKS"], "0")

    def test_repository_environment_restores_only_the_reviewed_import_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            package = repo / "tests"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text("")
            (package / "marker.py").write_text("VALUE = 42\n")
            env = VERIFIER.build_repository_env(
                tools=TOOLS,
                lane_root=root / "lane",
                repo_root=repo,
            )
            self.assertEqual(env["PYTHONSAFEPATH"], "1")
            self.assertEqual(env["PYTHONPATH"], str(repo.resolve()))
            result = subprocess.run(
                [
                    str(TOOLS.python),
                    "-c",
                    "from tests.marker import VALUE; print(VALUE)",
                ],
                cwd=root,
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "42")

    def test_trusted_git_ignores_replacement_objects(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            for args in (
                ("init", "-q"),
                ("config", "user.name", "Test"),
                ("config", "user.email", "t@example.invalid"),
            ):
                self.assertEqual(run(str(REAL_GIT), *args, cwd=repo).returncode, 0)
            payload = repo / "payload.txt"
            payload.write_text("original\n")
            self.assertEqual(run(str(REAL_GIT), "add", ".", cwd=repo).returncode, 0)
            self.assertEqual(
                run(str(REAL_GIT), "commit", "-qm", "original", cwd=repo).returncode,
                0,
            )
            original = run(str(REAL_GIT), "rev-parse", "HEAD", cwd=repo).stdout.strip()
            payload.write_text("replacement\n")
            self.assertEqual(
                run(str(REAL_GIT), "commit", "-qam", "replacement", cwd=repo).returncode,
                0,
            )
            replacement = run(
                str(REAL_GIT), "rev-parse", "HEAD", cwd=repo
            ).stdout.strip()
            self.assertEqual(
                run(str(REAL_GIT), "replace", original, replacement, cwd=repo).returncode,
                0,
            )
            self.assertEqual(
                run(str(REAL_GIT), "show", f"{original}:payload.txt", cwd=repo).stdout,
                "replacement\n",
            )
            with tempfile.TemporaryDirectory() as env_temp:
                env = VERIFIER.build_sanitized_env(
                    tools=TOOLS, lane_root=Path(env_temp) / "lane"
                )
                trusted = VERIFIER._run_git(
                    TOOLS,
                    env,
                    repo,
                    "show",
                    f"{original}:payload.txt",
                )
        self.assertEqual(trusted, "original\n")

    def test_selected_executable_is_reverified_before_every_launch(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_git = root / "git"
            marker = root / "owned"
            fake_git.write_text(f"#!/bin/sh\nexec {REAL_GIT} \"$@\"\n")
            fake_git.chmod(0o755)
            tools = VERIFIER.ExternalTools(TOOLS.python, fake_git.resolve(), TOOLS.bash)
            repo = root / "repo"
            repo.mkdir()
            self.assertEqual(run(str(REAL_GIT), "init", "-q", cwd=repo).returncode, 0)
            env = VERIFIER.build_sanitized_env(tools=tools, lane_root=root / "lane")
            VERIFIER._run_git(tools, env, repo, "rev-parse", "--git-dir")
            fake_git.write_text(
                f"#!/bin/sh\necho owned > {marker}\nexec {REAL_GIT} \"$@\"\n"
            )
            fake_git.chmod(0o755)
            with self.assertRaisesRegex(
                VERIFIER.VerificationError, "changed after preflight"
            ):
                VERIFIER._run_git(tools, env, repo, "rev-parse", "--git-dir")
            self.assertFalse(marker.exists())

    def test_unsafe_local_git_configuration_is_rejected_even_when_overridden(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            for args in (
                ("init", "-q"),
                ("config", "user.name", "Test"),
                ("config", "user.email", "t@example.invalid"),
            ):
                self.assertEqual(run(str(REAL_GIT), *args, cwd=repo).returncode, 0)
            (repo / "tracked.txt").write_text("clean\n")
            self.assertEqual(run(str(REAL_GIT), "add", ".", cwd=repo).returncode, 0)
            self.assertEqual(run(str(REAL_GIT), "commit", "-qm", "base", cwd=repo).returncode, 0)
            self.assertEqual(
                run(str(REAL_GIT), "config", "include.path", str(root / "hostile.cfg"), cwd=repo).returncode,
                0,
            )
            ref = run(str(REAL_GIT), "rev-parse", "HEAD", cwd=repo).stdout.strip()
            with tempfile.TemporaryDirectory() as env_temp:
                env = VERIFIER.build_sanitized_env(
                    tools=TOOLS, lane_root=Path(env_temp) / "lane"
                )
                with self.assertRaisesRegex(VERIFIER.VerificationError, "unsafe repository-local"):
                    VERIFIER.assert_clean_worktree(
                        repo, expected_ref=ref, tools=TOOLS, env=env
                    )

    def test_local_core_worktree_cannot_redirect_physical_cleanliness(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            external = root / "external"
            repo.mkdir()
            external.mkdir()
            for args in (
                ("init", "-q"),
                ("config", "user.name", "Test"),
                ("config", "user.email", "t@example.invalid"),
            ):
                self.assertEqual(run(str(REAL_GIT), *args, cwd=repo).returncode, 0)
            tracked = repo / "tracked.txt"
            tracked.write_text("clean\n")
            self.assertEqual(run(str(REAL_GIT), "add", ".", cwd=repo).returncode, 0)
            self.assertEqual(run(str(REAL_GIT), "commit", "-qm", "base", cwd=repo).returncode, 0)
            shutil.copy2(tracked, external / tracked.name)
            self.assertEqual(
                run(str(REAL_GIT), "config", "core.worktree", str(external), cwd=repo).returncode,
                0,
            )
            tracked.write_text("dirty\n")
            ref = run(str(REAL_GIT), "rev-parse", "HEAD", cwd=repo).stdout.strip()
            with tempfile.TemporaryDirectory() as env_temp:
                env = VERIFIER.build_sanitized_env(
                    tools=TOOLS, lane_root=Path(env_temp) / "lane"
                )
                with self.assertRaisesRegex(VERIFIER.VerificationError, "unsafe repository-local|dirty worktree"):
                    VERIFIER.assert_clean_worktree(
                        repo, expected_ref=ref, tools=TOOLS, env=env
                    )

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process containment")
    def test_repository_lane_rechecks_all_selected_tools_after_child_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            fake_bash = root / "bash"
            fake_bash.write_text(f"#!/bin/sh\nexec {REAL_BASH} \"$@\"\n")
            fake_bash.chmod(0o755)
            tools = VERIFIER.ExternalTools(TOOLS.python, TOOLS.git, fake_bash.resolve())
            trusted = root / "trusted"
            trusted.mkdir()
            (trusted / "reports").mkdir()
            lane = root / "lane"
            env = VERIFIER.build_repository_env(tools=tools, lane_root=lane, repo_root=root)
            code = (
                "import pathlib; "
                f"p=pathlib.Path({str(fake_bash)!r}); "
                "p.write_text('#!/bin/sh\\nexit 0\\n'); p.chmod(0o755)"
            )
            with self.assertRaisesRegex(VERIFIER.VerificationError, "changed after preflight"):
                VERIFIER.run_repository_lane(
                    [str(tools.python), "-c", code],
                    cwd=root,
                    env=env,
                    log_path=trusted / "logs" / "lane.log",
                    timeout_seconds=10,
                    tools=tools,
                    trusted_root=trusted,
                )

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process containment")
    def test_descendant_that_calls_setsid_is_reaped_before_return(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            ready = root / "ready"
            child_pid_path = root / "child.pid"
            delayed_sentinel = root / "escaped-write"
            child = (
                "import os,pathlib,time; os.setsid(); "
                f"pathlib.Path({str(child_pid_path)!r}).write_text(str(os.getpid())); "
                f"pathlib.Path({str(ready)!r}).write_text('ready'); "
                "time.sleep(0.8); "
                f"pathlib.Path({str(delayed_sentinel)!r}).write_text('escaped'); "
                "time.sleep(30)"
            )
            parent = (
                "import pathlib,subprocess,sys,time; "
                f"subprocess.Popen([sys.executable,'-c',{child!r}]); "
                f"ready=pathlib.Path({str(ready)!r});\n"
                "while not ready.exists(): time.sleep(0.01)"
            )
            result = VERIFIER.run_isolated(
                [str(TOOLS.python), "-c", parent],
                cwd=root,
                env={**os.environ},
                log_path=root / "run.log",
                timeout_seconds=10,
                tools=TOOLS,
            )
            self.assertEqual(result.exit_code, 0)
            child_pid = int(child_pid_path.read_text())
            for _ in range(100):
                if not process_is_live(child_pid):
                    break
                time.sleep(0.03)
            self.assertFalse(process_is_live(child_pid), f"child {child_pid} survived")
            time.sleep(1.0)
            self.assertFalse(delayed_sentinel.exists())

    def test_external_tool_set_is_rejected_when_any_captured_identity_is_inside_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidate"
            baseline = root / "baseline"
            candidate.mkdir()
            baseline.mkdir()
            fake_python = candidate / "python"
            fake_python.write_text("#!/bin/sh\nexit 0\n")
            fake_python.chmod(0o755)
            tools = VERIFIER.ExternalTools(fake_python, REAL_GIT, REAL_BASH)
            with self.assertRaisesRegex(VERIFIER.VerificationError, "inside tested worktree"):
                tools.assert_outside((baseline.resolve(), candidate.resolve()))

    @unittest.skipIf(os.name != "posix", "POSIX executable symlink contract")
    def test_external_executable_symlink_to_candidate_bytes_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidate"
            baseline = root / "baseline"
            candidate.mkdir()
            baseline.mkdir()
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

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process containment")
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
                [str(TOOLS.python), "-c", code],
                cwd=root,
                env={**os.environ},
                log_path=root / "run.log",
                timeout_seconds=10,
                tools=TOOLS,
            )
            self.assertEqual(result.exit_code, 0)
            child_pid = int(pid_file.read_text())
            for _ in range(40):
                if not process_is_live(child_pid):
                    break
                time.sleep(0.05)
            self.assertFalse(process_is_live(child_pid), f"child {child_pid} survived")

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process containment")
    def test_missing_executable_maps_to_operational_exit(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            result = VERIFIER.run_isolated(
                ["/definitely/missing/orche-command"],
                cwd=root,
                env={"PATH": "/usr/bin:/bin"},
                log_path=root / "missing.log",
                timeout_seconds=1,
                tools=None,
            )
            self.assertEqual(result.exit_code, 127)
            self.assertIn("command executable not found", result.log_path.read_text())

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process containment")
    def test_lane_cannot_precreate_parent_owned_log_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            log_path = root / "run.log"
            external = root / "external"
            external.write_text("external")
            code = (
                "import pathlib; "
                f"pathlib.Path({str(log_path)!r}).symlink_to({str(external)!r})"
            )
            with self.assertRaisesRegex(
                VERIFIER.VerificationError, "cannot create fresh trusted file"
            ):
                VERIFIER.run_isolated(
                    [str(TOOLS.python), "-c", code],
                    cwd=root,
                    env={**os.environ},
                    log_path=log_path,
                    timeout_seconds=10,
                    tools=TOOLS,
                )
            self.assertEqual(external.read_text(), "external")
            self.assertTrue(log_path.is_symlink())

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process containment")
    def test_child_stdout_is_nonseekable_and_parent_captured(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            code = (
                "import os, stat\n"
                "print(f'stdout_fifo={stat.S_ISFIFO(os.fstat(1).st_mode)}', flush=True)\n"
                "try:\n"
                "    os.ftruncate(1, 0)\n"
                "except OSError as exc:\n"
                "    print(f'truncate_errno={exc.errno}', flush=True)\n"
                "else:\n"
                "    print('truncate_succeeded=True', flush=True)\n"
            )
            result = VERIFIER.run_isolated(
                [str(TOOLS.python), "-c", code],
                cwd=root,
                env={**os.environ},
                log_path=root / "captured.log",
                timeout_seconds=10,
                tools=TOOLS,
            )
            text = result.log_path.read_text(encoding="utf-8")
        self.assertEqual(result.exit_code, 0)
        self.assertIn("stdout_fifo=True", text)
        self.assertRegex(text, r"truncate_errno=\d+")
        self.assertNotIn("truncate_succeeded=True", text)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process containment")
    def test_detached_child_cannot_rewrite_parent_captured_pytest_outcome(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            log_path = root / "captured.log"
            code = (
                "import os\n"
                "print('SKIPPED [1] tests/test_skip.py:1: genuine retained skip', flush=True)\n"
                "print('===== 1 skipped in 0.01s =====', flush=True)\n"
                "try:\n"
                "    os.ftruncate(1, 0)\n"
                "except OSError:\n"
                "    pass\n"
                "print('PASSED tests/test_skip.py::test_real_skip', flush=True)\n"
                "print('===== 1 passed in 0.01s =====', flush=True)\n"
            )
            result = VERIFIER.run_isolated(
                [str(TOOLS.python), "-c", code],
                cwd=root,
                env={**os.environ},
                log_path=log_path,
                timeout_seconds=10,
                tools=TOOLS,
            )
            self.assertEqual(result.exit_code, 0)
            with self.assertRaisesRegex(
                VERIFIER.VerificationError,
                "exactly one terminal summary",
            ):
                VERIFIER._pytest_zero_exit_outcome_evidence(result.log_path)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux process containment")
    def test_parent_generated_pytest_lane_revalidates_after_each_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tests = repo / "tests"
            tests.mkdir(parents=True)
            support = repo / "support.txt"
            support.write_text("original\n", encoding="utf-8")
            second_ran = root / "second-ran"
            (tests / "test_00_mutate.py").write_text(
                "from pathlib import Path\n"
                "def test_mutate_support():\n"
                f"    Path({str(support)!r}).write_text('changed\\n')\n",
                encoding="utf-8",
            )
            (tests / "test_01_restore.py").write_text(
                "from pathlib import Path\n"
                "def test_restore_support():\n"
                f"    Path({str(support)!r}).write_text('original\\n')\n"
                f"    Path({str(second_ran)!r}).write_text('ran')\n",
                encoding="utf-8",
            )
            trusted = root / "trusted"
            for directory in (
                trusted,
                trusted / "logs",
                trusted / "evidence",
                root / "lanes",
            ):
                directory.mkdir(parents=True, exist_ok=True)
            checks = []

            def revalidate() -> None:
                checks.append(support.read_text(encoding="utf-8"))
                if checks[-1] != "original\n":
                    raise VERIFIER.VerificationBlocked(
                        "worktree changed between retained test files"
                    )

            with self.assertRaisesRegex(
                VERIFIER.VerificationBlocked,
                "worktree changed between retained test files",
            ):
                VERIFIER.run_parent_generated_pytest_lane(
                    repo_root=repo,
                    test_paths=(
                        "tests/test_00_mutate.py",
                        "tests/test_01_restore.py",
                    ),
                    lane_parent=root / "lanes",
                    log_dir=trusted / "logs",
                    junit_dir=trusted / "evidence",
                    suite_name="candidate",
                    timeout_seconds=30,
                    tools=TOOLS,
                    trusted_root=trusted,
                    **revalidation_kwargs(revalidate),
                )
            self.assertEqual(checks, ["changed\n"])
            self.assertFalse(second_ran.exists())

    @unittest.skipIf(os.name != "posix", "symlink output contract")
    def test_symlinked_scratch_is_rejected_without_deleting_external_sentinel(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidate = root / "candidate"
            external = root / "external"
            candidate.mkdir()
            external.mkdir()
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
            for args in (
                ("init", "-q"),
                ("config", "user.name", "Test"),
                ("config", "user.email", "t@example.invalid"),
            ):
                self.assertEqual(run(str(REAL_GIT), *args, cwd=repo).returncode, 0)
            (repo / ".gitignore").write_text("__pycache__/\n")
            module = repo / "module.py"
            module.write_text("VALUE = 1\n")
            self.assertEqual(run(str(REAL_GIT), "add", ".", cwd=repo).returncode, 0)
            self.assertEqual(
                run(str(REAL_GIT), "commit", "-qm", "base", cwd=repo).returncode,
                0,
            )
            ref = run(str(REAL_GIT), "rev-parse", "HEAD", cwd=repo).stdout.strip()
            with tempfile.TemporaryDirectory() as env_temp:
                env = VERIFIER.build_sanitized_env(
                    tools=TOOLS, lane_root=Path(env_temp) / "lane"
                )
                py_compile.compile(str(module), doraise=True)
                with self.assertRaisesRegex(VERIFIER.VerificationError, "bytecode"):
                    VERIFIER.assert_clean_worktree(
                        repo.resolve(), expected_ref=ref, tools=TOOLS, env=env
                    )
                shutil.rmtree(repo / "__pycache__")
                self.assertEqual(
                    run(
                        str(REAL_GIT),
                        "update-index",
                        "--assume-unchanged",
                        "module.py",
                        cwd=repo,
                    ).returncode,
                    0,
                )
                module.write_text("VALUE = 2\n")
                with self.assertRaisesRegex(VERIFIER.VerificationError, "index flags"):
                    VERIFIER.assert_clean_worktree(
                        repo.resolve(), expected_ref=ref, tools=TOOLS, env=env
                    )

    def test_trusted_snapshot_rejects_new_entries_symlinks_and_hardlinks(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            trusted = Path(temp) / "trusted"
            report = trusted / "reports" / "accepted.json"
            report.parent.mkdir(parents=True)
            report.write_text("accepted\n")
            snapshot = VERIFIER._trusted_evidence_snapshot(trusted)
            (trusted / "summary.json").symlink_to(report)
            with self.assertRaisesRegex(VERIFIER.VerificationError, "symlink"):
                VERIFIER._verify_protected_digests(snapshot)
            (trusted / "summary.json").unlink()
            snapshot = VERIFIER._trusted_evidence_snapshot(trusted)
            (trusted / "unexpected.json").write_text("new")
            with self.assertRaisesRegex(VERIFIER.VerificationError, "added"):
                VERIFIER._verify_protected_digests(snapshot)
            (trusted / "unexpected.json").unlink()
            os.link(report, trusted / "hardlink.json")
            with self.assertRaisesRegex(VERIFIER.VerificationError, "hard-linked"):
                VERIFIER._trusted_evidence_snapshot(trusted)

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
            with self.assertRaisesRegex(
                VERIFIER.VerificationError, "trusted-tree"
            ):
                VERIFIER._verify_protected_digests(snapshot)

    def test_verification_workspace_cleans_success_and_failure_by_default(self) -> None:
        success_paths: tuple[Path, Path]
        with VERIFIER.verification_workspace() as workspace:
            success_paths = (workspace.trusted_root, workspace.lane_root)
            self.assertTrue(all(path.is_dir() for path in success_paths))
        self.assertTrue(all(not path.exists() for path in success_paths))

        failure_paths: tuple[Path, Path] | None = None
        with self.assertRaisesRegex(RuntimeError, "boom"):
            with VERIFIER.verification_workspace() as workspace:
                failure_paths = (workspace.trusted_root, workspace.lane_root)
                raise RuntimeError("boom")
        assert failure_paths is not None
        self.assertTrue(all(not path.exists() for path in failure_paths))

    def test_verification_workspace_does_not_live_under_bootstrap_tmpdir(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            bootstrap = Path(temp) / "bootstrap"
            bootstrap.mkdir()
            previous = os.environ.get("TMPDIR")
            os.environ["TMPDIR"] = str(bootstrap)
            try:
                with VERIFIER.verification_workspace() as workspace:
                    self.assertFalse(workspace.trusted_root.is_relative_to(bootstrap))
                    self.assertFalse(workspace.lane_root.is_relative_to(bootstrap))
            finally:
                if previous is None:
                    os.environ.pop("TMPDIR", None)
                else:
                    os.environ["TMPDIR"] = previous

    def test_failed_workspace_is_preserved_only_when_explicitly_requested(self) -> None:
        paths: tuple[Path, Path] | None = None
        try:
            with self.assertRaisesRegex(RuntimeError, "boom"):
                with VERIFIER.verification_workspace(preserve_failed=True) as workspace:
                    paths = (workspace.trusted_root, workspace.lane_root)
                    raise RuntimeError("boom")
            assert paths is not None
            self.assertTrue(all(path.is_dir() for path in paths))
        finally:
            if paths is not None:
                for path in paths:
                    VERIFIER._remove_private_temp_root(path)

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
                "trusted-environment/gitconfig",
            ):
                self.assertFalse((output / relative).exists(), relative)

    def test_parent_generated_pytest_evidence_cannot_be_rewritten_by_candidate_hook(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            (repo / "tests").mkdir()
            sentinel = repo / "candidate-hook-ran"
            (repo / "conftest.py").write_text(
                "def pytest_sessionfinish(session, exitstatus):\n"
                f"    open({str(sentinel)!r}, 'w').write('ran')\n"
                "    session.exitstatus = 0\n"
                "    for arg in session.config.invocation_params.args:\n"
                "        if str(arg).startswith('--junitxml='):\n"
                "            open(str(arg).split('=', 1)[1], 'w').write('<testsuite tests=\"1\"><testcase name=\"forged\"/></testsuite>')\n",
                encoding="utf-8",
            )
            (repo / "tests" / "test_failure.py").write_text(
                "import sys\n"
                "def test_real_failure():\n"
                "    assert not any(str(arg).startswith('--junitxml') for arg in sys.argv)\n"
                "    assert False, 'real failure'\n",
                encoding="utf-8",
            )
            trusted = root / "trusted"
            logs = trusted / "logs"
            evidence = trusted / "evidence"
            lane_parent = root / "lanes"
            for directory in (trusted, logs, evidence, lane_parent):
                directory.mkdir()
            result = VERIFIER.run_parent_generated_pytest_lane(
                repo_root=repo,
                test_paths=("tests/test_failure.py",),
                lane_parent=lane_parent,
                log_dir=logs,
                junit_dir=evidence,
                suite_name="candidate",
                timeout_seconds=30,
                tools=TOOLS,
                trusted_root=trusted,
                **revalidation_kwargs(),
            )
            self.assertEqual(result.exit_code, 1)
            self.assertFalse(sentinel.exists())
            tree = ET.parse(result.junit_path)
            cases = list(tree.getroot().iter("testcase"))
            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0].get("file"), "tests/test_failure.py")
            failure = cases[0].find("failure")
            self.assertIsNotNone(failure)
            assert failure is not None
            self.assertIn("real failure", failure.text or "")
            self.assertNotIn("forged", result.junit_path.read_text(encoding="utf-8"))


    def test_zero_exit_outcome_parser_preserves_non_skip_counts_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "pytest.log"
            log.write_text(
                "================ short test summary info ================\n"
                "PASSED tests/test_demo.py::test_pass[a]\n"
                "PASSED tests/test_demo.py::test_pass[b]\n"
                "XFAIL tests/test_demo.py::test_expected_failure - known defect\n"
                "XPASS tests/test_demo.py::test_unexpected_pass - fixed defect\n"
                "===== 2 passed, 1 xfailed, 1 xpassed, 3 deselected in 0.02s =====\n",
                encoding="utf-8",
            )
            evidence = VERIFIER._pytest_zero_exit_outcome_evidence(log)

        self.assertEqual(
            evidence["counts"],
            {
                "passed": 2,
                "skipped": 0,
                "xfailed": 1,
                "xpassed": 1,
                "deselected": 3,
            },
        )
        self.assertEqual(
            evidence["diagnostics"]["passed"],
            [
                "PASSED tests/test_demo.py::test_pass[a]",
                "PASSED tests/test_demo.py::test_pass[b]",
            ],
        )
        self.assertEqual(
            evidence["diagnostics"]["xfailed"],
            [
                "XFAIL tests/test_demo.py::test_expected_failure - known defect",
            ],
        )
        self.assertEqual(
            evidence["diagnostics"]["xpassed"],
            [
                "XPASS tests/test_demo.py::test_unexpected_pass - fixed defect",
            ],
        )
        self.assertEqual(
            evidence["diagnostics"]["deselected"],
            ["3 deselected"],
        )

    def test_parent_generated_pytest_evidence_preserves_non_skip_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline_repo = root / "baseline"
            candidate_repo = root / "candidate"
            test_source = (
                "from pathlib import Path\n"
                "import pytest\n"
                "\n"
                "state = (Path(__file__).parents[1] / 'runtime-state.txt').read_text().strip()\n"
                "parameters = (1, 2) if state == 'wide' else (1,)\n"
                "\n"
                "@pytest.mark.parametrize('value', parameters)\n"
                "def test_parameter(value):\n"
                "    assert value > 0\n"
                "\n"
                "@pytest.mark.xfail(reason='known defect')\n"
                "def test_expected_failure():\n"
                "    assert False\n"
                "\n"
                "@pytest.mark.xfail(reason='fixed defect')\n"
                "def test_unexpected_pass():\n"
                "    assert True\n"
            )
            for repo, state in ((baseline_repo, "wide"), (candidate_repo, "narrow")):
                (repo / "tests").mkdir(parents=True)
                (repo / "tests" / "test_outcomes.py").write_text(
                    test_source, encoding="utf-8"
                )
                (repo / "runtime-state.txt").write_text(state, encoding="utf-8")

            trusted = root / "trusted"
            baseline_evidence = trusted / "baseline-evidence"
            candidate_evidence = trusted / "candidate-evidence"
            baseline_lanes = root / "baseline-lanes"
            candidate_lanes = root / "candidate-lanes"
            for directory in (
                trusted,
                baseline_evidence,
                candidate_evidence,
                baseline_lanes,
                candidate_lanes,
            ):
                directory.mkdir(parents=True, exist_ok=True)

            baseline_result = VERIFIER.run_parent_generated_pytest_lane(
                repo_root=baseline_repo,
                test_paths=("tests/test_outcomes.py",),
                lane_parent=baseline_lanes,
                log_dir=trusted / "logs" / "baseline",
                junit_dir=baseline_evidence,
                suite_name="baseline",
                timeout_seconds=30,
                tools=TOOLS,
                trusted_root=trusted,
                **revalidation_kwargs(),
            )
            candidate_result = VERIFIER.run_parent_generated_pytest_lane(
                repo_root=candidate_repo,
                test_paths=("tests/test_outcomes.py",),
                lane_parent=candidate_lanes,
                log_dir=trusted / "logs" / "candidate",
                junit_dir=candidate_evidence,
                suite_name="candidate",
                timeout_seconds=30,
                tools=TOOLS,
                trusted_root=trusted,
                **revalidation_kwargs(),
            )

            def read_outcomes(path: Path) -> dict[str, object]:
                case = next(ET.parse(path).getroot().iter("testcase"))
                properties = case.find("properties")
                self.assertIsNotNone(properties)
                assert properties is not None
                values = [
                    item.get("value")
                    for item in properties.findall("property")
                    if item.get("name") == "orche.pytest.outcomes.v1"
                ]
                self.assertEqual(len(values), 1)
                assert values[0] is not None
                return json.loads(values[0])

            baseline_outcomes = read_outcomes(baseline_result.junit_path)
            candidate_outcomes = read_outcomes(candidate_result.junit_path)

        self.assertEqual(baseline_result.exit_code, 0)
        self.assertEqual(candidate_result.exit_code, 0)
        self.assertEqual(
            baseline_outcomes["counts"],
            {
                "passed": 2,
                "skipped": 0,
                "xfailed": 1,
                "xpassed": 1,
                "deselected": 0,
            },
        )
        self.assertEqual(
            candidate_outcomes["counts"],
            {
                "passed": 1,
                "skipped": 0,
                "xfailed": 1,
                "xpassed": 1,
                "deselected": 0,
            },
        )
        self.assertEqual(len(baseline_outcomes["diagnostics"]["passed"]), 2)
        self.assertEqual(len(candidate_outcomes["diagnostics"]["passed"]), 1)
        self.assertEqual(len(baseline_outcomes["diagnostics"]["xfailed"]), 1)
        self.assertEqual(len(baseline_outcomes["diagnostics"]["xpassed"]), 1)

    def test_parent_generated_pytest_evidence_preserves_candidate_only_skip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline_repo = root / "baseline"
            candidate_repo = root / "candidate"
            test_source = (
                "from pathlib import Path\n"
                "import pytest\n"
                "\n"
                "def test_runtime_state():\n"
                "    state = (Path(__file__).parents[1] / 'runtime-state.txt').read_text().strip()\n"
                "    if state == 'skip':\n"
                "        pytest.skip('candidate-only runtime skip')\n"
                "    assert state == 'run'\n"
            )
            for repo, state in ((baseline_repo, "run"), (candidate_repo, "skip")):
                (repo / "tests").mkdir(parents=True)
                (repo / "tests" / "test_runtime_state.py").write_text(
                    test_source, encoding="utf-8"
                )
                (repo / "runtime-state.txt").write_text(state, encoding="utf-8")

            trusted = root / "trusted"
            logs = trusted / "logs"
            baseline_evidence = trusted / "baseline-evidence"
            candidate_evidence = trusted / "candidate-evidence"
            baseline_lanes = root / "baseline-lanes"
            candidate_lanes = root / "candidate-lanes"
            for directory in (
                trusted,
                logs,
                baseline_evidence,
                candidate_evidence,
                baseline_lanes,
                candidate_lanes,
            ):
                directory.mkdir(parents=True, exist_ok=True)

            baseline_result = VERIFIER.run_parent_generated_pytest_lane(
                repo_root=baseline_repo,
                test_paths=("tests/test_runtime_state.py",),
                lane_parent=baseline_lanes,
                log_dir=logs / "baseline",
                junit_dir=baseline_evidence,
                suite_name="baseline",
                timeout_seconds=30,
                tools=TOOLS,
                trusted_root=trusted,
                **revalidation_kwargs(),
            )
            candidate_result = VERIFIER.run_parent_generated_pytest_lane(
                repo_root=candidate_repo,
                test_paths=("tests/test_runtime_state.py",),
                lane_parent=candidate_lanes,
                log_dir=logs / "candidate",
                junit_dir=candidate_evidence,
                suite_name="candidate",
                timeout_seconds=30,
                tools=TOOLS,
                trusted_root=trusted,
                **revalidation_kwargs(),
            )

            self.assertEqual(baseline_result.exit_code, 0)
            self.assertEqual(candidate_result.exit_code, 0)
            baseline_suite = ET.parse(baseline_result.junit_path).getroot()
            candidate_suite = ET.parse(candidate_result.junit_path).getroot()
            self.assertEqual(baseline_suite.get("skipped"), "0")
            self.assertEqual(candidate_suite.get("skipped"), "1")
            baseline_case = next(baseline_suite.iter("testcase"))
            candidate_case = next(candidate_suite.iter("testcase"))
            self.assertIsNone(baseline_case.find("skipped"))
            candidate_skip = candidate_case.find("skipped")
            self.assertIsNotNone(candidate_skip)
            assert candidate_skip is not None
            self.assertIn("candidate-only runtime skip", candidate_skip.text or "")


if __name__ == "__main__":
    unittest.main()

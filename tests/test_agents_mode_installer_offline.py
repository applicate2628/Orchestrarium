"""Offline validator boundaries; no installer process or filesystem mutation."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "orche_installer_regression_under_test",
    ROOT / "scripts" / "validate-agents-mode-installers.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

class OfflineValidatorTests(unittest.TestCase):
    def test_environment_redirects_state_and_drops_secrets(self):
        hostile = {"PATH": "/toolchain", "SystemRoot": "C:/Windows",
                   "PYTHONPATH": "/hostile", "OPENAI_API_KEY": "example-secret",
                   "CODEX_HOME": "/live", "HTTP_PROXY": "proxy"}
        home = (ROOT / ".scratch" / "synthetic-home").resolve()
        with patch.dict(os.environ, hostile, clear=True), patch.object(Path, "mkdir"):
            env = MODULE.fixture_environment(home)
        self.assertEqual(env["PATH"], "/toolchain")
        for key in ("PYTHONPATH", "OPENAI_API_KEY", "HTTP_PROXY"):
            self.assertNotIn(key, env)
        for key in ("HOME", "USERPROFILE", "CODEX_HOME", "APPDATA",
                    "LOCALAPPDATA", "TMP", "TEMP", "TMPDIR",
                    "XDG_CONFIG_HOME", "CLAUDE_CONFIG_DIR"):
            self.assertTrue(Path(env[key]).is_relative_to(home))

    def test_old_python_refused_before_writes(self):
        with patch.object(MODULE.sys, "version_info", (3, 12)), patch.object(Path, "mkdir") as mkdir:
            with self.assertRaisesRegex(MODULE.InstallerRegressionError, "3.13"):
                MODULE.fixture_environment(ROOT / "synthetic-home")
        mkdir.assert_not_called()

    def test_both_launchers_bind_only_fixture(self):
        with patch.object(Path, "mkdir"), patch.object(Path, "is_file", return_value=True), \
             patch.object(Path, "is_symlink", return_value=False), \
             patch.object(MODULE.subprocess, "run", return_value=SimpleNamespace(returncode=0)) as run:
            MODULE.run_installer(ROOT, MODULE.INSTALLER_CASES[0], Path(".scratch/trash/project"))
            MODULE.run_python_codex_global_installer(ROOT, ROOT / ".scratch/trash/home")
        self.assertEqual(run.call_count, 2)
        for call in run.call_args_list:
            self.assertEqual(call.kwargs["env"]["CODEX_BIN"],
                             str(ROOT / "tests/fixtures/fake_codex_hooks_host.py"))
            self.assertTrue(Path(call.kwargs["env"]["HOME"]).is_relative_to(ROOT / ".scratch/trash"))

    def test_missing_or_linked_fixture_refused_before_launch(self):
        for exists, linked in ((False, False), (True, True)):
            with self.subTest(exists=exists, linked=linked), \
                 patch.object(Path, "is_file", return_value=exists), \
                 patch.object(Path, "is_symlink", return_value=linked), \
                 patch.object(MODULE.subprocess, "run") as run:
                with self.assertRaisesRegex(MODULE.InstallerRegressionError, "fixture"):
                    MODULE.run_python_codex_global_installer(ROOT, ROOT / "synthetic-home")
                run.assert_not_called()

    def test_launch_failure_preserves_diagnostic(self):
        with patch.object(Path, "mkdir"), patch.object(Path, "is_file", return_value=True), \
             patch.object(Path, "is_symlink", return_value=False), \
             patch.object(MODULE.subprocess, "run", return_value=SimpleNamespace(
                 returncode=1, stdout="output", stderr="original failure")):
            with self.assertRaisesRegex(MODULE.InstallerRegressionError, "original failure"):
                MODULE.run_python_codex_global_installer(ROOT, ROOT / "synthetic-home")

    def run_orchestration(self, fail_at=None):
        calls = []
        error = RuntimeError("original installer failure")
        def install(*args):
            calls.append(args)
            if len(calls) == fail_at:
                raise error
        with contextlib.ExitStack() as stack:
            for name in ("load_json", "seed_stale_overlay", "validate_overlay", "validate_codex_native_role_install"):
                stack.enter_context(patch.object(MODULE, name))
            stack.enter_context(patch.object(MODULE, "run_installer", side_effect=install))
            stack.enter_context(patch.object(MODULE, "run_python_codex_global_installer", side_effect=install))
            stack.enter_context(patch.object(Path, "mkdir"))
            stack.enter_context(patch.object(Path, "write_text"))
            stack.enter_context(patch.object(Path, "unlink", side_effect=AssertionError("unexpected cleanup")))
            stack.enter_context(patch.object(Path, "rmdir", side_effect=AssertionError("unexpected cleanup")))
            output = stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            if fail_at:
                with self.assertRaises(RuntimeError) as caught:
                    MODULE.run_regression(ROOT)
                self.assertIs(caught.exception, error)
            else:
                MODULE.run_regression(ROOT)
        self.assertIn("RETAINED FIXTURE:", output.getvalue())
        for call in calls:
            self.assertIn("trash", call[-1].parts)
        return calls

    def test_all_six_steps_retain_fixture(self):
        self.assertEqual(len(self.run_orchestration()), 6)

    def test_each_failure_preserves_original_error(self):
        for index in range(1, 7):
            with self.subTest(step=index):
                self.assertEqual(len(self.run_orchestration(index)), index)

    def test_success_label_limits_claim(self):
        with patch.object(sys, "argv", ["validator", "--root", str(ROOT)]), \
             patch.object(MODULE, "run_regression"), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(MODULE.main(), 0)
        self.assertIn("fixture host; not real host admission", output.getvalue())

if __name__ == "__main__":
    unittest.main()

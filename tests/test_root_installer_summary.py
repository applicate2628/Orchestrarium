"""Root-router messages with inert runners, never real provider installers."""
from __future__ import annotations
import argparse
import ast
import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]


class RootInstallerSummaryTests(unittest.TestCase):
    def invoke(self, choice="3", exits=(0, 0), argv=("--global",), summary_error=None):
        tree = ast.parse((ROOT / "install.py").read_bytes())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        runner = Mock(side_effect=exits)
        reader = Mock(side_effect=choice) if isinstance(choice, BaseException) else Mock(return_value=choice)
        scope = {"sys": sys, "argparse": argparse, "CLIENTS": {"codex": {"label": "Codex"}, "claude": {"label": "Claude Code"}}, "input": reader, "_run_production": runner}
        exec(compile(ast.Module(body=[next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_run_selected"), main], type_ignores=[]), "install.py", "exec"), scope)
        class CapturedOutput(io.StringIO):
            def write(self, text):
                if summary_error is not None and text.startswith("Installer summary:"):
                    raise summary_error
                return super().write(text)

        out, err = CapturedOutput(), CapturedOutput()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                args = list(argv)
                if choice in ("1", "2", "3"):
                    args = ["--clients", *({"1": ["codex"], "2": ["claude"], "3": ["codex", "claude"]}[choice]), *args]
                result = scope["main"](args)
            except BaseException as caught:
                result = caught
        return result, runner.call_args_list, out.getvalue(), err.getvalue()

    def test_both_complete_and_order_is_unchanged(self):
        result, calls, out, err = self.invoke()
        self.assertEqual(result, 0)
        self.assertEqual([c.args for c in calls], [("codex", ["--global"]), ("claude", ["--global"])])
        self.assertIn("Installer summary: codex: completed (exit 0); claude: completed (exit 0)", out)
        self.assertLess(out.index("Starting codex installer"), out.index("Starting claude installer"))
        self.assertEqual(err, "")

    def test_second_failure_reports_partial_without_retry_or_rollback(self):
        result, calls, out, err = self.invoke(exits=(0, 9))
        self.assertEqual(result, 9)
        self.assertEqual(len(calls), 2)
        self.assertIn("codex: completed (exit 0); claude: failed (exit 9)", err)
        self.assertIn("Earlier completed calls were not rolled back by this router.", err)
        self.assertIn("Review provider output and recovery state before retrying", err)
        self.assertNotIn("Installer summary:", out)

    def test_first_failure_keeps_next_provider_unstarted(self):
        result, calls, out, err = self.invoke(exits=(7,))
        self.assertEqual(result, 7)
        self.assertEqual(len(calls), 1)
        self.assertIn("codex: failed (exit 7); claude: not started", err)
        self.assertNotIn("Starting claude installer", out)
        self.assertNotIn("Earlier completed calls", err)

    def test_single_provider_and_dry_run_do_not_claim_installation(self):
        for choice, name in (("1", "codex"), ("2", "claude")):
            with self.subTest(provider=name):
                result, calls, out, err = self.invoke(choice=choice, exits=(0,), argv=("--dry-run",))
                self.assertEqual(result, 0)
                self.assertEqual(calls[0].args, (name, ["--dry-run"]))
                self.assertIn(f"Installer summary: {name}: completed (exit 0)", out)
                self.assertNotIn("installed", out.lower())
                self.assertEqual(err, "")

    def test_empty_interactive_selection_cancels(self):
        result, calls, out, err = self.invoke(choice="")
        self.assertEqual(result, 0)
        self.assertEqual(calls, [])
        self.assertIn("Cancelled before preview.", out)
        self.assertEqual(err, "")

    def test_arguments_are_forwarded_without_reinterpretation(self):
        argv = ("--target", "path with spaces/\u03b1", "--no-hypothesis-hook")
        result, calls, _, _ = self.invoke(argv=argv)
        self.assertEqual(result, 0)
        self.assertEqual([c.args[1] for c in calls], [list(argv), list(argv)])

    def test_invalid_and_missing_selection_never_launch(self):
        for choice in ("unknown", EOFError()):
            with self.subTest(choice=type(choice).__name__):
                result, calls, out, err = self.invoke(choice=choice, exits=())
                self.assertEqual(result, 1)
                self.assertEqual(calls, [])
                self.assertNotIn("Installer summary:", out + err)

    def test_interruption_retains_exception_and_unknown_outcome(self):
        error = KeyboardInterrupt()
        result, calls, out, err = self.invoke(exits=(0, error))
        self.assertIs(result, error)
        self.assertEqual(len(calls), 2)
        self.assertIn("claude: outcome unavailable", err)
        self.assertIn("codex: completed (exit 0)", err)
        self.assertIn("Earlier completed calls were not rolled back", err)
        self.assertNotIn("claude: failed", err)

    def test_launch_error_remains_unknown_not_safe_to_retry(self):
        error = OSError("synthetic launch error")
        result, calls, _, err = self.invoke(exits=(error,))
        self.assertIs(result, error)
        self.assertEqual(len(calls), 1)
        self.assertIn("codex: outcome unavailable; claude: not started", err)
        self.assertIn("before retrying", err)
        for primary in (OSError("synthetic launch error"), KeyboardInterrupt()):
            with self.subTest(primary=type(primary).__name__):
                result, _, _, _ = self.invoke(exits=(primary,), summary_error=BrokenPipeError("synthetic output failure"))
                self.assertIs(result, primary)
        for ambient in (False, True):
            for exits in ((0, 0), (7,)):
                with self.subTest(ambient_exception=ambient, exits=exits):
                    output_error = BrokenPipeError("synthetic output failure")
                    if ambient:
                        try:
                            raise ValueError("unrelated caller exception")
                        except ValueError:
                            result, _, _, _ = self.invoke(exits=exits, summary_error=output_error)
                    else:
                        result, _, _, _ = self.invoke(exits=exits, summary_error=output_error)
                    self.assertIs(result, output_error)

    def test_readme_surfaces_hold_before_first_install_command(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        install = text[text.index("## Installation"):]
        before_command = install[:install.index("bash install.sh --global")]
        self.assertIn("Linux, macOS and Windows Subsystem for Linux", before_command)
        self.assertIn("including " + chr(96) + "--dry-run" + chr(96), before_command)
        self.assertIn("INSTALL.md#temporary-posix-installation-hold", before_command)

    def test_native_entrypoint_with_inert_provider_scripts(self):
        for exits in ((0, 9), (0, 0)):
            with self.subTest(exits=exits), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                scripts = root / "scripts"
                scripts.mkdir()
                shutil.copyfile(ROOT / "install.py", root / "install.py")
                shutil.copyfile(ROOT / "scripts/python_installer_bootstrap.py", scripts / "python_installer_bootstrap.py")
                (scripts / "installation").mkdir()
                shutil.copyfile(ROOT / "scripts/installation/clients.py", scripts / "installation/clients.py")
                for name, code in zip(("codex", "claude"), exits):
                    (scripts / f"install-{name}.py").write_text(
                        "import json, sys\n"
                        f"print('INERT-{name}: ' + json.dumps(sys.argv[1:]))\n"
                        f"raise SystemExit({code})\n",
                        encoding="utf-8",
                    )
                result = subprocess.run(
                    [sys.executable, "-I", "-S", "-B", str(root / "install.py"), "--dry-run"],
                    input="3\n", text=True, capture_output=True, timeout=10, cwd=root,
                )
                self.assertEqual(result.returncode, exits[-1], result.stderr)
                for name in ("codex", "claude"):
                    self.assertEqual(result.stdout.count(f"INERT-{name}: "), 1)
                    self.assertIn(f'INERT-{name}: ["--dry-run"]', result.stdout)
                summary = result.stderr if exits[-1] else result.stdout
                self.assertIn("Installer summary: codex: completed (exit 0); claude:", summary)
                self.assertNotIn("installed", summary.lower())
                self.assertFalse((root / ".agents").exists())
                self.assertFalse((root / ".claude").exists())


if __name__ == "__main__":
    unittest.main()

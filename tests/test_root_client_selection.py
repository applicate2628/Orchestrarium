"""Client selection at the root: no model or host process is started."""
import ast
import argparse
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]

class RootClientSelectionTests(unittest.TestCase):
    def invoke(self, args, exits=(0, 0)):
        tree = ast.parse((ROOT / "install.py").read_bytes())
        main = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main")
        run = Mock(side_effect=exits)
        reader = Mock(side_effect=AssertionError("explicit selection must not prompt"))
        scope = {"sys": sys, "argparse": argparse, "CLIENTS": {"codex": {"label": "Codex"}, "claude": {"label": "Claude Code"}}, "input": reader, "_run_production": run}
        exec(compile(ast.Module(body=[main], type_ignores=[]), "install.py", "exec"), scope)
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            try:
                status = scope["main"](args)
            except SystemExit as exc:
                status = exc.code
        return status, run.call_args_list, out.getvalue(), err.getvalue()

    def test_explicit_selection_preserves_arguments_and_catalog_order(self):
        for names in (["codex"], ["claude"], ["claude", "codex", "claude"]):
            with self.subTest(names=names):
                rc, calls, _, _ = self.invoke(["--target", "relative project", "--clients", *names, "--dry-run", "--unrecognized"])
                self.assertEqual(rc, 0)
                self.assertEqual([c.args for c in calls], [(name, ["--target", "relative project", "--dry-run", "--unrecognized"]) for name in ("codex", "claude") if name in names])

    def test_list_is_read_only(self):
        rc, calls, out, _ = self.invoke(["--list-clients"])
        self.assertEqual((rc, calls), (0, []))
        self.assertEqual(out, "codex: Codex\nclaude: Claude Code\n")

    def test_invalid_or_mixed_list_options_fail_before_installer(self):
        for args in (["--clients"], ["--clients", "grok"], ["--list-clients", "--global"], ["--list-clients", "--clients", "codex"]):
            with self.subTest(args=args):
                rc, calls, _, _ = self.invoke(args)
                self.assertEqual((rc, calls), (2, []))

    def test_partial_completion_retains_existing_summary(self):
        rc, calls, _, err = self.invoke(["--clients", "codex", "claude"], exits=(0, 9))
        self.assertEqual(rc, 9)
        self.assertEqual(len(calls), 2)
        self.assertIn("Earlier completed calls were not rolled back", err)
        self.assertIn("claude: failed (exit 9)", err)

    def test_real_isolated_entry_without_stdin(self):
        for args in (["--list-clients"], ["--clients", "codex", "--help"], ["--clients", "claude", "--help"]):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, "-I", "-B", str(ROOT / "install.py"), *args], input="", capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertNotIn("What to install?", result.stdout)

if __name__ == "__main__":
    unittest.main()

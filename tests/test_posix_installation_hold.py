"""Check the early CLI hold in memory, without importing installer effects."""
from __future__ import annotations

import __future__
import argparse
import ast
import contextlib
import copy
import io
from pathlib import Path
from types import SimpleNamespace
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "scripts" / "production_installer.py"
HOLD = "E_POSIX_DISPOSAL_UNQUALIFIED"
CONTINUED = "reached_after_guard"


class PosixInstallationHoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SOURCE.read_bytes())
        cls.parser = next(node for node in cls.tree.body
                          if isinstance(node, ast.FunctionDef) and node.name == "_parser")
        cls.install = next(node for node in cls.tree.body
                           if isinstance(node, ast.FunctionDef) and node.name == "install")

    def invoke_prefix(self, host, provider, argv):
        # Compile only argument parsing and the immediately following statement.
        # No installer import, preflight, filesystem operation or dependency runs.
        prefix = copy.deepcopy(self.install)
        prefix.body = prefix.body[:2] + [ast.Return(value=ast.Constant(CONTINUED))]
        module = ast.fix_missing_locations(ast.Module(body=[self.parser, prefix], type_ignores=[]))
        output, error = io.StringIO(), io.StringIO()
        scope = {"__builtins__": {"print": print}, "argparse": argparse,
                 "os": SimpleNamespace(name=host), "sys": SimpleNamespace(stderr=error)}
        exec(compile(module, str(SOURCE), "exec",
                     flags=__future__.annotations.compiler_flag), scope)
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            result = scope["install"](provider, argv)
        return result, output.getvalue(), error.getvalue()

    def test_hold_immediately_follows_argument_parsing(self):
        self.assertEqual(ast.unparse(self.install.body[0]),
                         "args = _parser(provider).parse_args(argv)")
        guard = self.install.body[1]
        self.assertIsInstance(guard, ast.If)
        self.assertEqual(ast.unparse(guard.test), "os.name == 'posix'")
        self.assertEqual(len(guard.body), 2)
        self.assertIsInstance(guard.body[0], ast.Expr)
        self.assertIsInstance(guard.body[0].value, ast.Call)
        self.assertEqual(ast.unparse(guard.body[0].value.func), "print")
        self.assertIsInstance(guard.body[1], ast.Return)
        self.assertEqual(ast.literal_eval(guard.body[1].value), 1)
        self.assertEqual(guard.orelse, [])

    def test_posix_modes_stop_including_preview_and_force(self):
        options = ([], ["--global"], ["--dry-run"], ["--global", "--dry-run"],
                   ["--target", "/synthetic/project", "--allow-unsafe-target"],
                   ["--target", "/synthetic/project", "--allow-unsafe-target",
                    "--dry-run", "--force"], ["--global", "--force", "--no-hypothesis-hook"])
        for provider in ("codex", "claude"):
            for argv in options:
                with self.subTest(provider=provider, argv=argv):
                    result, output, error = self.invoke_prefix("posix", provider, argv)
                    self.assertEqual(result, 1)
                    self.assertEqual(output, "")
                    self.assertIn(HOLD, error)
                    self.assertIn("including --dry-run", error)
                    self.assertIn("race remains unresolved", error)

    def test_windows_continues_past_guard_without_running_installer(self):
        for provider in ("codex", "claude"):
            for argv in ([], ["--global"], ["--dry-run"], ["--force"]):
                with self.subTest(provider=provider, argv=argv):
                    result, output, error = self.invoke_prefix("nt", provider, argv)
                    self.assertEqual((result, output, error), (CONTINUED, "", ""))

    def test_help_still_exits_before_hold(self):
        for provider in ("codex", "claude"):
            with self.subTest(provider=provider):
                with self.assertRaises(SystemExit) as caught:
                    self.invoke_prefix("posix", provider, ["--help"])
                self.assertEqual(caught.exception.code, 0)

    def test_invalid_arguments_keep_parser_refusal(self):
        with self.assertRaises(SystemExit) as caught:
            self.invoke_prefix("posix", "codex", ["--unknown-option"])
        self.assertEqual(caught.exception.code, 2)


if __name__ == "__main__":
    unittest.main()

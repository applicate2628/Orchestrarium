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
HOLD = "E_INSTALLER_PLATFORM_UNSUPPORTED"
CONTINUED = "reached_after_guard"


class PosixInstallationHoldTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(SOURCE.read_bytes())
        cls.parser = next(node for node in cls.tree.body
                          if isinstance(node, ast.FunctionDef) and node.name == "_parser")
        cls.admission = next(node for node in cls.tree.body
                             if isinstance(node, ast.FunctionDef) and node.name == "_installer_platform_admitted")
        cls.install = next(node for node in cls.tree.body
                           if isinstance(node, ast.FunctionDef) and node.name == "install")

    def invoke_prefix(self, host, provider, argv):
        # Compile through the actual platform guard, including pure option checks.
        # No installer import, preflight, filesystem operation or dependency runs.
        prefix = copy.deepcopy(self.install)
        guard_index = self.platform_guard_index()
        prefix.body = prefix.body[:guard_index + 1]
        allowed_calls = {"get_client", "_parser", "_parser(provider).parse_args",
                         "os.environ.get", "any", "vars", "vars(args).items",
                         "print", "_installer_platform_admitted"}
        self.assertTrue({ast.unparse(node.func) for node in ast.walk(prefix)
                         if isinstance(node, ast.Call)} <= allowed_calls)
        prefix.body.append(ast.Return(value=ast.Constant(CONTINUED)))
        module = ast.fix_missing_locations(ast.Module(body=[self.parser, self.admission, prefix], type_ignores=[]))
        output, error = io.StringIO(), io.StringIO()
        scope = {"__builtins__": {"print": print, "any": any, "vars": vars},
                 "argparse": argparse, "Path": Path,
                 "os": SimpleNamespace(name=host, environ={}), "sys": SimpleNamespace(stderr=error),
                 "get_client": lambda provider: None}
        exec(compile(module, str(SOURCE), "exec",
                     flags=__future__.annotations.compiler_flag), scope)
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            result = scope["install"](provider, argv)
        return result, output.getvalue(), error.getvalue()

    def argument_parsing_index(self):
        matches = [index for index, node in enumerate(self.install.body)
                   if isinstance(node, ast.Assign)
                   and any(isinstance(target, ast.Name) and target.id == "args"
                           for target in node.targets)
                   and isinstance(node.value, ast.Call)
                   and isinstance(node.value.func, ast.Attribute)
                   and node.value.func.attr == "parse_args"]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def platform_guard_index(self):
        matches = [index for index, node in enumerate(self.install.body)
                   if isinstance(node, ast.If)
                   and ast.unparse(node.test) == "not _installer_platform_admitted()"]
        self.assertEqual(len(matches), 1)
        return matches[0]

    def test_hold_follows_parsing_before_target_and_staging_operations(self):
        parse_index = self.argument_parsing_index()
        self.assertEqual(ast.unparse(self.install.body[parse_index]),
                         "args = _parser(provider).parse_args(argv)")
        guard_index = self.platform_guard_index()
        self.assertLess(parse_index, guard_index)
        guard = self.install.body[guard_index]
        self.assertIsInstance(guard, ast.If)
        self.assertEqual(ast.unparse(guard.test), "not _installer_platform_admitted()")
        self.assertEqual(ast.unparse(self.admission.body[-1]), "return os.name in {'nt', 'posix'}")
        self.assertEqual(len(guard.body), 2)
        self.assertIsInstance(guard.body[0], ast.Expr)
        self.assertIsInstance(guard.body[0].value, ast.Call)
        self.assertEqual(ast.unparse(guard.body[0].value.func), "print")
        self.assertIsInstance(guard.body[1], ast.Return)
        self.assertEqual(ast.literal_eval(guard.body[1].value), 1)
        self.assertEqual(guard.orelse, [])

    def test_unknown_host_stops_including_preview_and_force(self):
        options = ([], ["--global"], ["--dry-run"], ["--global", "--dry-run"],
                   ["--target", "/synthetic/project", "--allow-unsafe-target"],
                   ["--target", "/synthetic/project", "--allow-unsafe-target",
                    "--dry-run", "--force"], ["--global", "--force", "--no-hypothesis-hook"])
        for provider in ("codex", "claude"):
            for argv in options:
                with self.subTest(provider=provider, argv=argv):
                    result, output, error = self.invoke_prefix("unknown", provider, argv)
                    self.assertEqual(result, 1)
                    self.assertEqual(output, "")
                    self.assertIn(HOLD, error)
                    self.assertIn("No target or staging operations", error)

    def test_supported_hosts_continue_without_running_installer(self):
        for provider in ("codex", "claude"):
            for argv in ([], ["--global"], ["--dry-run"], ["--force"]):
                with self.subTest(provider=provider, argv=argv):
                    for host in ("nt", "posix"):
                        result, output, error = self.invoke_prefix(host, provider, argv)
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

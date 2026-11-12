"""Root dispatch preserves project discovery and relative targets; no provider runs."""
import ast
import contextlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RootProjectContextTests(unittest.TestCase):
    def test_real_child_keeps_caller_context_and_arguments(self):
        tree = ast.parse((ROOT / "install.py").read_bytes())
        function = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
                        and n.name == "_run_production")
        with tempfile.TemporaryDirectory(prefix="orche-context-") as temporary:
            base = Path(temporary)
            source = base / "installer source"
            scripts = source / "scripts"
            scripts.mkdir(parents=True)
            caller = base / "user project"
            caller.mkdir()
            report = base / "result.json"
            body = (
                "import json,sys\nfrom pathlib import Path\n"
                f"Path({str(report)!r}).write_text(json.dumps({{"
                "'cwd': str(Path.cwd()), 'argv':sys.argv[1:],"
                "'target': str(Path(sys.argv[2]).resolve()) if len(sys.argv)>2 else None"
                "}))\n"
                "raise SystemExit(7)\n"
            )
            for provider in ("codex", "claude"):
                (scripts / ("install-" + provider + ".py")).write_text(body)
            scope = {"sys": sys, "subprocess": subprocess, "ROOT": source}
            exec(compile(ast.Module(body=[function], type_ignores=[]), "install.py", "exec"), scope)
            old = Path.cwd()
            try:
                os.chdir(caller)
                for provider in ("codex", "claude"):
                    for arguments in ([], ["--target", "nested project/alpha"], ["--target", str(base / "absolute project")]):
                        with self.subTest(provider=provider, arguments=arguments):
                            self.assertEqual(scope["_run_production"](provider, arguments), 7)
                            actual = json.loads(report.read_text())
                            self.assertEqual(Path(actual["cwd"]), caller)
                            self.assertEqual(actual["argv"], arguments)
                            if arguments:
                                self.assertEqual(Path(actual["target"]), Path(arguments[1]).resolve())
                            self.assertEqual(Path.cwd(), caller)
            finally:
                os.chdir(old)


if __name__ == "__main__":
    unittest.main()

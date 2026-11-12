"""Client selection delegates to the existing installer without model calls."""
import argparse
import ast
import contextlib
import io
import os
import tempfile
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT/"scripts/install-client.py"

class ClientEntryTests(unittest.TestCase):
    def main(self, callback):
        tree = ast.parse(ENTRY.read_bytes())
        node = next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=="main")
        scope = {"argparse":argparse,"sys":sys,"CLIENTS":{"codex":{},"claude":{}},"install":callback}
        exec(compile(ast.Module(body=[node],type_ignores=[]),str(ENTRY),"exec"),scope)
        return scope["main"]

    def test_forwarding_and_exit_status(self):
        for client in ("codex","claude"):
            for forwarded in (["--help"],["--target","project with spaces","--allow-unsafe-target"],
                              ["--global","--dry-run"],["--unknown-option","literal"]):
                with self.subTest(client=client,argv=forwarded):
                    callback = Mock(return_value=7)
                    args = ["--client",client,*forwarded]
                    original = list(args)
                    self.assertEqual(self.main(callback)(args),7)
                    callback.assert_called_once_with(client,forwarded)
                    self.assertEqual(args,original)

    def test_invalid_or_missing_client_never_calls_installer(self):
        for args in ([],["--client","grok"],["--cl","codex"],["--client"]):
            with self.subTest(argv=args), contextlib.redirect_stderr(io.StringIO()):
                callback = Mock()
                with self.assertRaises(SystemExit) as caught:
                    self.main(callback)(args)
                self.assertEqual(caught.exception.code,2)
                callback.assert_not_called()

    def test_real_provider_help_without_install(self):
        for client in ("codex","claude"):
            with self.subTest(client=client):
                result = subprocess.run([sys.executable,"-I","-B",str(ENTRY),"--client",client,"--help"],
                                        capture_output=True,timeout=30)
                self.assertEqual(result.returncode,0,result.stderr)
                self.assertIn(b"--allow-unsafe-target",result.stdout)
                self.assertIn(b"--dry-run",result.stdout)

    def test_caller_modules_cannot_override_entry(self):
        with tempfile.TemporaryDirectory(prefix="client entry caller ") as directory:
            caller = Path(directory)
            for name in ("python_installer_bootstrap.py", "production_installer.py"):
                (caller/name).write_text("raise SystemExit(93)\n")
            env = os.environ.copy()
            env["PYTHONPATH"] = str(caller)
            result = subprocess.run([sys.executable,"-I","-B",str(ENTRY),"--client","codex","--help"],
                                    cwd=caller,env=env,capture_output=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertIn(b"--allow-unsafe-target",result.stdout)

if __name__ == "__main__":
    unittest.main()

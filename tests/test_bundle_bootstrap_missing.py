"""Native bootstrap fails closed without an ambient interpreter."""
import importlib.util
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

@unittest.skipUnless(os.name == "nt", "Windows native bootstrap")
class MissingRuntimeTests(unittest.TestCase):
    def test_missing_and_directory_runtime(self):
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location("builder", root/"scripts/distribution/build.py")
        builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(builder)
        shell = Path(os.environ["SystemRoot"])/"System32/WindowsPowerShell/v1.0/powershell.exe"
        with tempfile.TemporaryDirectory(prefix="orche bootstrap ") as name:
            bundle = Path(name)/"runtime 测试 with spaces"
            bundle.mkdir()
            script = bundle/"orche.ps1"
            script.write_text(builder.PS, encoding="utf-8")
            env = os.environ.copy()
            env.update(PATH="", PYTHONHOME=str(bundle/"invalid"), PYTHONPATH=str(bundle/"invalid"))
            for kind in ("missing", "directory"):
                if kind == "directory":
                    (bundle/"python/python.exe").mkdir(parents=True)
                with self.subTest(kind=kind):
                    p = subprocess.run([str(shell),"-NoProfile","-NonInteractive","-File",str(script),"--help"],
                                       env=env,capture_output=True,timeout=30)
                    self.assertEqual(p.returncode,2,p.stderr)
                    self.assertEqual(p.stdout,b"")
                    self.assertIn(b"E_BUNDLE_RUNTIME_MISSING",p.stderr)

if __name__ == "__main__":
    unittest.main()

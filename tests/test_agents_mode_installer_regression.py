import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class AgentsModeInstallerRegressionTest(unittest.TestCase):
    def test_installer_regression_validator_passes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["HOME"] = str(root)
        env["CODEX_BIN"] = str(
            root / "tests" / "fixtures" / "fake_codex_hooks_host.py"
        )
        with tempfile.TemporaryDirectory() as empty_path:
            env["PATH"] = empty_path
            result = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "validate-agents-mode-installers.py"),
                    "--root",
                    str(root),
                ],
                cwd=root,
                text=True,
                capture_output=True,
                env=env,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: agents-mode installer regression validated", result.stdout)


if __name__ == "__main__":
    unittest.main()

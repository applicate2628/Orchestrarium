import subprocess
import sys
import unittest
from pathlib import Path


class AgentsModeInstallerRegressionTest(unittest.TestCase):
    def test_installer_regression_validator_passes(self) -> None:
        root = Path(__file__).resolve().parents[1]
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
        )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: agents-mode installer regression validated", result.stdout)


if __name__ == "__main__":
    unittest.main()

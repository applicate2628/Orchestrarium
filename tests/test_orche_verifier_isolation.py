#!/usr/bin/env python3
"""Regression tests for the canonical Stage 0 verifier isolation contract."""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "baseline" / "orchestrarium-v1" / "README.md"


class VerifierIsolationTests(unittest.TestCase):
    def test_pytest_entry_point_plugins_are_disabled_in_isolated_environment(self) -> None:
        text = README.read_text(encoding="utf-8")
        env_contract = (
            "PYTHONDONTWRITEBYTECODE=1 PYTHONUTF8=1 "
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 CI=1"
        )
        self.assertIn(env_contract, text)
        self.assertLess(
            text.index("PYTEST_DISABLE_PLUGIN_AUTOLOAD=1"),
            text.index("run_isolated pytest-baseline"),
        )
        prose = " ".join(text.split())
        self.assertIn(
            "Any repository-required Pytest plugin must be loaded explicitly and pinned",
            prose,
        )

    @unittest.skipIf(os.name == "nt", "POSIX launcher exit contract")
    def test_timeout_runner_maps_missing_executable_to_operational_exit(self) -> None:
        text = README.read_text(encoding="utf-8")
        start_marker = "# BEGIN ORCHE_TIMEOUT_RUNNER"
        end_marker = "# END ORCHE_TIMEOUT_RUNNER"
        start = text.index(start_marker) + len(start_marker)
        end = text.index(end_marker, start)
        runner = text[start:end]
        result = subprocess.run(
            [sys.executable, "-c", runner, "10", "/definitely/missing/orche-command"],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(result.returncode, 127, result.stderr)
        self.assertIn("BLOCKED: command executable not found", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_validator_lanes_declare_semantic_failure_exit(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("--semantic-failure-exit 1", text)
        self.assertIn("undeclared exit codes always block", text)
        self.assertLess(
            text.index("--semantic-failure-exit 1"),
            text.index("compare_validator agents-spine"),
        )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Tests for the generic Stage 0 command differential gate."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "baseline" / "compare_command_baseline.py"


class CommandBaselineTests(unittest.TestCase):
    def invoke(
        self,
        *,
        baseline_exit: int,
        candidate_exit: int,
        baseline_log: str | bytes,
        candidate_log: str | bytes,
        baseline_root: str = "/tmp/baseline",
        candidate_root: str = "/tmp/candidate",
        extra_args: tuple[str, ...] = (),
        output_parent_is_file: bool = False,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline_path = root / "baseline.log"
            candidate_path = root / "candidate.log"
            if output_parent_is_file:
                blocker = root / "not-a-directory"
                blocker.write_text("blocked\n", encoding="utf-8")
                report_path = blocker / "report.json"
            else:
                report_path = root / "report.json"

            baseline_path.write_bytes(
                baseline_log
                if isinstance(baseline_log, bytes)
                else baseline_log.encode("utf-8")
            )
            candidate_path.write_bytes(
                candidate_log
                if isinstance(candidate_log, bytes)
                else candidate_log.encode("utf-8")
            )

            command = [
                sys.executable,
                str(SCRIPT),
                "--name",
                "agents-mode-installers",
                "--baseline-exit",
                str(baseline_exit),
                "--candidate-exit",
                str(candidate_exit),
                "--baseline-log",
                str(baseline_path),
                "--candidate-log",
                str(candidate_path),
                "--baseline-root",
                baseline_root,
                "--candidate-root",
                candidate_root,
                "--baseline-ref",
                "a" * 40,
                "--candidate-ref",
                "b" * 40,
                "--output",
                str(report_path),
                *extra_args,
            ]
            result = subprocess.run(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            report = (
                json.loads(report_path.read_text(encoding="utf-8"))
                if report_path.is_file()
                else {}
            )
            return result, report

    def test_two_successes_pass(self) -> None:
        result, report = self.invoke(
            baseline_exit=0,
            candidate_exit=0,
            baseline_log="RESULT: PASS\n",
            candidate_log="RESULT: PASS\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["classification"], "preserved-success")
        self.assertEqual(report["status"], "PASS")

    def test_new_candidate_failure_is_rejected(self) -> None:
        result, report = self.invoke(
            baseline_exit=0,
            candidate_exit=1,
            baseline_log="RESULT: PASS\n",
            candidate_log="ERROR: new failure\n",
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["classification"], "new-failure")
        self.assertEqual(report["status"], "FAIL")

    def test_identical_normalized_baseline_failure_is_characterized(self) -> None:
        result, report = self.invoke(
            baseline_exit=1,
            candidate_exit=1,
            baseline_log=(
                "/tmp/baseline/shared/agents-mode.schema.json: failure at "
                + "a" * 40
                + "\r\n"
            ),
            candidate_log=(
                "/tmp/candidate/shared/agents-mode.schema.json: failure at "
                + "b" * 40
                + "\n"
            ),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["classification"], "preserved-failure")
        self.assertEqual(
            report["baseline"]["normalizedSha256"],
            report["candidate"]["normalizedSha256"],
        )

    def test_resolved_baseline_failure_passes(self) -> None:
        result, report = self.invoke(
            baseline_exit=1,
            candidate_exit=0,
            baseline_log="ERROR: historical failure\n",
            candidate_log="RESULT: PASS\n",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["classification"], "resolved-failure")

    def test_changed_failure_is_rejected(self) -> None:
        result, report = self.invoke(
            baseline_exit=1,
            candidate_exit=1,
            baseline_log="ERROR: historical failure\n",
            candidate_log="ERROR: different failure\n",
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["classification"], "drifted-failure")
        self.assertNotEqual(
            report["baseline"]["normalizedSha256"],
            report["candidate"]["normalizedSha256"],
        )

    def test_exit_code_drift_is_rejected_even_with_same_log(self) -> None:
        result, report = self.invoke(
            baseline_exit=1,
            candidate_exit=2,
            baseline_log="ERROR: historical failure\n",
            candidate_log="ERROR: historical failure\n",
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["classification"], "drifted-failure")

    def test_distinct_invalid_utf8_diagnostics_are_not_collapsed(self) -> None:
        result, report = self.invoke(
            baseline_exit=1,
            candidate_exit=1,
            baseline_log=b"ERROR: invalid byte " + bytes([0xFF]) + b"\n",
            candidate_log=b"ERROR: invalid byte " + bytes([0xFE]) + b"\n",
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["classification"], "drifted-failure")
        self.assertNotEqual(
            report["baseline"]["normalizedSha256"],
            report["candidate"]["normalizedSha256"],
        )

    def test_declared_uuid_path_is_normalized(self) -> None:
        pattern = r"agents-mode-installer-regression[/\\][0-9a-f]{32}"
        result, report = self.invoke(
            baseline_exit=1,
            candidate_exit=1,
            baseline_log=(
                "/tmp/baseline/.scratch/agents-mode-installer-regression/"
                + "a" * 32
                + "/failure\n"
            ),
            candidate_log=(
                "/tmp/candidate/.scratch/agents-mode-installer-regression/"
                + "b" * 32
                + "/failure\n"
            ),
            extra_args=("--volatile-pattern", pattern),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["classification"], "preserved-failure")
        self.assertEqual(
            report["normalization"]["volatilePatterns"],
            [pattern],
        )

    def test_report_write_failure_uses_invalid_input_exit(self) -> None:
        result, report = self.invoke(
            baseline_exit=0,
            candidate_exit=0,
            baseline_log="RESULT: PASS\n",
            candidate_log="RESULT: PASS\n",
            output_parent_is_file=True,
        )
        self.assertEqual(report, {})
        self.assertEqual(result.returncode, 2)
        self.assertIn("COMMAND_BASELINE_INVALID", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()

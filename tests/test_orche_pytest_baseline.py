#!/usr/bin/env python3
"""Tests for differential pytest baseline comparison."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "baseline" / "compare_pytest_baseline.py"


def junit(cases: list[tuple[str, str, str]]) -> str:
    nodes = []
    for classname, name, status in cases:
        child = ""
        if status == "failure":
            child = '<failure message="failed">trace</failure>'
        elif status == "error":
            child = '<error message="errored">trace</error>'
        elif status == "skipped":
            child = '<skipped message="skip" />'
        nodes.append(
            f'<testcase classname="{classname}" name="{name}" file="tests/test_x.py">'
            f"{child}</testcase>"
        )
    return f'<testsuites><testsuite tests="{len(cases)}">{"".join(nodes)}</testsuite></testsuites>'


class PytestBaselineComparatorTests(unittest.TestCase):
    def run_compare(
        self,
        baseline_cases: list[tuple[str, str, str]],
        candidate_cases: list[tuple[str, str, str]],
        *,
        baseline_exit: int = 0,
        candidate_exit: int = 0,
    ) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline.xml"
            candidate = root / "candidate.xml"
            output = root / "report.json"
            baseline.write_text(junit(baseline_cases), encoding="utf-8")
            candidate.write_text(junit(candidate_cases), encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPT),
                    "--baseline-junit",
                    str(baseline),
                    "--candidate-junit",
                    str(candidate),
                    "--baseline-exit",
                    str(baseline_exit),
                    "--candidate-exit",
                    str(candidate_exit),
                    "--baseline-ref",
                    "baseline",
                    "--candidate-ref",
                    "candidate",
                    "--output",
                    str(output),
                ],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            report = json.loads(output.read_text(encoding="utf-8"))
            return result, report

    def test_allows_known_failures_resolutions_and_additional_passing_tests(self) -> None:
        result, report = self.run_compare(
            [
                ("suite.Test", "test_pass", "passed"),
                ("suite.Test", "test_known", "failure"),
                ("suite.Test", "test_resolved", "error"),
            ],
            [
                ("suite.Test", "test_pass", "passed"),
                ("suite.Test", "test_known", "failure"),
                ("suite.Test", "test_resolved", "passed"),
                ("suite.Test", "test_new", "passed"),
            ],
            baseline_exit=1,
            candidate_exit=1,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["verdict"], "PASS")
        self.assertEqual(
            report["observations"]["resolvedBaselineFailures"],
            ["suite.Test::test_resolved"],
        )
        self.assertEqual(
            report["observations"]["additionalCandidateTests"],
            ["suite.Test::test_new"],
        )

    def test_blocks_new_failure(self) -> None:
        result, report = self.run_compare(
            [("suite.Test", "test_pass", "passed")],
            [("suite.Test", "test_pass", "failure")],
            candidate_exit=1,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertEqual(
            report["blockers"]["newFailures"],
            ["suite.Test::test_pass"],
        )

    def test_blocks_missing_test_and_failure_hidden_by_skip(self) -> None:
        result, report = self.run_compare(
            [
                ("suite.Test", "test_missing", "passed"),
                ("suite.Test", "test_known", "failure"),
            ],
            [("suite.Test", "test_known", "skipped")],
            baseline_exit=1,
            candidate_exit=0,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            report["blockers"]["missingBaselineTests"],
            ["suite.Test::test_missing"],
        )
        self.assertEqual(
            report["blockers"]["maskedBaselineFailures"],
            ["suite.Test::test_known"],
        )

    def test_blocks_new_nonzero_pytest_exit_even_when_junit_is_all_passing(self) -> None:
        result, report = self.run_compare(
            [("suite.Test", "test_pass", "passed")],
            [("suite.Test", "test_pass", "passed")],
            baseline_exit=0,
            candidate_exit=3,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertEqual(
            report["blockers"]["pytestExitCodeRegression"],
            [{"baselineExitCode": 0, "candidateExitCode": 3}],
        )

    def test_blocks_zero_candidate_exit_when_junit_still_contains_failure(self) -> None:
        result, report = self.run_compare(
            [("suite.Test", "test_known", "failure")],
            [("suite.Test", "test_known", "failure")],
            baseline_exit=1,
            candidate_exit=0,
        )
        self.assertEqual(result.returncode, 1)
        self.assertEqual(report["verdict"], "BLOCKED")
        self.assertEqual(
            report["blockers"]["candidateExitContradiction"],
            [{"candidateExitCode": 0, "junitFailureCount": 1}],
        )
        self.assertFalse(report["observations"]["resolvedPytestExitCode"])


if __name__ == "__main__":
    unittest.main()

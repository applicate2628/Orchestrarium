#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "baseline" / "compare_pytest_baseline.py"
BASELINE_ROOT = "/work/baseline"
CANDIDATE_ROOT = "/work/candidate"
BASELINE_REF = "a" * 40
CANDIDATE_REF = "b" * 40
UUID_PATTERN = r"agents-mode-installer-regression[/\\][0-9a-f]{32}"


def junit(cases):
    nodes = []
    for case in cases:
        cls, name, status, *diagnostic = case
        default_message = {
            "failure": "failed",
            "error": "errored",
            "skipped": "skip",
        }.get(status)
        message = diagnostic[0] if diagnostic else default_message
        details = (
            diagnostic[1]
            if len(diagnostic) > 1
            else ("trace" if status in {"failure", "error"} else "")
        )
        outcome_type = diagnostic[2] if len(diagnostic) > 2 else None
        if status in {"failure", "error", "skipped"}:
            attrs = []
            if message is not None:
                attrs.append(f'message="{escape(message, quote=True)}"')
            if outcome_type is not None:
                attrs.append(f'type="{escape(outcome_type, quote=True)}"')
            attr_text = f" {' '.join(attrs)}" if attrs else ""
            if details is None:
                child = f"<{status}{attr_text}/>"
            else:
                child = f"<{status}{attr_text}>{escape(details)}</{status}>"
        else:
            child = ""
        nodes.append(
            f'<testcase classname="{escape(cls, quote=True)}" '
            f'name="{escape(name, quote=True)}" file="tests/test_x.py">'
            f"{child}</testcase>"
        )
    return (
        f'<testsuites><testsuite tests="{len(cases)}">'
        f"{''.join(nodes)}</testsuite></testsuites>"
    )


class PytestBaselineComparatorTests(unittest.TestCase):
    def run_compare(
        self,
        baseline,
        candidate,
        *,
        baseline_exit=0,
        candidate_exit=0,
        baseline_root=BASELINE_ROOT,
        candidate_root=CANDIDATE_ROOT,
        baseline_ref=BASELINE_REF,
        candidate_ref=CANDIDATE_REF,
        volatile_patterns=(),
        output_as_directory=False,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline_path = root / "baseline.xml"
            candidate_path = root / "candidate.xml"
            output = root / "report.json"
            baseline_path.write_text(junit(baseline), encoding="utf-8")
            candidate_path.write_text(junit(candidate), encoding="utf-8")
            if output_as_directory:
                output.mkdir()
            command = [
                sys.executable,
                str(SCRIPT),
                "--baseline-junit",
                str(baseline_path),
                "--candidate-junit",
                str(candidate_path),
                "--baseline-exit",
                str(baseline_exit),
                "--candidate-exit",
                str(candidate_exit),
                "--baseline-ref",
                baseline_ref,
                "--candidate-ref",
                candidate_ref,
                "--baseline-root",
                baseline_root,
                "--candidate-root",
                candidate_root,
            ]
            for pattern in volatile_patterns:
                command.extend(["--volatile-pattern", pattern])
            command.extend(["--output", str(output)])
            result = subprocess.run(
                command,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            report = json.loads(output.read_text()) if output.is_file() else None
            return result, report

    def test_allows_known_failure_resolution_and_new_pass(self):
        result, report = self.run_compare(
            [("S", "p", "passed"), ("S", "k", "failure"), ("S", "r", "error")],
            [("S", "p", "passed"), ("S", "k", "failure"), ("S", "r", "passed"), ("S", "n", "passed")],
            baseline_exit=1,
            candidate_exit=1,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["verdict"], "PASS")

    def test_blocks_changed_message_and_trace(self):
        result, report = self.run_compare(
            [("S", "k", "failure", "assertion failed", "AssertionError: 1 != 2", "AssertionError")],
            [("S", "k", "failure", "database failed", "RuntimeError: unavailable", "RuntimeError")],
            baseline_exit=1,
            candidate_exit=1,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(report["blockers"]["changedKnownFailureDiagnostics"], ["S::k"])

    def test_blocks_changed_trace_with_same_message(self):
        result, report = self.run_compare(
            [("S", "k", "failure", "failed", "trace one", "AssertionError")],
            [("S", "k", "failure", "failed", "trace two", "AssertionError")],
            baseline_exit=1,
            candidate_exit=1,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(report["blockers"]["changedKnownFailureDiagnostics"], ["S::k"])

    def test_blocks_changed_junit_type(self):
        result, report = self.run_compare(
            [("S", "k", "failure", "failed", "trace", "AssertionError")],
            [("S", "k", "failure", "failed", "trace", "RuntimeError")],
            baseline_exit=1,
            candidate_exit=1,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(report["blockers"]["changedKnownFailureDiagnostics"], ["S::k"])

    def test_blocks_empty_failure_diagnostics(self):
        result, report = self.run_compare(
            [("S", "k", "failure", None, None, None)],
            [("S", "k", "failure", None, None, None)],
            baseline_exit=1,
            candidate_exit=1,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(report["blockers"]["missingBaselineFailureDiagnostics"], ["S::k"])
        self.assertEqual(report["blockers"]["missingCandidateFailureDiagnostics"], ["S::k"])

    def test_normalises_line_endings_and_trailing_whitespace_only(self):
        result, report = self.run_compare(
            [("S", "k", "failure", "failed  \r\n", "line one  \r\nline two\t\r\n\r\n", "AssertionError")],
            [("S", "k", "failure", "failed\n", "line one\nline two\n", "AssertionError")],
            baseline_exit=1,
            candidate_exit=1,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["blockers"]["changedKnownFailureDiagnostics"], [])

    def test_normalises_lane_roots_refs_and_declared_uuid(self):
        baseline_uuid = "1" * 32
        candidate_uuid = "2" * 32
        baseline_message = f"failed at {BASELINE_ROOT}/tests/test_x.py on {BASELINE_REF}"
        candidate_message = f"failed at {CANDIDATE_ROOT}/tests/test_x.py on {CANDIDATE_REF}"
        baseline_trace = (
            f"tmp={BASELINE_ROOT}/.scratch/agents-mode-installer-regression/"
            f"{baseline_uuid}/case"
        )
        candidate_trace = (
            f"tmp={CANDIDATE_ROOT}/.scratch/agents-mode-installer-regression/"
            f"{candidate_uuid}/case"
        )
        result, report = self.run_compare(
            [("S", "k", "failure", baseline_message, baseline_trace, "AssertionError")],
            [("S", "k", "failure", candidate_message, candidate_trace, "AssertionError")],
            baseline_exit=1,
            candidate_exit=1,
            volatile_patterns=(UUID_PATTERN,),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["blockers"]["changedKnownFailureDiagnostics"], [])
        self.assertEqual(report["normalization"]["volatilePatterns"], [UUID_PATTERN])

    def test_does_not_normalise_undeclared_uuid(self):
        result, report = self.run_compare(
            [("S", "k", "failure", "failed", "agents-mode-installer-regression/" + "1" * 32, "AssertionError")],
            [("S", "k", "failure", "failed", "agents-mode-installer-regression/" + "2" * 32, "AssertionError")],
            baseline_exit=1,
            candidate_exit=1,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(report["blockers"]["changedKnownFailureDiagnostics"], ["S::k"])

    def test_does_not_erase_plain_ref_words(self):
        result, report = self.run_compare(
            [("S", "k", "failure", "baseline condition", "trace", "AssertionError")],
            [("S", "k", "failure", "candidate condition", "trace", "AssertionError")],
            baseline_exit=1,
            candidate_exit=1,
            baseline_ref="baseline",
            candidate_ref="candidate",
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(report["blockers"]["changedKnownFailureDiagnostics"], ["S::k"])

    def test_rejects_same_lane_root(self):
        result, report = self.run_compare(
            [("S", "p", "passed")],
            [("S", "p", "passed")],
            baseline_root="/same/root",
            candidate_root="/same/root/",
        )
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(report)
        self.assertIn("roots must be distinct", result.stderr)

    def test_rejects_invalid_volatile_pattern(self):
        result, report = self.run_compare(
            [("S", "p", "passed")],
            [("S", "p", "passed")],
            volatile_patterns=("[",),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIsNone(report)
        self.assertNotIn("Traceback", result.stderr)

    def test_blocks_new_failure(self):
        result, report = self.run_compare(
            [("S", "p", "passed")],
            [("S", "p", "failure")],
            candidate_exit=1,
        )
        self.assertEqual(result.returncode, 1)
        self.assertTrue(report["blockers"]["newFailures"])

    def test_blocks_operational_exits_even_with_junit_failures(self):
        for code in (2, 3, 4, 5):
            with self.subTest(code=code):
                result, report = self.run_compare(
                    [("S", "k", "failure")],
                    [("S", "k", "failure")],
                    baseline_exit=code,
                    candidate_exit=code,
                )
                self.assertEqual(result.returncode, 1)
                self.assertEqual(report["blockers"]["baselineExitContradiction"][0]["reason"], "operational-pytest-exit")
                self.assertEqual(report["blockers"]["candidateExitContradiction"][0]["reason"], "operational-pytest-exit")

    def test_blocks_nonzero_without_junit_failure(self):
        result, report = self.run_compare(
            [("S", "k", "failure")],
            [("S", "k", "passed")],
            baseline_exit=1,
            candidate_exit=1,
        )
        self.assertEqual(result.returncode, 1)
        self.assertTrue(report["blockers"]["candidateExitContradiction"])

    def test_blocks_zero_with_junit_failure(self):
        result, report = self.run_compare(
            [("S", "k", "failure")],
            [("S", "k", "failure")],
            baseline_exit=1,
            candidate_exit=0,
        )
        self.assertEqual(result.returncode, 1)
        self.assertTrue(report["blockers"]["candidateExitContradiction"])

    def test_blocks_failure_to_error(self):
        result, report = self.run_compare(
            [("S", "k", "failure")],
            [("S", "k", "error")],
            baseline_exit=1,
            candidate_exit=1,
        )
        self.assertEqual(result.returncode, 1)
        self.assertTrue(report["blockers"]["changedKnownFailureKind"])

    def test_report_write_failure_returns_two(self):
        result, report = self.run_compare(
            [("S", "p", "passed")],
            [("S", "p", "passed")],
            output_as_directory=True,
        )
        self.assertIsNone(report)
        self.assertEqual(result.returncode, 2)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()

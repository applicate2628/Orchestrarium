#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "baseline" / "compare_command_baseline.py"
A = "a" * 40
B = "b" * 40


class CommandComparatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.baseline = self.root / "baseline.log"
        self.candidate = self.root / "candidate.log"
        self.output = self.root / "report.json"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def invoke(
        self,
        *,
        baseline_exit: int = 0,
        candidate_exit: int = 0,
        baseline_ref: str = A,
        candidate_ref: str = B,
        success: str = r"(?m)^RESULT: PASS$",
        failure: str | None = r"(?m)^RESULT: FAIL$",
        volatile: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        args = [
            sys.executable,
            str(SCRIPT),
            "--name",
            "demo",
            "--baseline-exit",
            str(baseline_exit),
            "--candidate-exit",
            str(candidate_exit),
            "--baseline-log",
            str(self.baseline),
            "--candidate-log",
            str(self.candidate),
            "--baseline-root",
            "/work/lane-old",
            "--candidate-root",
            "/work/lane-new",
            "--baseline-ref",
            baseline_ref,
            "--candidate-ref",
            candidate_ref,
            "--success-pattern",
            success,
            "--semantic-failure-exit",
            "1",
            "--output",
            str(self.output),
        ]
        if failure is not None:
            args.extend(("--failure-pattern", failure))
        if volatile is not None:
            args.extend(("--volatile-pattern", volatile))
        return subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_preserved_success_compares_normalized_diagnostics(self) -> None:
        self.baseline.write_text(f"root=/work/lane-old ref={A}\nRESULT: PASS\n")
        self.candidate.write_text(f"root=/work/lane-new ref={B}\r\nRESULT: PASS\r\n")
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(self.output.read_text())["classification"], "preserved-success"
        )

    def test_semantic_exit_requires_terminal_failure_marker(self) -> None:
        self.baseline.write_text("Traceback: runtime failure\n")
        self.candidate.write_text("Traceback: runtime failure\n")
        result = self.invoke(baseline_exit=1, candidate_exit=1)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            json.loads(self.output.read_text())["classification"],
            "unverified-semantic-failure",
        )

    def test_verified_semantic_failure_may_be_preserved(self) -> None:
        self.baseline.write_text("diagnostic\nRESULT: FAIL\n")
        self.candidate.write_text("diagnostic\r\nRESULT: FAIL\r\n")
        result = self.invoke(baseline_exit=1, candidate_exit=1)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(self.output.read_text())["classification"], "preserved-failure"
        )

    def test_failure_marker_must_terminate_diagnostics(self) -> None:
        self.baseline.write_text("RESULT: FAIL\nafter\n")
        self.candidate.write_text("RESULT: FAIL\nafter\n")
        result = self.invoke(baseline_exit=1, candidate_exit=1)
        self.assertEqual(result.returncode, 1)

    def test_resolved_failure_requires_terminal_success_marker(self) -> None:
        self.baseline.write_text("RESULT: FAIL\n")
        self.candidate.write_text("RESULT: PASS\n")
        self.assertEqual(self.invoke(baseline_exit=1, candidate_exit=0).returncode, 0)
        self.candidate.write_text("RESULT: PASS\nwarning after\n")
        self.assertEqual(self.invoke(baseline_exit=1, candidate_exit=0).returncode, 1)

    def test_refs_must_be_exact_object_ids(self) -> None:
        self.baseline.write_text("RESULT: PASS\n")
        self.candidate.write_text("RESULT: PASS\n")
        result = self.invoke(baseline_ref="old", candidate_ref="new")
        self.assertEqual(result.returncode, 2)
        self.assertIn("exact 40- or 64-character", result.stderr)

    def test_path_and_ref_normalization_is_boundary_aware(self) -> None:
        self.baseline.write_text(f"/work/lane-old-backup {A}f\nRESULT: PASS\n")
        self.candidate.write_text(f"/work/lane-new-backup {B}f\nRESULT: PASS\n")
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            json.loads(self.output.read_text())["classification"], "drifted-success"
        )

    def test_declared_volatile_value_only_is_normalized(self) -> None:
        self.baseline.write_text("run=token-111\nRESULT: PASS\n")
        self.candidate.write_text("run=token-222\nRESULT: PASS\n")
        self.assertEqual(self.invoke(volatile=r"token-[0-9]+").returncode, 0)

    def test_operational_exit_uses_invalid_evidence_exit_two(self) -> None:
        self.baseline.write_text("same\n")
        self.candidate.write_text("same\n")
        result = self.invoke(baseline_exit=127, candidate_exit=127)
        self.assertEqual(result.returncode, 2)
        report = json.loads(self.output.read_text())
        self.assertEqual(report["classification"], "operational-exit")
        self.assertTrue(report["policy"]["operationalExitsUseInvalidEvidenceExitTwo"])


if __name__ == "__main__":
    unittest.main()

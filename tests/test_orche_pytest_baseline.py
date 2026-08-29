#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "baseline" / "compare_pytest_baseline.py"
A = "a" * 40
B = "b" * 40


def canonical(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def write_inventory(path: Path, ref: str, mapping: dict[str, str]) -> None:
    entries = [
        {
            "behavioralContractIds": [],
            "contentSha256": digest,
            "disposition": "retainedAs",
            "gitObject": "c" * 40,
            "kind": "test-file" if Path(name).name.startswith("test_") else "test-support",
            "path": name,
            "replacementTests": [],
            "reviewState": "baseline-captured",
            "sizeBytes": 1,
        }
        for name, digest in sorted(mapping.items())
    ]
    payload: dict[str, object] = {
        "schemaVersion": 2,
        "baseline": {"commitSha": ref, "repository": "x/y", "treeSha": "d" * 40},
        "entries": entries,
        "summary": {
            "retainedAs": len(entries),
            "testFiles": len(entries),
            "testSupportFiles": 0,
            "total": len(entries),
        },
    }
    payload["inventorySha256"] = hashlib.sha256(canonical(payload).encode()).hexdigest()
    path.write_text(canonical(payload))


def write_junit(path: Path, cases: list[dict[str, str | None]]) -> None:
    suite = ET.Element("testsuite")
    for case in cases:
        node = ET.SubElement(
            suite,
            "testcase",
            classname="demo",
            name=str(case["name"]),
            file=f"tests/{case['name']}.py",
        )
        status = case.get("status")
        if status in {"failure", "error", "skipped"}:
            child = ET.SubElement(node, str(status))
            if case.get("type") is not None:
                child.set("type", str(case["type"]))
            if case.get("message") is not None:
                child.set("message", str(case["message"]))
            child.text = case.get("details")
    ET.ElementTree(suite).write(path, encoding="unicode")


class PytestComparatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.baseline_junit = self.root / "baseline.xml"
        self.candidate_junit = self.root / "candidate.xml"
        self.baseline_inventory = self.root / "baseline-tests.json"
        self.candidate_inventory = self.root / "candidate-tests.json"
        self.output = self.root / "report.json"
        write_inventory(self.baseline_inventory, A, {"tests/test_existing.py": "1" * 64})
        write_inventory(self.candidate_inventory, B, {"tests/test_existing.py": "1" * 64})

    def tearDown(self) -> None:
        self.temp.cleanup()

    def invoke(
        self,
        *,
        baseline_exit: int = 0,
        candidate_exit: int = 0,
        baseline_ref: str = A,
        candidate_ref: str = B,
        baseline_root: str = "/work/base",
        candidate_root: str = "/work/candidate",
        baseline_lane: str = "/trusted/pytest-base",
        candidate_lane: str = "/trusted/pytest-candidate",
        volatile: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        args = [
            sys.executable,
            str(SCRIPT),
            "--baseline-junit",
            str(self.baseline_junit),
            "--candidate-junit",
            str(self.candidate_junit),
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
            "--baseline-lane-root",
            baseline_lane,
            "--candidate-lane-root",
            candidate_lane,
            "--baseline-test-inventory",
            str(self.baseline_inventory),
            "--candidate-test-inventory",
            str(self.candidate_inventory),
            "--output",
            str(self.output),
        ]
        if volatile:
            args.extend(("--volatile-pattern", volatile))
        return subprocess.run(
            args,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )

    def test_preserved_passing_tests_and_additional_candidate_tests_pass(self) -> None:
        cases = [{"name": "existing", "status": "passed"}]
        write_junit(self.baseline_junit, cases)
        write_junit(self.candidate_junit, cases + [{"name": "new", "status": "passed"}])
        write_inventory(
            self.candidate_inventory,
            B,
            {"tests/test_existing.py": "1" * 64, "tests/test_new.py": "2" * 64},
        )
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(self.output.read_text())
        self.assertEqual(report["observations"]["additionalCandidateTests"], ["demo::new"])
        self.assertEqual(
            report["observations"]["additionalCandidateTestFiles"],
            ["tests/test_new.py"],
        )

    def test_changed_or_missing_baseline_test_source_blocks(self) -> None:
        cases = [{"name": "existing", "status": "passed"}]
        write_junit(self.baseline_junit, cases)
        write_junit(self.candidate_junit, cases)
        write_inventory(self.candidate_inventory, B, {"tests/test_existing.py": "9" * 64})
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            json.loads(self.output.read_text())["blockers"]["changedBaselineTestFiles"],
            ["tests/test_existing.py"],
        )
        write_inventory(self.candidate_inventory, B, {})
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            json.loads(self.output.read_text())["blockers"]["missingBaselineTestFiles"],
            ["tests/test_existing.py"],
        )

    def test_retained_skip_reason_and_body_are_preserved(self) -> None:
        write_junit(
            self.baseline_junit,
            [
                {
                    "name": "existing",
                    "status": "skipped",
                    "type": "pytest.skip",
                    "message": "requires Windows",
                    "details": "reason\n",
                }
            ],
        )
        write_junit(
            self.candidate_junit,
            [
                {
                    "name": "existing",
                    "status": "skipped",
                    "type": "pytest.skip",
                    "message": "feature removed",
                    "details": "reason\n",
                }
            ],
        )
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            json.loads(self.output.read_text())["blockers"]["changedRetainedSkipDiagnostics"],
            ["demo::existing"],
        )

    def test_skip_line_endings_only_are_normalized(self) -> None:
        write_junit(
            self.baseline_junit,
            [
                {
                    "name": "existing",
                    "status": "skipped",
                    "type": "pytest.skip",
                    "message": "same",
                    "details": "one\r\ntwo\r\n",
                }
            ],
        )
        write_junit(
            self.candidate_junit,
            [
                {
                    "name": "existing",
                    "status": "skipped",
                    "type": "pytest.skip",
                    "message": "same",
                    "details": "one\ntwo\n",
                }
            ],
        )
        self.assertEqual(self.invoke().returncode, 0)

    def test_empty_skip_diagnostics_block(self) -> None:
        case = {
            "name": "existing",
            "status": "skipped",
            "type": None,
            "message": None,
            "details": None,
        }
        write_junit(self.baseline_junit, [case])
        write_junit(self.candidate_junit, [case])
        result = self.invoke()
        self.assertEqual(result.returncode, 1)
        blockers = json.loads(self.output.read_text())["blockers"]
        self.assertEqual(blockers["missingBaselineSkipDiagnostics"], ["demo::existing"])
        self.assertEqual(blockers["missingCandidateSkipDiagnostics"], ["demo::existing"])

    def test_worktree_and_isolated_lane_roots_are_normalized(self) -> None:
        write_junit(
            self.baseline_junit,
            [
                {
                    "name": "existing",
                    "status": "failure",
                    "type": "AssertionError",
                    "message": "/work/base /trusted/pytest-base/tmp " + A,
                    "details": "same",
                }
            ],
        )
        write_junit(
            self.candidate_junit,
            [
                {
                    "name": "existing",
                    "status": "failure",
                    "type": "AssertionError",
                    "message": "/work/candidate /trusted/pytest-candidate/tmp " + B,
                    "details": "same",
                }
            ],
        )
        self.assertEqual(self.invoke(baseline_exit=1, candidate_exit=1).returncode, 0)

    def test_sibling_prefixes_are_not_erased(self) -> None:
        write_junit(
            self.baseline_junit,
            [
                {
                    "name": "existing",
                    "status": "failure",
                    "type": "AssertionError",
                    "message": "/trusted/pytest-base-backup",
                    "details": "same",
                }
            ],
        )
        write_junit(
            self.candidate_junit,
            [
                {
                    "name": "existing",
                    "status": "failure",
                    "type": "AssertionError",
                    "message": "/trusted/pytest-candidate-backup",
                    "details": "same",
                }
            ],
        )
        result = self.invoke(baseline_exit=1, candidate_exit=1)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(
            json.loads(self.output.read_text())["blockers"]["changedKnownFailureDiagnostics"],
            ["demo::existing"],
        )

    def test_invalid_refs_and_operational_exits_are_invalid_evidence(self) -> None:
        cases = [{"name": "existing", "status": "passed"}]
        write_junit(self.baseline_junit, cases)
        write_junit(self.candidate_junit, cases)
        self.assertEqual(self.invoke(baseline_ref="old", candidate_ref="new").returncode, 2)
        result = self.invoke(baseline_exit=3, candidate_exit=3)
        self.assertEqual(result.returncode, 2)
        blockers = json.loads(self.output.read_text())["blockers"]
        self.assertTrue(blockers["baselineExitContradiction"])
        self.assertTrue(blockers["candidateExitContradiction"])

    def test_inventory_commit_binding_is_enforced(self) -> None:
        cases = [{"name": "existing", "status": "passed"}]
        write_junit(self.baseline_junit, cases)
        write_junit(self.candidate_junit, cases)
        write_inventory(self.candidate_inventory, A, {"tests/test_existing.py": "1" * 64})
        result = self.invoke()
        self.assertEqual(result.returncode, 2)
        self.assertIn("commit mismatch", result.stderr)


if __name__ == "__main__":
    unittest.main()

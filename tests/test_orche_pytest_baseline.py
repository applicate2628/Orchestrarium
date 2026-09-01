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
OUTCOME_PROPERTY = "orche.pytest.outcomes.v1"
OUTCOME_KEYS = ("passed", "skipped", "xfailed", "xpassed", "deselected")


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


def outcome_evidence(
    *,
    passed: int = 0,
    skipped: int = 0,
    xfailed: int = 0,
    xpassed: int = 0,
    deselected: int = 0,
    diagnostics: dict[str, list[str]] | None = None,
) -> dict[str, object]:
    counts = {
        "passed": passed,
        "skipped": skipped,
        "xfailed": xfailed,
        "xpassed": xpassed,
        "deselected": deselected,
    }
    details = {key: [] for key in OUTCOME_KEYS}
    if diagnostics:
        for key, lines in diagnostics.items():
            details[key] = list(lines)
    if passed and not details["passed"]:
        details["passed"] = [
            f"PASSED tests/generated.py::test_pass[{index}]"
            for index in range(passed)
        ]
    if skipped and not details["skipped"]:
        details["skipped"] = [
            f"SKIPPED [{skipped}] tests/generated.py: retained skip"
        ]
    if xfailed and not details["xfailed"]:
        details["xfailed"] = [
            f"XFAIL tests/generated.py::test_xfail[{index}] - expected"
            for index in range(xfailed)
        ]
    if xpassed and not details["xpassed"]:
        details["xpassed"] = [
            f"XPASS tests/generated.py::test_xpass[{index}] - unexpected"
            for index in range(xpassed)
        ]
    if deselected:
        details["deselected"] = [f"{deselected} deselected"]
    return {
        "schemaVersion": 1,
        "counts": counts,
        "diagnostics": details,
    }


def write_junit(path: Path, cases: list[dict[str, object]]) -> None:
    suite = ET.Element("testsuite")
    for case in cases:
        name = str(case["name"])
        node = ET.SubElement(
            suite,
            "testcase",
            classname="demo",
            name=name,
            file=f"tests/{name}.py",
        )
        status = case.get("status")
        outcomes = case.get("outcomes")
        if outcomes is None and status in {None, "passed", "skipped"}:
            if status == "skipped":
                reason = str(case.get("message") or "retained skip")
                outcomes = outcome_evidence(
                    skipped=1,
                    diagnostics={
                        "skipped": [
                            f"SKIPPED tests/{name}.py::{name} - {reason}"
                        ]
                    },
                )
            else:
                outcomes = outcome_evidence(
                    passed=1,
                    diagnostics={
                        "passed": [f"PASSED tests/{name}.py::{name}"]
                    },
                )
        if outcomes is not None:
            if not isinstance(outcomes, dict):
                raise AssertionError("outcomes must be an object")
            properties = ET.SubElement(node, "properties")
            ET.SubElement(
                properties,
                "property",
                name=OUTCOME_PROPERTY,
                value=json.dumps(
                    outcomes,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            )
        if status in {"failure", "error", "skipped"}:
            child = ET.SubElement(node, str(status))
            if case.get("type") is not None:
                child.set("type", str(case["type"]))
            if case.get("message") is not None:
                child.set("message", str(case["message"]))
            details = case.get("details")
            child.text = None if details is None else str(details)
    with path.open("w", encoding="utf-8", newline="") as stream:
        ET.ElementTree(suite).write(stream, encoding="unicode")


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

    def test_retained_zero_exit_outcome_fingerprint_changes_block(self) -> None:
        baseline_outcomes = outcome_evidence(
            passed=3,
            diagnostics={
                "passed": [
                    "PASSED tests/test_existing.py::test_existing[a]",
                    "PASSED tests/test_existing.py::test_existing[b]",
                    "PASSED tests/test_existing.py::test_existing[c]",
                ]
            },
        )
        candidate_outcomes = outcome_evidence(
            passed=1,
            xfailed=1,
            deselected=1,
            diagnostics={
                "passed": [
                    "PASSED tests/test_existing.py::test_existing[a]",
                ],
                "xfailed": [
                    "XFAIL tests/test_existing.py::test_existing[b] - expected failure",
                ],
            },
        )
        write_junit(
            self.baseline_junit,
            [
                {
                    "name": "existing",
                    "status": "passed",
                    "outcomes": baseline_outcomes,
                }
            ],
        )
        write_junit(
            self.candidate_junit,
            [
                {
                    "name": "existing",
                    "status": "passed",
                    "outcomes": candidate_outcomes,
                }
            ],
        )
        result = self.invoke()
        self.assertEqual(result.returncode, 1, result.stderr)
        report = json.loads(self.output.read_text())
        self.assertEqual(report["schemaVersion"], 4)
        self.assertEqual(
            report["blockers"]["changedRetainedOutcomeEvidence"],
            ["demo::existing"],
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
        self.assertIn(b"one\r\ntwo\r\n", self.baseline_junit.read_bytes())
        self.assertNotIn(b"\r\r\n", self.baseline_junit.read_bytes())
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

#!/usr/bin/env python3
"""Compare candidate pytest JUnit results against an immutable baseline run.

The comparator allows additional passing tests and resolved baseline failures,
but blocks:
- failures/errors not present in the baseline failure set;
- baseline tests that disappear from candidate collection;
- baseline failures hidden by a skip;
- baseline passing tests that regress to skipped/failure/error;
- a successful candidate process exit whose JUnit still contains failures/errors.

Output is deterministic JSON. Pure stdlib.
"""

from __future__ import annotations

import argparse
import json
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

SCHEMA_VERSION = 1
NONPASSING = {"failure", "error"}
SKIPPED = {"skipped"}


class ComparisonError(RuntimeError):
    """Stable user-facing comparator error."""


@dataclass(frozen=True)
class TestCaseResult:
    test_id: str
    status: str
    classname: str
    name: str
    file: str | None
    message: str | None


def _normalise_path(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("\\", "/")


def _test_id(element: ET.Element) -> str:
    classname = element.get("classname", "").strip()
    name = element.get("name", "").strip()
    file_name = _normalise_path(element.get("file"))
    if classname and name:
        return f"{classname}::{name}"
    if file_name and name:
        return f"{file_name}::{name}"
    if name:
        return name
    if file_name:
        return file_name
    raise ComparisonError("JUnit testcase is missing classname, name, and file")


def _status(element: ET.Element) -> tuple[str, str | None]:
    failure = element.find("failure")
    if failure is not None:
        return "failure", failure.get("message") or (failure.text or "").strip() or None
    error = element.find("error")
    if error is not None:
        return "error", error.get("message") or (error.text or "").strip() or None
    skipped = element.find("skipped")
    if skipped is not None:
        return "skipped", skipped.get("message") or (skipped.text or "").strip() or None
    return "passed", None


def parse_junit(path: Path) -> dict[str, TestCaseResult]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        raise ComparisonError(f"cannot parse JUnit file {path}: {exc}") from exc

    results: dict[str, TestCaseResult] = {}
    for element in root.iter("testcase"):
        test_id = _test_id(element)
        if test_id in results:
            raise ComparisonError(f"duplicate JUnit testcase ID in {path}: {test_id}")
        status, message = _status(element)
        results[test_id] = TestCaseResult(
            test_id=test_id,
            status=status,
            classname=element.get("classname", ""),
            name=element.get("name", ""),
            file=_normalise_path(element.get("file")),
            message=message,
        )
    if not results:
        raise ComparisonError(f"JUnit file contains no testcases: {path}")
    return results


def _record(result: TestCaseResult) -> dict[str, object]:
    return {
        "id": result.test_id,
        "status": result.status,
        "classname": result.classname,
        "name": result.name,
        "file": result.file,
        "message": result.message,
    }


def compare(
    baseline: dict[str, TestCaseResult],
    candidate: dict[str, TestCaseResult],
    *,
    baseline_exit: int,
    candidate_exit: int,
    baseline_ref: str,
    candidate_ref: str,
) -> dict[str, object]:
    if baseline_exit < 0 or candidate_exit < 0:
        raise ComparisonError("pytest exit codes must be non-negative")
    baseline_ids = set(baseline)
    candidate_ids = set(candidate)
    baseline_failures = {
        test_id for test_id, result in baseline.items() if result.status in NONPASSING
    }
    candidate_failures = {
        test_id for test_id, result in candidate.items() if result.status in NONPASSING
    }

    missing_baseline_tests = sorted(baseline_ids - candidate_ids)
    additional_candidate_tests = sorted(candidate_ids - baseline_ids)
    new_failures = sorted(candidate_failures - baseline_failures)
    resolved_failures = sorted(
        test_id
        for test_id in baseline_failures
        if test_id in candidate and candidate[test_id].status == "passed"
    )
    masked_failures = sorted(
        test_id
        for test_id in baseline_failures
        if test_id in candidate and candidate[test_id].status in SKIPPED
    )
    regressions = sorted(
        test_id
        for test_id in baseline_ids & candidate_ids
        if baseline[test_id].status == "passed"
        and candidate[test_id].status != "passed"
    )
    changed_known_failure_kind = sorted(
        test_id
        for test_id in baseline_failures & candidate_failures
        if baseline[test_id].status != candidate[test_id].status
    )

    pytest_exit_code_regression = (
        []
        if candidate_exit == 0 or candidate_exit == baseline_exit
        else [
            {
                "baselineExitCode": baseline_exit,
                "candidateExitCode": candidate_exit,
            }
        ]
    )
    candidate_exit_contradiction = (
        [
            {
                "candidateExitCode": candidate_exit,
                "junitFailureCount": len(candidate_failures),
            }
        ]
        if candidate_exit == 0 and candidate_failures
        else []
    )
    blockers = {
        "newFailures": new_failures,
        "missingBaselineTests": missing_baseline_tests,
        "maskedBaselineFailures": masked_failures,
        "passingTestRegressions": regressions,
        "pytestExitCodeRegression": pytest_exit_code_regression,
        "candidateExitContradiction": candidate_exit_contradiction,
    }
    verdict = "PASS" if all(not values for values in blockers.values()) else "BLOCKED"

    return {
        "schemaVersion": SCHEMA_VERSION,
        "baseline": {
            "exitCode": baseline_exit,
            "ref": baseline_ref,
            "total": len(baseline),
            "passed": sum(result.status == "passed" for result in baseline.values()),
            "skipped": sum(result.status == "skipped" for result in baseline.values()),
            "failures": len(baseline_failures),
        },
        "candidate": {
            "exitCode": candidate_exit,
            "ref": candidate_ref,
            "total": len(candidate),
            "passed": sum(result.status == "passed" for result in candidate.values()),
            "skipped": sum(result.status == "skipped" for result in candidate.values()),
            "failures": len(candidate_failures),
        },
        "blockers": blockers,
        "observations": {
            "additionalCandidateTests": additional_candidate_tests,
            "resolvedBaselineFailures": resolved_failures,
            "unchangedBaselineFailures": sorted(baseline_failures & candidate_failures),
            "changedKnownFailureKind": changed_known_failure_kind,
            "resolvedPytestExitCode": (
                baseline_exit != 0
                and candidate_exit == 0
                and not candidate_failures
            ),
        },
        "baselineFailureDetails": [
            _record(baseline[test_id]) for test_id in sorted(baseline_failures)
        ],
        "candidateFailureDetails": [
            _record(candidate[test_id]) for test_id in sorted(candidate_failures)
        ],
        "verdict": verdict,
    }


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-junit", type=Path, required=True)
    parser.add_argument("--candidate-junit", type=Path, required=True)
    parser.add_argument("--baseline-exit", type=int, required=True)
    parser.add_argument("--candidate-exit", type=int, required=True)
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--candidate-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        report = compare(
            parse_junit(args.baseline_junit),
            parse_junit(args.candidate_junit),
            baseline_exit=args.baseline_exit,
            candidate_exit=args.candidate_exit,
            baseline_ref=args.baseline_ref,
            candidate_ref=args.candidate_ref,
        )
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(_canonical_json(report), encoding="utf-8")
        print(
            "RESULT: "
            f"{report['verdict']} pytest-baseline "
            f"baseline_failures={report['baseline']['failures']} "
            f"candidate_failures={report['candidate']['failures']} "
            f"new_failures={len(report['blockers']['newFailures'])} "
            f"missing={len(report['blockers']['missingBaselineTests'])}"
        )
        return 0 if report["verdict"] == "PASS" else 1
    except (ComparisonError, OSError, ValueError) as exc:
        print(f"RESULT: FAIL pytest-baseline: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

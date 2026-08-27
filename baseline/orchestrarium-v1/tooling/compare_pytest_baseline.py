#!/usr/bin/env python3
"""Compare candidate pytest JUnit results against an immutable baseline run.

Only Pytest exit 0 (tests passed) and exit 1 (tests failed) can represent valid
test evidence. Operational exits such as interrupted, internal-error, usage-error,
or no-tests-collected always block, even when JUnit contains failures. Retained
known failures must preserve their normalized type, message, and body diagnostics.
Lane roots and explicitly declared volatile paths are normalized before comparison.
Reports are written atomically. Pure stdlib.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Pattern, Sequence

SCHEMA_VERSION = 2
NONPASSING = {"failure", "error"}
SKIPPED = {"skipped"}
VALID_PYTEST_RESULT_EXITS = {0, 1}
GIT_OBJECT_ID = re.compile(r"[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?")


class ComparisonError(RuntimeError):
    """Stable user-facing comparator error."""


@dataclass(frozen=True)
class TestCaseResult:
    test_id: str
    status: str
    classname: str
    name: str
    file: str | None
    outcome_type: str | None
    message: str | None
    details: str | None


def _normalise_path(value: str | None) -> str | None:
    return None if value is None else value.replace("\\", "/")


def _canonical_root(value: str) -> str:
    canonical = _normalise_path(value.rstrip("/\\"))
    if not canonical:
        raise ComparisonError("baseline and candidate roots must be non-empty")
    return canonical


def _root_variants(root: str) -> tuple[str, ...]:
    stripped = root.rstrip("/\\")
    variants = {
        root,
        stripped,
        root.replace("\\", "/"),
        root.replace("/", "\\"),
        stripped.replace("\\", "/"),
        stripped.replace("/", "\\"),
    }
    return tuple(sorted((value for value in variants if value), key=len, reverse=True))


def _compile_volatile_patterns(values: Sequence[str]) -> tuple[Pattern[str], ...]:
    patterns: list[Pattern[str]] = []
    for value in values:
        try:
            pattern = re.compile(value)
        except re.error as exc:
            raise ComparisonError(f"invalid volatile pattern {value!r}: {exc}") from exc
        if pattern.search("") is not None:
            raise ComparisonError(
                f"volatile pattern must not match empty text: {value!r}"
            )
        patterns.append(pattern)
    return tuple(patterns)


def _normalise_diagnostic(
    value: str | None,
    *,
    root: str,
    ref: str,
    volatile_patterns: Sequence[Pattern[str]],
) -> str | None:
    if value is None:
        return None

    text = value.replace("\r\n", "\n").replace("\r", "\n")
    for variant in _root_variants(root):
        text = text.replace(variant, "<ROOT>")
    if GIT_OBJECT_ID.fullmatch(ref):
        text = text.replace(ref, "<REF>")
    for pattern in volatile_patterns:
        text = pattern.sub("<VOLATILE>", text)

    lines = [line.rstrip(" \t") for line in text.split("\n")]
    while lines and not lines[-1]:
        lines.pop()
    normalized = "\n".join(lines)
    return normalized or None


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


def _status(
    element: ET.Element,
) -> tuple[str, str | None, str | None, str | None]:
    failure = element.find("failure")
    if failure is not None:
        return (
            "failure",
            failure.get("type"),
            failure.get("message"),
            failure.text,
        )
    error = element.find("error")
    if error is not None:
        return "error", error.get("type"), error.get("message"), error.text
    skipped = element.find("skipped")
    if skipped is not None:
        return (
            "skipped",
            skipped.get("type"),
            skipped.get("message"),
            skipped.text,
        )
    return "passed", None, None, None


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
        status, outcome_type, message, details = _status(element)
        results[test_id] = TestCaseResult(
            test_id=test_id,
            status=status,
            classname=element.get("classname", ""),
            name=element.get("name", ""),
            file=_normalise_path(element.get("file")),
            outcome_type=outcome_type,
            message=message,
            details=details,
        )
    if not results:
        raise ComparisonError(f"JUnit file contains no testcases: {path}")
    return results


def _diagnostic(
    result: TestCaseResult,
    *,
    root: str,
    ref: str,
    volatile_patterns: Sequence[Pattern[str]],
) -> tuple[str | None, str | None, str | None]:
    return (
        _normalise_diagnostic(
            result.outcome_type,
            root=root,
            ref=ref,
            volatile_patterns=volatile_patterns,
        ),
        _normalise_diagnostic(
            result.message,
            root=root,
            ref=ref,
            volatile_patterns=volatile_patterns,
        ),
        _normalise_diagnostic(
            result.details,
            root=root,
            ref=ref,
            volatile_patterns=volatile_patterns,
        ),
    )


def _missing_diagnostic(diagnostic: tuple[str | None, ...]) -> bool:
    return not any(part is not None for part in diagnostic)


def _diagnostic_record(
    result: TestCaseResult,
    *,
    root: str,
    ref: str,
    volatile_patterns: Sequence[Pattern[str]],
) -> dict[str, object]:
    outcome_type, message, details = _diagnostic(
        result,
        root=root,
        ref=ref,
        volatile_patterns=volatile_patterns,
    )
    encoded = json.dumps(
        [outcome_type, message, details],
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "type": outcome_type,
        "message": message,
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "sizeBytes": len(encoded),
    }


def _record(
    result: TestCaseResult,
    *,
    root: str,
    ref: str,
    volatile_patterns: Sequence[Pattern[str]],
) -> dict[str, object]:
    return {
        "id": result.test_id,
        "status": result.status,
        "classname": result.classname,
        "name": result.name,
        "file": result.file,
        "diagnostic": _diagnostic_record(
            result,
            root=root,
            ref=ref,
            volatile_patterns=volatile_patterns,
        ),
    }


def _exit_contradiction(exit_code: int, failure_count: int) -> list[dict[str, object]]:
    if exit_code not in VALID_PYTEST_RESULT_EXITS:
        return [
            {
                "exitCode": exit_code,
                "junitFailureCount": failure_count,
                "reason": "operational-pytest-exit",
            }
        ]
    if (exit_code == 0 and failure_count > 0) or (
        exit_code == 1 and failure_count == 0
    ):
        return [{"exitCode": exit_code, "junitFailureCount": failure_count}]
    return []


def compare(
    baseline: dict[str, TestCaseResult],
    candidate: dict[str, TestCaseResult],
    *,
    baseline_exit: int,
    candidate_exit: int,
    baseline_ref: str,
    candidate_ref: str,
    baseline_root: str,
    candidate_root: str,
    volatile_pattern_values: Sequence[str],
) -> dict[str, object]:
    if baseline_exit < 0 or candidate_exit < 0:
        raise ComparisonError("pytest exit codes must be non-negative")

    canonical_baseline_root = _canonical_root(baseline_root)
    canonical_candidate_root = _canonical_root(candidate_root)
    if canonical_baseline_root == canonical_candidate_root:
        raise ComparisonError("baseline and candidate roots must be distinct")
    volatile_patterns = _compile_volatile_patterns(volatile_pattern_values)

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
    retained_failures = baseline_failures & candidate_failures
    changed_known_failure_kind = sorted(
        test_id
        for test_id in retained_failures
        if baseline[test_id].status != candidate[test_id].status
    )

    baseline_diagnostics = {
        test_id: _diagnostic(
            baseline[test_id],
            root=baseline_root,
            ref=baseline_ref,
            volatile_patterns=volatile_patterns,
        )
        for test_id in baseline_failures
    }
    candidate_diagnostics = {
        test_id: _diagnostic(
            candidate[test_id],
            root=candidate_root,
            ref=candidate_ref,
            volatile_patterns=volatile_patterns,
        )
        for test_id in candidate_failures
    }
    missing_baseline_failure_diagnostics = sorted(
        test_id
        for test_id, diagnostic in baseline_diagnostics.items()
        if _missing_diagnostic(diagnostic)
    )
    missing_candidate_failure_diagnostics = sorted(
        test_id
        for test_id, diagnostic in candidate_diagnostics.items()
        if _missing_diagnostic(diagnostic)
    )
    missing_diagnostic_ids = set(missing_baseline_failure_diagnostics) | set(
        missing_candidate_failure_diagnostics
    )
    changed_known_failure_diagnostics = sorted(
        test_id
        for test_id in retained_failures
        if baseline[test_id].status == candidate[test_id].status
        and test_id not in missing_diagnostic_ids
        and baseline_diagnostics[test_id] != candidate_diagnostics[test_id]
    )
    unchanged_baseline_failures = sorted(
        test_id
        for test_id in retained_failures
        if baseline[test_id].status == candidate[test_id].status
        and test_id not in missing_diagnostic_ids
        and baseline_diagnostics[test_id] == candidate_diagnostics[test_id]
    )

    baseline_exit_contradiction = _exit_contradiction(
        baseline_exit, len(baseline_failures)
    )
    candidate_exit_contradiction = _exit_contradiction(
        candidate_exit, len(candidate_failures)
    )
    resolved_exit = (
        baseline_exit == 1
        and candidate_exit == 0
        and not candidate_failures
        and not baseline_exit_contradiction
    )
    pytest_exit_code_regression = (
        []
        if candidate_exit == baseline_exit or resolved_exit
        else [
            {
                "baselineExitCode": baseline_exit,
                "candidateExitCode": candidate_exit,
            }
        ]
    )

    blockers = {
        "newFailures": new_failures,
        "missingBaselineTests": missing_baseline_tests,
        "maskedBaselineFailures": masked_failures,
        "passingTestRegressions": regressions,
        "changedKnownFailureKind": changed_known_failure_kind,
        "missingBaselineFailureDiagnostics": missing_baseline_failure_diagnostics,
        "missingCandidateFailureDiagnostics": missing_candidate_failure_diagnostics,
        "changedKnownFailureDiagnostics": changed_known_failure_diagnostics,
        "baselineExitContradiction": baseline_exit_contradiction,
        "candidateExitContradiction": candidate_exit_contradiction,
        "pytestExitCodeRegression": pytest_exit_code_regression,
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
        "normalization": {
            "laneRoots": True,
            "gitObjectIds": True,
            "volatilePatterns": list(volatile_pattern_values),
            "lineEndings": True,
            "trailingHorizontalWhitespace": True,
            "trailingBlankLines": True,
        },
        "blockers": blockers,
        "observations": {
            "additionalCandidateTests": additional_candidate_tests,
            "resolvedBaselineFailures": resolved_failures,
            "unchangedBaselineFailures": unchanged_baseline_failures,
            "resolvedPytestExitCode": resolved_exit,
        },
        "baselineFailureDetails": [
            _record(
                baseline[test_id],
                root=baseline_root,
                ref=baseline_ref,
                volatile_patterns=volatile_patterns,
            )
            for test_id in sorted(baseline_failures)
        ],
        "candidateFailureDetails": [
            _record(
                candidate[test_id],
                root=candidate_root,
                ref=candidate_ref,
                volatile_patterns=volatile_patterns,
            )
            for test_id in sorted(candidate_failures)
        ],
        "verdict": verdict,
    }


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _atomic_write(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", dir=path.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-junit", type=Path, required=True)
    parser.add_argument("--candidate-junit", type=Path, required=True)
    parser.add_argument("--baseline-exit", type=int, required=True)
    parser.add_argument("--candidate-exit", type=int, required=True)
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--candidate-ref", required=True)
    parser.add_argument("--baseline-root", required=True)
    parser.add_argument("--candidate-root", required=True)
    parser.add_argument("--volatile-pattern", action="append", default=[])
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
            baseline_root=args.baseline_root,
            candidate_root=args.candidate_root,
            volatile_pattern_values=args.volatile_pattern,
        )
        _atomic_write(args.output, _canonical_json(report).encode("utf-8"))
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

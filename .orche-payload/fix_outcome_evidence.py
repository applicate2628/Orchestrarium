#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

EXPECTED_HEAD = "075e049ef4aecc110721d5a9496109fee204f872"
OUTCOME_PROPERTY = "orche.pytest.outcomes.v1"


def replace_once(path: Path, old: str, new: str) -> None:
    text = path.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one literal match, found {count}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def regex_replace_once(path: Path, pattern: str, replacement: str) -> None:
    text = path.read_text(encoding="utf-8")
    updated, count = re.subn(pattern, lambda _match: replacement, text, count=1, flags=re.S)
    if count != 1:
        raise RuntimeError(f"{path}: expected one regex match, found {count}")
    path.write_text(updated, encoding="utf-8")


def git(root: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def add_tests(root: Path) -> None:
    comparator_tests = root / "tests" / "test_orche_pytest_baseline.py"
    replace_once(
        comparator_tests,
        'B = "b" * 40\n',
        'B = "b" * 40\n'
        f'OUTCOME_PROPERTY = "{OUTCOME_PROPERTY}"\n'
        'OUTCOME_KEYS = ("passed", "skipped", "xfailed", "xpassed", "deselected")\n',
    )

    old_write_junit = '''def write_junit(path: Path, cases: list[dict[str, str | None]]) -> None:
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
'''
    new_write_junit = '''def outcome_evidence(
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
    ET.ElementTree(suite).write(path, encoding="unicode")
'''
    replace_once(comparator_tests, old_write_junit, new_write_junit)

    comparator_test_method = '''    def test_retained_zero_exit_outcome_fingerprint_changes_block(self) -> None:
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

'''
    replace_once(
        comparator_tests,
        "    def test_changed_or_missing_baseline_test_source_blocks(self) -> None:\n",
        comparator_test_method
        + "    def test_changed_or_missing_baseline_test_source_blocks(self) -> None:\n",
    )

    isolation_tests = root / "tests" / "test_orche_verifier_isolation.py"
    replace_once(isolation_tests, "import importlib.util\n", "import importlib.util\nimport json\n")

    parser_test_method = '''    def test_zero_exit_outcome_parser_preserves_non_skip_counts_and_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / "pytest.log"
            log.write_text(
                "================ short test summary info ================\\n"
                "PASSED tests/test_demo.py::test_pass[a]\\n"
                "PASSED tests/test_demo.py::test_pass[b]\\n"
                "XFAIL tests/test_demo.py::test_expected_failure - known defect\\n"
                "XPASS tests/test_demo.py::test_unexpected_pass - fixed defect\\n"
                "===== 2 passed, 1 xfailed, 1 xpassed, 3 deselected in 0.02s =====\\n",
                encoding="utf-8",
            )
            evidence = VERIFIER._pytest_zero_exit_outcome_evidence(log)

        self.assertEqual(
            evidence["counts"],
            {
                "passed": 2,
                "skipped": 0,
                "xfailed": 1,
                "xpassed": 1,
                "deselected": 3,
            },
        )
        self.assertEqual(
            evidence["diagnostics"]["passed"],
            [
                "PASSED tests/test_demo.py::test_pass[a]",
                "PASSED tests/test_demo.py::test_pass[b]",
            ],
        )
        self.assertEqual(
            evidence["diagnostics"]["xfailed"],
            [
                "XFAIL tests/test_demo.py::test_expected_failure - known defect",
            ],
        )
        self.assertEqual(
            evidence["diagnostics"]["xpassed"],
            [
                "XPASS tests/test_demo.py::test_unexpected_pass - fixed defect",
            ],
        )
        self.assertEqual(
            evidence["diagnostics"]["deselected"],
            ["3 deselected"],
        )

    def test_parent_generated_pytest_evidence_preserves_non_skip_outcomes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline_repo = root / "baseline"
            candidate_repo = root / "candidate"
            test_source = (
                "from pathlib import Path\\n"
                "import pytest\\n"
                "\\n"
                "state = (Path(__file__).parents[1] / 'runtime-state.txt').read_text().strip()\\n"
                "parameters = (1, 2) if state == 'wide' else (1,)\\n"
                "\\n"
                "@pytest.mark.parametrize('value', parameters)\\n"
                "def test_parameter(value):\\n"
                "    assert value > 0\\n"
                "\\n"
                "@pytest.mark.xfail(reason='known defect')\\n"
                "def test_expected_failure():\\n"
                "    assert False\\n"
                "\\n"
                "@pytest.mark.xfail(reason='fixed defect')\\n"
                "def test_unexpected_pass():\\n"
                "    assert True\\n"
            )
            for repo, state in ((baseline_repo, "wide"), (candidate_repo, "narrow")):
                (repo / "tests").mkdir(parents=True)
                (repo / "tests" / "test_outcomes.py").write_text(
                    test_source, encoding="utf-8"
                )
                (repo / "runtime-state.txt").write_text(state, encoding="utf-8")

            trusted = root / "trusted"
            baseline_evidence = trusted / "baseline-evidence"
            candidate_evidence = trusted / "candidate-evidence"
            baseline_lanes = root / "baseline-lanes"
            candidate_lanes = root / "candidate-lanes"
            for directory in (
                trusted,
                baseline_evidence,
                candidate_evidence,
                baseline_lanes,
                candidate_lanes,
            ):
                directory.mkdir(parents=True, exist_ok=True)

            baseline_result = VERIFIER.run_parent_generated_pytest_lane(
                repo_root=baseline_repo,
                test_paths=("tests/test_outcomes.py",),
                lane_parent=baseline_lanes,
                log_dir=trusted / "logs" / "baseline",
                junit_dir=baseline_evidence,
                suite_name="baseline",
                timeout_seconds=30,
                tools=TOOLS,
                trusted_root=trusted,
            )
            candidate_result = VERIFIER.run_parent_generated_pytest_lane(
                repo_root=candidate_repo,
                test_paths=("tests/test_outcomes.py",),
                lane_parent=candidate_lanes,
                log_dir=trusted / "logs" / "candidate",
                junit_dir=candidate_evidence,
                suite_name="candidate",
                timeout_seconds=30,
                tools=TOOLS,
                trusted_root=trusted,
            )

            def read_outcomes(path: Path) -> dict[str, object]:
                case = next(ET.parse(path).getroot().iter("testcase"))
                properties = case.find("properties")
                self.assertIsNotNone(properties)
                assert properties is not None
                values = [
                    item.get("value")
                    for item in properties.findall("property")
                    if item.get("name") == "orche.pytest.outcomes.v1"
                ]
                self.assertEqual(len(values), 1)
                assert values[0] is not None
                return json.loads(values[0])

            baseline_outcomes = read_outcomes(baseline_result.junit_path)
            candidate_outcomes = read_outcomes(candidate_result.junit_path)

        self.assertEqual(baseline_result.exit_code, 0)
        self.assertEqual(candidate_result.exit_code, 0)
        self.assertEqual(
            baseline_outcomes["counts"],
            {
                "passed": 2,
                "skipped": 0,
                "xfailed": 1,
                "xpassed": 1,
                "deselected": 0,
            },
        )
        self.assertEqual(
            candidate_outcomes["counts"],
            {
                "passed": 1,
                "skipped": 0,
                "xfailed": 1,
                "xpassed": 1,
                "deselected": 0,
            },
        )
        self.assertEqual(len(baseline_outcomes["diagnostics"]["passed"]), 2)
        self.assertEqual(len(candidate_outcomes["diagnostics"]["passed"]), 1)
        self.assertEqual(len(baseline_outcomes["diagnostics"]["xfailed"]), 1)
        self.assertEqual(len(baseline_outcomes["diagnostics"]["xpassed"]), 1)

'''
    replace_once(
        isolation_tests,
        "    def test_parent_generated_pytest_evidence_preserves_candidate_only_skip(self) -> None:\n",
        parser_test_method
        + "    def test_parent_generated_pytest_evidence_preserves_candidate_only_skip(self) -> None:\n",
    )


def implement_stage0_evidence(root: Path) -> None:
    path = root / "scripts" / "baseline" / "stage0_evidence.py"
    parser_block = r'''_PYTEST_OUTCOME_PROPERTY = "orche.pytest.outcomes.v1"
_PYTEST_OUTCOME_KEYS = ("passed", "skipped", "xfailed", "xpassed", "deselected")
_PYTEST_DIAGNOSTIC_PREFIXES = {
    "passed": "PASSED ",
    "skipped": "SKIPPED ",
    "xfailed": "XFAIL ",
    "xpassed": "XPASS ",
}
_PYTEST_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_PYTEST_TERMINAL_COUNT = re.compile(
    r"(?P<count>\d+)\s+"
    r"(?P<outcome>passed|failed|skipped|errors?|xfailed|xpassed|deselected|warnings?)\b"
)
_PYTEST_TERMINAL_DURATION = re.compile(
    r"\bin\s+\d+(?:\.\d+)?s\b"
)
_PYTEST_SKIP_DIAGNOSTIC = re.compile(
    r"^SKIPPED(?:\s+\[(?P<count>\d+)\])?\s+"
)


def _canonical_pytest_outcome_evidence(evidence: Mapping[str, object]) -> str:
    return json.dumps(
        evidence,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _pytest_skip_diagnostic_count(line: str) -> int:
    match = _PYTEST_SKIP_DIAGNOSTIC.match(line)
    if match is None:
        raise VerificationError(
            f"cannot parse Pytest skip diagnostic multiplicity: {line!r}"
        )
    count = match.group("count")
    return 1 if count is None else int(count)


def _pytest_zero_exit_outcome_evidence(path: Path) -> dict[str, object]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise VerificationError(f"cannot read Pytest file log {path}: {exc}") from exc
    text = _PYTEST_ANSI_ESCAPE.sub(
        "", raw.decode("utf-8", errors="replace")
    ).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    parsed_counts: dict[str, int] | None = None
    for line in reversed(lines):
        if _PYTEST_TERMINAL_DURATION.search(line) is None:
            continue
        matches = list(_PYTEST_TERMINAL_COUNT.finditer(line))
        if not matches:
            continue
        parsed_counts = {}
        for match in matches:
            outcome = match.group("outcome")
            if outcome in {"error", "errors"}:
                outcome = "errors"
            elif outcome in {"warning", "warnings"}:
                outcome = "warnings"
            parsed_counts[outcome] = (
                parsed_counts.get(outcome, 0) + int(match.group("count"))
            )
        break
    if parsed_counts is None:
        raise VerificationError(
            f"zero-exit Pytest file log lacks a parseable terminal summary: {path}"
        )
    if parsed_counts.get("failed", 0) or parsed_counts.get("errors", 0):
        raise VerificationError(
            f"zero-exit Pytest file log reports failures or errors: {path}"
        )
    counts = {
        outcome: parsed_counts.get(outcome, 0)
        for outcome in _PYTEST_OUTCOME_KEYS
    }
    observed = sum(
        counts[outcome]
        for outcome in ("passed", "skipped", "xfailed", "xpassed")
    )
    if observed == 0:
        raise VerificationError(
            f"zero-exit Pytest file log reports no executed or skipped tests: {path}"
        )

    diagnostics: dict[str, list[str]] = {}
    for outcome, prefix in _PYTEST_DIAGNOSTIC_PREFIXES.items():
        outcome_lines = [
            _xml_safe_text(line.strip())
            for line in lines
            if line.lstrip().startswith(prefix)
        ]
        expected = counts[outcome]
        actual = (
            sum(_pytest_skip_diagnostic_count(line) for line in outcome_lines)
            if outcome == "skipped"
            else len(outcome_lines)
        )
        if actual != expected:
            raise VerificationError(
                "Pytest terminal outcome diagnostics do not match the summary: "
                f"{path}; outcome={outcome}, expected={expected}, actual={actual}"
            )
        diagnostics[outcome] = outcome_lines
    deselected = counts["deselected"]
    diagnostics["deselected"] = (
        [] if deselected == 0 else [f"{deselected} deselected"]
    )
    return {
        "schemaVersion": 1,
        "counts": counts,
        "diagnostics": diagnostics,
    }


'''
    regex_replace_once(
        path,
        r'_PYTEST_ANSI_ESCAPE = re\.compile\(.*?\n\ndef _write_parent_junit\(',
        parser_block + "def _write_parent_junit(",
    )

    writer_function = r'''def _write_parent_junit(
    *,
    junit_dir: Path,
    suite_name: str,
    cases: Sequence[tuple[RetainedTestFile, CommandResult]],
) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", suite_name):
        raise VerificationError(f"invalid Pytest suite name: {suite_name!r}")
    zero_exit_outcomes = {
        test_file.inventory_path: _pytest_zero_exit_outcome_evidence(result.log_path)
        for test_file, result in cases
        if result.exit_code == 0
    }
    failures = sum(result.exit_code == 1 for _test, result in cases)
    errors = sum(result.exit_code not in {0, 1} for _test, result in cases)
    skipped = sum(
        int(evidence["counts"]["skipped"]) > 0
        for evidence in zero_exit_outcomes.values()
    )
    suite = ET.Element(
        "testsuite",
        {
            "name": suite_name,
            "tests": str(len(cases)),
            "failures": str(failures),
            "errors": str(errors),
            "skipped": str(skipped),
        },
    )
    for test_file, result in cases:
        testcase = ET.SubElement(
            suite,
            "testcase",
            {
                "classname": "pytest.file",
                "name": test_file.inventory_path,
                "file": test_file.inventory_path,
            },
        )
        if result.exit_code == 1:
            failure = ET.SubElement(
                testcase,
                "failure",
                {
                    "type": "pytest.file.failure",
                    "message": "one or more tests in the file failed",
                },
            )
            failure.text = _diagnostic_from_log(result.log_path)
        elif result.exit_code != 0:
            error = ET.SubElement(
                testcase,
                "error",
                {
                    "type": "pytest.file.operational",
                    "message": f"Pytest file lane exited {result.exit_code}",
                },
            )
            error.text = _diagnostic_from_log(result.log_path)
        else:
            evidence = zero_exit_outcomes[test_file.inventory_path]
            properties = ET.SubElement(testcase, "properties")
            ET.SubElement(
                properties,
                "property",
                {
                    "name": _PYTEST_OUTCOME_PROPERTY,
                    "value": _canonical_pytest_outcome_evidence(evidence),
                },
            )
            counts = evidence["counts"]
            diagnostics = evidence["diagnostics"]
            skipped_count = int(counts["skipped"])
            if skipped_count:
                skipped_case = ET.SubElement(
                    testcase,
                    "skipped",
                    {
                        "type": "pytest.file.skipped",
                        "message": (
                            f"{skipped_count} skipped test(s) in retained file"
                        ),
                    },
                )
                skipped_case.text = "\n".join(diagnostics["skipped"])
    payload = ET.tostring(suite, encoding="utf-8", xml_declaration=True)
    junit_dir.mkdir(parents=True, exist_ok=True)
    path = junit_dir / f"{suite_name}-{uuid.uuid4().hex}.xml"
    handle, identity = _fresh_regular_file(path)
    with handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    _verify_prepared_file(identity, require_nonempty=True)
    return path
'''
    regex_replace_once(
        path,
        r'def _write_parent_junit\(.*?\n\ndef run_parent_generated_pytest_lane\(',
        writer_function + "\n\ndef run_parent_generated_pytest_lane(",
    )
    replace_once(
        path,
        '                    "-r",\n                    "s",\n',
        '                    "-r",\n                    "A",\n',
    )
    shutil.copyfile(
        path,
        root
        / "baseline"
        / "orchestrarium-v1"
        / "tooling"
        / "stage0_evidence.py",
    )


def implement_pytest_comparator(root: Path) -> None:
    path = root / "scripts" / "baseline" / "compare_pytest_baseline.py"
    replace_once(
        path,
        'HEX=set("0123456789abcdefABCDEF"); PATHCH=set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")\n',
        'HEX=set("0123456789abcdefABCDEF"); PATHCH=set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")\n'
        f'OUTCOME_PROPERTY="{OUTCOME_PROPERTY}"; OUTCOME_KEYS=("passed","skipped","xfailed","xpassed","deselected"); RESULT_STATUSES={{"passed","skipped"}}\n',
    )
    outcome_functions = r'''def outcome(node,tid,status):
    values=[]
    props=node.find("properties")
    if props is not None:
        for item in props.findall("property"):
            if item.get("name")==OUTCOME_PROPERTY: values.append(item.get("value"))
    if not values:
        if status in RESULT_STATUSES: raise Error(f"JUnit testcase {tid!r} lacks trusted Pytest outcome evidence")
        return None
    if len(values)!=1 or values[0] is None: raise Error(f"JUnit testcase {tid!r} has invalid or duplicate Pytest outcome evidence")
    try: payload=json.loads(values[0])
    except json.JSONDecodeError as e: raise Error(f"JUnit testcase {tid!r} has invalid Pytest outcome JSON: {e}") from e
    if not isinstance(payload,dict) or set(payload)!={"schemaVersion","counts","diagnostics"} or payload.get("schemaVersion")!=1:
        raise Error(f"JUnit testcase {tid!r} has invalid Pytest outcome schema")
    counts=payload.get("counts"); diagnostics=payload.get("diagnostics")
    if not isinstance(counts,dict) or set(counts)!=set(OUTCOME_KEYS):
        raise Error(f"JUnit testcase {tid!r} has invalid Pytest outcome counts")
    if any(type(counts[key]) is not int or counts[key]<0 for key in OUTCOME_KEYS):
        raise Error(f"JUnit testcase {tid!r} has invalid Pytest outcome count value")
    if not isinstance(diagnostics,dict) or set(diagnostics)!=set(OUTCOME_KEYS):
        raise Error(f"JUnit testcase {tid!r} has invalid Pytest outcome diagnostics")
    for key in OUTCOME_KEYS:
        lines=diagnostics[key]
        if not isinstance(lines,list) or any(not isinstance(line,str) or not line for line in lines):
            raise Error(f"JUnit testcase {tid!r} has invalid {key} diagnostics")
    for key in ("passed","xfailed","xpassed"):
        if len(diagnostics[key])!=counts[key]:
            raise Error(f"JUnit testcase {tid!r} has inconsistent {key} diagnostics")
    if bool(diagnostics["skipped"])!=bool(counts["skipped"]):
        raise Error(f"JUnit testcase {tid!r} has inconsistent skipped diagnostics")
    expected_deselected=[] if counts["deselected"]==0 else [f"{counts['deselected']} deselected"]
    if diagnostics["deselected"]!=expected_deselected:
        raise Error(f"JUnit testcase {tid!r} has inconsistent deselected diagnostics")
    if sum(counts[key] for key in ("passed","skipped","xfailed","xpassed"))==0:
        raise Error(f"JUnit testcase {tid!r} has no executed or skipped outcomes")
    if status=="passed" and counts["skipped"]!=0:
        raise Error(f"passed JUnit testcase {tid!r} reports skipped outcomes")
    if status=="skipped" and counts["skipped"]==0:
        raise Error(f"skipped JUnit testcase {tid!r} lacks skipped outcomes")
    return payload

'''
    replace_once(path, "def junit(path):\n", outcome_functions + "def junit(path):\n")
    replace_once(
        path,
        '        out[tid]={"status":st,"type":typ,"message":msg,"body":body,"file":f or None,"class":c,"name":n}\n',
        '        out[tid]={"status":st,"type":typ,"message":msg,"body":body,"file":f or None,"class":c,"name":n,"outcomes":outcome(x,tid,st)}\n',
    )
    replace_once(
        path,
        'def diag(x,work,lane,oid,pats): return tuple(norm(x[k],work,lane,oid,pats) for k in ("type","message","body"))\n',
        'def diag(x,work,lane,oid,pats): return tuple(norm(x[k],work,lane,oid,pats) for k in ("type","message","body"))\n'
        'def outcome_diag(x,work,lane,oid,pats):\n'
        '    payload=x["outcomes"]\n'
        '    if payload is None: return None\n'
        '    return (tuple((key,payload["counts"][key]) for key in OUTCOME_KEYS),tuple((key,tuple(norm(line,work,lane,oid,pats) for line in payload["diagnostics"][key])) for key in OUTCOME_KEYS))\n',
    )
    replace_once(
        path,
        '    sd1={i:diag(b[i],roots[0],roots[2],br,pats) for i in bs&cs}; sd2={i:diag(c[i],roots[1],roots[3],cr,pats) for i in bs&cs}\n',
        '    sd1={i:diag(b[i],roots[0],roots[2],br,pats) for i in bs&cs}; sd2={i:diag(c[i],roots[1],roots[3],cr,pats) for i in bs&cs}\n'
        '    outcome_ids={i for i in bids&cids if b[i]["status"] in RESULT_STATUSES and c[i]["status"] in RESULT_STATUSES}\n'
        '    od1={i:outcome_diag(b[i],roots[0],roots[2],br,pats) for i in outcome_ids}; od2={i:outcome_diag(c[i],roots[1],roots[3],cr,pats) for i in outcome_ids}\n',
    )
    replace_once(
        path,
        '      "changedRetainedSkipDiagnostics":sorted(i for i in bs&cs if i not in set(missbs+misscs) and sd1[i]!=sd2[i]),\n',
        '      "changedRetainedSkipDiagnostics":sorted(i for i in bs&cs if i not in set(missbs+misscs) and sd1[i]!=sd2[i]),\n'
        '      "changedRetainedOutcomeEvidence":sorted(i for i in outcome_ids if od1[i]!=od2[i]),\n',
    )
    replace_once(path, 'return {"schemaVersion":3,', 'return {"schemaVersion":4,')
    shutil.copyfile(
        path,
        root
        / "baseline"
        / "orchestrarium-v1"
        / "tooling"
        / "compare_pytest_baseline.py",
    )


def update_metadata(root: Path) -> None:
    pin_path = root / "baseline" / "orchestrarium-v1" / "baseline-pin.json"
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    for key in ("pytestComparator", "stage0Evidence"):
        record = pin["tooling"][key]
        record["gitBlobSha"] = git(root, "hash-object", record["path"])
    pin_path.write_text(
        json.dumps(pin, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    readme = root / "baseline" / "orchestrarium-v1" / "README.md"
    replace_once(
        readme,
        "then has the trusted parent synthesize the accepted file-level JUnit Extensible Markup Language report, including skip counts and reasons, only after the test process and descendants are gone;",
        "then has the trusted parent synthesize the accepted file-level JUnit Extensible Markup Language report, including a canonical zero-exit outcome fingerprint with passed, skipped, expected-failure, unexpected-pass, and deselected counts plus trusted short diagnostics, only after the test process and descendants are gone;",
    )
    replace_once(
        readme,
        "- **JUnit XML:** JUnit Extensible Markup Language, the machine-readable Pytest result format; Stage 0 synthesizes the accepted file from parent-observed per-file process exits rather than accepting candidate-written XML.\n",
        "- **Expected failure (`xfail`):** a Pytest outcome in which a known failing case fails as declared without making the test process fail.\n"
        "- **JUnit XML:** JUnit Extensible Markup Language, the machine-readable Pytest result format; Stage 0 synthesizes the accepted file from parent-observed per-file process exits and canonical outcome fingerprints rather than accepting candidate-written XML.\n",
    )
    replace_once(
        readme,
        "- **V1:** Version 1, the accepted legacy behavior frozen before Orche 2.0 migration.\n",
        "- **Unexpected pass (`xpass`):** a Pytest outcome in which a case declared as an expected failure passes and must remain visible in parity evidence.\n"
        "- **V1:** Version 1, the accepted legacy behavior frozen before Orche 2.0 migration.\n",
    )

    release_notes = root / "RELEASE_NOTES.md"
    replace_once(
        release_notes,
        "and retained baseline test files run without candidate `conftest.py` discovery or an exposed JUnit path, after which the trusted parent creates the accepted file-level report from process exits and captured logs, including skip counts and reasons. **Why it matters:** malformed filenames can no longer break JSON evidence, invalid bootstrap configuration is no longer mislabeled as semantic drift, and candidate hooks cannot replace the accepted test report or force a false-green comparison.",
        "and retained baseline test files run without candidate `conftest.py` discovery or an exposed JUnit path, after which the trusted parent creates the accepted file-level report from process exits and captured logs, including passed, skipped, expected-failure, unexpected-pass, and deselected counts plus trusted short diagnostics. **Why it matters:** malformed filenames can no longer break JSON evidence, invalid bootstrap configuration is no longer mislabeled as semantic drift, candidate hooks cannot replace the accepted test report, and reduced parametrized coverage or changed expected-failure behavior cannot collapse into a false-green file-level pass.",
    )


def implement(root: Path) -> None:
    implement_stage0_evidence(root)
    implement_pytest_comparator(root)
    update_metadata(root)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("tests", "implement"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    head = git(root, "rev-parse", "HEAD")
    if head != EXPECTED_HEAD:
        raise RuntimeError(f"unexpected target HEAD: {head}")
    if args.phase == "tests":
        add_tests(root)
    else:
        implement(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

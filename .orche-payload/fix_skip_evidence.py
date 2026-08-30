#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

EXPECTED_HEAD = "8230b21c5377200b74b28b351ed65ed1de5e1d5d"


def run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"command failed ({result.returncode}): {' '.join(args)}\n{result.stdout}"
        )
    return result


def add_regression(repo: Path) -> None:
    path = repo / "tests/test_orche_verifier_isolation.py"
    text = path.read_text(encoding="utf-8")
    marker = '\n\nif __name__ == "__main__":\n    unittest.main()\n'
    test = r'''
    def test_parent_generated_pytest_evidence_preserves_candidate_only_skip(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline_repo = root / "baseline"
            candidate_repo = root / "candidate"
            test_source = (
                "from pathlib import Path\n"
                "import pytest\n"
                "\n"
                "def test_runtime_state():\n"
                "    state = (Path(__file__).parents[1] / 'runtime-state.txt').read_text().strip()\n"
                "    if state == 'skip':\n"
                "        pytest.skip('candidate-only runtime skip')\n"
                "    assert state == 'run'\n"
            )
            for repo, state in ((baseline_repo, "run"), (candidate_repo, "skip")):
                (repo / "tests").mkdir(parents=True)
                (repo / "tests" / "test_runtime_state.py").write_text(
                    test_source, encoding="utf-8"
                )
                (repo / "runtime-state.txt").write_text(state, encoding="utf-8")

            trusted = root / "trusted"
            logs = trusted / "logs"
            baseline_evidence = trusted / "baseline-evidence"
            candidate_evidence = trusted / "candidate-evidence"
            baseline_lanes = root / "baseline-lanes"
            candidate_lanes = root / "candidate-lanes"
            for directory in (
                trusted,
                logs,
                baseline_evidence,
                candidate_evidence,
                baseline_lanes,
                candidate_lanes,
            ):
                directory.mkdir(parents=True, exist_ok=True)

            baseline_result = VERIFIER.run_parent_generated_pytest_lane(
                repo_root=baseline_repo,
                test_paths=("tests/test_runtime_state.py",),
                lane_parent=baseline_lanes,
                log_dir=logs / "baseline",
                junit_dir=baseline_evidence,
                suite_name="baseline",
                timeout_seconds=30,
                tools=TOOLS,
                trusted_root=trusted,
            )
            candidate_result = VERIFIER.run_parent_generated_pytest_lane(
                repo_root=candidate_repo,
                test_paths=("tests/test_runtime_state.py",),
                lane_parent=candidate_lanes,
                log_dir=logs / "candidate",
                junit_dir=candidate_evidence,
                suite_name="candidate",
                timeout_seconds=30,
                tools=TOOLS,
                trusted_root=trusted,
            )

            self.assertEqual(baseline_result.exit_code, 0)
            self.assertEqual(candidate_result.exit_code, 0)
            baseline_suite = ET.parse(baseline_result.junit_path).getroot()
            candidate_suite = ET.parse(candidate_result.junit_path).getroot()
            self.assertEqual(baseline_suite.get("skipped"), "0")
            self.assertEqual(candidate_suite.get("skipped"), "1")
            baseline_case = next(baseline_suite.iter("testcase"))
            candidate_case = next(candidate_suite.iter("testcase"))
            self.assertIsNone(baseline_case.find("skipped"))
            candidate_skip = candidate_case.find("skipped")
            self.assertIsNotNone(candidate_skip)
            assert candidate_skip is not None
            self.assertIn("candidate-only runtime skip", candidate_skip.text or "")
'''
    if "test_parent_generated_pytest_evidence_preserves_candidate_only_skip" in text:
        raise RuntimeError("regression test already exists")
    if marker not in text:
        raise RuntimeError("cannot locate unittest footer")
    path.write_text(text.replace(marker, "\n" + test + marker), encoding="utf-8")


def verify_red(repo: Path) -> None:
    result = run(
        sys.executable,
        "tests/test_orche_verifier_isolation.py",
        "VerifierIsolationTests.test_parent_generated_pytest_evidence_preserves_candidate_only_skip",
        cwd=repo,
        check=False,
    )
    if result.returncode == 0:
        raise RuntimeError("new regression unexpectedly passed before the fix")
    if "AssertionError" not in result.stdout:
        raise RuntimeError(
            "new regression failed for an unexpected reason:\n" + result.stdout
        )
    print("RED verified: synthesized JUnit currently masks candidate-only skips")


def implement(repo: Path) -> None:
    mutable = repo / "scripts/baseline/stage0_evidence.py"
    text = mutable.read_text(encoding="utf-8")

    helper = r'''
_PYTEST_ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
_PYTEST_TERMINAL_COUNT = re.compile(
    r"(?P<count>\d+)\s+"
    r"(?P<outcome>passed|failed|skipped|errors?|xfailed|xpassed|deselected|warnings?)\b"
)
_PYTEST_TERMINAL_DURATION = re.compile(
    r"\bin\s+\d+(?:\.\d+)?s(?:\s+\([^)]*\))?\s*$"
)


def _pytest_zero_exit_skip_evidence(path: Path) -> tuple[int, str | None]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise VerificationError(f"cannot read Pytest file log {path}: {exc}") from exc
    text = _PYTEST_ANSI_ESCAPE.sub(
        "", raw.decode("utf-8", errors="replace")
    ).replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    counts: dict[str, int] | None = None
    for line in reversed(lines):
        if _PYTEST_TERMINAL_DURATION.search(line) is None:
            continue
        matches = list(_PYTEST_TERMINAL_COUNT.finditer(line))
        if not matches:
            continue
        counts = {}
        for match in matches:
            outcome = match.group("outcome")
            if outcome in {"error", "errors"}:
                outcome = "errors"
            elif outcome in {"warning", "warnings"}:
                outcome = "warnings"
            counts[outcome] = counts.get(outcome, 0) + int(match.group("count"))
        break
    if counts is None:
        raise VerificationError(
            f"zero-exit Pytest file log lacks a parseable terminal summary: {path}"
        )
    if counts.get("failed", 0) or counts.get("errors", 0):
        raise VerificationError(
            f"zero-exit Pytest file log reports failures or errors: {path}"
        )
    observed = sum(
        counts.get(outcome, 0)
        for outcome in ("passed", "skipped", "xfailed", "xpassed")
    )
    if observed == 0:
        raise VerificationError(
            f"zero-exit Pytest file log reports no executed or skipped tests: {path}"
        )
    skipped = counts.get("skipped", 0)
    if skipped == 0:
        return 0, None
    diagnostics = [
        line.strip()
        for line in lines
        if line.lstrip().startswith("SKIPPED ")
    ]
    if not diagnostics:
        raise VerificationError(
            f"Pytest reported {skipped} skipped test(s) without skip diagnostics: {path}"
        )
    return skipped, _xml_safe_text("\n".join(diagnostics))


'''
    marker = "\n\ndef _write_parent_junit(\n"
    if marker not in text:
        raise RuntimeError("cannot locate parent JUnit writer")
    text = text.replace(marker, "\n\n" + helper + "def _write_parent_junit(\n", 1)

    old = '''    failures = sum(result.exit_code == 1 for _test, result in cases)
    errors = sum(result.exit_code not in {0, 1} for _test, result in cases)
    suite = ET.Element(
'''
    new = '''    zero_exit_skips = {
        test_file.inventory_path: _pytest_zero_exit_skip_evidence(result.log_path)
        for test_file, result in cases
        if result.exit_code == 0
    }
    failures = sum(result.exit_code == 1 for _test, result in cases)
    errors = sum(result.exit_code not in {0, 1} for _test, result in cases)
    skipped = sum(
        skipped_count > 0
        for skipped_count, _diagnostic in zero_exit_skips.values()
    )
    suite = ET.Element(
'''
    if old not in text:
        raise RuntimeError("cannot locate parent JUnit counters")
    text = text.replace(old, new, 1)
    if '            "skipped": "0",' not in text:
        raise RuntimeError("cannot locate parent JUnit skipped counter")
    text = text.replace(
        '            "skipped": "0",',
        '            "skipped": str(skipped),',
        1,
    )

    old = '''        elif result.exit_code != 0:
            error = ET.SubElement(
                testcase,
                "error",
                {
                    "type": "pytest.file.operational",
                    "message": f"Pytest file lane exited {result.exit_code}",
                },
            )
            error.text = _diagnostic_from_log(result.log_path)
    payload = ET.tostring(suite, encoding="utf-8", xml_declaration=True)
'''
    new = '''        elif result.exit_code != 0:
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
            skipped_count, skip_diagnostic = zero_exit_skips[
                test_file.inventory_path
            ]
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
                skipped_case.text = skip_diagnostic
    payload = ET.tostring(suite, encoding="utf-8", xml_declaration=True)
'''
    if old not in text:
        raise RuntimeError("cannot locate parent JUnit case writer")
    text = text.replace(old, new, 1)

    old = '''                    "-p",
                    "no:cacheprovider",
                    "--tb=long",
'''
    new = '''                    "-p",
                    "no:cacheprovider",
                    "-r",
                    "s",
                    "--tb=long",
'''
    if old not in text:
        raise RuntimeError("cannot locate Pytest command")
    text = text.replace(old, new, 1)
    mutable.write_text(text, encoding="utf-8")

    frozen = repo / "baseline/orchestrarium-v1/tooling/stage0_evidence.py"
    frozen.write_text(text, encoding="utf-8")

    pin_path = repo / "baseline/orchestrarium-v1/baseline-pin.json"
    pin = json.loads(pin_path.read_text(encoding="utf-8"))
    blob = run(
        "git",
        "hash-object",
        str(mutable.relative_to(repo)),
        cwd=repo,
    ).stdout.strip()
    pin["tooling"]["stage0Evidence"]["gitBlobSha"] = blob
    pin_path.write_text(
        json.dumps(pin, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    readme = repo / "baseline/orchestrarium-v1/README.md"
    readme_text = readme.read_text(encoding="utf-8")
    old_readme = (
        "then has the trusted parent synthesize the accepted file-level "
        "JUnit Extensible Markup Language report only after the test process "
        "and descendants are gone;"
    )
    new_readme = (
        "then has the trusted parent synthesize the accepted file-level "
        "JUnit Extensible Markup Language report, including skip counts and "
        "reasons, only after the test process and descendants are gone;"
    )
    if old_readme not in readme_text:
        raise RuntimeError("cannot locate README JUnit contract")
    readme.write_text(
        readme_text.replace(old_readme, new_readme, 1),
        encoding="utf-8",
    )

    release = repo / "RELEASE_NOTES.md"
    release_text = release.read_text(encoding="utf-8")
    old_release = (
        "after which the trusted parent creates the accepted file-level "
        "report from process exits and captured logs."
    )
    new_release = (
        "after which the trusted parent creates the accepted file-level "
        "report from process exits and captured logs, including skip counts "
        "and reasons."
    )
    if old_release not in release_text:
        raise RuntimeError("cannot locate release-note JUnit wording")
    release.write_text(
        release_text.replace(old_release, new_release, 1),
        encoding="utf-8",
    )


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: fix_skip_evidence.py REPO")
    repo = Path(sys.argv[1]).resolve(strict=True)
    head = run("git", "rev-parse", "HEAD", cwd=repo).stdout.strip()
    if head != EXPECTED_HEAD:
        raise RuntimeError(f"unexpected PR head: {head}")
    if run("git", "status", "--porcelain=v1", cwd=repo).stdout:
        raise RuntimeError("PR checkout is not clean")
    add_regression(repo)
    verify_red(repo)
    implement(repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "baseline" / "verify_stage0.py"
README = ROOT / "baseline" / "orchestrarium-v1" / "README.md"
SPEC = importlib.util.spec_from_file_location("verify_stage0_review9", SCRIPT)
assert SPEC and SPEC.loader
VERIFIER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = VERIFIER
SPEC.loader.exec_module(VERIFIER)
REAL_GIT = Path(shutil.which("git") or "git").resolve()
REAL_BASH = Path(shutil.which("bash") or "bash").resolve()
TOOLS = (
    VERIFIER.ExternalTools(Path(sys.executable).resolve(), REAL_GIT, REAL_BASH)
    if sys.platform.startswith("linux")
    else None
)


def run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        [str(REAL_GIT), *args],
        cwd=repo,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode:
        raise AssertionError(result.stdout + result.stderr)
    return result.stdout.strip()


def run_lane(repo: Path, trusted: Path):
    logs = trusted / "logs"
    junit = trusted / "junit"
    lanes = trusted.parent / "lanes"
    for directory in (trusted, logs, junit, lanes):
        directory.mkdir(parents=True, exist_ok=True)
    test_paths = tuple(
        path.relative_to(repo).as_posix()
        for path in sorted((repo / "tests").glob("test_*.py"))
    )
    return VERIFIER.run_parent_generated_pytest_lane(
        repo_root=repo,
        test_paths=test_paths,
        lane_parent=lanes,
        log_dir=logs,
        junit_dir=junit,
        suite_name="candidate",
        timeout_seconds=30,
        tools=TOOLS,
        trusted_root=trusted,
        revalidate_worktrees=lambda: None,
    )


@unittest.skipUnless(sys.platform.startswith("linux"), "Linux Stage 0 containment")
class ReviewNineRegressionTests(unittest.TestCase):
    def test_plain_pytest_failure_cannot_be_rewritten_by_sessionfinish(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tests = repo / "tests"
            tests.mkdir(parents=True)
            (repo / "evil.py").write_text(
                "import gc, sys\n"
                "from _pytest.config import Config\n"
                "def pytest_sessionfinish(session, exitstatus):\n"
                "    reporter = session.config.pluginmanager.getplugin('terminalreporter')\n"
                "    failed = list(reporter.stats.get('failed', []))\n"
                "    for report in failed:\n"
                "        report.outcome = 'passed'\n"
                "    reporter.stats.clear()\n"
                "    reporter.stats['passed'] = failed\n"
                "    session.exitstatus = 0\n"
                "config = next(item for item in gc.get_objects() if isinstance(item, Config))\n"
                "config.pluginmanager.register(sys.modules[__name__], 'candidate-evil')\n",
                encoding="utf-8",
            )
            (tests / "test_plain.py").write_text(
                "import evil\n"
                "def test_plain_failure():\n"
                "    assert False, 'real plain Pytest failure'\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                VERIFIER.VerificationError,
                "late Pytest plugin registration|trusted Pytest event processing failed",
            ):
                run_lane(repo, root / "trusted")

    def test_trusted_pytest_lane_preserves_one_process_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            tests = repo / "tests"
            tests.mkdir(parents=True)
            (repo / "counter.py").write_text(
                "value = 0\n"
                "def first_call():\n"
                "    global value\n"
                "    value += 1\n"
                "    return value\n",
                encoding="utf-8",
            )
            for name in ("a", "b"):
                (tests / f"test_{name}.py").write_text(
                    "from counter import first_call\n"
                    "def test_first_call():\n"
                    "    assert first_call() == 1\n",
                    encoding="utf-8",
                )
            result = run_lane(repo, root / "trusted")
            self.assertEqual(result.exit_code, 1)
            self.assertIn(
                "assert 2 == 1",
                result.junit_path.read_text(encoding="utf-8"),
            )

    def test_review_envelope_is_direct_and_manifest_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            run_git(repo, "init", "-q")
            run_git(repo, "config", "user.name", "Test")
            run_git(repo, "config", "user.email", "test@example.invalid")
            (repo / "payload.txt").write_text("code\n", encoding="utf-8")
            run_git(repo, "add", ".")
            run_git(repo, "commit", "-qm", "code")
            candidate_ref = run_git(repo, "rev-parse", "HEAD")
            candidate_tree = run_git(repo, "rev-parse", "HEAD^{tree}")
            manifest = repo / VERIFIER.DISPOSITIONS_PATH
            manifest.parent.mkdir(parents=True)
            manifest.write_text(
                json.dumps(
                    {
                        "schemaVersion": 2,
                        "scope": "ORCHE-IMPL-000",
                        "baselineRef": "a" * 40,
                        "baselineTree": "b" * 40,
                        "candidateRef": candidate_ref,
                        "candidateTree": candidate_tree,
                        "reviewEnvelope": {
                            "kind": "manifest-only-child",
                            "path": VERIFIER.DISPOSITIONS_PATH,
                        },
                        "entries": [],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            run_git(repo, "add", VERIFIER.DISPOSITIONS_PATH)
            run_git(repo, "commit", "-qm", "manifest")
            reviewed_ref = run_git(repo, "rev-parse", "HEAD")
            with tempfile.TemporaryDirectory() as lane:
                env = VERIFIER.build_sanitized_env(
                    tools=TOOLS, lane_root=Path(lane) / "trusted"
                )
                payload = VERIFIER._load_review_envelope(
                    tools=TOOLS,
                    env=env,
                    candidate_root=repo,
                    reviewed_ref=reviewed_ref,
                )
            self.assertEqual(payload["candidateRef"], candidate_ref)

            (repo / "extra.txt").write_text("unexpected\n", encoding="utf-8")
            run_git(repo, "add", "extra.txt")
            run_git(repo, "commit", "-qm", "not manifest only")
            invalid_ref = run_git(repo, "rev-parse", "HEAD")
            with tempfile.TemporaryDirectory() as lane:
                env = VERIFIER.build_sanitized_env(
                    tools=TOOLS, lane_root=Path(lane) / "trusted"
                )
                with self.assertRaisesRegex(
                    VERIFIER.VerificationError,
                    "direct manifest-only child|paths other than",
                ):
                    VERIFIER._load_review_envelope(
                        tools=TOOLS,
                        env=env,
                        candidate_root=repo,
                        reviewed_ref=invalid_ref,
                    )

    def test_partial_report_copy_is_removed_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            output = root / "visible-run"
            output.mkdir()
            original = VERIFIER._ORIGINAL_COPY_REPORTS

            def fail_after_partial(_trusted_root: Path, destination: Path) -> None:
                (destination / "partial.json").write_text("partial")
                raise OSError("copy failed")

            VERIFIER._ORIGINAL_COPY_REPORTS = fail_after_partial
            try:
                with self.assertRaisesRegex(OSError, "copy failed"):
                    VERIFIER._copy_reports_fail_closed(root / "trusted", output)
            finally:
                VERIFIER._ORIGINAL_COPY_REPORTS = original
            self.assertFalse(output.exists())

    def test_claude_validator_accepts_actual_terminal_markers(self) -> None:
        spec = next(item for item in VERIFIER.VALIDATORS if item.name == "claude-pack")
        for marker in ("  RESULT: PASS", "  RESULT: PASS with warnings"):
            self.assertRegex(marker, spec.success_pattern)
        self.assertRegex("  RESULT: FAIL", spec.failure_pattern)

    def test_bootstrap_uses_verified_env_executable(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("VERIFIER_ENV=/usr/bin/env", text)
        self.assertIn('assert_canonical_external "$VERIFIER_ENV"', text)
        self.assertIn('"$VERIFIER_ENV" -i', text)
        self.assertNotRegex(text, r"(?m)^\s*env -i\b")
        self.assertLess(
            text.index('assert_canonical_external "$VERIFIER_ENV"'),
            text.index('"$VERIFIER_ENV" -i'),
        )


if __name__ == "__main__":
    unittest.main()

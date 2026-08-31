#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import re
import stat
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "baseline" / "orchestrarium-v1" / "README.md"
PIN = ROOT / "baseline" / "orchestrarium-v1" / "baseline-pin.json"
EXPECTED_FOCUSED = {
    "tests/test_orche_baseline_pin.py",
    "tests/test_orche_pytest_baseline.py",
    "tests/test_orche_baseline_inventory.py",
    "tests/test_orche_target_effect_baseline.py",
    "tests/test_orche_command_baseline.py",
    "tests/test_orche_capability_baseline.py",
    "tests/test_orche_verifier_isolation.py",
    "tests/test_orche_review_regressions.py",
}


def load_verifier(name: str):
    path = ROOT / "scripts" / "baseline" / "verify_stage0.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_python(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    env = dict(os.environ)
    env.update(
        {
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONNOUSERSITE": "1",
        }
    )
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )


class ReviewRegressionTests(unittest.TestCase):
    def test_mutable_and_frozen_tooling_are_byte_identical(self) -> None:
        for name in (
            "build_inventory.py",
            "build_target_effect_baseline.py",
            "compare_capability_baseline.py",
            "compare_command_baseline.py",
            "compare_pytest_baseline.py",
            "stage0_runtime.py",
            "stage0_evidence.py",
            "stage0_orchestrator.py",
            "verify_stage0.py",
        ):
            self.assertEqual(
                (ROOT / "scripts" / "baseline" / name).read_bytes(),
                (ROOT / "baseline" / "orchestrarium-v1" / "tooling" / name).read_bytes(),
                name,
            )

    def test_readme_delegates_to_frozen_verifier_and_cleans_bootstrap_state(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("verify_stage0.py", text)
        self.assertIn("git cat-file blob", text)
        self.assertIn("python -I", text)
        self.assertNotIn("rm -rf", text)
        self.assertIn("unique output directory", text)
        self.assertIn("removed after a successful run", text)
        self.assertIn("trap cleanup_bootstrap EXIT", text)
        self.assertLess(
            text.index("trap cleanup_bootstrap EXIT"),
            text.index(': > "$BOOTSTRAP_ROOT/gitconfig"'),
        )
        self.assertLess(text.index("verify_shared_tmp"), text.index("BOOTSTRAP_ROOT="))
        self.assertIn("--preserve-failed-evidence", text)
        self.assertIn("## Terms and Abbreviations", text)
        self.assertTrue(
            text.rstrip().endswith(
                "V1:** Version 1, the accepted legacy behavior frozen before Orche 2.0 migration."
            )
        )

    def test_trusted_contract_covers_full_review_hardening(self) -> None:
        text = README.read_text(encoding="utf-8")
        required = (
            "GIT_NO_REPLACE_OBJECTS=1",
            "--no-replace-objects",
            "--git-dir",
            "--work-tree",
            "Linux child subreaper",
            "setsid()",
            "/proc",
            "PYTHONSAFEPATH=1",
            "PYTHONPATH",
            "revalidates that identity immediately before every launch",
            "snapshots the complete trusted-tree membership and identity",
            "symbolic links, hard links",
            "rechecks both baseline and candidate worktrees",
            "Git mode, and Git object type",
            "marker-free successes",
            "Operational Pytest exits",
            "root-owned directory with sticky-bit semantics",
            "single-process full Pytest suite",
            "independent `unittest` suite",
            "supplemental blockers",
        )
        for marker in required:
            self.assertIn(marker, text)

    def test_focused_suite_list_is_explicit_and_complete(self) -> None:
        module = load_verifier("stage0_verifier_review")
        self.assertEqual(set(module.FOCUSED_TESTS), EXPECTED_FOCUSED)

    def test_verifier_hardens_shared_temporary_parent(self) -> None:
        module = load_verifier("stage0_temp_parent_review")
        good = types.SimpleNamespace(st_mode=stat.S_IFDIR | 0o1777, st_uid=0)
        module._validate_shared_temporary_parent(Path("/tmp"), good)
        for metadata in (
            types.SimpleNamespace(st_mode=stat.S_IFLNK | 0o777, st_uid=0),
            types.SimpleNamespace(st_mode=stat.S_IFDIR | 0o0777, st_uid=0),
            types.SimpleNamespace(st_mode=stat.S_IFDIR | 0o1777, st_uid=1000),
        ):
            with self.assertRaises(module.VerificationError):
                module._validate_shared_temporary_parent(Path("/tmp"), metadata)
        self.assertIs(
            module._evidence._private_temp_parent,
            module._safe_private_temp_parent,
        )
        self.assertIs(module._private_temp_parent, module._safe_private_temp_parent)
        self.assertEqual(module._safe_private_temp_parent(), Path("/tmp"))

    def test_pytest_hook_false_pass_is_blocked_by_independent_unittest_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "test_failure.py").write_text(
                "import unittest\n"
                "class Failing(unittest.TestCase):\n"
                "    def test_failure(self):\n"
                "        self.fail('real failure')\n",
                encoding="utf-8",
            )
            (tests / "conftest.py").write_text(
                "def pytest_sessionfinish(session, exitstatus):\n"
                "    session.exitstatus = 0\n"
                "    terminal = session.config.pluginmanager.getplugin('terminalreporter')\n"
                "    if terminal is not None:\n"
                "        reports = list(terminal.stats.get('failed', ()))\n"
                "        terminal.stats.pop('failed', None)\n"
                "        terminal.stats.pop('error', None)\n"
                "        terminal.stats['passed'] = reports or [object()]\n",
                encoding="utf-8",
            )
            forged = run_python(
                root,
                "-B",
                "-m",
                "pytest",
                "-q",
                "--tb=no",
                "--disable-warnings",
                "tests/",
            )
            independent = run_python(
                root,
                "-B",
                "-m",
                "unittest",
                "discover",
                "-q",
                "-s",
                "tests",
                "-p",
                "test_*.py",
            )
        self.assertEqual(forged.returncode, 0, forged.stdout)
        self.assertIn("1 passed", forged.stdout)
        self.assertEqual(independent.returncode, 1, independent.stdout)
        self.assertIn("FAILED (failures=1)", independent.stdout)

    def test_full_suite_gates_preserve_process_global_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            tests = root / "tests"
            tests.mkdir()
            (tests / "__init__.py").write_text("", encoding="utf-8")
            (tests / "shared_state.py").write_text("value = 0\n", encoding="utf-8")
            source = (
                "import unittest\n"
                "from tests import shared_state\n"
                "class Stateful(unittest.TestCase):\n"
                "    def test_counter(self):\n"
                "        shared_state.value += 1\n"
                "        self.assertEqual(shared_state.value, 1)\n"
            )
            (tests / "test_a.py").write_text(source, encoding="utf-8")
            (tests / "test_b.py").write_text(source, encoding="utf-8")
            separate = [
                run_python(
                    root,
                    "-B",
                    "-m",
                    "pytest",
                    "--noconftest",
                    "-q",
                    f"tests/test_{name}.py",
                )
                for name in ("a", "b")
            ]
            full_pytest = run_python(
                root,
                "-B",
                "-m",
                "pytest",
                "-q",
                "--tb=no",
                "--disable-warnings",
                "tests/",
            )
            full_unittest = run_python(
                root,
                "-B",
                "-m",
                "unittest",
                "discover",
                "-q",
                "-s",
                "tests",
                "-p",
                "test_*.py",
            )
        self.assertEqual([item.returncode for item in separate], [0, 0])
        self.assertEqual(full_pytest.returncode, 1, full_pytest.stdout)
        self.assertEqual(full_unittest.returncode, 1, full_unittest.stdout)

    def test_pin_and_dispositions_are_committed_sources_not_generated_evidence(self) -> None:
        self.assertTrue(PIN.is_file())
        self.assertTrue(
            (ROOT / "baseline" / "orchestrarium-v1" / "reviewed-dispositions.json").is_file()
        )

    def test_bootstrap_rejects_symbolic_or_abbreviated_reviewed_refs_before_pin_read(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn('case "$REVIEWED_REF" in', text)
        self.assertIn('case "${#REVIEWED_REF}" in', text)
        self.assertIn("RESOLVED_REVIEWED_REF=", text)
        self.assertLess(text.index('case "$REVIEWED_REF" in'), text.index("PIN_JSON="))
        self.assertLess(text.index("RESOLVED_REVIEWED_REF="), text.index("PIN_JSON="))

    def test_repository_validator_marker_contracts_match_real_terminal_outputs(self) -> None:
        module = load_verifier("stage0_validator_markers")
        markers = {item.name: item for item in module.VALIDATORS}
        samples = {
            "pytest-full-suite": (
                "<VOLATILE> passed in <VOLATILE>",
                "<VOLATILE> failed, <VOLATILE> passed in <VOLATILE>",
            ),
            "unittest-full-suite": (
                "Ran <VOLATILE> tests in <VOLATILE>\n\nOK",
                "FAILED (failures=1)",
            ),
            "agents-spine": ("RESULT: PASS", "RESULT: FAIL"),
            "codex-pack": ("VALIDATION PASSED", "VALIDATION FAILED"),
            "claude-pack": ("VALIDATION PASSED (with warnings)", "VALIDATION FAILED"),
            "gemini-pack": (
                "PASS: Gemini source tree present at /repo/src.gemini",
                "FAIL: missing file",
            ),
            "qwen-pack": (
                "PASS: Qwen source tree present at /repo/src.qwen",
                "FAIL: missing file",
            ),
            "agents-mode-docs": (
                "PASS: agents-mode docs are synced",
                "FAIL: docs/agents-mode-reference.md is not synced",
            ),
            "universal-hooks": (
                "PASS: universal-hooks canon in sync with both mirrors",
                "FAIL: 2 mirrored file(s) drifted from scripts/universal-hooks/ canon. Run sync.",
            ),
            "agents-mode-installers": (
                "PASS: agents-mode installer regression validated",
                "FAIL: installer output drifted",
            ),
        }
        self.assertEqual(set(markers), set(samples))
        for name, (success, failure) in samples.items():
            self.assertIsNotNone(re.search(markers[name].success_pattern, success), name)
            self.assertIsNotNone(re.search(markers[name].failure_pattern, failure), name)

    def test_orchestrator_uses_workspace_lifecycle_and_two_worktree_rechecks(self) -> None:
        source = (ROOT / "scripts" / "baseline" / "stage0_orchestrator.py").read_text()
        self.assertIn("verification_workspace(", source)
        self.assertIn('getattr(args, "preserve_failed_evidence", False)', source)
        self.assertIn("_assert_both_worktrees_clean(", source)
        focused = source[source.index("for index, relative in enumerate(FOCUSED_TESTS)") :]
        focused = focused[: focused.index("baseline_lane_root =")]
        self.assertIn("_assert_both_worktrees_clean(", focused)

    def test_orchestrator_uses_parent_generated_pytest_evidence(self) -> None:
        source = (ROOT / "scripts" / "baseline" / "stage0_orchestrator.py").read_text()
        self.assertIn("run_parent_generated_pytest_lane(", source)
        self.assertNotIn("--junitxml", source)
        self.assertNotIn("mutable_paths=(baseline_xml,)", source)
        self.assertNotIn("mutable_paths=(candidate_xml,)", source)

    def test_retained_pytest_files_use_parent_capture_and_per_file_revalidation(self) -> None:
        evidence = (
            ROOT / "scripts" / "baseline" / "stage0_evidence.py"
        ).read_text(encoding="utf-8")
        orchestrator = (
            ROOT / "scripts" / "baseline" / "stage0_orchestrator.py"
        ).read_text(encoding="utf-8")
        self.assertIn("stdout=subprocess.PIPE", evidence)
        self.assertIn("_write_parent_captured_log", evidence)
        self.assertIn("revalidate_worktrees()", evidence)
        self.assertIn("def revalidate_pytest_worktrees()", orchestrator)
        self.assertEqual(
            orchestrator.count(
                "revalidate_worktrees=revalidate_pytest_worktrees"
            ),
            2,
        )

    def test_comparators_distinguish_invalid_evidence_from_semantic_drift(self) -> None:
        command = (ROOT / "scripts" / "baseline" / "compare_command_baseline.py").read_text()
        pytest_source = (ROOT / "scripts" / "baseline" / "compare_pytest_baseline.py").read_text()
        capability = (ROOT / "scripts" / "baseline" / "compare_capability_baseline.py").read_text()
        self.assertIn('"unverified-success", 2', command)
        self.assertIn("a.baseline_exit not in {0,1}", pytest_source)
        self.assertIn('raw.get("mode")', capability)
        self.assertIn('raw.get("objectType")', capability)

    def test_documented_bootstrap_is_valid_bash_syntax(self) -> None:
        text = README.read_text(encoding="utf-8")
        start = text.index("```bash") + len("```bash\n")
        end = text.index("\n```", start)
        with tempfile.TemporaryDirectory() as temp:
            script = Path(temp) / "bootstrap.sh"
            script.write_text(text[start:end] + "\n", encoding="utf-8")
            result = subprocess.run(
                ["bash", "-n", str(script)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()

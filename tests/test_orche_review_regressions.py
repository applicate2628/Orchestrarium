#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import tempfile
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
        )
        for marker in required:
            self.assertIn(marker, text)

    def test_focused_suite_list_is_explicit_and_complete(self) -> None:
        module = load_verifier("stage0_verifier_review")
        self.assertEqual(set(module.FOCUSED_TESTS), EXPECTED_FOCUSED)

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

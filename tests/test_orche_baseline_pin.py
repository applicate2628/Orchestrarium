#!/usr/bin/env python3
"""Regression tests for the committed Stage 0 baseline pin and local-only policy."""

from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE_DIR = ROOT / "baseline" / "orchestrarium-v1"
PIN_PATH = BASELINE_DIR / "baseline-pin.json"
README_PATH = BASELINE_DIR / "README.md"
GITIGNORE_PATH = ROOT / ".gitignore"
EXPECTED_COMMIT = "ce2052fb773576fd6e3206c2a7e21e01852d556b"
EXPECTED_TREE = "04dccf4575f17c9c5533474d2e0fd1503bfeceb7"
TOOL_PATHS = {
    "inventoryGenerator": "scripts/baseline/build_inventory.py",
    "targetEffectGenerator": "scripts/baseline/build_target_effect_baseline.py",
    "pytestComparator": "scripts/baseline/compare_pytest_baseline.py",
    "commandComparator": "scripts/baseline/compare_command_baseline.py",
}
VALIDATOR_MARKERS = (
    "src.codex/skills/lead/scripts/validate-skill-pack.sh",
    "src.claude/agents/scripts/validate-skill-pack.sh",
    "src.gemini/scripts/validate-pack.sh",
    "src.qwen/scripts/validate-pack.sh",
    "scripts/sync-agents-mode-docs.py",
    "scripts/validate-agents-spine.py",
    "scripts/sync-universal-hooks.py",
    "scripts/validate-agents-mode-installers.py",
)


def git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed ({result.returncode})\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result.stdout.strip()


class BaselinePinTests(unittest.TestCase):
    def test_pin_matches_exact_main_git_object_and_immutable_tool_blobs(self) -> None:
        payload = json.loads(PIN_PATH.read_text(encoding="utf-8"))
        baseline = payload["baseline"]

        self.assertEqual(payload["schemaVersion"], 4)
        self.assertEqual(baseline["sourceBranch"], "main")
        self.assertEqual(baseline["commitSha"], EXPECTED_COMMIT)
        self.assertEqual(baseline["sourceBranchHeadAtCapture"], EXPECTED_COMMIT)
        self.assertEqual(baseline["treeSha"], EXPECTED_TREE)
        self.assertNotIn("sourcePullRequest", baseline)
        self.assertNotIn("sourcePullRequestHeadAtCapture", baseline)
        self.assertEqual(
            git("rev-parse", "--verify", f"{EXPECTED_COMMIT}^{{commit}}"),
            EXPECTED_COMMIT,
        )
        self.assertEqual(
            git("rev-parse", "--verify", f"{EXPECTED_COMMIT}^{{tree}}"),
            EXPECTED_TREE,
        )

        tooling = payload["tooling"]
        self.assertEqual(set(tooling), set(TOOL_PATHS))
        for name, relative_path in TOOL_PATHS.items():
            record = tooling[name]
            blob_sha = record["gitBlobSha"]
            owning_commit = record["owningCommit"]
            self.assertEqual(record["path"], relative_path)
            self.assertEqual(record["materialization"], "git-cat-file-blob")
            self.assertEqual(
                git("rev-parse", "--verify", f"{owning_commit}^{{commit}}"),
                owning_commit,
            )
            tree_line = git("ls-tree", owning_commit, "--", relative_path)
            mode, object_type, recorded_sha, recorded_path = tree_line.split(None, 3)
            self.assertTrue(mode)
            self.assertEqual(object_type, "blob")
            self.assertEqual(recorded_sha, blob_sha)
            self.assertEqual(recorded_path, relative_path)
            self.assertEqual(git("cat-file", "-t", blob_sha), "blob")

    def test_verification_is_local_only_and_large_outputs_are_not_tracked(self) -> None:
        payload = json.loads(PIN_PATH.read_text(encoding="utf-8"))
        evidence = payload["evidence"]
        tracked = set(git("ls-files").splitlines())
        ignored_patterns = GITIGNORE_PATH.read_text(encoding="utf-8")

        self.assertEqual(evidence["verificationMode"], "local-only")
        self.assertFalse(evidence["commitGeneratedOutputs"])
        self.assertNotIn(".github/workflows/orche-stage0-baseline.yml", tracked)
        self.assertNotIn(".github/workflows/_orche_pr2_review2.yml", tracked)
        self.assertNotIn(".github/workflows/_orche_pr2_verify2.yml", tracked)
        self.assertNotIn(".github/workflows/_orche_pr2_verify3.yml", tracked)
        self.assertIn("/.github/workflows/_orche_pr2_verify*.yml", ignored_patterns)
        self.assertIn("/.github/workflows/_orche_pr2_review*.yml", ignored_patterns)

        for name in evidence["requiredGeneratedOutputs"]:
            self.assertNotIn(f"baseline/orchestrarium-v1/{name}", tracked)

    def test_readme_repeats_pin_isolation_differential_and_publication_gates(self) -> None:
        readme = README_PATH.read_text(encoding="utf-8")
        self.assertIn(EXPECTED_COMMIT, readme)
        self.assertIn(EXPECTED_TREE, readme)
        self.assertIn("Source branch at capture time: `main`", readme)
        self.assertNotIn("pull request #3", readme.lower())
        self.assertIn("does **not** use GitHub Actions", readme)
        self.assertIn("cat-file blob", readme)
        self.assertIn('git -C "$BASELINE_ROOT" rev-parse HEAD', readme)
        self.assertIn("status --porcelain=v1 --untracked-files=all", readme)
        self.assertIn('USERPROFILE="$lane_root/home"', readme)
        self.assertIn("compare_validator", readme)
        self.assertIn("--volatile-pattern", readme)
        self.assertIn('rm -f "$OUTPUT_ROOT/baseline.xml"', readme)
        self.assertIn('test -f "$OUTPUT_ROOT/candidate.xml"', readme)
        for marker in VALIDATOR_MARKERS:
            self.assertIn(marker, readme)
        self.assertIn("scripts/check-publication-gate.py", readme)
        self.assertIn("$knowledge-archivist", readme)
        self.assertLess(
            readme.index("$knowledge-archivist"),
            readme.index("git push origin refs/tags/"),
        )


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "baseline" / "orchestrarium-v1"
PIN = BASELINE / "baseline-pin.json"
README = BASELINE / "README.md"
EXPECTED_COMMIT = "ce2052fb773576fd6e3206c2a7e21e01852d556b"
EXPECTED_TREE = "04dccf4575f17c9c5533474d2e0fd1503bfeceb7"
TOOLS = {
    "inventoryGenerator": "build_inventory.py",
    "targetEffectGenerator": "build_target_effect_baseline.py",
    "capabilityComparator": "compare_capability_baseline.py",
    "pytestComparator": "compare_pytest_baseline.py",
    "commandComparator": "compare_command_baseline.py",
    "stage0Runtime": "stage0_runtime.py",
    "stage0Evidence": "stage0_evidence.py",
    "stage0Orchestrator": "stage0_orchestrator.py",
    "stage0Verifier": "verify_stage0.py",
}


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
            f"git {' '.join(args)} failed\n{result.stdout}\n{result.stderr}"
        )
    return result.stdout.strip()


class BaselinePinTests(unittest.TestCase):
    def test_pin_identity_and_complete_frozen_tooling(self) -> None:
        payload = json.loads(PIN.read_text(encoding="utf-8"))
        self.assertEqual(payload["schemaVersion"], 6)
        self.assertEqual(payload["baseline"]["commitSha"], EXPECTED_COMMIT)
        self.assertEqual(payload["baseline"]["treeSha"], EXPECTED_TREE)
        self.assertEqual(set(payload["tooling"]), set(TOOLS))
        self.assertEqual(
            payload["toolingAnchor"]["kind"], "reviewed-tree-frozen-paths"
        )
        for key, name in TOOLS.items():
            record = payload["tooling"][key]
            frozen = BASELINE / "tooling" / name
            source = ROOT / "scripts" / "baseline" / name
            self.assertEqual(frozen.read_bytes(), source.read_bytes(), name)
            self.assertEqual(
                record["path"], f"baseline/orchestrarium-v1/tooling/{name}"
            )
            self.assertEqual(record["sourcePath"], f"scripts/baseline/{name}")
            self.assertEqual(
                record["materialization"], "git-cat-file-reviewed-tree-blob"
            )
            self.assertEqual(
                git("hash-object", str(frozen.relative_to(ROOT))),
                record["gitBlobSha"],
            )

    def test_local_only_evidence_has_one_machine_readable_output_root(self) -> None:
        payload = json.loads(PIN.read_text(encoding="utf-8"))
        evidence = payload["evidence"]
        self.assertEqual(evidence["verificationMode"], "local-only")
        self.assertFalse(evidence["commitGeneratedOutputs"])
        self.assertEqual(
            evidence["generatedOutputDirectory"],
            ".scratch/orche-stage0/reviewed-runs",
        )
        self.assertIn(
            "reports/capability-comparison.json",
            evidence["requiredGeneratedOutputs"],
        )
        self.assertIn(
            "reports/pytest-comparison.json", evidence["requiredGeneratedOutputs"]
        )

    def test_readme_bootstrap_and_runtime_contract_are_hardened(self) -> None:
        text = README.read_text(encoding="utf-8")
        for marker in (
            "set -euo pipefail",
            "env -i",
            "python -I",
            "git cat-file blob",
            "materialize_bootstrap_tool stage0Runtime stage0_runtime.py",
            "materialize_bootstrap_tool stage0Evidence stage0_evidence.py",
            "materialize_bootstrap_tool stage0Orchestrator stage0_orchestrator.py",
            "materialize_bootstrap_tool stage0Verifier verify_stage0.py",
            "assert_canonical_external",
            "GIT_NO_REPLACE_OBJECTS=1",
            "--no-replace-objects",
            "--preserve-failed-evidence",
            "trap cleanup_bootstrap EXIT",
            "complete trusted-tree membership",
            "Git mode, and Git object type",
            "## Terms and Abbreviations",
        ):
            self.assertIn(marker, text)
        self.assertNotIn('PATH="$PATH"', text)
        self.assertNotIn("rm -rf", text)
        self.assertLess(
            text.index('assert_canonical_external "$VERIFIER_PYTHON"'),
            text.index("PIN_JSON="),
        )

    def test_dispositions_are_exact_and_scoped(self) -> None:
        dispositions = json.loads(
            (BASELINE / "reviewed-dispositions.json").read_text()
        )
        self.assertEqual(dispositions["scope"], "ORCHE-IMPL-000")
        self.assertEqual(dispositions["baselineRef"], EXPECTED_COMMIT)
        paths = [entry["path"] for entry in dispositions["entries"]]
        self.assertEqual(len(paths), len(set(paths)))
        self.assertIn("baseline/orchestrarium-v1/reviewed-dispositions.json", paths)
        self.assertIn("scripts/baseline/verify_stage0.py", paths)
        self.assertIn("tests/test_orche_capability_baseline.py", paths)
        for entry in dispositions["entries"]:
            self.assertIn(entry["change"], {"added", "modified", "removed"})
            self.assertTrue(entry["reason"])
            self.assertTrue(entry["contractIds"])

    def test_no_disposable_tmp_placeholder_is_tracked(self) -> None:
        tracked = set(git("ls-files").splitlines())
        self.assertNotIn(".tmp/test-noop", tracked)

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux Stage 0 bootstrap")
    def test_bootstrap_rejects_invalid_review_ref_with_operational_exit_two(self) -> None:
        text = README.read_text(encoding="utf-8")
        start = text.index("```bash") + len("```bash\n")
        end = text.index("\n```", start)
        script = text[start:end] + "\n"
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            baseline = root / "baseline"
            candidate = root / "candidate"
            baseline.mkdir()
            candidate.mkdir()
            replacements = {
                "BASELINE_ROOT": str(baseline),
                "CANDIDATE_ROOT": str(candidate),
                "REVIEWED_REF": "not-a-full-object-id",
                "VERIFIER_PYTHON": str(Path(shutil.which("python3") or shutil.which("python") or "python").resolve()),
                "VERIFIER_GIT": str(Path(shutil.which("git") or "git").resolve()),
                "VERIFIER_BASH": str(Path(shutil.which("bash") or "bash").resolve()),
            }
            for key, value in replacements.items():
                script = re.sub(
                    rf"(?m)^{key}=.*$",
                    f"{key}={value!r}",
                    script,
                    count=1,
                )
            path = root / "bootstrap.sh"
            path.write_text(script, encoding="utf-8")
            result = subprocess.run(
                [str(Path(shutil.which("bash") or "bash").resolve()), str(path)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("REVIEWED_REF", result.stderr)
        self.assertNotIn("exit 1", script)
        self.assertNotIn("return 1", script)

    def test_no_stage0_github_actions_workflow_is_tracked(self) -> None:
        tracked = set(git("ls-files").splitlines())
        self.assertFalse(
            any(path.startswith(".github/workflows/orche-stage0") for path in tracked)
        )
        self.assertFalse(any("_orche_pr2_" in path for path in tracked))


if __name__ == "__main__":
    unittest.main()

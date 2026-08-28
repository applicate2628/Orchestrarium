#!/usr/bin/env python3
"""Regression coverage for the final Stage 0 automated-review findings."""
from __future__ import annotations

import hashlib
import json
import os
import py_compile
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "baseline" / "orchestrarium-v1" / "README.md"
FROZEN = ROOT / "baseline" / "orchestrarium-v1" / "tooling" / "build_inventory.py"


def run(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


class FinalReviewRegressions(unittest.TestCase):
    @unittest.skipIf(os.name == "nt", "Bash guard contract")
    def test_clean_guard_rejects_ignored_importable_bytecode(self) -> None:
        text = README.read_text(encoding="utf-8")
        guard = text.split("# BEGIN ORCHE_CLEAN_WORKTREE_GUARD", 1)[1].split(
            "# END ORCHE_CLEAN_WORKTREE_GUARD", 1
        )[0]
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            run("git", "init", "-q", cwd=repo)
            run("git", "config", "user.name", "Orche Test", cwd=repo)
            run("git", "config", "user.email", "orche@example.invalid", cwd=repo)
            (repo / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
            module = repo / "tracked_module.py"
            module.write_text("VALUE = 1\n", encoding="utf-8")
            run("git", "add", ".", cwd=repo)
            run("git", "commit", "-qm", "base", cwd=repo)
            py_compile.compile(os.fspath(module), doraise=True)
            result = subprocess.run(
                ["bash", "-c", "VERIFIER_GIT=git\n" + guard + '\nassert_clean_worktree "$1"', "bash", os.fspath(repo)],
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("BLOCKED: ignored executable or test inputs", result.stderr)
            self.assertIn("__pycache__/", result.stderr.replace("\\", "/"))

    def test_frozen_generator_identifies_itself_in_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            run("git", "init", "-q", cwd=repo)
            run("git", "config", "user.name", "Orche Test", cwd=repo)
            run("git", "config", "user.email", "orche@example.invalid", cwd=repo)
            (repo / "tracked.txt").write_text("tracked\n", encoding="utf-8")
            run("git", "add", ".", cwd=repo)
            run("git", "commit", "-qm", "baseline", cwd=repo)
            output = repo / ".scratch" / "baseline"
            result = run(
                sys.executable,
                os.fspath(FROZEN),
                "--repo-root",
                os.fspath(repo),
                "--repository",
                "example/orche",
                "--ref",
                "HEAD",
                "--output-dir",
                os.fspath(output),
                cwd=repo,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            manifest = json.loads((output / "baseline-manifest.json").read_text(encoding="utf-8"))
            content = FROZEN.read_bytes()
            blob = hashlib.sha1(f"blob {len(content)}\0".encode("ascii") + content).hexdigest()
            self.assertEqual(
                manifest["generator"],
                {
                    "command": "python baseline/orchestrarium-v1/tooling/build_inventory.py",
                    "deterministic": True,
                    "gitBlobSha": blob,
                    "materialization": "git-cat-file-reviewed-tree-blob",
                    "path": "baseline/orchestrarium-v1/tooling/build_inventory.py",
                    "runtimeMutation": False,
                    "sourcePath": "scripts/baseline/build_inventory.py",
                },
            )


if __name__ == "__main__":
    unittest.main()

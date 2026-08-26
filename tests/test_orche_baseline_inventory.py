#!/usr/bin/env python3
"""Regression tests for the Stage 0 baseline inventory generator."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "baseline" / "build_inventory.py"


def run(*args: str, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [*args],
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"command failed ({result.returncode}): {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class BaselineInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name) / "repo"
        self.repo.mkdir()
        run("git", "init", "-q", cwd=self.repo)
        run("git", "config", "user.name", "Orche Test", cwd=self.repo)
        run("git", "config", "user.email", "orche-test@example.invalid", cwd=self.repo)

        write(self.repo / "AGENTS.md", "# Governance\n")
        write(self.repo / "RELEASE_NOTES.md", "# Release Notes\n")
        write(self.repo / "docs" / "guide.md", "# Guide\n")
        write(
            self.repo / "src.codex" / "skills" / "architect" / "SKILL.md",
            "---\nname: architect\n---\n",
        )
        write(
            self.repo / "src.claude" / "commands" / "agents-test.md",
            "# Test command\n",
        )
        write(
            self.repo / "src.qwen" / "commands" / "agents" / "help.md",
            "# Agent command help\n",
        )
        write(self.repo / "scripts" / "check.py", "print('ok')\n")
        write(self.repo / "tests" / "test_alpha.py", "def test_alpha():\n    assert True\n")
        write(self.repo / "tests" / "fixtures" / "data.json", '{"ok": true}\n')
        run("git", "add", ".", cwd=self.repo)
        run("git", "commit", "-qm", "baseline", cwd=self.repo)
        self.baseline = run("git", "rev-parse", "HEAD", cwd=self.repo).stdout.strip()

        # A later commit must not leak into an inventory generated for the baseline ref.
        write(self.repo / "later.txt", "later\n")
        run("git", "add", "later.txt", cwd=self.repo)
        run("git", "commit", "-qm", "later", cwd=self.repo)

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def invoke(self, output_dir: Path, *extra: str, check: bool = True) -> subprocess.CompletedProcess[str]:
        return run(
            sys.executable,
            os.fspath(SCRIPT),
            "--repo-root",
            os.fspath(self.repo),
            "--repository",
            "example/orche",
            "--ref",
            self.baseline,
            "--output-dir",
            os.fspath(output_dir),
            *extra,
            check=check,
        )

    def test_inventory_covers_exact_requested_tree_and_classifies_surfaces(self) -> None:
        output = self.repo / ".scratch" / "baseline"
        self.invoke(output)

        capability = json.loads((output / "capability-inventory.json").read_text(encoding="utf-8"))
        test_inventory = json.loads((output / "test-inventory.json").read_text(encoding="utf-8"))
        manifest = json.loads((output / "baseline-manifest.json").read_text(encoding="utf-8"))

        paths = [entry["path"] for entry in capability["entries"]]
        self.assertEqual(paths, sorted(paths))
        self.assertEqual(len(paths), 9)
        self.assertNotIn("later.txt", paths)
        self.assertEqual(capability["baseline"]["commitSha"], self.baseline)
        self.assertEqual(manifest["baseline"]["commitSha"], self.baseline)

        by_path = {entry["path"]: entry for entry in capability["entries"]}
        self.assertIn("governance", by_path["AGENTS.md"]["surfaces"])
        self.assertEqual(by_path["RELEASE_NOTES.md"]["primarySurface"], "release-log")
        self.assertIn("skill", by_path["src.codex/skills/architect/SKILL.md"]["surfaces"])
        self.assertIn("command", by_path["src.claude/commands/agents-test.md"]["surfaces"])
        nested_command = by_path["src.qwen/commands/agents/help.md"]
        self.assertIn("agent", nested_command["surfaces"])
        self.assertIn("command", nested_command["surfaces"])
        self.assertEqual(nested_command["primarySurface"], "command")
        self.assertIn("script", by_path["scripts/check.py"]["surfaces"])
        self.assertIn("test", by_path["tests/test_alpha.py"]["surfaces"])

        test_paths = [entry["path"] for entry in test_inventory["entries"]]
        self.assertEqual(test_paths, ["tests/fixtures/data.json", "tests/test_alpha.py"])
        self.assertEqual(
            {entry["disposition"] for entry in test_inventory["entries"]},
            {"retainedAs"},
        )

    def test_default_output_stays_under_repo_scratch(self) -> None:
        result = run(
            sys.executable,
            os.fspath(SCRIPT),
            "--repo-root",
            os.fspath(self.repo),
            "--repository",
            "example/orche",
            "--ref",
            self.baseline,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = self.repo / ".scratch" / "orche-stage0" / "orchestrarium-v1"
        self.assertTrue((expected / "capability-inventory.json").is_file())
        self.assertFalse(
            (self.repo / "baseline" / "orchestrarium-v1" / "capability-inventory.json").exists()
        )

    def test_output_is_deterministic_and_check_mode_detects_drift(self) -> None:
        output = self.repo / ".scratch" / "baseline"
        self.invoke(output)
        first = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.iterdir())
        }

        self.invoke(output)
        second = {
            path.name: hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(output.iterdir())
        }
        self.assertEqual(first, second)
        for generated in sorted(output.iterdir()):
            if generated.suffix in {".md", ".json"}:
                for line_number, line in enumerate(
                    generated.read_text(encoding="utf-8").splitlines(), start=1
                ):
                    self.assertEqual(
                        line,
                        line.rstrip(" \t"),
                        f"trailing whitespace in {generated.name}:{line_number}",
                    )

        check_ok = self.invoke(output, "--check", check=False)
        self.assertEqual(check_ok.returncode, 0, check_ok.stderr)

        summary = output / "summary.md"
        summary.write_text(summary.read_text(encoding="utf-8") + "drift\n", encoding="utf-8")
        check_bad = self.invoke(output, "--check", check=False)
        self.assertEqual(check_bad.returncode, 1)
        self.assertIn("DRIFT", check_bad.stdout + check_bad.stderr)


if __name__ == "__main__":
    unittest.main()

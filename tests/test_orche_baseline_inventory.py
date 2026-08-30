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
SCRIPT = ROOT / "scripts" / "baseline" / "build_inventory.py"
REAL_GIT = Path(shutil.which("git") or "git").resolve()
SPEC = importlib.util.spec_from_file_location("orche_build_inventory", SCRIPT)
assert SPEC and SPEC.loader
SCRIPT_MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SCRIPT_MODULE)


def run(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class BaselineInventoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name) / "repo"
        self.repo.mkdir()
        for args in (("init", "-q"), ("config", "user.name", "Test"), ("config", "user.email", "t@example.invalid")):
            self.assertEqual(run(os.fspath(REAL_GIT), *args, cwd=self.repo).returncode, 0)
        write(self.repo / "AGENTS.md", "# Governance\n")
        write(self.repo / "RELEASE_NOTES.md", "# Release Notes\n")
        write(self.repo / "tests" / "test_alpha.py", "def test_alpha():\n    assert True\n")
        body = "# Method\n\nShared body.\n"
        write(self.repo / "src.codex" / "skills" / "demo" / "SKILL.md", f"---\nname: codex-demo\n---\n{body}")
        write(self.repo / "src.claude" / "skills" / "demo" / "SKILL.md", f"---\nname: claude-demo\n---\r\n{body.replace(chr(10), chr(13)+chr(10))}")
        self.assertEqual(run(os.fspath(REAL_GIT), "add", ".", cwd=self.repo).returncode, 0)
        self.assertEqual(run(os.fspath(REAL_GIT), "commit", "-qm", "baseline", cwd=self.repo).returncode, 0)
        self.ref = run(os.fspath(REAL_GIT), "rev-parse", "HEAD", cwd=self.repo).stdout.strip()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def invoke(self, output: Path, *extra: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return run(
            sys.executable,
            os.fspath(SCRIPT),
            "--repo-root", os.fspath(self.repo),
            "--repository", "example/orche",
            "--ref", self.ref,
            "--git-executable", os.fspath(REAL_GIT),
            "--output-dir", os.fspath(output),
            *extra,
            env=env,
        )

    def test_inventory_uses_normalized_skill_bodies(self) -> None:
        output = self.repo / ".scratch" / "inventory"
        result = self.invoke(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads((output / "capability-inventory.json").read_text())
        skills = [entry for entry in payload["entries"] if "skill" in entry["surfaces"]]
        self.assertEqual(len(skills), 2)
        self.assertEqual({entry["skillBodySha256"] for entry in skills}, {skills[0]["skillBodySha256"]})
        self.assertEqual({entry["skillBodySizeBytes"] for entry in skills}, {len("# Method\n\nShared body.\n".encode())})
        self.assertEqual(payload["schemaVersion"], 2)

    def test_selected_git_is_not_resolved_from_path(self) -> None:
        fake = Path(self.temp.name) / "fake"
        fake.mkdir()
        marker = fake / "invoked"
        script = fake / "git"
        script.write_text(f"#!/bin/sh\ntouch '{marker}'\nexit 99\n")
        script.chmod(0o755)
        env = {**os.environ, "PATH": os.fspath(fake)}
        result = self.invoke(self.repo / ".scratch" / "selected-git", env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(marker.exists())

    def test_frozen_provenance_is_recorded_separately(self) -> None:
        output = self.repo / ".scratch" / "frozen"
        blob = "a" * 40
        result = self.invoke(
            output,
            "--generator-path", "baseline/orchestrarium-v1/tooling/build_inventory.py",
            "--generator-blob-sha", blob,
            "--generator-materialization", "git-cat-file-reviewed-tree-blob",
            "--generator-source-path", "scripts/baseline/build_inventory.py",
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        generator = json.loads((output / "baseline-manifest.json").read_text())["generator"]
        self.assertEqual(generator["path"], "baseline/orchestrarium-v1/tooling/build_inventory.py")
        self.assertEqual(generator["gitBlobSha"], blob)
        self.assertEqual(generator["sourcePath"], "scripts/baseline/build_inventory.py")

    def test_git_path_percent_encoding_is_injective_and_reversible(self) -> None:
        samples = (
            b"tests/plain.py",
            b"tests/literal-%FF.py",
            b"tests/raw-\xff.py",
            b"tests/line-\n-break.py",
            b"tests/tab-\t-name.py",
        )
        encoded = [SCRIPT_MODULE._encode_git_path(sample) for sample in samples]
        self.assertEqual(len(encoded), len(set(encoded)))
        self.assertEqual(
            [SCRIPT_MODULE._decode_git_path(value) for value in encoded],
            list(samples),
        )
        self.assertEqual(
            SCRIPT_MODULE._encode_git_path(b"tests/literal-%FF.py"),
            "tests/literal-%25FF.py",
        )

    @unittest.skipIf(os.name != "posix", "raw Git path bytes require POSIX")
    def test_non_utf8_git_path_is_json_safe_and_reversible(self) -> None:
        raw_relative = b"tests/nonutf8-\xff.py"
        raw_absolute = os.fsencode(self.repo) + b"/" + raw_relative
        descriptor = os.open(raw_absolute, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(b"def test_nonutf8():\n    assert True\n")
        add = subprocess.run(
            [os.fsencode(REAL_GIT), b"add", b"--", raw_relative],
            cwd=os.fsencode(self.repo),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        self.assertEqual(add.returncode, 0, add.stderr)
        self.assertEqual(run(os.fspath(REAL_GIT), "commit", "-qm", "raw path", cwd=self.repo).returncode, 0)
        self.ref = run(os.fspath(REAL_GIT), "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        output = self.repo / ".scratch" / "raw-path"
        result = self.invoke(output)
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads((output / "capability-inventory.json").read_text(encoding="utf-8"))
        entry = next(item for item in payload["entries"] if "nonutf8" in item["path"] )
        self.assertEqual(entry["path"], "tests/nonutf8-%FF.py")
        self.assertEqual(entry["pathEncoding"], "git-path-percent-v1")
        self.assertEqual(SCRIPT_MODULE._decode_git_path(entry["path"]), raw_relative)

    def test_malformed_frontmatter_fails_operationally(self) -> None:
        write(self.repo / "bad" / "skills" / "x" / "SKILL.md", "---\nname: broken\n# no close\n")
        self.assertEqual(run(os.fspath(REAL_GIT), "add", ".", cwd=self.repo).returncode, 0)
        self.assertEqual(run(os.fspath(REAL_GIT), "commit", "-qm", "bad", cwd=self.repo).returncode, 0)
        self.ref = run(os.fspath(REAL_GIT), "rev-parse", "HEAD", cwd=self.repo).stdout.strip()
        result = self.invoke(self.repo / ".scratch" / "bad")
        self.assertEqual(result.returncode, 2)
        self.assertIn("unterminated leading YAML frontmatter", result.stderr)
        self.assertNotIn("Traceback", result.stderr)

    def test_check_mode_reserves_exit_one_for_drift(self) -> None:
        output = self.repo / ".scratch" / "check"
        self.assertEqual(self.invoke(output).returncode, 0)
        self.assertEqual(self.invoke(output, "--check").returncode, 0)
        (output / "summary.md").write_text("drift\n")
        self.assertEqual(self.invoke(output, "--check").returncode, 1)
        invalid = run(
            sys.executable, os.fspath(SCRIPT),
            "--repo-root", os.fspath(self.repo),
            "--ref", "missing",
            "--git-executable", os.fspath(REAL_GIT),
            "--output-dir", os.fspath(output),
            "--check",
        )
        self.assertEqual(invalid.returncode, 2)


if __name__ == "__main__":
    unittest.main()

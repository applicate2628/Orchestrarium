"""Synthetic post-copy structure receiving, not provenance or race acceptance."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import tempfile
import unittest
from unittest import mock

from synthetic_bundle_support import synthetic_notice_root


ROOT = Path(__file__).resolve().parents[1]


def snapshot(root):
    """Independent inventory preserving empty directories and stored link text."""
    result = {}
    for directory, names, files in os.walk(root, followlinks=False):
        for name in sorted(names + files):
            path = Path(directory) / name
            metadata = path.lstat()
            key = path.relative_to(root).as_posix()
            if stat.S_ISLNK(metadata.st_mode):
                value = ["link", os.readlink(path)]
            elif stat.S_ISDIR(metadata.st_mode):
                value = ["directory"]
            else:
                value = ["file", hashlib.sha256(path.read_bytes()).hexdigest(),
                         bool(metadata.st_mode & 0o111)]
            result[key] = value
    return result


class BundleStructureReceivingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(
            prefix="bundle-structure-", dir=os.environ.get("ORCHE_TEST_TMPDIR"))
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        spec = importlib.util.spec_from_file_location(
            "structure_test_builder", ROOT / "scripts/distribution/build.py")
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        self.source = self.base / "source"
        self.source.mkdir()
        directory_inputs = {"scripts", "src.codex", "adapters", "shared",
                            "references-codex", "docs", "assets/branding"}
        for name in self.builder.APP_INPUTS:
            path = self.source / name
            if name in directory_inputs:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic application; never executed\n")
        distribution = self.source / "scripts/distribution"
        distribution.mkdir()
        for name in ("build.py", "launch.py"):
            shutil.copy2(ROOT / "scripts/distribution" / name, distribution / name)
        (self.source / "scripts/universal_hooks_manifest.py").write_text(
            "def shared_hook_payload(source): return []\n"
            "def validate_hook_payload(source, payload): return None\n",
            encoding="utf-8")
        self.runtime = self.base / "runtime"
        self.runtime.mkdir()
        self.target = "windows-x64" if os.name == "nt" else "linux-x64"
        interpreter = self.runtime / self.builder.TARGETS[self.target]
        interpreter.parent.mkdir(parents=True, exist_ok=True)
        interpreter.write_bytes(b"fake interpreter; never executed\n")
        self.notices = distribution / "notices"
        self.notice_leaf = synthetic_notice_root(self.source, self.target)
        self.notice_leaf.mkdir(parents=True)
        for root in (self.runtime, self.notice_leaf):
            for name in ("empty-a", "empty-b"):
                (root / name).mkdir()
            for name in ("payload-a", "payload-b"):
                (root / name).write_bytes(b"identical synthetic payload\n")
                (root / name).chmod(0o644)
            if os.name == "posix":
                (root / "executable").write_bytes(b"synthetic; never executed\n")
                (root / "executable").chmod(0o755)
                (root / "file-link").symlink_to("payload-a")
                (root / "directory-link").symlink_to("empty-a", target_is_directory=True)
        self.data = {"schemaVersion": 2, "target": self.target, "runtimeProfile": self.builder.RUNTIME_PROFILE,
                     "runtime": snapshot(self.runtime), "notices": snapshot(self.notices)}
        self.record = self.base / "record.json"
        self.record.write_bytes(json.dumps(self.data, indent=2).encode() + b"\n")
        self.output = self.base / "bundle"
        self.before = snapshot(self.source), snapshot(self.runtime), self.record.read_bytes()

    def assemble(self):
        return self.builder.build(self.source, self.runtime, self.output,
                                  target=self.target, release="development",
                                  runtime_evidence=self.record)

    def assert_inputs_unchanged(self):
        self.assertEqual(self.before,
                         (snapshot(self.source), snapshot(self.runtime), self.record.read_bytes()))

    def test_complete_structure_is_preserved(self):
        self.assemble()
        self.assertEqual(snapshot(self.output / "python"), self.data["runtime"])
        self.assertEqual(snapshot(self.output / "app/scripts/distribution/notices"),
                         self.data["notices"])
        self.assertEqual((self.output / "runtime-evidence.json").read_bytes(), self.before[2])
        manifest = json.loads((self.output / "bundle.json").read_bytes())
        self.assertEqual(manifest["runtimeEvidenceSha256"], hashlib.sha256(self.before[2]).hexdigest())
        self.assert_inputs_unchanged()

    def refuse(self, section, mutation):
        original_validate = self.builder._validate_tree
        injected = []

        def validate(path, boundary, **kwargs):
            if path == self.output:
                self.assertFalse(injected)
                copied = (self.output / "python" if section == "runtime" else
                          self.output / "app/scripts/distribution/notices")
                # The copied structure must be correct before this controlled fault.
                self.assertEqual(snapshot(copied), self.data[section])
                leaf = copied if section == "runtime" else copied / self.notice_leaf.relative_to(self.notices)
                mutation(leaf)
                injected.append(section)
            return original_validate(path, boundary, **kwargs)

        with mock.patch.object(self.builder, "_validate_tree", side_effect=validate), \
             mock.patch.object(self.builder, "_verify_runtime_evidence",
                               wraps=self.builder._verify_runtime_evidence) as verify:
            with self.assertRaisesRegex(ValueError, "does not match|do not match"):
                self.assemble()
        self.assertEqual(injected, [section])
        self.assertEqual(verify.call_count, 2)
        self.assertEqual(verify.call_args.args[:2],
                         (self.output / "python", self.output / "app/scripts/distribution/notices"))
        self.assertTrue(self.output.is_dir())
        self.assertFalse((self.output / "runtime-evidence.json").exists())
        self.assertFalse((self.output / "bundle.json").exists())
        self.assert_inputs_unchanged()


def missing_empty(root):
    # Keep the independent link-target fixture valid so final evidence owns refusal.
    (root / "empty-b").rmdir()


def extra_empty(root):
    (root / "extra-empty").mkdir()


def flipped_executable(root):
    (root / "payload-a").chmod(0o755)


def retarget_file_link(root):
    (root / "file-link").unlink()
    (root / "file-link").symlink_to("payload-b")


def retarget_directory_link(root):
    (root / "directory-link").unlink()
    (root / "directory-link").symlink_to("empty-b", target_is_directory=True)


def install_case(section, mutation, posix_only=False):
    def case(self):
        self.refuse(section, mutation)
    case.__name__ = f"test_{section}_{mutation.__name__}_refused_after_copy"
    if posix_only:
        case = unittest.skipUnless(os.name == "posix", "requires native POSIX mode/link semantics")(case)
    setattr(BundleStructureReceivingTests, case.__name__, case)


for _section in ("runtime", "notices"):
    for _mutation in (missing_empty, extra_empty):
        install_case(_section, _mutation)
    for _mutation in (flipped_executable, retarget_file_link, retarget_directory_link):
        install_case(_section, _mutation, posix_only=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)

"""Post-copy runtime/notice evidence must be received before bundle publication.

Only synthetic byte payloads are used. The fake hook manifest exposes no hooks;
the copied fake interpreter and installer are never executed.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from synthetic_bundle_support import synthetic_notice_root, synthetic_record

ROOT = Path(__file__).resolve().parents[1]


class BundleCopyReceivingTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="bundle-copy-receiving-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        spec = importlib.util.spec_from_file_location(
            "bundle_copy_receiving", ROOT / "scripts/distribution/build.py"
        )
        self.builder = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.builder)
        self.source = self.root / "source"
        self.source.mkdir()
        directories = {"scripts", "src.codex", "adapters", "shared",
                       "references-codex", "docs", "assets/branding"}
        for name in self.builder.APP_INPUTS:
            path = self.source / name
            if name in directories:
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"Synthetic source, never executed.\n")
        (self.source / "scripts/universal_hooks_manifest.py").write_text(
            "def shared_hook_payload(source):\n"
            "    return []\n"
            "def validate_hook_payload(source, payload):\n"
            "    assert payload == []\n",
            encoding="utf-8",
        )
        notices = self.source / "scripts/distribution/notices"
        selected = synthetic_notice_root(self.source, "linux-x64")
        selected.mkdir(parents=True)
        (selected / "LICENSE").write_bytes(b"Synthetic notice, not legal evidence.\n")
        (self.source / "scripts/distribution/launch.py").write_bytes(
            b"# Synthetic launcher, never executed.\n"
        )
        self.runtime = self.root / "runtime"
        (self.runtime / "bin").mkdir(parents=True)
        (self.runtime / "bin/python3").write_bytes(b"Synthetic interpreter, never executed.\n")
        self.record = self.root / "record.json"
        self.evidence = synthetic_record(self.builder, self.runtime, notices, "linux-x64")
        self.record.write_text(json.dumps(self.evidence), encoding="utf-8")
        self.record_bytes = self.record.read_bytes()
        self.source_before = self.builder._payload_inventory(self.source)
        self.runtime_before = self.builder._payload_inventory(self.runtime)
        self.output = self.root / "bundle"

    def assemble(self):
        return self.builder.build(
            self.source, self.runtime, self.output,
            target="linux-x64", release="development", runtime_evidence=self.record,
        )

    def assert_inputs_unchanged(self):
        self.assertEqual(self.builder._payload_inventory(self.source), self.source_before)
        self.assertEqual(self.builder._payload_inventory(self.runtime), self.runtime_before)
        self.assertEqual(self.record.read_bytes(), self.record_bytes)

    def test_unchanged_copy_receives_record_and_manifest(self):
        self.assertEqual(self.assemble(), self.output)
        self.assertEqual(self.builder._payload_inventory(self.output / "python"),
                         self.evidence["runtime"])
        self.assertEqual(self.builder._payload_inventory(
            self.output / "app/scripts/distribution/notices"), self.evidence["notices"])
        self.assertEqual((self.output / "runtime-evidence.json").read_bytes(),
                         self.record_bytes)
        manifest = json.loads((self.output / "bundle.json").read_bytes())
        self.assertEqual(manifest["runtimeEvidenceSha256"],
                         hashlib.sha256(self.record_bytes).hexdigest())
        self.assert_inputs_unchanged()

    def assert_bad_copy_refused(self, section, corruption):
        relative = ("python/bin/python3" if section == "runtime"
                    else "app/scripts/distribution/notices/python-build-standalone/linux-x64-cp315/LICENSE")
        selected = self.output / relative
        original_copy = self.builder._copy_leaf
        effects = []
        verifications = []
        original_verify = self.builder._verify_runtime_evidence

        def receive(runtime, notices, data, **kwargs):
            verifications.append((Path(runtime), Path(notices)))
            return original_verify(runtime, notices, data, **kwargs)

        def copy_with_fault(source, destination):
            result = original_copy(source, destination)
            destination = Path(destination)
            if destination == selected:
                effects.append(destination)
                if corruption == "changed":
                    destination.write_bytes(b"Synthetic copy fault.\n")
                elif corruption == "missing":
                    destination.unlink()
                elif corruption == "extra":
                    (destination.parent / "unexpected-member").write_bytes(b"Synthetic extra.\n")
                elif corruption == "extra-unselected":
                    (destination.parents[2] / "unexpected-member").write_bytes(b"Synthetic extra.\n")
                else:
                    raise AssertionError(corruption)
            return result

        message = ("Runtime payload does not match" if section == "runtime"
                   else "Runtime notices do not match")
        with patch.object(self.builder, "_copy_leaf", copy_with_fault), \
             patch.object(self.builder, "_verify_runtime_evidence", receive):
            with self.assertRaisesRegex(ValueError, message):
                self.assemble()
        self.assertEqual(effects, [selected])
        self.assertEqual(verifications, [
            (self.runtime, self.source / "scripts/distribution/notices"),
            (self.output / "python", self.output / "app/scripts/distribution/notices"),
        ])
        self.assertTrue(self.output.is_dir())
        self.assertFalse((self.output / "bundle.json").exists())
        self.assertFalse((self.output / "runtime-evidence.json").exists())
        self.assert_inputs_unchanged()

    def test_changed_runtime_copy_refused(self):
        self.assert_bad_copy_refused("runtime", "changed")

    def test_missing_runtime_copy_refused(self):
        self.assert_bad_copy_refused("runtime", "missing")

    def test_extra_runtime_copy_refused(self):
        self.assert_bad_copy_refused("runtime", "extra")

    def test_changed_notice_copy_refused(self):
        self.assert_bad_copy_refused("notices", "changed")

    def test_missing_notice_copy_refused(self):
        self.assert_bad_copy_refused("notices", "missing")

    def test_extra_notice_copy_refused(self):
        self.assert_bad_copy_refused("notices", "extra")

    def test_unselected_notice_added_to_output_is_refused(self):
        self.assert_bad_copy_refused("notices", "extra-unselected")


if __name__ == "__main__":
    unittest.main(verbosity=2)

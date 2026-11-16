"""Source-layout and memory-only runtime evidence checks for pre-SDK distribution."""
import importlib.util
import sys
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch
from contextlib import redirect_stderr
import io

ROOT = Path(__file__).resolve().parents[1]

def load(name):
    spec = importlib.util.spec_from_file_location("presdk_" + name,
        ROOT / "scripts/distribution" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class PreSdkDistributionTests(unittest.TestCase):
    def setUp(self):
        self.builder = load("build")
        self.launcher = load("launch")

    def test_current_factory_role_manifest_is_valid(self):
        with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
            installer = __import__("production_installer")
        manifest = installer._source_codex_role_manifest(ROOT, ROOT / "src.codex/agents")
        self.assertTrue(manifest["roles"])

    def test_factory_role_byte_drift_is_still_refused(self):
        with patch.object(sys, "path", [str(ROOT / "scripts"), *sys.path]):
            installer = __import__("production_installer")
        original = installer._file_sha256
        def changed_role(path):
            return "0" * 64 if Path(path).suffix == ".toml" else original(path)
        with patch.object(installer, "_file_sha256", side_effect=changed_role):
            with self.assertRaisesRegex(ValueError, "role digest"):
                installer._source_codex_role_manifest(ROOT, ROOT / "src.codex/agents")

    def test_selected_application_inputs_exist_in_current_layout(self):
        for name in self.builder.APP_INPUTS:
            with self.subTest(input=name):
                self.assertFalse(Path(name).is_absolute())
                self.assertTrue((ROOT / name).exists())
        selected = set(self.builder.APP_INPUTS)
        self.assertTrue({"install.py", "scripts", "src.codex", "src.claude",
                         "references-codex", "references-claude", "shared"} <= selected)
        self.assertFalse({"adapters", "assets/branding"} & selected)

    def test_qualified_evidence_bytes_are_preserved(self):
        evidence = {"schemaVersion": 1, "target": "windows-x64",
                    "runtime": {"python.exe": ["file", "a" * 64, False]},
                    "notices": {"LICENSE": ["file", "b" * 64, False]}}
        raw = json.dumps(evidence, indent=2).encode() + b"\r\n"
        path = SimpleNamespace(read_bytes=Mock(return_value=raw))
        self.assertEqual(self.builder._read_runtime_evidence(path, "windows-x64"), (raw, evidence))
        with self.assertRaises(ValueError):
            self.builder._read_runtime_evidence(path, "linux-x64")

    def test_runtime_and_notice_inventory_both_remain_required(self):
        runtime, notices = object(), Path("notices")
        evidence = {"runtime": {"r": ["directory"]}, "notices": {"n": ["directory"]}}
        with patch.object(self.builder, "_payload_inventory", side_effect=[
            evidence["runtime"], evidence["notices"]]) as inventory:
            self.builder._verify_runtime_evidence(runtime, notices, evidence)
            self.assertEqual(inventory.call_count, 2)
        for observed in (({}, evidence["notices"]), (evidence["runtime"], {})):
            with self.subTest(observed=observed), patch.object(
                    self.builder, "_payload_inventory", side_effect=observed):
                with self.assertRaises(ValueError):
                    self.builder._verify_runtime_evidence(runtime, notices, evidence)

    def test_duplicate_evidence_fields_are_refused(self):
        path = SimpleNamespace(read_bytes=lambda: b'{"schemaVersion":1,"schemaVersion":1}')
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            self.builder._read_runtime_evidence(path, "windows-x64")

    def test_sdk_only_list_clients_is_not_an_apply_retention_exemption(self):
        with patch.object(self.launcher, "resolve_launch",
                          return_value=(Path("python"), Path("install.py"))), patch.object(
                self.launcher, "_exec_child") as child, redirect_stderr(io.StringIO()):
            self.assertEqual(self.launcher.main(["--list-clients"]), 2)
            child.assert_not_called()

    def test_explicit_permanent_runtime_still_dispatches_existing_installer(self):
        with patch.object(self.launcher, "resolve_launch",
                          return_value=(Path("python"), Path("install.py"))), patch.object(
                self.launcher, "_exec_child", return_value=0) as child:
            self.assertEqual(self.launcher.main(["--permanent-runtime", "--dry-run"]), 0)
            self.assertEqual(child.call_args.args[1], ["python", "-I", "install.py", "--dry-run"])

if __name__ == "__main__":
    unittest.main()

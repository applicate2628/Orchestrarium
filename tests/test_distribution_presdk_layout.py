"""Source-layout and memory-only runtime evidence checks for the SDK distribution."""
import importlib.util
import ast
import sys
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
import tempfile
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

class SdkDistributionTests(unittest.TestCase):
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
        self.assertTrue({"install.py", "scripts", "src.codex", "adapters", "assets/branding",
                         "references-codex", "shared"} <= selected)
        self.assertFalse({"src.claude", "references-claude"} & selected)

    def test_qualified_evidence_bytes_are_preserved(self):
        evidence = {"schemaVersion": 2, "target": "windows-x64",
                    "runtimeProfile": "cpython-stdlib-only",
                    "runtime": {"python.exe": ["file", "a" * 64, False]},
                    "notices": {"LICENSE": ["file", "b" * 64, False]}}
        raw = json.dumps(evidence, indent=2).encode() + b"\r\n"
        path = SimpleNamespace(read_bytes=Mock(return_value=raw))
        self.assertEqual(self.builder._read_runtime_evidence(path, "windows-x64"), (raw, evidence))
        with self.assertRaises(ValueError):
            self.builder._read_runtime_evidence(path, "linux-x64")

    def test_runtime_and_notice_inventory_both_remain_required(self):
        runtime, notices = object(), Path("notices")
        evidence = {"target": "linux-x64", "runtime": {"r": ["directory"]},
                    "notices": {"n": ["directory"]}}
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

    def _bundle_inputs(self, root):
        source, runtime, output = (root / name for name in ("source", "runtime", "output"))
        for name in self.builder.APP_INPUTS:
            path = source / name
            if path.suffix in {".py", ".toml", ".md"} or path.name == "LICENSE":
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("fixture")
            else:
                path.mkdir(parents=True, exist_ok=True)
        dist = source / "scripts/distribution"
        dist.mkdir()
        for name in ("build.py", "launch.py"):
            (dist / name).write_bytes((ROOT / "scripts/distribution" / name).read_bytes())
        for name in ("README.md", "runtime-evidence.md", "historical-assembly.md"):
            (dist / name).write_text("fixture")
        histories = dist / "locks"
        histories.mkdir()
        (histories / "old.txt").write_text("historical input")
        notices = dist / "notices"
        selected = notices / "python-build-standalone/linux-x64-cp315"
        selected.mkdir(parents=True)
        (selected / "LICENSE.txt").write_text("qualified notice")
        other_target = selected.with_name("windows-x64-cp315")
        other_target.mkdir()
        (other_target / "LICENSE.txt").write_text("unselected notice")
        historical = notices / "historical-dependency"
        historical.mkdir()
        (historical / "LICENSE.txt").write_text("historical notice")
        interpreter = runtime / "bin/python3"
        interpreter.parent.mkdir(parents=True)
        interpreter.write_text("synthetic interpreter")
        backend = runtime / "lib/python3.15/lib-dynload/_dbm.cpython-315-x86_64-linux-gnu.so"
        backend.parent.mkdir(parents=True)
        backend.write_text("independently admitted standard library backend")
        return source, runtime, output, notices, backend

    def _profile_record(self, runtime, notices, path):
        evidence = {"schemaVersion": 2, "target": "linux-x64",
                    "runtimeProfile": "cpython-stdlib-only",
                    "runtime": self.builder._payload_inventory(runtime),
                    "notices": self.builder._payload_inventory(
                        notices, self.builder._notice_selection(notices, "linux-x64")
                    )}
        raw = json.dumps(evidence, indent=2).encode() + b"\r\n"
        path.write_bytes(raw)
        return raw

    def test_bundle_retains_exact_standard_library_and_only_qualified_notices(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, runtime, output, notices, backend = self._bundle_inputs(root)
            evidence = root / "evidence.json"
            raw = self._profile_record(runtime, notices, evidence)
            self.builder.build(source, runtime, output, target="linux-x64",
                               release="development", runtime_evidence=evidence)
            self.assertTrue((output / "python" / backend.relative_to(runtime)).is_file())
            packaged = output / "app/scripts/distribution"
            self.assertFalse((packaged / "locks").exists())
            self.assertFalse((packaged / "runtime-evidence.md").exists())
            self.assertFalse((packaged / "historical-assembly.md").exists())
            self.assertFalse((packaged / "notices/python-build-standalone/windows-x64-cp315").exists())
            self.assertFalse((packaged / "notices/historical-dependency").exists())
            self.assertTrue((packaged / "notices/python-build-standalone/linux-x64-cp315/LICENSE.txt").is_file())
            self.assertEqual((output / "runtime-evidence.json").read_bytes(), raw)
            with patch.object(self.launcher, "current_target", return_value="linux-x64"):
                self.assertEqual(self.launcher.resolve_launch(output, output / "python/bin/python3"),
                                 (output / "python/bin/python3", output / "app/install.py"))
                retained = root / "retained"
                self.assertEqual(self.launcher.retain_bundle(output, retained),
                                 (retained / "python/bin/python3", retained / "launch.py"))
                self.assertEqual((retained / "runtime-evidence.json").read_bytes(), raw)

    def test_third_party_runtime_is_refused_before_output_even_with_matching_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source, runtime, output, notices, _ = self._bundle_inputs(root)
            packages = runtime / "lib/python3.15/site-packages"
            packages.mkdir()
            (packages / "fixture.py").write_text("ordinary third-party fixture")
            evidence = root / "evidence.json"
            self._profile_record(runtime, notices, evidence)
            with self.assertRaisesRegex(ValueError, "third-party"):
                self.builder.build(source, runtime, output, target="linux-x64",
                                   release="development", runtime_evidence=evidence)
            self.assertFalse(output.exists())

    def test_package_metadata_and_linked_package_location_are_refused(self):
        for mode in ("path extension", "package metadata", "linked package location"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source, runtime, output, notices, _ = self._bundle_inputs(root)
                if mode == "path extension":
                    (runtime / "extension.pth").write_text("local-python")
                elif mode == "package metadata":
                    (runtime / "fixture-1.0.dist-info").mkdir()
                else:
                    (runtime / "alias-target").mkdir()
                    try:
                        (runtime / "site-packages").symlink_to("alias-target", target_is_directory=True)
                    except (NotImplementedError, OSError):
                        continue  # Other profile cases still run without symlink privilege.
                evidence = root / "evidence.json"
                self._profile_record(runtime, notices, evidence)
                # Windows rejects symlinks as reparse points before the runtime
                # profile check. POSIX reaches the linked-package-location check.
                expected = ("Reparse points are not bundle inputs"
                            if mode == "linked package location" and sys.platform == "win32"
                            else "third-party")
                with self.assertRaisesRegex(ValueError, expected):
                    self.builder.build(source, runtime, output, target="linux-x64",
                                       release="development", runtime_evidence=evidence)
                self.assertFalse(output.exists())

    def test_old_record_and_inventory_drift_are_refused_before_output(self):
        for mode, expected in (
            ("old schema", "standard-library"),
            ("runtime drift", "Runtime payload"),
            ("notice drift", "Runtime notices"),
        ):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                source, runtime, output, notices, backend = self._bundle_inputs(root)
                evidence = root / "evidence.json"
                self._profile_record(runtime, notices, evidence)
                if mode == "old schema":
                    previous = json.loads(evidence.read_bytes())
                    previous["schemaVersion"] = 1
                    del previous["runtimeProfile"]
                    evidence.write_text(json.dumps(previous))
                elif mode == "runtime drift":
                    backend.write_text("different bytes")
                else:
                    (notices / "python-build-standalone/linux-x64-cp315/LICENSE.txt").write_text("different notice")
                with self.assertRaisesRegex(ValueError, expected):
                    self.builder.build(source, runtime, output, target="linux-x64",
                                       release="development", runtime_evidence=evidence)
                self.assertFalse(output.exists())

    def test_new_launcher_does_not_accept_old_unprofiled_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "bundle.json").write_text(json.dumps({
                "schemaVersion": 2, "product": "Orche", "release": "old",
                "target": "linux-x64", "python": "python/bin/python3", "entry": "app/install.py",
                "runtimeEvidence": "runtime-evidence.json", "runtimeEvidenceSha256": "unused",
            }))
            with patch.object(self.launcher, "current_target", return_value="linux-x64"):
                with self.assertRaisesRegex(ValueError, "bundle manifest"):
                    self.launcher._manifest(root)

    def test_list_clients_needs_no_apply_retention(self):
        with patch.object(self.launcher, "resolve_launch",
                          return_value=(Path("python"), Path("install.py"))), patch.object(
                self.launcher, "_exec_child", return_value=0) as child, redirect_stderr(io.StringIO()):
            self.assertEqual(self.launcher.main(["--list-clients"]), 0)
            child.assert_called_once()

    def test_explicit_permanent_runtime_still_dispatches_existing_installer(self):
        with patch.object(self.launcher, "resolve_launch",
                          return_value=(Path("python"), Path("install.py"))), patch.object(
                self.launcher, "_exec_child", return_value=0) as child:
            self.assertEqual(self.launcher.main(["--permanent-runtime", "--dry-run"]), 0)
            self.assertEqual(child.call_args.args[1], ["python", "-I", "-B", "install.py", "--dry-run"])

class RootInstallerDispatchTests(unittest.TestCase):
    def test_production_dispatch_inherits_caller_directory_and_preserves_arguments(self):
        tree = ast.parse((ROOT / "install.py").read_bytes())
        dispatch = next(node for node in tree.body
                        if isinstance(node, ast.FunctionDef) and node.name == "_run_production")
        code = compile(ast.fix_missing_locations(ast.Module(
            body=ast.parse("from __future__ import annotations").body + [dispatch],
            type_ignores=[])), str(ROOT / "install.py"), "exec")
        for no_bytecode in (False, True):
            for provider in ("codex", "claude", "antigravity"):
                for arguments in ([], ["--target", "relative project"], ["--global"],
                              ["--no-hypothesis-hook", "--dry-run"]):
                    with self.subTest(provider=provider, arguments=arguments, no_bytecode=no_bytecode):
                        runner = Mock(return_value=SimpleNamespace(returncode=23))
                        scope = {"ROOT": ROOT, "sys": SimpleNamespace(
                                     executable=sys.executable, dont_write_bytecode=no_bytecode),
                                 "subprocess": SimpleNamespace(run=runner)}
                        exec(code, scope)
                        forwarded = list(arguments)
                        self.assertEqual(scope["_run_production"](provider, forwarded), 23)
                        runner.assert_called_once_with([
                            sys.executable, *(["-B"] if no_bytecode else []),
                            str(ROOT / "scripts" / "install-client.py"), "--client", provider, *arguments])
                        self.assertEqual(forwarded, arguments)

if __name__ == "__main__":
    unittest.main()

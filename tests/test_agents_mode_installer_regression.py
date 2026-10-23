import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch


def _isolated_validator():
    path = Path(__file__).resolve().parents[1] / "scripts" / "validate-agents-mode-installers.py"
    spec = importlib.util.spec_from_file_location("agents_mode_fixture_cleanup_test", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.load_json = lambda _path: {}
    module.run_installer = lambda *_args: None
    module.run_python_codex_global_installer = lambda *_args: None
    module.validate_overlay = lambda *_args, **_kwargs: None
    module.validate_codex_native_role_install = lambda *_args: None
    return module


class AgentsModeInstallerRegressionTest(unittest.TestCase):
    @unittest.skipUnless(os.name == "nt", "Windows ReadOnly unlink behavior")
    def test_owned_readonly_file_is_removed_with_its_fixture(self) -> None:
        validator = _isolated_validator()
        fixture_id = uuid.UUID("66666666-6666-4666-8666-666666666666")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owned = root / ".scratch" / "agents-mode-installer-regression" / fixture_id.hex
            created = False

            def seed_readonly(_root, _case, relative_target):
                nonlocal created
                if created:
                    return
                created = True
                readonly = root / relative_target / ".codex/.tmp/plugins-clone/.git/objects/pack/probe.idx"
                readonly.parent.mkdir(parents=True)
                readonly.write_bytes(b"index")
                readonly.chmod(stat.S_IREAD)
                self.assertTrue(
                    readonly.stat().st_file_attributes & stat.FILE_ATTRIBUTE_READONLY
                )

            validator.run_installer = seed_readonly
            with patch.object(validator.uuid, "uuid4", return_value=fixture_id):
                validator.run_regression(root)
            self.assertTrue(created)
            self.assertFalse(owned.exists())

    def test_owned_uuid_fixture_is_removed_without_touching_sibling(self) -> None:
        validator = _isolated_validator()
        fixture_id = uuid.UUID("11111111-1111-4111-8111-111111111111")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            parent = root / ".scratch" / "agents-mode-installer-regression"
            sibling = parent / "foreign-user-fixture"
            sibling.mkdir(parents=True)
            (sibling / "keep.txt").write_bytes(b"keep")
            with patch.object(validator.uuid, "uuid4", return_value=fixture_id):
                validator.run_regression(root)
            self.assertFalse((parent / fixture_id.hex).exists())
            self.assertEqual((sibling / "keep.txt").read_bytes(), b"keep")

    def test_owned_uuid_cleanup_failure_is_visible(self) -> None:
        validator = _isolated_validator()
        fixture_id = uuid.UUID("22222222-2222-4222-8222-222222222222")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owned = root / ".scratch" / "agents-mode-installer-regression" / fixture_id.hex
            original = shutil.rmtree
            def deny_owned(path, *args, **kwargs):
                if Path(path) == owned:
                    if kwargs.get("ignore_errors"):
                        return None
                    raise PermissionError("synthetic deletion denied")
                return original(path, *args, **kwargs)
            try:
                with patch.object(validator.uuid, "uuid4", return_value=fixture_id), patch.object(validator.shutil, "rmtree", side_effect=deny_owned):
                    with self.assertRaisesRegex(validator.InstallerRegressionError, "synthetic deletion denied") as failure:
                        validator.run_regression(root)
                self.assertIn(str(owned), str(failure.exception))
            finally:
                if owned.exists():
                    original(owned)

    def test_owned_uuid_cleanup_noop_is_not_a_pass(self) -> None:
        validator = _isolated_validator()
        fixture_id = uuid.UUID("44444444-4444-4444-8444-444444444444")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owned = root / ".scratch" / "agents-mode-installer-regression" / fixture_id.hex
            original = shutil.rmtree
            def leave_owned(path, *args, **kwargs):
                if Path(path) == owned:
                    return None
                return original(path, *args, **kwargs)
            try:
                with patch.object(validator.uuid, "uuid4", return_value=fixture_id), patch.object(validator.shutil, "rmtree", side_effect=leave_owned):
                    with self.assertRaisesRegex(validator.InstallerRegressionError, "owned UUID fixture remains after cleanup"):
                        validator.run_regression(root)
            finally:
                if owned.exists():
                    original(owned)

    def test_original_validation_failure_survives_successful_cleanup(self) -> None:
        validator = _isolated_validator()
        fixture_id = uuid.UUID("55555555-5555-4555-8555-555555555555")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owned = root / ".scratch" / "agents-mode-installer-regression" / fixture_id.hex
            def fail_validation(*_args):
                raise validator.InstallerRegressionError("original validation failure")
            validator.run_installer = fail_validation
            with patch.object(validator.uuid, "uuid4", return_value=fixture_id):
                with self.assertRaisesRegex(validator.InstallerRegressionError, "original validation failure"):
                    validator.run_regression(root)
            self.assertFalse(owned.exists())

    def test_validation_and_cleanup_failures_both_remain_visible(self) -> None:
        validator = _isolated_validator()
        fixture_id = uuid.UUID("33333333-3333-4333-8333-333333333333")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            owned = root / ".scratch" / "agents-mode-installer-regression" / fixture_id.hex
            original = shutil.rmtree
            def fail_validation(*_args):
                raise validator.InstallerRegressionError("original validation failure")
            def deny_owned(path, *args, **kwargs):
                if Path(path) == owned:
                    if kwargs.get("ignore_errors"):
                        return None
                    raise PermissionError("synthetic deletion denied")
                return original(path, *args, **kwargs)
            validator.run_installer = fail_validation
            try:
                with patch.object(validator.uuid, "uuid4", return_value=fixture_id), patch.object(validator.shutil, "rmtree", side_effect=deny_owned):
                    with self.assertRaises(validator.InstallerRegressionError) as failure:
                        validator.run_regression(root)
                self.assertIn("original validation failure", str(failure.exception))
                self.assertIn("synthetic deletion denied", str(failure.exception))
                self.assertIn(str(owned), str(failure.exception))
                self.assertIsInstance(failure.exception.__cause__, validator.InstallerRegressionError)
            finally:
                if owned.exists():
                    original(owned)

    def test_installer_regression_validator_passes(self) -> None:
        root = Path(__file__).resolve().parents[1]
        env = os.environ.copy()
        env["HOME"] = str(root)
        env["CODEX_BIN"] = str(
            root / "tests" / "fixtures" / "fake_codex_hooks_host.py"
        )
        with tempfile.TemporaryDirectory() as empty_path:
            env["PATH"] = empty_path
            result = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "validate-agents-mode-installers.py"),
                    "--root",
                    str(root),
                ],
                cwd=root,
                text=True,
                capture_output=True,
                env=env,
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("PASS: agents-mode installer regression validated", result.stdout)


if __name__ == "__main__":
    unittest.main()

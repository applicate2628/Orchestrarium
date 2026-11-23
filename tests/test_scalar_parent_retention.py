"""Implicit scalar-parent rollback qualification; caller owns fixture disposal."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "Native POSIX ownership required")
class ScalarParentRetentionTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "scalar_parent_installer", ROOT / "scripts/production_installer.py")
        self.m = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.m
        spec.loader.exec_module(self.m)
        self.root = Path(tempfile.mkdtemp(prefix="scalar-parent-"))
        self.home = self.root / "home"
        self.home.mkdir()
        self.target = self.home / "container" / "config.txt"

    def run_failure(self, inject):
        tx = self.m._InstallTransaction([], enabled=True)
        self.tx = tx
        with patch.object(self.m, "_require_transaction_disposal_backend", lambda: None):
            with tx:
                owner = self.m._CreateOnlyMutablePath(self.home, tx, dry_run=False)
                tx.transform_scalar(self.target, self.home / "missing-legacy",
                                    lambda _path: b"owned configuration", owner)
                inject()
                raise RuntimeError("injected operation failure")

    def test_external_sibling_preserved_without_blocking_owned_inverse(self):
        foreign = self.target.parent / "runtime.dat"
        with self.assertRaisesRegex(RuntimeError, "^injected operation failure$"):
            self.run_failure(lambda: foreign.write_bytes(b"external state"))
        self.assertFalse(self.target.exists())
        self.assertEqual(foreign.read_bytes(), b"external state")
        parents = [e for e in self.tx._entries if e.get("implicit_container")]
        self.assertEqual(len(parents), 1)
        self.assertEqual(parents[0].get("disposition"), "retained-external-container")
        self.assertIsNotNone(parents[0]["current_node"])

    def test_empty_parent_removed_after_owned_inverse(self):
        with self.assertRaisesRegex(RuntimeError, "^injected operation failure$"):
            self.run_failure(lambda: None)
        self.assertFalse(self.target.parent.exists())

    def assert_parent_substitution_refused(self, *, symlink):
        moved = self.home / "original-container"
        replacement = self.home / "replacement"
        replacement.mkdir()
        foreign = replacement / "foreign.txt"
        foreign.write_bytes(b"foreign replacement")
        def substitute():
            self.target.parent.rename(moved)
            if symlink:
                self.target.parent.symlink_to(replacement, target_is_directory=True)
            else:
                replacement.rename(self.target.parent)
        with self.assertRaises(self.m._InstallFailure) as caught:
            self.run_failure(substitute)
        self.assertEqual(caught.exception.stable_id, "E_ROLLBACK_SETTLEMENT_FAILED")
        actual = foreign if symlink else self.target.parent / "foreign.txt"
        self.assertEqual(actual.read_bytes(), b"foreign replacement")
        self.assertEqual((moved / "config.txt").read_bytes(), b"owned configuration")

    def test_parent_identity_substitution_refused(self):
        self.assert_parent_substitution_refused(symlink=False)

    def test_parent_symlink_substitution_refused(self):
        self.assert_parent_substitution_refused(symlink=True)

    def test_changed_owned_file_still_blocks_inverse(self):
        with self.assertRaises(self.m._InstallFailure) as caught:
            self.run_failure(lambda: self.target.write_bytes(b"external edit"))
        self.assertEqual(caught.exception.stable_id, "E_ROLLBACK_SETTLEMENT_FAILED")
        self.assertEqual(self.target.read_bytes(), b"external edit")


if __name__ == "__main__":
    unittest.main()

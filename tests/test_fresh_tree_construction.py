"""Native fresh-tree components; public POSIX admission is not enabled."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "Requires native POSIX relative construction")
class FreshTreeConstructionTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location(
            "fresh_tree_installer", ROOT / "scripts" / "production_installer.py")
        self.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.module
        spec.loader.exec_module(self.module)
        # Retain fixtures for caller-owned inspection and trash-first disposition.
        self.root = Path(tempfile.mkdtemp(prefix="fresh-tree-"))
        self.source = self.root / "source"
        (self.source / "nested").mkdir(parents=True)
        (self.source / "nested" / "data").write_bytes(b"source bytes")
        self.target = self.root / "target"
        self.storage = self.root / "staging"
        self.storage.mkdir()
        self.stack = __import__("contextlib").ExitStack()
        self.addCleanup(self.stack.close)
        # This is component qualification, not public transaction acceptance.
        self.stack.enter_context(patch.object(self.module, "_require_transaction_disposal_backend", lambda: None))
        self.stack.enter_context(patch.object(self.module.tempfile, "gettempdir", lambda: str(self.storage)))
        self.stack.enter_context(patch.object(
            self.module._InstallTransaction, "_native_publish_no_replace",
            staticmethod(lambda *args, **kwargs: False)))
        self.transaction = self.module._InstallTransaction([self.target], enabled=True)

    def create(self):
        owner = self.module._CreateOnlyMutablePath(self.root, self.transaction, dry_run=False)
        return owner.create_tree(Path("target"), self.source)

    def assert_source(self):
        self.assertEqual((self.source / "nested" / "data").read_bytes(), b"source bytes")

    def test_commit(self):
        with self.transaction:
            self.create()
            self.assertEqual((self.target / "nested" / "data").read_bytes(), b"source bytes")
            effect = self.transaction._effects[-1]
            self.assertTrue(effect.transition_order)
            self.assertEqual(effect.prepared_state, {})
            self.assertTrue(self.transaction._image_matches(self.target, effect.actual))
            self.transaction.commit()
        self.assert_source()
        self.assertEqual(list(self.storage.iterdir()), [])

    def test_late_rollback(self):
        with self.assertRaisesRegex(RuntimeError, "^late failure$"):
            with self.transaction:
                self.create()
                self.assertTrue((self.target / "nested" / "data").exists())
                raise RuntimeError("late failure")
        self.assertFalse(self.target.exists())
        self.assert_source()
        self.assertEqual(list(self.storage.iterdir()), [])

    def test_mid_construction_failure(self):
        original = self.transaction._copy_owned_file
        def fail(source, target, *args, **kwargs):
            original(source, target, *args, **kwargs)
            if self.target in target.parents:
                raise RuntimeError("partial copy")
        with patch.object(self.transaction, "_copy_owned_file", fail):
            with self.assertRaisesRegex(RuntimeError, "^partial copy$"):
                with self.transaction:
                    self.create()
        self.assertFalse(self.target.exists())
        self.assert_source()
        self.assertEqual(list(self.storage.iterdir()), [])

    def test_collision_is_preserved(self):
        self.target.mkdir()
        (self.target / "foreign").write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "COLLISION"):
            with self.transaction:
                self.create()
        self.assertEqual((self.target / "foreign").read_bytes(), b"preserve")
        self.assert_source()

    def test_publication_collision_is_preserved(self):
        def collide(*args, **kwargs):
            self.target.mkdir()
            (self.target / "foreign").write_bytes(b"preserve")
            return False
        with patch.object(self.transaction, "_native_publish_no_replace", collide):
            with self.assertRaisesRegex(RuntimeError, "ambiguous publication"):
                with self.transaction:
                    self.create()
        self.assertEqual((self.target / "foreign").read_bytes(), b"preserve")
        self.assert_source()

    def test_foreign_member_blocks_rollback(self):
        with self.assertRaises(RuntimeError):
            with self.transaction:
                self.create()
                (self.target / "foreign").write_bytes(b"preserve")
                raise RuntimeError("late failure")
        self.assertEqual((self.target / "foreign").read_bytes(), b"preserve")
        self.assertFalse(self.transaction._effects[-1].settled)
        self.assert_source()

    def test_prepared_cleanup_failure_is_not_success(self):
        dispose = self.transaction._dispose_image
        def fail(path, expected):
            if path.name.startswith(".target."):
                self.assertTrue((self.target / "nested" / "data").exists())
                raise OSError("prepared cleanup")
            return dispose(path, expected)
        with patch.object(self.transaction, "_dispose_image", fail):
            with self.assertRaises(RuntimeError) as caught:
                with self.transaction:
                    self.create()
        self.assertIn("prepared", str(caught.exception))
        self.assert_source()
        self.assertTrue(list(self.root.glob(".target.*")))
        self.assertFalse(self.target.exists())

    def test_existing_tree_still_requires_retention_capability(self):
        self.target.mkdir()
        (self.target / "old").write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "retained-object atomic capability"):
            with self.transaction:
                owner = self.module._CreateOnlyMutablePath(self.root, self.transaction, dry_run=False)
                owner.replace_exact_tree(Path("target"), self.module._tree_sha256(self.target), self.source)
        self.assertEqual((self.target / "old").read_bytes(), b"preserve")
        self.assert_source()


if __name__ == "__main__":
    unittest.main()

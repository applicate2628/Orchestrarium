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
        self.native_publish = self.module._InstallTransaction._native_publish_no_replace
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

    def replacement_fixture(self):
        # Component starts at an already-retained beforeimage, not a simulated
        # successful native rename. Both real images are sealed by the owner.
        self.target.mkdir()
        (self.target / "new").write_bytes(b"replacement")
        retained = self.root / "retained"
        retained.mkdir()
        (retained / "old").write_bytes(b"original")
        tx = self.module._InstallTransaction([], enabled=False)
        owner = self.module._CreateOnlyMutablePath(self.root, tx, dry_run=False)
        old = tx._observe(retained)
        actual = tx._observe(self.target)
        effect = self.module._DeclaredPathEffect(
            self.target, owner, tx._relocate(old, retained, self.target),
            dict(actual), retained, dict(actual), retained_state=dict(old),
            published_state=dict(actual), retention_parent=self.root,
            retention_parent_identity=owner._identity(self.root),
            transition_order=1)
        tx._effects.append(effect)
        return tx, effect, retained

    def test_replacement_inverse_disposes_owned_new_image(self):
        tx, effect, retained = self.replacement_fixture()
        result = tx._settle_effects()
        self.assertEqual(result, ([], [], ()))
        self.assertTrue(effect.settled)
        self.assertEqual((self.target / "old").read_bytes(), b"original")
        self.assertFalse((self.target / "new").exists())
        self.assertFalse(retained.exists())
        self.assertEqual(effect.restored_state, effect.actual)

    def test_replacement_inverse_preserves_foreign_new_member(self):
        tx, effect, retained = self.replacement_fixture()
        (self.target / "foreign").write_bytes(b"preserve")
        self.assertTrue(tx._settle_effects()[0])
        self.assertFalse(effect.settled)
        self.assertEqual((self.target / "foreign").read_bytes(), b"preserve")
        self.assertEqual((retained / "old").read_bytes(), b"original")

    def test_replacement_inverse_partial_disposal_is_retryable(self):
        tx, effect, retained = self.replacement_fixture()
        dispose = tx._dispose_node
        def fail_root(path, node):
            if path == self.target:
                raise OSError("partial replacement disposal")
            return dispose(path, node)
        with patch.object(tx, "_dispose_node", fail_root):
            self.assertTrue(tx._settle_effects()[0])
        self.assertFalse(effect.settled)
        self.assertFalse((self.target / "new").exists())
        self.assertEqual(set(effect.actual), {self.target})
        self.assertEqual((retained / "old").read_bytes(), b"original")
        self.assertEqual(tx._settle_effects(), ([], [], ()))
        self.assertEqual((self.target / "old").read_bytes(), b"original")

    def test_replacement_inverse_preserves_runtime_observations(self):
        from dataclasses import replace
        tx, effect, retained = self.replacement_fixture()
        effect.actual[self.target / "new"] = replace(
            effect.actual[self.target / "new"], evidence_role="runtime-observation")
        self.assertTrue(tx._settle_effects()[0])
        self.assertFalse(effect.settled)
        self.assertEqual((self.target / "new").read_bytes(), b"replacement")
        self.assertEqual((retained / "old").read_bytes(), b"original")

    def test_replacement_inverse_preserves_pending_migration(self):
        tx, effect, retained = self.replacement_fixture()
        with patch.object(tx, "_migration_dependencies", return_value=(object(),)):
            self.assertTrue(tx._settle_effects()[0])
        self.assertFalse(effect.settled)
        self.assertEqual((self.target / "new").read_bytes(), b"replacement")
        self.assertEqual((retained / "old").read_bytes(), b"original")

    def test_replacement_inverse_restore_failure_retains_original(self):
        tx, effect, retained = self.replacement_fixture()
        with patch.object(tx, "_construct_exclusive_tree", side_effect=OSError("restore failure")):
            self.assertTrue(tx._settle_effects()[0])
        self.assertFalse(effect.settled)
        self.assertFalse(self.target.exists())
        self.assertEqual(effect.actual, {})
        self.assertEqual((retained / "old").read_bytes(), b"original")
        self.assertEqual(tx._settle_effects(), ([], [], ()))
        self.assertEqual((self.target / "old").read_bytes(), b"original")

    def test_restored_inverse_retries_only_partial_backup_cleanup(self):
        tx, effect, retained = self.replacement_fixture()
        (retained / "second").write_bytes(b"second original")
        effect.retained_state = tx._observe(retained)
        effect.before = tx._relocate(effect.retained_state, retained, self.target)
        dispose = tx._dispose_node
        done = []
        def fail_after_first(path, node):
            if retained in path.parents or path == retained:
                if done:
                    raise OSError("partial retained cleanup")
                done.append(path)
            return dispose(path, node)
        with patch.object(tx, "_dispose_node", fail_after_first):
            self.assertTrue(tx._settle_effects()[0])
        self.assertTrue(done)
        self.assertFalse(done[0].exists())
        self.assertIsNotNone(effect.restored_state)
        restored = dict(effect.restored_state)
        self.assertEqual((self.target / "old").read_bytes(), b"original")
        self.assertEqual((self.target / "second").read_bytes(), b"second original")
        self.assertEqual(tx._settle_effects(), ([], [], ()))
        self.assertEqual(effect.actual, restored)
        self.assertEqual((self.target / "old").read_bytes(), b"original")
        self.assertEqual((self.target / "second").read_bytes(), b"second original")
        self.assertFalse(retained.exists())

    def test_existing_tree_still_requires_retention_capability(self):
        self.target.mkdir()
        (self.target / "old").write_bytes(b"preserve")
        with self.assertRaisesRegex(ValueError, "retained-object atomic capability"):
            with self.transaction:
                owner = self.module._CreateOnlyMutablePath(self.root, self.transaction, dry_run=False)
                owner.replace_exact_tree(Path("target"), self.module._tree_sha256(self.target), self.source)
        self.assertEqual((self.target / "old").read_bytes(), b"preserve")
        self.assert_source()


@unittest.skipUnless(os.name == "nt", "Requires native Windows regression")
class WindowsReplacementInverseTests(unittest.TestCase):
    def setUp(self):
        FreshTreeConstructionTests.setUp(self)
        self.stack.enter_context(patch.object(
            self.module._InstallTransaction, "_native_publish_no_replace",
            staticmethod(self.native_publish)))

    replacement_fixture = FreshTreeConstructionTests.replacement_fixture
    test_owned_inverse = FreshTreeConstructionTests.test_replacement_inverse_disposes_owned_new_image
    test_partial_inverse = FreshTreeConstructionTests.test_replacement_inverse_partial_disposal_is_retryable
    test_foreign_member = FreshTreeConstructionTests.test_replacement_inverse_preserves_foreign_new_member
    test_pending_migration = FreshTreeConstructionTests.test_replacement_inverse_preserves_pending_migration


if __name__ == "__main__":
    unittest.main()

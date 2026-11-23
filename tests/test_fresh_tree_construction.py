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

    def retention_fixture(self):
        self.target.mkdir()
        (self.target / "old").write_bytes(b"original")
        tx = self.module._InstallTransaction([], enabled=False)
        owner = self.module._CreateOnlyMutablePath(self.root, tx, dry_run=False)
        before = tx._observe(self.target)
        retained = self.root / "retained"
        effect = tx.arm_replacement(self.target, None, owner,
            retained_destination=retained, preserve_on_commit=True)
        return tx, effect, before, retained

    def test_reserved_retention_preserves_original_identities(self):
        tx, effect, before, retained = self.retention_fixture()
        result = tx._publish_retained(self.target, retained, effect=effect)
        self.assertEqual(result, tx._relocate(before, self.target, retained))
        self.assertFalse(self.target.exists())
        self.assertEqual((retained / "old").read_bytes(), b"original")
        self.assertIsNone(effect.reservation_state)
        tx.retained_replacement(effect, before)
        self.assertEqual(tx._settle_effects(commit=True), ([], [], ()))
        self.assertEqual((retained / "old").read_bytes(), b"original")

    def test_reserved_retention_preexisting_collision(self):
        tx, effect, before, retained = self.retention_fixture()
        retained.mkdir()
        with self.assertRaises(FileExistsError):
            tx._publish_retained(self.target, retained, effect=effect)
        self.assertTrue(tx._image_matches(self.target, before))
        self.assertTrue(retained.exists())

    def test_reserved_retention_rename_failure_cleans_only_reservation(self):
        tx, effect, before, retained = self.retention_fixture()
        with patch.object(self.module.os, "rename", side_effect=OSError("rename refused")):
            with self.assertRaisesRegex(OSError, "rename refused"):
                tx._retain_reserved_original(self.target, retained, before, effect)
        self.assertTrue(tx._image_matches(self.target, before))
        self.assertFalse(retained.exists())
        self.assertIsNone(effect.reservation_state)

    def test_reserved_retention_post_effect_error_records_move(self):
        tx, effect, before, retained = self.retention_fixture()
        rename = self.module.os.rename
        def move_then_fail(*args, **kwargs):
            rename(*args, **kwargs)
            raise OSError("after rename")
        with patch.object(self.module.os, "rename", move_then_fail):
            with self.assertRaisesRegex(OSError, "after rename"):
                tx._retain_reserved_original(self.target, retained, before, effect)
        self.assertTrue(tx._image_matches(retained, tx._relocate(before, self.target, retained)))
        self.assertFalse(self.target.exists())
        self.assertIsNone(effect.reservation_state)
        self.assertGreater(effect.transition_order, 0)

    def test_reserved_retention_preserves_changed_reservation(self):
        for replacement in (False, True):
            with self.subTest(replacement=replacement):
                # Each scenario gets independent, exclusively owned objects.
                self.root = self.root / ("changed-" + str(replacement))
                self.root.mkdir()
                self.target = self.root / "target"
                tx, effect, before, retained = self.retention_fixture()
                create = tx._create_owned_directory
                displaced = self.root / "displaced-reservation"
                def changed(path, record, **kwargs):
                    node = create(path, record, **kwargs)
                    if replacement:
                        path.rename(displaced)
                        path.mkdir()
                    (path / "foreign").write_bytes(b"preserve")
                    return node
                with patch.object(tx, "_create_owned_directory", changed):
                    with self.assertRaisesRegex(ValueError, "reservation drift"):
                        tx._publish_retained(self.target, retained, effect=effect)
                self.assertTrue(tx._image_matches(self.target, before))
                self.assertEqual((retained / "foreign").read_bytes(), b"preserve")
                # Keep the entire scenario for caller-owned trash disposition.
                self.target = self.root / "second-target"

    def test_reserved_retention_journal_error_does_not_repeat_move(self):
        tx, effect, before, retained = self.retention_fixture()
        moved = tx._moved
        calls = []
        def fail(*args, **kwargs):
            calls.append(1)
            moved(*args, **kwargs)
            raise RuntimeError("journal completion failure")
        with patch.object(tx, "_moved", fail):
            with self.assertRaisesRegex(RuntimeError, "journal completion failure"):
                tx._publish_retained(self.target, retained, effect=effect)
        self.assertEqual(calls, [1])
        self.assertIsNone(effect.reservation_state)
        self.assertTrue(tx._image_matches(retained, tx._relocate(before, self.target, retained)))

    def test_reserved_retention_parent_close_failure_preserves_move(self):
        tx, effect, before, retained = self.retention_fixture()
        bind, close = tx._bind_scalar_parent, self.module.os.close
        parents = set()
        def remember(*args, **kwargs):
            fd = bind(*args, **kwargs)
            parents.add(fd)
            return fd
        def fail_close(fd):
            close(fd)
            if fd in parents:
                parents.remove(fd)
                raise OSError("parent close failure")
        with patch.object(tx, "_bind_scalar_parent", remember), patch.object(self.module.os, "close", fail_close):
            with self.assertRaisesRegex(RuntimeError, "parent close failure"):
                tx._publish_retained(self.target, retained, effect=effect)
        self.assertIsNone(effect.reservation_state)
        self.assertTrue(tx._image_matches(retained, tx._relocate(before, self.target, retained)))

    def test_reserved_retention_cleanup_preserves_late_foreign_member(self):
        tx, effect, before, retained = self.retention_fixture()
        def fail(*args, **kwargs):
            (retained / "foreign").write_bytes(b"preserve")
            raise OSError("rename refused")
        with patch.object(self.module.os, "rename", fail):
            with self.assertRaisesRegex(OSError, "rename refused"):
                tx._retain_reserved_original(self.target, retained, before, effect)
        self.assertTrue(tx._image_matches(self.target, before))
        self.assertEqual((retained / "foreign").read_bytes(), b"preserve")
        self.assertIsNotNone(effect.reservation_state)

    def test_reserved_retention_keeps_primary_and_accounting_errors(self):
        tx, effect, before, retained = self.retention_fixture()
        rename = self.module.os.rename
        primary, accounting = OSError("after rename"), RuntimeError("accounting")
        def move_then_fail(*args, **kwargs):
            rename(*args, **kwargs)
            raise primary
        with patch.object(self.module.os, "rename", move_then_fail), patch.object(
                tx, "_moved", side_effect=accounting) as moved:
            with self.assertRaises(self.module._InstallFailure) as caught:
                tx._retain_reserved_original(self.target, retained, before, effect)
        self.assertIs(caught.exception.cause, primary)
        self.assertIs(caught.exception.members[0].cause_exception, accounting)
        self.assertEqual(moved.call_count, 1)
        self.assertTrue(tx._image_matches(retained, tx._relocate(before, self.target, retained)))

    def test_existing_tree_partial_new_construction_restores_original(self):
        self.target.mkdir()
        (self.target / "old").write_bytes(b"preserve")
        copy = self.transaction._copy_owned_file
        def fail(source, target, *args, **kwargs):
            copy(source, target, *args, **kwargs)
            if self.target in target.parents and target.name == "data":
                raise RuntimeError("partial replacement")
        with patch.object(self.transaction, "_copy_owned_file", fail):
            with self.assertRaisesRegex(RuntimeError, "^partial replacement$"):
                with self.transaction:
                    owner = self.module._CreateOnlyMutablePath(self.root, self.transaction, dry_run=False)
                    owner.replace_exact_tree(Path("target"), self.module._tree_sha256(self.target), self.source)
        self.assertEqual((self.target / "old").read_bytes(), b"preserve")
        self.assertFalse((self.target / "nested").exists())

    def test_existing_tree_retention_accounting_failure_records_beforeimage(self):
        self.target.mkdir()
        (self.target / "old").write_bytes(b"preserve")
        moved = self.transaction._moved
        def fail(*args, **kwargs):
            moved(*args, **kwargs)
            raise RuntimeError("accounting failure")
        with self.assertRaisesRegex(RuntimeError, "E_INSTALL_TRANSACTION_UNCOMMITTED"), self.transaction:
            owner = self.module._CreateOnlyMutablePath(self.root, self.transaction, dry_run=False)
            with patch.object(self.transaction, "_moved", fail):
                with self.assertRaisesRegex(RuntimeError, "accounting failure"):
                    owner.replace_exact_tree(Path("target"), self.module._tree_sha256(self.target), self.source)
            effect = self.transaction._effects[-1]
            self.assertTrue(effect.retained_state)
            self.assertEqual((effect.retained / "old").read_bytes(), b"preserve")
            self.assertFalse(effect.settled)
        self.assertEqual((self.target / "old").read_bytes(), b"preserve")

    def test_existing_tree_replacement_commits(self):
        self.target.mkdir()
        (self.target / "old").write_bytes(b"preserve")
        with self.transaction:
            owner = self.module._CreateOnlyMutablePath(self.root, self.transaction, dry_run=False)
            owner.replace_exact_tree(Path("target"), self.module._tree_sha256(self.target), self.source)
            self.transaction.commit()
        self.assertEqual((self.target / "nested" / "data").read_bytes(), b"source bytes")
        self.assertFalse((self.target / "old").exists())
        self.assert_source()

    def test_existing_tree_replacement_rolls_back(self):
        self.target.mkdir()
        (self.target / "old").write_bytes(b"preserve")
        with self.assertRaisesRegex(RuntimeError, "^late replacement$"):
            with self.transaction:
                owner = self.module._CreateOnlyMutablePath(self.root, self.transaction, dry_run=False)
                owner.replace_exact_tree(Path("target"), self.module._tree_sha256(self.target), self.source)
                self.assertTrue((self.target / "nested" / "data").exists())
                raise RuntimeError("late replacement")
        self.assertEqual((self.target / "old").read_bytes(), b"preserve")
        self.assertFalse((self.target / "nested").exists())
        self.assert_source()


    def migration_parent_fixture(self):
        from types import SimpleNamespace
        tx = self.module._InstallTransaction([], enabled=False)
        owner = self.module._CreateOnlyMutablePath(self.root, tx, dry_run=False)
        leaf = self.root / "selected-file"
        leaf.write_bytes(b"original")
        selected = tx._bind_scalar_storage(leaf)
        retention_parent = self.root / "retention"
        retention_parent.mkdir()
        retained = tx.reserve_migration_retention(owner, Path("retention"), self.root)
        record = SimpleNamespace(selection_links=selected[2], parent_path=self.root,
            leaf_path=leaf, prepared_path=self.root / "prepared", tombstone_path=retained / "original",
            retention_parent_path=retention_parent)
        return tx, record, retained

    def test_migration_guard_binds_distinct_destination_parent(self):
        tx, record, retained = self.migration_parent_fixture()
        descriptors = None
        with tx._migration_selection_guard(record, record.leaf_path, record.tombstone_path) as descriptors:
            self.assertEqual(os.fstat(descriptors[0]).st_ino, self.root.stat().st_ino)
            self.assertEqual(os.fstat(descriptors[1]).st_ino, retained.stat().st_ino)
            os.rename(record.leaf_path.name, record.tombstone_path.name,
                      src_dir_fd=descriptors[0], dst_dir_fd=descriptors[1])
        self.assertEqual(record.tombstone_path.read_bytes(), b"original")
        self.assertFalse(record.leaf_path.exists())
        for descriptor in set(descriptors):
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_migration_guard_reuses_same_parent(self):
        tx, record, _ = self.migration_parent_fixture()
        with tx._migration_selection_guard(record, record.prepared_path, record.leaf_path) as descriptors:
            self.assertEqual(descriptors[0], descriptors[1])
            self.assertEqual(os.fstat(descriptors[0]).st_ino, self.root.stat().st_ino)

    def test_migration_guard_refuses_replaced_retention_parent(self):
        tx, record, retained = self.migration_parent_fixture()
        retained.rename(retained.with_name("displaced"))
        retained.mkdir()
        with self.assertRaisesRegex(ValueError, "IDENTITY_CHANGED"):
            with tx._migration_selection_guard(record, record.leaf_path, record.tombstone_path):
                self.fail("drifted retention must not reach the move")
        self.assertEqual(record.leaf_path.read_bytes(), b"original")

    def test_migration_guard_reports_post_effect_foreign_retention(self):
        tx, record, retained = self.migration_parent_fixture()
        with self.assertRaisesRegex(ValueError, "foreign migration retention member"):
            with tx._migration_selection_guard(record, record.leaf_path, record.tombstone_path):
                (retained / "foreign").write_bytes(b"preserve")
        self.assertEqual((retained / "foreign").read_bytes(), b"preserve")


    def test_migration_guard_preserves_primary_with_retention_drift(self):
        tx, record, retained = self.migration_parent_fixture()
        primary = OSError("move failed")
        with self.assertRaises(self.module._InstallFailure) as caught:
            with tx._migration_selection_guard(record, record.leaf_path, record.tombstone_path):
                (retained / "foreign").write_bytes(b"preserve")
                raise primary
        self.assertIs(caught.exception.cause, primary)
        self.assertEqual((retained / "foreign").read_bytes(), b"preserve")

    def test_migration_guard_reports_parent_close_failure(self):
        tx, record, retained = self.migration_parent_fixture()
        close = os.close
        held = set()
        def fail_close(fd):
            close(fd)
            if fd in held:
                held.remove(fd)
                raise OSError("migration parent close")
        with patch.object(self.module.os, "close", fail_close):
            with self.assertRaisesRegex(RuntimeError, "migration parent close"):
                with tx._migration_selection_guard(record, record.leaf_path, record.tombstone_path) as descriptors:
                    held.update(descriptors)
        self.assertFalse(held)
        self.assertEqual(record.leaf_path.read_bytes(), b"original")


    def migrate_file(self, *, separate=False):
        owner = self.module._CreateOnlyMutablePath(self.root, self.transaction, dry_run=False)
        selection = self.transaction._bind_scalar_storage(self.target)
        if separate:
            (self.root / "retention").mkdir(exist_ok=True)
        owner.migrate_exact_file(Path("target"), self.module._file_sha256(self.target),
            b"replacement", selection=selection, retention_parent=Path("retention") if separate else None)
        return owner

    def test_file_reservation_migration_commit(self):
        self.target.write_bytes(b"original")
        original = self.target.stat().st_ino
        with self.transaction:
            self.migrate_file(separate=True)
            record = self.transaction._slice_a_migrated[-1]
            self.assertEqual(record.tombstone_path.stat().st_ino, original)
            self.assertIsNone(record.reservation_state)
            self.transaction.commit()
        self.assertEqual(self.target.read_bytes(), b"replacement")
        self.assertFalse(record.tombstone_path.exists())

    def test_file_reservation_migration_rollback_preserves_inode(self):
        self.target.write_bytes(b"original")
        original = self.target.stat().st_ino
        os.link(self.target, self.root / "alias")
        with self.assertRaisesRegex(RuntimeError, "^late migration$"):
            with self.transaction:
                self.migrate_file(separate=True)
                raise RuntimeError("late migration")
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assertEqual(self.target.stat().st_ino, original)
        self.assertEqual((self.root / "alias").stat().st_ino, original)

    def test_file_reservation_publication_failure_restores_inode(self):
        self.target.write_bytes(b"original")
        original = self.target.stat().st_ino
        publish = self.transaction._publish_retained
        def fail(source, target, **kwargs):
            record = kwargs.get("migration")
            if record is not None and source == record.prepared_path:
                raise OSError("new publication failed")
            return publish(source, target, **kwargs)
        with patch.object(self.transaction, "_publish_retained", fail):
            with self.assertRaisesRegex(OSError, "new publication failed"):
                with self.transaction:
                    self.migrate_file()
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assertEqual(self.target.stat().st_ino, original)


    def failed_file_reservation(self, *, foreign=False):
        self.target.write_bytes(b"original")
        self.transaction = self.module._InstallTransaction([], enabled=False)
        retain = self.transaction._retain_reserved_original
        def wrapped(*args, **kwargs):
            def fail_rename(*_args, **_kwargs):
                if foreign:
                    args[1].write_bytes(b"foreign")
                raise OSError("retention rename failed")
            with patch.object(self.module.os, "rename", fail_rename):
                return retain(*args, **kwargs)
        with patch.object(self.transaction, "_retain_reserved_original", wrapped):
            with patch.object(self.transaction, "_dispose_reservation", side_effect=OSError("reservation cleanup failed")):
                with self.assertRaises(OSError if foreign else self.module._InstallFailure):
                    self.migrate_file()
        record = self.transaction._slice_a_migrated[-1]
        self.assertIsNotNone(record.reservation_state)
        self.assertFalse(record.started)
        self.assertEqual(self.target.read_bytes(), b"original")
        return record

    def test_file_reservation_failed_cleanup_is_retryable(self):
        record = self.failed_file_reservation()
        unresolved, failures, _ = self.transaction._settle_migrated()
        self.assertEqual((unresolved, failures), ([], []))
        self.assertFalse(record.tombstone_path.exists())
        self.assertIsNone(self.transaction._slice_a_migrated[-1].reservation_state)
        self.assertEqual(self.target.read_bytes(), b"original")

    def test_file_reservation_direct_rollback_cleans_reservation(self):
        record = self.failed_file_reservation()
        owner = self.transaction._slice_a_owners[os.path.normcase(str(record.anchor_path))]
        owner.rollback_migrated(record, replacement_may_be_absent=True)
        self.assertFalse(record.tombstone_path.exists())
        self.assertEqual(self.target.read_bytes(), b"original")

    def test_file_reservation_direct_commit_does_not_claim_success(self):
        record = self.failed_file_reservation()
        owner = self.transaction._slice_a_owners[os.path.normcase(str(record.anchor_path))]
        with self.assertRaisesRegex(RuntimeError, "E_ROLLBACK_CREATED_IDENTITY_CHANGED"):
            owner.commit_migrated(record)
        self.assertFalse(record.tombstone_path.exists())
        self.assertFalse(self.transaction._slice_a_migrated[-1].settled)
        self.assertEqual(self.target.read_bytes(), b"original")

    def test_file_reservation_foreign_bytes_preserved(self):
        record = self.failed_file_reservation(foreign=True)
        unresolved, failures, _ = self.transaction._settle_migrated()
        self.assertTrue(failures)
        self.assertIn(record.tombstone_path, unresolved)
        self.assertEqual(record.tombstone_path.read_bytes(), b"foreign")
        self.assertIsNotNone(self.transaction._slice_a_migrated[-1].reservation_state)
        self.assertEqual(self.target.read_bytes(), b"original")

    def test_file_reservation_post_move_error_restores_original(self):
        self.target.write_bytes(b"original")
        original = self.target.stat().st_ino
        retain, rename = self.transaction._retain_reserved_original, os.rename
        def wrapped(*args, **kwargs):
            def after(*pos, **named):
                rename(*pos, **named)
                raise OSError("after file retention")
            with patch.object(self.module.os, "rename", after):
                return retain(*args, **kwargs)
        with patch.object(self.transaction, "_retain_reserved_original", wrapped):
            with self.assertRaisesRegex(OSError, "after file retention"):
                with self.transaction:
                    self.migrate_file()
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assertEqual(self.target.stat().st_ino, original)


    def test_file_reservation_unrelated_move_preserves_reservation_path(self):
        record = self.failed_file_reservation()
        before = self.transaction._observe(self.target)
        moved = self.root / "moved-leaf"
        os.rename(self.target, moved)
        self.transaction._moved(self.target, moved, before, None)
        current = self.transaction._slice_a_migrated[-1]
        self.assertEqual(current.leaf_path, moved)
        self.assertEqual(current.reservation_state, record.reservation_state)
        self.assertTrue(record.tombstone_path.exists())

    def test_file_reservation_wrong_direct_owner_cannot_clean(self):
        record = self.failed_file_reservation()
        other = self.root / "other-owner"
        other.mkdir()
        owner = self.module._CreateOnlyMutablePath(other, self.transaction, dry_run=False)
        for operation in (owner.rollback_migrated, owner.commit_migrated):
            with self.assertRaisesRegex(ValueError, "reservation owner"):
                operation(record)
        self.assertTrue(self.transaction._image_matches(record.tombstone_path, record.reservation_state))

    def test_file_reservation_close_failure_preserves_original(self):
        import stat
        self.target.write_bytes(b"original")
        original = self.target.stat().st_ino
        retain, close = self.transaction._retain_reserved_original, os.close
        def wrapped(*args, **kwargs):
            def fail_close(fd):
                metadata = os.fstat(fd)
                close(fd)
                if stat.S_ISREG(metadata.st_mode) and metadata.st_size == 0:
                    raise OSError("reservation descriptor close")
            with patch.object(self.module.os, "close", fail_close):
                return retain(*args, **kwargs)
        with patch.object(self.transaction, "_retain_reserved_original", wrapped):
            with self.assertRaisesRegex(RuntimeError, "reservation descriptor close"):
                with self.transaction:
                    self.migrate_file()
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assertEqual(self.target.stat().st_ino, original)


    def test_file_reservation_real_native_dispatch_commit(self):
        # Exercise actual filesystem capability detection, not an assumed directory result.
        with patch.object(self.transaction, "_native_publish_no_replace", self.native_publish):
            self.test_file_reservation_migration_commit()


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

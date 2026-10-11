"""Isolated parent-transaction mechanics; no public installer/helper execution."""
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("_installer_metadata_under_test", ROOT / "scripts/production_installer.py")
PI = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = PI
SPEC.loader.exec_module(PI)


class CopyMetadataTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="metadata-test-", dir=ROOT / ".scratch")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.temp_patch = patch.object(PI.tempfile, "tempdir", str(self.root))
        self.temp_patch.start()
        self.addCleanup(self.temp_patch.stop)
        self.target = self.root / "target"
        self.source = self.root / "source"
        self.target.write_bytes(b"same")
        self.source.write_bytes(b"same")
        os.utime(self.target, ns=(1_600_000_000_123_456_700, 1_600_000_000_223_456_700))
        os.utime(self.source, ns=(1_650_000_000_123_456_700, 1_650_000_000_223_456_700))
        self.before = self.target.stat()

    def transaction(self, paths=None):
        return PI._InstallTransaction(paths or [self.target], enabled=True, copy_paths=(self.target,))

    def owner(self, transaction):
        return PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)

    def assert_clean(self):
        self.assertFalse(list(self.root.glob("orchestrarium-install-transaction-*")))
        self.assertFalse(list(self.root.rglob(".orchestrarium-retained-*")))

    def test_equal_bytes_different_mtime_is_effect_and_restores_original_times(self):
        primary = RuntimeError("later-checkpoint")
        transaction = self.transaction()
        with self.assertRaises(RuntimeError) as caught:
            with transaction:
                original = transaction._copy_metadata[self.target].before
                self.assertEqual(original.atime_ns, self.before.st_atime_ns)
                self.owner(transaction).copy_file(Path("target"), self.source)
                self.assertEqual(self.target.stat().st_mtime_ns, self.source.stat().st_mtime_ns)
                self.assertEqual(transaction._expected[self.target], transaction._original[self.target])
                raise primary
        self.assertIs(caught.exception, primary)
        after = self.target.stat()  # Metadata-only completion check.
        self.assertEqual((after.st_atime_ns, after.st_mtime_ns),
                         (self.before.st_atime_ns, self.before.st_mtime_ns))
        self.assertEqual(self.target.read_bytes(), b"same")
        self.assert_clean()

    def test_changed_bytes_rollback_uses_original_not_backup_metadata(self):
        self.source.write_bytes(b"new payload")
        transaction = self.transaction()
        with self.assertRaisesRegex(RuntimeError, "later"):
            with transaction:
                backup = transaction._entries[0]["backup"]
                os.utime(backup, ns=(1_700_000_000_000_000_000,) * 2)
                self.owner(transaction).copy_file(Path("target"), self.source)
                raise RuntimeError("later")
        self.assertEqual(self.target.stat().st_mtime_ns, self.before.st_mtime_ns)
        self.assertEqual(self.target.read_bytes(), b"same")
        self.assert_clean()

    def test_completed_timestamp_setter_then_error_is_known_and_rolls_back(self):
        if os.name != "nt":
            self.skipTest("receiving probe uses this host's native timestamp setter")
        setter = PI._WindowsBoundNode.set_copy_times
        primary = OSError("after-times-effect")
        calls = []
        def fault(bound, atime, mtime):
            setter(bound, atime, mtime)
            calls.append(mtime)
            if len(calls) == 1:
                raise primary
        transaction = self.transaction()
        with self.assertRaises(OSError) as caught:
            with patch.object(PI._WindowsBoundNode, "set_copy_times", fault):
                with transaction:
                    self.owner(transaction).copy_file(Path("target"), self.source)
        self.assertIs(caught.exception, primary)
        self.assertEqual(self.target.stat().st_mtime_ns, self.before.st_mtime_ns)
        self.assertFalse(transaction._copy_metadata[self.target].unknown)
        self.assert_clean()

    def test_unknown_timestamp_effect_preserves_recovery_and_primary(self):
        if os.name != "nt":
            self.skipTest("native receiving probe")
        setter = PI._WindowsBoundNode.set_copy_times
        primary = OSError("partial-unproved-times")
        def fault(bound, atime, mtime):
            setter(bound, atime, mtime + 100_000)
            raise primary
        transaction = self.transaction()
        with self.assertRaises(PI._InstallFailure) as caught:
            with patch.object(PI._WindowsBoundNode, "set_copy_times", fault):
                with transaction:
                    self.owner(transaction).copy_file(Path("target"), self.source)
        self.assertTrue(transaction._copy_metadata[self.target].unknown)
        self.assertIsNotNone(caught.exception.recovery_path)
        self.assertTrue(caught.exception.recovery_path.exists())
        self.assertIs(caught.exception.cause, primary)
        self.assertNotEqual(self.target.stat().st_mtime_ns, self.before.st_mtime_ns)

    def test_foreign_mtime_preserves_target_and_safe_sibling_restores(self):
        sibling = self.root / "sibling"
        sibling.write_bytes(b"old")
        transaction = PI._InstallTransaction([self.target, sibling], enabled=True,
                                            copy_paths=(self.target, sibling))
        primary = RuntimeError("later")
        with self.assertRaises(PI._InstallFailure) as caught:
            with transaction:
                self.owner(transaction).copy_file(Path("target"), self.source)
                self.owner(transaction).copy_file(Path("sibling"), self.source)
                foreign = 1_750_000_000_000_000_000
                os.utime(self.target, ns=(foreign, foreign))
                raise primary
        self.assertIs(caught.exception.cause, primary)
        self.assertEqual(self.target.stat().st_mtime_ns, foreign)
        self.assertEqual(sibling.read_bytes(), b"old")
        self.assertTrue(caught.exception.recovery_path.exists())

    def test_incidental_atime_read_is_not_foreign_drift(self):
        transaction = self.transaction()
        with self.assertRaisesRegex(RuntimeError, "later"):
            with transaction:
                self.owner(transaction).copy_file(Path("target"), self.source)
                metadata = self.target.stat()
                os.utime(self.target, ns=(metadata.st_atime_ns + 1_000_000_000, metadata.st_mtime_ns))
                transaction._assert_copy_metadata(self.target)
                raise RuntimeError("later")
        self.assertEqual(self.target.stat().st_mtime_ns, self.before.st_mtime_ns)
        self.assert_clean()

    def test_absent_copy_leaf_rollback_removes_only_created_leaf(self):
        self.target.unlink()
        transaction = self.transaction()
        with self.assertRaisesRegex(RuntimeError, "later"):
            with transaction:
                self.owner(transaction).copy_file(Path("target"), self.source)
                raise RuntimeError("later")
        self.assertFalse(self.target.exists())
        self.assertEqual(self.source.read_bytes(), b"same")
        self.assert_clean()

    def test_commit_keeps_copy_metadata_and_has_no_recovery(self):
        transaction = self.transaction()
        with transaction:
            self.owner(transaction).copy_file(Path("target"), self.source)
            transaction.commit()
        self.assertEqual(self.target.stat().st_mtime_ns, self.source.stat().st_mtime_ns)
        self.assert_clean()

    def test_copy_into_managed_tree_composes_and_containing_inverse_runs_once(self):
        directory = self.root / "tree"
        directory.mkdir()
        self.target.rename(directory / "target")
        self.target = directory / "target"
        old_inode = self.target.stat().st_ino
        prepared = self.root / "prepared"
        prepared.mkdir()
        (prepared / "target").write_bytes(b"prepared")
        transaction = self.transaction([directory])
        owner = self.owner(transaction)
        with self.assertRaisesRegex(RuntimeError, "later"):
            with transaction:
                effect = transaction.arm_replacement(directory, prepared, owner)
                owner._replace_prepared(directory, prepared, effect=effect)
                owner.copy_file(Path("tree/target"), self.source)
                raise RuntimeError("later")
        self.assertEqual(self.target.stat().st_ino, old_inode)
        self.assertEqual(self.target.stat().st_mtime_ns, self.before.st_mtime_ns)
        self.assertEqual(self.target.read_bytes(), b"same")
        self.assertTrue(effect.settled)
        self.assert_clean()

    def test_source_readonly_final_mode_follows_timestamps_and_rollback(self):
        self.source.chmod(stat.S_IREAD)
        self.addCleanup(self.source.chmod, stat.S_IREAD | stat.S_IWRITE)
        transaction = self.transaction()
        with self.assertRaisesRegex(RuntimeError, "later"):
            with transaction:
                self.owner(transaction).copy_file(Path("target"), self.source)
                self.assertFalse(self.target.stat().st_mode & stat.S_IWRITE)
                self.assertEqual(self.target.stat().st_mtime_ns, self.source.stat().st_mtime_ns)
                raise RuntimeError("later")
        self.assertTrue(self.target.stat().st_mode & stat.S_IWRITE)
        self.assertEqual(self.target.stat().st_mtime_ns, self.before.st_mtime_ns)
        self.assert_clean()

    def test_bound_source_refuses_foreign_origin_before_read(self):
        transaction = self.transaction()
        expected = transaction._capture_node(self.source)
        foreign = self.root / "foreign"
        foreign.write_bytes(b"foreign")
        self.source.unlink()
        foreign.rename(self.source)
        with patch.object(PI.os, "read", side_effect=AssertionError("foreign read")) as read:
            with self.assertRaisesRegex(ValueError, "opened origin"):
                with transaction._copy_reference(self.source, expected):
                    raise AssertionError("unproved origin reached consumer")
        read.assert_not_called()

    def test_partial_content_failure_restores_and_keeps_same_primary(self):
        self.source.write_bytes(b"x" * (1024 * 1024 + 1))
        write = PI.os.write
        primary = OSError("second-block-failure")
        transaction = self.transaction()
        with self.assertRaises(OSError) as caught:
            with transaction:
                calls = []
                def fault(descriptor, payload):
                    calls.append(len(payload))
                    if len(calls) == 2:
                        raise primary
                    return write(descriptor, payload)
                with patch.object(PI.os, "write", fault):
                    self.owner(transaction).copy_file(Path("target"), self.source)
        self.assertIs(caught.exception, primary)
        self.assertEqual(self.target.stat().st_mtime_ns, self.before.st_mtime_ns)
        self.assertEqual(self.target.read_bytes(), b"same")
        self.assert_clean()

    def test_native_readback_reports_supported_timestamp_precision(self):
        if os.name != "nt":
            self.skipTest("Windows FILETIME receiving")
        transaction = self.transaction()
        with transaction:
            node = transaction._expected[self.target][self.target]
            participant = transaction._copy_metadata[self.target]
            desired = PI.replace(participant.before, atime_ns=participant.before.atime_ns + 73,
                                 mtime_ns=participant.before.mtime_ns + 173)
            actual = transaction._apply_copy_metadata(self.target, node, desired,
                stat.S_IMODE(node.python_identity[2]),
                lambda member, value: transaction._advance(member, {member: value}), participant)
            self.assertEqual(actual.atime_ns, desired.atime_ns // 100 * 100)
            self.assertEqual(actual.mtime_ns, desired.mtime_ns // 100 * 100)
            transaction.commit()
        self.assert_clean()

    def test_completed_mode_setter_then_error_records_prefix_and_restores(self):
        chmod = PI._InstallTransaction._chmod_owned
        self.source.chmod(stat.S_IREAD)
        self.addCleanup(self.source.chmod, stat.S_IREAD | stat.S_IWRITE)
        primary = OSError("after-mode-effect")
        calls = []
        def fault(path, before, requested, **kwargs):
            actual = chmod(path, before, requested, **kwargs)
            calls.append(actual)
            if len(calls) == 1:
                raise primary
            return actual
        transaction = self.transaction()
        with self.assertRaises(OSError) as caught:
            with patch.object(PI._InstallTransaction, "_chmod_owned", staticmethod(fault)):
                with transaction:
                    self.owner(transaction).copy_file(Path("target"), self.source)
        self.assertIs(caught.exception, primary)
        self.assertTrue(self.target.stat().st_mode & stat.S_IWRITE)
        self.assertEqual(self.target.stat().st_mtime_ns, self.before.st_mtime_ns)
        self.assert_clean()

    def test_unchanged_readonly_member_replays_access_time_without_permission_widening(self):
        self.target.chmod(stat.S_IREAD)
        self.addCleanup(self.target.chmod, stat.S_IREAD | stat.S_IWRITE)
        before = self.target.stat()
        with self.assertRaisesRegex(RuntimeError, "later"):
            with self.transaction():
                os.utime(self.target, ns=(before.st_atime_ns + 1_000_000_000, before.st_mtime_ns))
                raise RuntimeError("later")
        after = self.target.stat()
        self.assertEqual(after.st_atime_ns, before.st_atime_ns)
        self.assertFalse(after.st_mode & stat.S_IWRITE)
        self.assert_clean()

    def test_same_object_copy_retains_copy2_failure_contract(self):
        self.source.unlink()
        os.link(self.target, self.source)
        with self.assertRaises(PI.shutil.SameFileError):
            with self.transaction() as transaction:
                self.owner(transaction).copy_file(Path("target"), self.source)
        self.assertEqual(self.target.stat().st_mtime_ns, self.before.st_mtime_ns)
        self.assertEqual(self.target.read_bytes(), b"same")
        self.assert_clean()


class RetentionAndAnchorTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="retention-test-", dir=ROOT / ".scratch")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.temp_patch = patch.object(PI.tempfile, "tempdir", str(self.root))
        self.temp_patch.start()
        self.addCleanup(self.temp_patch.stop)
        self.source = self.root / "original"
        self.source.mkdir()
        (self.source / "member").write_bytes(b"original bytes")
        self.backup = self.root / "backup"
        self.inode = self.source.stat().st_ino

    def test_explicit_persistent_retention_commit_keeps_original_object(self):
        with PI._InstallTransaction([self.source, self.backup], enabled=True) as transaction:
            owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
            owner.retain_path(Path("original"), transaction._original[self.source],
                              retained_destination=self.backup, preserve_on_commit=True)
            transaction.commit()
        self.assertFalse(self.source.exists())
        self.assertEqual(self.backup.stat().st_ino, self.inode)
        self.assertEqual((self.backup / "member").read_bytes(), b"original bytes")
        self.assertEqual(transaction._remaining_recovery(), (None, [], []))
        self.assertFalse(list(self.root.glob("orchestrarium-install-transaction-*")))

    def test_persistent_retention_failure_restores_original_identity_and_backup_absence(self):
        with self.assertRaisesRegex(RuntimeError, "later"):
            with PI._InstallTransaction([self.source, self.backup], enabled=True) as transaction:
                owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                owner.retain_path(Path("original"), transaction._original[self.source],
                                  retained_destination=self.backup, preserve_on_commit=True)
                raise RuntimeError("later")
        self.assertEqual(self.source.stat().st_ino, self.inode)
        self.assertFalse(self.backup.exists())
        self.assertEqual((self.source / "member").read_bytes(), b"original bytes")

    def test_existing_persistent_backup_untouched_by_temporary_original_retention(self):
        self.backup.mkdir()
        (self.backup / "member").write_bytes(b"existing backup")
        backup_inode = self.backup.stat().st_ino
        with self.assertRaisesRegex(RuntimeError, "later"):
            with PI._InstallTransaction([self.source, self.backup], enabled=True) as transaction:
                owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                owner.retain_path(Path("original"), transaction._original[self.source])
                raise RuntimeError("later")
        self.assertEqual(self.source.stat().st_ino, self.inode)
        self.assertEqual(self.backup.stat().st_ino, backup_inode)
        self.assertEqual((self.backup / "member").read_bytes(), b"existing backup")

    def test_retention_original_authority_rejects_foreign_same_bytes(self):
        transaction = PI._InstallTransaction([], enabled=False)
        owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
        expected = transaction._observe(self.source)
        displaced = self.root / "displaced"
        self.source.rename(displaced)
        self.source.mkdir()
        (self.source / "member").write_bytes(b"original bytes")
        with self.assertRaisesRegex(ValueError, "original source"):
            owner.retain_path(Path("original"), expected)
        self.assertTrue(self.source.exists())
        self.assertTrue(displaced.exists())
        self.assertFalse(transaction._effects)

    def test_missing_anchor_suffix_uses_creator_rows_and_rolls_back(self):
        anchor = self.root / "missing" / "anchor"
        with self.assertRaisesRegex(RuntimeError, "later"):
            with PI._InstallTransaction([], enabled=True) as transaction:
                owner = PI._CreateOnlyMutablePath.bind_or_create_anchor(anchor, transaction,
                    admitted_parent=self.root, parent_state=transaction._capture_node(self.root), dry_run=False)
                self.assertEqual(owner.anchor, anchor)
                self.assertEqual(len(transaction._slice_a_created), 2)
                raise RuntimeError("later")
        self.assertFalse((self.root / "missing").exists())

    def test_missing_anchor_foreign_empty_replacement_is_preserved(self):
        anchor = self.root / "missing" / "anchor"
        primary = RuntimeError("later")
        with self.assertRaises(PI._InstallFailure) as caught:
            with PI._InstallTransaction([], enabled=True) as transaction:
                PI._CreateOnlyMutablePath.bind_or_create_anchor(anchor, transaction,
                    admitted_parent=self.root, parent_state=transaction._capture_node(self.root), dry_run=False)
                anchor.rename(self.root / "owned-displaced")
                anchor.mkdir()
                foreign_inode = anchor.stat().st_ino
                raise primary
        self.assertIs(caught.exception.cause, primary)
        self.assertEqual(anchor.stat().st_ino, foreign_inode)
        self.assertTrue((self.root / "owned-displaced").exists())

    def test_regular_retention_restores_exact_original_file(self):
        source = self.source / "member"
        inode = source.stat().st_ino
        with self.assertRaisesRegex(RuntimeError, "later"):
            with PI._InstallTransaction([source], enabled=True) as transaction:
                owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                owner.retain_path(Path("original/member"), transaction._original[source])
                raise RuntimeError("later")
        self.assertEqual(source.stat().st_ino, inode)
        self.assertEqual(source.read_bytes(), b"original bytes")

    def test_link_retention_moves_link_object_without_touching_target(self):
        link = self.root / "link"
        target = self.source / "member"
        try:
            link.symlink_to(target)
        except OSError as error:
            self.skipTest(f"synthetic link creation unsupported on current host: {error.winerror or error.errno}")
        identity = link.lstat().st_ino
        target_inode = target.stat().st_ino
        with self.assertRaisesRegex(RuntimeError, "later"):
            with PI._InstallTransaction([link], enabled=True) as transaction:
                owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                owner.retain_path(Path("link"), transaction._original[link])
                raise RuntimeError("later")
        self.assertTrue(link.is_symlink())
        self.assertEqual(link.lstat().st_ino, identity)
        self.assertEqual(target.stat().st_ino, target_inode)
        self.assertEqual(target.read_bytes(), b"original bytes")

    def test_dry_run_creates_no_retention_or_missing_anchor(self):
        transaction = PI._InstallTransaction([], enabled=False)
        owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=True)
        owner.retain_path(Path("original"), transaction._observe(self.source),
                          retained_destination=self.backup, preserve_on_commit=True)
        anchor = self.root / "missing" / "anchor"
        result = PI._CreateOnlyMutablePath.bind_or_create_anchor(anchor, transaction,
            admitted_parent=self.root, parent_state=transaction._capture_node(self.root), dry_run=True)
        self.assertIsNone(result)
        self.assertFalse(anchor.exists())
        self.assertFalse(self.backup.exists())
        self.assertTrue(self.source.exists())
        self.assertFalse(transaction._effects)
        self.assertFalse(transaction._slice_a_created)


class BytePublicationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="byte-test-", dir=ROOT / ".scratch")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.temp_patch = patch.object(PI.tempfile, "tempdir", str(self.root))
        self.temp_patch.start()
        self.addCleanup(self.temp_patch.stop)
        self.target = self.root / "target"
        self.target.write_bytes(b"original")

    def transaction(self):
        return PI._InstallTransaction([self.target], enabled=True)

    def owner(self, transaction):
        return PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)

    def assert_clean(self):
        self.assertFalse(list(self.root.glob("orchestrarium-install-transaction-*")))
        self.assertFalse(list(self.root.glob(".orchestrarium-write-*")))

    def test_inplace_bytes_keep_original_object_mode_and_exact_newlines(self):
        before = self.target.stat()
        payload = 'document\r\nβ\n'.encode()
        primary = RuntimeError("later")
        with self.assertRaises(RuntimeError) as caught:
            with self.transaction() as transaction:
                with patch.object(PI.os, "fsync", side_effect=AssertionError("unexpected fsync")):
                    self.owner(transaction).write_file(Path("target"), payload)
                self.assertEqual(self.target.stat().st_ino, before.st_ino)
                self.assertEqual(self.target.stat().st_mode, before.st_mode)
                self.assertEqual(self.target.read_bytes(), payload)
                raise primary
        self.assertIs(caught.exception, primary)
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assert_clean()

    def test_absent_inplace_bytes_retire_parent_after_leaf_inverse(self):
        target = self.root / "new-parent" / "leaf"
        primary = RuntimeError("later")
        with self.assertRaises(RuntimeError) as caught:
            with PI._InstallTransaction([target], enabled=True) as transaction:
                self.owner(transaction).write_file(Path("new-parent/leaf"), b"new")
                raise primary
        self.assertIs(caught.exception, primary)
        self.assertFalse(target.parent.exists())
        self.assert_clean()

    def test_atomic_bytes_replace_still_present_target_and_use_one_snapshot_inverse(self):
        original = self.target.stat().st_ino
        replace = PI.os.replace
        observations = []
        primary = RuntimeError("later")
        def receiving(source, target):
            observations.append((Path(target).exists(), Path(target).read_bytes()))
            replace(source, target)
        with self.assertRaises(RuntimeError) as caught:
            with self.transaction() as transaction:
                with patch.object(PI.os, "replace", receiving):
                    self.owner(transaction).replace_file_atomic(Path("target"), b'{"new":1}\r\n')
                self.assertNotEqual(self.target.stat().st_ino, original)
                self.assertEqual(self.target.read_bytes(), b'{"new":1}\r\n')
                self.assertFalse(transaction._effects)
                raise primary
        self.assertIs(caught.exception, primary)
        self.assertEqual(observations, [(True, b"original")])
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assert_clean()

    def test_atomic_exception_after_completed_replace_restores_with_same_primary(self):
        replace = PI.os.replace
        primary = OSError("after-atomic-effect")
        def after(source, target):
            replace(source, target)
            raise primary
        with self.assertRaises(OSError) as caught:
            with self.transaction() as transaction:
                with patch.object(PI.os, "replace", after):
                    self.owner(transaction).replace_file_atomic(Path("target"), b"new")
        self.assertIs(caught.exception, primary)
        self.assertEqual(self.target.read_bytes(), b"original")
        self.assert_clean()

    def test_unknown_atomic_after_effect_preserves_foreign_target_and_original_primary(self):
        replace = PI.os.replace
        primary = OSError("uncertain atomic effect")
        def after(source, target):
            replace(source, target)
            foreign = self.root / "foreign"
            foreign.write_bytes(b"foreign")
            replace(foreign, target)
            raise primary
        with self.assertRaises(PI._InstallFailure) as caught:
            with self.transaction() as transaction:
                with patch.object(PI.os, "replace", after):
                    self.owner(transaction).replace_file_atomic(Path("target"), b"planned")
        self.assertIs(caught.exception.cause, primary)
        self.assertEqual(self.target.read_bytes(), b"foreign")
        self.assertTrue(caught.exception.recovery_path.exists())
        self.assertFalse(list(self.root.glob(".orchestrarium-write-*")))

    def test_atomic_refuses_foreign_target_changed_during_preparation(self):
        transaction = self.transaction()
        prepare = transaction._prepare_payload_file
        foreign_identity = []
        def retarget(*args, **kwargs):
            result = prepare(*args, **kwargs)
            self.target.rename(self.root / "displaced")
            self.target.write_bytes(b"foreign")
            foreign_identity.append(self.target.stat().st_ino)
            return result
        with self.assertRaises(PI._InstallFailure) as caught:
            with transaction:
                with patch.object(transaction, "_prepare_payload_file", retarget):
                    self.owner(transaction).replace_file_atomic(Path("target"), b"planned")
        self.assertIn("opened origin", str(caught.exception.cause))
        self.assertEqual(self.target.stat().st_ino, foreign_identity[0])
        self.assertEqual(self.target.read_bytes(), b"foreign")
        self.assertTrue(caught.exception.recovery_path.exists())
        self.assertFalse(list(self.root.glob(".orchestrarium-write-*")))

    def test_atomic_fsync_contract_is_explicit_and_required_failure_preserves_target(self):
        primary = OSError("sync unavailable")
        with self.transaction() as transaction:
            with patch.object(PI.os, "fsync", side_effect=primary):
                self.owner(transaction).replace_file_atomic(Path("target"), b"best effort", fsync="best-effort")
            transaction.commit()
        self.assertEqual(self.target.read_bytes(), b"best effort")
        with self.assertRaises(OSError) as caught:
            with self.transaction() as transaction:
                with patch.object(PI.os, "fsync", side_effect=primary):
                    self.owner(transaction).replace_file_atomic(Path("target"), b"required", fsync="required")
        self.assertIs(caught.exception, primary)
        self.assertEqual(self.target.read_bytes(), b"best effort")
        self.assert_clean()

    def test_legacy_file_link_snapshot_keeps_write_through_selection_and_link_object(self):
        alias = self.root / "alias"
        alias.symlink_to(self.target.name)
        original = alias.lstat().st_ino
        primary = RuntimeError("later")
        with self.assertRaises(RuntimeError) as caught:
            with PI._InstallTransaction([alias], enabled=True) as transaction:
                self.assertIn(self.target, transaction.paths)
                self.owner(transaction).write_file(Path("target"), b"new")
                raise primary
        self.assertIs(caught.exception, primary)
        self.assertEqual(alias.lstat().st_ino, original)
        self.assertEqual(alias.read_bytes(), b"original")
        self.assert_clean()


class CrossOwnerRetentionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="dual-owner-test-", dir=ROOT / ".scratch")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.temp_patch = patch.object(PI.tempfile, "tempdir", str(self.root))
        self.temp_patch.start()
        self.addCleanup(self.temp_patch.stop)
        self.source_root = self.root / "projection"
        self.home = self.root / "home"
        self.source_root.mkdir()
        self.home.mkdir()
        self.source = self.source_root / "original"
        self.source.mkdir()
        (self.source / "member").write_bytes(b"original")
        self.backup = self.home / "backups" / "original"
        self.inode = self.source.stat().st_ino

    def transaction(self):
        return PI._InstallTransaction([self.source, self.backup], enabled=True)

    def owners(self, transaction):
        return (PI._CreateOnlyMutablePath(self.source_root, transaction, dry_run=False),
                PI._CreateOnlyMutablePath(self.home, transaction, dry_run=False))

    def test_cross_owner_failure_restores_source_once_and_exact_backup_absence(self):
        primary = RuntimeError("later")
        with self.assertRaises(RuntimeError) as caught:
            with self.transaction() as transaction:
                source_owner, home_owner = self.owners(transaction)
                home_owner._ensure_parent(self.backup)
                source_owner.retain_path(Path("original"), transaction._original[self.source],
                    retained_destination=self.backup, preserve_on_commit=True, retained_owner=home_owner)
                self.assertEqual(self.backup.stat().st_ino, self.inode)
                raise primary
        self.assertIs(caught.exception, primary)
        self.assertEqual(self.source.stat().st_ino, self.inode)
        self.assertFalse(self.backup.parent.exists())
        self.assertFalse(list(self.root.rglob("orchestrarium-install-transaction-*")))

    def test_cross_owner_commit_keeps_exact_durable_object(self):
        with self.transaction() as transaction:
            source_owner, home_owner = self.owners(transaction)
            home_owner._ensure_parent(self.backup)
            source_owner.retain_path(Path("original"), transaction._original[self.source],
                retained_destination=self.backup, preserve_on_commit=True, retained_owner=home_owner)
            transaction.commit()
        self.assertFalse(self.source.exists())
        self.assertEqual(self.backup.stat().st_ino, self.inode)
        self.assertEqual((self.backup / "member").read_bytes(), b"original")
        self.assertEqual(transaction._remaining_recovery(), (None, [], []))

    def test_cross_owner_wrong_transaction_refuses_before_move(self):
        with self.assertRaisesRegex(ValueError, "transaction owner"):
            with self.transaction() as transaction:
                source_owner, home_owner = self.owners(transaction)
                home_owner._ensure_parent(self.backup)
                other = PI._InstallTransaction([], enabled=False)
                wrong = PI._CreateOnlyMutablePath(self.home, other, dry_run=False)
                source_owner.retain_path(Path("original"), transaction._original[self.source],
                    retained_destination=self.backup, preserve_on_commit=True, retained_owner=wrong)
        self.assertEqual(self.source.stat().st_ino, self.inode)
        self.assertFalse(self.backup.exists())
        self.assertFalse(transaction._effects)

    def test_cross_owner_retargeted_destination_anchor_preserves_foreign_state(self):
        transaction = self.transaction()
        arm = transaction.arm_replacement
        foreign_inode = []
        def retarget(*args, **kwargs):
            result = arm(*args, **kwargs)
            self.home.rename(self.root / "displaced-home")
            self.home.mkdir()
            (self.home / "sentinel").write_bytes(b"foreign")
            foreign_inode.append(self.home.stat().st_ino)
            return result
        with self.assertRaises(PI._InstallFailure) as caught:
            with transaction:
                source_owner, home_owner = self.owners(transaction)
                home_owner._ensure_parent(self.backup)
                with patch.object(transaction, "arm_replacement", retarget):
                    source_owner.retain_path(Path("original"), transaction._original[self.source],
                        retained_destination=self.backup, preserve_on_commit=True, retained_owner=home_owner)
        self.assertEqual(self.source.stat().st_ino, self.inode)
        self.assertEqual(self.home.stat().st_ino, foreign_inode[0])
        self.assertEqual((self.home / "sentinel").read_bytes(), b"foreign")
        self.assertIn("anchor drift", str(caught.exception.cause))


class CreatedDirectorySnapshotHandoffTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="creator-handoff-", dir=ROOT / ".scratch")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.temp_patch = patch.object(PI.tempfile, "tempdir", str(self.root))
        self.temp_patch.start()
        self.addCleanup(self.temp_patch.stop)
        self.absent = self.root / "generic"
        self.primary = RuntimeError("original VERIFY failure")

    def populate(self, transaction):
        anchor = self.absent / "nested"
        PI._CreateOnlyMutablePath.bind_or_create_anchor(anchor, transaction,
            admitted_parent=self.root, parent_state=transaction._capture_node(self.root), dry_run=False)
        owner = transaction._slice_a_owners[os.path.normcase(str(self.root))]
        owner.create_file(Path("generic/nested/deeper/member"), b"managed child")
        return owner

    def test_absent_snapshot_hands_nested_owned_directories_to_creator_once(self):
        transaction = PI._InstallTransaction([self.absent], enabled=True)
        removed = []
        rollback = PI._CreateOnlyMutablePath.rollback_created
        def observe(owner, record):
            removed.append(record.leaf_path)
            return rollback(owner, record)
        with patch.object(PI._CreateOnlyMutablePath, "rollback_created", observe):
            with self.assertRaises(RuntimeError) as caught:
                with transaction:
                    self.populate(transaction)
                    raise self.primary
        self.assertIs(caught.exception, self.primary)
        self.assertFalse(self.absent.exists())
        self.assertEqual(transaction._expected[self.absent], {})
        directories = [row for row in transaction._slice_a_created if row.kind == "directory"]
        self.assertTrue(all(row.consumed for row in directories))
        self.assertEqual(len(removed), len(set(removed)))
        self.assertEqual([path for path in removed if path in {row.leaf_path for row in directories}],
                         sorted((row.leaf_path for row in directories), key=lambda path: len(path.parts), reverse=True))
        self.assertFalse(list(self.root.glob("orchestrarium-install-transaction-*")))

    def refusal_after_children_settle(self, mutate, *, preexisting=False):
        if preexisting:
            self.absent.mkdir()
        safe = self.root / "safe"
        safe.write_bytes(b"original sibling")
        transaction = PI._InstallTransaction([self.absent, safe], enabled=True)
        settle = transaction._settle_snapshots
        def at_snapshot(unresolved):
            self.assertTrue(all(effect.settled for effect in transaction._effects))
            mutate(transaction)
            return settle(unresolved)
        with patch.object(transaction, "_settle_snapshots", at_snapshot):
            with self.assertRaises(PI._InstallFailure) as caught:
                with transaction:
                    owner = self.populate(transaction)
                    owner.write_file(Path("safe"), b"changed sibling")
                    raise self.primary
        self.assertIs(caught.exception.cause, self.primary)
        self.assertTrue(self.absent.exists())
        self.assertEqual(safe.read_bytes(), b"original sibling")
        self.assertTrue(any(member.phase == "snapshot" for member in caught.exception.members))
        if caught.exception.recovery_path is not None:
            self.assertTrue(caught.exception.recovery_path.exists())
        return transaction

    def test_missing_or_duplicate_creator_proof_refuses(self):
        for degradation in ("missing", "duplicate"):
            with self.subTest(degradation=degradation):
                def mutate(transaction):
                    row = next(row for row in transaction._slice_a_created if row.leaf_path == self.absent)
                    if degradation == "missing":
                        transaction._slice_a_created.remove(row)
                    else:
                        transaction._slice_a_created.append(row)
                self.refusal_after_children_settle(mutate)
                # Each finite fixture belongs to this test, including deliberately foreign objects.
                for path in sorted(self.absent.rglob("*"), key=lambda path: len(path.parts), reverse=True):
                    path.rmdir()
                self.absent.rmdir()

    def test_wrong_parent_binding_refuses_before_any_directory_inverse(self):
        def mutate(transaction):
            transaction._slice_a_created = [PI.replace(row, parent_identity=(row.parent_identity[0],
                row.parent_identity[1] + 1, *row.parent_identity[2:])) if row.leaf_path == self.absent
                else row for row in transaction._slice_a_created]
        transaction = self.refusal_after_children_settle(mutate)
        self.assertTrue(all(not row.consumed for row in transaction._slice_a_created if row.kind == "directory"))
        self.assertTrue((self.absent / "nested/deeper").is_dir())

    def test_missing_native_creator_proof_refuses_on_native_host(self):
        def mutate(transaction):
            row = next(row for row in transaction._slice_a_created if row.leaf_path == self.absent)
            if row.native_proof is None:
                self.skipTest("current host does not supply native creator proof")
            transaction._slice_a_created = [PI.replace(record, native_proof=None)
                if record is row else record for record in transaction._slice_a_created]
        transaction = self.refusal_after_children_settle(mutate)
        self.assertTrue(all(not row.consumed for row in transaction._slice_a_created if row.kind == "directory"))

    def test_foreign_empty_replacement_is_preserved(self):
        identities = []
        def mutate(transaction):
            self.absent.rename(self.root / "displaced")
            self.absent.mkdir()
            identities.append(self.absent.stat().st_ino)
        self.refusal_after_children_settle(mutate)
        self.assertEqual(self.absent.stat().st_ino, identities[0])
        self.assertTrue((self.root / "displaced/nested/deeper").is_dir())

    def test_retargeted_parent_with_same_original_child_refuses(self):
        identities = []
        def mutate(transaction):
            original_child = self.absent / "nested"
            identities.append(original_child.stat().st_ino)
            self.absent.rename(self.root / "displaced")
            self.absent.mkdir()
            (self.root / "displaced/nested").rename(original_child)
            identities.append(self.absent.stat().st_ino)
            # Even a matching current census cannot replace the original creator proof.
            transaction._advance(self.absent, transaction._observe(self.absent))
        self.refusal_after_children_settle(mutate)
        self.assertEqual((self.absent / "nested").stat().st_ino, identities[0])
        self.assertEqual(self.absent.stat().st_ino, identities[1])
        self.assertTrue((self.absent / "nested/deeper").is_dir())

    def test_unmapped_directory_or_non_directory_residual_is_not_adopted(self):
        for kind in ("directory", "file"):
            with self.subTest(kind=kind):
                member = self.absent / "unmapped"
                def mutate(transaction):
                    if kind == "directory":
                        member.mkdir()
                    else:
                        member.write_bytes(b"foreign participant")
                    # Degraded bookkeeping must not manufacture creator authority.
                    transaction._advance(member, transaction._observe(member))
                self.refusal_after_children_settle(mutate)
                self.assertTrue(member.exists())
                for path in sorted(self.absent.rglob("*"), key=lambda path: len(path.parts), reverse=True):
                    path.rmdir() if path.is_dir() else path.unlink()
                self.absent.rmdir()

    def test_unsettled_descendant_effect_cannot_be_handed_off(self):
        def mutate(transaction):
            transaction._effects[0].settled = False  # Missing positive settlement proof.
        transaction = self.refusal_after_children_settle(mutate)
        self.assertTrue(all(not row.consumed for row in transaction._slice_a_created if row.kind == "directory"))

    def test_preexisting_snapshot_keeps_its_existing_refusal(self):
        self.refusal_after_children_settle(lambda transaction: None, preexisting=True)

    def test_reparse_residual_is_preserved_and_target_untouched(self):
        target = self.root / "target"
        target.mkdir()
        (target / "sentinel").write_bytes(b"target")
        probe = self.root / "link-probe"
        try:
            probe.symlink_to(target, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"synthetic directory link unsupported: {error.winerror or error.errno}")
        probe.unlink()
        def mutate(transaction):
            leaf = self.absent / "nested/deeper"
            leaf.rmdir()
            leaf.symlink_to(target, target_is_directory=True)
            transaction._advance(leaf, transaction._observe(leaf))
        self.refusal_after_children_settle(mutate)
        self.assertTrue((self.absent / "nested/deeper").is_symlink())
        self.assertEqual((target / "sentinel").read_bytes(), b"target")


class ExpectedImageAndTypedSettlementTests(unittest.TestCase):
    setUp = CreatedDirectorySnapshotHandoffTests.setUp
    populate = CreatedDirectorySnapshotHandoffTests.populate

    def test_after_retirement_foreign_file_refuses_without_payload_read_or_delete(self):
        if os.name != "nt":
            self.skipTest("native digest interception requires Windows")
        safe = self.root / "safe"
        safe.write_bytes(b"original sibling")
        transaction = PI._InstallTransaction([self.absent, safe], enabled=True)
        settle = transaction._settle_created
        digest = PI._WindowsBoundNode.digest
        reads = []
        deletes = []
        identities = []
        dispose = transaction._dispose_node
        def after_retirement(blocked=None, *, records=None):
            result = settle(blocked, records=records)
            if records and all(row.kind == "directory" for row in records) and result == ([], []):
                self.assertEqual(transaction._expected[self.absent], {})
                self.absent.write_bytes(b"foreign bytes must not be read")
                identities.append(self.absent.stat().st_ino)
            return result
        def native_read(bound):
            if bound.path == self.absent:
                reads.append(bound.path)
            return digest(bound)
        def native_dispose(path, expected):
            if identities and path == self.absent:
                deletes.append(path)
            return dispose(path, expected)
        with patch.object(transaction, "_settle_created", after_retirement), patch.object(PI._WindowsBoundNode, "digest", native_read), patch.object(transaction, "_dispose_node", native_dispose):
            with self.assertRaises(PI._InstallFailure) as caught:
                with transaction:
                    self.populate(transaction).write_file(Path("safe"), b"changed")
                    raise self.primary
        self.assertIs(caught.exception.cause, self.primary)
        self.assertEqual(reads, [])
        self.assertEqual(deletes, [])
        self.assertEqual(self.absent.stat().st_ino, identities[0])
        self.assertEqual(safe.read_bytes(), b"original sibling")
        self.assertIsNotNone(caught.exception.recovery_path)
        self.assertTrue(caught.exception.recovery_path.exists())

    def test_after_effect_typed_child_member_survives_handoff(self):
        safe = self.root / "safe"
        safe.write_bytes(b"original sibling")
        transaction = PI._InstallTransaction([self.absent, safe], enabled=True)
        rollback = PI._CreateOnlyMutablePath.rollback_created
        sentinel = PI._RollbackFailureMember("backup", 71, str(self.root / "secondary"),
            "E_SENTINEL_NATIVE_CLOSE", "distinct secondary cause")
        def after_effect(owner, record):
            rollback(owner, record)
            if record.kind == "directory" and record.leaf_path == self.absent / "nested/deeper":
                raise PI._InstallFailure("E_ROLLBACK_SETTLEMENT_FAILED", "creator-close", "secondary",
                                         members=(sentinel,))
        with patch.object(PI._CreateOnlyMutablePath, "rollback_created", after_effect):
            with self.assertRaises(PI._InstallFailure) as caught:
                with transaction:
                    self.populate(transaction).write_file(Path("safe"), b"changed")
                    raise self.primary
        self.assertIs(caught.exception.cause, self.primary)
        self.assertIn(sentinel, caught.exception.members)
        self.assertTrue(any(member is sentinel for member in caught.exception.members))
        self.assertFalse((self.absent / "nested/deeper").exists())
        self.assertTrue(self.absent.exists())
        self.assertEqual(safe.read_bytes(), b"original sibling")
        self.assertIsNotNone(caught.exception.recovery_path)
        self.assertTrue(caught.exception.recovery_path.exists())

    def test_nonempty_image_membership_and_origin_precede_all_payload_reads(self):
        if os.name != "nt":
            self.skipTest("native digest interception requires Windows")
        tree = self.root / "tree"
        tree.mkdir()
        known = tree / "a-known"
        known.write_bytes(b"known")
        transaction = PI._InstallTransaction([], enabled=False)
        image = transaction._observe(tree)  # Authorized original acquisition.
        self.assertTrue(transaction._image_matches(tree, image))
        unknown = tree / "z-foreign"
        unknown.write_bytes(b"foreign")
        reads = []
        digest = PI._WindowsBoundNode.digest
        def native_read(bound):
            reads.append(bound.path)
            return digest(bound)
        with patch.object(PI._WindowsBoundNode, "digest", native_read):
            self.assertFalse(transaction._image_matches(tree, image))
            self.assertEqual(reads, [])  # Even known payload waits for complete membership proof.
            unknown.unlink()
            known.rename(self.root / "displaced")
            known.write_bytes(b"known")
            foreign_identity = known.stat().st_ino
            self.assertFalse(transaction._image_matches(tree, image))
            self.assertEqual(reads, [])
        self.assertEqual(known.stat().st_ino, foreign_identity)
        self.assertTrue((self.root / "displaced").exists())

    def test_known_same_origin_content_drift_remains_visible(self):
        path = self.root / "known"
        path.write_bytes(b"before")
        transaction = PI._InstallTransaction([], enabled=False)
        image = transaction._observe(path)
        identity = path.stat().st_ino
        path.write_bytes(b"after")
        self.assertEqual(path.stat().st_ino, identity)
        self.assertFalse(transaction._image_matches(path, image))
        self.assertEqual(path.read_bytes(), b"after")

    def test_missing_expected_proof_is_distinct_from_explicit_absence(self):
        transaction = PI._InstallTransaction([], enabled=False)
        self.assertTrue(transaction._image_matches(self.absent, {}))
        for missing in (None, [], (), ""):
            with self.subTest(proof=missing):
                with self.assertRaisesRegex(ValueError, "missing expected image proof"):
                    transaction._image_matches(self.absent, missing)
        self.absent.write_bytes(b"known")
        image = transaction._observe(self.absent)
        node = image[self.absent]
        corrupt = PI.replace(node, kind="directory", data=None)
        with patch.object(PI._InstallTransaction, "_copy_reference", side_effect=AssertionError("kind not yet proved")):
            self.assertFalse(transaction._image_matches(self.absent, {self.absent: corrupt}))

    def test_foreign_reparse_origin_refuses_before_raw_reparse_read(self):
        if os.name != "nt":
            self.skipTest("native reparse interception requires Windows")
        target = self.root / "target"
        target.mkdir()
        link = self.root / "link"
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"synthetic directory link unsupported: {error.winerror or error.errno}")
        transaction = PI._InstallTransaction([], enabled=False)
        expected = transaction._observe(link)
        link.rename(self.root / "displaced-link")
        link.symlink_to(target, target_is_directory=True)
        foreign = link.lstat().st_ino
        reads = []
        reparse = PI._WindowsBoundNode.reparse_data
        def raw_read(bound):
            if bound.path == link:
                reads.append(bound.path)
            return reparse(bound)
        with patch.object(PI._WindowsBoundNode, "reparse_data", raw_read):
            self.assertFalse(transaction._image_matches(link, expected))
        self.assertEqual(reads, [])
        self.assertEqual(link.lstat().st_ino, foreign)
        self.assertTrue((self.root / "displaced-link").is_symlink())

    def test_native_io_failure_retains_original_exception(self):
        path = self.root / "known"
        path.write_bytes(b"known")
        transaction = PI._InstallTransaction([], enabled=False)
        expected = transaction._observe(path)
        primary = PermissionError("synthetic native open denied")
        with patch.object(PI._InstallTransaction, "_capture_node", side_effect=primary):
            with self.assertRaises(PermissionError) as caught:
                transaction._image_matches(path, expected)
        self.assertIs(caught.exception, primary)

    def test_typed_failure_without_members_preserves_id_cause_and_unsafe_paths(self):
        endpoint = self.root / "unsafe"
        child = PI._InstallFailure("E_NATIVE_SETTLEMENT_DETAIL", "close", "actual close cause",
                                   unresolved_paths=(endpoint,))
        paths, members = PI._InstallTransaction._settlement_failure(child, "created", 9, self.absent,
                                                                  "E_ROLLBACK_CREATED_IDENTITY_CHANGED")
        self.assertIn(endpoint, paths)
        self.assertEqual((members[0].phase, members[0].ordinal, members[0].path, members[0].stable_id, members[0].cause),
                         ("created", 9, str(self.absent), "E_NATIVE_SETTLEMENT_DETAIL", "actual close cause"))

    def test_plain_after_effect_failure_is_classified_once_at_creator(self):
        transaction = PI._InstallTransaction([self.absent], enabled=True)
        rollback = PI._CreateOnlyMutablePath.rollback_created
        leaf = self.absent / "nested/deeper"
        def after_effect(owner, record):
            rollback(owner, record)
            if record.kind == "directory" and record.leaf_path == leaf:
                raise OSError("plain secondary cause")
        with patch.object(PI._CreateOnlyMutablePath, "rollback_created", after_effect):
            with self.assertRaises(PI._InstallFailure) as caught:
                with transaction:
                    self.populate(transaction)
                    raise self.primary
        self.assertIs(caught.exception.cause, self.primary)
        classified = [member for member in caught.exception.members if member.cause == "plain secondary cause"]
        self.assertEqual(len(classified), 1)
        self.assertEqual((classified[0].phase, classified[0].ordinal, classified[0].path, classified[0].stable_id),
                         ("created", 2, str(leaf), "E_ROLLBACK_CREATED_IDENTITY_CHANGED"))
        self.assertIn(leaf, caught.exception.unresolved_paths)

    def test_typed_effect_failure_keeps_secondary_unsafe_endpoint(self):
        safe = self.root / "safe"
        safe.write_bytes(b"original sibling")
        transaction = PI._InstallTransaction([self.absent, safe], enabled=True)
        dispose = transaction._dispose_image
        endpoint = self.root / "secondary-unsafe"
        sentinel = PI._RollbackFailureMember("backup", 82, str(endpoint), "E_SECONDARY_CLOSE", "secondary")
        def after_disposal(path, expected):
            dispose(path, expected)
            if transaction._effects and path == transaction._effects[0].retained:
                raise PI._InstallFailure("E_ROLLBACK_SETTLEMENT_FAILED", "effect-close", "secondary",
                    members=(sentinel,), unresolved_paths=(endpoint,))
        with patch.object(transaction, "_dispose_image", after_disposal):
            with self.assertRaises(PI._InstallFailure) as caught:
                with transaction:
                    self.populate(transaction).write_file(Path("safe"), b"changed")
                    raise self.primary
        self.assertIs(caught.exception.cause, self.primary)
        self.assertTrue(any(member is sentinel for member in caught.exception.members))
        self.assertIn(endpoint, caught.exception.unresolved_paths)
        self.assertEqual(safe.read_bytes(), b"original sibling")

    def test_native_migration_current_role_survives_commit_and_inverse(self):
        for commit in (False, True):
            with self.subTest(commit=commit):
                path = self.root / ("native-commit" if commit else "native-rollback")
                path.write_bytes(b"stock original")
                original = path.stat().st_ino
                transaction = PI._InstallTransaction([path], enabled=True)
                def publish():
                    with transaction:
                        owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                        owner.migrate_exact_file(path.relative_to(self.root), PI.hashlib.sha256(b"stock original").hexdigest(),
                                                 b"replacement", retention_parent=Path("."))
                        self.assertEqual(path.read_bytes(), b"replacement")
                        if commit:
                            transaction.commit()
                        else:
                            raise self.primary
                if commit:
                    publish()
                    self.assertEqual(path.read_bytes(), b"replacement")
                else:
                    with self.assertRaises(RuntimeError) as caught:
                        publish()
                    self.assertIs(caught.exception, self.primary)
                    self.assertEqual(path.stat().st_ino, original)
                    self.assertEqual(path.read_bytes(), b"stock original")
                self.assertEqual(transaction._remaining_recovery(), (None, [], []))
                self.assertFalse(list(self.root.glob(".orchestrarium-migration-retention-*")))


@PI.contextmanager
def _synthetic_native_byte_lock(path):
    import ctypes
    from ctypes import wintypes
    class Overlapped(ctypes.Structure):
        _fields_ = [("internal", ctypes.c_size_t), ("internal_high", ctypes.c_size_t),
                    ("offset", wintypes.DWORD), ("offset_high", wintypes.DWORD), ("event", wintypes.HANDLE)]
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                   wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE)
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.LockFileEx.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(Overlapped))
    kernel.LockFileEx.restype = wintypes.BOOL
    kernel.UnlockFileEx.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                    wintypes.DWORD, ctypes.POINTER(Overlapped))
    kernel.UnlockFileEx.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.CreateFileW(str(path), 0xC0000000, 7, None, 3, 0, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    locked = False
    overlap = Overlapped()
    try:
        if not kernel.LockFileEx(handle, 3, 0, 0xFFFFFFFF, 0, ctypes.byref(overlap)):
            raise ctypes.WinError(ctypes.get_last_error())
        locked = True
        yield
    finally:
        try:
            if locked and not kernel.UnlockFileEx(handle, 0, 0xFFFFFFFF, 0, ctypes.byref(overlap)):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            if not kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())


class PointAndRecoverySelectionTests(unittest.TestCase):
    setUp = CreatedDirectorySnapshotHandoffTests.setUp

    def test_nonempty_bound_directory_is_point_not_empty_complete_tree(self):
        directory = self.root / "parent"
        directory.mkdir()
        (directory / "ordinary-member").write_bytes(b"member")
        transaction = PI._InstallTransaction([], enabled=False)
        point = transaction._capture_node(directory)
        with PI.ExitStack() as resources:
            transaction._bind_scalar_parent(directory, point, resources)
            transaction._assert_scalar_binding({"links": ((directory, point),)}, check_storage=False)
        self.assertFalse(transaction._image_matches(directory, {directory: point}))
        self.assertEqual((directory / "ordinary-member").read_bytes(), b"member")

    def test_native_locked_beforeimage_keeps_original_primary_and_retained_bytes(self):
        if os.name != "nt":
            self.skipTest("actual LockFileEx requires Windows")
        path = self.root / "victim"
        path.write_bytes(b"original beforeimage")
        transaction = PI._InstallTransaction([path], enabled=True)
        transaction.__enter__()
        backup = next(entry["backup"] for entry in transaction._entries if entry["path"] == path)
        PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False).write_file(Path("victim"), b"changed")
        with _synthetic_native_byte_lock(backup):
            with self.assertRaises(PI._InstallFailure) as caught:
                transaction.__exit__(RuntimeError, self.primary, None)
        self.assertIs(caught.exception.cause, self.primary)
        self.assertIsNone(caught.exception.recovery_path)  # Retained data is not verified usable while locked.
        self.assertTrue(any("33" in member.cause for member in caught.exception.members))
        self.assertIn(backup, caught.exception.unresolved_paths)
        self.assertIsNotNone(transaction._temporary)
        self.assertEqual(backup.read_bytes(), b"original beforeimage")

    def test_point_selected_link_payload_and_origin_are_preserved(self):
        first = self.root / "first"
        second = self.root / "second"
        first.mkdir()
        second.mkdir()
        (first / "member").write_bytes(b"ordinary child")
        link = self.root / "link"
        try:
            link.symlink_to(first, target_is_directory=True)
        except OSError as error:
            self.skipTest(f"synthetic selected link unsupported: {getattr(error, 'winerror', None) or error.errno}")
        transaction = PI._InstallTransaction([], enabled=False)
        expected = transaction._capture_node(link)
        self.assertTrue(transaction._point_matches(link, expected))
        self.assertFalse(transaction._point_matches(link, PI.replace(expected, data=str(second))))
        link.rename(self.root / "original-link")
        link.symlink_to(first, target_is_directory=True)
        self.assertFalse(transaction._point_matches(link, expected))
        self.assertEqual((first / "member").read_bytes(), b"ordinary child")

    def test_point_directory_origin_drift_refuses_with_complete_tree_still_strict(self):
        directory = self.root / "parent"
        directory.mkdir()
        transaction = PI._InstallTransaction([], enabled=False)
        expected = transaction._capture_node(directory)
        self.assertTrue(transaction._image_matches(directory, {directory: expected}))
        (directory / "member").write_bytes(b"foreign membership")
        self.assertTrue(transaction._point_matches(directory, expected))
        self.assertFalse(transaction._image_matches(directory, {directory: expected}))
        directory.rename(self.root / "original-parent")
        directory.mkdir()
        self.assertFalse(transaction._point_matches(directory, expected))

    def test_committed_native_lock_freezes_primary_and_prior_secondary(self):
        if os.name != "nt":
            self.skipTest("actual LockFileEx requires Windows")
        path = self.root / "victim"
        path.write_bytes(b"original beforeimage")
        transaction = PI._InstallTransaction([path], enabled=True)
        transaction.__enter__()
        backup = next(entry["backup"] for entry in transaction._entries if entry["path"] == path)
        owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
        owner.write_file(Path("victim"), b"committed bytes")
        transaction.commit()
        sentinel_path = self.root / "secondary-endpoint"
        sentinel = PI._RollbackFailureMember("migration", 43, str(sentinel_path), "E_SECONDARY_NATIVE_CLOSE", "prior secondary")
        with _synthetic_native_byte_lock(backup), patch.object(transaction, "_commit_migrated", return_value=([sentinel_path], [sentinel])):
            with self.assertRaises(PI._InstallFailure) as caught:
                transaction.__exit__(RuntimeError, self.primary, None)
        self.assertIs(caught.exception.cause, self.primary)
        self.assertTrue(any(member is sentinel for member in caught.exception.members))
        self.assertTrue(any("33" in member.cause for member in caught.exception.members))
        self.assertIn(sentinel_path, caught.exception.unresolved_paths)
        self.assertIn(backup, caught.exception.unresolved_paths)
        self.assertIsNone(caught.exception.recovery_path)
        self.assertIsNotNone(transaction._temporary)
        self.assertEqual(backup.read_bytes(), b"original beforeimage")
        self.assertEqual(path.read_bytes(), b"committed bytes")

    def test_selector_preserves_locked_temporary_candidate_then_selects_known_effect(self):
        if os.name != "nt":
            self.skipTest("actual LockFileEx requires Windows")
        victim = self.root / "victim"
        victim.write_bytes(b"snapshot beforeimage")
        original = self.root / "original"
        original.write_bytes(b"retained effect beforeimage")
        transaction = PI._InstallTransaction([victim], enabled=True)
        transaction.__enter__()
        backup = next(entry["backup"] for entry in transaction._entries if entry["path"] == victim)
        owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
        owner.retain_path(Path("original"), transaction._observe(original))
        retained = transaction._effects[0].retained
        try:
            with _synthetic_native_byte_lock(backup):
                selected, unresolved, failures = transaction._remaining_recovery()
            self.assertEqual(selected, retained)
            self.assertIn(backup, unresolved)
            self.assertTrue(any(member.path == str(backup) and "33" in member.cause for member in failures))
            self.assertEqual(backup.read_bytes(), b"snapshot beforeimage")
            self.assertEqual(retained.read_bytes(), b"retained effect beforeimage")
        finally:
            transaction.__exit__(None, None, None) if transaction.committed else self._finish_uncommitted(transaction)

    def _finish_uncommitted(self, transaction):
        try:
            transaction.__exit__(RuntimeError, self.primary, None)
        except RuntimeError as caught:
            self.assertIs(caught, self.primary)

    def test_selector_migration_role_failure_then_exact_unsettled_migration(self):
        for name in ("first", "second"):
            (self.root / name).write_bytes(b"stock original")
        transaction = PI._InstallTransaction([], enabled=True)
        transaction.__enter__()
        owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
        digest = PI.hashlib.sha256(b"stock original").hexdigest()
        for name in ("first", "second"):
            owner.migrate_exact_file(Path(name), digest, b"new", retention_parent=Path("."))
        original_record = transaction._slice_a_migrated[0]
        transaction._slice_a_migrated[0] = PI.replace(original_record, old_current=None)
        try:
            selected, unresolved, failures = transaction._remaining_recovery()
            self.assertEqual(selected, transaction._slice_a_migrated[1].tombstone_path)
            self.assertIn(original_record.tombstone_path, unresolved)
            self.assertTrue(any(member.phase == "migration" and member.ordinal == 0 for member in failures))
        finally:
            transaction._slice_a_migrated[0] = original_record
            self._finish_uncommitted(transaction)

    def test_selector_foreign_effect_mismatch_is_reported_without_adoption(self):
        path = self.root / "original"
        path.write_bytes(b"original")
        transaction = PI._InstallTransaction([], enabled=True)
        transaction.__enter__()
        owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
        owner.retain_path(Path("original"), transaction._observe(path))
        effect = transaction._effects[0]
        retained = effect.retained
        displaced = self.root / "displaced"
        retained.rename(displaced)
        retained.write_bytes(b"original")
        foreign = retained.stat().st_ino
        try:
            selected, unresolved, failures = transaction._remaining_recovery()
            self.assertIsNone(selected)
            self.assertIn(retained, unresolved)
            self.assertTrue(any(member.phase == "snapshot" and member.path == str(retained) for member in failures))
            self.assertTrue(effect.retained_state)
            self.assertEqual(retained.stat().st_ino, foreign)
            self.assertEqual(displaced.read_bytes(), b"original")
        finally:
            with self.assertRaises(PI._InstallFailure) as caught:
                transaction.__exit__(RuntimeError, self.primary, None)
            self.assertIs(caught.exception.cause, self.primary)
        self.assertEqual(retained.stat().st_ino, foreign)
        self.assertEqual(displaced.read_bytes(), b"original")


class BorrowedOpeningTests(unittest.TestCase):
    setUp = CreatedDirectorySnapshotHandoffTests.setUp

    def scalar_binding(self, transaction, logical):
        # Synthetic ordinary geometry; all actual nodes/openings/writes are native.
        parent = transaction._capture_node(self.root)
        before = transaction._capture_node(logical) if logical.exists() else None
        return logical, before, ((self.root, parent),), logical

    def test_actual_absent_scalar_creation_registers_and_checks_live_opening(self):
        path = self.root / "scalar"
        transaction = PI._InstallTransaction([path], enabled=True)
        with transaction:
            owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
            with patch.object(transaction, "_bind_scalar_storage", lambda logical: self.scalar_binding(transaction, logical)):
                transaction.transform_scalar(path, self.root / "missing-legacy", lambda _path: b"scalar payload", owner)
            transaction.commit()
        self.assertEqual(path.read_bytes(), b"scalar payload")
        self.assertEqual(transaction._remaining_recovery(), (None, [], []))

    @PI.contextmanager
    def opening(self, name="file", payload=b"payload"):
        path = self.root / name
        path.write_bytes(payload)
        transaction = PI._InstallTransaction([], enabled=False)
        original = transaction._capture_node(path)
        descriptor = os.open(path, os.O_RDWR | getattr(os, "O_BINARY", 0))
        try:
            yield transaction, path, descriptor, original
        finally:
            os.close(descriptor)

    def test_borrow_at_eof_reads_whole_expected_image_resets_and_lender_closes_once(self):
        closed = []
        close = PI.os.close
        selected = []
        def observe_close(descriptor):
            if descriptor in selected:
                closed.append(descriptor)
            return close(descriptor)
        with patch.object(PI.os, "close", observe_close):
            with self.opening() as (transaction, path, descriptor, original):
                selected.append(descriptor)
                os.lseek(descriptor, 0, os.SEEK_END)
                with patch.object(PI._InstallTransaction, "_copy_reference", side_effect=AssertionError("fresh payload opening")):
                    self.assertTrue(transaction._image_matches(path, {path: original}, borrowed_opening=(descriptor, original)))
                self.assertEqual(os.lseek(descriptor, 0, os.SEEK_CUR), 0)
                self.assertEqual(os.fstat(descriptor).st_ino, original.python_identity[1])
                os.write(descriptor, b"P")
                current = transaction._capture_node(path, descriptor=descriptor, kind="file",
                    data=PI.hashlib.sha256(b"Payload").hexdigest())
                self.assertTrue(transaction._image_matches(path, {path: current}, borrowed_opening=(descriptor, original)))
                self.assertEqual(os.lseek(descriptor, 0, os.SEEK_CUR), 0)
                self.assertEqual(closed, [])
        self.assertEqual(closed, selected)

    def test_invalid_wrong_original_and_closed_borrows_never_read_or_fallback(self):
        with self.opening("first") as (transaction, path, descriptor, original), self.opening("second", b"foreign") as (_other, other_path, other_descriptor, other_original):
            with patch.object(PI._InstallTransaction, "_copy_reference", side_effect=AssertionError("borrow fallback")), patch.object(PI.os, "read", side_effect=AssertionError("unproved borrow bytes")):
                for invalid in ((other_descriptor, original), (descriptor, other_original), (True, original), (descriptor, None), [descriptor, original]):
                    with self.subTest(borrow=invalid), self.assertRaises(ValueError):
                        transaction._image_matches(path, {path: original}, borrowed_opening=invalid)
                closed_descriptor = os.open(other_path, os.O_RDONLY | getattr(os, "O_BINARY", 0))
                os.close(closed_descriptor)
                with self.assertRaises(PI._InstallFailure) as caught:
                    transaction._image_matches(path, {path: original}, borrowed_opening=(closed_descriptor, original))
                self.assertIsInstance(caught.exception.cause, OSError)

    def test_independent_expected_content_is_not_original_identity_only(self):
        with self.opening() as (transaction, path, descriptor, original):
            os.write(descriptor, b"changed")
            with patch.object(PI._InstallTransaction, "_copy_reference", side_effect=AssertionError("borrow fallback")):
                self.assertFalse(transaction._image_matches(path, {path: original}, borrowed_opening=(descriptor, original)))
            self.assertEqual(os.lseek(descriptor, 0, os.SEEK_CUR), 0)
            self.assertEqual(os.fstat(descriptor).st_ino, original.python_identity[1])

    def test_read_failure_resets_zero_keeps_primary_and_lender_live(self):
        with self.opening() as (transaction, path, descriptor, original):
            os.lseek(descriptor, 0, os.SEEK_END)
            primary = OSError("borrowed read failure")
            with patch.object(PI.os, "read", side_effect=primary):
                with self.assertRaises(PI._InstallFailure) as caught:
                    transaction._image_matches(path, {path: original}, borrowed_opening=(descriptor, original))
            self.assertIs(caught.exception.cause, primary)
            self.assertEqual(os.lseek(descriptor, 0, os.SEEK_CUR), 0)
            self.assertEqual(os.fstat(descriptor).st_ino, original.python_identity[1])

    def test_read_and_reset_failure_preserve_existing_secondary_members(self):
        with self.opening() as (transaction, path, descriptor, original):
            sentinel = PI._RollbackFailureMember("backup", 39, str(path), "E_PRIOR_CLOSE", "prior secondary")
            primary = PI._InstallFailure("E_ROLLBACK_SETTLEMENT_FAILED", "prior-read", "read cause",
                                         members=(sentinel,), unresolved_paths=(path,))
            reset = OSError("zero-position reset failure")
            seek = PI.os.lseek
            calls = []
            def fail_reset(current_descriptor, position, whence):
                if current_descriptor == descriptor:
                    calls.append(position)
                    if len(calls) == 2:
                        raise reset
                return seek(current_descriptor, position, whence)
            with patch.object(PI.os, "read", side_effect=primary), patch.object(PI.os, "lseek", fail_reset):
                with self.assertRaises(PI._InstallFailure) as caught:
                    transaction._image_matches(path, {path: original}, borrowed_opening=(descriptor, original))
            self.assertIs(caught.exception.cause, primary)
            self.assertTrue(any(member is sentinel for member in caught.exception.members))
            self.assertTrue(any("zero-position reset failure" in member.cause for member in caught.exception.members))
            self.assertIn(path, caught.exception.unresolved_paths)
            self.assertEqual(os.fstat(descriptor).st_ino, original.python_identity[1])

    def test_normal_read_reset_failure_is_visible_and_does_not_close_lender(self):
        with self.opening() as (transaction, path, descriptor, original):
            reset = OSError("normal zero-position reset failure")
            seek = PI.os.lseek
            calls = []
            def fail_reset(current_descriptor, position, whence):
                if current_descriptor == descriptor:
                    calls.append(position)
                    if len(calls) == 2:
                        raise reset
                return seek(current_descriptor, position, whence)
            with patch.object(PI.os, "lseek", fail_reset):
                with self.assertRaises(PI._InstallFailure) as caught:
                    transaction._image_matches(path, {path: original}, borrowed_opening=(descriptor, original))
            self.assertIs(caught.exception.cause, reset)
            self.assertEqual(os.fstat(descriptor).st_ino, original.python_identity[1])

    def test_native_post_read_path_replacement_refuses_while_original_lender_lives(self):
        if os.name != "nt":
            self.skipTest("actual native shareable opening requires Windows")
        import msvcrt
        path = self.root / "file"
        path.write_bytes(b"original")
        transaction = PI._InstallTransaction([], enabled=False)
        with PI._WindowsBoundNode(path) as lender:
            original = transaction._capture_node(path, bound_node=lender)
            # Establish one original CRT descriptor; verification never converts or owns it.
            descriptor = lender.descriptor
            if descriptor is None:
                descriptor = msvcrt.open_osfhandle(lender.handle, os.O_RDONLY | os.O_BINARY)
                lender.descriptor, lender.handle = descriptor, None
            read = PI._InstallTransaction._scalar_descriptor_node
            def replace_after_read(selected, opening, origin):
                current = read(selected, opening, origin)
                path.rename(self.root / "original-displaced")
                path.write_bytes(b"foreign")
                return current
            with patch.object(PI._InstallTransaction, "_scalar_descriptor_node", replace_after_read):
                self.assertFalse(transaction._image_matches(path, {path: original}, borrowed_opening=(descriptor, original)))
            self.assertEqual(os.fstat(descriptor).st_ino, original.python_identity[1])
            self.assertEqual((self.root / "original-displaced").read_bytes(), b"original")
            self.assertEqual(path.read_bytes(), b"foreign")

    def test_actual_existing_and_legacy_scalar_storage_checkpoints_keep_inverse(self):
        for legacy_branch in (False, True):
            with self.subTest(legacy=legacy_branch):
                path = self.root / ("from-legacy" if legacy_branch else "existing")
                legacy = self.root / "legacy"
                source = legacy if legacy_branch else path
                source.write_bytes(b"original")
                transaction = PI._InstallTransaction([path, legacy] if legacy_branch else [path], enabled=True)
                with self.assertRaises(RuntimeError) as caught:
                    with transaction:
                        owner = PI._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                        with patch.object(transaction, "_bind_scalar_storage", lambda logical: self.scalar_binding(transaction, logical)):
                            transaction.transform_scalar(path, legacy, lambda _path: b"updated", owner)
                        self.assertEqual(path.read_bytes(), b"updated")
                        raise self.primary
                self.assertIs(caught.exception, self.primary)
                self.assertEqual(source.read_bytes(), b"original")
                if legacy_branch:
                    self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()

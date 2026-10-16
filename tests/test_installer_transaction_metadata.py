"""Isolated transaction mechanics and the shared installer error boundary."""
from contextlib import contextmanager
from dataclasses import replace
import errno
import hashlib
import importlib.util
import io
import os
from contextlib import redirect_stderr
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
    def native_observed_then_later_atime(self, *, restored=False, forward_result=True):
        """Actual result, never an expected-value echo; intervention is synthetic."""
        if os.name != "nt":
            self.skipTest("same-handle native assignment receiving")
        if restored:
            os.utime(self.target, ns=(1_650_000_000_123_456_700, 1_650_000_000_223_456_700))
        tx = PI._InstallTransaction([], enabled=False)
        node = tx._capture_node(self.target)
        with tx._copy_reference(self.target, node, metadata_only=True) as (descriptor, bound):
            current = tx._read_copy_metadata(os.fstat(descriptor), descriptor, bound)
        desired = PI._CopyMetadataImage(
            1_600_000_000_123_456_700 if restored else 1_650_000_000_123_456_700,
            1_600_000_000_223_456_700 if restored else 1_650_000_000_223_456_700,
            current.flags, current.xattrs)
        participant = PI._CopyMetadataParticipant(node, desired if restored else current, current)
        before = participant.before
        real = PI._WindowsBoundNode.set_copy_times
        observations, records = [], []
        def operation(bound, atime, mtime):
            result = real(bound, atime, mtime)
            observed = bound.basic()
            epoch = 116444736000000000
            pair = ((observed.access-epoch)*100, (observed.write-epoch)*100)
            self.assertEqual(pair, (atime//100*100, mtime//100*100))
            observations.append(pair)
            # Deliberately change only atime AFTER the full assignment observation.
            real(bound, current.atime_ns, mtime)
            return result if forward_result else None
        def record(path, image):
            records.append((tx._copy_current[path], participant.unknown))
        with patch.object(PI._WindowsBoundNode, "set_copy_times", operation):
            if forward_result:
                value = tx._apply_copy_metadata(self.target, node, desired,
                    stat.S_IMODE(node.python_identity[2]), record, participant, restored=restored)
                self.assertEqual(value.stable(), desired.stable())
                self.assertEqual(value.atime_ns, current.atime_ns)
                self.assertIs(participant.current, value)
                self.assertIs(participant.restored, value if restored else None)
                self.assertFalse(participant.unknown)
                self.assertEqual(len(records), 2)
                self.assertTrue(all(unknown for _image, unknown in records))
            else:
                with self.assertRaisesRegex(ValueError, "unknown copy setter effect"):
                    tx._apply_copy_metadata(self.target, node, desired,
                        stat.S_IMODE(node.python_identity[2]), record, participant, restored=restored)
                self.assertTrue(participant.unknown)
                self.assertEqual(records, [])
        self.assertEqual(len(observations), 1)
        self.assertIs(participant.before, before)

    def test_native_assignment_observation_accepts_later_atime_forward(self):
        self.native_observed_then_later_atime()

    def test_native_assignment_observation_accepts_later_atime_inverse(self):
        self.native_observed_then_later_atime(restored=True)

    def test_dropped_native_assignment_result_keeps_strict_full_image(self):
        self.native_observed_then_later_atime(forward_result=False)

    def test_native_assignment_observation_is_actual_for_zero_and_equal_inputs(self):
        if os.name != "nt":
            self.skipTest("native timestamp observation")
        with PI._WindowsBoundNode(self.target, purpose="attributes") as bound:
            for pair in ((0, 0), (0, 0), (1_650_000_000_123_456_773, 1_650_000_000_223_456_873)):
                with self.subTest(pair=pair):
                    result = bound.set_copy_times(*pair)
                    self.assertIs(type(result), bound._api()[4])
                    observed = bound.basic()
                    self.assertEqual((result.access, result.write), (observed.access, observed.write))
                    epoch = 116444736000000000
                    self.assertEqual(((result.access-epoch)*100, (result.write-epoch)*100),
                                     (pair[0]//100*100, pair[1]//100*100))

    def test_partial_assignment_result_cannot_be_laundered_by_later_complete_pair(self):
        if os.name != "nt":
            self.skipTest("native timestamp observation")
        current = PI._CopyMetadataImage(self.before.st_atime_ns, self.before.st_mtime_ns, None, None)
        desired = replace(current, atime_ns=1_650_000_000_123_456_700, mtime_ns=1_650_000_000_223_456_700)
        tx, node, participant, records, record = self.diagnostic_case(current)
        real = PI._WindowsBoundNode.set_copy_times
        def partial(bound, atime, mtime):
            observed = real(bound, current.atime_ns, mtime)
            real(bound, atime, mtime)  # A later complete image cannot repair the partial operation proof.
            return observed
        with patch.object(PI._WindowsBoundNode, "set_copy_times", partial):
            with self.assertRaisesRegex(ValueError, "unknown copy setter effect"):
                tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
        self.assertTrue(participant.unknown)
        self.assertEqual(records, [])

    def test_actual_current_assignment_observation_is_known_but_unmet(self):
        if os.name != "nt":
            self.skipTest("native timestamp observation")
        current = PI._CopyMetadataImage(self.before.st_atime_ns, self.before.st_mtime_ns, None, None)
        desired = replace(current, atime_ns=1_650_000_000_123_456_700, mtime_ns=1_650_000_000_223_456_700)
        tx, node, participant, records, record = self.diagnostic_case(current)
        with patch.object(PI._WindowsBoundNode, "set_copy_times", lambda bound, *_args: bound.basic()):
            with self.assertRaisesRegex(ValueError, "copy metadata readback"):
                tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
        self.assertFalse(participant.unknown)
        self.assertEqual(len(records), 1)

    def test_malformed_result_never_grants_later_atime_exemption(self):
        if os.name != "nt":
            self.skipTest("native timestamp observation")
        real = PI._WindowsBoundNode.set_copy_times
        for malformed in (0, True, (1_650_000_000_123_456_700, 1_650_000_000_223_456_700)):
            with self.subTest(result=malformed):
                os.utime(self.target, ns=(self.before.st_atime_ns, self.before.st_mtime_ns))
                current = PI._CopyMetadataImage(self.before.st_atime_ns, self.before.st_mtime_ns, None, None)
                desired = replace(current, atime_ns=1_650_000_000_123_456_700, mtime_ns=1_650_000_000_223_456_700)
                tx, node, participant, records, record = self.diagnostic_case(current)
                def operation(bound, atime, mtime):
                    real(bound, atime, mtime)
                    real(bound, current.atime_ns, mtime)
                    return malformed
                with patch.object(PI._WindowsBoundNode, "set_copy_times", operation):
                    with self.assertRaisesRegex(ValueError, "copy timestamp observation"):
                        tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
                self.assertTrue(participant.unknown)
                self.assertEqual(records, [])

    def test_native_assignment_observation_error_keeps_primary_and_known_prefix(self):
        if os.name != "nt":
            self.skipTest("native timestamp observation")
        current = PI._CopyMetadataImage(self.before.st_atime_ns, self.before.st_mtime_ns, None, None)
        desired = replace(current, atime_ns=1_650_000_000_123_456_700, mtime_ns=1_650_000_000_223_456_700)
        tx, node, participant, records, record = self.diagnostic_case(current)
        primary = OSError(errno.EIO, "native-observation-unavailable")
        primary.__cause__ = ValueError("original-cause")
        before_chain = primary.args, primary.__cause__
        basic = PI._WindowsBoundNode.basic
        inside = []
        def observation(bound):
            if sys._getframe(1).f_code.co_name == "set_copy_times":
                inside.append(True)
                if len(inside) == 2:
                    raise primary
            return basic(bound)
        with patch.object(PI._WindowsBoundNode, "basic", observation):
            with self.assertRaises(OSError) as caught:
                tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
        self.assertIs(caught.exception, primary)
        self.assertEqual((primary.args, primary.__cause__), before_chain)
        self.assertEqual(len(records), 1)
        self.assertFalse(participant.unknown)
        self.assertEqual(PI._copy_setter_detail(primary).stage, "operation")
        self.assertEqual(PI._copy_setter_operation_errors(primary), ())

    def test_proved_assignment_rejects_later_old_mtime(self):
        if os.name != "nt":
            self.skipTest("native timestamp observation")
        current = PI._CopyMetadataImage(self.before.st_atime_ns, self.before.st_mtime_ns, None, None)
        desired = replace(current, atime_ns=1_650_000_000_123_456_700, mtime_ns=1_650_000_000_223_456_700)
        tx, node, participant, records, record = self.diagnostic_case(current)
        real = PI._WindowsBoundNode.set_copy_times
        def changed(bound, atime, mtime):
            observed = real(bound, atime, mtime)
            real(bound, atime, current.mtime_ns)
            return observed
        with patch.object(PI._WindowsBoundNode, "set_copy_times", changed):
            with self.assertRaisesRegex(ValueError, "unknown copy setter effect"):
                tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
        self.assertTrue(participant.unknown)
        self.assertEqual(records, [])

    def public_copy_with_assignment_observation(self, *, inverse):
        if os.name != "nt":
            self.skipTest("native timestamp observation")
        real = PI._WindowsBoundNode.set_copy_times
        calls = []
        def later(bound, atime, mtime):
            observed = real(bound, atime, mtime)
            real(bound, atime+1_000_000_000, mtime)  # Labeled later atime-only intervention.
            calls.append((atime, mtime))
            return observed
        if not inverse:
            self.source.write_bytes(b"changed synthetic payload")
        tx = self.transaction()
        checkpoint = RuntimeError("synthetic-after-copy")
        with patch.object(PI._WindowsBoundNode, "set_copy_times", later):
            if inverse:
                with self.assertRaises(RuntimeError) as caught:
                    with tx:
                        self.owner(tx).copy_file(Path("target"), self.source)
                        raise checkpoint
                self.assertIs(caught.exception, checkpoint)
                self.assertEqual(self.target.read_bytes(), b"same")
                self.assertEqual(self.target.stat().st_mtime_ns, self.before.st_mtime_ns)
                self.assertEqual(len(calls), 2)
            else:
                with tx:
                    self.owner(tx).copy_file(Path("target"), self.source)
                    tx.commit()
                self.assertEqual(self.target.read_bytes(), b"changed synthetic payload")
                self.assertEqual(self.target.stat().st_mtime_ns, self.source.stat().st_mtime_ns)
                self.assertEqual(len(calls), 1)
        self.assertFalse(tx._copy_metadata[self.target].unknown)
        self.assert_clean()

    def test_public_changed_copy_accepts_actual_observation_then_later_atime(self):
        self.public_copy_with_assignment_observation(inverse=False)

    def test_public_equal_copy_inverse_accepts_actual_observation_then_later_atime(self):
        self.public_copy_with_assignment_observation(inverse=True)

    @unittest.skipUnless(os.name != "nt" and os.utime in os.supports_fd,
                         "requires actual POSIX descriptor timestamp receiving")
    def test_descriptor_assignment_observation_accepts_later_atime(self):
        current = PI._CopyMetadataImage(self.before.st_atime_ns, self.before.st_mtime_ns, None, None)
        tx, node, participant, records, record = self.diagnostic_case(current)
        with tx._copy_reference(self.target, node, metadata_only=True) as (descriptor, bound):
            current = tx._read_copy_metadata(os.fstat(descriptor), descriptor, bound)
        desired = replace(current, atime_ns=1_650_000_000_123_456_700, mtime_ns=1_650_000_000_223_456_700)
        reader = tx._read_copy_metadata
        observed = []
        def acquire(metadata, descriptor, bound, **kwargs):
            actual = reader(metadata, descriptor, bound, **kwargs)
            if sys._getframe(1).f_code.co_name == "operation":
                observed.append(actual)
                os.utime(descriptor, ns=(current.atime_ns, actual.mtime_ns))
            return actual
        with patch.object(tx, "_read_copy_metadata", acquire):
            actual = tx._apply_copy_metadata(self.target, node, desired,
                stat.S_IMODE(node.python_identity[2]), record, participant)
        self.assertEqual(len(observed), 1)
        self.assertEqual((observed[0].atime_ns, observed[0].mtime_ns), (desired.atime_ns, desired.mtime_ns))
        self.assertEqual(actual.stable(), desired.stable())
        self.assertEqual(actual.atime_ns, current.atime_ns)
        self.assertFalse(participant.unknown)

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

    def through_install(self, action):
        """Exercise the actual shared output/exit boundary before pack acquisition."""
        escaped = []
        def selected_target(*_args):
            try:
                action()
            except BaseException as error:
                escaped.append(error)
                raise
            raise AssertionError("the diagnostic fixture must fail")
        stderr = io.StringIO()
        with patch.object(PI, "_target", selected_target), redirect_stderr(stderr):
            result = PI.install("claude", ["--target", str(self.root)])
        return result, stderr.getvalue(), escaped

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
        primary.__cause__ = ValueError("original-cause")
        primary.__context__ = RuntimeError("original-context")
        original_chain = (primary.args, primary.__cause__, primary.__context__)
        calls = []
        def fault(bound, atime, mtime):
            setter(bound, atime, mtime)
            calls.append(mtime)
            if len(calls) == 1:
                raise primary
        transaction = self.transaction()
        def action():
            with patch.object(PI._WindowsBoundNode, "set_copy_times", fault):
                with transaction:
                    self.owner(transaction).copy_file(Path("target"), self.source)
        result, stderr, escaped = self.through_install(action)
        self.assertEqual(result, 1)
        self.assertIs(escaped[0], primary)
        self.assertEqual(primary.args, original_chain[0])
        self.assertIs(primary.__cause__, original_chain[1])
        self.assertIs(primary.__context__, original_chain[2])
        self.assertIn("operation=timestamps", stderr)
        self.assertEqual(stderr.count("operation=timestamps"), 1)
        self.assertIn("stage=operation", stderr)
        self.assertIn("metadata-projected=true", stderr)
        self.assertNotIn("operation=timestamps", str(primary))
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
            assignments = []
            def record(member, value):
                assignments.append(transaction._copy_current[member])
                transaction._advance(member, {member: value})
            actual = transaction._apply_copy_metadata(self.target, node, desired,
                stat.S_IMODE(node.python_identity[2]),
                record, participant)
            self.assertEqual(assignments[0].atime_ns, desired.atime_ns // 100 * 100)
            self.assertEqual(assignments[0].mtime_ns, desired.mtime_ns // 100 * 100)
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

    def diagnostic_case(self, current):
        """Use a real held ordinary file; only test observations are substituted."""
        transaction = PI._InstallTransaction([], enabled=False)
        node = transaction._capture_node(self.target)
        participant = PI._CopyMetadataParticipant(node, current, current)
        records = []
        def record(path, value):
            records.append((path, value, participant.unknown))
        return transaction, node, participant, records, record

    def test_scalar_checkpoint_reaches_actual_cli_with_primary_target(self):
        current = PI._CopyMetadataImage(-11644473600000000000, -100, None, None)
        desired = replace(current, mtime_ns=0)
        actual = replace(current, atime_ns=current.atime_ns + 100)
        tx = self.transaction()
        node = tx._capture_node(self.target)
        participant = tx._copy_metadata[self.target]
        records = []
        def action():
            with self.no_timestamp_effect(), patch.object(tx, "_read_copy_metadata", side_effect=[current, actual]):
                tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]),
                                        lambda *args: records.append(args), participant)
        result, stderr, escaped = self.through_install(action)
        self.assertEqual(result, 1)
        self.assertEqual(str(escaped[0]), "E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY: unknown copy setter effect")
        self.assertIn("atime_ns[unix-epoch-ns]=before:-11644473600000000000,projected:-11644473600000000000,observed:-11644473599999999900", stderr)
        self.assertIn("mtime_ns[unix-epoch-ns]=before:-100,projected:0,observed:-100", stderr)
        self.assertIn("flags[decimal-bitmask]=before:none,projected:none,observed:none", stderr)
        normalized = os.path.abspath(self.target)
        digest = hashlib.sha256(normalized.encode("utf-8", "surrogatepass")).hexdigest()
        self.assertEqual(stderr.count("target-path-sha256=" + digest), 1)
        self.assertNotIn(normalized, stderr)
        self.assertEqual(PI._copy_setter_detail(escaped[0]).target_text, normalized)
        self.assertEqual(records, [])
        self.assertTrue(participant.unknown)

    def test_scalar_created_target_without_origin_keeps_association(self):
        created = self.root / "created"
        tx = PI._InstallTransaction([], enabled=False, copy_paths=(created,))
        created.write_bytes(b"created")
        node = tx._capture_node(created)
        participant = tx._copy_metadata[created]
        self.assertIsNone(participant.origin)
        current = PI._CopyMetadataImage(-11644473600000000000, 0, None, None)
        desired = replace(current, mtime_ns=100)
        primary = OSError(errno.EIO, "created-readback")
        def action():
            with self.no_timestamp_effect(), patch.object(tx, "_read_copy_metadata", side_effect=[current, primary]):
                tx._apply_copy_metadata(created, node, desired, stat.S_IMODE(node.python_identity[2]),
                                        lambda *_args: self.fail("unexpected record"), participant)
        result, stderr, escaped = self.through_install(action)
        self.assertEqual(result, 1)
        self.assertIs(escaped[0], primary)
        self.assertIn("flags[decimal-bitmask]=before:none,projected:none,observed:unavailable", stderr)
        self.assertIn("mtime_ns[unix-epoch-ns]=before:0,projected:100,observed:unavailable", stderr)
        expected = os.path.abspath(created)
        self.assertEqual(PI._copy_setter_detail(primary).target_text, expected)
        self.assertIn("target-path-sha256=" + hashlib.sha256(expected.encode()).hexdigest(), stderr)
        self.assertNotIn(expected, stderr)

    def test_scalar_nested_inverse_targets_leaf_not_containing_member(self):
        directory = self.root / "tree"
        directory.mkdir()
        self.target.rename(directory / "target")
        self.target = directory / "target"
        tx = self.transaction([directory])
        primary = RuntimeError("nested-primary")
        inverse_error = OSError(errno.EIO, "PRIVATE_nested_inverse")
        setter = PI._WindowsBoundNode.set_copy_times
        def inverse(bound, atime, mtime):
            setter(bound, atime, mtime)
            raise inverse_error
        def action():
            inverse_patch = patch.object(PI._WindowsBoundNode, "set_copy_times", inverse)
            try:
                with tx:
                    self.owner(tx).copy_file(Path("tree/target"), self.source)
                    inverse_patch.start()
                    raise primary
            finally:
                inverse_patch.stop()
        result, stderr, escaped = self.through_install(action)
        aggregate = escaped[0]
        self.assertEqual(result, 1)
        self.assertIs(aggregate.cause, primary)
        self.assertEqual(len(aggregate.members), 1)
        member = aggregate.members[0]
        self.assertEqual(member.path, str(directory))
        normalized = os.path.abspath(self.target)
        context = member.copy_setter_diagnostic
        self.assertEqual(context.target_text, normalized)
        self.assertEqual(stderr.count("target-path-sha256=" + hashlib.sha256(normalized.encode()).hexdigest()), 1)
        self.assertNotIn("target-path-sha256=" + hashlib.sha256(os.path.abspath(directory).encode()).hexdigest(), stderr)
        self.assertNotIn(normalized, stderr)
        self.assertNotIn("PRIVATE_nested_inverse", stderr)
        self.assertEqual(member.cause, str(inverse_error))

    def test_scalar_aggregate_preserves_all_32_members_and_per_occurrence_bounds(self):
        high, low = 10 ** 40 - 1, -(10 ** 39 - 1)
        current = PI._CopyMetadataImage(high, low, high, None)
        projected = PI._CopyMetadataImage(low, high, low, None)
        actual = PI._CopyMetadataImage(high, high, high, None)
        identity = (1, 2, 3, 4)
        primary = ValueError("original-primary")
        primary_participant = PI._CopyMetadataParticipant(None, None, None, target_text="PRIVATE_primary_target")
        primary_current = PI._CopyMetadataImage(-11644473600000000000, 0, None, None)
        primary_projected = replace(primary_current, flags=0)
        primary_actual = replace(primary_projected, atime_ns=primary_current.atime_ns + 100)
        PI._CopySetterDiagnostic.attach(primary, "timestamps", False, "comparison", 1,
                                       primary_current, primary_projected, identity, identity, primary_actual, identity,
                                       participant=primary_participant)
        members = []
        contexts = [PI._copy_setter_detail(primary)]
        for index in range(32):
            error = OSError(errno.EIO, f"PRIVATE_member_cause_{index}")
            participant = PI._CopyMetadataParticipant(None, None, None, target_text=f"PRIVATE_inverse_target_{index}")
            PI._CopySetterDiagnostic.attach(error, "timestamps", True, "comparison", index + 1,
                                           current, projected, identity, identity, actual, identity, participant=participant)
            _paths, received, _retained_errors = PI._InstallTransaction._settlement_failure(error, "snapshot", index,
                                                                         Path(f"member-{index:02}"), "E_MEMBER")
            members.extend(received)
            contexts.append(PI._copy_setter_detail(error))
        aggregate = PI._InstallFailure("E_AGGREGATE", "rollback", primary, members=tuple(members),
                                       recovery_path=Path("synthetic-recovery"))
        original = str(aggregate)
        legacy = []
        additions = []
        for index, context in enumerate(contexts):
            rendered = context.render()
            preceding, payload = rendered.split("; atime_ns[", 1)
            addition = "atime_ns[" + payload
            self.assertLessEqual(len(addition.encode("ascii")), 768)
            self.assertLessEqual(len(("; " + addition).encode("ascii")), 2048)
            if index:
                self.assertEqual(addition.count(str(high)), 6)
                self.assertEqual(addition.count(str(low)), 3)
            self.assertIn(hashlib.sha256(context.target_text.encode()).hexdigest(), addition)
            legacy.append(preceding)
            additions.append(addition)
        self.assertGreater(len(" | ".join(legacy)), 2048)
        def action():
            raise aggregate
        result, stderr, escaped = self.through_install(action)
        self.assertEqual(result, 1)
        self.assertIs(escaped[0], aggregate)
        self.assertEqual(str(aggregate), original)
        self.assertTrue(stderr.startswith("FAIL: " + original + " | copy-setter="))
        self.assertGreater(len(stderr), 2048)
        self.assertEqual(stderr.count("cleanup-copy-setter="), 32)
        self.assertEqual(stderr.count("target-path-sha256="), 33)
        self.assertNotIn("PRIVATE_", stderr)
        self.assertNotIn("detail-budget=exceeded", stderr)
        self.assertIn("flags[decimal-bitmask]=before:none,projected:0,observed:0", stderr)
        self.assertIn("atime_ns[unix-epoch-ns]=before:-11644473600000000000,projected:-11644473600000000000,observed:-11644473599999999900", stderr)
        positions = []
        for index, member in enumerate(members):
            self.assertIs(aggregate.members[index], member)
            self.assertEqual(member.cause, str(OSError(errno.EIO, f"PRIVATE_member_cause_{index}")))
            marker = f"cleanup-copy-setter=snapshot:{index}:E_MEMBER:" + contexts[index + 1].render()
            positions.append(stderr.index(marker))
            self.assertIn(legacy[index + 1], stderr)
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(stderr.count("target-path-sha256=" + hashlib.sha256(b"PRIVATE_primary_target").hexdigest()), 1)
        value_free = stderr
        for addition in additions:
            value_free = value_free.replace("; " + addition, "")
        expected_legacy = "FAIL: " + original + " | copy-setter=" + legacy[0]
        for index, context in enumerate(legacy[1:]):
            expected_legacy += f" | cleanup-copy-setter=snapshot:{index}:E_MEMBER:" + context
        self.assertEqual(value_free, expected_legacy + "\n")

    def test_scalar_limits_and_foreign_optional_fields_preserve_legacy_and_other_components(self):
        hooks = []
        class ForeignInteger(int):
            def __le__(self, other):
                hooks.append("integer-order")
                return True
            def __str__(self):
                hooks.append("integer-text")
                return "PRIVATE_integer"
        class ForeignString(str):
            def encode(self, *_args):
                hooks.append("string-encode")
                return b"PRIVATE_string"
            def __len__(self):
                hooks.append("string-length")
                return 1
        legacy = PI._CopySetterDiagnostic("timestamps", "forward", "comparison", 1,
                                         True, False, True, True, (), ("mtime_ns",), (), ())
        malformed = replace(legacy, scalar_values=((ForeignInteger(1), True, 10 ** 40),
                                                  (0, -100, -(10 ** 39)), (None, 0, ())),
                            target_text=ForeignString("PRIVATE_path"))
        error = ValueError("optional-original")
        PI._store_copy_setter_detail(error, malformed)
        def action():
            raise error
        result, stderr, escaped = self.through_install(action)
        self.assertEqual(result, 1)
        self.assertIs(escaped[0], error)
        self.assertIn("metadata-vs-projected=mtime_ns", stderr)
        self.assertIn("atime_ns[unix-epoch-ns]=before:unavailable,projected:unavailable,observed:unavailable", stderr)
        self.assertIn("mtime_ns[unix-epoch-ns]=before:0,projected:-100,observed:unavailable", stderr)
        self.assertIn("flags[decimal-bitmask]=before:none,projected:0,observed:unavailable", stderr)
        self.assertIn("target-path-sha256=unavailable", stderr)
        self.assertNotIn("PRIVATE_", stderr)
        self.assertEqual(hooks, [])
        identity = (1, 2, 3, 4)
        current = PI._CopyMetadataImage(10 ** 40, 123, 0, (("PRIVATE_xattr", b"PRIVATE_payload"),))
        participant = PI._CopyMetadataParticipant(None, None, None, target_text="PRIVATE_path" * 131073)
        PI._CopySetterDiagnostic.attach(error, "timestamps", False, "comparison", 1,
                                       current, current, identity, identity, current, identity, participant=participant)
        context = PI._copy_setter_detail(error)
        self.assertIsNone(context.target_text)
        self.assertIn("mtime_ns[unix-epoch-ns]=before:123,projected:123,observed:123", context.render())
        self.assertIn("metadata-current=true", context.render())
        self.assertNotIn("PRIVATE_", context.render())
        # Exact UTF-8 byte limit, including native surrogate characters.
        for target, admitted in (("a" * 131072, True), ("a" * 131073, False),
                                 ("\u00e9" * 65536, True), ("\u00e9" * 65537, False), ("\ud800", True)):
            participant.target_text = target
            PI._CopySetterDiagnostic.attach(error, "timestamps", False, "comparison", 1,
                                           current, current, identity, identity, current, identity, participant=participant)
            context = PI._copy_setter_detail(error)
            self.assertEqual(context.target_text is not None, admitted)
            expected = hashlib.sha256(target.encode("utf-8", "surrogatepass")).hexdigest() if admitted else "unavailable"
            self.assertIn("target-path-sha256=" + expected, context.render())
        with patch.object(PI.hashlib, "sha256", side_effect=OSError("optional-digest-unavailable")):
            result, stderr, escaped = self.through_install(action)
        self.assertEqual(result, 1)
        self.assertIs(escaped[0], error)
        self.assertIn("metadata-current=true", stderr)
        self.assertIn("mtime_ns[unix-epoch-ns]=before:123,projected:123,observed:123", stderr)
        self.assertIn("target-path-sha256=unavailable", stderr)

    def test_scalar_participant_namespace_and_subclass_do_not_dispatch(self):
        hooks = []
        class ForeignParticipant(PI._CopyMetadataParticipant):
            def __getattribute__(self, name):
                hooks.append("participant-getter")
                raise AssertionError(name)
        class ForeignKey:
            def __hash__(self):
                return hash("target_text")
            def __eq__(self, other):
                hooks.append("participant-key")
                return False
        malformed = PI._CopyMetadataParticipant(None, None, None, target_text="PRIVATE_path")
        storage = PI._CopyMetadataParticipant.__dict__["__dict__"].__get__(malformed)
        dict.__setitem__(storage, ForeignKey(), "PRIVATE_namespace")
        hooks.clear()
        current = PI._CopyMetadataImage(1, 2, None, None)
        identity = (1, 2, 3, 4)
        for participant in (malformed, ForeignParticipant(None, None, None)):
            error = ValueError("namespace-original")
            PI._CopySetterDiagnostic.attach(error, "timestamps", False, "comparison", 1,
                                           current, current, identity, identity, current, identity, participant=participant)
            context = PI._copy_setter_detail(error)
            self.assertIsNone(context.target_text)
            self.assertIn("metadata-current=true", context.render())
            self.assertIn("mtime_ns[unix-epoch-ns]=before:2,projected:2,observed:2", context.render())
        self.assertEqual(hooks, [])

    @contextmanager
    def no_timestamp_effect(self):
        with patch.object(PI._WindowsBoundNode, "set_copy_times", lambda *_args: None):
            yield

    def test_mixed_full_image_rejection_keeps_unknown_and_recovery(self):
        setter = PI._WindowsBoundNode.set_copy_times
        reader = PI._InstallTransaction._read_copy_metadata
        source_inode = self.source.stat().st_ino
        def source_observation(metadata, descriptor, bound):
            image = reader(metadata, descriptor, bound)
            return replace(image, atime_ns=1_650_000_000_123_456_700) if metadata.st_ino == source_inode else image
        def mixed_effect(bound, atime, mtime):
            # Preserve actual old atime and apply only projected mtime.
            old = os.fstat(bound.descriptor)
            self.assertNotEqual(old.st_atime_ns, atime)
            self.assertNotEqual(old.st_mtime_ns, mtime)
            setter(bound, old.st_atime_ns, mtime)
        transaction = self.transaction()
        with patch.object(PI._InstallTransaction, "_read_copy_metadata", staticmethod(source_observation)), \
                patch.object(PI._WindowsBoundNode, "set_copy_times", mixed_effect):
            with self.assertRaises(PI._InstallFailure) as caught:
                with transaction:
                    self.owner(transaction).copy_file(Path("target"), self.source)
        primary = caught.exception.cause
        self.assertIs(type(primary), ValueError)
        self.assertEqual(str(primary), "E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY: unknown copy setter effect")
        context = PI._copy_setter_detail(primary)
        self.assertFalse(context.metadata_current)
        self.assertFalse(context.metadata_projected)
        self.assertEqual(context.metadata_vs_current, ("mtime_ns",))
        self.assertEqual(context.metadata_vs_projected, ("atime_ns",))
        self.assertTrue(context.identity_old)
        self.assertTrue(transaction._copy_metadata[self.target].unknown)
        self.assertTrue(caught.exception.recovery_path.exists())

    def test_known_current_unmet_projection_reports_inverse_without_changing_record(self):
        current = PI._CopyMetadataImage(100, 200, None, None)
        desired = PI._CopyMetadataImage(300, 400, None, None)
        tx, node, participant, records, record = self.diagnostic_case(current)
        with self.no_timestamp_effect(), patch.object(tx, "_read_copy_metadata", side_effect=[current, current]):
            with self.assertRaises(ValueError) as caught:
                tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]),
                                        record, participant, restored=True)
        self.assertEqual(str(caught.exception), "E_MUTABLE_PATH_POSTCONDITION: copy metadata readback")
        context = PI._copy_setter_detail(caught.exception)
        self.assertEqual(context.direction, "inverse")
        self.assertTrue(context.metadata_current)
        self.assertFalse(context.metadata_projected)
        self.assertEqual(context.metadata_vs_current, ())
        self.assertEqual(context.metadata_vs_projected, ("atime_ns", "mtime_ns"))
        self.assertEqual(len(records), 1)
        self.assertTrue(records[0][2])  # Existing record precedes participant settlement.
        self.assertFalse(participant.unknown)
        self.assertEqual(participant.current, current)
        self.assertEqual(participant.restored, current)

    def test_metadata_acquisition_failure_has_no_fabricated_comparisons(self):
        current = PI._CopyMetadataImage(100, 200, None, None)
        desired = PI._CopyMetadataImage(300, 400, None, None)
        tx, node, participant, records, record = self.diagnostic_case(current)
        operation = OSError(errno.EIO, "operation-first")
        operation.__cause__ = RuntimeError("kept-operation-cause")
        operation.__context__ = ValueError("kept-operation-context")
        operation_chain = (operation.args, operation.__cause__, operation.__context__, operation.__suppress_context__)
        primary = OSError(errno.EIO, "metadata-acquisition")
        primary.__cause__ = RuntimeError("kept-cause")
        chain = (primary.args, primary.__cause__, primary.__context__, primary.__suppress_context__)
        with patch.object(PI._WindowsBoundNode, "set_copy_times", side_effect=operation), \
                patch.object(tx, "_read_copy_metadata", side_effect=[current, primary]):
            with self.assertRaises(OSError) as caught:
                tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
        self.assertIs(caught.exception, primary)
        self.assertEqual((primary.args, primary.__cause__, primary.__context__, primary.__suppress_context__), chain)
        self.assertEqual((operation.args, operation.__cause__, operation.__context__, operation.__suppress_context__), operation_chain)
        retained = PI._copy_setter_operation_errors(primary)
        self.assertEqual(len(retained), 1)
        self.assertIs(retained[0], operation)
        context = PI._copy_setter_detail(primary)
        self.assertEqual(context.stage, "metadata-acquisition")
        self.assertIsNone(context.metadata_current)
        self.assertIsNone(context.identity_old)
        self.assertIsNone(context.metadata_vs_current)
        self.assertTrue(participant.unknown)
        self.assertEqual(records, [])

    def test_compound_identity_and_record_keep_actual_errors_and_completed_prefix(self):
        current = PI._CopyMetadataImage(100, 200, None, None)
        desired = PI._CopyMetadataImage(300, 400, None, None)
        for stage in ("identity", "record"):
            with self.subTest(stage=stage):
                tx, node, participant, records, record = self.diagnostic_case(current)
                operation = OSError(errno.EIO, "PRIVATE-earlier-operation")
                operation.__cause__ = ValueError("PRIVATE-earlier-cause")
                operation.__context__ = RuntimeError("PRIVATE-earlier-context")
                later = OSError(errno.EIO, "later-" + stage)
                later.__cause__ = ValueError("kept-later-cause")
                later.__context__ = RuntimeError("kept-later-context")
                earlier_chain = (operation.args, operation.__cause__, operation.__context__, operation.__suppress_context__)
                later_chain = (later.args, later.__cause__, later.__context__, later.__suppress_context__)
                if stage == "record":
                    def record(path, value):
                        records.append((path, value, participant.unknown))
                        raise later
                with patch.object(PI._WindowsBoundNode, "set_copy_times", side_effect=operation), \
                        patch.object(tx, "_read_copy_metadata", side_effect=[current, desired]), \
                        patch.object(tx, "_capture_node", side_effect=later if stage == "identity" else None,
                                     return_value=node):
                    with self.assertRaises(OSError) as caught:
                        tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]),
                                                record, participant)
                self.assertIs(caught.exception, later)
                retained = PI._copy_setter_operation_errors(later)
                self.assertEqual(len(retained), 1)
                self.assertIs(retained[0], operation)
                self.assertEqual((later.args, later.__cause__, later.__context__, later.__suppress_context__), later_chain)
                self.assertEqual((operation.args, operation.__cause__, operation.__context__, operation.__suppress_context__), earlier_chain)
                self.assertTrue(participant.unknown)
                self.assertIs(participant.current, current)
                self.assertIsNone(participant.restored)
                if stage == "identity":
                    self.assertEqual(records, [])
                    self.assertNotIn(self.target, tx._copy_current)
                    self.assertEqual(PI._copy_setter_detail(later).stage, "identity-acquisition")
                else:
                    self.assertEqual(len(records), 1)
                    self.assertTrue(records[0][2])
                    self.assertIs(tx._copy_current[self.target], desired)
                    self.assertIsNone(PI._copy_setter_detail(later))

    def test_compound_required_errors_survive_unavailable_optional_diagnostic_and_public_transport(self):
        class NonprimitiveInteger(int):
            def __eq__(self, _other):
                raise AssertionError("foreign optional equality")
        current = PI._CopyMetadataImage(100, 200, NonprimitiveInteger(1), None)
        desired = replace(current, atime_ns=300, mtime_ns=400)
        tx, node, participant, records, record = self.diagnostic_case(current)
        operation = OSError(errno.EIO, "PRIVATE-earlier-operation")
        operation.__cause__ = ValueError("PRIVATE-earlier-cause")
        later = OSError(errno.EIO, "later-metadata")
        later.__cause__ = RuntimeError("kept-later-cause")
        later.__context__ = ValueError("kept-later-context")
        chain = (later.args, later.__cause__, later.__context__, later.__suppress_context__)
        def action():
            with patch.object(PI._WindowsBoundNode, "set_copy_times", side_effect=operation), \
                    patch.object(tx, "_read_copy_metadata", side_effect=[current, later]):
                tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
        result, stderr, escaped = self.through_install(action)
        self.assertEqual(result, 1)
        self.assertIs(escaped[0], later)
        self.assertEqual(PI._copy_setter_detail(later), ())
        self.assertIs(PI._copy_setter_operation_errors(later)[0], operation)
        self.assertEqual((later.args, later.__cause__, later.__context__, later.__suppress_context__), chain)
        self.assertIn("copy-setter=unavailable", stderr)
        self.assertIn("copy-setter-operation-errors=1", stderr)
        self.assertNotIn("PRIVATE-earlier", stderr)
        self.assertTrue(participant.unknown)
        self.assertEqual(records, [])

        wrapped = PI._InstallFailure("E_COMPOUND", "copy", later)
        self.assertIs(wrapped.cause, later)
        self.assertIs(PI._copy_setter_operation_errors(wrapped), PI._copy_setter_operation_errors(later))
        _paths, members, retained_errors = tx._settlement_failure(wrapped, "snapshot", 2, self.target, "E_IGNORED")
        self.assertEqual(len(members), 1)
        self.assertIs(members[0].copy_setter_failure, wrapped)
        self.assertIs(PI._copy_setter_operation_errors(members[0].copy_setter_failure)[0], operation)
        aggregate = PI._InstallFailure("E_ROLLBACK_SETTLEMENT_FAILED", "rollback", "public-primary", members=tuple(members))
        def aggregate_action():
            raise aggregate
        result, stderr, escaped = self.through_install(aggregate_action)
        self.assertEqual(result, 1)
        self.assertIs(escaped[0], aggregate)
        self.assertIs(aggregate.members[0], members[0])
        self.assertIn("cleanup-copy-setter-operation-errors=snapshot:2:E_COMPOUND:1", stderr)
        self.assertNotIn("PRIVATE-earlier", stderr)
        plain = replace(members[0], copy_setter_failure=None)
        self.assertEqual(plain, members[0])
        self.assertEqual(repr(plain), repr(members[0]))
        _paths, forwarded, retained_errors = tx._settlement_failure(aggregate, "backup", 3, self.target, "E_IGNORED")
        self.assertIs(forwarded[0], members[0])
        _paths, ordinary, retained_errors = tx._settlement_failure(later, "snapshot", 4, self.target, "E_PLAIN")
        self.assertIs(ordinary[0].copy_setter_failure, later)
        _paths, unrelated, retained_errors = tx._settlement_failure(ValueError("ordinary"), "snapshot", 5, self.target, "E_PLAIN")
        self.assertIsNone(unrelated[0].copy_setter_failure)

    def test_composite_error_two_forwarding_hops_keep_whole_wrapper_and_members(self):
        primary = OSError("PRIVATE-earlier-operation")
        primary.__cause__ = ValueError("PRIVATE-earlier-cause")
        primary.__context__ = RuntimeError("PRIVATE-earlier-context")
        later = OSError("later-observation")
        later.__cause__ = ValueError("later-existing-cause")
        later.__context__ = RuntimeError("later-existing-context")
        chains = [(error.args, error.__cause__, error.__context__, error.__suppress_context__)
                  for error in (primary, later)]
        PI._retain_copy_setter_operation_errors(later, (primary,))
        PI._store_copy_setter_detail(later, ())
        members = (PI._RollbackFailureMember("backup", 7, "synthetic-one", "E_CLOSE_ONE", "close-one"),
                   PI._RollbackFailureMember("backup", 8, "synthetic-two", "E_CLOSE_TWO", "close-two"))
        wrapper = PI._InstallFailure("E_COMPOUND", "native-close", later, members=members)
        _paths, received, errors = PI._InstallTransaction._settlement_failure(
            wrapper, "snapshot", 9, Path("synthetic-target"), "E_UNUSED")
        self.assertIs(errors[0], wrapper)
        unrelated = RuntimeError("unrelated-checkpoint")
        aggregate = PI._InstallFailure("E_ROLLBACK_SETTLEMENT_FAILED", "rollback", unrelated,
                                        members=tuple(received), retained_errors=errors)
        self.assertIs(PI._copy_setter_operation_errors(aggregate)[0], wrapper)
        _paths, forwarded, errors = PI._InstallTransaction._settlement_failure(
            aggregate, "backup", 10, Path("synthetic-target"), "E_UNUSED")
        self.assertIs(errors[0], aggregate)
        second = PI._InstallFailure("E_ROLLBACK_SETTLEMENT_FAILED", "rollback", RuntimeError("second-checkpoint"),
                                     members=tuple(forwarded), retained_errors=errors)
        retained_aggregate = PI._copy_setter_operation_errors(second)[0]
        self.assertIs(retained_aggregate, aggregate)
        retained_wrapper = PI._copy_setter_operation_errors(retained_aggregate)[0]
        self.assertIs(retained_wrapper, wrapper)
        self.assertIs(retained_wrapper.cause, later)
        self.assertIs(PI._copy_setter_operation_errors(retained_wrapper)[0], primary)
        for received_error in (aggregate, second):
            self.assertEqual(len(received_error.members), 2)
            for actual, original in zip(received_error.members, members):
                self.assertIs(actual, original)
                self.assertIsNone(actual.copy_setter_failure)
            def action():
                raise received_error
            result, stderr, escaped = self.through_install(action)
            self.assertEqual(result, 1)
            self.assertIs(escaped[0], received_error)
            self.assertIn("copy-setter-operation-errors=1", stderr)
            self.assertNotIn("PRIVATE", stderr)
        for error, chain in zip((primary, later), chains):
            self.assertEqual((error.args, error.__cause__, error.__context__, error.__suppress_context__), chain)

    def test_settlement_empty_channels_and_member_normalization_do_not_invent_errors(self):
        tx = PI._InstallTransaction([], enabled=False)
        self.assertEqual(tx._settle_effects(), ([], [], ()))
        self.assertEqual(tx._settle_scalars([]), ([], [], ()))
        self.assertEqual(tx._settle_created(), ([], [], ()))
        self.assertEqual(tx._settle_migrated(), ([], [], ()))
        self.assertEqual(tx._commit_migrated(), ([], [], ()))
        self.assertEqual(tx._settle_migration_retention(), ([], [], ()))
        self.assertEqual(tx._settle_snapshots([]), ([], False, ()))
        self.assertEqual(tx._remaining_recovery(), (None, [], [], ()))
        ordinary = ValueError("ordinary")
        _paths, ordinary_members, errors = tx._settlement_failure(ordinary, "snapshot", 0, Path("synthetic"), "E_ORDINARY")
        self.assertEqual(errors, ())
        self.assertIsNone(ordinary_members[0].copy_setter_failure)
        self.assertEqual(PI._copy_setter_operation_errors(PI._InstallFailure("E_ORDINARY", "copy", ordinary)), ())
        primary, later = OSError("PRIVATE-earlier"), ValueError("later")
        PI._retain_copy_setter_operation_errors(later, (primary,))
        member = PI._RollbackFailureMember("snapshot", 1, "synthetic", "E_COMPOUND", "later", copy_setter_failure=later)
        aggregate = PI._InstallFailure("E_AGGREGATE", "rollback", "unrelated", members=(member,),
                                        retained_errors=(later, later))
        retained = PI._copy_setter_operation_errors(aggregate)
        self.assertEqual(len(retained), 1)
        self.assertIs(retained[0], later)
        self.assertIs(aggregate.members[0], member)

    def test_transaction_commit_and_rollback_receive_collected_composite_error(self):
        for committed in (False, True):
            with self.subTest(committed=committed):
                primary, later = OSError("PRIVATE-earlier"), OSError("later-observation")
                PI._retain_copy_setter_operation_errors(later, (primary,))
                members = (PI._RollbackFailureMember("backup", 7, "synthetic-one", "E_ONE", "one"),
                           PI._RollbackFailureMember("backup", 8, "synthetic-two", "E_TWO", "two"))
                wrapper = PI._InstallFailure("E_COMPOUND", "native-close", later, members=members)
                outer = RuntimeError("unrelated-checkpoint")
                tx = self.transaction()
                collector = "_commit_migrated" if committed else "_settle_effects"
                with patch.object(tx, collector, return_value=([self.target], list(members), (wrapper,))):
                    with self.assertRaises(PI._InstallFailure) as caught:
                        with tx:
                            if committed:
                                tx.commit()
                            raise outer
                final = caught.exception
                self.assertIs(final.cause, outer)
                self.assertTrue(any(error is wrapper for error in PI._copy_setter_operation_errors(final)))
                self.assertIs(wrapper.cause, later)
                self.assertIs(PI._copy_setter_operation_errors(wrapper)[0], primary)
                for member in members:
                    self.assertTrue(any(actual is member for actual in final.members))
                self.assertTrue(final.recovery_path.exists())
                text = PI._installer_failure_text(final)
                self.assertIn("copy-setter-operation-errors=1", text)
                self.assertNotIn("PRIVATE", text)

    def test_recovery_failure_returns_actual_composite_alongside_existing_members(self):
        primary, later = OSError("PRIVATE-earlier"), OSError("later-observation")
        PI._retain_copy_setter_operation_errors(later, (primary,))
        members = (PI._RollbackFailureMember("backup", 7, "synthetic-one", "E_ONE", "one"),
                   PI._RollbackFailureMember("backup", 8, "synthetic-two", "E_TWO", "two"))
        wrapper = PI._InstallFailure("E_COMPOUND", "native-close", later, members=members)
        outer = RuntimeError("final-cleanup-checkpoint")
        tx = self.transaction()
        with self.assertRaises(RuntimeError) as final:
            with tx:
                with patch.object(tx, "_point_matches", side_effect=wrapper):
                    selected, unresolved, received, errors = tx._remaining_recovery()
                self.assertIsNone(selected)
                self.assertIn(tx._temporary, unresolved)
                self.assertIs(errors[0], wrapper)
                self.assertEqual(len(received), 2)
                for actual, original in zip(received, members):
                    self.assertIs(actual, original)
                raise outer
        self.assertIs(final.exception, outer)
        self.assert_clean()

    def test_required_error_carriage_is_ordered_identity_idempotent_and_bypasses_foreign_hooks(self):
        hooks = []
        class NativeDictionary(dict):
            def __getitem__(self, key):
                hooks.append("dictionary-read")
                raise AssertionError("foreign dictionary")
            def __setitem__(self, key, value):
                hooks.append("dictionary-write")
                raise AssertionError("foreign dictionary")
        class ForeignError(OSError):
            def __getattribute__(self, key):
                if key in ("__dict__", "_copy_setter_operation_errors"):
                    hooks.append("attribute-read")
                    raise AssertionError("foreign attribute")
                return super().__getattribute__(key)
            def __setattr__(self, key, value):
                if key == "_copy_setter_operation_errors":
                    hooks.append("attribute-write")
                    raise AssertionError("foreign attribute")
                super().__setattr__(key, value)
            def __eq__(self, _other):
                hooks.append("error-equality")
                raise AssertionError("foreign equality")
            def __hash__(self):
                hooks.append("error-hash")
                raise AssertionError("foreign hash")
            def __str__(self):
                hooks.append("error-string")
                raise AssertionError("foreign string")
        first, second, later = ForeignError("PRIVATE-first"), ForeignError("PRIVATE-second"), ValueError("later")
        BaseException.__dict__["__dict__"].__set__(later, NativeDictionary())
        PI._retain_copy_setter_operation_errors(later, (first,))
        PI._retain_copy_setter_operation_errors(later, (first, second, later, second))
        retained = PI._copy_setter_operation_errors(later)
        self.assertEqual(len(retained), 2)
        self.assertIs(retained[0], first)
        self.assertIs(retained[1], second)
        wrapped = PI._InstallFailure("E_COMPOUND", "copy", later)
        PI._retain_copy_setter_operation_errors(wrapped, retained)
        self.assertIs(PI._copy_setter_operation_errors(wrapped), retained)
        self.assertIn("copy-setter-operation-errors=2", PI._installer_failure_text(wrapped))
        # Exercise carriage access on the foreign exception itself as well.
        PI._retain_copy_setter_operation_errors(first, (second,))
        self.assertIs(PI._copy_setter_operation_errors(first)[0], second)
        self.assertEqual(hooks, [])

    def test_identity_acquisition_failure_reports_only_acquired_metadata(self):
        current = PI._CopyMetadataImage(100, 200, None, None)
        desired = PI._CopyMetadataImage(300, 400, None, None)
        tx, node, participant, records, record = self.diagnostic_case(current)
        primary = OSError(errno.EIO, "identity-acquisition")
        chain = (primary.args, primary.__cause__, primary.__context__)
        with self.no_timestamp_effect(), patch.object(tx, "_read_copy_metadata", side_effect=[current, desired]), \
                patch.object(tx, "_capture_node", side_effect=primary):
            with self.assertRaises(OSError) as caught:
                tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
        self.assertIs(caught.exception, primary)
        self.assertEqual((primary.args, primary.__cause__, primary.__context__), chain)
        context = PI._copy_setter_detail(primary)
        self.assertEqual(context.stage, "identity-acquisition")
        self.assertEqual(PI._copy_setter_operation_errors(primary), ())
        self.assertFalse(context.metadata_current)
        self.assertTrue(context.metadata_projected)
        self.assertIsNone(context.identity_old)
        self.assertIsNone(context.identity_vs_old)
        self.assertEqual(context.metadata_vs_projected, ())
        self.assertTrue(participant.unknown)
        self.assertEqual(records, [])

    def test_raw_failure_observation_and_record_order_adds_no_getter(self):
        tx = PI._InstallTransaction([], enabled=False)
        node = tx._capture_node(self.target)
        current = PI._CopyMetadataImage(self.before.st_atime_ns, self.before.st_mtime_ns, None, None)
        desired = replace(current, mtime_ns=self.before.st_mtime_ns + 100)
        participant = PI._CopyMetadataParticipant(node, current, current)
        primary = OSError("completed-observed-operation")
        events = []
        setter = PI._WindowsBoundNode.set_copy_times
        def fault(bound, atime, mtime):
            self.assertTrue(participant.unknown)
            events.append("operation")
            setter(bound, atime, mtime)
            raise primary
        def record(_path, _node):
            self.assertTrue(participant.unknown)
            events.append("record")
        def trace(frame, event, _argument):
            if event == "call" and frame.f_code.co_filename == PI.__file__:
                caller = frame.f_back.f_code.co_name
                if frame.f_code.co_name == "_read_copy_metadata" and caller in ("progress", "_apply_copy_metadata"):
                    events.append("metadata")
                if frame.f_code.co_name == "_capture_node" and caller == "progress":
                    events.append("identity")
            return trace
        try:
            sys.settrace(trace)
            with patch.object(PI._WindowsBoundNode, "set_copy_times", fault):
                with self.assertRaises(OSError) as caught:
                    tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
        finally:
            sys.settrace(None)
        self.assertIs(caught.exception, primary)
        self.assertEqual(events, ["metadata", "operation", "metadata", "identity", "record"])
        self.assertFalse(participant.unknown)
        # Post-record diagnostics retain the immediate pre-setter checkpoint.
        self.assertEqual(PI._copy_setter_detail(primary).scalar_values[1],
                         (current.mtime_ns, desired.mtime_ns, desired.mtime_ns))

    def test_aggregate_inverse_cli_keeps_member_identity_order_and_private_causes(self):
        second = self.root / "second"
        second.write_bytes(b"same")
        os.utime(second, ns=(1_610_000_000_000_000_000,) * 2)
        tx = PI._InstallTransaction([self.target, second], enabled=True, copy_paths=(self.target, second))
        primary = RuntimeError("later-checkpoint")
        setter = PI._WindowsBoundNode.set_copy_times
        failure_objects = [OSError(errno.EIO, "PRIVATE-inverse-token-one"), OSError(errno.EIO, "PRIVATE-inverse-token-two")]
        receipts = []
        settlement = PI._InstallTransaction._settlement_failure
        def observe(*args, **kwargs):
            paths, members, retained_errors = settlement(*args, **kwargs)
            receipts.extend(members)
            return paths, members, retained_errors
        count = 0
        def inverse(bound, atime, mtime):
            nonlocal count
            setter(bound, atime, mtime)
            error = failure_objects[count]
            count += 1
            raise error
        # Keep inverse patch active during context exit, not just the raise.
        def action():
            inverse_patch = patch.object(PI._WindowsBoundNode, "set_copy_times", inverse)
            with patch.object(PI._InstallTransaction, "_settlement_failure", staticmethod(observe)):
                try:
                    with tx:
                        owner = self.owner(tx)
                        owner.copy_file(Path("target"), self.source)
                        owner.copy_file(Path("second"), self.source)
                        inverse_patch.start()
                        raise primary
                finally:
                    inverse_patch.stop()
        result, stderr, escaped = self.through_install(action)
        aggregate = escaped[0]
        self.assertEqual(result, 1)
        self.assertIs(aggregate.cause, primary)
        self.assertEqual(len(aggregate.members), 2)
        self.assertTrue(all(any(member is receipt for receipt in receipts) for member in aggregate.members))
        self.assertEqual([member.ordinal for member in aggregate.members], sorted(member.ordinal for member in aggregate.members))
        self.assertEqual({member.cause for member in aggregate.members}, {str(error) for error in failure_objects})
        self.assertEqual(stderr.count("cleanup-copy-setter="), 2)
        self.assertEqual(stderr.count("direction=inverse"), 2)
        self.assertNotIn("PRIVATE-inverse-token", stderr)
        self.assertNotIn("operation=timestamps", str(aggregate))
        self.assertTrue(aggregate.recovery_path.exists())
        self.assertTrue(all(not item.unknown and item.restored == item.before for item in tx._copy_metadata.values()))

    def test_associated_unavailable_and_unrelated_errors_use_actual_cli_without_noise(self):
        private = "PRIVATE-path-token-xattr-value"
        associated = ValueError(private)
        associated._copy_setter_diagnostic = {"unrecognized": private}
        _paths, members, retained_errors = PI._InstallTransaction._settlement_failure(associated, "snapshot", 2, self.target, "E_CUSTOM_NEW_ID")
        child = PI._InstallFailure("E_CHILD", "child", "original", members=tuple(members))
        _paths, forwarded, retained_errors = PI._InstallTransaction._settlement_failure(child, "backup", 5, self.source, "E_OTHER")
        self.assertIs(forwarded[0], members[0])
        self.assertEqual(forwarded[0].cause, private)
        legacy_member = PI._RollbackFailureMember("snapshot", 2, str(self.target), "E_CUSTOM_NEW_ID", private)
        self.assertEqual(members[0], legacy_member)
        self.assertEqual(hash(members[0]), hash(legacy_member))
        self.assertEqual(repr(members[0]), repr(legacy_member))
        def fail():
            raise child
        result, stderr, escaped = self.through_install(fail)
        self.assertEqual(result, 1)
        self.assertIs(escaped[0], child)
        self.assertIn("cleanup-copy-setter=snapshot:2:E_CUSTOM_NEW_ID:unavailable", stderr)
        self.assertNotIn(private, stderr)
        missing = ValueError("associated detail missing")
        missing._copy_setter_diagnostic = None
        def missing_detail():
            raise missing
        result, stderr, escaped = self.through_install(missing_detail)
        self.assertEqual(result, 1)
        self.assertIs(escaped[0], missing)
        self.assertEqual(stderr, "FAIL: associated detail missing | copy-setter=unavailable\n")
        for error in (ValueError("ordinary legacy failure"),
                      PI._InstallFailure("E_ORDINARY", "old", "primary", members=(PI._RollbackFailureMember("snapshot", 0, "ordinary", "E_OLD", private),))):
            def fail():
                raise error
            result, stderr, _escaped = self.through_install(fail)
            self.assertEqual(result, 1)
            self.assertEqual(stderr, f"FAIL: {error}\n")

    def test_unrelated_record_failure_stays_uninstrumented(self):
        current = PI._CopyMetadataImage(100, 200, None, None)
        desired = PI._CopyMetadataImage(300, 400, None, None)
        tx, node, participant, _records, _record = self.diagnostic_case(current)
        primary = ValueError("record-callback")
        def record(*_args):
            raise primary
        with self.no_timestamp_effect(), patch.object(tx, "_read_copy_metadata", side_effect=[current, desired]):
            with self.assertRaises(ValueError) as caught:
                tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
        self.assertIs(caught.exception, primary)
        self.assertIsNone(PI._copy_setter_detail(primary))
        self.assertEqual(PI._copy_setter_operation_errors(primary), ())
        self.assertTrue(participant.unknown)

    def test_native_exception_storage_bypasses_mutating_foreign_carriage(self):
        hooks = []
        class NativeDictionary(dict):
            def __getitem__(self, key):
                hooks.append("dictionary-read")
                raise RuntimeError("foreign dictionary read")
            def __setitem__(self, key, value):
                hooks.append("dictionary-write")
                raise RuntimeError("foreign dictionary write")
            def __contains__(self, key):
                hooks.append("dictionary-membership")
                raise RuntimeError("foreign dictionary membership")
        class ForeignError(OSError):
            @property
            def __dict__(self):
                hooks.append("dictionary-descriptor")
                raise RuntimeError("foreign dictionary")
            def __getattribute__(self, name):
                if name == "_copy_setter_diagnostic":
                    hooks.append("attribute-read")
                    raise RuntimeError("foreign attribute read")
                return super().__getattribute__(name)
            def __setattr__(self, name, value):
                if name == "_copy_setter_diagnostic":
                    hooks.append("attribute-write")
                    self.args = ("MUTATED-original-args",)
                    self.__cause__ = ValueError("MUTATED-cause")
                    self.__context__ = RuntimeError("MUTATED-context")
                    raise RuntimeError("carriage unsupported")
                super().__setattr__(name, value)
        current = PI._CopyMetadataImage(100, 200, None, None)
        tx, node, participant, _records, record = self.diagnostic_case(current)
        primary = ForeignError(errno.EIO, "foreign-operation")
        BaseException.__dict__["__dict__"].__set__(primary, NativeDictionary())
        primary.__cause__ = ValueError("original-cause")
        primary.__context__ = RuntimeError("original-context")
        original = (primary.args, primary.__cause__, primary.__context__)
        def action():
            with patch.object(PI._WindowsBoundNode, "set_copy_times", side_effect=primary), \
                    patch.object(tx, "_read_copy_metadata", side_effect=[current, current]):
                tx._apply_copy_metadata(self.target, node, current, stat.S_IMODE(node.python_identity[2]), record, participant)
        result, stderr, escaped = self.through_install(action)
        self.assertEqual(result, 1)
        self.assertIs(escaped[0], primary)
        self.assertEqual((primary.args, primary.__cause__, primary.__context__), original)
        self.assertEqual(hooks, [])
        self.assertEqual(PI._copy_setter_detail(primary).operation, "timestamps")
        self.assertIn("stage=operation", stderr)
        self.assertFalse(participant.unknown)

    def test_foreign_inner_diagnostic_fields_are_unavailable_without_dispatch(self):
        hooks = []
        class ForeignLabel(str):
            def __eq__(self, other):
                hooks.append("equality")
                return True
            def __hash__(self):
                hooks.append("hash")
                return str.__hash__(self)
            def __format__(self, spec):
                hooks.append("format")
                return "PRIVATE_FORMAT_SENTINEL"
        ordinary = PI._CopySetterDiagnostic("owner-extension", "forward", "comparison", 1,
                                           True, True, True, True, (), (), (), ())
        malformed = (replace(ordinary, direction=ForeignLabel("forward"), stage=ForeignLabel("comparison")),
                     replace(ordinary, metadata_vs_current=(ForeignLabel("PRIVATE_FIELD_SENTINEL"),)))
        for context in malformed:
            primary = ValueError("associated-original")
            primary._copy_setter_diagnostic = context
            def action():
                raise primary
            result, stderr, escaped = self.through_install(action)
            self.assertEqual(result, 1)
            self.assertIs(escaped[0], primary)
            self.assertEqual(stderr, "FAIL: associated-original | copy-setter=unavailable\n")
        self.assertEqual(hooks, [])
        self.assertIn("operation=owner-extension", ordinary.render())

    def test_owner_behavior_and_namespace_admission_precede_added_rendering(self):
        hooks = []
        class ForeignField(str):
            def __eq__(self, other):
                hooks.append("table-equality")
                return True
        class ForeignKey:
            def __hash__(self):
                return hash("direction")
            def __eq__(self, other):
                hooks.append("namespace-equality")
                return False
        ordinary = PI._CopySetterDiagnostic("owner-extension", "forward", "comparison", 1,
                                           True, True, True, True, (), (), (), ())
        table = replace(ordinary)
        object.__setattr__(table, "_metadata_fields", (ForeignField("PRIVATE_TABLE"),))
        method = replace(ordinary)
        def foreign_render():
            hooks.append("render")
            return "PRIVATE_RENDER"
        object.__setattr__(method, "render", foreign_render)
        collision = replace(ordinary)
        storage = PI._CopySetterDiagnostic.__dict__["__dict__"].__get__(collision)
        original = dict.copy(storage)
        dict.clear(storage)
        dict.__setitem__(storage, ForeignKey(), "synthetic")
        for name, value in dict.items(original):
            dict.__setitem__(storage, name, value)
        hooks.clear()
        for context in (table, method, collision):
            primary = ValueError("owner-original")
            primary._copy_setter_diagnostic = context
            def action():
                raise primary
            result, stderr, escaped = self.through_install(action)
            self.assertEqual(result, 1)
            self.assertIs(escaped[0], primary)
            self.assertNotIn("PRIVATE", stderr)
        self.assertEqual(hooks, [])

    def test_capture_image_namespace_is_passive_before_field_lookup(self):
        hooks = []
        class ForeignKey:
            def __hash__(self):
                return hash("atime_ns")
            def __eq__(self, other):
                hooks.append("metadata-equality")
                return False
        image = PI._CopyMetadataImage(100, 200, None, None)
        storage = PI._CopyMetadataImage.__dict__["__dict__"].__get__(image)
        original = dict.copy(storage)
        dict.clear(storage)
        dict.__setitem__(storage, ForeignKey(), "synthetic")
        for name, value in dict.items(original):
            dict.__setitem__(storage, name, value)
        hooks.clear()
        primary = ValueError("capture-original")
        PI._CopySetterDiagnostic.attach(primary, "timestamps", False, "comparison", 1,
            image, image, (1, 2, 3, 4), (1, 2, 3, 4), image, (1, 2, 3, 4))
        self.assertEqual(hooks, [])
        self.assertEqual(PI._copy_setter_detail(primary), ())

    def test_passive_capture_and_aggregate_carriage_share_the_primitive_boundary(self):
        hooks = []
        class ForeignInteger(int):
            def __eq__(self, other):
                hooks.append("value-equality")
                return True
            def __format__(self, spec):
                hooks.append("value-format")
                return "PRIVATE_INTEGER_SENTINEL"
        current = PI._CopyMetadataImage(100, 200, None, None)
        primary = ValueError("capture-original")
        PI._CopySetterDiagnostic.attach(primary, "timestamps", False, "comparison", 1,
            current, replace(current, flags=ForeignInteger(1)), (1, 2, 3, 4), (1, 2, 3, 4), current, (1, 2, 3, 4))
        self.assertEqual(PI._copy_setter_detail(primary), ())
        class ChildFailure(PI._InstallFailure):
            def __setattr__(self, name, value):
                if name == "_copy_setter_diagnostic":
                    hooks.append("aggregate-write")
                    raise RuntimeError("foreign aggregate write")
                super().__setattr__(name, value)
        child = ChildFailure("E_CHILD", "child", primary)
        self.assertEqual(PI._copy_setter_detail(child), ())
        member = PI._RollbackFailureMember("snapshot", 0, "ordinary", "E_OLD", "raw", ())
        aggregate = PI._InstallFailure("E_AGGREGATE", "rollback", "primary", members=(member,))
        # Keep the original cached base message; only added locator data is malformed.
        object.__setattr__(member, "ordinal", ForeignInteger(0))
        def action():
            raise aggregate
        result, stderr, escaped = self.through_install(action)
        self.assertEqual(result, 1)
        self.assertIs(escaped[0], aggregate)
        self.assertIn("cleanup-copy-setter=unavailable", stderr)
        self.assertEqual(hooks, [])

    def test_later_atime_observations_preserve_assignment_and_beforeimage(self):
        for restored in (False, True):
            with self.subTest(inverse=restored):
                current = PI._CopyMetadataImage(100, 200, None, None)
                desired = replace(current, atime_ns=300, mtime_ns=400)
                later = replace(desired, atime_ns=500)
                final = replace(later, atime_ns=700)
                tx, node, participant, records, record = self.diagnostic_case(current)
                participant.before = desired if restored else current
                before = participant.before
                with self.no_timestamp_effect(), patch.object(tx, "_read_copy_metadata",
                        side_effect=[current, desired, later, final]) as metadata:
                    result = tx._apply_copy_metadata(self.target, node, desired,
                        stat.S_IMODE(node.python_identity[2]), record, participant, restored=restored)
                self.assertIs(result, final)
                self.assertIs(participant.before, before)
                self.assertIs(participant.current, final)
                self.assertIs(participant.restored, final if restored else None)
                self.assertFalse(participant.unknown)
                self.assertEqual(metadata.call_count, 4)
                self.assertEqual(len(records), 2)
                self.assertTrue(all(entry[2] for entry in records))
                self.assertEqual((desired.atime_ns, desired.mtime_ns), (300, 400))

    def test_wrong_mtime_assignment_is_not_a_known_atime_only_observation(self):
        current = PI._CopyMetadataImage(100, 200, None, None)
        desired = replace(current, atime_ns=300, mtime_ns=400)
        wrong = replace(desired, mtime_ns=current.mtime_ns)
        tx, node, participant, records, record = self.diagnostic_case(current)
        with self.no_timestamp_effect(), patch.object(tx, "_read_copy_metadata", side_effect=[current, wrong]):
            with self.assertRaises(ValueError) as caught:
                tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
        self.assertEqual(PI._copy_setter_detail(caught.exception).metadata_vs_projected, ("mtime_ns",))
        self.assertTrue(participant.unknown)
        self.assertEqual(records, [])

    def test_non_time_whole_stable_tuple_rejects_mixed_fields(self):
        current = PI._CopyMetadataImage(100, 200, None, ())
        desired = replace(current, xattrs=(("synthetic", b"value"),))
        mixed = replace(desired, mtime_ns=400)
        tx, node, participant, records, record = self.diagnostic_case(current)
        with patch.object(tx, "_read_copy_metadata", side_effect=[current, mixed]), \
                patch.object(PI.os, "setxattr", create=True), \
                patch.object(PI._WindowsBoundNode, "set_copy_times") as times:
            with self.assertRaises(ValueError):
                tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
        self.assertTrue(participant.unknown)
        self.assertEqual(records, [])
        times.assert_not_called()

    def test_optional_xattr_primary_cannot_hide_foreign_mtime(self):
        current = PI._CopyMetadataImage(100, 200, None, ())
        desired = replace(current, xattrs=(("synthetic", b"value"),))
        foreign = replace(current, mtime_ns=400)
        tx, node, participant, records, record = self.diagnostic_case(current)
        tx._copy_metadata[self.target] = participant
        primary = OSError(errno.EPERM, "xattr-primary")
        primary.__cause__ = RuntimeError("original-cause")
        chain = (primary.args, primary.__cause__, primary.__context__)
        with patch.object(tx, "_read_copy_metadata", side_effect=[current, foreign]), \
                patch.object(PI.os, "setxattr", side_effect=primary, create=True), \
                patch.object(PI._WindowsBoundNode, "set_copy_times") as times, \
                patch.object(PI._InstallTransaction, "_chmod_owned") as mode:
            with self.assertRaises(OSError) as caught:
                tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
        self.assertIs(caught.exception, primary)
        self.assertEqual((primary.args, primary.__cause__, primary.__context__), chain)
        self.assertEqual(PI._copy_setter_detail(primary).stage, "operation")
        self.assertEqual(PI._copy_setter_detail(primary).metadata_vs_current, ("mtime_ns",))
        self.assertTrue(participant.unknown)
        self.assertEqual(records, [])
        times.assert_not_called()
        mode.assert_not_called()
        with self.assertRaisesRegex(ValueError, "unknown"):
            tx._assert_copy_metadata(self.target)

    def test_optional_xattr_policy_does_not_admit_acquisition_identity_or_record_errno(self):
        # These failures share EPERM but originate outside operation(), so none
        # can admit continuation; their recording/diagnostic stages differ.
        for stage in ("metadata", "identity", "record"):
            with self.subTest(stage=stage):
                current = PI._CopyMetadataImage(100, 200, None, ())
                desired = replace(current, xattrs=(("synthetic", b"value"),))
                tx, node, participant, records, record = self.diagnostic_case(current)
                primary = OSError(errno.EPERM, stage + "-primary")
                observed = [current, primary] if stage == "metadata" else [current, desired]
                def recording(path, value):
                    if stage == "record":
                        raise primary
                    record(path, value)
                with patch.object(tx, "_read_copy_metadata", side_effect=observed), \
                        patch.object(PI.os, "setxattr", create=True), \
                        patch.object(tx, "_capture_node", side_effect=primary if stage == "identity" else None,
                                     return_value=node), \
                        patch.object(PI._WindowsBoundNode, "set_copy_times") as times, \
                        patch.object(PI._InstallTransaction, "_chmod_owned") as mode:
                    with self.assertRaises(OSError) as caught:
                        tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), recording, participant)
                self.assertIs(caught.exception, primary)
                context = PI._copy_setter_detail(primary)
                if stage == "record":
                    self.assertIsNone(context)
                else:
                    self.assertEqual(context.stage, stage + "-acquisition")
                self.assertTrue(participant.unknown)
                self.assertEqual(records, [])
                times.assert_not_called()
                mode.assert_not_called()

    def test_final_failure_retains_known_prefix_without_success(self):
        for acquisition in (True, False):
            with self.subTest(acquisition=acquisition):
                current = PI._CopyMetadataImage(100, 200, None, None)
                desired = replace(current, atime_ns=300, mtime_ns=400)
                tx, node, participant, records, record = self.diagnostic_case(current)
                primary = OSError(errno.EPERM, "final-acquisition")
                final = primary if acquisition else replace(desired, mtime_ns=600)
                with self.no_timestamp_effect(), patch.object(tx, "_read_copy_metadata",
                        side_effect=[current, desired, desired, final]):
                    with self.assertRaises(OSError if acquisition else ValueError) as caught:
                        tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
                if acquisition:
                    self.assertIs(caught.exception, primary)
                else:
                    self.assertIn("final copy metadata drift", str(caught.exception))
                self.assertFalse(participant.unknown)
                self.assertIs(participant.current, desired)
                self.assertEqual(len(records), 2)

    def test_optional_xattr_foreign_effect_retains_guarded_transaction_recovery(self):
        reader = PI._InstallTransaction._read_copy_metadata
        source_inode = self.source.stat().st_ino
        primary = OSError(errno.EPERM, "xattr-foreign-primary")
        foreign_mtime = 1_750_000_000_000_000_000
        def observation(metadata, descriptor, bound):
            image = reader(metadata, descriptor, bound)
            return replace(image, xattrs=(("synthetic", b"value"),) if metadata.st_ino == source_inode else ())
        def foreign_effect(*_args):
            os.utime(self.target, ns=(self.before.st_atime_ns, foreign_mtime))
            raise primary
        transaction = self.transaction()
        with patch.object(PI._InstallTransaction, "_read_copy_metadata", staticmethod(observation)), \
                patch.object(PI.os, "setxattr", side_effect=foreign_effect, create=True), \
                patch.object(PI._WindowsBoundNode, "set_copy_times") as times, \
                patch.object(PI._InstallTransaction, "_chmod_owned", wraps=PI._InstallTransaction._chmod_owned) as mode:
            with self.assertRaises(PI._InstallFailure) as caught:
                with transaction:
                    # Snapshot acquisition has its own mandatory chmod; observe
                    # that real producer and count only following copy setters.
                    mode.reset_mock()
                    self.owner(transaction).copy_file(Path("target"), self.source)
        self.assertIs(caught.exception.cause, primary)
        self.assertTrue(transaction._copy_metadata[self.target].unknown)
        self.assertIsNotNone(caught.exception.recovery_path)
        self.assertTrue(caught.exception.recovery_path.exists())
        self.assertEqual(self.target.stat().st_mtime_ns, foreign_mtime)
        times.assert_not_called()
        mode.assert_not_called()

    def test_same_xattr_errno_continues_forward_and_escapes_inverse(self):
        for restored in (False, True):
            with self.subTest(inverse=restored):
                current = PI._CopyMetadataImage(100, 200, None, ())
                desired = replace(current, xattrs=(("PRIVATE-xattr-name", b"PRIVATE-value"),))
                tx, node, participant, records, record = self.diagnostic_case(current)
                participant.before = desired if restored else current
                primary = OSError(errno.EPERM, "xattr-denied")
                with self.no_timestamp_effect(), patch.object(tx, "_read_copy_metadata", return_value=current), \
                        patch.object(PI.os, "setxattr", side_effect=primary, create=True):
                    if restored:
                        with self.assertRaises(OSError) as caught:
                            tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant, restored=True)
                        self.assertIs(caught.exception, primary)
                        self.assertEqual(len(records), 1)
                    else:
                        actual = tx._apply_copy_metadata(self.target, node, desired, stat.S_IMODE(node.python_identity[2]), record, participant)
                        self.assertEqual(actual, current)
                        self.assertEqual(len(records), 3)
                context = PI._copy_setter_detail(primary)
                self.assertEqual(context.operation, "xattr-set")
                self.assertEqual(context.direction, "inverse" if restored else "forward")
                self.assertEqual(context.metadata_vs_projected, ("xattrs",))
                self.assertNotIn("PRIVATE", context.render())
                self.assertFalse(participant.unknown)


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
        self.assertEqual(transaction._remaining_recovery(), (None, [], [], ()))
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
        self.assertEqual(transaction._remaining_recovery(), (None, [], [], ()))

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
            if records and all(row.kind == "directory" for row in records) and result == ([], [], ()):
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
        paths, members, retained_errors = PI._InstallTransaction._settlement_failure(child, "created", 9, self.absent,
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
                self.assertEqual(transaction._remaining_recovery(), (None, [], [], ()))
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
        with _synthetic_native_byte_lock(backup), patch.object(transaction, "_commit_migrated", return_value=([sentinel_path], [sentinel], ())):
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
                selected, unresolved, failures, retained_errors = transaction._remaining_recovery()
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
            selected, unresolved, failures, retained_errors = transaction._remaining_recovery()
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
            selected, unresolved, failures, retained_errors = transaction._remaining_recovery()
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
        self.assertEqual(transaction._remaining_recovery(), (None, [], [], ()))

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


class ScalarLinkedTraversalTests(unittest.TestCase):
    setUp = CreatedDirectorySnapshotHandoffTests.setUp

    def link(self, path, target, *, directory=False):
        try:
            path.symlink_to(target, target_is_directory=directory)
        except OSError as exc:
            self.skipTest(f"scalar symlink unavailable: {exc}")

    def test_actual_file_parent_alias_linked_leaf_and_missing_suffix_contracts(self):
        storage = self.root / "storage"
        storage.mkdir()
        file = storage / "data.bin"
        file.write_bytes(b"actual scalar payload")
        alias = self.root / "alias"
        self.link(alias, storage, directory=True)
        linked = storage / "selected.link"
        self.link(linked, Path("data.bin"))
        transaction = PI._InstallTransaction([], enabled=True)
        cases = (
            (file, file, file, False),
            (alias / "data.bin", file, file, False),
            (alias / "selected.link", file, linked, False),
            (alias / "missing.bin", storage / "missing.bin", storage / "missing.bin", True),
            (alias / "absent/nested/new.bin", storage / "absent/nested/new.bin", storage / "absent/nested/new.bin", True),
        )
        for logical, expected, selected_leaf, missing in cases:
            with self.subTest(logical=logical):
                actual, origin, components, leaf = transaction._bind_scalar_storage(logical)
                self.assertEqual(actual, expected)
                self.assertEqual(leaf, selected_leaf)
                self.assertEqual(origin is None, missing)
                if not missing:
                    self.assertEqual(actual, logical.resolve(strict=True))
                    self.assertEqual(origin, transaction._capture_node(file))
                    self.assertEqual(origin.data, hashlib.sha256(b"actual scalar payload").hexdigest())
                    if os.name == "nt":
                        self.assertIsNotNone(origin.native_proof)
                self.assertTrue(components)
                for path, node in components:
                    self.assertEqual(node, transaction._capture_node(path))
                if logical != file:
                    self.assertIn(alias, dict(components))
                if logical == alias / "selected.link":
                    self.assertEqual(dict(components)[linked].data, os.readlink(linked))
                if missing:
                    self.assertFalse(actual.exists())
                    self.assertNotIn(storage / "absent", dict(components))
        self.assertEqual(file.read_bytes(), b"actual scalar payload")

    @unittest.skipUnless(os.name == "nt", "native file-id proof is Windows-specific")
    def test_scalar_binding_rechecks_full_native_proof_not_only_python_identity(self):
        file, other = self.root / "file", self.root / "other"
        file.write_bytes(b"same")
        other.write_bytes(b"same")
        transaction = PI._InstallTransaction([], enabled=True)
        capture = transaction._capture_node
        foreign_proof = capture(other).native_proof
        original = capture(file)
        self.assertNotEqual(original.native_proof, foreign_proof)
        def wrong_proof(path, **kwargs):
            node = capture(path, **kwargs)
            return replace(node, native_proof=foreign_proof) if path == file else node
        with patch.object(transaction, "_capture_node", wrong_proof):
            with self.assertRaisesRegex(ValueError, "E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY: scalar pointer drift"):
                transaction._bind_scalar_storage(file)
        self.assertEqual(capture(file), original)

    def test_same_endpoint_raw_link_retarget_during_native_receiving_refuses(self):
        file, link = self.root / "data.bin", self.root / "selected.link"
        file.write_bytes(b"untouched referent")
        self.link(link, Path("data.bin"))
        transaction = PI._InstallTransaction([], enabled=True)
        capture = transaction._capture_node
        changed = []
        def retarget_after_capture(path, **kwargs):
            node = capture(path, **kwargs)
            if path == link and not changed:
                link.unlink()
                self.link(link, "." + os.sep + "data.bin")
                changed.append(True)
            return node
        with patch.object(transaction, "_capture_node", retarget_after_capture):
            with self.assertRaisesRegex(ValueError, "E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY: scalar raw target"):
                transaction._bind_scalar_storage(link)
        self.assertEqual(changed, [True])
        self.assertEqual(link.resolve(strict=True), file)
        self.assertEqual(file.read_bytes(), b"untouched referent")

    def test_scalar_readlink_failure_after_lstat_remains_native_failure(self):
        file, link = self.root / "file", self.root / "link"
        file.write_bytes(b"untouched")
        self.link(link, file)
        transaction = PI._InstallTransaction([], enabled=True)
        primary = FileNotFoundError("link vanished during readlink")
        with patch.object(PI.os, "readlink", side_effect=primary):
            with self.assertRaises(FileNotFoundError) as caught:
                transaction._bind_scalar_storage(link)
        self.assertIs(caught.exception, primary)
        self.assertEqual(file.read_bytes(), b"untouched")


if __name__ == "__main__":
    unittest.main()

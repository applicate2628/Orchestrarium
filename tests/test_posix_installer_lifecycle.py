"""Assembled POSIX installer qualification with explicit admission substitution.

No public admission, live profile, model invocation or CI job is enabled here.
"""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix", "Requires native POSIX filesystem")
class PosixInstallerLifecycleTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("lifecycle_installer", ROOT / "scripts/production_installer.py")
        self.module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.module
        spec.loader.exec_module(self.module)
        # Caller provides an authorized fixture root and handles trash disposition.
        self.root = Path(tempfile.mkdtemp(prefix="installer-lifecycle-"))
        self.project = self.root / "project"
        self.project.mkdir()
        self.home = self.root / "home"
        self.home.mkdir()
        self.staging = self.root / "staging"
        self.staging.mkdir()
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.dict(os.environ, {"HOME": str(self.home)}))
        self.stack.enter_context(patch.object(self.module.tempfile, "tempdir", str(self.staging)))

    def invoke(self, provider, *extra):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            result = self.module.install(provider, ["--target", str(self.project),
                "--allow-unsafe-target", "--no-hypothesis-hook", *extra])
        return result, output.getvalue()

    def test_public_hold_still_precedes_target_and_staging(self):
        with patch.object(self.module, "_target", side_effect=AssertionError("target reached")):
            code, output = self.invoke("codex")
        self.assertEqual(code, 1)
        self.assertIn("E_POSIX_DISPOSAL_UNQUALIFIED", output)
        self.assertEqual(list(self.staging.iterdir()), [])
        self.assertEqual(list(self.project.iterdir()), [])

    def test_codex_fresh_timestamp_failure_rolls_back_cleanly(self):
        marker = self.project / "user.txt"
        marker.write_bytes(b"preserve user content")
        reader = self.module._InstallTransaction._read_copy_metadata
        injected = []
        def acquire(metadata, descriptor, bound, **kwargs):
            if not injected and bound is None and sys._getframe(1).f_code.co_name == "operation":
                # Controlled unexpected assignment on the real held descriptor.
                os.utime(descriptor, ns=(1_600_000_000_000_000_000, 1_600_000_000_000_000_000))
                metadata = os.fstat(descriptor)
                injected.append(True)
            return reader(metadata, descriptor, bound, **kwargs)
        with patch.object(self.module, "_installer_platform_admitted", lambda: True), \
                patch.object(self.module, "_require_transaction_disposal_backend", lambda: None), \
                patch.object(self.module._InstallTransaction, "_read_copy_metadata", staticmethod(acquire)):
            code, output = self.invoke("codex")
        self.assertEqual(code, 1, output[-12000:])
        self.assertEqual(injected, [True])
        self.assertIn("copy-setter=operation=timestamps", output)
        self.assertNotIn("E_ROLLBACK_SETTLEMENT_FAILED", output)
        self.assertNotIn("cleanup-detail=", output)
        self.assertEqual(list(self.staging.iterdir()), [])
        self.assertEqual(marker.read_bytes(), b"preserve user content")
        self.assertEqual(list(self.project.rglob("*")), [marker])


    def assert_timestamp_outcome(self, *, late_drift=False):
        from dataclasses import replace
        import stat
        tx = self.module._InstallTransaction([], enabled=False)
        path = self.root / "timestamp-target"
        path.write_bytes(b"preserve bytes")
        node = tx._capture_node(path)
        with tx._copy_reference(path, node, metadata_only=True) as (fd, bound):
            before = tx._read_copy_metadata(os.fstat(fd), fd, bound)
        desired = replace(before, atime_ns=1_650_000_000_123_456_700,
                          mtime_ns=1_650_000_000_223_456_700)
        participant = self.module._CopyMetadataParticipant(node, before, before)
        records = []
        reader = tx._read_copy_metadata
        observed = []
        def acquire(metadata, descriptor, bound, **kwargs):
            if sys._getframe(1).f_code.co_name == "operation":
                # Explicit filesystem-quantization intervention, not native acceptance.
                os.utime(descriptor, ns=(1_650_000_000_000_000_000, 1_650_000_000_000_000_000))
                metadata = os.fstat(descriptor)
            if late_drift and observed and sys._getframe(1).f_code.co_name == "progress":
                os.utime(descriptor, ns=(1_660_000_000_000_000_000, 1_660_000_000_000_000_000))
                metadata = os.fstat(descriptor)
            result = reader(metadata, descriptor, bound, **kwargs)
            if sys._getframe(1).f_code.co_name == "operation":
                observed.append(result)
            return result
        with patch.object(tx, "_read_copy_metadata", acquire):
            with self.assertRaisesRegex(ValueError, "unknown copy setter effect" if late_drift else "copy metadata readback"):
                tx._apply_copy_metadata(path, node, desired, stat.S_IMODE(node.python_identity[2]),
                    lambda path, image: records.append(image), participant, fresh_copy=True)
        self.assertEqual(len(records), 0 if late_drift else 1)
        if not late_drift:
            self.assertEqual(participant.current, observed[0])
        self.assertEqual(participant.unknown, late_drift)
        self.assertNotEqual(participant.current, desired)
        self.assertEqual(path.read_bytes(), b"preserve bytes")


    def test_unrequested_timestamp_image_is_recorded_but_not_accepted(self):
        self.assert_timestamp_outcome()

    def test_later_timestamp_drift_stays_unknown(self):
        self.assert_timestamp_outcome(late_drift=True)


    def test_repeated_transaction_born_copy_keeps_representability(self):
        target = self.project / "copied"
        source = ROOT / "AGENTS.md"
        tx = self.module._InstallTransaction([target], enabled=True, copy_paths=(target,))
        with patch.object(self.module, "_require_transaction_disposal_backend", lambda: None):
            with tx:
                owner = self.module._CreateOnlyMutablePath(self.project, tx, dry_run=False)
                owner.copy_file(Path("copied"), source)
                self.assertIsNone(tx._copy_metadata[target].origin)
                self.assertIsNone(tx._copy_metadata[target].before)
                owner.copy_file(Path("copied"), source)
                tx.commit()
        self.assertEqual(target.read_bytes(), source.read_bytes())
        self.assertEqual(list(self.project.iterdir()), [target])

    def test_moved_original_without_creator_witness_stays_exact(self):
        target = self.project / "copied"
        original = self.project / "original"
        source = self.root / "source"
        source.write_bytes(b"original bytes")
        original.write_bytes(b"original bytes")
        tx = self.module._InstallTransaction([original, target], enabled=True, copy_paths=(target,))
        observed = []
        def metadata(path, node, desired, mode, record, participant, **kwargs):
            observed.append(kwargs["fresh_copy"])
            return participant.current
        with patch.object(self.module, "_require_transaction_disposal_backend", lambda: None):
            with tx:
                image = dict(tx._expected[original])
                original.rename(target)
                tx._moved(original, target, image, None)
                participant = tx._copy_metadata[target]
                self.assertIsNone(participant.origin)
                self.assertIsNone(participant.before)
                self.assertIsNone(participant.created_origin)
                owner = self.module._CreateOnlyMutablePath(self.project, tx, dry_run=False)
                with patch.object(tx, "_apply_copy_metadata", metadata):
                    owner.copy_file(Path("copied"), source)
                tx.commit()
        self.assertEqual(observed, [False])
        self.assertEqual(target.read_bytes(), b"original bytes")

    def test_transaction_born_same_bytes_foreign_inode_refuses(self):
        target = self.project / "copied"
        source = self.root / "source"
        source.write_bytes(b"same bytes")
        refused = []
        tx = self.module._InstallTransaction([target], enabled=True, copy_paths=(target,))
        with patch.object(self.module, "_require_transaction_disposal_backend", lambda: None):
            with self.assertRaises(self.module._InstallFailure) as outcome:
                with tx:
                    owner = self.module._CreateOnlyMutablePath(self.project, tx, dry_run=False)
                    owner.copy_file(Path("copied"), source)
                    target.rename(self.root / "displaced")
                    target.write_bytes(b"same bytes")
                    with self.assertRaisesRegex(ValueError, "E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY"):
                        owner.copy_file(Path("copied"), source)
                    refused.append(True)
                    raise RuntimeError("foreign replacement retained")
        self.assertEqual(refused, [True], repr(outcome.exception))
        self.assertEqual(target.read_bytes(), b"same bytes")
        self.assertEqual((self.root / "displaced").read_bytes(), b"same bytes")

    def test_existing_copy_restores_original_bytes_and_exact_times(self):
        target = self.project / "original"
        target.write_bytes(b"user original")
        os.utime(target, ns=(1_600_000_000_000_000_000, 1_600_000_001_000_000_000))
        before = target.stat()
        tx = self.module._InstallTransaction([target], enabled=True, copy_paths=(target,))
        with patch.object(self.module, "_require_transaction_disposal_backend", lambda: None):
            with self.assertRaisesRegex(RuntimeError, "later failure"):
                with tx:
                    owner = self.module._CreateOnlyMutablePath(self.project, tx, dry_run=False)
                    owner.copy_file(Path("original"), ROOT / "AGENTS.md")
                    self.assertEqual(target.read_bytes(), (ROOT / "AGENTS.md").read_bytes())
                    raise RuntimeError("later failure")
        after = target.stat()
        self.assertEqual((after.st_atime_ns, after.st_mtime_ns), (before.st_atime_ns, before.st_mtime_ns))
        self.assertEqual(target.read_bytes(), b"user original")

    def test_unrestorable_original_refuses_before_byte_write(self):
        target = self.project / "original"
        target.write_bytes(b"user original")
        tx = self.module._InstallTransaction([target], enabled=True, copy_paths=(target,))
        with patch.object(self.module, "_require_transaction_disposal_backend", lambda: None):
            with self.assertRaisesRegex(ValueError, "original timestamps not restorable"):
                with tx:
                    owner = self.module._CreateOnlyMutablePath(self.project, tx, dry_run=False)
                    with patch.object(tx, "_representable_copy_times", return_value=(-1, -1)), \
                            patch.object(tx, "_write_owned_file", side_effect=AssertionError("destructive write reached")):
                        owner.copy_file(Path("original"), ROOT / "AGENTS.md")
        self.assertEqual(target.read_bytes(), b"user original")

    def test_existing_preflight_metadata_drift_refuses_before_write(self):
        target = self.project / "original"
        target.write_bytes(b"user original")
        os.utime(target, ns=(1_600_000_000_000_000_000, 1_600_000_001_000_000_000))
        tx = self.module._InstallTransaction([target], enabled=True, copy_paths=(target,))
        refused = []
        def drift(path, descriptor, pair):
            os.utime(target, ns=(1_610_000_000_000_000_000, 1_610_000_001_000_000_000))
            return pair
        with patch.object(self.module, "_require_transaction_disposal_backend", lambda: None):
            with self.assertRaises(self.module._InstallFailure):
                with tx:
                    owner = self.module._CreateOnlyMutablePath(self.project, tx, dry_run=False)
                    with patch.object(tx, "_representable_copy_times", drift), \
                            patch.object(tx, "_write_owned_file", side_effect=AssertionError("destructive write reached")):
                        try:
                            owner.copy_file(Path("original"), ROOT / "AGENTS.md")
                        except ValueError as error:
                            self.assertIn("copy stable metadata drift", str(error))
                            refused.append(True)
                            raise
        self.assertEqual(refused, [True])
        self.assertEqual(target.read_bytes(), b"user original")
        self.assertEqual(target.stat().st_mtime_ns, 1_610_000_001_000_000_000)

    def test_exact_original_metadata_does_not_call_setters(self):
        import stat
        target = self.project / "original"
        target.write_bytes(b"user original")
        tx = self.module._InstallTransaction([], enabled=False)
        node = tx._capture_node(target)
        with tx._copy_reference(target, node, metadata_only=True) as (fd, bound):
            current = tx._read_copy_metadata(os.fstat(fd), fd, bound)
        participant = self.module._CopyMetadataParticipant(node, current, current)
        with patch.object(os, "utime", side_effect=AssertionError("timestamp setter reached")), \
                patch.object(tx, "_chmod_owned", side_effect=AssertionError("mode setter reached")):
            result = tx._apply_copy_metadata(target, node, current, stat.S_IMODE(node.python_identity[2]),
                lambda path, image: None, participant, restored=True)
        self.assertEqual(result, current)
        self.assertEqual(participant.restored, current)
        # A representable time pair lets the changed-mode case reach its setter.
        os.utime(target, ns=(1_600_000_000_000_000_000, 1_600_000_001_000_000_000))
        tx = self.module._InstallTransaction([], enabled=False)
        with tx._copy_reference(target, node, metadata_only=True) as (fd, bound):
            current = tx._read_copy_metadata(os.fstat(fd), fd, bound)
        participant = self.module._CopyMetadataParticipant(node, current, current)
        with patch.object(tx, "_chmod_owned", side_effect=RuntimeError("mode change reached")):
            with self.assertRaisesRegex(RuntimeError, "mode change reached"):
                tx._apply_copy_metadata(target, node, current, stat.S_IMODE(node.python_identity[2]) ^ stat.S_IXUSR,
                    lambda path, image: None, participant)

    def test_probe_rejects_each_independently_stuck_timestamp(self):
        real = os.utime
        for stuck in (0, 1):
            with self.subTest(stuck=stuck):
                target = self.root / ("probe-target-" + str(stuck))
                target.write_bytes(b"preserved")
                tx = self.module._InstallTransaction([], enabled=False)
                fd = os.open(target, os.O_RDWR)
                def setter(descriptor, *, ns):
                    pair = list(ns)
                    pair[stuck] = 0
                    real(descriptor, ns=tuple(pair))
                try:
                    with patch.object(self.module, "_require_transaction_disposal_backend", lambda: None), patch.object(os, "utime", setter):
                        with self.assertRaisesRegex(ValueError, "probe reproducibility"):
                            tx._representable_copy_times(target, fd, (1_650_000_000_123_456_700, 1_650_000_001_223_456_700))
                    self.assertEqual(list(self.root.glob(".timestamp-*")), [])
                    self.assertEqual(target.read_bytes(), b"preserved")
                finally:
                    os.close(fd)

    def test_fresh_timestamp_representation_preserves_content(self):
        from dataclasses import replace
        import stat
        target = self.root / "fresh"
        target.write_bytes(b"fresh bytes")
        tx = self.module._InstallTransaction([], enabled=False)
        node = tx._capture_node(target)
        with tx._copy_reference(target, node, metadata_only=True) as (fd, bound):
            current = tx._read_copy_metadata(os.fstat(fd), fd, bound)
        desired = replace(current, atime_ns=1_650_000_000_123_456_700, mtime_ns=1_650_000_001_223_456_700)
        participant = self.module._CopyMetadataParticipant(None, None, current)
        with patch.object(self.module, "_require_transaction_disposal_backend", lambda: None):
            actual = tx._apply_copy_metadata(target, node, desired, stat.S_IMODE(node.python_identity[2]),
                lambda path, image: None, participant, fresh_copy=True)
        self.assertEqual(actual, participant.current)
        self.assertFalse(participant.unknown)
        self.assertLessEqual(actual.mtime_ns, desired.mtime_ns)
        self.assertEqual(target.read_bytes(), b"fresh bytes")
        self.assertEqual(list(self.root.glob(".timestamp-*")), [])

    def assert_fresh_target_drift(self, *, metadata=False):
        from dataclasses import replace
        import stat
        target = self.root / "changed"
        target.write_bytes(b"fresh bytes")
        tx = self.module._InstallTransaction([], enabled=False)
        node = tx._capture_node(target)
        with tx._copy_reference(target, node, metadata_only=True) as (fd, bound):
            current = tx._read_copy_metadata(os.fstat(fd), fd, bound)
        desired = replace(current, atime_ns=1_650_000_000_123_456_700, mtime_ns=1_650_000_001_223_456_700)
        participant = self.module._CopyMetadataParticipant(None, None, current)
        real = tx._representable_copy_times
        def drift(path, descriptor, requested):
            pair = real(path, descriptor, requested)
            if metadata:
                os.utime(target, ns=(1_600_000_000_000_000_000, 1_600_000_001_000_000_000))
            else:
                target.write_bytes(b"foreign content")
            return pair
        with patch.object(self.module, "_require_transaction_disposal_backend", lambda: None), patch.object(tx, "_representable_copy_times", drift):
            # This fixture requires a genuinely inexact native setter.
            with tx._copy_reference(target, node, metadata_only=True) as (fd, bound):
                pair = real(target, fd, (desired.atime_ns, desired.mtime_ns))
            if pair == (desired.atime_ns, desired.mtime_ns):
                self.skipTest("Native timestamp representation is exact")
            with self.assertRaisesRegex(ValueError, "timestamp target metadata drift" if metadata else "timestamp target drift"):
                tx._apply_copy_metadata(target, node, desired, stat.S_IMODE(node.python_identity[2]),
                    lambda path, image: None, participant, fresh_copy=True)
        self.assertEqual(target.read_bytes(), b"fresh bytes" if metadata else b"foreign content")
        if metadata:
            self.assertEqual(target.stat().st_mtime_ns, 1_600_000_001_000_000_000)
            self.assertTrue(participant.unknown)

    def test_fresh_target_content_drift_during_probe_refuses(self):
        self.assert_fresh_target_drift()

    def test_fresh_target_metadata_drift_during_probe_refuses(self):
        self.assert_fresh_target_drift(metadata=True)


    def test_selected_tree_capability_uses_available_retention_owner(self):
        from types import SimpleNamespace
        target = self.root / "skills"
        target.mkdir()
        plan = SimpleNamespace(skills=(SimpleNamespace(
            name="selected", accepted_prior="a" * 64, managed_before=None),))
        with patch.object(self.module, "_require_transaction_disposal_backend", lambda: None):
            parents = self.module._preflight_directory_move_capabilities(plan, target)
        self.assertEqual(len(parents), 1)
        self.assertEqual(parents[0][0], target)
        self.assertEqual(list(target.iterdir()), [])


    def test_selected_tree_probe_settles_completed_move_before_error(self):
        from types import SimpleNamespace
        target = self.root / "skills"
        target.mkdir()
        plan = SimpleNamespace(skills=(SimpleNamespace(
            name="selected", accepted_prior="a" * 64, managed_before=None),))
        original = self.module._InstallTransaction._publish_retained
        def publish(tx, source, destination, **kwargs):
            result = original(tx, source, destination, **kwargs)
            if kwargs.get("effect") is not None:
                raise RuntimeError("after probe move")
            return result
        with patch.object(self.module, "_require_transaction_disposal_backend", lambda: None), \
                patch.object(self.module._InstallTransaction, "_publish_retained", publish):
            with self.assertRaisesRegex(RuntimeError, "after probe move"):
                self.module._preflight_directory_move_capabilities(plan, target)
        self.assertEqual(list(target.iterdir()), [])

    def test_selected_tree_probe_preserves_foreign_destination(self):
        from types import SimpleNamespace
        target = self.root / "skills"
        target.mkdir()
        plan = SimpleNamespace(skills=(SimpleNamespace(
            name="selected", accepted_prior="a" * 64, managed_before=None),))
        original = self.module._InstallTransaction._publish_retained
        foreign = []
        def publish(tx, source, destination, **kwargs):
            if kwargs.get("effect") is not None:
                destination.mkdir()
                member = destination / "foreign"
                member.write_bytes(b"do not delete")
                foreign.append(member)
            return original(tx, source, destination, **kwargs)
        with patch.object(self.module, "_require_transaction_disposal_backend", lambda: None), \
                patch.object(self.module._InstallTransaction, "_publish_retained", publish):
            with self.assertRaises(self.module._InstallFailure):
                self.module._preflight_directory_move_capabilities(plan, target)
        self.assertEqual(len(foreign), 1)
        self.assertEqual(foreign[0].read_bytes(), b"do not delete")
        self.assertTrue((foreign[0].parent.parent / "source").is_dir())


if __name__ == "__main__":
    unittest.main()

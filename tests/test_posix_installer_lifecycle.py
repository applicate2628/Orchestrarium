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


if __name__ == "__main__":
    unittest.main()

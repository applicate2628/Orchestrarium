"""Bounded API fault tests complement actual Windows security-replay regressions."""
import ctypes
from ctypes import wintypes
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest import mock

from test_windows_tree_security_preservation import installer


class SecurityStreamTests(unittest.TestCase):
    def setUp(self):
        acl = struct.pack('<BBHHH', 2, 0, 8, 0, 0)
        descriptor = struct.pack('<BBHLLLL', 1, 0, 0x8404, 0, 0, 0, 20) + acl
        self.expected = installer._WindowsSecurityImage.from_descriptor(descriptor)
        self.observed = installer._WindowsSecurityImage.from_descriptor(
            descriptor[:2] + struct.pack('<H', 0x8004) + descriptor[4:])
        self.node = installer._WindowsBoundNode(Path('new-synthetic'), purpose='creator')
        self.node.born_path = self.node.path
        self.node.creator_proof = object()
        self.node.handle = 123
        self.calls = []

    def invoke(self, *, denied=False, short=False, abort_fails=False, read_error=None,
               identity_changes=False):
        def write(handle, buffer, size, written, abort, security, context):
            self.calls.append((handle, bool(abort), bool(security), context._obj.value))
            self.assertEqual(handle, self.node.handle)
            if abort:
                self.assertIsNone(buffer)
                self.assertEqual(size, 0)
                return not abort_fails
            self.assertIsNone(context._obj.value)
            payload = ctypes.string_at(buffer, size)
            self.assertEqual(struct.unpack_from('<IIqI', payload),
                             (3, 2, len(self.expected.descriptor), 0))
            self.assertEqual(payload[20:], self.expected.descriptor)
            context._obj.value = 111
            written._obj.value = size - int(short)
            return not denied
        kernel = SimpleNamespace(BackupWrite=mock.Mock(side_effect=write))
        proof = self.node.creator_proof
        with mock.patch.object(installer._WindowsBoundNode, '_api',
                               return_value=(ctypes, wintypes, kernel)), \
             mock.patch.object(installer._WindowsBoundNode, 'proof', new_callable=mock.PropertyMock,
                               side_effect=[proof, object() if identity_changes else proof]), \
             mock.patch.object(installer._WindowsBoundNode, 'security_image',
                               side_effect=read_error, return_value=self.expected), \
             mock.patch.object(ctypes, 'WinError', side_effect=lambda code: OSError(code, 'native fixture'), create=True), \
             mock.patch.object(ctypes, 'get_last_error', side_effect=[5, 87], create=True):
            return self.node.finalize_created_security(self.expected, self.observed)

    def assert_aborted(self):
        self.assertEqual(self.calls, [(123, False, True, None), (123, True, False, 111)])

    def test_security_only_stream_uses_same_handle_and_releases_context(self):
        self.assertEqual(self.invoke(), self.expected)
        self.assert_aborted()

    def test_short_write_refuses_and_releases_context(self):
        with self.assertRaisesRegex(ValueError, 'incomplete security stream'):
            self.invoke(short=True)
        self.assert_aborted()

    def test_write_denial_refuses_and_releases_context(self):
        with self.assertRaises(OSError) as caught:
            self.invoke(denied=True)
        self.assertEqual(caught.exception.errno, 5)
        self.assert_aborted()

    def test_denial_remains_primary_when_abort_also_fails(self):
        with self.assertRaises(installer._InstallFailure) as caught:
            self.invoke(denied=True, abort_fails=True)
        self.assertEqual(caught.exception.cause.errno, 5)
        self.assertIs(caught.exception.__cause__, caught.exception.cause)
        self.assertEqual(caught.exception.recovery_path, self.node.path)
        self.assertIn('87', caught.exception.members[0].cause)
        self.assert_aborted()

    def test_abort_failure_is_not_reported_as_success(self):
        with self.assertRaises(OSError):
            self.invoke(abort_fails=True)
        self.assert_aborted()

    def test_readback_failure_remains_primary_when_abort_also_fails(self):
        primary = RuntimeError('synthetic readback unavailable')
        with self.assertRaises(installer._InstallFailure) as caught:
            self.invoke(read_error=primary, abort_fails=True)
        self.assertIs(caught.exception.cause, primary)
        self.assert_aborted()

    def test_changed_object_identity_refuses_and_releases_context(self):
        with self.assertRaisesRegex(ValueError, 'security creator identity'):
            self.invoke(identity_changes=True)
        self.assert_aborted()

"""Real AST methods/formatter, inert native calls; not Windows qualification."""
import ast
import ctypes
import dataclasses
import errno
import hashlib
from pathlib import Path
import re
import sys
import types
import unittest
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / 'scripts/production_installer.py'

class ProjectionDiagnosticTests(unittest.TestCase):
    def setUp(self):
        tree = ast.parse(SOURCE.read_bytes())
        names = {'_InstallFailure', '_RollbackFailureMember', '_CopySetterDiagnostic',
                 '_passive_owner_storage', '_store_copy_setter_detail', '_copy_setter_detail',
                 '_copy_setter_operation_errors', '_merge_copy_setter_operation_errors',
                 '_retain_copy_setter_operation_errors', '_installer_failure_text'}
        nodes = [n for n in tree.body if isinstance(n, (ast.FunctionDef, ast.ClassDef)) and n.name in names]
        self.assertEqual({n.name for n in nodes}, names)
        nodes += [n for n in tree.body if isinstance(n, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == 'SLICE_A_FAILURE_IDS' for t in n.targets)]
        owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == '_WindowsBoundNode')
        nodes += [n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name in ('set_reparse_data', '__exit__')]
        module = types.ModuleType('_projection_diagnostic_test')
        module.__dict__.update(dataclass=dataclasses.dataclass, field=dataclasses.field,
                              errno=errno, hashlib=hashlib, Path=Path, re=re)
        sys.modules[module.__name__] = module
        self.addCleanup(sys.modules.pop, module.__name__, None)
        future = ast.parse('from __future__ import annotations').body
        exec(compile(ast.Module(body=future+nodes, type_ignores=[]), str(SOURCE), 'exec'), module.__dict__)
        self.m = module
        self.primary = OSError(22, 'PRIVATE_PRIMARY', 'PRIVATE_PATH')
        self.cleanup = OSError(13, 'PRIVATE_CLEANUP')
        self.calls = []

    def owner(self, result=False, close=True, dispatch_error=None):
        def dispatch(*args):
            self.calls.append(args)
            if dispatch_error is not None:
                raise dispatch_error
            return result
        kernel = SimpleNamespace(DeviceIoControl=dispatch, CloseHandle=lambda h: close)
        fake = SimpleNamespace(create_string_buffer=ctypes.create_string_buffer, byref=ctypes.byref,
                               get_last_error=lambda: 1314, WinError=lambda code: self.primary if len(self.calls)==1 else self.cleanup)
        owner = SimpleNamespace(live_handle=200, handle=200, descriptor=None, settlement_primary=None,
                                path=Path('PRIVATE_PATH'), _api=lambda: (fake, SimpleNamespace(DWORD=ctypes.c_uint32), kernel))
        return owner, fake

    def failed_set(self):
        owner, fake = self.owner()
        with self.assertRaises(self.m._InstallFailure) as caught:
            self.m.set_reparse_data(owner, b'PRIVATE_BUFFER')
        error = caught.exception
        self.assertIs(error.cause, self.primary)
        self.assertIs(error.__cause__, self.primary)
        self.assertEqual(self.calls[0][1], 0x900A4)
        return owner, fake, error

    def test_primary_real_formatter(self):
        _, _, error = self.failed_set()
        rendered = self.m._installer_failure_text(error)
        self.assertIn('E_NATIVE_PROJECTION_SET_FAILED | context=projection-set', rendered)
        self.assertIn('errno:22', rendered)
        self.assertNotIn('PRIVATE', rendered)

    def test_actual_close_wrapper_preserves_both_causes(self):
        owner, fake, error = self.failed_set()
        owner._api()[2].CloseHandle = lambda h: False
        fake.WinError = lambda code: self.cleanup
        with self.assertRaises(self.m._InstallFailure) as caught:
            self.m.__exit__(owner, type(error), error, None)
        outer = caught.exception
        self.assertIs(outer.cause, error)
        self.assertIs(outer.members[0].cause_exception, self.cleanup)
        rendered = self.m._installer_failure_text(outer)
        self.assertIn('id:E_NATIVE_PROJECTION_SET_FAILED;context:projection-set;errno:22', rendered)
        self.assertIn('errno:13', rendered)
        self.assertNotIn('PRIVATE', rendered)

    def test_success_unchanged(self):
        owner, _ = self.owner(result=True)
        self.assertIsNone(self.m.set_reparse_data(owner, b'data'))
        self.assertEqual(len(self.calls), 1)

    def test_dispatch_interrupt_not_relabelled(self):
        error = KeyboardInterrupt()
        owner, _ = self.owner(dispatch_error=error)
        with self.assertRaises(KeyboardInterrupt) as caught:
            self.m.set_reparse_data(owner, b'data')
        self.assertIs(caught.exception, error)

    def test_unknown_nested_exception_not_rendered(self):
        class PrivateError(OSError):
            @property
            def winerror(self):
                raise AssertionError('must not access')
        nested = self.m._InstallFailure('E_NATIVE_PROJECTION_SET_FAILED', 'projection-set', PrivateError('PRIVATE'))
        outer = self.m._InstallFailure('E_ROLLBACK_SETTLEMENT_FAILED', 'native-close', nested)
        rendered = self.m._installer_failure_text(outer)
        self.assertIn('errno:unavailable;winerror:unavailable', rendered)
        self.assertNotIn('PRIVATE', rendered)

    @unittest.skipUnless('winerror' in OSError.__dict__, 'native Windows OSError descriptor required')
    def test_native_winerror_descriptor(self):
        self.primary = OSError(22, 'PRIVATE', None, 1314)
        _, _, error = self.failed_set()
        self.assertIn('winerror:1314', self.m._installer_failure_text(error))
        outer = self.m._InstallFailure('E_ROLLBACK_SETTLEMENT_FAILED', 'native-close', error)
        self.assertIn('winerror:1314', self.m._installer_failure_text(outer))

if __name__ == '__main__':
    unittest.main()

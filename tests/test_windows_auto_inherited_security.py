"""Only newly-created fixture ACLs are initialized; no profile permissions change."""
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from test_windows_tree_security_preservation import installer, _apis, _security, _create_protected


def initialize_fixture_auto_inheritance(path):
    kernel, _convert, _render, _get, _attributes = _apis()
    with installer._WindowsBoundNode(path, security=True) as bound:
        image = bound.security_image()
    buffer = ctypes.create_string_buffer(image.descriptor)
    dacl = struct.unpack_from('<I', image.descriptor, 16)[0]
    setter = ctypes.WinDLL('advapi32', use_last_error=True).SetSecurityInfo
    setter.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
    setter.restype = wintypes.DWORD
    # UNPROTECTED processing reads existing security as well as writing it.
    handle = kernel.CreateFileW(str(path), 0x60000, 7, None, 3, 0x2200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        code = setter(handle, 1, 0x20000004, None, None,
                      ctypes.c_void_p(ctypes.addressof(buffer) + dacl), None)
        if code:
            raise ctypes.WinError(code)
    finally:
        kernel.CloseHandle(handle)


@unittest.skipUnless(os.name == 'nt', 'actual Windows security API')
class AutoInheritedSecurityTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='auto-inherited-',
                                         dir=os.environ.get('ORCHE_SECURITY_TEST_ROOT')))
        self.target = self.root / 'installed'
        self.source = self.root / 'source'
        self.target.mkdir(); self.source.mkdir()
        (self.target / 'leaf.txt').write_bytes(b'old')
        (self.source / 'leaf.txt').write_bytes(b'new')
        for path in (self.target, self.target / 'leaf.txt'):
            initialize_fixture_auto_inheritance(path)
        self.previous = {p.relative_to(self.target): _security(p)
                         for p in (self.target, self.target / 'leaf.txt')}
        self.assertTrue(all('AI' in value for value in self.previous.values()))
        self.digest = installer._tree_sha256(self.target)

    def replace(self, transaction):
        owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
        owner.replace_exact_tree(Path('installed'), self.digest, self.source)

    def test_native_replacement_preserves_auto_inheritance(self):
        with installer._InstallTransaction([self.target], enabled=True) as transaction:
            self.replace(transaction)
            self.assertEqual((self.target / 'leaf.txt').read_bytes(), b'new')
            self.assertEqual({p: _security(self.target / p) for p in self.previous}, self.previous)
            transaction.commit()

    def test_moved_file_keeps_its_own_inherited_acl_not_current_parent_acl(self):
        restricted = self.root / 'different-original-parent'
        common = '(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)'
        _create_protected(restricted, directory=True, sddl='D:P' + common + '(A;OICI;FR;;;WD)')
        original = restricted / 'leaf.txt'
        original.write_bytes(b'old')
        initialize_fixture_auto_inheritance(original)
        self.target.rename(self.root / 'retained-base-fixture')
        _create_protected(self.target, directory=True, sddl='D:P' + common + '(A;OICI;FR;;;AU)')
        original.rename(self.target / 'leaf.txt')
        reference = self.target / 'parent-policy-reference.txt'
        reference.write_bytes(b'parent-policy reference')
        initialize_fixture_auto_inheritance(reference)
        with installer._WindowsBoundNode(self.target / 'leaf.txt', security=True) as moved, \
             installer._WindowsBoundNode(reference, security=True) as inherited:
            moved_policy, parent_policy = moved.security_image(), inherited.security_image()
        self.assertTrue(moved_policy.policy[3] & 0x400)
        self.assertNotEqual(moved_policy.policy[2], parent_policy.policy[2])
        reference.rename(self.root / 'retained-parent-policy-reference.txt')
        self.previous = {p: _security(self.target / p) for p in (Path('.'), Path('leaf.txt'))}
        self.digest = installer._tree_sha256(self.target)
        with installer._InstallTransaction([self.target], enabled=True) as transaction:
            self.replace(transaction)
            self.assertEqual((self.target / 'leaf.txt').read_bytes(), b'new')
            self.assertEqual({p: _security(self.target / p) for p in self.previous}, self.previous)
            transaction.commit()

    def test_failure_restores_original_auto_inheritance(self):
        ids = {p: (self.target / p).stat().st_ino for p in self.previous}
        with self.assertRaisesRegex(RuntimeError, 'synthetic rollback'):
            with installer._InstallTransaction([self.target], enabled=True) as transaction:
                self.replace(transaction)
                raise RuntimeError('synthetic rollback')
        self.assertEqual(installer._tree_sha256(self.target), self.digest)
        self.assertEqual({p: (self.target / p).stat().st_ino for p in self.previous}, ids)
        self.assertEqual({p: _security(self.target / p) for p in self.previous}, self.previous)

    def test_denied_finalization_preserves_original_objects(self):
        ids = {p: (self.target / p).stat().st_ino for p in self.previous}
        original = installer._WindowsBoundNode.finalize_created_security
        def denied(node, expected, observed):
            if expected != observed:
                raise PermissionError('synthetic finalization denied')
            return original(node, expected, observed)
        with mock.patch.object(installer._WindowsBoundNode, 'finalize_created_security', denied):
            with self.assertRaisesRegex(PermissionError, 'synthetic finalization denied'):
                with installer._InstallTransaction([self.target], enabled=True) as transaction:
                    self.replace(transaction)
        self.assertEqual(installer._tree_sha256(self.target), self.digest)
        self.assertEqual({p: (self.target / p).stat().st_ino for p in self.previous}, ids)
        self.assertEqual({p: _security(self.target / p) for p in self.previous}, self.previous)


    def test_failure_after_security_mutation_retains_owned_stage(self):
        ids = {p: (self.target / p).stat().st_ino for p in self.previous}
        original = installer._WindowsBoundNode.finalize_created_security
        changed = []
        def interrupted(node, expected, observed):
            result = original(node, expected, observed)
            if result != observed:
                changed.append(node.path)
                raise OSError('synthetic failure after security mutation')
            return result
        with mock.patch.object(installer._WindowsBoundNode, 'finalize_created_security', interrupted):
            with self.assertRaises(installer._InstallFailure) as caught:
                with installer._InstallTransaction([self.target], enabled=True) as transaction:
                    self.replace(transaction)
        self.assertTrue(changed)
        self.assertEqual(caught.exception.stable_id, 'E_ROLLBACK_SETTLEMENT_FAILED')
        # recovery_path names a verified beforeimage, not an unsafe stage.
        stage = changed[0]
        self.assertIn(stage, caught.exception.unresolved_paths)
        self.assertTrue(any(Path(member.path) == stage for member in caught.exception.members))
        self.assertTrue(stage.is_dir())
        self.assertIn(str(stage), str(caught.exception))
        self.assertEqual(installer._tree_sha256(self.target), self.digest)
        self.assertEqual({p: (self.target / p).stat().st_ino for p in self.previous}, ids)
        self.assertEqual({p: _security(self.target / p) for p in self.previous}, self.previous)


    def test_wrong_policy_readback_cannot_commit(self):
        ids = {p: (self.target / p).stat().st_ino for p in self.previous}
        original = installer._WindowsBoundNode.finalize_created_security
        injected = []
        def wrong_readback(node, expected, observed):
            result = original(node, expected, observed)
            if result != observed:
                injected.append(node.path)
                return installer._WindowsSecurityImage(result.descriptor,
                    (*result.policy[:3], result.policy[3] ^ 0x1000))
            return result
        with mock.patch.object(installer._WindowsBoundNode, 'finalize_created_security', wrong_readback):
            with self.assertRaises(installer._InstallFailure) as caught:
                with installer._InstallTransaction([self.target], enabled=True) as transaction:
                    self.replace(transaction)
                    transaction.commit()
        self.assertTrue(injected)
        self.assertEqual(caught.exception.stable_id, 'E_ROLLBACK_SETTLEMENT_FAILED')
        # recovery_path names a verified beforeimage, not an unsafe stage.
        stage = injected[0]
        self.assertIn(stage, caught.exception.unresolved_paths)
        self.assertTrue(any(Path(member.path) == stage for member in caught.exception.members))
        self.assertTrue(stage.is_dir())
        self.assertIn(str(stage), str(caught.exception))
        self.assertEqual(installer._tree_sha256(self.target), self.digest)
        self.assertEqual({p: (self.target / p).stat().st_ino for p in self.previous}, ids)
        self.assertEqual({p: _security(self.target / p) for p in self.previous}, self.previous)


class CreationSecurityGuardTests(unittest.TestCase):
    def test_non_ai_policy_changes_never_call_setter(self):
        expected = installer._WindowsSecurityImage(b'', (b'owner', b'group', b'acl', 0x404))
        cases = [(b'other', b'group', b'acl', 4),
                 (b'owner', b'other', b'acl', 4),
                 (b'owner', b'group', b'changed-acl', 4),
                 (b'owner', b'group', b'acl', 0x1004),
                 (b'owner', b'group', b'acl', 0)]
        node = installer._WindowsBoundNode(Path('synthetic'), purpose='creator')
        node.born_path = node.path; node.creator_proof = object()
        with mock.patch.object(installer._WindowsBoundNode, 'proof',
                               new_callable=mock.PropertyMock, return_value=node.creator_proof), \
             mock.patch.object(installer._WindowsBoundNode, '_api', side_effect=AssertionError('setter forbidden')):
            for policy in cases:
                observed = installer._WindowsSecurityImage(b'', policy)
                self.assertIs(node.finalize_created_security(expected, observed), observed)
            observed = installer._WindowsSecurityImage(b'', (b'owner', b'group', b'acl', 4))
            node.purpose = 'observe'
            self.assertIs(node.finalize_created_security(expected, observed), observed)
            node.purpose = 'creator'; node.born_path = None
            self.assertIs(node.finalize_created_security(expected, observed), observed)

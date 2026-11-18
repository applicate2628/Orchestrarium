"""Windows replacement must retain destination access policy before publication.

Only synthetic trees are used. The fixture creates protected objects directly;
it never changes an existing user's or system object's permissions.
"""
from __future__ import annotations

import ctypes
from contextlib import contextmanager
from ctypes import wintypes
import os
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import production_installer as installer


def _apis():
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    class SecurityAttributes(ctypes.Structure):
        _fields_ = [("length", wintypes.DWORD), ("descriptor", ctypes.c_void_p),
                    ("inherit", wintypes.BOOL)]
    convert = advapi.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = (wintypes.LPCWSTR, wintypes.DWORD,
                        ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p)
    convert.restype = wintypes.BOOL
    render = advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW
    render.argtypes = (ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                       ctypes.POINTER(wintypes.LPWSTR), ctypes.c_void_p)
    render.restype = wintypes.BOOL
    kernel.CreateFileW.argtypes = (wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                                  ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                                  wintypes.HANDLE)
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CreateDirectoryW.argtypes = (wintypes.LPCWSTR, ctypes.c_void_p)
    kernel.CreateDirectoryW.restype = wintypes.BOOL
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = (ctypes.c_void_p,)
    kernel.LocalFree.restype = ctypes.c_void_p
    get = advapi.GetKernelObjectSecurity
    get.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p,
                   wintypes.DWORD, ctypes.POINTER(wintypes.DWORD))
    get.restype = wintypes.BOOL
    return kernel, convert, render, get, SecurityAttributes


def _security(path: Path) -> str:
    """Independent native owner/group/DACL readback, never a product getter."""
    kernel, _convert, render, get, _attributes = _apis()
    handle = kernel.CreateFileW(str(path), 0x20000, 7, None, 3, 0x2200000, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        needed = wintypes.DWORD()
        if get(handle, 7, None, 0, ctypes.byref(needed)):
            raise AssertionError("security query unexpectedly needed no buffer")
        if ctypes.get_last_error() != 122 or not needed.value:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(needed.value)
        if not get(handle, 7, buffer, len(buffer), ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        rendered = wintypes.LPWSTR()
        if not render(buffer, 1, 7, ctypes.byref(rendered), None):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return rendered.value
        finally:
            if kernel.LocalFree(rendered):
                raise ctypes.WinError(ctypes.get_last_error())
    finally:
        if not kernel.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())


def _create_protected(path: Path, *, directory: bool = False, sddl: str | None = None) -> None:
    """Select restrictive security at creation of one new synthetic object."""
    kernel, convert, _render, _get, SecurityAttributes = _apis()
    descriptor = ctypes.c_void_p()
    inheritance = "OICI" if directory else ""
    sddl = sddl or f"D:P(A;{inheritance};FA;;;SY)(A;{inheritance};FA;;;BA)(A;{inheritance};FA;;;OW)"
    if not convert(sddl, 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), descriptor, False)
        if directory:
            if not kernel.CreateDirectoryW(str(path), ctypes.byref(attributes)):
                raise ctypes.WinError(ctypes.get_last_error())
        else:
            handle = kernel.CreateFileW(str(path), 0x40000000, 7,
                                        ctypes.byref(attributes), 1, 0x80, None)
            if handle == ctypes.c_void_p(-1).value:
                raise ctypes.WinError(ctypes.get_last_error())
            if not kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
    finally:
        if kernel.LocalFree(descriptor):
            raise ctypes.WinError(ctypes.get_last_error())



def _change_fixture_dacl(path: Path) -> None:
    """Inject ACL-only drift on a test-created file, never on an installed profile."""
    kernel, convert, _render, _get, _attributes = _apis()
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    setter = advapi.SetKernelObjectSecurity
    setter.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p)
    setter.restype = wintypes.BOOL
    descriptor = ctypes.c_void_p()
    if not convert("D:P(A;;FA;;;OW)", 1, ctypes.byref(descriptor), None):
        raise ctypes.WinError(ctypes.get_last_error())
    handle = None
    try:
        handle = kernel.CreateFileW(str(path), 0x40000, 7, None, 3, 0x200000, None)
        if handle == ctypes.c_void_p(-1).value:
            handle = None
            raise ctypes.WinError(ctypes.get_last_error())
        if not setter(handle, 0x80000004, descriptor):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        if handle is not None and not kernel.CloseHandle(handle):
            raise ctypes.WinError(ctypes.get_last_error())
        if kernel.LocalFree(descriptor):
            raise ctypes.WinError(ctypes.get_last_error())


@unittest.skipUnless(os.name == "nt", "Windows security descriptors")
class WindowsTreeSecurityPreservationTests(unittest.TestCase):
    def setUp(self):
        base = os.environ.get("ORCHE_SECURITY_TEST_ROOT")
        if base:
            Path(base).mkdir(parents=True, exist_ok=True)
        self.root = Path(tempfile.mkdtemp(prefix="tree-security-", dir=base))
        _create_protected(self.root / "installed", directory=True,
                          sddl="D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)(A;OICI;FR;;;WD)")
        self.target = self.root / "installed" / "lead"
        self.target.mkdir()
        self.source = self.root / "source"
        self.source.mkdir()
        self.members = (Path("SKILL.md"), Path("shared/schemas/agent-runs.schema.json"))
        (self.target / "shared").mkdir()
        _create_protected(self.target / "shared/schemas", directory=True)
        (self.source / "shared/schemas").mkdir(parents=True)
        for relative in self.members:
            _create_protected(self.target / relative)
            (self.target / relative).write_bytes(b"old synthetic policy\n")
            (self.source / relative).write_bytes(b"new synthetic policy\n")
        (self.source / "shared/schemas/new.json").write_bytes(b"new synthetic member\n")
        (self.source / "new-root.txt").write_bytes(b"new public synthetic member\n")
        _create_protected(self.target / "shared/mixed.txt", sddl="D:AI(A;;FA;;;OW)(A;;FR;;;AU)")
        (self.target / "shared/mixed.txt").write_bytes(b"old synthetic member\n")
        (self.source / "shared/mixed.txt").write_bytes(b"new synthetic member\n")
        self.old_security = {
            relative: _security(self.target / relative)
            for relative in (Path("."), Path("shared"), Path("shared/schemas"),
                             Path("shared/mixed.txt"), *self.members)
        }
        self.assertIn("D:P", self.old_security[Path("SKILL.md")])
        self.assertNotEqual(self.old_security[Path("SKILL.md")],
                            self.old_security[Path(".")])
        self.assertIn(";;;WD)", self.old_security[Path(".")])
        self.assertNotIn(";;;WD)", self.old_security[Path("SKILL.md")])
        self.expected_digest = installer._tree_sha256(self.target)
        self.original_ids = {p.relative_to(self.target): p.stat().st_ino
                             for p in (self.target, *self.target.rglob("*"))}

    def test_replacement_preserves_protected_file_and_directory_security(self):
        with installer._InstallTransaction([self.target], enabled=True) as transaction:
            owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
            owner.replace_exact_tree(self.target.relative_to(self.root),
                                     self.expected_digest, self.source)
            for relative, previous in self.old_security.items():
                with self.subTest(relative=str(relative)):
                    self.assertEqual(_security(self.target / relative), previous)
            for relative in self.members:
                self.assertEqual((self.target / relative).read_bytes(),
                                 b"new synthetic policy\n")
            self.assertIn(";;;WD)", _security(self.target / "new-root.txt"))
            self.assertNotIn(";;;WD)", _security(self.target / "shared/schemas/new.json"))
            transaction.commit()


    def assert_original(self, *, changed_security: dict[Path, str] | None = None):
        expected = dict(self.old_security)
        expected.update(changed_security or {})
        self.assertEqual(installer._tree_sha256(self.target), self.expected_digest)
        self.assertEqual({p.relative_to(self.target): p.stat().st_ino
                          for p in (self.target, *self.target.rglob("*"))}, self.original_ids)
        self.assertEqual({p: _security(self.target / p) for p in expected}, expected)

    def test_denied_security_capture_preserves_original(self):
        actual = installer._WindowsBoundNode.security_image
        def denied(node):
            if node.path == self.target / "SKILL.md":
                raise PermissionError("synthetic READ_CONTROL refusal")
            return actual(node)
        with mock.patch.object(installer._WindowsBoundNode, "security_image", denied):
            with self.assertRaises(PermissionError):
                with installer._InstallTransaction([self.target], enabled=True) as transaction:
                    owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                    owner.replace_exact_tree(self.target.relative_to(self.root),
                                             self.expected_digest, self.source)
        self.assert_original()

    def test_native_creation_mismatch_refuses_before_retention(self):
        create = installer._WindowsBoundNode.create
        injected = []
        @contextmanager
        def drop_security(path, **kwargs):
            if ".upgrade." in str(path) and path.name == "SKILL.md":
                self.assertIn("security_image", kwargs)
                del kwargs["security_image"]
                injected.append(path)
            with create(path, **kwargs) as node:
                yield node
        with mock.patch.object(installer._WindowsBoundNode, "create", drop_security):
            with self.assertRaisesRegex(ValueError, "file security creation"):
                with installer._InstallTransaction([self.target], enabled=True) as transaction:
                    owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                    owner.replace_exact_tree(self.target.relative_to(self.root),
                                             self.expected_digest, self.source)
        self.assertEqual(len(injected), 1)
        self.assert_original()

    def test_failure_after_retention_restores_original_security(self):
        with self.assertRaisesRegex(RuntimeError, "synthetic publication failure"):
            with installer._InstallTransaction([self.target], enabled=True) as transaction:
                publish = transaction._publish_retained
                def fail_stage(source, target, **kwargs):
                    effect = kwargs.get("effect")
                    if effect is not None and source == effect.prepared_path:
                        raise RuntimeError("synthetic publication failure")
                    return publish(source, target, **kwargs)
                with mock.patch.object(transaction, "_publish_retained", fail_stage):
                    owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                    owner.replace_exact_tree(self.target.relative_to(self.root),
                                             self.expected_digest, self.source)
        self.assert_original()

    def test_failure_after_publication_restores_original_security(self):
        with self.assertRaisesRegex(RuntimeError, "synthetic postpublication failure"):
            with installer._InstallTransaction([self.target], enabled=True) as transaction:
                owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                owner.replace_exact_tree(self.target.relative_to(self.root),
                                         self.expected_digest, self.source)
                self.assertNotEqual(installer._tree_sha256(self.target), self.expected_digest)
                raise RuntimeError("synthetic postpublication failure")
        self.assert_original()

    def test_security_only_drift_is_not_overwritten(self):
        changed = {}
        with self.assertRaises(installer._InstallFailure) as caught:
            with installer._InstallTransaction([self.target], enabled=True) as transaction:
                construct = transaction._construct_exclusive_tree
                def drift_after_stage(*args, **kwargs):
                    result = construct(*args, **kwargs)
                    if kwargs.get("stage"):
                        path = self.target / "SKILL.md"
                        _change_fixture_dacl(path)
                        changed[Path("SKILL.md")] = _security(path)
                    return result
                with mock.patch.object(transaction, "_construct_exclusive_tree", drift_after_stage):
                    owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                    owner.replace_exact_tree(self.target.relative_to(self.root),
                                             self.expected_digest, self.source)
        self.assertIsInstance(caught.exception.cause, ValueError)
        self.assertIn("E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY: replacement drift",
                      str(caught.exception.cause))
        self.assertEqual(set(changed), {Path("SKILL.md")})
        self.assertNotEqual(changed[Path("SKILL.md")], self.old_security[Path("SKILL.md")])
        self.assert_original(changed_security=changed)



    def test_runtime_cache_reconciliation_keeps_security_and_original_custody(self):
        with self.assertRaisesRegex(RuntimeError, "synthetic warm failure"):
            with installer._InstallTransaction([self.target], enabled=True) as transaction:
                owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                owner.replace_exact_tree(self.target.relative_to(self.root),
                                         self.expected_digest, self.source,
                                         ignore_runtime_cache=True)
                effect = transaction._effects[-1]
                sealed = dict(effect.actual)
                cache = self.target / "__pycache__"
                cache.mkdir()
                (cache / "synthetic.pyc").write_bytes(b"settled synthetic cache")
                transaction.assert_effect_current(effect)
                self.assertTrue(all(effect.actual[path] == node
                                    for path, node in sealed.items()))
                raise RuntimeError("synthetic warm failure")
        self.assert_original()
        self.assertTrue(effect.settled)
        self.assertIsNotNone(effect.quarantine_state)
        for relative, previous in self.old_security.items():
            self.assertEqual(_security(effect.quarantine / relative), previous)
        self.assertEqual((effect.quarantine / "__pycache__/synthetic.pyc").read_bytes(),
                         b"settled synthetic cache")

    def test_published_lead_keeps_transport_predecessor_recognition(self):
        with installer._InstallTransaction([self.target], enabled=True) as transaction:
            predecessor = SimpleNamespace(
                canonical_target=self.target.parent,
                canonical_state=tuple(sorted(transaction._observe(self.target).items())))
            transport = SimpleNamespace(predecessor=predecessor)
            skill = SimpleNamespace(
                name="lead", source=self.source,
                source_digest=installer._tree_sha256(self.source),
                installed_digest=self.expected_digest, accepted_prior=self.expected_digest,
                managed_before=None, ignore_runtime_cache=False)
            plan = SimpleNamespace(
                lead_receipt=None, skills=(skill,), nonlead_expected=None,
                transport_stage=transport, stage=SimpleNamespace(path=self.source),
                directory_move_parents=((self.target.parent,
                    installer._CreateOnlyMutablePath._identity(self.target.parent)),))
            owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
            owner.replace_exact_tree(self.target.relative_to(self.root),
                                     self.expected_digest, self.source)
            # Only unrelated transport re-rendering is inert. Real preflight,
            # retained replacement and security currentness remain exercised.
            with mock.patch.object(installer, "_stage_claude_transport_projection",
                                   return_value=transport):
                installer._assert_canonical_skills_plan_current(
                    plan, self.target.parent, root=ROOT,
                    claude_transport_root=self.root / "claude", transaction=transaction)
            transaction.commit()


if __name__ == "__main__":
    unittest.main()

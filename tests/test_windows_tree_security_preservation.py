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

    def test_bound_scalar_rollback_retains_creator_owner_inherited_security(self):
        parent = self.root / "inherited"
        _create_protected(parent, directory=True,
                          sddl="D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)(A;OICIIO;FR;;;CO)")
        paths = tuple(parent / name for name in ("primary.txt", "companion.txt"))
        for path in paths:
            path.write_bytes(f"old {path.name}\n".encode())
        before = {path: (path.stat().st_ino, _security(path), path.read_bytes())
                  for path in paths}
        for _, security, _ in before.values():
            self.assertIn(";FR;;;", security)
            self.assertNotIn(";;;CO)", security)  # CREATOR OWNER mapped to the child owner.

        stop = RuntimeError("late synthetic refusal")
        with self.assertRaises(RuntimeError) as caught:
            with installer._InstallTransaction(list(paths), enabled=True) as transaction:
                owner = installer._CreateOnlyMutablePath(parent, transaction, dry_run=False)
                for path in paths:
                    with transaction.direct_operation():
                        transaction.transform_scalar(path, None, lambda _: b"updated\n", owner)
                    self.assertEqual((path.stat().st_ino, _security(path)), before[path][:2])
                    self.assertEqual(path.read_bytes(), b"updated\n")
                raise stop
        self.assertIs(caught.exception, stop)
        self.assertEqual({path: (path.stat().st_ino, _security(path), path.read_bytes())
                          for path in paths}, before)

    def _same_shape_with_historical_inheritance(self):
        staging = self.root / "original-parent"
        _create_protected(staging, directory=True,
                          sddl="D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;FA;;;OW)")
        historical = staging / "historical.txt"
        historical.write_bytes(b"historical\n")
        # Deliberately refresh inheritance before the same-volume move. The
        # file keeps its original inherited ACEs despite the new parent.
        with installer._WindowsBoundNode(historical, security=True) as bound:
            prior = bound.security_image()
        kernel, *_ = _apis()
        handle = kernel.CreateFileW(str(historical), 0x60000, 7, None, 3, 0x200000, None)
        if handle == ctypes.c_void_p(-1).value:
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            setter = ctypes.WinDLL("advapi32").SetSecurityInfo
            setter.argtypes = (wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                               ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
            setter.restype = wintypes.DWORD
            error = setter(handle, 1, 4, None, None, ctypes.create_string_buffer(prior.policy[2]), None)
            if error:
                raise ctypes.WinError(error)
        finally:
            if not kernel.CloseHandle(handle):
                raise ctypes.WinError(ctypes.get_last_error())
        historical = historical.rename(self.target / historical.name)
        self.assertIn("D:AI", _security(historical))
        self.assertNotIn(";;;WD)", _security(historical))
        self.assertIn(";;;WD)", _security(self.target))
        (self.source / historical.name).write_bytes(b"updated\n")
        (self.source / "new-root.txt").unlink()
        (self.source / "shared/schemas/new.json").unlink()
        return historical

    def test_same_shape_upgrade_preserves_historical_inherited_file(self):
        historical = self._same_shape_with_historical_inheritance()
        before = (historical.stat().st_ino, _security(historical))
        expected = installer._tree_sha256(self.target)
        with installer._InstallTransaction([self.target], enabled=True) as transaction:
            owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
            owner.replace_exact_tree(self.target.relative_to(self.root), expected, self.source)
            self.assertEqual(installer._tree_sha256(self.target), installer._tree_sha256(self.source))
            self.assertEqual((historical.stat().st_ino, _security(historical)), before)
            transaction.commit()

    def test_additive_upgrade_preserves_historical_inheritance(self):
        historical = self._same_shape_with_historical_inheritance()
        before = {p: (p.stat().st_ino, _security(p))
                  for p in (self.target, *self.target.rglob("*"))}
        relative = Path("shared/schemas/new.json")
        (self.source / relative).write_bytes(b"new admitted member\n")
        expected = installer._tree_sha256(self.target)
        with installer._InstallTransaction([self.target], enabled=True) as transaction:
            owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
            owner.replace_exact_tree(self.target.relative_to(self.root), expected, self.source, allow_file_additions=True)
            self.assertEqual(installer._tree_sha256(self.target), installer._tree_sha256(self.source))
            self.assertEqual((self.target / relative).read_bytes(), b"new admitted member\n")
            self.assertEqual(historical.read_bytes(), b"updated\n")
            for path, identity in before.items():
                self.assertEqual((path.stat().st_ino, _security(path)), identity)
            transaction.commit()

    def test_additive_upgrade_rollback_preserves_original_members(self):
        historical = self._same_shape_with_historical_inheritance()
        before = {p: (p.read_bytes(), p.stat().st_ino, _security(p))
                  for p in self.target.rglob("*") if p.is_file()}
        relative = Path("shared/schemas/new.json")
        (self.source / relative).write_bytes(b"new admitted member\n")
        expected = installer._tree_sha256(self.target)
        with self.assertRaisesRegex(RuntimeError, "after additive publication"):
            with installer._InstallTransaction([self.target], enabled=True) as transaction:
                owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                owner.replace_exact_tree(self.target.relative_to(self.root), expected, self.source, allow_file_additions=True)
                self.assertTrue((self.target / relative).is_file())
                self.assertEqual(historical.read_bytes(), b"updated\n")
                raise RuntimeError("after additive publication")
        self.assertFalse((self.target / relative).exists())
        self.assertEqual({p: (p.read_bytes(), p.stat().st_ino, _security(p))
                          for p in self.target.rglob("*") if p.is_file()}, before)

    def test_additive_upgrade_does_not_adopt_equal_foreign_leaf(self):
        self._same_shape_with_historical_inheritance()
        relative = Path("shared/schemas/new.json")
        added = self.target / relative
        payload = b"same bytes, distinct creator\n"
        (self.source / relative).write_bytes(payload)
        expected = installer._tree_sha256(self.target)
        born = []
        with self.assertRaises((ValueError, installer._InstallFailure)):
            with installer._InstallTransaction([self.target], enabled=True) as transaction:
                owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                real_create = owner.create_file

                def competing_writer(path, data):
                    self.assertEqual(self.root / path, added)
                    self.assertEqual(data, payload)
                    added.write_bytes(payload)
                    born.append(added.stat().st_ino)
                    return real_create(path, data)

                with mock.patch.object(owner, "create_file", competing_writer):
                    owner.replace_exact_tree(self.target.relative_to(self.root), expected, self.source,
                                             allow_file_additions=True)
                self.fail("foreign leaf must not be accepted as an owned publication")
        self.assertEqual(len(born), 1)
        self.assertEqual(added.stat().st_ino, born[0])
        self.assertEqual(added.read_bytes(), payload)

    def test_same_shape_late_rollback_restores_original_files_and_cache(self):
        historical = self._same_shape_with_historical_inheritance()
        cache = self.target / "__pycache__" / "historical.cpython-315.pyc"
        cache.parent.mkdir()
        cache.write_bytes(b"disposable bytecode")
        snapshot = lambda: {p: (p.read_bytes(), _security(p), p.stat().st_ino)
                            for p in self.target.rglob("*") if p.is_file()}
        before = snapshot()
        before_digest = installer._tree_sha256(self.target, ignore_runtime_cache=True)
        with self.assertRaisesRegex(RuntimeError, "late fixture failure"):
            with installer._InstallTransaction([self.target], enabled=True) as transaction:
                owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                owner.replace_exact_tree(self.target.relative_to(self.root), before_digest,
                                         self.source, ignore_runtime_cache=True)
                self.assertFalse(cache.exists())
                self.assertEqual(historical.read_bytes(), b"updated\n")
                raise RuntimeError("late fixture failure")
        self.assertEqual(snapshot(), before)

    def test_same_shape_with_alias_uses_staged_replacement(self):
        (self.source / "new-root.txt").unlink()
        (self.source / "shared/schemas/new.json").unlink()
        victim = self.target / self.members[0]
        alias = self.root / "other-owner.txt"
        os.link(victim, alias)
        before = (alias.read_bytes(), _security(alias), alias.stat().st_ino)
        expected = installer._tree_sha256(self.target)
        with installer._InstallTransaction([self.target], enabled=True) as transaction:
            owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
            owner.replace_exact_tree(self.target.relative_to(self.root), expected, self.source)
            self.assertEqual(installer._tree_sha256(self.target), installer._tree_sha256(self.source))
            transaction.commit()
        self.assertEqual((alias.read_bytes(), _security(alias), alias.stat().st_ino), before)

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
            with self.assertRaises(installer._InstallFailure) as caught:
                with installer._InstallTransaction([self.target], enabled=True) as transaction:
                    owner = installer._CreateOnlyMutablePath(self.root, transaction, dry_run=False)
                    owner.replace_exact_tree(self.target.relative_to(self.root),
                                             self.expected_digest, self.source)
        self.assertEqual(len(injected), 1)
        self.assertEqual(caught.exception.stable_id, "E_WINDOWS_SECURITY_CREATION_MISMATCH")
        self.assertEqual(caught.exception.context, "security-creation")
        terminal = installer._installer_failure_text(caught.exception)
        self.assertIn("E_WINDOWS_SECURITY_CREATION_MISMATCH | context=security-creation", terminal)
        self.assertNotIn(str(self.root), terminal)
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

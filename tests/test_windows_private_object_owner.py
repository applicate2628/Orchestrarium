"""Native private-object permissions: spelling may vary, authority must not."""
from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from provider_prompt import WindowsPrivateObjectOwnerV1 as Owner  # noqa: E402

pytestmark = pytest.mark.skipif(os.name != "nt", reason="native Windows security descriptors")


def _apis():
    from ctypes import wintypes as w

    a = ctypes.WinDLL("advapi32", use_last_error=True)
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.LocalFree.argtypes = [ctypes.c_void_p]
    k.LocalFree.restype = ctypes.c_void_p
    k.CloseHandle.argtypes = [w.HANDLE]
    k.CloseHandle.restype = w.BOOL
    a.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [
        ctypes.c_void_p, w.DWORD, w.DWORD,
        ctypes.POINTER(w.LPWSTR), ctypes.POINTER(w.DWORD),
    ]
    a.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = w.BOOL
    return a, k


def test_expected_dacl_uses_the_same_native_canonical_spelling_as_readback():
    """An administrator's numeric SID can render as LA without changing rights."""
    from ctypes import wintypes as w

    a, k = _apis()
    descriptor, expected = Owner.current_user_security_descriptor()
    rendered = w.LPWSTR()
    try:
        assert a.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor, 1, 4, ctypes.byref(rendered), None
        )
        assert expected == rendered.value
        assert expected.startswith("D:P(A;;FA;;;")
    finally:
        if rendered:
            k.LocalFree(rendered)
        k.LocalFree(descriptor)


@pytest.mark.parametrize("directory", [False, True])
def test_private_object_protection_round_trip_preserves_exact_dacl(tmp_path, directory):
    target = tmp_path / "owned"
    if directory:
        target.mkdir()
    else:
        target.write_bytes(b"owned fixture")
    Owner.protect_and_verify(target, directory=directory)
    a, k = _apis()
    descriptor, expected = Owner.current_user_security_descriptor()
    handle = Owner._open_verified_handle(target, directory=directory, write_dac=True)
    try:
        Owner.verify_handle_dacl(handle, expected)
        # Exact authority is still enforced; another principal is not accepted.
        with pytest.raises(OSError, match="DACL mismatch"):
            Owner.verify_handle_dacl(handle, "D:P(A;;FA;;;SY)")
        # A protected empty ACL is not equivalent to the granted current-user ACL.
        a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes = [
            ctypes.c_wchar_p, ctypes.c_uint32,
            ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
        ]
        a.ConvertStringSecurityDescriptorToSecurityDescriptorW.restype = ctypes.c_int
        empty = ctypes.c_void_p()
        assert a.ConvertStringSecurityDescriptorToSecurityDescriptorW("D:P", 1, ctypes.byref(empty), None)
        nt = ctypes.WinDLL("ntdll")
        nt.NtSetSecurityObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p]
        nt.NtSetSecurityObject.restype = ctypes.c_long
        try:
            assert nt.NtSetSecurityObject(handle, 4, empty) >= 0
            with pytest.raises(OSError, match="DACL mismatch"):
                Owner.verify_handle_dacl(handle, expected)
        finally:
            k.LocalFree(empty)
            # Keep the fixture deletable even when a regression assertion fails.
            assert nt.NtSetSecurityObject(handle, 4, descriptor) >= 0
    finally:
        k.CloseHandle(handle)
        k.LocalFree(descriptor)

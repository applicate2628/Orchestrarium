"""Native Windows DACL identity must not depend on SID string spelling."""
from __future__ import annotations

import ctypes
import importlib.util
import os
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="requires native Windows security descriptors")
ROOT = Path(__file__).resolve().parents[1]


def _owner():
    spec = importlib.util.spec_from_file_location("dacl_audit_provider_prompt", ROOT / "scripts/provider_prompt.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_current_user_descriptor_returns_the_windows_rendered_identity():
    from ctypes import wintypes
    module = _owner()
    descriptor, expected = module.WindowsPrivateObjectOwnerV1.current_user_security_descriptor()
    rendered = wintypes.LPWSTR()
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    render = advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW
    render.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                       ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(wintypes.DWORD)]
    render.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    try:
        assert render(descriptor, 1, 4, ctypes.byref(rendered), None)
        assert expected == rendered.value
        assert expected.startswith("D:P(A;;FA;;;")
        assert expected.count("(") == 1
    finally:
        if rendered:
            kernel32.LocalFree(rendered)
        kernel32.LocalFree(descriptor)


@pytest.mark.parametrize("change", ["other-principal", "extra-grant", "unprotected", "less-access"])
def test_private_receipt_still_requires_exact_principal_permissions_and_protection(tmp_path, change):
    module = _owner()
    descriptor, expected = module.WindowsPrivateObjectOwnerV1.current_user_security_descriptor()
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree(descriptor)
    alternatives = {
        "other-principal": "D:P(A;;FA;;;WD)",
        "extra-grant": expected + "(A;;FR;;;WD)",
        "unprotected": expected.replace("D:P(", "D:(", 1),
        "less-access": expected.replace(";;FA;", ";;FR;", 1),
    }
    changed = alternatives[change]
    assert changed != expected
    with module.TerminalReceiptV1.reserve(tmp_path.resolve() / "receipt") as receipt:
        module.WindowsPrivateObjectOwnerV1.verify_handle_dacl(receipt.file_handle, expected)
        with pytest.raises(OSError, match="DACL mismatch"):
            module.WindowsPrivateObjectOwnerV1.verify_handle_dacl(receipt.file_handle, changed)

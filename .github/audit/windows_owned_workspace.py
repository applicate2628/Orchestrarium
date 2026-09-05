"""CI-only ownership setup; never imported by product code or shipped tests.

The elevated hosted Windows account defaults newly created objects to the
Administrators group. Production intentionally admits only current-user-owned
working directories. Exercise that unchanged boundary with current-user-owned
disposable checkout directories and newly created fixture objects.
"""
from __future__ import annotations

import ctypes
import os
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def current_user_owned_workspace(root: Path):
    if os.name != "nt":
        yield {"owner_setup": "not-required"}
        return
    from ctypes import wintypes
    root = root.resolve(strict=True)
    workspace = Path(os.environ["GITHUB_WORKSPACE"]).resolve(strict=True)
    if root != workspace or not (root / ".git").is_dir():
        raise RuntimeError("refusing ownership changes outside disposable checkout")
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.OpenProcessToken.restype = wintypes.BOOL
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.GetTokenInformation.restype = wintypes.BOOL
    advapi.SetTokenInformation.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD]
    advapi.SetTokenInformation.restype = wintypes.BOOL
    advapi.SetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    advapi.SetNamedSecurityInfoW.restype = wintypes.DWORD
    token = wintypes.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x8 | 0x80, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    changed = False
    def information(kind):
        size = wintypes.DWORD()
        advapi.GetTokenInformation(token, kind, None, 0, ctypes.byref(size))
        if not size.value:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(size.value)
        if not advapi.GetTokenInformation(token, kind, buffer, size, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer
    try:
        # TOKEN_USER and TOKEN_OWNER both start with their SID pointer.
        user = information(1)
        original_owner = information(4)
        current_user_sid = ctypes.cast(user, ctypes.POINTER(ctypes.c_void_p)).contents.value
        requested_owner = ctypes.c_void_p(current_user_sid)
        if not advapi.SetTokenInformation(token, 4, ctypes.byref(requested_owner), ctypes.sizeof(requested_owner)):
            raise ctypes.WinError(ctypes.get_last_error())
        changed = True
        count = 0
        for current, dirs, _files in os.walk(root, followlinks=False):
            ordinary = []
            for name in dirs:
                path = Path(current) / name
                metadata = path.lstat()
                if not path.is_symlink() and not (getattr(metadata, "st_file_attributes", 0) & 0x400):
                    ordinary.append(name)
            dirs[:] = ordinary
            result = advapi.SetNamedSecurityInfoW(str(current), 1, 1, current_user_sid, None, None, None)
            if result:
                raise ctypes.WinError(result)
            count += 1
        yield {"owner_setup": "current-user-token-default-and-disposable-checkout-directories", "directories": count, "product_policy_changed": False}
    finally:
        try:
            if changed and not advapi.SetTokenInformation(token, 4, original_owner, ctypes.sizeof(ctypes.c_void_p)):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(token)

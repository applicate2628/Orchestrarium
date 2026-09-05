"""Run tests with current-user ownership on disposable hosted Windows fixtures.

Production identity and access checks remain unchanged. The context restores the
process token's prior default owner after pytest; descendants inherit the explicit
fixture owner. This helper belongs only to the isolated audit control branch.
"""
from __future__ import annotations

import ctypes
import json
import os
import sys
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def owned_test_objects():
    if os.name != "nt":
        yield
        return
    from ctypes import wintypes as w

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel.GetCurrentProcess.restype = w.HANDLE
    kernel.CloseHandle.argtypes = [w.HANDLE]
    kernel.CloseHandle.restype = w.BOOL
    advapi.OpenProcessToken.argtypes = [w.HANDLE, w.DWORD, ctypes.POINTER(w.HANDLE)]
    advapi.OpenProcessToken.restype = w.BOOL
    advapi.GetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD, ctypes.POINTER(w.DWORD)]
    advapi.GetTokenInformation.restype = w.BOOL
    advapi.SetTokenInformation.argtypes = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD]
    advapi.SetTokenInformation.restype = w.BOOL
    token = w.HANDLE()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 0x8 | 0x80, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())

    class TOKEN_OWNER(ctypes.Structure):
        _fields_ = [("Owner", ctypes.c_void_p)]

    def information(kind):
        needed = w.DWORD()
        advapi.GetTokenInformation(token, kind, None, 0, ctypes.byref(needed))
        if not needed.value:
            raise ctypes.WinError(ctypes.get_last_error())
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi.GetTokenInformation(token, kind, buffer, needed, ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        return buffer

    changed = False
    try:
        user = information(1)
        previous = information(4)
        sid = ctypes.cast(user, ctypes.POINTER(ctypes.c_void_p))[0]
        replacement = TOKEN_OWNER(sid)
        if not advapi.SetTokenInformation(token, 4, ctypes.byref(replacement), ctypes.sizeof(replacement)):
            raise ctypes.WinError(ctypes.get_last_error())
        changed = True
        from tempfile import TemporaryDirectory
        sys.path.insert(0, str(Path.cwd() / "scripts"))
        from process_supervision.process_runner import bind_cwd_identity
        with TemporaryDirectory(prefix="pr4-owned-precondition-") as tmp:
            bind_cwd_identity(str(Path(tmp).resolve()))
        # Refuse before tests if the hosted checkout was not prepared correctly.
        bind_cwd_identity(str(Path.cwd().resolve()))
        print("AUDIT: current-user ownership precondition verified; production checks unchanged", flush=True)
        yield
    finally:
        try:
            if changed and not advapi.SetTokenInformation(token, 4, previous, len(previous)):
                raise ctypes.WinError(ctypes.get_last_error())
        finally:
            kernel.CloseHandle(token)


if __name__ == "__main__":
    import pytest

    sys.path.insert(0, str(Path.cwd()))
    with owned_test_objects():
        raise SystemExit(pytest.main(sys.argv[1:]))

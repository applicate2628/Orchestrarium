"""Run isolated audit commands with current-user-owned Windows test objects.

This is test-host provisioning, not a production ownership exception. It keeps
all discretionary access lists unchanged and restores the prior default owner.
"""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import subprocess
import sys
import tempfile


@contextmanager
def current_user_owned_scope(root: Path):
    if os.name != 'nt':
        raise RuntimeError('This explicit test host setup requires Windows')
    root = root.resolve(strict=True)
    workspace = Path(os.environ['GITHUB_WORKSPACE']).resolve(strict=True)
    if root == workspace or workspace not in root.parents or not (root / '.git').exists():
        raise RuntimeError('Refusing ownership provisioning outside the isolated checkout')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    security = ctypes.WinDLL('advapi32', use_last_error=True)
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree.restype = ctypes.c_void_p
    security.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    security.OpenProcessToken.restype = wintypes.BOOL
    security.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    security.GetTokenInformation.restype = wintypes.BOOL
    security.SetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
    security.SetTokenInformation.restype = wintypes.BOOL
    security.SetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
    security.SetNamedSecurityInfoW.restype = wintypes.DWORD
    security.GetNamedSecurityInfoW.argtypes = [wintypes.LPWSTR, ctypes.c_int, wintypes.DWORD,
        ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p)]
    security.GetNamedSecurityInfoW.restype = wintypes.DWORD
    security.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    security.EqualSid.restype = wintypes.BOOL
    token = wintypes.HANDLE()
    if not security.OpenProcessToken(kernel.GetCurrentProcess(), 0x0008 | 0x0080, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    prior = None
    changed = False
    try:
        def read_information(kind):
            size = wintypes.DWORD()
            security.GetTokenInformation(token, kind, None, 0, ctypes.byref(size))
            if not size.value:
                raise ctypes.WinError(ctypes.get_last_error())
            result = ctypes.create_string_buffer(size.value)
            if not security.GetTokenInformation(token, kind, result, size, ctypes.byref(size)):
                raise ctypes.WinError(ctypes.get_last_error())
            return result
        user = read_information(1)
        prior = read_information(4)
        sid = ctypes.cast(user, ctypes.POINTER(ctypes.c_void_p))[0]
        desired = ctypes.c_void_p(sid)
        if not security.SetTokenInformation(token, 4, ctypes.byref(desired), ctypes.sizeof(desired)):
            raise ctypes.WinError(ctypes.get_last_error())
        changed = True
        status = security.SetNamedSecurityInfoW(str(root), 1, 1, sid, None, None, None)
        if status:
            raise ctypes.WinError(status)
        def require_user_owner(path):
            owner = ctypes.c_void_p()
            descriptor = ctypes.c_void_p()
            try:
                status = security.GetNamedSecurityInfoW(str(path), 1, 1,
                    ctypes.byref(owner), None, None, None, ctypes.byref(descriptor))
                if status:
                    raise ctypes.WinError(status)
                if not security.EqualSid(owner, sid):
                    raise RuntimeError('Isolated test object is not owned by the current user')
            finally:
                if descriptor:
                    kernel.LocalFree(descriptor)
        require_user_owner(root)
        with tempfile.TemporaryDirectory(prefix='orche-owner-check-') as temporary:
            require_user_owner(Path(temporary))
        print('Verified current-user checkout and new-object ownership; access lists unchanged.', flush=True)
        yield
    finally:
        try:
            if changed:
                if not security.SetTokenInformation(token, 4, prior, ctypes.sizeof(ctypes.c_void_p)):
                    raise ctypes.WinError(ctypes.get_last_error())
                print('Restored prior process default owner.', flush=True)
        finally:
            kernel.CloseHandle(token)


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Supply an explicit audit command')
    with current_user_owned_scope(Path.cwd()):
        return subprocess.call(sys.argv[1:])


if __name__ == '__main__':
    raise SystemExit(main())

"""Read-only diagnostics of exact candidate owners; no provider launches."""
from __future__ import annotations

import ctypes
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import traceback
from ctypes import wintypes

ROOT = Path.cwd()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def capture(label, function):
    print('\nCASE:', label, flush=True)
    try:
        result = function()
        print('RESULT:', str(result), flush=True)
    except Exception as error:
        print('ERROR:', type(error).__name__, str(error), flush=True)
        traceback.print_exc()


owner = load('audit_prompt_owner', ROOT / 'scripts/provider_prompt.py')
verify = owner.WindowsPrivateObjectOwnerV1.verify_handle_dacl


def diagnostic_dacl(handle, expected):
    # Log only the access-control structure; remove all machine/user SID values.
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    advapi32 = ctypes.WinDLL('advapi32', use_last_error=True)
    advapi32.GetSecurityInfo.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
        ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p)]
    advapi32.GetSecurityInfo.restype = wintypes.DWORD
    advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [ctypes.c_void_p,
        wintypes.DWORD, wintypes.DWORD, ctypes.POINTER(wintypes.LPWSTR), ctypes.c_void_p]
    advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    descriptor = ctypes.c_void_p()
    dacl = ctypes.c_void_p()
    text = wintypes.LPWSTR()
    try:
        status = advapi32.GetSecurityInfo(wintypes.HANDLE(handle), 1, 4, None, None,
            ctypes.byref(dacl), None, ctypes.byref(descriptor))
        if status == 0 and advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW(
            descriptor, 1, 4, ctypes.byref(text), None):
            scrub = lambda value: re.sub(r'S-\d+(?:-\d+)+', '<SID>', value)
            print('DACL observed:', scrub(text.value), 'expected:', scrub(expected), flush=True)
        else:
            print('DACL query error:', status, ctypes.get_last_error(), flush=True)
    finally:
        if text: kernel32.LocalFree(text)
        if descriptor: kernel32.LocalFree(descriptor)
    return verify(handle, expected)


owner.WindowsPrivateObjectOwnerV1.verify_handle_dacl = staticmethod(diagnostic_dacl)
with tempfile.TemporaryDirectory(prefix='orche-diagnostic-') as temporary:
    root = Path(temporary).resolve()
    leaf = root / 'private.txt'
    leaf.write_bytes(b'synthetic')
    capture('protect existing file', lambda: owner.WindowsPrivateObjectOwnerV1.protect_and_verify(leaf, directory=False))
    def receipt():
        with owner.TerminalReceiptV1.reserve(root / 'terminal.receipt'):
            return 'reserved with real owner checks'
    capture('reserve new terminal', receipt)

helper = load('audit_runner_fixture', ROOT / 'tests/test_process_runner_windows_runtime.py')
runner = helper._load_runner()
request = helper._request(runner, (str(Path(sys.executable).resolve()), '-c', 'print(1)'))
locations = []

def trace(frame, event, arg):
    if event == 'exception' and frame.f_code.co_filename.endswith('process_runner.py'):
        kind, error, _ = arg
        if isinstance(error, (runner.ProcessSupervisionError, OSError)):
            row = (frame.f_code.co_name, frame.f_lineno, type(error).__name__, str(error))
            if row not in locations: locations.append(row)
    return trace

sys.settrace(trace)
try:
    capture('validate ordinary Windows request', lambda: runner.validate_process_request(request))
    capture('cwd ownership', lambda: runner.bind_cwd_identity(str(ROOT)))
    result = runner.ProcessRunnerV1().run(request)
    print('RUN:', result.outcome, result.error_code, flush=True)
finally:
    sys.settrace(None)
    print('REFUSAL LOCATIONS:', json.dumps(locations, indent=2), flush=True)

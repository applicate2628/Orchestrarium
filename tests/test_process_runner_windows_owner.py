"""Windows ownership accepts only the token user or its OS-selected default owner."""
from __future__ import annotations

import ctypes
import hashlib
import importlib.util
import os
import sys
from ctypes import wintypes
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _runner():
    spec = importlib.util.spec_from_file_location(
        "process_runner_owner_contract", ROOT / "scripts/process_supervision/process_runner.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class Function:
    def __init__(self, function):
        self.function = function

    def __call__(self, *args):
        return self.function(*args)


def _install_windows_api(monkeypatch, runner, *, owner, fail_information=None):
    # These byte buffers are synthetic identities. No real process is launched.
    identities = {name: ctypes.create_string_buffer(name.encode(), 16)
                  for name in ("user", "default", "unrelated")}
    addresses = {name: ctypes.addressof(value) for name, value in identities.items()}
    closed, freed, queries = [], [], []

    def set_value(pointer, ctype, value):
        ctypes.cast(pointer, ctypes.POINTER(ctype))[0] = value

    def named(_path, _kind, _flags, owner_out, _group, _dacl, _sacl, descriptor):
        set_value(owner_out, ctypes.c_void_p, addresses[owner])
        set_value(descriptor, ctypes.c_void_p, 1234)
        return 0

    def open_token(_process, _access, token_out):
        set_value(token_out, wintypes.HANDLE, 4321)
        return 1

    def information(_token, kind, buffer, _length, needed):
        queries.append(kind)
        if kind == fail_information:
            set_value(needed, wintypes.DWORD, 0)
            return 0
        set_value(needed, wintypes.DWORD, ctypes.sizeof(ctypes.c_void_p))
        if buffer is None:
            return 0
        set_value(buffer, ctypes.c_void_p, addresses[{1: "user", 4: "default"}[kind]])
        return 1

    def equal(left, right):
        return (left.value if isinstance(left, ctypes.c_void_p) else left) == right

    advapi = SimpleNamespace(**{name: Function(function) for name, function in {
        "GetNamedSecurityInfoW": named,
        "OpenProcessToken": open_token,
        "GetTokenInformation": information,
        "EqualSid": equal,
        "GetLengthSid": lambda _sid: 16,
    }.items()})
    kernel = SimpleNamespace(**{name: Function(function) for name, function in {
        "GetCurrentProcess": lambda: 999,
        "CloseHandle": lambda handle: closed.append(handle.value) or 1,
        "LocalFree": lambda handle: freed.append(handle.value),
    }.items()})
    monkeypatch.setattr(runner.ctypes, "WinDLL", lambda name, **_kw: {
        "advapi32": advapi, "kernel32": kernel,
    }[name], raising=False)
    return identities, closed, freed, queries


@pytest.mark.parametrize("owner", ("user", "default"))
def test_exact_user_or_default_owner_is_accepted_and_hashed(monkeypatch, tmp_path, owner):
    runner = _runner()
    identities, closed, freed, queries = _install_windows_api(monkeypatch, runner, owner=owner)
    digest = runner._windows_owner_digest(tmp_path)
    assert digest == hashlib.sha256(identities[owner].raw).hexdigest()
    assert closed == [4321] and freed == [1234]
    assert set(queries) <= {1, 4}


def test_unrelated_owner_remains_rejected_and_handles_are_closed(monkeypatch, tmp_path):
    runner = _runner()
    _, closed, freed, _ = _install_windows_api(monkeypatch, runner, owner="unrelated")
    with pytest.raises(runner.ProcessSupervisionError):
        runner._windows_owner_digest(tmp_path)
    assert closed == [4321] and freed == [1234]


@pytest.mark.parametrize("information_class", (1, 4))
def test_unavailable_identity_never_authorizes_an_owner(monkeypatch, tmp_path, information_class):
    runner = _runner()
    _, closed, freed, _ = _install_windows_api(
        monkeypatch, runner, owner="default", fail_information=information_class
    )
    with pytest.raises(runner.ProcessSupervisionError):
        runner._windows_owner_digest(tmp_path)
    assert closed == [4321] and freed == [1234]


@pytest.mark.skipif(os.name != "nt", reason="native Windows ownership API")
def test_native_new_directory_satisfies_the_current_token_owner_contract(tmp_path):
    runner = _runner()
    identity = runner.bind_cwd_identity(str(tmp_path))
    assert len(identity.owner) == 64

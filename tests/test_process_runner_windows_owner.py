"""Windows ownership follows the exact current token, not arbitrary groups."""
from __future__ import annotations

import ctypes
import hashlib
import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    spec = importlib.util.spec_from_file_location(
        "process_runner_owner_test", ROOT / "scripts/process_supervision/process_runner.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class TokenApi:
    """Deterministic Win32 acquisition boundary; production comparison is real."""

    def __init__(self, owner, failure=None):
        self.sids = {name: ctypes.create_string_buffer(name.encode())
                     for name in ("user", "default", "foreign")}
        self.owner = owner
        self.failure = failure
        self.queries = []
        self.closed = []
        self.freed = []

        def named(path, kind, flags, owner_out, group, dacl, sacl, descriptor_out):
            owner_out._obj.value = ctypes.addressof(self.sids[self.owner])
            descriptor_out._obj.value = 321
            return 5 if failure == "security" else 0

        def open_token(process, flags, token_out):
            if failure == "open":
                return False
            token_out._obj.value = 123
            return True

        def info(token, kind, buffer, size, needed):
            self.queries.append((kind, buffer is not None))
            if failure == ("probe", kind) and buffer is None:
                needed._obj.value = 0
                return False
            needed._obj.value = ctypes.sizeof(ctypes.c_void_p)
            if buffer is None:
                return False
            if failure == ("read", kind):
                return False
            value = ctypes.addressof(self.sids[{1: "user", 4: "default"}[kind]])
            if failure == ("null", kind):
                value = None
            ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0] = value
            return True

        def address(value):
            return value.value if isinstance(value, ctypes.c_void_p) else value

        self.advapi = SimpleNamespace(
            GetNamedSecurityInfoW=named, OpenProcessToken=open_token,
            GetTokenInformation=info,
            EqualSid=lambda left, right: address(left) == address(right),
            GetLengthSid=lambda pointer: 0 if failure == "length" else len(self.owner),
        )
        self.kernel = SimpleNamespace(
            GetCurrentProcess=lambda: -1,
            CloseHandle=lambda handle: self.closed.append(handle.value) or True,
            LocalFree=lambda descriptor: self.freed.append(descriptor.value) or None,
        )

    def install(self, module, monkeypatch):
        monkeypatch.setattr(module.ctypes, "WinDLL", lambda name, **kw:
                            self.advapi if name == "advapi32" else self.kernel, raising=False)


@pytest.mark.parametrize("owner", ["user", "default"])
def test_accepts_user_or_exact_default_owner_and_binds_actual_owner(owner, monkeypatch):
    module = _load()
    api = TokenApi(owner)
    api.install(module, monkeypatch)
    assert module._windows_owner_digest(Path("owned")) == hashlib.sha256(owner.encode()).hexdigest()
    assert api.closed == [123] and api.freed == [321]
    kinds = {kind for kind, _ in api.queries}
    assert kinds == ({1} if owner == "user" else {1, 4})


def test_unrelated_owner_is_denied_even_when_token_has_default_owner(monkeypatch):
    module = _load()
    api = TokenApi("foreign")
    api.install(module, monkeypatch)
    with pytest.raises(module.ProcessSupervisionError):
        module._windows_owner_digest(Path("foreign"))
    assert api.closed == [123] and api.freed == [321]


@pytest.mark.parametrize("failure", ["security", "open", "length", *[
    (operation, kind) for kind in (1, 4) for operation in ("probe", "read", "null")
]])
def test_failed_owner_acquisition_denies_and_releases_resources(failure, monkeypatch):
    module = _load()
    api = TokenApi("default", failure)
    api.install(module, monkeypatch)
    with pytest.raises(module.ProcessSupervisionError):
        module._windows_owner_digest(Path("owned"))
    assert api.freed == [321]
    assert api.closed == ([] if failure in ("security", "open") else [123])


@pytest.mark.skipif(os.name != "nt", reason="native Windows token ownership")
def test_native_fresh_directory_has_admissible_stable_owner(tmp_path):
    module = _load()
    first = module.bind_cwd_identity(str(tmp_path))
    assert first == module.bind_cwd_identity(str(tmp_path))
    assert len(module._windows_owner_digest(tmp_path)) == 64

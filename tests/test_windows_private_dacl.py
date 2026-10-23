"""Private DACL representation and allocation ownership at the Windows boundary."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
import os
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts.provider_prompt import WindowsPrivateObjectOwnerV1 as Owner


@pytest.fixture
def api(monkeypatch):
    """Only API storage is simulated; exercise the real descriptor producer."""
    sid = ctypes.create_unicode_buffer("S-1-5-18")
    rendered = ctypes.create_unicode_buffer("D:P(A;;FA;;;SY)")
    descriptor = ctypes.create_string_buffer(32)
    addresses = {name: ctypes.addressof(value) for name, value in
                 (("sid", sid), ("rendered", rendered), ("descriptor", descriptor))}
    freed = []

    def output(pointer, value):
        ctypes.cast(pointer, ctypes.POINTER(ctypes.c_void_p))[0] = value

    def token_info(token, kind, buffer, size, needed):
        ctypes.cast(needed, ctypes.POINTER(wintypes.DWORD))[0] = 32
        return True

    def convert(text, revision, target, size):
        assert text == "D:P(A;;FA;;;S-1-5-18)"
        output(target, addresses["descriptor"])
        return True

    def render(source, revision, information, target, size):
        assert source.value == addresses["descriptor"]
        assert (revision, information) == (1, 4)
        output(target, addresses["rendered"])
        return True

    kernel = SimpleNamespace(
        GetCurrentProcess=Mock(return_value=1), CloseHandle=Mock(return_value=True),
        LocalFree=Mock(side_effect=lambda value: freed.append(ctypes.cast(value, ctypes.c_void_p).value)),
    )
    advapi = SimpleNamespace(
        OpenProcessToken=Mock(side_effect=lambda process, access, target: output(target, 2) or True),
        GetTokenInformation=Mock(side_effect=token_info),
        ConvertSidToStringSidW=Mock(side_effect=lambda source, target: output(target, addresses["sid"]) or True),
        ConvertStringSecurityDescriptorToSecurityDescriptorW=Mock(side_effect=convert),
        ConvertSecurityDescriptorToStringSecurityDescriptorW=Mock(side_effect=render),
    )
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **kw: kernel if name == "kernel32" else advapi, raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 5, raising=False)
    return SimpleNamespace(kernel=kernel, advapi=advapi, addresses=addresses,
                           freed=freed, output=output, render=render, storage=(sid, rendered, descriptor))


def test_expected_identity_uses_rendered_alias_and_transfers_descriptor(api):
    descriptor, expected = Owner.current_user_security_descriptor()
    assert expected == "D:P(A;;FA;;;SY)"
    assert descriptor.value == api.addresses["descriptor"]
    assert api.freed == [api.addresses["sid"], api.addresses["rendered"]]
    api.kernel.LocalFree(descriptor)  # Existing caller owns the successful return.
    assert api.freed.count(api.addresses["descriptor"]) == 1
    api.kernel.CloseHandle.assert_called_once()


@pytest.mark.parametrize("failure", ["false-with-output", "empty", "null", "exception", "interrupt", "setup"])
def test_failed_render_releases_owned_allocations(api, failure):
    def fail(source, revision, information, target, size):
        if failure != "null":
            api.render(source, revision, information, target, size)
        if failure == "empty":
            ctypes.memset(api.addresses["rendered"], 0, ctypes.sizeof(ctypes.c_wchar))
        if failure == "exception":
            raise RuntimeError("render interrupted")
        if failure == "interrupt":
            raise KeyboardInterrupt("render interrupted")
        return failure in {"empty", "null"}

    api.advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW.side_effect = fail
    if failure == "setup":
        del api.advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW
    error = {"exception": RuntimeError, "interrupt": KeyboardInterrupt, "setup": AttributeError}.get(failure, OSError)
    with pytest.raises(error):
        Owner.current_user_security_descriptor()
    expected = [api.addresses["sid"], api.addresses["descriptor"]]
    if failure not in {"null", "setup"}:
        expected.insert(1, api.addresses["rendered"])
    assert api.freed == expected


native_windows = pytest.mark.skipif(os.name != "nt", reason="requires native Windows security descriptors")


@native_windows
def test_current_user_descriptor_matches_native_rendering():
    descriptor, expected = Owner.current_user_security_descriptor()
    rendered = wintypes.LPWSTR()
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    render = advapi.ConvertSecurityDescriptorToStringSecurityDescriptorW
    render.argtypes = [ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                       ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(wintypes.DWORD)]
    render.restype = wintypes.BOOL
    try:
        assert render(descriptor, 1, 4, ctypes.byref(rendered), None)
        assert expected == rendered.value
        assert expected.startswith("D:P(A;;FA;;;") and expected.count("(") == 1
    finally:
        if rendered:
            kernel.LocalFree(rendered)
        kernel.LocalFree(descriptor)


@native_windows
def test_recognized_sid_alias_uses_native_rendering(monkeypatch):
    """Inject only SID text; native conversion/rendering touch no object ACL."""
    native_dll = ctypes.WinDLL
    sid = ctypes.create_unicode_buffer("S-1-5-18")
    sid_address = ctypes.addressof(sid)
    kernel = native_dll("kernel32", use_last_error=True)
    advapi = native_dll("advapi32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]

    def supply_sid(source, target):
        ctypes.cast(target, ctypes.POINTER(ctypes.c_void_p))[0] = sid_address
        return True

    class Api:
        def __init__(self, original, overrides):
            self.original, self.overrides = original, overrides

        def __getattr__(self, name):
            return self.overrides[name] if name in self.overrides else getattr(self.original, name)

    kernel_proxy = Api(kernel, {"LocalFree": Mock(side_effect=lambda pointer:
        None if ctypes.cast(pointer, ctypes.c_void_p).value == sid_address else kernel.LocalFree(pointer))})
    advapi_proxy = Api(advapi, {"ConvertSidToStringSidW": Mock(side_effect=supply_sid)})
    monkeypatch.setattr(ctypes, "WinDLL", lambda name, **kw: kernel_proxy if name == "kernel32" else advapi_proxy)
    descriptor, expected = Owner.current_user_security_descriptor()
    try:
        assert expected != "D:P(A;;FA;;;S-1-5-18)"
        assert expected == "D:P(A;;FA;;;SY)"
    finally:
        kernel.LocalFree(descriptor)


@native_windows
@pytest.mark.parametrize("change", ["other-principal", "extra-grant", "unprotected", "less-access"])
def test_receipt_verifier_rejects_inexact_expectations(tmp_path, change):
    from scripts.provider_prompt import TerminalReceiptV1

    descriptor, expected = Owner.current_user_security_descriptor()
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    kernel.LocalFree(descriptor)
    changed = {
        "other-principal": "D:P(A;;FA;;;WD)",
        "extra-grant": expected + "(A;;FR;;;WD)",
        "unprotected": expected.replace("D:P(", "D:(", 1),
        "less-access": expected.replace(";;FA;", ";;FR;", 1),
    }[change]
    assert changed != expected
    with TerminalReceiptV1.reserve(tmp_path.resolve() / "receipt") as receipt:
        Owner.verify_handle_dacl(receipt.file_handle, expected)
        with pytest.raises(OSError, match="DACL mismatch"):
            Owner.verify_handle_dacl(receipt.file_handle, changed)

"""Synthetic receipt-handle close progress; no native provider/process calls."""
import ctypes
import importlib.util
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sdk_receipt_close_owner", ROOT / "scripts/provider_prompt.py")
owner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = owner
SPEC.loader.exec_module(owner)


def receipt(windows=False):
    return owner.TerminalReceiptV1(Path("/synthetic/receipt"), 101, 102, windows,
                                  ancestor_handles=(103, 102))


@pytest.mark.parametrize("failed", (101, 102))
@pytest.mark.parametrize("failure", (OSError("synthetic uncertain close"), KeyboardInterrupt()))
def test_posix_failure_attempts_all_siblings_without_retry(monkeypatch, failure, failed):
    value = receipt()
    calls = []
    original = owner.os.close

    def close(handle):
        if handle not in {101, 102, 103}:
            return original(handle)
        calls.append(handle)
        if handle == failed:
            raise failure

    monkeypatch.setattr(owner.os, "close", close)
    with pytest.raises(type(failure)) as first:
        value.close()
    assert first.value is failure
    assert calls == [101, 102, 103]
    with pytest.raises(type(failure)):
        value.close()
    assert calls == [101, 102, 103]


def test_posix_success_is_idempotent_and_deduplicates_owned_handles(monkeypatch):
    value = receipt()
    value.ancestor_handles = (103, 102, 102)
    calls = []
    original = owner.os.close
    monkeypatch.setattr(owner.os, "close", lambda handle: calls.append(handle)
                        if handle in {101, 102, 103} else original(handle))
    value.close()
    value.close()
    assert calls == [101, 102, 103]
    assert value.file_handle == value.parent_handle == -1


@pytest.mark.parametrize("failed", (None, 101, 102))
def test_windows_checks_false_and_never_retries_uncertain_handle(monkeypatch, failed):
    value = receipt(windows=True)
    calls = []

    class FakeCloseHandle:
        def __call__(self, handle):
            calls.append(handle.value)
            return handle.value != failed

    class Kernel:
        CloseHandle = FakeCloseHandle()

    monkeypatch.setattr(ctypes, "WinDLL", lambda *args, **kwargs: Kernel(), raising=False)
    monkeypatch.setattr(ctypes, "get_last_error", lambda: 6, raising=False)
    if failed is None:
        value.close()
        value.close()
        assert value.file_handle == value.parent_handle == -1
    else:
        with pytest.raises(OSError, match="CloseHandle"):
            value.close()
        with pytest.raises(OSError, match="CloseHandle"):
            value.close()
    assert calls == [101, 102, 103]

"""File acquisition keeps per-API metadata stability on Windows and POSIX."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "src.codex/skills/policy-overlay/scripts/policy_overlay_core.py"


def _metadata(value, **changes):
    names = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns",
             "st_ctime_ns", "st_birthtime_ns", "st_file_attributes")
    data = {name: getattr(value, name, 0) for name in names}
    data.update(changes)
    return SimpleNamespace(**data)


@pytest.fixture
def reader(monkeypatch):
    spec = importlib.util.spec_from_file_location("policy_metadata_compatibility", MODULE)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    # Replace only the module view, not the process-wide os.name or pathlib.
    platform_os = SimpleNamespace(**vars(os))
    platform_os.name = "nt"
    monkeypatch.setattr(module, "os", platform_os)
    return module


def _read(module, path):
    return module._read_regular(path, 1024, label="metadata fixture")


def test_unchanged_windows_file_with_different_ctime_representations_is_read(reader, tmp_path):
    path = tmp_path / "plain.json"
    expected = b'{"ordinary":true}\r\n'
    path.write_bytes(expected)
    real_fstat = reader.os.fstat
    reader.os.fstat = lambda fd: _metadata(real_fstat(fd), st_ctime_ns=path.lstat().st_ctime_ns + 1)
    assert _read(reader, path) == expected


@pytest.mark.parametrize("field", ["st_ctime_ns", "st_mtime_ns", "st_size", "st_ino", "st_birthtime_ns"])
def test_descriptor_metadata_change_during_read_is_still_rejected(reader, tmp_path, field):
    path = tmp_path / "plain.json"
    path.write_bytes(b"unchanged body")
    real_fstat = reader.os.fstat
    calls = 0

    def changing_fstat(fd):
        nonlocal calls
        calls += 1
        value = _metadata(real_fstat(fd))
        if calls > 1:
            setattr(value, field, getattr(value, field) + 1)
        return value

    reader.os.fstat = changing_fstat
    with pytest.raises(reader.PolicyOverlayError):
        _read(reader, path)


@pytest.mark.parametrize("field", ["st_ctime_ns", "st_mtime_ns", "st_size", "st_ino", "st_birthtime_ns"])
def test_path_metadata_change_during_read_is_still_rejected(reader, tmp_path, monkeypatch, field):
    path = tmp_path / "plain.json"
    path.write_bytes(b"unchanged body")
    original = path.lstat()
    real_lstat = Path.lstat
    observed = False
    real_read = reader.os.read

    def after_read(fd, count):
        nonlocal observed
        data = real_read(fd, count)
        observed = True
        return data

    def changing_lstat(self):
        value = real_lstat(self)
        if observed and self == path:
            return _metadata(value, **{field: getattr(original, field, 0) + 1})
        return value

    reader.os.read = after_read
    monkeypatch.setattr(Path, "lstat", changing_lstat)
    # The worker reader calls module os.lstat instead of Path.lstat.
    real_os_lstat = reader.os.lstat
    reader.os.lstat = lambda name: changing_lstat(Path(name)) if Path(name) == path else real_os_lstat(name)
    with pytest.raises(reader.PolicyOverlayError):
        _read(reader, path)


def test_posix_cross_api_ctime_mismatch_is_not_relaxed(reader, tmp_path):
    reader.os.name = "posix"
    path = tmp_path / "plain.json"
    path.write_bytes(b"ordinary input")
    real_fstat = reader.os.fstat
    reader.os.fstat = lambda fd: _metadata(real_fstat(fd), st_ctime_ns=path.lstat().st_ctime_ns + 1)
    with pytest.raises(reader.PolicyOverlayError):
        _read(reader, path)

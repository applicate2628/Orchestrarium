"""Prepare only verified file-metadata fixes on isolated candidate branches."""
from pathlib import Path
import hashlib
import subprocess
import sys

surface = sys.argv[1]
root = Path(sys.argv[2]).resolve()
configs = {
    "policy": (
        "8279b8fdb51984a0eff3d0eb005c0c0ced5d8568",
        "src.codex/skills/policy-overlay/scripts/policy_overlay_core.py",
        "tests/test_policy_overlay_metadata_compatibility.py",
        "PolicyOverlayError",
        'return module._read_regular(path, 1024, label="metadata fixture")',
        "5c7d44b30b479bfbfa4565c368e0af9bea1116f4",
        "63071ae4d23bfb77021ba8e4e30e05030c0c061c",
    ),
    "worker": (
        "838feaa92ea972e0785465e2d3a1a8ff490cffae",
        "src.codex/skills/lead-worker-routing/scripts/resolve.py",
        "tests/test_lead_worker_routing_v1_metadata_compatibility.py",
        "UnsafeRequestFileError", "return module._read_file_bytes(path)",
        "b4b437f38365273df69a6bcdfa22e2a1a1fbfb59",
        "d3ad1b51db29b40b2c6650278ab8f12d0a9b2035",
    ),
}
head, source, test, error, readcall, source_blob, test_blob = configs[surface]
actual = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip()
if actual != head:
    raise SystemExit('Unexpected source head: ' + actual)

def replace_once(text, old, new):
    if text.count(old) != 1:
        raise SystemExit('Expected one exact source anchor')
    return text.replace(old, new, 1)

path = root / source
text = path.read_text(encoding='utf-8')
if surface == 'policy':
    text = replace_once(text,
        '        getattr(info, "st_ctime_ns", 0),\n        getattr(info, "st_file_attributes", 0),',
        '        getattr(info, "st_file_attributes", 0),\n        getattr(info, "st_birthtime_ns", 0),\n        getattr(info, "st_ctime_ns", 0),')
    text = replace_once(text,
        '        if _file_signature(before) != _file_signature(opened):',
        '        before_signature = _file_signature(before)\n'
        '        opened_signature = _file_signature(opened)\n'
        '        # Windows path and descriptor APIs can give ctime different meanings.\n'
        '        # Compare it within each API below, never discard either stability check.\n'
        '        comparable = slice(None, -1) if os.name == "nt" else slice(None)\n'
        '        if before_signature[comparable] != opened_signature[comparable]:')
    text = replace_once(text,
        '            _file_signature(opened) != _file_signature(os.fstat(fd))\n'
        '            or _file_signature(opened) != _file_signature(path.lstat())',
        '            opened_signature != _file_signature(os.fstat(fd))\n'
        '            or before_signature != _file_signature(path.lstat())')
else:
    text = replace_once(text,
        '        getattr(metadata, "st_mtime_ns", 0),\n        getattr(metadata, "st_ctime_ns", 0),',
        '        getattr(metadata, "st_mtime_ns", 0),\n        getattr(metadata, "st_birthtime_ns", 0),\n        getattr(metadata, "st_ctime_ns", 0),')
    text = replace_once(text,
        '        opened = os.fstat(descriptor)\n'
        '        if (\n'
        '            not stat.S_ISREG(opened.st_mode)\n'
        '            or _entry_signature(opened, leaf=True) != before_signature\n',
        '        opened = os.fstat(descriptor)\n'
        '        opened_signature = _entry_signature(opened, leaf=True)\n'
        '        # Windows path and descriptor APIs can give ctime different meanings.\n'
        '        # Full same-API snapshots below still bind it independently on both sides.\n'
        '        comparable = slice(None, -1) if os.name == "nt" else slice(None)\n'
        '        if (\n'
        '            not stat.S_ISREG(opened.st_mode)\n'
        '            or opened_signature[comparable] != before_signature[comparable]\n')
path.write_text(text, encoding='utf-8', newline='\n')

template = '''"""File acquisition keeps per-API metadata stability on Windows and POSIX."""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE = ROOT / "{module}"


def _metadata(value, **changes):
    names = ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns",
             "st_ctime_ns", "st_birthtime_ns", "st_file_attributes")
    data = {{name: getattr(value, name, 0) for name in names}}
    data.update(changes)
    return SimpleNamespace(**data)


@pytest.fixture
def reader(monkeypatch):
    spec = importlib.util.spec_from_file_location("{modname}", MODULE)
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
    {readcall}


def test_unchanged_windows_file_with_different_ctime_representations_is_read(reader, tmp_path):
    path = tmp_path / "plain.json"
    expected = b'{{"ordinary":true}}\\r\\n'
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
    with pytest.raises(reader.{error}):
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
            return _metadata(value, **{{field: getattr(original, field, 0) + 1}})
        return value

    reader.os.read = after_read
    monkeypatch.setattr(Path, "lstat", changing_lstat)
    # The worker reader calls module os.lstat instead of Path.lstat.
    real_os_lstat = reader.os.lstat
    reader.os.lstat = lambda name: changing_lstat(Path(name)) if Path(name) == path else real_os_lstat(name)
    with pytest.raises(reader.{error}):
        _read(reader, path)


def test_posix_cross_api_ctime_mismatch_is_not_relaxed(reader, tmp_path):
    reader.os.name = "posix"
    path = tmp_path / "plain.json"
    path.write_bytes(b"ordinary input")
    real_fstat = reader.os.fstat
    reader.os.fstat = lambda fd: _metadata(real_fstat(fd), st_ctime_ns=path.lstat().st_ctime_ns + 1)
    with pytest.raises(reader.{error}):
        _read(reader, path)
'''
module_name = 'policy_metadata_compatibility' if surface == 'policy' else 'routing_metadata_compatibility'
test_path = root / test
if test_path.exists():
    raise SystemExit('Regression path already exists')
test_path.write_text(template.format(module=source, modname=module_name, readcall=readcall, error=error), encoding='utf-8', newline='\n')
for relative, expected in ((source, source_blob), (test, test_blob)):
    data = (root / relative).read_bytes()
    observed = hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()
    if observed != expected:
        raise SystemExit(f'Tested file identity mismatch: {relative}: {observed}')

release = root / 'RELEASE_NOTES.md'
old_bytes = release.read_bytes()
header = b'# Release Notes\n\nThis file is the canonical release log for tracked Orchestrarium monorepo changes that matter at publication time.\n\n'
if not old_bytes.startswith(header):
    raise SystemExit('Unexpected release-note header')
label = 'Policy overlay' if surface == 'policy' else 'Worker routing'
note = (
    f'- **{label} file reads now compare Windows timestamps within their originating metadata interface.** '
    'Path-based and descriptor-based status can report different `st_ctime_ns` meanings for the same unchanged file. '
    'Cross-interface checks still bind identity, type, size, modification time, attributes, and creation time when available; '
    'each interface retains its own complete before/after stability checks. Unix checks remain exact. '
    '**Why it matters:** ordinary Windows inputs no longer produce false unsafe-file errors, while replacement and metadata changes remain rejected.\n'
).encode('utf-8')
section = b'## 2026-09-05\n\n'
if old_bytes[len(header):].startswith(section):
    insertion = len(header) + len(section)
    release.write_bytes(old_bytes[:insertion] + note + old_bytes[insertion:])
else:
    release.write_bytes(header + section + note + b'\n' + old_bytes[len(header):])
expected_paths = sorted((source, test, 'RELEASE_NOTES.md'))
subprocess.run(['git', 'add', '--', *expected_paths], cwd=root, check=True)
actual_paths = subprocess.check_output(['git', 'diff', '--cached', '--name-only'], cwd=root, text=True).splitlines()
if sorted(actual_paths) != expected_paths:
    raise SystemExit('Unexpected staged paths')
subprocess.run(['git', 'diff', '--cached', '--check'], cwd=root, check=True)
subprocess.run([sys.executable, 'scripts/check-publication-gate.py'], cwd=root, check=True, timeout=120)

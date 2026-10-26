from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest


def _make_file_symlink(link: Path, target: Path) -> None:
    link.parent.mkdir(parents=True, exist_ok=True)
    try:
        link.symlink_to(target, target_is_directory=False)
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"file symlinks are unavailable: {exc}")
    assert link.is_symlink()


def _make_directory_junction(link: Path, target: Path) -> None:
    if os.name != "nt":
        pytest.skip("Windows junction coverage")
    link.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            "New-Item",
            "-ItemType",
            "Junction",
            "-Path",
            str(link),
            "-Target",
            str(target),
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0 or not os.path.isjunction(link):
        pytest.skip(f"junction creation is unavailable: {result.stdout}{result.stderr}")


def _write_directory_attributes(installer, path: Path, attributes: int) -> None:
    ctypes_api, _wintypes, kernel, *_rest = installer._WindowsBoundNode._api()
    with installer._WindowsBoundNode(path, purpose="attributes") as bound:
        basic = bound.basic()
        basic.attributes = attributes
        if not kernel.SetFileInformationByHandle(
            bound.live_handle, 0, ctypes_api.byref(basic), ctypes_api.sizeof(basic)
        ):
            raise ctypes_api.WinError(ctypes_api.get_last_error())


def _flip_directory_binding_attributes(installer, path: Path):
    before = installer._InstallTransaction._capture_node(path)
    raw_change_bits = stat.FILE_ATTRIBUTE_ARCHIVE | stat.FILE_ATTRIBUTE_READONLY
    attributes = before.python_identity[3] ^ raw_change_bits
    _write_directory_attributes(installer, path, attributes)
    requested = stat.S_IMODE(before.python_identity[2])
    if attributes & stat.FILE_ATTRIBUTE_READONLY:
        requested &= ~stat.S_IWRITE
    else:
        requested |= stat.S_IWRITE
    path.chmod(requested)
    after = installer._InstallTransaction._capture_node(path)
    assert before.kind == after.kind == "directory"
    assert before.python_identity[:2] == after.python_identity[:2]
    assert before.native_proof == after.native_proof
    assert before.python_identity[3] ^ after.python_identity[3] == raw_change_bits
    assert after.python_identity[2] == installer._InstallTransaction._chmod_identity(
        before.python_identity, requested
    )[2]
    return before, after

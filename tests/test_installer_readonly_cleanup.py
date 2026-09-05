"""Deletion of transaction-owned trees must not modify link referents."""
from __future__ import annotations

import errno
import os
from pathlib import Path
import shutil
import stat
import sys
import typing

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import production_installer as installer  # noqa: E402


def _restore_owned_tree(path: Path) -> None:
    """Keep a failed regression from leaving inaccessible pytest fixtures."""
    if path.is_symlink() or not path.exists():
        return
    path.chmod(0o700)
    for child in path.iterdir():
        if child.is_symlink():
            continue
        if child.is_dir():
            _restore_owned_tree(child)
        else:
            child.chmod(0o600)


@pytest.mark.parametrize('directory_mode', [0o500, 0o400, 0o000])
def test_cleanup_retraverses_owned_readonly_directories(tmp_path: Path, directory_mode: int) -> None:
    if os.name == 'nt' or (hasattr(os, 'geteuid') and os.geteuid() == 0):
        pytest.skip('requires non-root POSIX directory permission enforcement')
    root = tmp_path / 'owned'
    nested = root / 'first' / 'second'
    nested.mkdir(parents=True)
    (nested / 'payload').write_bytes(b'owned')
    (nested / 'payload').chmod(0o400)
    for directory in (nested, nested.parent, root):
        directory.chmod(directory_mode)
    parent_mode = stat.S_IMODE(tmp_path.stat().st_mode)
    try:
        installer._remove_readonly_tree(root)
        assert not root.exists()
        assert stat.S_IMODE(tmp_path.stat().st_mode) == parent_mode
    finally:
        _restore_owned_tree(root)


def test_cleanup_does_not_chmod_or_traverse_external_links(tmp_path: Path) -> None:
    root, outside = tmp_path / 'owned', tmp_path / 'outside'
    root.mkdir()
    outside.mkdir()
    sentinel = outside / 'sentinel'
    sentinel.write_bytes(b'external')
    sentinel.chmod(0o400)
    try:
        (root / 'directory-link').symlink_to(outside, target_is_directory=True)
        (root / 'file-link').symlink_to(sentinel)
        (root / 'broken-link').symlink_to(outside / 'missing')
    except OSError as exc:
        pytest.skip(f'symlink creation unavailable: {exc}')
    original_mode = stat.S_IMODE(sentinel.stat().st_mode)
    root.chmod(0o500)
    try:
        installer._remove_readonly_tree(root)
        assert not root.exists()
        assert sentinel.read_bytes() == b'external'
        assert stat.S_IMODE(sentinel.stat().st_mode) == original_mode
        assert list(outside.iterdir()) == [sentinel]
    finally:
        _restore_owned_tree(root)
        sentinel.chmod(0o600)


def test_cleanup_rejects_symlink_as_tree_root(tmp_path: Path) -> None:
    outside = tmp_path / 'outside'
    outside.mkdir()
    sentinel = outside / 'sentinel'
    sentinel.write_bytes(b'external')
    root = tmp_path / 'owned-link'
    try:
        root.symlink_to(outside, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f'symlink creation unavailable: {exc}')
    with pytest.raises(OSError):
        installer._remove_readonly_tree(root)
    assert root.is_symlink()
    assert sentinel.read_bytes() == b'external'


def test_cleanup_does_not_repair_unrelated_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / 'owned'
    root.mkdir()
    root.chmod(0o500)
    failure = OSError(errno.EIO, 'synthetic storage failure')

    def failing_rmtree(path, *, onexc=None, onerror=None):
        if onexc is not None:
            onexc(os.rmdir, str(path), failure)
        else:
            onerror(os.rmdir, str(path), (type(failure), failure, None))

    monkeypatch.setattr(shutil, 'rmtree', failing_rmtree)
    original_mode = stat.S_IMODE(root.stat().st_mode)
    try:
        with pytest.raises(OSError) as error:
            installer._remove_readonly_tree(root)
        assert error.value is failure
        assert stat.S_IMODE(root.stat().st_mode) == original_mode
    finally:
        if root.exists():
            root.chmod(0o700)


def test_cleanup_bounds_persistent_permission_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / 'owned'
    root.mkdir()
    root.chmod(0o500)
    failure = PermissionError(errno.EACCES, 'synthetic permanent denial')
    calls = 0

    def failing_rmtree(path, *, onexc=None, onerror=None):
        nonlocal calls
        calls += 1
        assert calls <= 2, 'cleanup retried without making permission progress'
        if onexc is not None:
            onexc(os.rmdir, str(path), failure)
        else:
            onerror(os.rmdir, str(path), (type(failure), failure, None))

    monkeypatch.setattr(shutil, 'rmtree', failing_rmtree)
    try:
        with pytest.raises(PermissionError) as error:
            installer._remove_readonly_tree(root)
        assert error.value is failure
    finally:
        if root.exists():
            root.chmod(0o700)


def test_rmtree_callback_annotations_can_be_resolved() -> None:
    assert typing.get_type_hints(installer._rmtree_callback_kwargs)

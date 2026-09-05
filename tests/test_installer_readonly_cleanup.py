"""Exercise owned-tree cleanup with real filesystem permissions and links."""
from __future__ import annotations

import errno
import inspect
import os
import shutil
import stat
import sys
import typing
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import production_installer as installer  # noqa: E402


def _restore_test_tree(path: Path) -> None:
    """Teardown only: never follow links when releasing our own test fixture."""
    try:
        metadata = path.lstat()
    except FileNotFoundError:
        return
    if stat.S_ISLNK(metadata.st_mode) or installer._is_reparse_metadata(metadata):
        return
    os.chmod(path, metadata.st_mode | stat.S_IRWXU)
    if stat.S_ISDIR(metadata.st_mode):
        for child in path.iterdir():
            _restore_test_tree(child)


@pytest.fixture
def owned_root(tmp_path):
    root = tmp_path / "owned"
    root.mkdir()
    try:
        yield root
    finally:
        _restore_test_tree(tmp_path)


def _require_permission_enforcement() -> None:
    if os.name == "posix" and os.geteuid() == 0:
        pytest.skip("POSIX permission-denial regression must run as a non-root user")


@pytest.mark.parametrize("level", [0, 1, 2])
@pytest.mark.parametrize("mode", [0o500, 0o400, 0o100, 0o000])
def test_remove_tree_with_unwritable_or_unsearchable_directory(owned_root, level, mode):
    _require_permission_enforcement()
    directories = [owned_root]
    for index in range(2):
        child = directories[-1] / f"level-{index}"
        child.mkdir()
        directories.append(child)
    payload = directories[-1] / "payload.txt"
    payload.write_text("owned bytes", encoding="utf-8")
    payload.chmod(0o400)
    directories[level].chmod(mode)

    installer._remove_readonly_tree(owned_root)

    assert not owned_root.exists()


@pytest.mark.parametrize("kind", ["file", "directory", "dangling"])
def test_remove_link_in_readonly_directory_preserves_external_target(owned_root, kind):
    _require_permission_enforcement()
    external = owned_root.parent / "external"
    if kind == "directory":
        external.mkdir()
        payload = external / "sentinel"
        payload.write_bytes(b"external contents")
        external.chmod(0o500)
    elif kind == "file":
        external.write_bytes(b"external contents")
        external.chmod(0o400)
    original = external.lstat() if kind != "dangling" else None
    link = owned_root / "link"
    try:
        link.symlink_to(external, target_is_directory=(kind == "directory"))
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("Creating a symbolic link requires Windows developer mode or privilege")
        raise
    owned_root.chmod(0o500)

    installer._remove_readonly_tree(owned_root)

    assert not owned_root.exists()
    if original is None:
        assert not external.exists()
    else:
        assert stat.S_IMODE(external.lstat().st_mode) == stat.S_IMODE(original.st_mode)
        assert external.lstat().st_ino == original.st_ino
        content_path = external / "sentinel" if kind == "directory" else external
        assert content_path.read_bytes() == b"external contents"


def test_cleanup_does_not_make_unowned_parent_writable(owned_root):
    if os.name != "posix":
        pytest.skip("POSIX directory-mode boundary")
    _require_permission_enforcement()
    parent = owned_root.parent
    (owned_root / "payload").write_bytes(b"owned")
    parent.chmod(0o500)
    original_mode = stat.S_IMODE(parent.stat().st_mode)

    with pytest.raises(PermissionError):
        installer._remove_readonly_tree(owned_root)

    assert stat.S_IMODE(parent.stat().st_mode) == original_mode


def test_cleanup_propagates_non_permission_failure_without_chmod(owned_root, monkeypatch):
    original_mode = stat.S_IMODE(owned_root.stat().st_mode)
    error = OSError(errno.EIO, "simulated I/O failure", str(owned_root))

    def failing_rmtree(path, *, onexc):
        onexc(os.rmdir, str(path), error)

    def unexpected_chmod(*args, **kwargs):
        pytest.fail("non-permission failures must not change permissions")

    with monkeypatch.context() as patch:
        patch.setattr(shutil, "rmtree", failing_rmtree)
        patch.setattr(os, "chmod", unexpected_chmod)
        with pytest.raises(OSError) as raised:
            installer._remove_readonly_tree(owned_root)
    assert raised.value is error
    assert stat.S_IMODE(owned_root.stat().st_mode) == original_mode


def test_repeated_permission_failure_is_bounded(owned_root, monkeypatch):
    error = PermissionError(errno.EACCES, "permission remains denied", str(owned_root))
    calls = 0

    def failing_rmtree(path, *, onexc):
        nonlocal calls
        calls += 1
        if calls > 2:
            pytest.fail("cleanup retried an unchanged denial more than once")
        onexc(os.scandir, str(path), error)

    with monkeypatch.context() as patch:
        patch.setattr(shutil, "rmtree", failing_rmtree)
        with pytest.raises(PermissionError) as raised:
            installer._remove_readonly_tree(owned_root)
    assert raised.value is error
    assert calls == 2
    assert owned_root.is_dir()


def test_missing_top_level_tree_is_not_silently_accepted(tmp_path):
    with pytest.raises(FileNotFoundError):
        installer._remove_readonly_tree(tmp_path / "absent")


def test_top_level_symlink_is_not_followed(owned_root):
    external = owned_root.parent / "external"
    external.mkdir()
    sentinel = external / "sentinel"
    sentinel.write_bytes(b"outside")
    link = owned_root / "link"
    try:
        link.symlink_to(external, target_is_directory=True)
    except OSError as error:
        if os.name == "nt" and getattr(error, "winerror", None) == 1314:
            pytest.skip("Creating a symbolic link requires Windows developer mode or privilege")
        raise

    with pytest.raises(OSError):
        installer._remove_readonly_tree(link)

    assert link.is_symlink()
    assert sentinel.read_bytes() == b"outside"


def test_callback_type_annotations_can_be_resolved():
    assert "onexc" in typing.get_type_hints(installer._rmtree_callback_kwargs)


def test_legacy_error_callback_forwards_original_exception():
    def legacy_rmtree(path, *, onerror):
        pass
    observed = []
    error = PermissionError("denied")
    callback = installer._rmtree_callback_kwargs(
        legacy_rmtree, lambda function, path, exc: observed.append((function, path, exc))
    )["onerror"]
    callback(os.unlink, "owned/path", (PermissionError, error, None))
    assert observed == [(os.unlink, "owned/path", error)]


def test_cleanup_runs_through_legacy_onerror_api(owned_root, monkeypatch):
    _require_permission_enforcement()
    (owned_root / "payload").write_bytes(b"owned")
    owned_root.chmod(0o500)
    original = shutil.rmtree

    def legacy_rmtree(path, *, onerror):
        def forward(function, value, exc):
            onerror(function, value, (type(exc), exc, exc.__traceback__))
        if "onexc" in inspect.signature(original).parameters:
            return original(path, onexc=forward)
        return original(path, onerror=onerror)

    with monkeypatch.context() as patch:
        patch.setattr(shutil, "rmtree", legacy_rmtree)
        installer._remove_readonly_tree(owned_root)
    assert not owned_root.exists()


def test_unsupported_rmtree_callback_contract_refuses_before_mutation(owned_root, monkeypatch):
    sentinel = owned_root / "sentinel"
    sentinel.write_bytes(b"preserve")

    def unsupported_rmtree(path):
        pytest.fail("unsupported callback interface must be refused before deletion")

    with monkeypatch.context() as patch:
        patch.setattr(shutil, "rmtree", unsupported_rmtree)
        with pytest.raises(TypeError, match="no supported error callback"):
            installer._remove_readonly_tree(owned_root)
    assert sentinel.read_bytes() == b"preserve"

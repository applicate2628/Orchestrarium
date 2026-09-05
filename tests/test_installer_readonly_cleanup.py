"""Regressions for removal of installer-owned readonly trees.

These tests do not relax hook, process-launch, or publication checks. Permission
cases need a non-privileged POSIX user or native Windows filesystem semantics.
"""
from __future__ import annotations

import errno
import os
import stat
from pathlib import Path

import pytest

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import production_installer as installer  # noqa: E402


def _real_permission_semantics(tmp_path: Path) -> None:
    if os.name == "nt":
        return
    probe = tmp_path / "permission-probe"
    probe.mkdir()
    probe.chmod(0o500)
    try:
        try:
            (probe / "write").write_text("probe", encoding="utf-8")
        except PermissionError:
            return
        pytest.skip("requires an unprivileged user; this account bypasses mode bits")
    finally:
        probe.chmod(0o700)
        for child in probe.iterdir():
            child.unlink()
        probe.rmdir()


@pytest.mark.parametrize("mode", [0o555, 0o500, 0o400, 0o000])
def test_readonly_directory_is_fully_removed(tmp_path: Path, mode: int) -> None:
    _real_permission_semantics(tmp_path)
    tree = tmp_path / "owned"
    child = tree / "nested"
    child.mkdir(parents=True)
    (tree / "top.txt").write_text("top", encoding="utf-8")
    (child / "leaf.txt").write_text("leaf", encoding="utf-8")
    child.chmod(mode)
    tree.chmod(mode)
    try:
        installer._remove_readonly_tree(tree)
        assert not tree.exists()
    finally:
        if tree.exists():
            tree.chmod(0o700)
            if child.exists():
                child.chmod(0o700)


def test_readonly_file_is_removed(tmp_path: Path) -> None:
    tree = tmp_path / "owned"
    tree.mkdir()
    file = tree / "leaf.txt"
    file.write_text("payload", encoding="utf-8")
    file.chmod(0o400)
    installer._remove_readonly_tree(tree)
    assert not tree.exists()


def test_root_link_is_refused_without_changing_referent(tmp_path: Path) -> None:
    target = tmp_path / "external"
    target.mkdir()
    (target / "keep.txt").write_text("keep", encoding="utf-8")
    target.chmod(0o555)
    link = tmp_path / "link"
    try:
        link.symlink_to(target, target_is_directory=True)
    except OSError as exc:
        target.chmod(0o700)
        pytest.skip(f"symlink prerequisite unavailable: {exc}")
    mode = stat.S_IMODE(target.stat().st_mode)
    try:
        with pytest.raises(OSError):
            installer._remove_readonly_tree(link)
        assert link.is_symlink()
        assert stat.S_IMODE(target.stat().st_mode) == mode
        assert (target / "keep.txt").read_text(encoding="utf-8") == "keep"
    finally:
        target.chmod(0o700)


def test_child_links_never_mutate_external_targets(tmp_path: Path) -> None:
    _real_permission_semantics(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    file = external / "keep.txt"
    file.write_text("keep", encoding="utf-8")
    file.chmod(0o400)
    tree = tmp_path / "owned"
    tree.mkdir()
    try:
        (tree / "file-link").symlink_to(file)
        (tree / "directory-link").symlink_to(external, target_is_directory=True)
        (tree / "broken-link").symlink_to(tmp_path / "absent")
    except OSError as exc:
        pytest.skip(f"symlink prerequisite unavailable: {exc}")
    external.chmod(0o500)
    tree.chmod(0o500)
    file_mode = stat.S_IMODE(file.stat().st_mode)
    directory_mode = stat.S_IMODE(external.stat().st_mode)
    try:
        installer._remove_readonly_tree(tree)
        assert not tree.exists()
        assert external.is_dir()
        assert file.read_text(encoding="utf-8") == "keep"
        assert stat.S_IMODE(file.stat().st_mode) == file_mode
        assert stat.S_IMODE(external.stat().st_mode) == directory_mode
    finally:
        external.chmod(0o700)
        file.chmod(0o600)
        if tree.exists():
            tree.chmod(0o700)


def test_external_parent_is_not_made_writable(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("POSIX parent directory mode-bit contract")
    _real_permission_semantics(tmp_path)
    parent = tmp_path / "not-owned-parent"
    tree = parent / "owned"
    tree.mkdir(parents=True)
    parent.chmod(0o500)
    try:
        with pytest.raises(PermissionError):
            installer._remove_readonly_tree(tree)
        assert stat.S_IMODE(parent.stat().st_mode) == 0o500
    finally:
        parent.chmod(0o700)


def test_missing_root_is_not_reported_as_success(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        installer._remove_readonly_tree(tmp_path / "missing")


def test_unrelated_failure_preserves_exception_and_permissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = tmp_path / "owned"
    tree.mkdir()
    tree.chmod(0o500)
    failure = OSError(errno.EIO, "injected I/O failure", str(tree))

    def fail_remove(path, *, onexc=None, onerror=None):
        assert Path(path) == tree
        if onexc is not None:
            onexc(os.rmdir, str(tree), failure)
        else:
            assert onerror is not None
            onerror(os.rmdir, str(tree), (OSError, failure, None))

    monkeypatch.setattr(installer.shutil, "rmtree", fail_remove)
    mode = stat.S_IMODE(tree.stat().st_mode)
    try:
        with pytest.raises(OSError) as raised:
            installer._remove_readonly_tree(tree)
        assert raised.value is failure
        assert stat.S_IMODE(tree.stat().st_mode) == mode
    finally:
        if tree.exists():
            tree.chmod(0o700)


def test_legacy_callback_adapts_exact_exception() -> None:
    def legacy(path, ignore_errors=False, onerror=None):
        raise AssertionError("signature-only function must not execute")

    failure = PermissionError(errno.EACCES, "denied")
    observed = []
    callback = installer._rmtree_callback_kwargs(
        legacy, lambda *args: observed.append(args)
    )
    assert set(callback) == {"onerror"}
    callback["onerror"](os.unlink, "owned", (type(failure), failure, None))
    assert observed == [(os.unlink, "owned", failure)]


def test_callback_selection_rejects_unsupported_signature_before_mutation() -> None:
    def unsupported(path):
        raise AssertionError("must not execute")

    with pytest.raises(TypeError, match="no supported error callback"):
        installer._rmtree_callback_kwargs(unsupported, lambda *args: None)


def test_repeated_permission_denial_cannot_retry_forever(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = tmp_path / "owned"
    tree.mkdir()
    tree.chmod(0o500)
    failure = PermissionError(errno.EACCES, "permission remains denied", str(tree))
    calls = []

    def deny(path, *, onexc=None, onerror=None):
        calls.append(path)
        assert len(calls) <= 2, "permission recovery did not terminate"
        if onexc is not None:
            onexc(os.scandir, str(tree), failure)
        else:
            onerror(os.scandir, str(tree), (type(failure), failure, None))

    monkeypatch.setattr(installer.shutil, "rmtree", deny)
    try:
        with pytest.raises(PermissionError) as raised:
            installer._remove_readonly_tree(tree)
        assert raised.value is failure
        assert len(calls) == 2
    finally:
        tree.chmod(0o700)


def test_sibling_prefix_is_not_treated_as_an_owned_descendant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = tmp_path / "owned"
    other = tmp_path / "owned-sibling"
    tree.mkdir()
    other.mkdir()
    other.chmod(0o500)
    failure = PermissionError(errno.EACCES, "outside reported", str(other))

    def fail_outside(path, *, onexc=None, onerror=None):
        if onexc is not None:
            onexc(os.rmdir, str(other), failure)
        else:
            onerror(os.rmdir, str(other), (type(failure), failure, None))

    monkeypatch.setattr(installer.shutil, "rmtree", fail_outside)
    try:
        with pytest.raises(PermissionError) as raised:
            installer._remove_readonly_tree(tree)
        assert raised.value is failure
        assert other.is_dir()
        assert stat.S_IMODE(other.stat().st_mode) == 0o500
    finally:
        if other.exists():
            other.chmod(0o700)


def test_root_replacement_before_repair_cannot_change_external_permissions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tree = tmp_path / "owned"
    displaced = tmp_path / "displaced"
    external = tmp_path / "external"
    tree.mkdir()
    external.mkdir()
    nested = external / "nested"
    nested.mkdir()
    nested.chmod(0o500)
    failure = PermissionError(errno.EACCES, "root replaced")

    def replace_root(path, *, onexc=None, onerror=None):
        tree.rename(displaced)
        try:
            tree.symlink_to(external, target_is_directory=True)
        except OSError as exc:
            pytest.skip(f"symlink prerequisite unavailable: {exc}")
        member = str(tree / "nested" / "leaf")
        if onexc is not None:
            onexc(os.unlink, member, failure)
        else:
            onerror(os.unlink, member, (type(failure), failure, None))

    monkeypatch.setattr(installer.shutil, "rmtree", replace_root)
    try:
        with pytest.raises(PermissionError) as raised:
            installer._remove_readonly_tree(tree)
        assert raised.value is failure
        assert stat.S_IMODE(nested.stat().st_mode) == 0o500
    finally:
        nested.chmod(0o700)


def test_readonly_hard_link_does_not_change_external_file_mode(tmp_path: Path) -> None:
    if os.name == "nt":
        pytest.skip("POSIX file deletion requires parent, not file, permission")
    _real_permission_semantics(tmp_path)
    external = tmp_path / "external.txt"
    external.write_text("keep", encoding="utf-8")
    tree = tmp_path / "owned"
    tree.mkdir()
    os.link(external, tree / "hardlink")
    external.chmod(0o400)
    tree.chmod(0o500)
    try:
        installer._remove_readonly_tree(tree)
        assert not tree.exists()
        assert external.read_text(encoding="utf-8") == "keep"
        assert stat.S_IMODE(external.stat().st_mode) == 0o400
    finally:
        external.chmod(0o600)
        if tree.exists():
            tree.chmod(0o700)


def test_readable_readonly_tree_does_not_restart_for_each_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _real_permission_semantics(tmp_path)
    tree = tmp_path / "owned"
    for index in range(12):
        child = tree / str(index)
        child.mkdir(parents=True)
        (child / "leaf").write_text("payload", encoding="utf-8")
        child.chmod(0o555)
    tree.chmod(0o555)
    original = installer.shutil.rmtree
    calls = []

    def counted(path, *, onexc=None, onerror=None):
        calls.append(path)
        if onexc is not None:
            callback = installer._rmtree_callback_kwargs(original, onexc)
        else:
            callback = {"onerror": onerror}
        return original(path, **callback)

    monkeypatch.setattr(installer.shutil, "rmtree", counted)
    installer._remove_readonly_tree(tree)
    assert not tree.exists()
    assert len(calls) == 1, "ordinary readonly entries must not cause quadratic rescans"

"""Native POSIX permission receiving for transaction rollback snapshots."""

import os
from pathlib import Path

import pytest

from test_hook_runtime_transactions import production_installer as installer


@pytest.mark.skipif(os.name != "posix" or os.geteuid() == 0,
                    reason="requires POSIX permissions under an unprivileged user")
@pytest.mark.parametrize("fail", [False, True])
def test_transaction_discards_private_snapshot_of_readonly_directory(tmp_path, fail):
    target = tmp_path / "target"
    nested = target / "nested"
    nested.mkdir(parents=True)
    leaf = nested / "member"
    leaf.write_bytes(b"preserve")
    nested.chmod(0o500)
    target.chmod(0o550)
    tx = installer._InstallTransaction([target], enabled=True)

    class LaterError(Exception):
        pass

    def install():
        with tx:
            if fail:
                raise LaterError("later operation failed")
            tx.commit()

    try:
        if fail:
            with pytest.raises(LaterError, match="later operation failed"):
                install()
        else:
            install()
        assert tx._temporary is None or not Path(tx._temporary).exists()
        assert target.stat().st_mode & 0o777 == 0o550
        assert nested.stat().st_mode & 0o777 == 0o500
        assert leaf.read_bytes() == b"preserve"
    finally:
        # pytest owns these fixtures; make fixture removal possible.
        target.chmod(0o700)
        nested.chmod(0o700)
        if tx._temporary and Path(tx._temporary).is_dir():
            for directory, _, _ in os.walk(tx._temporary):
                Path(directory).chmod(0o700)


@pytest.mark.skipif(os.name != "posix", reason="requires POSIX descriptor disposal")
def test_disposal_failure_keeps_recovery_mode_and_original_bytes(tmp_path, monkeypatch):
    target = tmp_path / "target"
    target.mkdir()
    (target / "member").write_bytes(b"preserve")
    target.chmod(0o500)
    tx = installer._InstallTransaction([target], enabled=True)
    seen = []
    unlink = os.unlink

    def failing_unlink(path, *, dir_fd=None):
        if path == "member" and dir_fd is not None:
            seen.append(os.fstat(dir_fd).st_mode & 0o777)
            raise PermissionError("injected snapshot cleanup failure")
        return unlink(path, dir_fd=dir_fd)

    try:
        with pytest.raises(installer._InstallFailure, match="injected snapshot cleanup failure"):
            with tx:
                # Preserve this host's dir_fd capability while observing its use.
                with monkeypatch.context() as patch:
                    patch.setattr(os, "unlink", failing_unlink)
                    patch.setattr(os, "supports_dir_fd", {*os.supports_dir_fd, failing_unlink})
                    error = tx._discard_backup()
                assert error is not None
                assert seen == [0o700]
                backup = Path(tx._temporary) / "0"
                assert backup.stat().st_mode & 0o777 == 0o500
                assert (backup / "member").read_bytes() == b"preserve"
                assert target.stat().st_mode & 0o777 == 0o500
                assert (target / "member").read_bytes() == b"preserve"
                raise error
        assert tx._temporary is None or not Path(tx._temporary).exists()
    finally:
        target.chmod(0o700)
        if tx._temporary and Path(tx._temporary).is_dir():
            for directory, _, _ in os.walk(tx._temporary):
                Path(directory).chmod(0o700)

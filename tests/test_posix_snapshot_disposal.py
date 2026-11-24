"""Permission changes may consume only the exact owned snapshot child."""
import os
from pathlib import Path
import stat

import pytest

from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]
installer = load_module(ROOT / "scripts/production_installer.py", "posix_snapshot_disposal_backend")


@pytest.mark.skipif(os.name != "posix", reason="POSIX descriptor permission transition")
@pytest.mark.parametrize("drift", ["none", "bytes", "group-write"])
def test_private_snapshot_disposal_rechecks_child_after_parent_permission_change(tmp_path, monkeypatch, drift):
    source = tmp_path / "source"
    source.mkdir()
    (source / "body").write_bytes(b"owned bytes\n")
    source.chmod(0o555)
    transaction = installer._InstallTransaction([], enabled=False)
    born = {}
    private = transaction._allocate_owned_directory(tmp_path, "private-", born.__setitem__)
    backup = private / "copy"
    expected = transaction._copy_snapshot(source, backup, transaction._observe(source))
    assert transaction._backup_root_state[backup] == expected[backup]
    parent_identity = expected[backup].python_identity[:2]
    real_fchmod = os.fchmod
    hits = []

    def change_after_setter(descriptor, mode):
        real_fchmod(descriptor, mode)
        metadata = os.fstat(descriptor)
        if (metadata.st_dev, metadata.st_ino) == parent_identity and mode & stat.S_IWUSR and not hits:
            hits.append(mode)
            if drift == "bytes":
                (backup / "body").write_bytes(b"foreign bytes\n")
            elif drift == "group-write":
                real_fchmod(descriptor, mode | stat.S_IWGRP)

    monkeypatch.setattr(os, "fchmod", change_after_setter)
    if drift == "none":
        transaction._dispose_image(backup, expected)
        assert not backup.exists()
    else:
        reason = "disposal permission content drift" if drift == "bytes" else "disposal permission transition"
        with pytest.raises(ValueError, match=reason):
            transaction._dispose_image(backup, expected)
        assert (backup / "body").read_bytes() == (b"foreign bytes\n" if drift == "bytes" else b"owned bytes\n")
        assert stat.S_IMODE(backup.stat().st_mode) == 0o555
        assert installer._CreateOnlyMutablePath._identity(backup) == expected[backup].python_identity
        assert transaction._backup_states[backup] == expected
    assert hits == [0o755]
    assert (source / "body").read_bytes() == b"owned bytes\n"
    assert stat.S_IMODE(source.stat().st_mode) == 0o555

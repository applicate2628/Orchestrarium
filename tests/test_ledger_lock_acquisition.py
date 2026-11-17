"""Lock acquisition fault injection: no provider/model or network operations."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from _module_loading_support import load_module

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def owner():
    return load_module(ROOT / "scripts/agent-run-ledger.py", "ledger_lock_acquisition_test")


def invoke(owner, item, caller):
    if caller == "context":
        with owner.ledger_write_lock(item):
            pytest.fail("failed metadata must not enter the protected operation")
    elif caller == "append":
        owner._append_event_transaction(item, SimpleNamespace(load_lifecycle_owner=lambda: None), None)
    else:
        owner.load_validator = lambda: SimpleNamespace(load_lifecycle_owner=lambda: None)
        owner._commit_recovery_append(item, {}, lambda *args: [], "unused", None)


@pytest.mark.parametrize("caller", ["context", "append", "recovery"])
@pytest.mark.parametrize("partial", [False, True])
def test_metadata_failure_releases_only_acquired_lock(owner, tmp_path, monkeypatch, caller, partial):
    original_write, original_close = owner.os.write, owner.os.close
    closed = []
    failure = OSError("injected metadata write failure")

    def fail(fd, data):
        if partial:
            original_write(fd, data[:3])
        raise failure

    def close(fd):
        closed.append(fd)
        original_close(fd)

    with monkeypatch.context() as patch:
        patch.setattr(owner.os, "write", fail)
        patch.setattr(owner.os, "close", close)
        with pytest.raises(OSError) as result:
            invoke(owner, tmp_path, caller)
    assert result.value is failure
    assert len(closed) == 1
    assert not (tmp_path / "agent-runs.jsonl.lock").exists()
    assert not (tmp_path / "agent-runs.jsonl").exists()
    # Same item can immediately resume; no stale-lock takeover is needed.
    with owner.ledger_write_lock(tmp_path):
        assert (tmp_path / "agent-runs.jsonl.lock").is_file()
    assert not (tmp_path / "agent-runs.jsonl.lock").exists()


def test_short_write_is_completed(owner, tmp_path, monkeypatch):
    original = owner.os.write
    monkeypatch.setattr(owner.os, "write", lambda fd, data: original(fd, data[:2]))
    with owner.ledger_write_lock(tmp_path):
        metadata = (tmp_path / "agent-runs.jsonl.lock").read_text()
        assert metadata.startswith("pid=") and metadata.endswith("\n") and " at=" in metadata


def test_zero_progress_is_failure_and_releases(owner, tmp_path, monkeypatch):
    monkeypatch.setattr(owner.os, "write", lambda *args: 0)
    with pytest.raises(OSError, match="no progress"):
        owner._create_ledger_lock(tmp_path / "agent-runs.jsonl.lock")
    assert not list(tmp_path.iterdir())


def test_existing_foreign_lock_remains(owner, tmp_path, monkeypatch):
    lock = tmp_path / "agent-runs.jsonl.lock"
    lock.write_bytes(b"foreign")
    with pytest.raises(FileExistsError):
        owner._create_ledger_lock(lock)
    assert lock.read_bytes() == b"foreign"


def test_changed_identity_is_preserved(owner, tmp_path, monkeypatch):
    lock = tmp_path / "agent-runs.jsonl.lock"
    original = Path.lstat
    failure = OSError("injected")
    monkeypatch.setattr(owner.os, "write", lambda *args: (_ for _ in ()).throw(failure))

    def changed(path, *args, **kwargs):
        value = original(path, *args, **kwargs)
        if path == lock:
            return SimpleNamespace(st_mode=value.st_mode, st_dev=value.st_dev, st_ino=value.st_ino + 1)
        return value

    with monkeypatch.context() as patch:
        patch.setattr(Path, "lstat", changed)
        with pytest.raises(OSError) as result:
            owner._create_ledger_lock(lock)
    assert result.value is failure
    assert lock.exists()


def test_cleanup_error_does_not_mask_acquisition_error(owner, tmp_path, monkeypatch):
    failure = OSError("primary metadata failure")
    monkeypatch.setattr(owner.os, "write", lambda *args: (_ for _ in ()).throw(failure))
    monkeypatch.setattr(Path, "unlink", lambda *args, **kwargs: (_ for _ in ()).throw(OSError("cleanup failure")))
    with pytest.raises(OSError) as result:
        owner._create_ledger_lock(tmp_path / "agent-runs.jsonl.lock")
    assert result.value is failure
    assert any("cleanup failure" in note for note in failure.__notes__)


def test_identity_acquisition_failure_closes_descriptor_and_preserves_unknown_path(owner, tmp_path, monkeypatch):
    lock = tmp_path / "agent-runs.jsonl.lock"
    original_close = owner.os.close
    closed = []
    failure = OSError("injected identity failure")

    def close(fd):
        closed.append(fd)
        original_close(fd)

    with monkeypatch.context() as patch:
        patch.setattr(owner.os, "fstat", lambda fd: (_ for _ in ()).throw(failure))
        patch.setattr(owner.os, "close", close)
        with pytest.raises(OSError) as result:
            owner._create_ledger_lock(lock)
    assert result.value is failure and len(closed) == 1
    assert lock.exists()  # No identity proof: no guessed path cleanup.


def test_close_failure_preserves_lock_and_primary_error(owner, tmp_path, monkeypatch):
    lock = tmp_path / "agent-runs.jsonl.lock"
    original_close = owner.os.close
    descriptors = []
    failure = OSError("injected metadata failure")

    def failed_close(fd):
        descriptors.append(fd)
        raise OSError("injected close failure")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(owner.os, "write", lambda *args: (_ for _ in ()).throw(failure))
            patch.setattr(owner.os, "close", failed_close)
            with pytest.raises(OSError) as result:
                owner._create_ledger_lock(lock)
        assert result.value is failure and lock.exists()
        assert len(descriptors) == 1
        assert any("injected close failure" in note for note in failure.__notes__)
    finally:
        for fd in descriptors:
            original_close(fd)


def test_replacement_before_cleanup_observation_is_preserved(owner, tmp_path, monkeypatch):
    lock = tmp_path / "agent-runs.jsonl.lock"
    original_close = owner.os.close
    failure = OSError("injected metadata failure")

    def replaced_after_close(fd):
        original_close(fd)
        lock.rename(tmp_path / "retired-owned-lock")
        lock.write_bytes(b"replacement owner")

    with monkeypatch.context() as patch:
        patch.setattr(owner.os, "write", lambda *args: (_ for _ in ()).throw(failure))
        patch.setattr(owner.os, "close", replaced_after_close)
        with pytest.raises(OSError) as result:
            owner._create_ledger_lock(lock)
    assert result.value is failure
    assert lock.read_bytes() == b"replacement owner"

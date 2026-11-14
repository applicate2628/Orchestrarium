"""Native snapshot lifecycle components; POSIX admission remains test-only."""
import os
import pytest
from test_provider_prompt_projections import _load_installer


def setup(tmp_path, monkeypatch):
    module = _load_installer()
    storage = tmp_path / "staging"
    storage.mkdir()
    monkeypatch.setattr(module.tempfile, "gettempdir", lambda: str(storage))
    if os.name == "posix":
        monkeypatch.setattr(module, "_require_transaction_disposal_backend", lambda: None)
    source = tmp_path / "source"
    source.mkdir()
    (source / "payload").write_bytes(b"original")
    return module, storage, source


@pytest.mark.parametrize("outcome", ["commit", "rollback"])
@pytest.mark.parametrize("shape", ["file", "tree"])
def test_snapshot_acquisition_and_terminal_cleanup(tmp_path, monkeypatch, outcome, shape):
    module, storage, source = setup(tmp_path, monkeypatch)
    selected = source if shape == "tree" else source / "payload"
    transaction = module._InstallTransaction([selected], enabled=True)
    from contextlib import nullcontext
    primary = RuntimeError("body")
    receiving = pytest.raises(RuntimeError, match="^body$") if outcome == "rollback" else nullcontext()
    with receiving as caught:
        with transaction:
            assert transaction._image_matches(selected, transaction._original[selected])
            backup = transaction._entries[0]["backup"]
            assert transaction._image_matches(backup, transaction._backup_states[backup])
            if outcome == "commit":
                transaction.commit()
            else:
                # An owned disposal leaves an absent image for the real snapshot inverse.
                transaction._remove_current(selected)
                assert transaction._expected[selected] == {}
                raise primary
    if outcome == "rollback":
        assert caught.value is primary
    assert (source / "payload").read_bytes() == b"original"
    assert transaction._temporary is None
    assert list(storage.iterdir()) == []


def test_partial_acquisition_failure_disposes_only_owned_backup(tmp_path, monkeypatch):
    module, storage, source = setup(tmp_path, monkeypatch)
    transaction = module._InstallTransaction([source], enabled=True)
    copy = transaction._copy_owned_file
    failure = RuntimeError("after copied member")
    def fail(*args, **kwargs):
        copy(*args, **kwargs)
        raise failure
    monkeypatch.setattr(transaction, "_copy_owned_file", fail)
    with pytest.raises(RuntimeError) as caught:
        transaction.__enter__()
    assert caught.value is failure
    assert (source / "payload").read_bytes() == b"original"
    assert list(storage.iterdir()) == []


@pytest.mark.parametrize("truth", ["false", "raises"])
def test_rollback_retains_primary_without_truthiness(tmp_path, monkeypatch, truth):
    module, storage, source = setup(tmp_path, monkeypatch)
    class Primary(RuntimeError):
        def __bool__(self):
            if truth == "raises":
                raise AssertionError("exception truthiness must not run")
            return False
    primary = Primary("original body failure")
    transaction = module._InstallTransaction([source], enabled=True)
    transaction.__enter__()
    # Foreign mutation must retain beforeimage, not be adopted or erased.
    (source / "payload").write_bytes(b"foreign")
    with pytest.raises(module._InstallFailure) as caught:
        transaction.__exit__(Primary, primary, primary.__traceback__)
    assert caught.value.__cause__ is primary
    assert (source / "payload").read_bytes() == b"foreign"
    assert transaction._temporary.exists()
    backup = transaction._entries[0]["backup"]
    assert (backup / "payload").read_bytes() == b"original"


def test_acquisition_cleanup_refuses_foreign_backup_member(tmp_path, monkeypatch):
    module, storage, source = setup(tmp_path, monkeypatch)
    transaction = module._InstallTransaction([source], enabled=True)
    copy = transaction._copy_snapshot
    primary = RuntimeError("acquisition interrupted")
    def interrupt(*args, **kwargs):
        copy(*args, **kwargs)
        (transaction._temporary / "foreign").write_bytes(b"preserve")
        raise primary
    monkeypatch.setattr(transaction, "_copy_snapshot", interrupt)
    with pytest.raises(module._InstallFailure) as caught:
        transaction.__enter__()
    assert caught.value.__cause__ is primary
    assert caught.value.recovery_path == transaction._temporary
    assert (transaction._temporary / "foreign").read_bytes() == b"preserve"
    assert (source / "payload").read_bytes() == b"original"
    assert (transaction._temporary / "0" / "payload").read_bytes() == b"original"


def test_uncommitted_unchanged_snapshot_reports_without_retention(tmp_path, monkeypatch):
    module, storage, source = setup(tmp_path, monkeypatch)
    transaction = module._InstallTransaction([source], enabled=True)
    with pytest.raises(module._InstallFailure, match="E_INSTALL_TRANSACTION_UNCOMMITTED"):
        with transaction:
            pass
    assert transaction._temporary is None
    assert list(storage.iterdir()) == []
    assert (source / "payload").read_bytes() == b"original"

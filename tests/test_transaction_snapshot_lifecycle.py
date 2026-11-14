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


@pytest.mark.parametrize("outcome", ["commit", "rollback"])
@pytest.mark.parametrize("origin", ["fresh", "existing", "legacy"])
def test_scalar_component_terminal_lifecycle(tmp_path, monkeypatch, outcome, origin):
    """Exercise actual scalar writers/inverses; admission alone is substituted."""
    module, storage, source = setup(tmp_path, monkeypatch)
    from contextlib import nullcontext
    target = source / "scalar"
    legacy = source / "legacy"
    if origin != "fresh":
        (target if origin == "existing" else legacy).write_bytes(b"before")
    transaction = module._InstallTransaction([target, legacy], enabled=True)
    primary = RuntimeError("scalar body")
    receiving = pytest.raises(RuntimeError, match="^scalar body$") if outcome == "rollback" else nullcontext()
    with receiving as caught:
        with transaction:
            owner = module._CreateOnlyMutablePath(source, transaction, dry_run=False)
            transaction.transform_scalar(target, legacy, lambda _path: b"after", owner)
            assert target.read_bytes() == b"after"
            assert not legacy.exists()
            if outcome == "commit":
                transaction.commit()
            else:
                raise primary
    if outcome == "rollback":
        assert caught.value is primary
        assert target.exists() == (origin == "existing")
        assert legacy.exists() == (origin == "legacy")
        if origin != "fresh":
            assert (target if origin == "existing" else legacy).read_bytes() == b"before"
    else:
        assert target.read_bytes() == b"after"
        assert not legacy.exists()
    assert transaction._temporary is None
    assert list(storage.iterdir()) == []


def test_scalar_rollback_preserves_foreign_content_and_beforeimage(tmp_path, monkeypatch):
    module, storage, source = setup(tmp_path, monkeypatch)
    target = source / "scalar"
    target.write_bytes(b"before")
    transaction = module._InstallTransaction([target], enabled=True)
    primary = RuntimeError("body after foreign mutation")
    with pytest.raises(module._InstallFailure) as caught:
        with transaction:
            owner = module._CreateOnlyMutablePath(source, transaction, dry_run=False)
            transaction.transform_scalar(target, source / "legacy", lambda _path: b"owned", owner)
            target.write_bytes(b"foreign")
            raise primary
    assert caught.value.__cause__ is primary
    assert target.read_bytes() == b"foreign"
    entry = next(entry for entry in transaction._entries if entry["kind"] == "scalar")
    assert not entry["consumed"]
    assert entry["operation_backup"].read_bytes() == b"before"
    assert transaction._temporary.exists()

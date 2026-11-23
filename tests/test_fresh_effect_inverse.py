"""Fresh-effect inverse without native moves; isolated Windows qualification."""
from pathlib import Path
from types import SimpleNamespace
import os
import pytest
from test_provider_prompt_projections import _load_installer


def _publish_fixture(owner, target, prepared):
    transaction = owner.transaction
    effect = transaction.arm_replacement(target, prepared, owner)
    effect.prepared_path = prepared
    effect.prepared_state = transaction._observe(prepared)
    owner._replace_prepared(target, prepared, effect=effect)


@pytest.mark.parametrize("finish", ["commit", "rollback"])
@pytest.mark.skipif(os.name != "nt", reason="Transaction lifecycle is Windows-only until POSIX backend qualification")
def test_fresh_file_without_native_move(tmp_path, monkeypatch, finish):
    installer = _load_installer()
    target = tmp_path / "installed"
    prepared = tmp_path / "prepared"
    prepared.write_bytes(b"new bytes")
    calls = []
    def unsupported(source, destination, **kwargs):
        calls.append((source, destination))
        return False
    monkeypatch.setattr(installer._InstallTransaction, "_native_publish_no_replace", staticmethod(unsupported))
    transaction = installer._InstallTransaction([target], enabled=True)
    def operation():
        with transaction:
            owner = installer._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
            with transaction.direct_operation():
                _publish_fixture(owner, target, prepared)
            assert target.read_bytes() == b"new bytes"
            if finish == "rollback":
                raise RuntimeError("injected late failure")
            transaction.commit()
    if finish == "rollback":
        with pytest.raises(RuntimeError, match="injected late failure"):
            operation()
        assert not target.exists()
    else:
        operation()
        assert target.read_bytes() == b"new bytes"
    assert calls
    assert not prepared.exists()


@pytest.mark.skipif(os.name != "nt", reason="Transaction lifecycle is Windows-only until POSIX backend qualification")
def test_existing_file_without_native_move_is_preserved(tmp_path, monkeypatch):
    installer = _load_installer()
    target = tmp_path / "installed"
    prepared = tmp_path / "prepared"
    target.write_bytes(b"user bytes")
    prepared.write_bytes(b"replacement")
    monkeypatch.setattr(installer._InstallTransaction, "_native_publish_no_replace", staticmethod(lambda *args, **kwargs: False))
    with pytest.raises(ValueError, match="retained-object atomic capability"):
        with installer._InstallTransaction([target], enabled=True) as transaction:
            owner = installer._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
            with transaction.direct_operation():
                _publish_fixture(owner, target, prepared)
    assert target.read_bytes() == b"user bytes"

@pytest.mark.parametrize("interference", ["content", "identity", "disposal-failure", "runtime-observation"])
@pytest.mark.skipif(os.name != "nt", reason="Transaction lifecycle is Windows-only until POSIX backend qualification")
def test_fresh_inverse_preserves_unqualified_or_failed_effect(tmp_path, monkeypatch, interference):
    from dataclasses import replace
    installer = _load_installer()
    target, prepared = tmp_path / "installed", tmp_path / "prepared"
    prepared.write_bytes(b"created bytes")
    monkeypatch.setattr(installer._InstallTransaction, "_native_publish_no_replace", staticmethod(lambda *args, **kwargs: False))
    transaction = installer._InstallTransaction([target], enabled=True)
    with pytest.raises(RuntimeError):
        with transaction:
            owner = installer._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
            with transaction.direct_operation():
                _publish_fixture(owner, target, prepared)
            if interference == "content":
                target.write_bytes(b"foreign bytes")
            elif interference == "identity":
                target.rename(tmp_path / "preserved-created")
                target.write_bytes(b"foreign bytes")
            elif interference == "disposal-failure":
                dispose = transaction._dispose_node
                def refuse_selected(path, node):
                    if path == target:
                        raise OSError("injected disposal failure")
                    return dispose(path, node)
                monkeypatch.setattr(transaction, "_dispose_node", refuse_selected)
            else:
                effect = transaction._effects[0]
                transaction._advance(target, {target: replace(effect.actual[target], evidence_role="runtime-observation")})
            raise RuntimeError("injected late failure")
    expected = b"foreign bytes" if interference in {"content", "identity"} else b"created bytes"
    assert target.read_bytes() == expected
    assert any(not effect.settled for effect in transaction._effects)


@pytest.mark.skipif(os.name != "nt", reason="Transaction lifecycle is Windows-only until POSIX backend qualification")
def test_fresh_tree_rollback_uses_owned_images(tmp_path):
    installer = _load_installer()
    target, prepared = tmp_path / "installed", tmp_path / "prepared"
    prepared.mkdir()
    (prepared / "nested").mkdir()
    (prepared / "nested" / "data").write_bytes(b"new bytes")
    with pytest.raises(RuntimeError, match="injected late failure"):
        with installer._InstallTransaction([target], enabled=True) as transaction:
            owner = installer._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
            with transaction.direct_operation():
                _publish_fixture(owner, target, prepared)
            raise RuntimeError("injected late failure")
    assert not target.exists()


@pytest.mark.skipif(os.name != "nt", reason="Transaction lifecycle is Windows-only until POSIX backend qualification")
def test_missing_directory_atomic_publish_stays_refused(tmp_path, monkeypatch):
    installer = _load_installer()
    target, prepared = tmp_path / "installed", tmp_path / "prepared"
    prepared.mkdir()
    (prepared / "data").write_bytes(b"new bytes")
    monkeypatch.setattr(installer._InstallTransaction, "_native_publish_no_replace", staticmethod(lambda *args, **kwargs: False))
    with pytest.raises(RuntimeError, match="E_ATOMIC_DIRECTORY_PUBLISH_UNSUPPORTED"):
        with installer._InstallTransaction([target], enabled=True) as transaction:
            owner = installer._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
            with transaction.direct_operation():
                _publish_fixture(owner, target, prepared)
    assert not target.exists()
    assert (prepared / "data").read_bytes() == b"new bytes"

@pytest.mark.parametrize("interference", ["pending-migration", "partial-disposal"])
@pytest.mark.skipif(os.name != "nt", reason="Transaction lifecycle is Windows-only until POSIX backend qualification")
def test_fresh_tree_failed_inverse_tracks_remaining_owned_nodes(tmp_path, monkeypatch, interference):
    installer = _load_installer()
    target, prepared = tmp_path / "installed", tmp_path / "prepared"
    prepared.mkdir()
    (prepared / "data").write_bytes(b"created bytes")
    transaction = installer._InstallTransaction([target], enabled=True)
    with pytest.raises(RuntimeError):
        with transaction:
            owner = installer._CreateOnlyMutablePath(tmp_path, transaction, dry_run=False)
            with transaction.direct_operation():
                _publish_fixture(owner, target, prepared)
            if interference == "pending-migration":
                original = transaction._migration_dependencies
                monkeypatch.setattr(transaction, "_migration_dependencies", lambda root: (object(),) if root == target else original(root))
            else:
                dispose = transaction._dispose_node
                def refuse_root(path, node):
                    if path == target:
                        raise OSError("injected root disposal failure")
                    return dispose(path, node)
                monkeypatch.setattr(transaction, "_dispose_node", refuse_root)
            raise RuntimeError("injected late failure")
    effect = transaction._effects[0]
    assert not effect.settled
    assert target.exists()
    if interference == "pending-migration":
        assert (target / "data").read_bytes() == b"created bytes"
    else:
        assert not (target / "data").exists()
        assert set(effect.actual) == {target}
        # A later replacement is not adopted by inverse reentry.
        target.rename(tmp_path / "preserved-empty")
        target.mkdir()
        (target / "foreign").write_bytes(b"preserve foreign")
        _unresolved, failures, _errors = transaction._settle_effects()
        assert failures
        assert (target / "foreign").read_bytes() == b"preserve foreign"


def test_unqualified_transaction_preserves_prepared_image(tmp_path, monkeypatch):
    """An unsupported platform must refuse before transaction writes."""
    installer = _load_installer()
    target, prepared = tmp_path / "installed", tmp_path / "prepared"
    prepared.mkdir()
    payload = prepared / "data"
    payload.write_bytes(b"preserve prepared bytes")
    identity = (prepared.stat().st_dev, prepared.stat().st_ino)
    transaction = installer._InstallTransaction([target], enabled=True)
    monkeypatch.setattr(installer, "os", SimpleNamespace(name="unsupported-platform"))
    entered = False
    with pytest.raises(ValueError, match="E_EFFECT_BOUND_DISPOSAL_UNQUALIFIED"):
        with transaction:
            entered = True
    assert not entered
    assert transaction._temporary is None
    assert not target.exists()
    assert list(tmp_path.iterdir()) == [prepared]
    assert list(prepared.iterdir()) == [payload]
    assert payload.read_bytes() == b"preserve prepared bytes"
    assert (prepared.stat().st_dev, prepared.stat().st_ino) == identity

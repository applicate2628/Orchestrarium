"""Native tree/journal component checks with test-only admission.

These tests do not qualify public transaction entry. Only the admission check and
leaf dispatch are substituted; image validation, journal advancement, and all
filesystem effects use the actual owners.
"""
from dataclasses import replace
import os
from types import SimpleNamespace
import pytest
from test_provider_prompt_projections import _load_installer

pytestmark = pytest.mark.skipif(os.name != "posix", reason="Native POSIX component effects")


def fixture(tmp_path, monkeypatch):
    module = _load_installer()
    root = tmp_path / "tree"
    root.mkdir()
    (root / "first").write_bytes(b"one")
    (root / "second").write_bytes(b"two")
    outside = tmp_path / "outside"
    outside.write_bytes(b"untouched")
    (root / "link").symlink_to("../outside")
    transaction = module._InstallTransaction([], enabled=False)
    image = transaction._observe(root)
    transaction._expected[root] = dict(image)
    transaction._copy_current = dict(image)
    parent_id = module._CreateOnlyMutablePath._identity(tmp_path)
    root_id = image[root].python_identity
    transaction._slice_a_created = [
        module._SliceACreatedRecord(
            anchor_path=tmp_path, anchor_identity=parent_id,
            root_path=root, root_identity=root_id,
            parent_path=path.parent,
            parent_identity=module._CreateOnlyMutablePath._identity(path.parent),
            leaf_path=path, leaf_identity=node.python_identity, kind=node.kind,
            digest=node.data, projection_target=None)
        for path, node in image.items()]
    transaction._migration_retention = {
        path: (path, node.python_identity, node, None) for path, node in image.items()}
    monkeypatch.setattr(module, "_require_transaction_disposal_backend", lambda: None)
    monkeypatch.setattr(transaction, "_dispose_node", transaction._dispose_posix_node)
    return module, transaction, root, image, outside


def test_tree_consumption_updates_owned_journals(tmp_path, monkeypatch):
    module, transaction, root, image, outside = fixture(tmp_path, monkeypatch)
    transaction._dispose_image(root, image)
    assert not root.exists()
    assert outside.read_bytes() == b"untouched"
    assert transaction._expected[root] == {}
    assert transaction._copy_current == {}
    assert all(record.consumed for record in transaction._slice_a_created)
    assert transaction._migration_retention == {}


@pytest.mark.parametrize("drift", ["foreign-member", "content", "observed"])
def test_preflight_refusal_does_not_advance_journal(tmp_path, monkeypatch, drift):
    module, transaction, root, image, outside = fixture(tmp_path, monkeypatch)
    if drift == "foreign-member":
        (root / "foreign").write_bytes(b"preserve")
    elif drift == "content":
        (root / "first").write_bytes(b"changed")
    else:
        image[root / "first"] = replace(image[root / "first"], evidence_role="observed")
    before = dict(transaction._expected[root])
    with pytest.raises(ValueError, match="E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY"):
        transaction._dispose_image(root, image)
    assert transaction._expected[root] == before
    assert not any(record.consumed for record in transaction._slice_a_created)
    assert set(transaction._migration_retention) == set(before)
    assert (root / "second").read_bytes() == b"two"
    assert outside.read_bytes() == b"untouched"


def test_partial_failure_advances_only_completed_members(tmp_path, monkeypatch):
    module, transaction, root, image, outside = fixture(tmp_path, monkeypatch)
    done = []
    leaf_owner = transaction._dispose_posix_node
    def fail_second(path, node):
        if done:
            raise RuntimeError("injected before second leaf")
        leaf_owner(path, node)
        done.append(path)
    monkeypatch.setattr(transaction, "_dispose_node", fail_second)
    with pytest.raises(RuntimeError, match="before second leaf"):
        transaction._dispose_image(root, image)
    assert len(done) == 1
    removed = done[0]
    assert not os.path.lexists(removed)
    assert set(transaction._expected[root]) == set(image) - {removed}
    assert set(transaction._copy_current) == set(image) - {removed}
    assert {record.leaf_path for record in transaction._slice_a_created if record.consumed} == {removed}
    assert set(transaction._migration_retention) == set(image) - {removed}
    assert outside.read_bytes() == b"untouched"


def test_late_foreign_child_blocks_parent_without_adoption(tmp_path, monkeypatch):
    module, transaction, root, image, outside = fixture(tmp_path, monkeypatch)
    leaf_owner = transaction._dispose_posix_node
    def insert_before_parent(path, node):
        if path == root:
            (root / "foreign").write_bytes(b"preserve")
        leaf_owner(path, node)
    monkeypatch.setattr(transaction, "_dispose_node", insert_before_parent)
    with pytest.raises(OSError):
        transaction._dispose_image(root, image)
    assert (root / "foreign").read_bytes() == b"preserve"
    assert set(transaction._expected[root]) == {root}
    assert set(transaction._migration_retention) == {root}
    assert {record.leaf_path for record in transaction._slice_a_created if not record.consumed} == {root}
    assert outside.read_bytes() == b"untouched"


def test_pending_migration_preserves_whole_image(tmp_path, monkeypatch):
    module, transaction, root, image, outside = fixture(tmp_path, monkeypatch)
    transaction._slice_a_migrated.append(SimpleNamespace(
        settled=False, leaf_path=root / "first", tombstone_path=tmp_path / "retained"))
    with pytest.raises(ValueError, match="pending migration"):
        transaction._dispose_image(root, image)
    assert transaction._expected[root] == image
    assert not any(record.consumed for record in transaction._slice_a_created)
    assert (root / "first").read_bytes() == b"one"


def test_uncertain_leaf_completion_is_not_consumed_or_replayed(tmp_path, monkeypatch):
    module, transaction, root, image, outside = fixture(tmp_path, monkeypatch)
    completed = []
    close = module.os.close
    failure = RuntimeError("injected parent close failure")
    def uncertain(descriptor):
        parent_descriptor = os.path.samestat(os.fstat(descriptor), root.stat())
        close(descriptor)
        if parent_descriptor:
            completed.append(descriptor)
            raise failure
    monkeypatch.setattr(module.os, "close", uncertain)
    with pytest.raises(module._InstallFailure) as caught:
        transaction._dispose_image(root, image)
    assert caught.value.__cause__ is failure
    assert len(completed) == 1
    missing = {path for path in image if not os.path.lexists(path)}
    assert len(missing) == 1
    assert root not in missing
    assert transaction._expected[root] == image
    assert not any(record.consumed for record in transaction._slice_a_created)
    assert set(transaction._migration_retention) == set(image)
    with pytest.raises(ValueError, match="disposal drift"):
        transaction._dispose_image(root, image)
    assert len(completed) == 1
    assert outside.read_bytes() == b"untouched"


def test_completed_tree_updates_effect_and_backup_images(tmp_path, monkeypatch):
    module, transaction, root, image, outside = fixture(tmp_path, monkeypatch)
    effect = SimpleNamespace(
        location=root, actual=dict(image), restored_state=dict(image),
        retained=root, retained_state=dict(image),
        quarantine=root, quarantine_state=dict(image),
        prepared_path=root, prepared_state=dict(image))
    transaction._effects.append(effect)
    transaction._temporary = root
    transaction._backup_root_state = dict(image)
    transaction._dispose_image(root, image)
    for field in ("actual", "restored_state", "retained_state", "quarantine_state", "prepared_state"):
        assert getattr(effect, field) == {}
    assert transaction._backup_root_state == {}
    assert outside.read_bytes() == b"untouched"

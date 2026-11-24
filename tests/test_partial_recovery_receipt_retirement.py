"""Pending recovery receipts keep their native image through owned retirement."""

from pathlib import Path

import pytest

from test_mutate_work_item import load_module


def _settle(module, root: Path, path: Path, data: bytes, *, held: bool):
    def operation(repository: Path):
        assert repository == root
        return module._partial_recovery_settle_receipt(path, data)

    if held:
        operation = module._lifecycle_participant(operation, input_role="repository-root")
    return operation(root)


def _receipt_paths(tmp_path: Path):
    root = tmp_path / "repository"
    (root / "work-items").mkdir(parents=True)
    scratch = root / ".scratch"
    scratch.mkdir()
    receipt = scratch / "receipt.json"
    return root, receipt, scratch / ".receipt.json.pending-v1"


@pytest.mark.parametrize("pending_state", ("absent", "exact", "prefix"))
def test_pending_retirement_publishes_absence_to_held_transaction(tmp_path, pending_state):
    module = load_module()
    root, receipt, pending = _receipt_paths(tmp_path)
    data = b"authorized recovery receipt\n"
    if pending_state != "absent":
        pending.write_bytes(data if pending_state == "exact" else data[:9])

    assert _settle(module, root, receipt, data, held=True) is True
    assert receipt.read_bytes() == data
    assert not pending.exists()
    assert _settle(module, root, receipt, data, held=True) is False


@pytest.mark.parametrize("held", (False, True))
@pytest.mark.parametrize("same_bytes", (False, True))
def test_pending_replacement_during_promotion_preserves_foreign_image(
    tmp_path, monkeypatch, held, same_bytes
):
    module = load_module()
    root, receipt, pending = _receipt_paths(tmp_path)
    data = b"authorized recovery receipt\n"
    foreign = data if same_bytes else b"foreign pending receipt\n"
    observed = {}

    def replace_pending():
        observed["original"] = module._lifecycle_file_identity(receipt.stat())
        # The published destination retains the original native object while
        # an external actor replaces or recreates only the pending name.
        if pending.exists():
            pending.unlink()
        with pending.open("xb") as stream:
            stream.write(foreign)
        observed["foreign"] = module._lifecycle_file_identity(pending.stat())
        assert observed["foreign"] != observed["original"]

    if module.os.name == "nt":
        real_rename = module.LifecycleWriteTarget._windows_rename

        def replace_after_rename(owner, handle, leaf, *, replace):
            result = real_rename(owner, handle, leaf, replace=replace)
            if owner.path == receipt:
                replace_pending()
            return result

        monkeypatch.setattr(module.LifecycleWriteTarget, "_windows_rename", replace_after_rename)
    else:
        real_link = module.os.link

        def replace_after_link(source, destination, **kwargs):
            result = real_link(source, destination, **kwargs)
            if Path(source) in (pending, Path(pending.name)):
                replace_pending()
            return result

        monkeypatch.setattr(module.os, "link", replace_after_link)
    with pytest.raises(module.LifecycleError) as caught:
        _settle(module, root, receipt, data, held=held)

    assert pending.exists(), str(caught.value)
    assert pending.read_bytes() == foreign
    assert module._lifecycle_file_identity(pending.stat()) == observed["foreign"]
    assert receipt.read_bytes() == data
    assert module._lifecycle_file_identity(receipt.stat()) == observed["original"]


def test_pending_recreation_after_owned_retirement_refuses_before_commit(tmp_path, monkeypatch):
    module = load_module()
    root, receipt, pending = _receipt_paths(tmp_path)
    data = b"authorized recovery receipt\n"
    foreign = b"foreign pending recreation\n"
    real_promote = module.LifecycleWriteTarget.promote_create
    observed = {}

    def recreate_after_retirement(owner, image):
        result = real_promote(owner, image)
        if owner.path == receipt:
            with pending.open("xb") as stream:
                stream.write(foreign)
            observed["foreign"] = module._lifecycle_file_identity(pending.stat())
        return result

    monkeypatch.setattr(module.LifecycleWriteTarget, "promote_create", recreate_after_retirement)
    with pytest.raises(module.LifecycleError):
        _settle(module, root, receipt, data, held=True)

    assert observed
    assert pending.read_bytes() == foreign
    assert module._lifecycle_file_identity(pending.stat()) == observed["foreign"]
    assert receipt.read_bytes() == data


@pytest.mark.parametrize("held", (False, True))
def test_pending_recreation_during_durability_preserves_foreign_image(tmp_path, monkeypatch, held):
    module = load_module()
    root, receipt, pending = _receipt_paths(tmp_path)
    data = b"authorized recovery receipt\n"
    foreign = b"foreign pending recreation during durability\n"
    real_fsync = module._partial_recovery_fsync_directory
    observed = {}

    def recreate_after_fsync(parent):
        real_fsync(parent)
        if pending.exists():
            pending.unlink()
        with pending.open("xb") as stream:
            stream.write(foreign)
        observed["foreign"] = module._lifecycle_file_identity(pending.stat())

    monkeypatch.setattr(module, "_partial_recovery_fsync_directory", recreate_after_fsync)
    with pytest.raises(module.LifecycleError):
        _settle(module, root, receipt, data, held=held)

    assert pending.read_bytes() == foreign
    assert module._lifecycle_file_identity(pending.stat()) == observed["foreign"]
    assert receipt.read_bytes() == data


@pytest.mark.parametrize("held", (False, True))
def test_pending_cleanup_failure_does_not_replace_primary(tmp_path, monkeypatch, held):
    module = load_module()
    root, receipt, pending = _receipt_paths(tmp_path)
    data = b"authorized recovery receipt\n"
    primary = module.LifecycleError("WI-TEST-PRIMARY", "promotion refused before publication")
    cleanup = module.LifecycleError("WI-TEST-CLEANUP", "exact pending retirement unavailable")
    observed = {}

    def refuse_promotion(owner, image):
        assert owner.path == receipt
        observed["original"] = module._lifecycle_file_identity(pending.stat())
        raise primary

    def refuse_retirement(owner, leaf, image):
        assert owner.path.parent / leaf == pending
        assert image["identity"]["value"] == list(observed["original"])
        observed["cleanup"] = True
        raise cleanup

    monkeypatch.setattr(module.LifecycleWriteTarget, "promote_create", refuse_promotion)
    monkeypatch.setattr(module.LifecycleWriteTarget, "remove_owned", refuse_retirement)
    with pytest.raises(module.LifecycleError) as caught:
        _settle(module, root, receipt, data, held=held)

    assert caught.value is primary
    assert observed["cleanup"]
    assert pending.read_bytes() == data
    assert module._lifecycle_file_identity(pending.stat()) == observed["original"]
    assert not receipt.exists()

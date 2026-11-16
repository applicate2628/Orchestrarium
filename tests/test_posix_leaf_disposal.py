"""Native ordinary-writer leaf qualification; not transaction admission."""
from dataclasses import replace
import os
from pathlib import Path
import pytest
from test_provider_prompt_projections import _load_installer

pytestmark = pytest.mark.skipif(os.name == "nt", reason="Native POSIX leaf effects")


@pytest.mark.parametrize("kind", ["file", "directory", "link"])
def test_selected_leaf_is_removed(tmp_path, kind):
    module = _load_installer()
    leaf = tmp_path / "owned"
    if kind == "file":
        leaf.write_bytes(b"owned")
    elif kind == "directory":
        leaf.mkdir()
    else:
        leaf.symlink_to("missing-referent")
    transaction = module._InstallTransaction([], enabled=False)
    witness = transaction._capture_node(leaf)
    transaction._dispose_posix_node(leaf, witness)
    assert not os.path.lexists(leaf)


@pytest.mark.parametrize("drift", ["content", "identity", "observed"])
def test_unowned_or_changed_leaf_is_preserved(tmp_path, drift):
    module = _load_installer()
    leaf = tmp_path / "owned"
    leaf.write_bytes(b"original")
    transaction = module._InstallTransaction([], enabled=False)
    witness = transaction._capture_node(leaf)
    if drift == "content":
        leaf.write_bytes(b"changed")
    elif drift == "identity":
        leaf.rename(tmp_path / "retained")
        leaf.write_bytes(b"foreign")
    else:
        witness = replace(witness, evidence_role="observed")
    before = leaf.read_bytes()
    with pytest.raises(ValueError, match="E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY"):
        transaction._dispose_posix_node(leaf, witness)
    assert leaf.read_bytes() == before


def test_nonempty_directory_is_preserved(tmp_path):
    module = _load_installer()
    leaf = tmp_path / "owned"
    leaf.mkdir()
    (leaf / "foreign").write_bytes(b"preserve")
    transaction = module._InstallTransaction([], enabled=False)
    witness = transaction._capture_node(leaf)
    with pytest.raises(OSError):
        transaction._dispose_posix_node(leaf, witness)
    assert (leaf / "foreign").read_bytes() == b"preserve"


def test_link_retarget_is_preserved(tmp_path):
    module = _load_installer()
    leaf = tmp_path / "owned"
    leaf.symlink_to("one")
    transaction = module._InstallTransaction([], enabled=False)
    witness = transaction._capture_node(leaf)
    leaf.unlink()
    leaf.symlink_to("two")
    with pytest.raises(ValueError, match="E_ROLLBACK_RESTORE_BLOCKED_BY_IDENTITY"):
        transaction._dispose_posix_node(leaf, witness)
    assert os.readlink(leaf) == "two"


def test_public_transaction_admission_stays_closed(tmp_path):
    module = _load_installer()
    with pytest.raises(ValueError, match="E_EFFECT_BOUND_DISPOSAL_UNQUALIFIED"):
        with module._InstallTransaction([tmp_path / "target"], enabled=True):
            pytest.fail("unqualified transaction entered")
    assert not (tmp_path / "target").exists()


def test_parent_replacement_during_check_preserves_both_leaves(tmp_path, monkeypatch):
    module = _load_installer()
    parent = tmp_path / "parent"
    parent.mkdir()
    leaf = parent / "owned"
    leaf.write_bytes(b"original")
    transaction = module._InstallTransaction([], enabled=False)
    witness = transaction._capture_node(leaf)
    check = transaction._point_matches
    def replace_parent(*args, **kwargs):
        result = check(*args, **kwargs)
        parent.rename(tmp_path / "retained-parent")
        parent.mkdir()
        leaf.write_bytes(b"foreign")
        return result
    monkeypatch.setattr(transaction, "_point_matches", replace_parent)
    with pytest.raises(ValueError, match="POSIX disposal binding"):
        transaction._dispose_posix_node(leaf, witness)
    assert leaf.read_bytes() == b"foreign"
    assert (tmp_path / "retained-parent" / "owned").read_bytes() == b"original"


def test_symlink_parent_is_not_followed(tmp_path):
    module = _load_installer()
    real = tmp_path / "real"
    real.mkdir()
    (real / "owned").write_bytes(b"keep")
    alias = tmp_path / "alias"
    alias.symlink_to("real", target_is_directory=True)
    transaction = module._InstallTransaction([], enabled=False)
    witness = transaction._capture_node(real / "owned")
    with pytest.raises(OSError):
        transaction._dispose_posix_node(alias / "owned", witness)
    assert (real / "owned").read_bytes() == b"keep"


@pytest.mark.parametrize("has_primary", [False, True])
def test_close_failure_preserves_primary_and_is_not_retried(tmp_path, monkeypatch, has_primary):
    module = _load_installer()
    leaf = tmp_path / "owned"
    leaf.write_bytes(b"original")
    transaction = module._InstallTransaction([], enabled=False)
    witness = transaction._capture_node(leaf)
    class FalseError(RuntimeError):
        def __bool__(self):
            raise AssertionError("exception truthiness must not be evaluated")
    primary = FalseError("selected failure")
    cleanup = KeyboardInterrupt("close failure")
    if has_primary:
        def fail(*args, **kwargs):
            raise primary
        monkeypatch.setattr(transaction, "_point_matches", fail)
    close = module.os.close
    closed = []
    def close_failure(descriptor):
        is_parent = os.path.samestat(os.fstat(descriptor), tmp_path.stat())
        close(descriptor)
        if is_parent:
            closed.append(descriptor)
            raise cleanup
    monkeypatch.setattr(module.os, "close", close_failure)
    with pytest.raises(module._InstallFailure) as failure:
        transaction._dispose_posix_node(leaf, witness)
    assert len(closed) == 1
    assert failure.value.__cause__ is (primary if has_primary else cleanup)
    assert failure.value.members[0].cause_exception is cleanup
    assert os.path.lexists(leaf) is has_primary


def test_typed_primary_survives_close_failure(tmp_path, monkeypatch):
    module = _load_installer()
    leaf = tmp_path / "owned"
    leaf.write_bytes(b"preserve")
    transaction = module._InstallTransaction([], enabled=False)
    witness = transaction._capture_node(leaf)
    original = RuntimeError("copy failure")
    member = module._RollbackFailureMember(
        "copy", 3, str(leaf), "E_ROLLBACK_RESTORE_FAILED", "copy failure",
        participant="scalar", cause_exception=original)
    recovery = tmp_path / "original-recovery"
    primary = module._InstallFailure(
        "E_ROLLBACK_SETTLEMENT_FAILED", "copy", original,
        members=(member,), unresolved_paths=(recovery,), recovery_path=recovery)
    def fail(*args, **kwargs):
        raise primary
    monkeypatch.setattr(transaction, "_point_matches", fail)
    close = module.os.close
    cleanup = RuntimeError("close failure")
    def close_failure(descriptor):
        close(descriptor)
        raise cleanup
    monkeypatch.setattr(module.os, "close", close_failure)
    with pytest.raises(module._InstallFailure) as caught:
        transaction._dispose_posix_node(leaf, witness)
    assert caught.value.__cause__ is primary
    assert caught.value.members[0] is member
    assert caught.value.members[-1].cause_exception is cleanup
    assert recovery in caught.value.unresolved_paths
    assert caught.value.recovery_path == recovery
    assert leaf.read_bytes() == b"preserve"


def test_missing_relative_capability_preserves_leaf(tmp_path, monkeypatch):
    module = _load_installer()
    leaf = tmp_path / "owned"
    leaf.write_bytes(b"preserve")
    transaction = module._InstallTransaction([], enabled=False)
    witness = transaction._capture_node(leaf)
    monkeypatch.setattr(module.os, "supports_dir_fd", set())
    with pytest.raises(ValueError, match="relative disposal capability"):
        transaction._dispose_posix_node(leaf, witness)
    assert leaf.read_bytes() == b"preserve"


def test_replacement_after_content_check_is_preserved(tmp_path, monkeypatch):
    module = _load_installer()
    leaf = tmp_path / "owned"
    leaf.write_bytes(b"original")
    transaction = module._InstallTransaction([], enabled=False)
    witness = transaction._capture_node(leaf)
    check = transaction._point_matches
    def replace_leaf(*args, **kwargs):
        result = check(*args, **kwargs)
        leaf.rename(tmp_path / "retained")
        leaf.write_bytes(b"foreign")
        return result
    monkeypatch.setattr(transaction, "_point_matches", replace_leaf)
    with pytest.raises(ValueError, match="POSIX disposal binding"):
        transaction._dispose_posix_node(leaf, witness)
    assert leaf.read_bytes() == b"foreign"
    assert (tmp_path / "retained").read_bytes() == b"original"

"""Private recovery custody only: no SDK/provider/native process execution."""
import hashlib
import importlib.util
import os
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sdk_recovery_lifecycle_owner", ROOT / "scripts/provider_prompt.py")
owner = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = owner
SPEC.loader.exec_module(owner)


@pytest.fixture
def lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("CODEX_PROMPTS_DIR", str(tmp_path / "captures"))
    value = owner.RunCaptureLifecycle.create("codex", "synthetic")
    value.initialize(b"synthetic prompt")
    yield value
    value.cleanup()


def test_retained_evidence_is_verified_private_and_cleanup_is_idempotent(lifecycle):
    lifecycle.arm_evidence_retention()
    payload = b'{"authorizing":false,"synthetic":true}\n'
    path, digest = lifecycle.persist_recovery_evidence(payload, max_bytes=1024)
    assert path == lifecycle.run_dir / "sdk-recovery.json"
    assert path.read_bytes() == payload
    assert digest == hashlib.sha256(payload).hexdigest()
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600
    result = lifecycle.cleanup()
    assert result.clean and result.recovery_retained
    assert lifecycle.cleanup() is result
    assert not lifecycle._has_unresolved_resources()
    assert path.read_bytes() == payload


def test_success_release_restores_ordinary_purge(lifecycle):
    lifecycle.arm_evidence_retention()
    lifecycle.persist_recovery_evidence(b'{}\n', max_bytes=3)
    lifecycle.release_evidence_retention()
    result = lifecycle.cleanup()
    assert result.clean and not result.recovery_retained
    assert not lifecycle.run_dir.exists()


@pytest.mark.parametrize("fault", ("partial-write", "readback"))
@pytest.mark.skipif(os.name == "nt", reason="POSIX injected descriptor faults; Windows qualification separate")
def test_persistence_failure_retains_partial_bytes_and_closes_resources(lifecycle, monkeypatch, fault):
    lifecycle.arm_evidence_retention()
    payload = b'{"synthetic":"retained"}\n'
    original = owner.TerminalReceiptV1.commit

    def fail(receipt, data):
        if fault == "partial-write":
            os.write(receipt.file_handle, data[:8])
            raise OSError("synthetic partial write")
        original(receipt, data)
        raise OSError("synthetic readback failure")

    monkeypatch.setattr(owner.TerminalReceiptV1, "commit", fail)
    with pytest.raises(OSError, match="synthetic"):
        lifecycle.persist_recovery_evidence(payload, max_bytes=1024)
    path = lifecycle.run_dir / "sdk-recovery.json"
    expected = payload[:8] if fault == "partial-write" else payload
    assert path.read_bytes() == expected
    with pytest.raises(ValueError, match="cannot be released"):
        lifecycle.release_evidence_retention()
    result = lifecycle.cleanup()
    assert not result.clean and result.recovery_retained
    assert "capture-evidence-persistence-incomplete" in result.issues
    assert not lifecycle._has_unresolved_resources()
    assert path.read_bytes() == expected
    assert lifecycle.cleanup() is result


@pytest.mark.parametrize("kind", ("ordinary", "symlink"))
def test_foreign_leaf_is_never_overwritten_or_purged(lifecycle, tmp_path, kind):
    lifecycle.arm_evidence_retention()
    foreign = tmp_path / "foreign"
    foreign.write_bytes(b"foreign evidence")
    path = lifecycle.run_dir / "sdk-recovery.json"
    if kind == "symlink":
        path.symlink_to(foreign)
    else:
        path.write_bytes(b"unowned leaf")
    with pytest.raises(ValueError):
        lifecycle.persist_recovery_evidence(b'{}\n', max_bytes=3)
    result = lifecycle.cleanup()
    assert not result.clean and result.recovery_retained
    assert foreign.read_bytes() == b"foreign evidence"
    assert path.is_symlink() if kind == "symlink" else path.read_bytes() == b"unowned leaf"
    assert not lifecycle._has_unresolved_resources()


@pytest.mark.parametrize("payload,budget", ((b'{}\n', 2), (b'', 1), (b'{}', 2), (b'{}\n', True), (b'{}\n', 0)))
def test_payload_budget_validation_does_not_create_file(lifecycle, payload, budget):
    lifecycle.arm_evidence_retention()
    with pytest.raises(ValueError, match="budget invalid"):
        lifecycle.persist_recovery_evidence(payload, max_bytes=budget)
    assert not (lifecycle.run_dir / "sdk-recovery.json").exists()
    assert lifecycle.cleanup().recovery_retained


def test_persistence_requires_armed_and_is_single_use(lifecycle):
    with pytest.raises(ValueError, match="state invalid"):
        lifecycle.persist_recovery_evidence(b'{}\n', max_bytes=3)
    lifecycle.arm_evidence_retention()
    path, _ = lifecycle.persist_recovery_evidence(b'{}\n', max_bytes=3)
    with pytest.raises(ValueError, match="state invalid"):
        lifecycle.persist_recovery_evidence(b'[]\n', max_bytes=3)
    assert path.read_bytes() == b'{}\n'
    lifecycle.cleanup()
    with pytest.raises(ValueError, match="already settled"):
        lifecycle.arm_evidence_retention()
    with pytest.raises(ValueError, match="cannot be released"):
        lifecycle.release_evidence_retention()


@pytest.mark.skipif(os.name == "nt", reason="POSIX namespace swap; Windows qualification separate")
def test_retargeted_directory_is_not_claimed_or_purged(lifecycle):
    lifecycle.arm_evidence_retention()
    path, _ = lifecycle.persist_recovery_evidence(b'{}\n', max_bytes=3)
    original = lifecycle.run_dir.with_name("original")
    lifecycle.run_dir.rename(original)
    lifecycle.run_dir.mkdir()
    foreign = lifecycle.run_dir / "foreign"
    foreign.write_bytes(b"preserve")
    result = lifecycle.cleanup()
    assert not result.clean and not result.recovery_retained
    assert "capture-evidence-retention-unknown" in result.issues
    assert foreign.read_bytes() == b"preserve"
    assert (original / path.name).read_bytes() == b'{}\n'
    assert not lifecycle._has_unresolved_resources()


def test_receipt_close_failure_never_retries_uncertain_close(lifecycle, monkeypatch):
    lifecycle.arm_evidence_retention()
    original = owner.TerminalReceiptV1.close
    calls = []

    def fail_after_close(receipt):
        calls.append(receipt)
        original(receipt)
        raise OSError("synthetic close effect uncertain")

    monkeypatch.setattr(owner.TerminalReceiptV1, "close", fail_after_close)
    with pytest.raises(OSError, match="effect uncertain"):
        lifecycle.persist_recovery_evidence(b'{}\n', max_bytes=3)
    result = lifecycle.cleanup()
    assert not result.clean and result.recovery_retained
    assert lifecycle._has_unresolved_resources()  # Uncertainty is retained, not guessed closed.
    assert len(calls) == 1
    assert lifecycle._child_resource is None
    assert lifecycle._namespace.resources == []
    assert lifecycle.cleanup() is result
    assert (lifecycle.run_dir / "sdk-recovery.json").read_bytes() == b'{}\n'


def test_leaf_replacement_after_writer_close_has_no_verified_locator(lifecycle, monkeypatch):
    lifecycle.arm_evidence_retention()
    original = owner.TerminalReceiptV1.close

    def replace_after_close(receipt):
        original(receipt)
        receipt.path.rename(receipt.path.with_name("saved-original"))
        receipt.path.write_bytes(b"foreign replacement")

    monkeypatch.setattr(owner.TerminalReceiptV1, "close", replace_after_close)
    with pytest.raises(OSError, match="leaf identity changed"):
        lifecycle.persist_recovery_evidence(b'{}\n', max_bytes=3)
    with pytest.raises(ValueError, match="cannot be released"):
        lifecycle.release_evidence_retention()
    result = lifecycle.cleanup()
    assert not result.clean and result.recovery_retained
    assert (lifecycle.run_dir / "sdk-recovery.json").read_bytes() == b"foreign replacement"
    assert (lifecycle.run_dir / "saved-original").read_bytes() == b'{}\n'


def test_leaf_replacement_blocks_release_and_preserves_foreign_bytes(lifecycle):
    lifecycle.arm_evidence_retention()
    path, _ = lifecycle.persist_recovery_evidence(b'{}\n', max_bytes=3)
    path.rename(path.with_name("saved-original"))
    path.write_bytes(b"foreign replacement")
    with pytest.raises(OSError, match="leaf identity changed"):
        lifecycle.release_evidence_retention()
    assert lifecycle.cleanup().recovery_retained
    assert path.read_bytes() == b"foreign replacement"

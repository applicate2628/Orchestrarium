from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "scripts" / "agent-run-ledger.py"
RECORDED_AT = "2026-09-10T12:00:00Z"
OPERATION_ID = "linked-ledger-replay"
ORIGINAL = (
    b'{"date":"2026-09-10","lane":"example","execution_role":"analyst",'
    b'"result":"historical note"}\n'
)


def load_ledger(name: str):
    spec = importlib.util.spec_from_file_location(name, LEDGER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_fixture(tmp_path: Path, name: str):
    ledger = load_ledger(name)
    item = tmp_path / "work-items" / "active" / "identity-bound-publish"
    item.mkdir(parents=True)
    expected_sha256 = hashlib.sha256(ORIGINAL).hexdigest()
    history = item / f"agent-runs.history.{expected_sha256}.jsonl"
    history.write_bytes(ORIGINAL)
    marker = ledger._noncanonical_history_marker(
        item, expected_sha256, ORIGINAL, OPERATION_ID, RECORDED_AT
    )
    marker_bytes = (ledger.serialize_event(marker) + "\n").encode("utf-8")
    return ledger, item, expected_sha256, marker_bytes


def command_for(ledger, operation: str):
    return (
        ledger._command_apply_noncanonical_history
        if operation == "apply"
        else ledger._command_rollback_noncanonical_history
    )


@pytest.mark.parametrize("operation", ("apply", "rollback"))
def test_fixed_candidate_swap_is_quarantined_before_canonical_replace(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    ledger, item, expected_sha256, marker_bytes = make_fixture(
        tmp_path, f"pr10_identity_swap_{operation}"
    )
    canonical = item / "agent-runs.jsonl"
    initial = ORIGINAL if operation == "apply" else marker_bytes
    canonical.write_bytes(initial)
    candidate = item / "agent-runs.jsonl.tmp"
    foreign = b"foreign fixed-name replacement\n"
    original_replace = ledger.os.replace
    raced = False

    def racing_replace(source, destination, *args, **kwargs):
        nonlocal raced
        if Path(source) == candidate and not raced:
            raced = True
            replacement = candidate.with_suffix(".foreign")
            replacement.write_bytes(foreign)
            original_replace(replacement, candidate)
        return original_replace(source, destination, *args, **kwargs)

    monkeypatch.setattr(ledger.os, "replace", racing_replace)
    monkeypatch.setattr(
        ledger, "_validate_noncanonical_marker_candidate", lambda *_args: None
    )

    with pytest.raises(ledger.LedgerNoncanonicalRecoveryError):
        command_for(ledger, operation)(
            item,
            expected_sha256,
            OPERATION_ID,
            RECORDED_AT,
            ledger.load_validator(),
            None,
        )

    assert raced is True
    assert canonical.read_bytes() == initial
    quarantined = [
        path
        for path in item.rglob("*")
        if path.is_file() and path.read_bytes() == foreign
    ]
    assert quarantined, "the foreign object must be preserved, not published or deleted"


@pytest.mark.parametrize("operation", ("apply", "rollback"))
def test_canonical_replace_uses_the_admitted_inode_via_private_handoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    ledger, item, expected_sha256, marker_bytes = make_fixture(
        tmp_path, f"pr10_identity_handoff_{operation}"
    )
    canonical = item / "agent-runs.jsonl"
    initial = ORIGINAL if operation == "apply" else marker_bytes
    expected = marker_bytes if operation == "apply" else ORIGINAL
    canonical.write_bytes(initial)
    candidate = item / "agent-runs.jsonl.tmp"
    captured_identity = None
    publication_identity = None
    original_write = ledger._write_exact_staging_file
    original_replace = ledger.os.replace

    def capture_write(path: Path, value: bytes):
        nonlocal captured_identity
        identity = original_write(path, value)
        if path == candidate:
            captured_identity = identity
        return identity

    def capture_replace(source, destination, *args, **kwargs):
        nonlocal publication_identity
        source_path = Path(source)
        destination_path = Path(destination)
        if destination_path == canonical and source_path != candidate:
            metadata = source_path.stat()
            publication_identity = ledger._noncanonical_file_identity(metadata)
        return original_replace(source, destination, *args, **kwargs)

    monkeypatch.setattr(ledger, "_write_exact_staging_file", capture_write)
    monkeypatch.setattr(ledger.os, "replace", capture_replace)
    monkeypatch.setattr(
        ledger, "_validate_noncanonical_marker_candidate", lambda *_args: None
    )

    completed, _history = command_for(ledger, operation)(
        item,
        expected_sha256,
        OPERATION_ID,
        RECORDED_AT,
        ledger.load_validator(),
        None,
    )

    assert completed is False
    assert captured_identity is not None
    assert publication_identity == captured_identity
    assert canonical.read_bytes() == expected
    assert not candidate.exists()
    assert not list(item.glob(".agent-runs.jsonl.tmp.publish-*"))

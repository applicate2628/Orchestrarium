from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
MUTATE = ROOT / "scripts" / "mutate-work-item.py"
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"
LEDGER = ROOT / "scripts" / "agent-run-ledger.py"
CHECKER = ROOT / "scripts" / "check-work-items-state.py"
LEGACY_TRANSFER_TESTS = ROOT / "tests" / "test_legacy_obligation_migration.py"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_h1_artifact_set_digest_binds_directory_snapshot_bytes() -> None:
    lifecycle = load_module(MUTATE, "pr10_h1_digest_owner")
    base = [
        {
            "logicalPath": "work-items/ledger-h1-migration-receipts",
            "kind": "directory",
            "byteLength": 17,
            "sha256": "a" * 64,
        }
    ]
    changed_digest = [dict(base[0], sha256="b" * 64)]
    changed_length = [dict(base[0], byteLength=18)]

    observed = lifecycle._ledger_h1_artifact_set_digest(base)

    assert lifecycle._ledger_h1_artifact_set_digest(changed_digest) != observed
    assert lifecycle._ledger_h1_artifact_set_digest(changed_length) != observed


def _transfer_receipt_payload(validator, archive_path: str, ledger: bytes, operation_id: str) -> dict:
    ledger_sha256 = hashlib.sha256(ledger).hexdigest()
    return {
        "schemaVersion": 2,
        "owner": "mutate-work-item:archive-with-successor-v2",
        "operationId": operation_id,
        "archivePath": archive_path,
        "ledgerSha256": ledger_sha256,
        "archiveIdentity": validator.archived_ledger_identity(archive_path, ledger_sha256),
        "obligations": [],
    }


def test_transfer_receipt_symlink_never_supplies_authority(tmp_path: Path) -> None:
    validator = load_module(VALIDATOR, "pr10_transfer_symlink_validator")
    root = tmp_path / "repo"
    archive = root / "work-items" / "archive" / "2026-09" / "source-item"
    archive.mkdir(parents=True)
    ledger = b"{}\n"
    (archive / "agent-runs.jsonl").write_bytes(ledger)
    archive_path = archive.relative_to(root).as_posix()
    payload = _transfer_receipt_payload(validator, archive_path, ledger, "transfer-symlink-op")
    external = tmp_path / "external-receipt.json"
    external.write_text(json.dumps(payload), encoding="utf-8")
    receipt = archive / "lifecycle-transition-receipt.json"
    try:
        receipt.symlink_to(external)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    errors: list[str] = []
    receipts = validator._transfer_receipts(root, errors)

    assert receipts == {}
    assert any("WI-OBLIGATION-TRANSFER-OWNER" in error for error in errors)


def test_transfer_receipt_archive_path_is_assertion_not_locator(tmp_path: Path) -> None:
    validator = load_module(VALIDATOR, "pr10_transfer_path_validator")
    root = tmp_path / "repo"
    archive = root / "work-items" / "archive" / "2026-09" / "source-item"
    archive.mkdir(parents=True)
    external_archive = tmp_path / "outside-ledger"
    external_archive.mkdir()
    ledger = b"{}\n"
    (external_archive / "agent-runs.jsonl").write_bytes(ledger)
    unsafe_archive_path = "../outside-ledger"
    payload = _transfer_receipt_payload(
        validator, unsafe_archive_path, ledger, "transfer-escape-op"
    )
    (archive / "lifecycle-transition-receipt.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )

    errors: list[str] = []
    receipts = validator._transfer_receipts(root, errors)

    assert receipts == {}
    assert errors


def _write_transfer_authority_fixture(
    tmp_path: Path, validator, operation_id: str, ledger: bytes
) -> tuple[Path, Path]:
    root = tmp_path / "repo"
    archive = root / "work-items" / "archive" / "2026-09" / "source-item"
    archive.mkdir(parents=True)
    ledger_path = archive / "agent-runs.jsonl"
    ledger_path.write_bytes(ledger)
    archive_path = archive.relative_to(root).as_posix()
    payload = _transfer_receipt_payload(validator, archive_path, ledger, operation_id)
    (archive / "lifecycle-transition-receipt.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )
    return root, ledger_path


def test_transfer_ledger_digest_never_uses_unbounded_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validator = load_module(VALIDATOR, "pr10_transfer_streaming_digest_validator")
    operation_id = "transfer-streaming-digest-op"
    root, _ledger_path = _write_transfer_authority_fixture(
        tmp_path, validator, operation_id, b'{"schemaVersion":1}\n'
    )
    original_fdopen = validator.os.fdopen
    requested_sizes: list[int] = []

    class TrackingReader:
        def __init__(self, descriptor: int, mode: str) -> None:
            self.stream = original_fdopen(descriptor, mode)

        def __enter__(self):
            self.stream.__enter__()
            return self

        def fileno(self) -> int:
            return self.stream.fileno()

        def read(self, size: int = -1) -> bytes:
            requested_sizes.append(size)
            return self.stream.read(size)

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

    monkeypatch.setattr(validator.os, "fdopen", TrackingReader)

    errors: list[str] = []
    receipts = validator._transfer_receipts(root, errors)

    assert operation_id in receipts
    assert errors == []
    assert requested_sizes
    assert -1 not in requested_sizes


def test_transfer_ledger_digest_enforces_fixed_cumulative_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    validator = load_module(VALIDATOR, "pr10_transfer_ledger_limit_validator")
    operation_id = "transfer-ledger-limit-op"
    ledger = b'{"schemaVersion":1}\n' * 8
    root, _ledger_path = _write_transfer_authority_fixture(
        tmp_path, validator, operation_id, ledger
    )
    monkeypatch.setattr(
        validator, "MAX_TRANSFER_LEDGER_BYTES", len(ledger) - 1, raising=False
    )

    errors: list[str] = []
    receipts = validator._transfer_receipts(root, errors)

    assert receipts == {}
    assert any(
        error.startswith("WI-OBLIGATION-TRANSFER-DRIFT:")
        and f"{len(ledger) - 1} bytes" in error
        for error in errors
    )


def _break_transfer_relation(fixture: dict) -> None:
    backlog = (
        fixture["root"]
        / "work-items"
        / "backlog"
        / f"{fixture['successorSlug']}.md"
    )
    text = backlog.read_text(encoding="utf-8")
    text = "\n".join(
        line
        for line in text.splitlines()
        if not line.startswith("Continues:")
        and not line.startswith("Obligation-transfer:")
    ) + "\n"
    backlog.write_text(text, encoding="utf-8")


def test_transfer_chain_endpoint_must_retain_owner_relation(tmp_path: Path) -> None:
    fixtures = load_module(LEGACY_TRANSFER_TESTS, "pr10_legacy_transfer_fixtures")
    fixture = fixtures.transfer_fixture(tmp_path)
    fixtures.run_transfer(fixture)
    _break_transfer_relation(fixture)

    with pytest.raises(fixture["lifecycle"].LifecycleError) as caught:
        fixture["lifecycle"].audit(fixture["root"])

    assert caught.value.failure_id == "WI-OBLIGATION-TRANSFER-OWNER"


def test_active_only_checker_cannot_hide_broken_transfer_owner(tmp_path: Path) -> None:
    fixtures = load_module(LEGACY_TRANSFER_TESTS, "pr10_checker_transfer_fixtures")
    fixture = fixtures.transfer_fixture(tmp_path)
    fixtures.run_transfer(fixture)
    _break_transfer_relation(fixture)

    result = subprocess.run(
        [
            sys.executable,
            str(CHECKER),
            "--root",
            str(fixture["root"]),
            "--active-only",
        ],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    assert result.returncode == 1, result.stdout + result.stderr
    assert "WI-OBLIGATION-TRANSFER-OWNER" in result.stdout + result.stderr


def test_captured_successor_detects_same_size_in_place_rewrite(tmp_path: Path) -> None:
    lifecycle = load_module(MUTATE, "pr10_successor_capture_owner")
    successor = tmp_path / "successor.md"
    successor.write_bytes(b"accepted-version")
    snapshot = lifecycle._capture_file_snapshot(
        successor, failure_id="WI-BUG-SUCCESSOR-BINDING"
    )
    successor.write_bytes(b"rewritten-versio")
    assert len(successor.read_bytes()) == len(snapshot.data)

    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle._verify_captured_file(snapshot, "WI-BUG-SUCCESSOR-BINDING")

    assert caught.value.failure_id == "WI-BUG-SUCCESSOR-BINDING"


def test_noncanonical_staging_rejects_existing_symlink(tmp_path: Path) -> None:
    ledger = load_module(LEDGER, "pr10_noncanonical_staging_owner")
    external = tmp_path / "external"
    expected = b"exact staging bytes\n"
    external.write_bytes(expected)
    staging = tmp_path / "agent-runs.jsonl.tmp"
    try:
        staging.symlink_to(external)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    with pytest.raises(ledger.LedgerNoncanonicalRecoveryError):
        ledger._write_exact_staging_file(staging, expected)

    assert staging.is_symlink()
    assert external.read_bytes() == expected


def test_noncanonical_staging_rejects_external_hardlink(tmp_path: Path) -> None:
    ledger = load_module(LEDGER, "pr10_noncanonical_hardlink_owner")
    external = tmp_path / "external-hardlink-source"
    expected = b"exact staging bytes\n"
    external.write_bytes(expected)
    staging = tmp_path / "agent-runs.jsonl.tmp"
    try:
        os.link(external, staging)
    except OSError as exc:
        pytest.skip(f"hardlink unavailable: {exc}")

    with pytest.raises(ledger.LedgerNoncanonicalRecoveryError):
        ledger._write_exact_staging_file(staging, expected)

    assert staging.exists()
    assert external.read_bytes() == expected


def test_noncanonical_staging_existing_candidate_read_is_bounded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledger = load_module(LEDGER, "pr10_noncanonical_bounded_staging_owner")
    expected = b"exact staging bytes\n"
    staging = tmp_path / "agent-runs.jsonl.tmp"
    staging.write_bytes(expected + b"foreign trailing bytes")
    original_fdopen = ledger.os.fdopen
    requested_sizes = []

    class TrackingReader:
        def __init__(self, descriptor, mode):
            self.stream = original_fdopen(descriptor, mode)

        def __enter__(self):
            self.stream.__enter__()
            return self

        def fileno(self):
            return self.stream.fileno()

        def read(self, size=-1):
            requested_sizes.append(size)
            return self.stream.read(size)

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

    monkeypatch.setattr(ledger.os, "fdopen", TrackingReader)

    with pytest.raises(ledger.LedgerNoncanonicalRecoveryError):
        ledger._write_exact_staging_file(staging, expected)

    assert requested_sizes == [len(expected) + 1]
    assert staging.exists()


def _noncanonical_replay_fixture(tmp_path: Path, module_name: str):
    ledger = load_module(LEDGER, module_name)
    item = tmp_path / "work-items" / "active" / "noncanonical-replay"
    item.mkdir(parents=True)
    original = (
        b'{"date":"2026-09-10","lane":"example","execution_role":"analyst",'
        b'"result":"historical note"}\n'
    )
    expected_sha256 = hashlib.sha256(original).hexdigest()
    history = item / f"agent-runs.history.{expected_sha256}.jsonl"
    history.write_bytes(original)
    marker = ledger._noncanonical_history_marker(
        item, expected_sha256, original, "linked-ledger-replay", "2026-09-10T12:00:00Z"
    )
    marker_bytes = (ledger.serialize_event(marker) + "\n").encode("utf-8")
    return ledger, item, expected_sha256, marker_bytes


@pytest.mark.parametrize("operation", ("apply", "rollback"))
def test_noncanonical_recovery_preserves_foreign_candidate(
    tmp_path: Path, operation: str
) -> None:
    ledger, item, expected_sha256, marker_bytes = _noncanonical_replay_fixture(
        tmp_path, f"pr10_foreign_candidate_{operation}_owner"
    )
    history = item / f"agent-runs.history.{expected_sha256}.jsonl"
    original = history.read_bytes()
    canonical = item / "agent-runs.jsonl"
    canonical.write_bytes(original if operation == "apply" else marker_bytes)
    candidate = item / "agent-runs.jsonl.tmp"
    foreign = b"foreign staging candidate\n"
    candidate.write_bytes(foreign)
    command = (
        ledger._command_apply_noncanonical_history
        if operation == "apply"
        else ledger._command_rollback_noncanonical_history
    )

    with pytest.raises(ledger.LedgerNoncanonicalRecoveryError):
        command(
            item, expected_sha256, "linked-ledger-replay",
            "2026-09-10T12:00:00Z", ledger.load_validator(), None,
        )

    assert candidate.read_bytes() == foreign


@pytest.mark.parametrize("operation", ("apply", "rollback"))
def test_noncanonical_recovery_cleanup_preserves_same_bytes_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    ledger, item, expected_sha256, marker_bytes = _noncanonical_replay_fixture(
        tmp_path, f"pr10_replaced_candidate_{operation}_owner"
    )
    history = item / f"agent-runs.history.{expected_sha256}.jsonl"
    original = history.read_bytes()
    canonical = item / "agent-runs.jsonl"
    canonical.write_bytes(original if operation == "apply" else marker_bytes)
    candidate = item / "agent-runs.jsonl.tmp"
    original_write = ledger._write_exact_staging_file
    replacement_identity = {}

    def replace_after_write(path: Path, expected: bytes):
        owned = original_write(path, expected)
        if path == candidate:
            replacement = path.with_suffix(".replacement")
            replacement.write_bytes(expected)
            metadata = replacement.stat()
            replacement_identity["value"] = (metadata.st_dev, metadata.st_ino)
            os.replace(replacement, path)
        return owned

    monkeypatch.setattr(ledger, "_write_exact_staging_file", replace_after_write)
    monkeypatch.setattr(ledger, "_validate_noncanonical_marker_candidate", lambda *_: None)
    command = (
        ledger._command_apply_noncanonical_history
        if operation == "apply"
        else ledger._command_rollback_noncanonical_history
    )

    completed, _history = command(
        item, expected_sha256, "linked-ledger-replay",
        "2026-09-10T12:00:00Z", ledger.load_validator(), "pre-ledger-replace",
    )

    assert completed is False
    assert candidate.exists()
    metadata = candidate.stat()
    assert (metadata.st_dev, metadata.st_ino) == replacement_identity["value"]


def test_noncanonical_replay_rejects_symlinked_canonical_ledger(tmp_path: Path) -> None:
    ledger, item, expected_sha256, marker_bytes = _noncanonical_replay_fixture(
        tmp_path, "pr10_noncanonical_replay_symlink_owner"
    )
    external = tmp_path / "external-canonical-ledger"
    external.write_bytes(marker_bytes)
    canonical = item / "agent-runs.jsonl"
    try:
        canonical.symlink_to(external)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")

    with pytest.raises(ledger.LedgerNoncanonicalRecoveryError):
        ledger._noncanonical_recovery_state(
            item,
            expected_sha256,
            "linked-ledger-replay",
            "2026-09-10T12:00:00Z",
            ledger.load_validator(),
        )

    assert canonical.is_symlink()
    assert external.read_bytes() == marker_bytes


def test_noncanonical_replay_rejects_hardlinked_canonical_ledger(tmp_path: Path) -> None:
    ledger, item, expected_sha256, marker_bytes = _noncanonical_replay_fixture(
        tmp_path, "pr10_noncanonical_replay_hardlink_owner"
    )
    external = tmp_path / "external-canonical-ledger-hardlink"
    external.write_bytes(marker_bytes)
    canonical = item / "agent-runs.jsonl"
    try:
        os.link(external, canonical)
    except OSError as exc:
        pytest.skip(f"hardlink unavailable: {exc}")

    with pytest.raises(ledger.LedgerNoncanonicalRecoveryError):
        ledger._noncanonical_recovery_state(
            item,
            expected_sha256,
            "linked-ledger-replay",
            "2026-09-10T12:00:00Z",
            ledger.load_validator(),
        )

    assert canonical.exists()
    assert external.read_bytes() == marker_bytes


def test_transition_intent_inventory_counts_every_directory_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lifecycle = load_module(MUTATE, "pr10_transition_inventory_entries")
    root = tmp_path / "repo"
    transition_root = root / ".scratch" / "work-items-lifecycle-transitions"
    transition_root.mkdir(parents=True)
    (transition_root / "one.txt").write_text("x", encoding="utf-8")
    (transition_root / "two.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(
        lifecycle, "TRANSITION_INTENT_INVENTORY_MAX_ENTRIES", 1
    )

    with pytest.raises(lifecycle.LifecycleError) as caught:
        list(lifecycle._iter_transition_intents(root))

    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"


def test_transition_intent_inventory_refuses_before_recovery_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lifecycle = load_module(MUTATE, "pr10_transition_inventory_decode")
    root = tmp_path / "repo"
    transition_root = root / ".scratch" / "work-items-lifecycle-transitions"
    transition_root.mkdir(parents=True)
    (transition_root / "one.json").write_text("{}\n", encoding="utf-8")
    (transition_root / "two.json").write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        lifecycle, "TRANSITION_INTENT_INVENTORY_MAX_ENTRIES", 1
    )
    monkeypatch.setattr(
        lifecycle,
        "_recover_transition",
        lambda *_args, **_kwargs: pytest.fail(
            "over-limit inventory reached transition decode"
        ),
    )

    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle._recover_all_transitions(root)

    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"


def test_transition_intent_loader_rejects_symlink_before_json_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lifecycle = load_module(MUTATE, "pr10_transition_intent_nofollow")
    root = tmp_path / "repo"
    outside = tmp_path / "outside-intent.json"
    outside.write_text("{}\n", encoding="utf-8")
    link = root / ".scratch" / "work-items-lifecycle-transitions" / "linked.json"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(outside)
    except OSError as exc:
        pytest.skip(f"symlink unavailable: {exc}")
    monkeypatch.setattr(
        lifecycle.json,
        "loads",
        lambda *_args, **_kwargs: pytest.fail(
            "linked transition intent reached JSON decode"
        ),
    )

    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle._load_transition_intent(root, link)

    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"


def test_transition_intent_loader_rejects_hardlink_before_json_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lifecycle = load_module(MUTATE, "pr10_transition_intent_hardlink")
    root = tmp_path / "repo"
    external = tmp_path / "outside-intent.json"
    external.write_text("{}\n", encoding="utf-8")
    intent = root / ".scratch" / "work-items-lifecycle-transitions" / "linked.json"
    intent.parent.mkdir(parents=True)
    try:
        os.link(external, intent)
    except OSError as exc:
        pytest.skip(f"hardlink unavailable: {exc}")
    monkeypatch.setattr(
        lifecycle.json,
        "loads",
        lambda *_args, **_kwargs: pytest.fail(
            "hardlinked transition intent reached JSON decode"
        ),
    )

    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle._load_transition_intent(root, intent)

    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"


def test_ledger_location_proof_rejects_hardlink_before_json_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lifecycle = load_module(MUTATE, "pr10_ledger_proof_hardlink")
    external = tmp_path / "outside-proof.json"
    external.write_text("{}\n", encoding="utf-8")
    proof = tmp_path / "proof.json"
    try:
        os.link(external, proof)
    except OSError as exc:
        pytest.skip(f"hardlink unavailable: {exc}")
    monkeypatch.setattr(
        lifecycle.json,
        "loads",
        lambda *_args, **_kwargs: pytest.fail(
            "hardlinked ledger proof reached JSON decode"
        ),
    )

    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle._ledger_location_proof_object(
            proof,
            failure_id="WI-LIFECYCLE-TRANSITION-INTENT-INVALID",
            unreadable="transition intent is unreadable",
        )

    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-INTENT-INVALID"


def test_captured_snapshot_rejects_same_size_rewrite_with_restored_mtime(
    tmp_path: Path,
) -> None:
    lifecycle = load_module(MUTATE, "pr10_snapshot_content_drift")
    target = tmp_path / "snapshot.bin"
    target.write_bytes(b"same-size")
    snapshot = lifecycle._capture_file_snapshot(
        target, failure_id="WI-SNAPSHOT-DRIFT"
    )
    metadata = target.stat()
    target.write_bytes(b"new-bytes")
    os.utime(target, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))

    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle._verify_captured_file(snapshot, "WI-SNAPSHOT-DRIFT")

    assert caught.value.failure_id == "WI-SNAPSHOT-DRIFT"


def test_single_link_requirement_is_scoped_to_authority_files(tmp_path: Path) -> None:
    lifecycle = load_module(MUTATE, "pr10_snapshot_link_scope")
    external = tmp_path / "external.bin"
    external.write_bytes(b"ordinary")
    linked = tmp_path / "linked.bin"
    try:
        os.link(external, linked)
    except OSError as exc:
        pytest.skip(f"hardlink unavailable: {exc}")

    snapshot = lifecycle._capture_file_snapshot(
        linked, failure_id="WI-SNAPSHOT-GENERIC"
    )
    assert snapshot.data == b"ordinary"
    with pytest.raises(lifecycle.LifecycleError):
        lifecycle._capture_file_snapshot(
            linked,
            failure_id="WI-SNAPSHOT-AUTHORITY",
            require_single_link=True,
        )


@pytest.mark.parametrize("size", (0, 1, 65536, 131089))
def test_lifecycle_artifact_digest_uses_fixed_size_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, size: int
) -> None:
    lifecycle = load_module(MUTATE, "pr10_artifact_streaming")
    artifact = tmp_path / "status.md"
    data = (b"bounded-artifact\n" * (size // 16 + 1))[:size]
    artifact.write_bytes(data)
    original_fdopen = os.fdopen
    requested_sizes: list[int] = []
    monkeypatch.setattr(lifecycle, "LEDGER_LOCATION_PROOF_BYTE_CAP", size)

    class TrackingReader:
        def __init__(self, *args, **kwargs):
            self.stream = original_fdopen(*args, **kwargs)

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def read(self, size=-1):
            requested_sizes.append(size)
            assert 0 < size <= 65536, "digest read must be bounded to 64 KiB"
            return self.stream.read(size)

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

    monkeypatch.setattr(os, "fdopen", TrackingReader)
    monkeypatch.setattr(
        Path, "read_bytes",
        lambda _path: pytest.fail("digest materialized a whole artifact"),
    )
    assert lifecycle._ledger_location_regular_sha256(
        artifact, failure_id="WI-TEST-ARTIFACT"
    ) == hashlib.sha256(data).hexdigest()
    assert requested_sizes


def test_lifecycle_artifact_digest_rejects_oversize_before_open(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lifecycle = load_module(MUTATE, "pr10_artifact_limit")
    artifact = tmp_path / "closure.md"
    artifact.write_bytes(b"over-limit")
    monkeypatch.setattr(lifecycle, "LEDGER_LOCATION_PROOF_BYTE_CAP", 4)
    monkeypatch.setattr(
        lifecycle, "_open_readonly_nofollow",
        lambda *_: pytest.fail("oversized artifact was opened"),
    )
    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle._ledger_location_regular_sha256(
            artifact, failure_id="WI-TEST-ARTIFACT"
        )
    assert caught.value.failure_id == "WI-TEST-ARTIFACT"


def test_lifecycle_artifact_digest_rejects_same_size_path_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lifecycle = load_module(MUTATE, "pr10_artifact_identity")
    artifact = tmp_path / "status.md"
    replacement = tmp_path / "replacement.md"
    artifact.write_bytes(b"original")
    replacement.write_bytes(b"replaced")
    original_lstat = Path.lstat
    replaced = False

    def swap_after_inspection(path, *args, **kwargs):
        nonlocal replaced
        info = original_lstat(path, *args, **kwargs)
        if path == artifact and not replaced:
            replaced = True
            os.replace(replacement, artifact)
        return info

    original_reject = lifecycle._lifecycle_reject_unreduced_reparse

    def checked_path(*args, **kwargs):
        original_reject(*args, **kwargs)
        monkeypatch.setattr(Path, "lstat", swap_after_inspection)

    monkeypatch.setattr(lifecycle, "_lifecycle_reject_unreduced_reparse", checked_path)
    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle._ledger_location_regular_sha256(
            artifact, failure_id="WI-TEST-ARTIFACT"
        )
    assert caught.value.failure_id == "WI-TEST-ARTIFACT"
    assert replaced
    assert artifact.read_bytes() == b"replaced"


@pytest.mark.parametrize("tamper", ("duplicate-key", "oversize", "hardlink", "deep-json", "huge-integer"))
def test_settlement_receipt_uses_bounded_unique_owned_proof(
    tmp_path: Path, tamper: str
) -> None:
    fixtures = load_module(LEGACY_TRANSFER_TESTS, f"pr10_settlement_proof_{tamper}")
    fixture = fixtures.transition_fixture(tmp_path)
    fixtures.run_transition(fixture)
    lifecycle = fixture["lifecycle"]
    receipt = (
        tmp_path / "work-items" / "archive" / "2026-08"
        / fixture["slug"] / "lifecycle-transition-receipt.json"
    )
    original = receipt.read_bytes()
    if tamper == "duplicate-key":
        receipt.write_bytes(b'{"status":"unsettled",' + original.lstrip()[1:])
    elif tamper == "deep-json":
        nested = b"[" * (sys.getrecursionlimit() + 100) + b"0" + b"]" * (sys.getrecursionlimit() + 100)
        receipt.write_bytes(b'{"unused":' + nested + b"," + original.lstrip()[1:])
    elif tamper == "huge-integer":
        receipt.write_bytes(b'{"unused":' + b"1" * 10000 + b"," + original.lstrip()[1:])
    elif tamper == "oversize":
        receipt.write_bytes(original + b" " * lifecycle.LEDGER_LOCATION_PROOF_BYTE_CAP)
    else:
        try:
            os.link(receipt, tmp_path / "foreign-receipt.json")
        except OSError as exc:
            pytest.skip(f"hardlink unavailable: {exc}")
    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle._verify_settlement(tmp_path, receipt)
    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH"


@pytest.mark.parametrize("operation", ("capture", "verify"))
def test_snapshot_fdopen_failure_closes_owned_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    lifecycle = load_module(MUTATE, f"pr10_snapshot_fdopen_{operation}")
    artifact = tmp_path / "receipt.json"
    artifact.write_bytes(b"{}")
    snapshot = lifecycle._capture_file_snapshot(artifact, failure_id="WI-TEST-SNAPSHOT")
    original_open = lifecycle._open_readonly_nofollow
    descriptors: list[int] = []

    def tracked_open(path):
        descriptor = original_open(path)
        descriptors.append(descriptor)
        return descriptor

    def fail_fdopen(*args, **kwargs):
        raise OSError("injected stream construction failure")

    monkeypatch.setattr(lifecycle, "_open_readonly_nofollow", tracked_open)
    monkeypatch.setattr(os, "fdopen", fail_fdopen)
    closed: list[bool] = []
    try:
        with pytest.raises(lifecycle.LifecycleError) as caught:
            if operation == "capture":
                lifecycle._capture_file_snapshot(artifact, failure_id="WI-TEST-SNAPSHOT")
            else:
                lifecycle._verify_captured_file(snapshot, "WI-TEST-SNAPSHOT")
        assert caught.value.failure_id == "WI-TEST-SNAPSHOT"
    finally:
        for descriptor in descriptors:
            try:
                os.fstat(descriptor)
            except OSError:
                closed.append(True)
            else:
                os.close(descriptor)  # Keep even the failing regression leak-free.
                closed.append(False)
    assert closed == [True], "snapshot leaked the descriptor before stream ownership"


@pytest.mark.parametrize("fault", ("fdopen", "read", "growth", "rewrite", "replace", "parent"))
def test_lifecycle_artifact_digest_failure_is_typed_and_closes_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str
) -> None:
    lifecycle = load_module(MUTATE, f"pr10_digest_failure_{fault}")
    artifact = tmp_path / "owned" / "status.md"
    artifact.parent.mkdir()
    artifact.write_bytes(b"original")
    metadata = artifact.stat()
    original_fdopen = os.fdopen
    descriptors: list[int] = []
    injected = False
    mutation_completed = False

    class FaultReader:
        def __init__(self, descriptor, *args, **kwargs):
            descriptors.append(descriptor)
            if fault == "fdopen":
                raise OSError("injected stream construction failure")
            self.stream = original_fdopen(descriptor, *args, **kwargs)

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __getattr__(self, name):
            return getattr(self.stream, name)

        def read(self, size):
            nonlocal injected, mutation_completed
            if fault == "read":
                raise OSError("injected read failure")
            data = self.stream.read(size)
            if not injected and fault in {"growth", "rewrite"}:
                injected = True
                if fault == "growth":
                    with artifact.open("ab") as writer:
                        writer.write(b"!")
                elif fault == "rewrite":
                    artifact.write_bytes(b"rewritte")
                    os.utime(artifact, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))
                mutation_completed = True
            return data

        def __exit__(self, *args):
            nonlocal injected, mutation_completed
            result = self.stream.__exit__(*args)
            # Exercise revalidation after close: some Windows filesystems refuse
            # replacement while the descriptor is open, before our guard can run.
            if fault in {"replace", "parent"}:
                injected = True
                if fault == "replace":
                    replacement = artifact.with_name("replacement.md")
                    replacement.write_bytes(b"original")
                    os.replace(replacement, artifact)
                else:
                    moved = tmp_path / "moved"
                    artifact.parent.rename(moved)
                    artifact.parent.mkdir()
                    os.replace(moved / artifact.name, artifact)
                mutation_completed = True
            return result

    monkeypatch.setattr(os, "fdopen", FaultReader)
    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle._ledger_location_regular_sha256(
            artifact, failure_id="WI-TEST-ARTIFACT", maximum_bytes=8
        )
    assert caught.value.failure_id == "WI-TEST-ARTIFACT"
    assert len(descriptors) == 1
    with pytest.raises(OSError):
        os.fstat(descriptors[0])
    if fault not in {"fdopen", "read"}:
        assert injected and mutation_completed


def test_settlement_ledger_digest_uses_validator_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fixtures = load_module(LEGACY_TRANSFER_TESTS, "pr10_settlement_ledger_limit")
    fixture = fixtures.transition_fixture(tmp_path)
    payload = fixtures.run_transition(fixture)
    lifecycle = fixture["lifecycle"]
    archive = tmp_path / payload["archivePath"]
    ledger = archive / "agent-runs.jsonl"
    cap = 32 * 1024
    data = ledger.read_bytes() + b"\n" * cap
    ledger.write_bytes(data)
    payload["ledgerSha256"] = hashlib.sha256(data).hexdigest()
    receipt = archive / "lifecycle-transition-receipt.json"
    receipt.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(lifecycle, "LEDGER_LOCATION_PROOF_BYTE_CAP", cap)
    assert lifecycle._verify_settlement(tmp_path, receipt) == payload
    validator = lifecycle._validator_module()
    monkeypatch.setattr(validator, "MAX_TRANSFER_LEDGER_BYTES", cap)
    monkeypatch.setattr(lifecycle, "_validator_module", lambda: validator)
    with pytest.raises(lifecycle.LifecycleError) as caught:
        lifecycle._verify_settlement(tmp_path, receipt)
    assert caught.value.failure_id == "WI-LIFECYCLE-TRANSITION-SETTLEMENT-MISMATCH"


@pytest.mark.skipif(os.name != "posix" or not hasattr(os, "mkfifo"), reason="requires POSIX named pipes")
def test_lifecycle_artifact_digest_refuses_fifo_replacement(tmp_path: Path) -> None:
    # Isolate the potentially blocking open so a regression cannot hang the suite.
    program = """
import importlib.util
import os
import sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("fifo_digest_owner", sys.argv[1])
lifecycle = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = lifecycle
spec.loader.exec_module(lifecycle)
artifact = Path(sys.argv[2])
artifact.write_bytes(b"regular")
original_open = lifecycle._open_readonly_nofollow

def replace_before_open(path):
    path.unlink()
    os.mkfifo(path)
    return original_open(path)

lifecycle._open_readonly_nofollow = replace_before_open
try:
    lifecycle._ledger_location_regular_sha256(artifact, failure_id="WI-TEST-ARTIFACT")
except lifecycle.LifecycleError as exc:
    assert exc.failure_id == "WI-TEST-ARTIFACT"
    print("FIFO-REFUSED")
else:
    raise AssertionError("digest accepted a substituted named pipe")
"""
    result = subprocess.run(
        [sys.executable, "-c", program, str(MUTATE), str(tmp_path / "status.md")],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "FIFO-REFUSED"

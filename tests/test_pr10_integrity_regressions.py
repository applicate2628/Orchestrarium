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

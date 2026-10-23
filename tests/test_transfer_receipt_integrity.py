from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
VALIDATOR = ROOT / "scripts" / "validate-work-item-state.py"


def _validator_module():
    spec = importlib.util.spec_from_file_location("validate_transfer_integrity_under_test", VALIDATOR)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _write_receipt(archive: Path, *, archive_path: str) -> bytes:
    ledger = archive / "agent-runs.jsonl"
    ledger_bytes = b'{}\n'
    ledger.write_bytes(ledger_bytes)
    ledger_sha = hashlib.sha256(ledger_bytes).hexdigest()
    payload = {
        "schemaVersion": 2,
        "owner": "mutate-work-item:archive-with-successor-v2",
        "operationId": "op-transfer-1",
        "workItem": "source",
        "requestSuccessorSlug": "successor",
        "archivePath": archive_path,
        "ledgerSha256": ledger_sha,
        "archiveIdentity": hashlib.sha256(
            b"orchestrarium-archive-v1\0"
            + archive_path.encode("utf-8")
            + b"\0"
            + ledger_sha.encode("ascii")
        ).hexdigest(),
        "obligations": [],
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    (archive / "lifecycle-transition-receipt.json").write_bytes(raw)
    return raw


def test_transfer_receipt_rejects_symlink_authority(tmp_path: Path) -> None:
    validator = _validator_module()
    root = tmp_path / "repo"
    archive = root / "work-items" / "archive" / "2026-09" / "source"
    archive.mkdir(parents=True)
    raw = _write_receipt(
        archive,
        archive_path="work-items/archive/2026-09/source",
    )
    receipt = archive / "lifecycle-transition-receipt.json"
    external = tmp_path / "external-receipt.json"
    external.write_bytes(raw)
    receipt.unlink()
    try:
        receipt.symlink_to(external)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks unavailable on this filesystem")

    errors: list[str] = []
    assert validator._transfer_receipts(root, errors) == {}
    assert errors


def test_transfer_receipt_archive_path_must_match_physical_parent(tmp_path: Path) -> None:
    validator = _validator_module()
    root = tmp_path / "repo"
    archive = root / "work-items" / "archive" / "2026-09" / "source"
    archive.mkdir(parents=True)
    forged = "work-items/archive/2026-09/source/../../../../outside"
    _write_receipt(archive, archive_path=forged)
    outside = root / "outside"
    outside.mkdir()
    (outside / "agent-runs.jsonl").write_bytes(
        (archive / "agent-runs.jsonl").read_bytes()
    )

    errors: list[str] = []
    assert validator._transfer_receipts(root, errors) == {}
    assert errors

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "scripts" / "mutate-work-item.py"


def _owner_module():
    spec = importlib.util.spec_from_file_location("mutate_work_item_h1_under_test", OWNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_h1_artifact_set_digest_binds_directory_snapshot_fields() -> None:
    owner = _owner_module()
    first = (
        {
            "logicalPath": "work-items/ledger-migration-receipts",
            "kind": "directory",
            "byteLength": 11,
            "sha256": "1" * 64,
        },
    )
    second = (
        {
            "logicalPath": "work-items/ledger-migration-receipts",
            "kind": "directory",
            "byteLength": 12,
            "sha256": "2" * 64,
        },
    )

    assert owner._ledger_h1_artifact_set_digest(first) != owner._ledger_h1_artifact_set_digest(second)


def test_h1_directory_snapshot_rejects_external_hardlink(tmp_path: Path) -> None:
    owner = _owner_module()
    directory = tmp_path / "artifact-dir"
    directory.mkdir()
    member = directory / "receipt.json"
    member.write_text("{}\n", encoding="utf-8")
    external = tmp_path / "external.json"
    try:
        os.link(member, external)
    except (OSError, NotImplementedError):
        pytest.skip("hard links unavailable on this filesystem")

    with pytest.raises(owner.LifecycleError):
        owner._ledger_h1_directory_snapshot(directory)


def test_h1_receipt_reader_rejects_external_hardlink(tmp_path: Path) -> None:
    owner = _owner_module()
    receipt = tmp_path / "relocation-receipt.json"
    receipt.write_text(json.dumps({"schemaVersion": 1}), encoding="utf-8")
    external = tmp_path / "external-receipt.json"
    try:
        os.link(receipt, external)
    except (OSError, NotImplementedError):
        pytest.skip("hard links unavailable on this filesystem")

    with pytest.raises(owner.LifecycleError):
        owner._ledger_h1_receipt_object(receipt)

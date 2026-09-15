from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
OWNER = ROOT / "scripts" / "mutate-work-item.py"
RELOCATION_FIXTURES = ROOT / "tests" / "test_h1_artifact_set_relocation.py"


def _owner_module():
    spec = importlib.util.spec_from_file_location("mutate_work_item_h1_under_test", OWNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _relocation_fixture_module(name: str):
    spec = importlib.util.spec_from_file_location(name, RELOCATION_FIXTURES)
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


def test_h1_directory_member_hardlink_relocates_and_alias_drift_is_rejected(
    tmp_path: Path,
) -> None:
    fixtures = _relocation_fixture_module("h1_hardlink_member_fixture")
    root = tmp_path / "hardlinked-member"
    _support, owner, _reader, request, _items, _paths = (
        fixtures.activated_relocation_fixture(root)
    )
    source_directory = root / "work-items" / "legacy-ledger-projection-manifests"
    members = list(source_directory.glob("*.json"))
    assert len(members) == 1
    source = members[0]
    before = source.read_bytes()
    assert before
    external = tmp_path / "external-manifest.json"
    try:
        os.link(source, external)
    except (OSError, NotImplementedError):
        pytest.skip("hard links unavailable on this filesystem")

    result = owner.relocate_ledger_h1_artifact_set(root, request, apply=True)
    target = (
        root
        / "work-items"
        / "archive"
        / "2026-09"
        / "h1-owner"
        / "ledger-h1-compatibility"
        / source_directory.name
        / source.name
    )

    assert result["status"] == "settled"
    assert not source.exists()
    assert target.read_bytes() == before
    assert os.path.samefile(target, external)

    external.write_bytes(bytes([before[0] ^ 1]) + before[1:])
    with pytest.raises(owner.LifecycleError) as rejected:
        owner.resolve_ledger_h1_artifact_set_location(root)
    assert rejected.value.failure_id == "WI-LEDGER-COMPAT-SET-TOPOLOGY"


def test_h1_hardlinked_settled_receipt_is_readable_and_replay_preserves_bytes(
    tmp_path: Path,
) -> None:
    fixtures = _relocation_fixture_module("h1_hardlink_receipt_fixture")
    root = tmp_path / "hardlinked-receipt"
    _support, owner, _reader, request, _items, _paths = (
        fixtures.activated_relocation_fixture(root)
    )
    owner.relocate_ledger_h1_artifact_set(root, request, apply=True)
    receipt = (
        root
        / "work-items"
        / "archive"
        / "2026-09"
        / "h1-owner"
        / "ledger-h1-compatibility"
        / "relocation-receipt.json"
    )
    original = receipt.read_bytes()
    external = tmp_path / "external-receipt.json"
    try:
        os.link(receipt, external)
    except (OSError, NotImplementedError):
        pytest.skip("hard links unavailable on this filesystem")

    parsed, raw = owner._ledger_h1_receipt_object(receipt)
    replay = owner.relocate_ledger_h1_artifact_set(root, request, apply=True)

    assert raw == original
    assert parsed["operationId"] == request.operation_id
    assert replay["replay"] is True
    assert receipt.read_bytes() == original
    assert external.read_bytes() == original

from __future__ import annotations

import hashlib
import importlib.util
import os
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "scripts" / "agent-run-ledger.py"


def _ledger_module(name: str):
    spec = importlib.util.spec_from_file_location(name, LEDGER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _existing_history(tmp_path: Path, name: str):
    ledger = _ledger_module(name)
    item = tmp_path / "item"
    item.mkdir()
    original = b'{"historical":"opaque"}\n'
    digest = hashlib.sha256(original).hexdigest()
    history = item / f"agent-runs.history.{digest}.jsonl"
    history.write_bytes(original)
    staging = item / f".{history.name}.tmp"
    return ledger, item, history, staging, digest, original


def test_existing_history_replay_preserves_foreign_regular_staging(tmp_path: Path) -> None:
    ledger, item, history, staging, digest, original = _existing_history(
        tmp_path, "replay_foreign_staging_owner"
    )
    foreign = b"foreign staging entry\n"
    staging.write_bytes(foreign)

    with pytest.raises(ledger.LedgerNoncanonicalRecoveryError):
        ledger._publish_noncanonical_history_blob(item, history, digest, original)

    assert history.read_bytes() == original
    assert staging.read_bytes() == foreign


def test_existing_history_replay_cleans_same_inode_reserved_link(tmp_path: Path) -> None:
    ledger, item, history, staging, digest, original = _existing_history(
        tmp_path, "replay_owned_staging_owner"
    )
    try:
        os.link(history, staging)
    except OSError as exc:
        pytest.skip(f"hardlink unavailable: {exc}")
    before = history.stat()
    assert before.st_nlink == 2
    assert staging.stat().st_ino == before.st_ino

    ledger._publish_noncanonical_history_blob(item, history, digest, original)

    assert history.read_bytes() == original
    assert history.stat().st_nlink == 1
    assert not staging.exists()
    assert not list(item.glob(f".{staging.name}.cleanup-*"))

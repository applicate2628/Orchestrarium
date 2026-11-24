from __future__ import annotations

import json
from pathlib import Path

import pytest

from _module_loading_support import load_module


ROOT = Path(__file__).resolve().parents[1]
RELEASE_FIXTURE = ROOT / "tests" / "test_retained_scratch_release.py"


def empty_namespace_fixture(tmp_path: Path, state: str):
    helpers = load_module(RELEASE_FIXTURE, f"empty_scratch_fixture_{id(tmp_path)}")
    fixture = helpers.prior_disposal_fixture(tmp_path)
    _scratch_helpers, _mutator, _root, _item, scratch, *_rest = fixture
    owner = scratch.parent.parent
    if state == "owner-absent":
        owner.rename(tmp_path / "original-empty-owner")
    elif state == "parent-absent":
        owner.parent.rename(tmp_path / "original-empty-owners")
    else:
        assert state == "empty-run" and scratch.parent.is_dir()
    return fixture


@pytest.mark.parametrize("state", ["empty-run", "owner-absent", "parent-absent"])
@pytest.mark.parametrize("phase", ["before-write", "last-settlement", "transaction-exit"])
def test_empty_selected_scratch_namespace_remains_current_through_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str, phase: str,
) -> None:
    helpers, mutator, root, item, scratch, *_rest = empty_namespace_fixture(tmp_path, state)
    before = {path.relative_to(item): path.read_bytes() for path in item.rglob("*") if path.is_file()}
    readme = root / "work-items/README.md"
    readme_before = readme.read_bytes()
    instant = "2026-08-09T01:00:00Z"
    archived = root / "work-items/archive/2026-08" / item.name
    injected = []
    seam = {"before-write": "_prepare_bug_dispositions", "last-settlement": "_verify_settlement",
            "transaction-exit": "_settle_scratch_dispositions"}[phase]
    original = getattr(mutator, seam)

    def create_foreign_after(*args, **kwargs):
        result = original(*args, **kwargs)
        if not injected:
            scratch.parent.mkdir(parents=True, exist_ok=True)
            with scratch.open("xb") as stream:
                stream.write(b"foreign resource created after the empty selection")
            injected.append(mutator._lifecycle_file_identity(scratch.lstat()))
        return result

    monkeypatch.setattr(mutator, seam, create_foreign_after)
    observer = mutator.LifecycleDiagnosticObserver()
    with pytest.raises(mutator.LifecycleError) as caught:
        mutator.close_item(root, item.name, helpers.closure(instant), instant, diagnostic_observer=observer)
    assert len(injected) == 1
    expected = "WI-BUG-DISPOSITIONS-ROLLBACK" if phase == "last-settlement" else "WI-CATEGORY-MIGRATION-INVENTORY"
    assert caught.value.failure_id == expected, str(caught.value)
    assert scratch.read_bytes() == b"foreign resource created after the empty selection"
    assert mutator._lifecycle_file_identity(scratch.lstat()) == injected[0]
    if phase == "transaction-exit":
        # The final observer refuses success after the body has returned. It
        # preserves the completed archive and the newly observed foreign leaf.
        assert not item.exists() and archived.is_dir()
        assert (archived / "agent-runs.jsonl").read_bytes() == before[Path("agent-runs.jsonl")]
        assert any(row.phase == "transaction-verification" and row.failureId == "WI-CATEGORY-MIGRATION-INVENTORY"
                   for row in observer.snapshot.cleanupFailures)
    else:
        assert observer.snapshot.primaryFailureId == "WI-CATEGORY-MIGRATION-INVENTORY"
        assert item.is_dir() and not archived.exists()
        assert {path.relative_to(item): path.read_bytes() for path in item.rglob("*") if path.is_file()} == before
        assert readme.read_bytes() == readme_before
        if phase == "last-settlement":
            # The independent inverse restores item/README, while the existing
            # creator cleanup refuses new deletion after a retained violation.
            assert observer.snapshot.rollback == "incomplete"
            assert archived.parent.is_dir() and not tuple(archived.parent.iterdir())
            assert "remove created directory" in str(caught.value)


@pytest.mark.parametrize("state", ["empty-run", "owner-absent", "parent-absent"])
def test_empty_scratch_selection_does_not_admit_history_or_another_owner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, state: str,
) -> None:
    helpers, mutator, root, item, scratch, *_rest = empty_namespace_fixture(tmp_path, state)
    ledger = (item / "agent-runs.jsonl").read_bytes()
    sibling = scratch.parent.parent.parent / "unrelated-owner" / "unrelated-run" / "foreign.bin"
    prepare = mutator._prepare_bug_dispositions
    calls = []

    def prepare_with_sibling(*args, **kwargs):
        result = prepare(*args, **kwargs)
        sibling.parent.mkdir(parents=True)
        sibling.write_bytes(b"unselected foreign resource")
        calls.append(mutator._lifecycle_file_identity(sibling.lstat()))
        return result

    def historical_selection(*args, **kwargs):
        pytest.fail("ordinary empty physical selection must not acquire historical scratch rows")

    monkeypatch.setattr(mutator, "_prepare_bug_dispositions", prepare_with_sibling)
    monkeypatch.setattr(mutator, "_scratch_ledger_entries", historical_selection)
    instant = "2026-08-09T01:00:00Z"
    archived = mutator.close_item(root, item.name, helpers.closure(instant), instant)
    assert calls and (archived / "agent-runs.jsonl").read_bytes() == ledger
    assert json.loads((archived / mutator.BUG_DISPOSITIONS_RECEIPT).read_bytes())["scratchSelection"] == []
    assert not scratch.exists() and sibling.read_bytes() == b"unselected foreign resource"
    assert mutator._lifecycle_file_identity(sibling.lstat()) == calls[0]
    assert mutator.close_item(root, item.name, helpers.closure(instant), instant) == archived

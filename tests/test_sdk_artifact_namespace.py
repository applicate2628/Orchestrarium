"""Reject reserved ledger outputs before any coordinator or worker effect."""
from pathlib import Path

import pytest

from test_sdk_coordinator import composed_harness
from sdk_execution import coordinator, receiving


@pytest.mark.parametrize("artifact", [
    "agent-runs.jsonl", "agent-runs.jsonl.lock",
    "./agent-runs.jsonl", "./agent-runs.jsonl.lock",
])
def test_coordinator_refuses_reserved_artifact_before_effects(tmp_path, monkeypatch, artifact):
    h = composed_harness(monkeypatch, tmp_path)
    try:
        with pytest.raises(ValueError, match="artifact.*ledger"):
            coordinator.create_review_coordinator(**{**h.options, "artifact": artifact})
        assert h.sdk.model_calls == h.process_calls == 0
        item = Path(h.selection.work_item)
        assert not (item / "agent-runs.jsonl").exists()
        assert not (item / "agent-runs.jsonl.lock").exists()
    finally:
        h.owner.__exit__(None, None, None)


@pytest.mark.parametrize("name", ["agent-runs.jsonl", "agent-runs.jsonl.lock"])
def test_shared_artifact_preflight_preserves_existing_ledger_files(tmp_path, name):
    target = tmp_path / name
    content = b"existing ledger owner bytes\n"
    target.write_bytes(content)
    before = target.stat()
    with pytest.raises(ValueError, match="artifact.*ledger"):
        receiving.review_artifact_target(tmp_path, name)
    assert target.stat() == before
    assert target.read_bytes() == content


def test_nested_artifact_with_ledger_basename_is_not_reserved(tmp_path):
    (tmp_path / "reviews").mkdir()
    assert receiving.review_artifact_target(
        tmp_path, "reviews/agent-runs.jsonl", must_be_new=True
    ) == tmp_path / "reviews/agent-runs.jsonl"

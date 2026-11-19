"""Registry claims use canonical Root receipts, never prepared memory as permission."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import pytest

from test_sdk_root_registry import registry_fixture, admit
from sdk_execution import runtime
from test_sdk_child_admission_claims import decisions
from test_sdk_child_lead_authority import INSTANT


def restarted(values):
    registry, owner, assignment, requests, selections, root, proposal, candidate = values
    fresh = runtime.RootTaskRegistry(root_authority=registry._root_authority,
                                     root_selection=root, source_environment={})
    child = runtime.ChildLeadAuthority(
        root_authority=fresh, root_selection=root, child_id=assignment.child_id,
        selections=selections, closure_data=owner._closure_data,
        terminal_instant=INSTANT, repository_root=owner._repository_root)
    return fresh, child


@pytest.mark.parametrize("after_commit", [False, True])
def test_registration_commit_failure_never_turns_prepared_memory_into_permission(
        tmp_path, monkeypatch, after_commit):
    values = registry_fixture(tmp_path, monkeypatch)
    registry, owner, assignment, requests, selections, root, proposal, candidate = values
    writer = runtime._ledger(root)[0]
    original = writer._append_event_transaction
    captured = {}

    def interrupted(item, *args, **kwargs):
        if Path(item) != Path(root.work_item):
            return original(item, *args, **kwargs)
        key, entry = next(iter(registry._prepared.items()))
        captured.update(key=key, request=entry[2])
        # A request can be resolved for admission while publication is active,
        # but it still cannot launch before the canonical receipt exists.
        with pytest.raises(ValueError, match="not_received"):
            runtime.claim_launch(entry[2], entry[3],
                                 authority=registry.assert_current, started_at=INSTANT)
        if after_commit:
            original(item, *args, **kwargs)
        raise RuntimeError("injected registration acknowledgement loss")

    with patch.object(writer, "_append_event_transaction", new=interrupted):
        if after_commit:
            outcome = admit(values)
            assert outcome["status"] == "accepted"
        else:
            with pytest.raises(RuntimeError, match="acknowledgement"):
                admit(values)
    key = captured["key"]
    artifact = Path(root.work_item) / "registered.json"
    original_bytes = artifact.read_bytes()
    assert len(decisions(root)) == int(after_commit)
    fresh, child = restarted(values)
    restored = fresh.restore(child)
    if not after_commit:
        assert restored["selections"] == {}
        with pytest.raises(ValueError, match="not_received"):
            registry.resolve(key)
        assert child.proposal_results(assignment)[proposal["proposal_id"]]["status"] == "pending"
    result = fresh.admit(authority=child, proposal_id=proposal["proposal_id"],
                         request=candidate, selection=selections["task-one"],
                         artifact="registered.json", started_at=INSTANT)
    assert result["request_id"] == key
    assert len(decisions(root)) == 1
    assert artifact.read_bytes() == original_bytes
    assert fresh.resolve(key) == captured["request"]


def test_concurrent_changed_root_decisions_preserve_exact_winner(tmp_path, monkeypatch):
    values = registry_fixture(tmp_path, monkeypatch)
    registry, owner, assignment, requests, selections, root, proposal, candidate = values
    other_registry, other_child = restarted(values)
    candidates = [candidate, runtime.prepare_codex_request(
        replace(candidate, prompt="A distinct explicitly selected Root task."))]
    actors = [(registry, owner), (other_registry, other_child)]
    barrier = Barrier(2)
    lifecycle_error = runtime._ledger(root)[1].load_lifecycle_owner().LifecycleError

    def attempt(index):
        actor, child = actors[index]
        barrier.wait(timeout=30)
        try:
            return actor.admit(authority=child, proposal_id=proposal["proposal_id"],
                               request=candidates[index], selection=selections["task-one"],
                               artifact=f"race-{index}.json", started_at=INSTANT)
        except (ValueError, lifecycle_error) as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(attempt, range(2)))
    assert len(decisions(root)) == 1, outcomes
    fresh, child = restarted(values)
    restored = fresh.restore(child)
    key = next(iter(restored["selections"]))
    winner_request = fresh.resolve(key)
    winner = next(i for i, request in enumerate(candidates) if request.prompt == winner_request.prompt)
    before = (Path(root.work_item) / "agent-runs.jsonl").read_bytes()
    assert actors[winner][0].admit(
        authority=actors[winner][1], proposal_id=proposal["proposal_id"],
        request=candidates[winner], selection=selections["task-one"],
        artifact=f"race-{winner}.json", started_at=INSTANT)["request_id"] == key
    with pytest.raises(ValueError, match="conflict"):
        actors[1-winner][0].admit(
            authority=actors[1-winner][1], proposal_id=proposal["proposal_id"],
            request=candidates[1-winner], selection=selections["task-one"],
            artifact=f"race-{1-winner}.json", started_at=INSTANT)
    assert (Path(root.work_item) / "agent-runs.jsonl").read_bytes() == before


def test_revoked_registration_restore_preserves_other_admitted_work(tmp_path, monkeypatch):
    values = registry_fixture(tmp_path, monkeypatch)
    registry, owner, assignment, requests, selections, root, proposal, candidate = values
    outcome = admit(values)
    key = outcome["request_id"]
    exact = registry.resolve(key)
    original = registry._root_authority.assert_current

    def revoked(request, effect):
        if request == exact:
            raise ValueError("registered task permission revoked")
        return original(request, effect)

    monkeypatch.setattr(registry._root_authority, "assert_current", revoked)
    fresh, child = restarted(values)
    before = (Path(root.work_item) / "agent-runs.jsonl").read_bytes()
    restored = fresh.restore(child)
    assert restored["selections"] == {}
    assert restored["unavailable"] == {key: "current_registration_authority_unavailable"}
    assert child.resolve("task-one") == requests["task-one"]
    child.assert_current(requests["task-one"], "sdk_launch_admission")
    with pytest.raises(ValueError, match="revoked"):
        registry.assert_current(exact, "sdk_launch_admission")
    assert (Path(root.work_item) / "agent-runs.jsonl").read_bytes() == before

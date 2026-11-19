"""Root admission atomicity and recovery with real grant/proposal/ledger owners."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

import pytest

from test_sdk_dynamic_child_admission import proposed, addition
from test_sdk_child_lead_authority import INSTANT
from sdk_execution import runtime


def acceptance(values, artifact="admission.json"):
    owner, assignment, requests, selections, root, proposal = values
    selection = addition(owner, requests, selections)
    return dict(authority=owner, proposal_id=proposal["proposal_id"], accepted=True,
                request_id="new-task", selection=selection, artifact=artifact, started_at=INSTANT)


def rejection(values, artifact="rejection.json"):
    return dict(authority=values[0], proposal_id=values[-1]["proposal_id"],
                accepted=False, artifact=artifact, started_at=INSTANT)


def decisions(root):
    return [event for event in runtime._events(root)[2]
            if event.get("runId", "").startswith("child-admission-")]


def restore(values, selections=None):
    owner, assignment, requests, old_selections, root, proposal = values
    return runtime.ChildLeadAuthority(
        root_authority=owner._root_authority, root_selection=root,
        child_id=assignment.child_id, selections=selections or old_selections,
        closure_data=owner._closure_data, terminal_instant=INSTANT,
        repository_root=owner._repository_root)


def test_accept_reject_race_has_one_canonical_decision_and_truthful_retry(tmp_path, monkeypatch):
    values = proposed(tmp_path, monkeypatch)
    owner, assignment, requests, selections, root, proposal = values
    args = [acceptance(values), rejection(values)]
    barrier = Barrier(2)
    lifecycle_error = runtime._ledger(root)[1].load_lifecycle_owner().LifecycleError

    def decide(kwargs):
        barrier.wait(timeout=30)
        try:
            return runtime.publish_child_task_admission(**kwargs)
        except (ValueError, lifecycle_error) as error:
            return str(error)

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(decide, args))
    final = owner.proposal_results(assignment)[proposal["proposal_id"]]
    assert final["status"] in {"accepted", "rejected"}, outcomes
    assert len(decisions(root)) == 1
    winner = args[0] if final["status"] == "accepted" else args[1]
    loser = args[1] if final["status"] == "accepted" else args[0]
    before = (Path(root.work_item) / "agent-runs.jsonl").read_bytes()
    # A post-commit read failure is not permission to invent a second decision.
    assert runtime.publish_child_task_admission(**winner) == final
    with pytest.raises(ValueError, match="already_decided"):
        runtime.publish_child_task_admission(**loser)
    assert (Path(root.work_item) / "agent-runs.jsonl").read_bytes() == before
    catalog = dict(owner.child_catalog(assignment))
    assert ("new-task" in catalog) == (final["status"] == "accepted")


def test_same_proposal_id_different_decision_never_overwrites_receipt(tmp_path, monkeypatch):
    values = proposed(tmp_path, monkeypatch)
    args = acceptance(values)
    result = runtime.publish_child_task_admission(**args)
    root = Path(values[4].work_item)
    receipt_before = (root / args["artifact"]).read_bytes()
    ledger_before = (root / "agent-runs.jsonl").read_bytes()
    for other in (rejection(values, args["artifact"]), {**args, "required": False}):
        with pytest.raises(ValueError, match="already_decided"):
            runtime.publish_child_task_admission(**other)
    assert (root / args["artifact"]).read_bytes() == receipt_before
    assert (root / "agent-runs.jsonl").read_bytes() == ledger_before
    assert runtime.publish_child_task_admission(**args) == result


def test_orphan_receipt_before_commit_does_not_admit_after_restart(tmp_path, monkeypatch):
    values = proposed(tmp_path, monkeypatch)
    owner, assignment, requests, selections, root, proposal = values
    args = acceptance(values, "orphan-admission.json")
    writer = runtime._ledger(root)[0]
    original = writer._append_event_transaction

    def fail_root_commit(item, *args, **kwargs):
        if Path(item) == Path(root.work_item):
            raise RuntimeError("injected loss before admission commit")
        return original(item, *args, **kwargs)

    with patch.object(writer, "_append_event_transaction", new=fail_root_commit):
        with pytest.raises(RuntimeError, match="injected loss"):
            runtime.publish_child_task_admission(**args)
    orphan = Path(root.work_item) / args["artifact"]
    assert orphan.is_file()
    orphan_before = orphan.read_bytes()
    assert decisions(root) == []
    restarted = restore(values)
    assert restarted.proposal_results(assignment)[proposal["proposal_id"]]["status"] == "pending"
    with pytest.raises(ValueError, match="unassigned"):
        restarted.resolve("new-task")
    # Exact immutable orphan bytes can be reconciled after restart, not overwritten.
    accepted = runtime.publish_child_task_admission(**{**args, "authority": restarted})
    assert accepted["status"] == "accepted" and len(decisions(root)) == 1
    assert orphan.read_bytes() == orphan_before


@pytest.mark.parametrize("moment", ["preflight", "commit"])
def test_root_revocation_prevents_admission_even_after_receipt_write(tmp_path, monkeypatch, moment):
    values = proposed(tmp_path, monkeypatch)
    owner, assignment, requests, selections, root, proposal = values
    args = acceptance(values)
    original = owner._root_authority.assert_current

    def revoked(request, effect):
        if effect == ("child_task_admission" if moment == "preflight" else "child_task_admission_commit"):
            raise ValueError("root request authorization revoked")
        return original(request, effect)

    monkeypatch.setattr(owner._root_authority, "assert_current", revoked)
    with pytest.raises(ValueError, match="revoked"):
        runtime.publish_child_task_admission(**args)
    assert decisions(root) == []
    assert owner.proposal_results(assignment)[proposal["proposal_id"]]["status"] == "pending"
    assert owner.child_catalog(assignment) == assignment.catalog


def test_durable_child_revocation_prevents_any_root_decision(tmp_path, monkeypatch):
    values = proposed(tmp_path, monkeypatch)
    owner, assignment, requests, selections, root, proposal = values
    args = acceptance(values)
    asyncio.run(owner.cancel_child(assignment))
    for choice in (args, rejection(values)):
        with pytest.raises(ValueError, match="cancelled"):
            runtime.publish_child_task_admission(**choice)
    assert decisions(root) == []


def test_changed_request_scope_between_admission_and_commit_has_no_effect(tmp_path, monkeypatch):
    values = proposed(tmp_path, monkeypatch)
    owner, assignment, requests, selections, root, proposal = values
    args = acceptance(values)
    original = owner._root_authority.assert_current

    def change_after_check(request, effect):
        original(request, effect)
        if effect == "child_task_admission":
            requests["new-task"] = replace(request, scope=("outside assigned scope",))

    monkeypatch.setattr(owner._root_authority, "assert_current", change_after_check)
    with pytest.raises(ValueError, match="changed|scope"):
        runtime.publish_child_task_admission(**args)
    assert decisions(root) == []
    assert owner.proposal_results(assignment)[proposal["proposal_id"]]["status"] == "pending"



def test_lost_commit_ack_recovers_exact_decision_without_duplicate(tmp_path, monkeypatch):
    values = proposed(tmp_path, monkeypatch)
    owner, assignment, requests, selections, root, proposal = values
    args = acceptance(values)
    writer = runtime._ledger(root)[0]
    original = writer._append_event_transaction

    lost_root_acks = 0

    def lose_ack(item, *args, **kwargs):
        nonlocal lost_root_acks
        result = original(item, *args, **kwargs)
        if Path(item) == Path(root.work_item):
            lost_root_acks += 1
            raise RuntimeError("injected lost admission commit acknowledgement")
        return result

    with patch.object(writer, "_append_event_transaction", new=lose_ack):
        result = runtime.publish_child_task_admission(**args)
    assert lost_root_acks == 1
    assert result["status"] == "accepted"
    assert len(decisions(root)) == 1
    assert runtime.publish_child_task_admission(**args) == result
    assert len(decisions(root)) == 1

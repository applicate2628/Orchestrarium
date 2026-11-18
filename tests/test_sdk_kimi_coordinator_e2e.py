"""Crossed Host composition: synthetic model/process, real Kimi receipt/ledger."""
import asyncio
import json
from types import SimpleNamespace
import pytest
from test_sdk_kimi import prepared, offline_owner, adapter, fixtures, owner
from test_sdk_coordinator import FakeSdk, FakeTool, FakeModel, FakeAuthority
from test_agent_run_ledger import prepare_valid_work_item
from sdk_execution import coordinator
from sdk_execution.kimi import KimiAcpAdapter

def make_composition(tmp_path, monkeypatch):
    item = prepare_valid_work_item(tmp_path)
    launch, request = prepared(tmp_path, monkeypatch, extra_args=(
        "--ledger", str(item), "--ledger-artifact", "reviews/qa.md"))
    requests, runners = offline_owner(monkeypatch, tmp_path, fixtures._FakeKimiAcpPeer())
    monkeypatch.setattr(owner, "run_ledger", lambda runner, args: owner._ledger_owner().main(args) == 0)
    authority = FakeAuthority()
    authority.current = request
    records = []
    executor = adapter(launch, current=authority.assert_current, records=records)
    sdk = FakeSdk()
    monkeypatch.setattr(coordinator, "_load_agents_sdk", lambda: (sdk, FakeTool))
    instance = coordinator.AgentsCoordinator(model=FakeModel(),
        coordinator_binding=request.coordinator_binding, authority=authority,
        executor=executor, max_turns=2)
    return SimpleNamespace(instance=instance, authority=authority, sdk=sdk, executor=executor,
        records=records, requests=requests, runners=runners, launch=launch, request=request,
        ledger=item / "agent-runs.jsonl")

def recover_unchanged(state, monkeypatch):
    before = {p: p.read_bytes() for p in (state.ledger, state.launch.control.terminal_receipt)}
    def forbidden(*args, **kwargs):
        pytest.fail("received-result recovery must not launch or write")
    monkeypatch.setattr(owner, "launch", forbidden)
    monkeypatch.setattr(owner, "record_terminal", forbidden)
    recovery = KimiAcpAdapter(prevalidated=state.launch,
        assert_current=state.authority.assert_current, record=forbidden)
    first = recovery.reconcile_received(state.request, output_context=owner.ProviderOutputContext(()))
    assert first == recovery.reconcile_received(state.request, output_context=owner.ProviderOutputContext(()))
    assert json.loads(first.terminal_json)["resultText"] == "artifact\nGATE: PASS\n"
    assert before == {p: p.read_bytes() for p in before}
    assert len(state.requests) == 1
    return first

def test_coordinator_kimi_actual_receiving_then_read_only_recovery(tmp_path, monkeypatch):
    state = make_composition(tmp_path, monkeypatch)
    result = asyncio.run(state.instance.run("fixture-request"))
    assert len(state.records) == 1
    output = json.loads(result.final_output)
    assert output["status"] == "completed"
    assert output["native_result_text"] == "artifact\nGATE: PASS\n"
    assert output["authoritative"] is False
    assert output["actual_execution_path"] == "direct-external-cli"
    assert output["review"] is None
    assert output["process_settlement"] == "not_established"
    assert state.sdk.model_calls == 1
    assert state.authority.effects[-1] == "executor_result"
    assert len(state.ledger.read_text().splitlines()) == 2
    recover_unchanged(state, monkeypatch)

def test_post_provider_root_denial_preserves_actual_received_kimi_evidence(tmp_path, monkeypatch):
    state = make_composition(tmp_path, monkeypatch)
    state.authority.denied.add("executor_result")
    with pytest.raises(PermissionError, match="current authority denied"):
        asyncio.run(state.instance.run("fixture-request"))
    assert len(state.records) == 1
    assert state.sdk.model_calls == 1 and len(state.requests) == 1
    assert len(state.ledger.read_text().splitlines()) == 2
    state.authority.denied.clear()
    recover_unchanged(state, monkeypatch)

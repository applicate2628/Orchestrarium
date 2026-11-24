"""Direct Kimi Host delivery remains current after canonical receiving."""
import asyncio
import json
import inspect
import pytest
from test_sdk_kimi import prepared, offline_owner, fixtures, owner
from test_agent_run_ledger import prepare_valid_work_item
from sdk_execution.kimi import KimiAcpAdapter, KimiAdapterError


@pytest.mark.parametrize("deny", [False, True])
def test_received_result_currentness_and_readonly_recovery(tmp_path, monkeypatch, deny):
    item = prepare_valid_work_item(tmp_path)
    launch, request = prepared(tmp_path, monkeypatch, extra_args=(
        "--ledger", str(item), "--ledger-artifact", "reviews/qa.md"))
    native, _ = offline_owner(monkeypatch, tmp_path, fixtures._FakeKimiAcpPeer())
    monkeypatch.setattr(owner, "run_ledger", lambda runner, args: owner._ledger_owner().main(args) == 0)
    recorded = []
    effects = []
    def record(observation):
        recorded.append(observation)
    def current(actual, effect):
        assert actual == request
        effects.append(effect)
        if effect == "kimi_result":
            assert recorded
            assert owner.read_back_external_terminal(
                launch.control, "kimi", request.run_id, launch.provenance) is not None
            if deny:
                raise ValueError("private revoked authority detail")
    adapter = KimiAcpAdapter(prevalidated=launch, assert_current=current, record=record)
    if deny:
        with pytest.raises(KimiAdapterError, match="^kimi_result_authority_denied$"):
            asyncio.run(adapter.execute(request))
    else:
        result = asyncio.run(adapter.execute(request))
        assert result is adapter.execution_result
    assert adapter.execution_result.status == "completed"
    assert effects[-1] == "kimi_result"
    assert len(native) == 1
    paths = (launch.control.terminal_receipt, item / "agent-runs.jsonl")
    before = {path: path.read_bytes() for path in paths}
    with pytest.raises(KimiAdapterError, match="operation_already_consumed"):
        asyncio.run(adapter.execute(request))
    assert len(native) == 1
    recovered = adapter.reconcile_received(request, output_context=owner.ProviderOutputContext(()))
    assert json.loads(recovered.terminal_json)["resultText"] == adapter.execution_result.native_result_text
    assert before == {path: path.read_bytes() for path in paths}
    assert (asyncio.run(adapter.cancel(request.run_id))).error == "already_finished"


@pytest.mark.parametrize("deferred", [False, True])
def test_final_callback_non_none_withholds_retained_result(tmp_path, monkeypatch, deferred):
    launch, request = prepared(tmp_path, monkeypatch)
    native, _ = offline_owner(monkeypatch, tmp_path, fixtures._FakeKimiAcpPeer())
    calls = []
    async def never_scheduled():
        pytest.fail("deferred authority must not run")
    def current(_, effect):
        if effect == "kimi_result":
            value = never_scheduled() if deferred else True
            calls.append(value)
            return value
        return None
    adapter = KimiAcpAdapter(prevalidated=launch, assert_current=current, record=lambda _: None)
    with pytest.raises(KimiAdapterError, match="kimi_result_authority_denied"):
        asyncio.run(adapter.execute(request))
    assert adapter.execution_result is not None
    assert len(native) == 1
    if deferred:
        assert inspect.getcoroutinestate(calls[0]) == inspect.CORO_CLOSED

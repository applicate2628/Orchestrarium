"""Actual receipt/ledger recovery; only the native ACP process is synthetic."""
import asyncio
import json
from types import SimpleNamespace
import pytest
from test_sdk_kimi import prepared, offline_owner, adapter, fixtures, owner
from test_agent_run_ledger import prepare_valid_work_item
from sdk_execution.kimi import KimiAcpAdapter, KimiReceivedEvidence
from sdk_execution.contracts import ExecutionResult


def make_received(tmp_path,monkeypatch,*,configure=None):
    item=prepare_valid_work_item(tmp_path)
    launch,request=prepared(tmp_path,monkeypatch,extra_args=(
        "--ledger",str(item),"--ledger-artifact","reviews/qa.md"))
    peer=fixtures._FakeKimiAcpPeer()
    native_requests,runners=offline_owner(monkeypatch,tmp_path,peer)
    # Exercise the actual ledger CLI owner in process; do not ask the fake
    # native runner to execute Python helpers or replace canonical validation.
    monkeypatch.setattr(owner,"run_ledger",lambda runner,args:owner._ledger_owner().main(args)==0)
    current=adapter(launch)
    if configure is not None:configure()
    result=asyncio.run(current.execute(request))
    return SimpleNamespace(launch=launch,request=request,adapter=current,result=result,
        receipt_path=launch.control.terminal_receipt,ledger_path=item/"agent-runs.jsonl",
        output_context=owner.ProviderOutputContext(()),requests=native_requests)


def test_new_host_recovers_actual_received_kimi_evidence_without_launch_or_writes(tmp_path,monkeypatch):
    state=make_received(tmp_path,monkeypatch)
    assert state.result.status=="completed",state.result.to_dict()
    before={path:path.read_bytes() for path in (state.receipt_path,state.ledger_path)}
    def forbidden(*args,**kwargs):pytest.fail("recovery must not launch or record")
    monkeypatch.setattr(owner,"launch",forbidden)
    monkeypatch.setattr(owner,"record_terminal",forbidden)
    effects=[]
    recovered=KimiAcpAdapter(prevalidated=state.launch,
        assert_current=lambda request,effect:effects.append(effect),record=forbidden)
    first=recovered.reconcile_received(state.request,output_context=state.output_context)
    second=recovered.reconcile_received(state.request,output_context=state.output_context)
    assert first==second and type(first) is KimiReceivedEvidence
    assert not isinstance(first,ExecutionResult)
    assert json.loads(first.terminal_json)["resultText"]=="artifact\nGATE: PASS\n"
    row=json.loads(first.ledger_json)
    assert row["runId"]==state.request.external_evidence_run_id
    assert row["terminalReceiptSizeBytes"]==len(before[state.receipt_path])
    assert len(state.requests)==1
    assert effects==["kimi_receipt_read","kimi_receipt_result"]*2
    assert before=={path:path.read_bytes() for path in before}
    assert len([json.loads(line) for line in before[state.ledger_path].splitlines()])==2


@pytest.mark.parametrize("legacy",[False,True])
def test_exported_ledger_evidence_is_scanned_even_without_receipt_digest(tmp_path,monkeypatch,legacy):
    from sdk_execution.kimi import KimiAdapterError
    state=make_received(tmp_path,monkeypatch)
    rows=[json.loads(line) for line in state.ledger_path.read_text().splitlines()]
    terminal=next(row for row in rows if row["eventKind"]=="terminal")
    terminal["notes"]+="; fixture-secret-in-ledger"
    if legacy:
        terminal.pop("terminalReceiptSha256")
        terminal.pop("terminalReceiptSizeBytes")
    state.ledger_path.write_text("".join(json.dumps(row)+"\n" for row in rows))
    def forbidden(*args,**kwargs):pytest.fail("recovery must not launch or record")
    monkeypatch.setattr(owner,"launch",forbidden)
    recovered=KimiAcpAdapter(prevalidated=state.launch,assert_current=lambda *args:None,record=forbidden)
    with pytest.raises(KimiAdapterError,match="E_EXTERNAL_PROVIDER_CREDENTIAL_ECHO"):
        recovered.reconcile_received(state.request,
            output_context=owner.ProviderOutputContext((b"fixture-secret-in-ledger",)))

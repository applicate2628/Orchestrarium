"""Late profile drift over real Kimi receipt/ledger owners; native ACP is synthetic."""
import asyncio
import copy
import json
import pytest
from test_sdk_kimi_received_e2e import make_received
from test_sdk_kimi import fixtures,owner
from sdk_execution.kimi import KimiAcpAdapter,KimiAdapterError


@pytest.mark.parametrize("control,phase",[("model","session/close"),("thinking","session/delete")])
def test_late_profile_drift_is_received_failed_and_readback_never_replays(tmp_path,monkeypatch,control,phase):
    peer=fixtures._FakeKimiAcpPeer()
    model=copy.deepcopy(peer.model_config_result["configOptions"])
    thinking=copy.deepcopy(peer.thinking_config_result["configOptions"])
    # ACP configOptions is a full snapshot; unrelated mode remains valid.
    full=list({option["id"]:option for option in model+thinking}.values())
    peer.thinking_config_result={"configOptions":full}
    changed=copy.deepcopy(full)
    next(option for option in changed if option["id"]==control)["currentValue"]=("unselected-model" if control=="model" else "max")
    peer.interleaved_method=phase
    peer.interleaved_update={"sessionUpdate":"config_option_update","configOptions":changed}
    monkeypatch.setattr(fixtures,"_FakeKimiAcpPeer",lambda:peer)
    state=make_received(tmp_path,monkeypatch)
    assert state.result.status=="failed"
    assert state.result.execution_error=="kimi_native_result_blocked"
    assert state.result.native_result_text=="artifact\nGATE: PASS\n"
    methods=[row["method"] for row in peer.requests]
    assert methods.count("session/prompt")==1
    assert methods.count("session/set_config_option")==2
    assert methods.count("session/close")==methods.count("session/delete")==1
    assert len(state.requests)==1
    rows=[json.loads(line) for line in state.ledger_path.read_text().splitlines()]
    assert len(rows)==2 and rows[-1]["eventKind"]=="terminal"
    assert rows[-1]["status"]!="completed" and rows[-1]["gate"]!="PASS"
    assert rows[-1]["authorizing"] is False
    before={path:path.read_bytes() for path in (state.receipt_path,state.ledger_path)}
    def forbidden(*args,**kwargs):pytest.fail("readback must not launch or record")
    monkeypatch.setattr(owner,"launch",forbidden)
    monkeypatch.setattr(owner,"record_terminal",forbidden)
    recovered=KimiAcpAdapter(prevalidated=state.launch,assert_current=lambda *args:None,record=forbidden)
    first=recovered.reconcile_received(state.request,output_context=state.output_context)
    assert first==recovered.reconcile_received(state.request,output_context=state.output_context)
    terminal=json.loads(first.terminal_json)
    assert terminal["status"]!="completed" and terminal["resultText"]=="artifact\nGATE: PASS\n"
    with pytest.raises(KimiAdapterError,match="consumed"):
        asyncio.run(state.adapter.execute(state.request))
    assert before=={path:path.read_bytes() for path in before}
    assert len(state.requests)==1 and methods==[row["method"] for row in peer.requests]

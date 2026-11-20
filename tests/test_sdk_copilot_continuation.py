"""Fresh and resumed Consultant turns use actual SDK-shaped history evidence."""
import asyncio
from dataclasses import replace
import pytest
from test_sdk_copilot import FakeSdk, make_executor, request, payload
from test_sdk_copilot_coordination import event
from sdk_execution.contracts import NativeContinuation, ExecutionRequest, json_text

def continued(req,first):
    return replace(req,external_dispatch_id="next-dispatch",external_evidence_run_id="next-evidence",
        artifact_id="next.json",context_mode="continuation",
        native_continuation=NativeContinuation(req.external_dispatch_id,req.external_evidence_run_id,"a"*64,
            first.native_thread_id,first.native_turn_id))

def test_fresh_consultant_then_resumed_new_turn_with_no_fresh_fallback(tmp_path):
    req=request(); executor,sdk,_=make_executor(tmp_path)
    first=asyncio.run(executor.execute(req))
    assert first.status=="completed" and first.native_turn_id=="native-turn"
    next_req=continued(req,first)
    peer=FakeSdk();peer.history=list(sdk.history);peer.turn="next-native-turn"
    peer.content=json_text(payload(run_id="next-evidence",artifact_id="next.json"))
    other,_,_=make_executor(tmp_path,sdk=peer)
    result=asyncio.run(other.execute(next_req))
    assert result.status=="completed",result.execution_error
    assert peer.calls.count("resume")==1 and "create" not in peer.calls and peer.calls.count("send")==1
    assert result.native_turn_id=="next-native-turn"
    assert result.sdk_execution["continuationSourceSha256"]==next_req.native_continuation.source_sha256
    assert ExecutionRequest.from_dict(next_req.to_dict())==next_req

@pytest.mark.parametrize("activity",["user.message","assistant.turn_start","abort"])
def test_unsettled_history_refuses_new_consultant_send(tmp_path,activity):
    req=request(); first,peer,_=make_executor(tmp_path)
    result=asyncio.run(first.execute(req));next_req=continued(req,result)
    sdk=FakeSdk();sdk.history=peer.history+[event(activity,"unsettled")]
    executor,_,_=make_executor(tmp_path,sdk=sdk)
    observed=asyncio.run(executor.execute(next_req))
    assert observed.status=="incomplete" and observed.execution_error=="copilot_native_tip_changed"
    assert "send" not in sdk.calls and "create" not in sdk.calls

@pytest.mark.parametrize("changes",[{"context_mode":"fork"},{"role":"lead"},{"result_kind":"review"},{"tool_profile":"default"}])
def test_continuation_does_not_widen_other_roles_or_profiles(tmp_path,changes):
    req=request()
    prior=NativeContinuation("old-dispatch","old-evidence","a"*64,"session","turn")
    with pytest.raises(ValueError):
        replace(req,context_mode="continuation",native_continuation=prior,**changes) if "context_mode" not in changes else replace(req,native_continuation=prior,**changes)

def test_missing_actual_root_turn_end_keeps_task_but_cannot_complete(tmp_path):
    class MissingEnd(FakeSdk):
        async def get_events(self):
            return [event("assistant.turn_start",self.turn),
                event("assistant.message",self.turn,content=self.content)]
    executor,_,_=make_executor(tmp_path,sdk=MissingEnd())
    result=asyncio.run(executor.execute(request()))
    assert result.status=="incomplete" and result.task is not None and result.native_turn_id is None

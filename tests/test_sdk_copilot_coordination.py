"""Actual Copilot decision lifecycle against an offline SDK-shaped peer."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace
import pytest
from test_sdk_copilot import FakeSdk, make_executor
from test_sdk_child_choice import request as codex_request, intent
from sdk_execution.coordination import CoordinationInferenceRequest, CoordinationInferenceResult
from sdk_execution.contracts import NativeContinuation, ExecutionRequest

def request(**changes):
    return replace(codex_request(), provider="copilot", model="selected-model", effort="high",
        decision_session_mode="native-persistent", **changes)

def event(kind, turn=None, **data):
    return SimpleNamespace(type=kind, id="event-"+kind+"-"+str(turn), agent_id=None,
        data=SimpleNamespace(turn_id=turn, **data))

class PersistentSdk(FakeSdk):
    def __init__(self, request, history=None):
        super().__init__()
        self.content=intent(request)
        self.history=list(history or [])
        self.turn="turn-"+request.operation_id
        self.after=[]
    async def resume_session(self, session_id, **kwargs):
        self.calls.append("resume")
        assert session_id==self.session_id
        assert kwargs["continue_pending_work"] is False
        assert kwargs["allow_transcript_recovery"] is False
        self.options=kwargs
        return self
    async def get_events(self):
        self.calls.append("history")
        return list(self.history)
    async def send_and_wait(self, prompt, **kwargs):
        await super().send_and_wait(prompt, **kwargs)
        self.history += [event("user.message"),event("assistant.turn_start",self.turn)]
        final=event("assistant.message",self.turn,content=self.content)
        self.history += [final,event("assistant.turn_end",self.turn),*self.after]
        return final

def test_real_fresh_then_new_session_object_resumes_without_replaying(tmp_path):
    req=request()
    sdk=PersistentSdk(req)
    executor,_,_=make_executor(tmp_path,sdk=sdk)
    first=asyncio.run(executor.execute(req))
    assert type(first) is CoordinationInferenceResult
    assert first.status=="completed", first.execution_error
    assert first.native_turn_id==sdk.turn
    prior=NativeContinuation(req.external_dispatch_id,req.external_evidence_run_id,"a"*64,
        first.native_thread_id,first.native_turn_id)
    next_req=replace(req,external_dispatch_id="next-dispatch",external_evidence_run_id="next-evidence",
        artifact_id="next.json", context_mode="continuation",native_continuation=prior)
    other=PersistentSdk(next_req,sdk.history)
    other.turn="next-native-turn"
    second,_,_=make_executor(tmp_path,sdk=other)
    result=asyncio.run(second.execute(next_req))
    assert result.status=="completed", result.execution_error
    assert other.calls.count("resume")==1 and "create" not in other.calls
    assert other.calls.count("send")==1
    assert result.native_thread_id==first.native_thread_id
    assert result.native_turn_id!=first.native_turn_id
    assert result.sdk_execution["continuationSourceSha256"]==prior.source_sha256
    assert other.options["tools"]=={"available_tools":[]}

@pytest.mark.parametrize("kind",["user.message","assistant.turn_start","pending_messages.modified","abort"])
def test_newer_unsettled_activity_refuses_next_send(tmp_path,kind):
    req=request()
    prior=NativeContinuation("old-dispatch","old-evidence","a"*64,"native-session","old-turn")
    req=replace(req,context_mode="continuation",native_continuation=prior)
    sdk=PersistentSdk(req,[event("assistant.turn_start","old-turn"),
        event("assistant.message","old-turn",content="Previously received intent."),
        event("assistant.turn_end","old-turn"),event(kind,"new-turn")])
    executor,_,_=make_executor(tmp_path,sdk=sdk)
    result=asyncio.run(executor.execute(req))
    assert result.status=="incomplete"
    assert result.execution_error=="copilot_native_tip_changed"
    assert "send" not in sdk.calls and "create" not in sdk.calls
    assert "disconnect" in sdk.calls and "stop" in sdk.calls

def test_completed_decision_requires_actual_matching_turn_end(tmp_path):
    req=request();sdk=PersistentSdk(req)
    sdk.after=[event("assistant.turn_start","unclosed")]
    executor,_,_=make_executor(tmp_path,sdk=sdk)
    result=asyncio.run(executor.execute(req))
    assert result.status=="incomplete" and result.intent_json
    assert result.native_turn_id is None

def test_generic_copilot_lead_does_not_acquire_scoped_authority():
    req=request()
    assert CoordinationInferenceRequest.from_dict(req.to_dict())==req
    fields={k:v for k,v in req.to_dict().items() if k in ExecutionRequest.__dataclass_fields__}
    with pytest.raises(ValueError):
        ExecutionRequest(**fields)

def test_mismatched_new_turn_end_cannot_restore_old_tip(tmp_path):
    req=request()
    prior=NativeContinuation("old-dispatch","old-evidence","a"*64,"native-session","old-turn")
    req=replace(req,context_mode="continuation",native_continuation=prior)
    history=[event("assistant.turn_start","old-turn"),event("assistant.turn_end","old-turn"),
        event("user.message"),event("assistant.turn_start","new-turn"),event("assistant.turn_end","old-turn")]
    sdk=PersistentSdk(req,history)
    executor,_,_=make_executor(tmp_path,sdk=sdk)
    result=asyncio.run(executor.execute(req))
    assert result.execution_error=="copilot_native_tip_changed"
    assert "send" not in sdk.calls

def test_old_session_history_is_not_new_request_event_budget(tmp_path):
    req=replace(request(),max_events=4)
    sdk=PersistentSdk(req)
    sdk.history=[event("session.info") for _ in range(20)]
    executor,_,_=make_executor(tmp_path,sdk=sdk)
    result=asyncio.run(executor.execute(req))
    assert result.status=="completed",result.execution_error

def test_service_tail_does_not_invent_new_activity(tmp_path):
    req=request();sdk=PersistentSdk(req)
    sdk.after=[event("assistant.usage"),event("assistant.idle"),event("session.idle",aborted=False)]
    executor,_,_=make_executor(tmp_path,sdk=sdk)
    result=asyncio.run(executor.execute(req))
    assert result.status=="completed",result.execution_error

@pytest.mark.parametrize("kind",["session.idle","assistant.idle"])
def test_aborted_idle_is_not_completed_tip(tmp_path,kind):
    req=request();sdk=PersistentSdk(req)
    sdk.after=[event(kind,aborted=True)]
    executor,_,_=make_executor(tmp_path,sdk=sdk)
    result=asyncio.run(executor.execute(req))
    assert result.status=="incomplete"
    assert result.execution_error=="copilot_native_tip_changed"

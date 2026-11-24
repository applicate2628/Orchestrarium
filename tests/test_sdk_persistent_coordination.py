"""Native persisted decision transport; all provider calls are in-memory."""
import asyncio
from dataclasses import fields, replace
import pytest
import test_sdk_child_choice as base
from sdk_execution.coordination import CoordinationInferenceRequest
from sdk_execution.contracts import ExecutionRequest, NativeContinuation


def request(resume=False):
    req=replace(base.request(),decision_session_mode="native-persistent")
    if resume:
        req=replace(req,context_mode="continuation",native_continuation=NativeContinuation(
            "prior-dispatch","prior-evidence","a"*64,"thread-1","prior-turn"))
    return req


class Client(base.base.Client):
    def __init__(self,req):
        super().__init__(req,text=base.intent(req))
        self.calls=[]
        self.history={"thread":{"id":"thread-1","turns":[{"id":"prior-turn","status":"completed","error":None}]}}
    def thread_start(self,params):
        self.calls.append(("start",params))
        return super().thread_start(params)
    def thread_resume(self,thread_id,params):
        self.calls.append(("resume",thread_id,params))
        return super().thread_start(params)
    def thread_read(self,thread_id,include_turns=False):
        self.calls.append(("read",thread_id))
        return self.history
    def turn_start(self,thread_id,input_items,params):
        self.calls.append(("turn",thread_id,params))
        return super().turn_start(thread_id,input_items,params)


def test_persistent_first_decision_and_legacy_wire():
    req=request();client=Client(req)
    result=asyncio.run(base.adapter(client).execute(req))
    assert result.status=="completed",result.execution_error
    assert client.calls[0][1]["ephemeral"] is False
    assert "decision_session_mode" not in base.request().to_dict()
    assert CoordinationInferenceRequest.from_dict(req.to_dict())==req


def test_continuation_same_thread_new_turn_and_intent_schema():
    req=request(True);client=Client(req)
    result=asyncio.run(base.adapter(client).execute(req))
    assert result.status=="completed",result.execution_error
    assert [call[0] for call in client.calls]==["resume","read","turn"]
    assert result.native_thread_id=="thread-1" and result.native_turn_id=="turn-1"
    assert "child_choice_sha256" in client.calls[-1][2]["outputSchema"]["required"]
    assert result.sdk_execution["continuationSourceSha256"]==req.native_continuation.source_sha256
    assert CoordinationInferenceRequest.from_dict(req.to_dict())==req
    with pytest.raises(ValueError):
        ExecutionRequest(**{f.name:getattr(req,f.name) for f in fields(ExecutionRequest)})


@pytest.mark.parametrize("changes",[
    {"decision_session_mode":"fresh-handoff"},{"child_choice_json":None},
    {"context_mode":"fork"},{"context_mode":"fresh"},{"native_continuation":None},
    {"external_dispatch_id":"prior-dispatch"},{"role":"consultant"},
])
def test_persistent_invalid_contexts(changes):
    with pytest.raises(ValueError):replace(request(True),**changes)


@pytest.mark.parametrize("turns",[[],[{"id":"prior-turn","status":"inProgress"}],
    [{"id":"later","status":"completed"}],
    [{"id":"prior-turn","status":"completed"},{"id":"later","status":"completed"}]])
def test_stale_or_uncertain_tip_never_starts_or_falls_back(turns):
    req=request(True);client=Client(req);client.history["thread"]["turns"]=turns
    result=asyncio.run(base.adapter(client).execute(req))
    assert result.status=="incomplete"
    assert [call[0] for call in client.calls]==["resume","read"]
    assert result.native_turn_id is None


def test_cancel_before_new_decision_turn_does_not_interrupt_previous():
    req=request(True);client=Client(req);instance=base.adapter(client)
    old=client.thread_read
    def read(*args,**kwargs):
        instance._cancel(req.run_id)
        return old(*args,**kwargs)
    client.thread_read=read
    result=asyncio.run(instance.execute(req))
    assert result.status=="incomplete"
    assert [call[0] for call in client.calls]==["resume","read"]
    assert result.native_turn_id is None


def test_prior_turn_identity_cannot_be_reused_for_new_decision():
    req=request(True);client=Client(req)
    old=client.turn_start
    def start(*args,**kwargs):
        value=old(*args,**kwargs);value["turn"]["id"]="prior-turn";return value
    client.turn_start=start
    result=asyncio.run(base.adapter(client).execute(req))
    assert result.status=="incomplete" and result.native_turn_id is None


def test_missing_resume_api_refuses_before_client_effects():
    req=request(True);client=Client(req);client.thread_resume=None
    result=asyncio.run(base.adapter(client).execute(req))
    assert result.status=="incomplete" and not client.calls

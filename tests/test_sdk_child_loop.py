"""Loop-only tests; concrete owner/ledger integration is separately tested."""
import asyncio
from dataclasses import replace
from types import SimpleNamespace
import pytest
import test_sdk_child_choice as choice
from sdk_execution import runtime
from sdk_execution.coordinator import ChildLeadCoordinator
from sdk_execution.coordination import child_coordination_payload
from sdk_execution.contracts import json_text


def fixture(monkeypatch, *, actions=None, drift=False, missing_receipt=False, swallow_cancel=False):
    assignment=SimpleNamespace(child_id="child",coordinator_binding="host-fixture",
        child_work_item="fixture-item",scope=("fixture scope",),request_ids=("first","second"),
        required_request_ids=("first","second"),task_depth=1,assignment_sha256="a"*64)
    requests={key:replace(choice.base.inner_request(),external_dispatch_id=key+"-dispatch",
        external_evidence_run_id=key+"-evidence",artifact_id=key) for key in assignment.request_ids}
    completed={}
    attempted={}
    calls=[]
    class Authority:
        def resolve_child(self,child_id):return assignment
        def assert_child_current(self,a,effect):
            assert a is assignment
            calls.append(effect)
        def resolve(self,key):return requests[key]
        def attach_executors(self,executors):pass
        def attach_decision_worker(self,a,worker,payload):pass
        def completed_requests(self,a):return dict(completed)
        def attempted_requests(self,a):return dict(attempted)
        def received_context(self,a):return {key:{"receipt":value,"result":"scanned"} for key,value in completed.items()}
        def validate_decision(self,a,req,payload):
            assert req.child_choice_json==payload
        def receive_child_result(self,a):
            assert set(completed)==set(a.required_request_ids)
            calls.append("closed")
            return "archived-child"
        async def cancel_child(self,a):
            calls.append("cancelled")
            return {"status":"cancellation-requested","settled":False}
    authority=Authority()
    executors={key:object.__new__(runtime.SdkReviewExecutor) for key in requests}
    for key,obj in executors.items():obj.test_request=requests[key]
    monkeypatch.setattr(runtime.SdkReviewExecutor,"validate_request",lambda self:self.test_request)
    async def execute(self,request):
        key=next(key for key,value in requests.items() if value==request)
        calls.append("execute:"+key)
        if swallow_cancel:
            asyncio.current_task().cancel()
            try:
                await asyncio.sleep(0)
            except asyncio.CancelledError:
                pass  # Concrete process draining may return retained evidence.
        attempted[key]={"runId":request.external_dispatch_id,"status":"blocked" if missing_receipt else "completed"}
        if not missing_receipt:completed[key]={"runId":request.external_evidence_run_id}
        return SimpleNamespace(request=request,status="completed")
    monkeypatch.setattr(runtime.SdkReviewExecutor,"execute",execute)
    remaining=iter(actions or [("execute","second"),("execute","first"),("finish",None)])
    def factory(a,payload):
        req=choice.base.request()
        req=replace(req,child_choice_json=payload,
            prompt=child_coordination_payload(req.operation_id,req.system_instructions,payload))
        worker=object.__new__(runtime.SdkCoordinationWorker)
        worker.test_request=req
        worker.test_intent=choice.intent(req,*next(remaining))
        return worker
    async def decide(self,req):
        if drift:
            completed["first"]={"runId":"changed-during-model"}
            attempted["first"]={"runId":"changed-launch"}
        return SimpleNamespace(result=SimpleNamespace(intent_json=self.test_intent))
    monkeypatch.setattr(runtime.SdkCoordinationWorker,"__call__",decide)
    loop=ChildLeadCoordinator(child_id="child",authority=authority,decision_factory=factory,executors=executors)
    return loop,calls


def test_real_choice_order_then_child_owner_close(monkeypatch):
    loop,calls=fixture(monkeypatch)
    assert asyncio.run(loop.run())=="archived-child"
    assert [x for x in calls if x.startswith("execute:")]==["execute:second","execute:first"]
    assert calls[-1]=="closed"
    with pytest.raises(ValueError,match="already consumed"):asyncio.run(loop.run())


def test_changed_state_after_decision_cannot_delegate(monkeypatch):
    loop,calls=fixture(monkeypatch,drift=True)
    with pytest.raises(ValueError,match="state changed"):asyncio.run(loop.run())
    assert not any(x.startswith("execute:") for x in calls)


def test_uncertain_result_stops_no_retry_no_close(monkeypatch):
    loop,calls=fixture(monkeypatch,missing_receipt=True)
    result=asyncio.run(loop.run())
    assert result["status"]=="needs-reconciliation"
    assert [x for x in calls if x.startswith("execute:")]==["execute:second","execute:first"]
    assert "closed" not in calls


def test_cancel_intent_reaches_async_owner_without_delegation(monkeypatch):
    loop,calls=fixture(monkeypatch,actions=[("cancel",None)])
    assert asyncio.run(loop.run())=={"status":"cancellation-requested","settled":False}
    assert calls[-1]=="cancelled"
    assert not any(x.startswith("execute:") for x in calls)


def test_drained_executor_cannot_swallow_parent_cancellation_and_continue(monkeypatch):
    loop,calls=fixture(monkeypatch,swallow_cancel=True)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(loop.run())
    assert [x for x in calls if x.startswith("execute:")]==["execute:second"]
    assert calls[-1]=="cancelled" and "closed" not in calls

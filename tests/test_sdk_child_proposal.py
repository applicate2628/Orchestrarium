"""Closed task proposals are data, not executable authority."""
import json
from dataclasses import replace
import pytest
import test_sdk_child_choice as base
from sdk_execution.coordination import child_coordination_payload,validate_intent,intent_schema,validate_task_proposal
from sdk_execution.contracts import json_text


def request(outcomes=()):
    original=base.request();choice=json.loads(original.child_choice_json)
    choice["proposal_results"]=list(outcomes)
    projection=json_text(choice)
    return replace(original,child_choice_json=projection,
        prompt=child_coordination_payload(original.operation_id,original.system_instructions,projection))


def proposal():return {"proposal_id":"additional-check","role":"consultant","prompt":"Check the omitted branch.","scope":["fixture scope"]}


def intent(req,proposal_value=None):
    value=json.loads(base.intent(req,"propose",None));value["proposal"]=proposal() if proposal_value is None else proposal_value
    return json_text(value)


def test_proposal_schema_and_parser_do_not_grant_execution_controls():
    req=request();value=json.loads(validate_intent(intent(req),req))
    assert value["request_id"] is None
    assert set(value["proposal"])=={"proposal_id","role","prompt","scope"}
    assert "propose" in intent_schema(req)["properties"]["action"]["enum"]
    assert "proposal" in intent_schema(req)["required"]
    legacy=base.request()
    assert "propose" not in intent_schema(legacy)["properties"]["action"]["enum"]
    with pytest.raises(ValueError):validate_intent(intent(legacy),legacy)


@pytest.mark.parametrize("field,value",[("model","unadmitted"),("provider","claude"),("write_workspace","/workspace"),("account","other"),("required",True)])
def test_proposal_cannot_select_controls(field,value):
    with pytest.raises(ValueError):validate_task_proposal({**proposal(),field:value})


@pytest.mark.parametrize("status",["pending","accepted","rejected"])
def test_received_proposal_identity_cannot_be_proposed_again(status):
    req=request([{"proposal_id":"additional-check","result":{"proposal":proposal(),"status":status,"request_id":None}}])
    with pytest.raises(ValueError,match="already received"):validate_intent(intent(req),req)
    validate_intent(base.intent(req,"execute","second"),req)


def test_scope_and_payload_shape_are_validated():
    with pytest.raises(ValueError):validate_intent(intent(request(),{**proposal(),"scope":["outside"]}),request())
    with pytest.raises(ValueError):validate_task_proposal({**proposal(),"scope":[]})
    with pytest.raises(ValueError):validate_task_proposal({**proposal(),"prompt":" "})


def test_nonproposal_has_null_proposal_not_hidden_request():
    req=request();value=json.loads(base.intent(req));value["proposal"]=None
    validate_intent(json_text(value),req)
    value["proposal"]=proposal()
    with pytest.raises(ValueError):validate_intent(json_text(value),req)


def test_pending_proposal_does_not_replay_or_stop_ready_siblings(monkeypatch):
    import asyncio
    from test_sdk_child_loop import fixture
    loop,calls=fixture(monkeypatch,actions=[("execute","first"),("execute","second")])
    loop._authority.proposal_results=lambda assignment:{"additional-check":{"proposal":proposal(),"status":"pending","request_id":None}}
    result=asyncio.run(loop.run())
    assert result["status"]=="needs-admission"
    assert [x for x in calls if x.startswith("execute:")]==["execute:first","execute:second"]
    assert len(loop.decisions)==2 and "closed" not in calls


def test_rejected_proposal_does_not_block_other_work_or_close(monkeypatch):
    import asyncio
    from test_sdk_child_loop import fixture
    loop,calls=fixture(monkeypatch)
    loop._authority.proposal_results=lambda assignment:{"additional-check":{"proposal":proposal(),"status":"rejected","request_id":None}}
    assert asyncio.run(loop.run())=="archived-child"
    assert len(loop.decisions)==3


def test_own_received_proposal_is_expected_projection_change(monkeypatch):
    import asyncio
    from types import SimpleNamespace
    from test_sdk_child_loop import fixture
    from sdk_execution import runtime
    loop,calls=fixture(monkeypatch,actions=[("execute","first"),("execute","second")])
    outcomes={}
    loop._authority.proposal_results=lambda assignment:dict(outcomes)
    loop._authority.submit_child_proposal=lambda assignment,worker,value:outcomes[value["proposal_id"]]
    old_factory=loop._factory
    def factory(assignment,projection):
        if outcomes:return old_factory(assignment,projection)
        req=base.base.request()
        req=replace(req,child_choice_json=projection,prompt=child_coordination_payload(req.operation_id,req.system_instructions,projection))
        worker=object.__new__(runtime.SdkCoordinationWorker)
        worker.test_request=req;worker.test_intent=intent(req)
        return worker
    loop._factory=factory
    old_decide=runtime.SdkCoordinationWorker.__call__
    async def decide(worker,req):
        result=await old_decide(worker,req)
        if json.loads(result.result.intent_json)["action"]=="propose":
            outcomes["additional-check"]={"proposal":proposal(),"status":"pending","request_id":None}
        return result
    monkeypatch.setattr(runtime.SdkCoordinationWorker,"__call__",decide)
    assert asyncio.run(loop.run())["status"]=="needs-admission"
    assert len(loop.decisions)==3
    assert [x for x in calls if x.startswith("execute:")]==["execute:first","execute:second"]


def test_new_unbound_acceptance_waits_until_bound_ready_work_finishes(monkeypatch):
    import asyncio
    from test_sdk_child_loop import fixture
    loop,calls=fixture(monkeypatch,actions=[("execute","first"),("execute","second")])
    loop._authority.child_catalog=lambda assignment:tuple((key,"b"*64) for key in ("first","second","new-task"))
    loop._authority.child_bound_request_ids=lambda assignment:("first","second")
    loop._authority.child_required_request_ids=lambda assignment:("first","second","new-task")
    loop._authority.proposal_results=lambda assignment:{"additional-check":{"proposal":proposal(),"status":"accepted","request_id":"new-task"}}
    assert asyncio.run(loop.run())["status"]=="needs-host-refresh"
    assert [x for x in calls if x.startswith("execute:")]==["execute:first","execute:second"]


def test_finish_cannot_ignore_pending_or_unbound_admission():
    for status,request_id in (("pending",None),("accepted","not-bound")):
        req=request([{"proposal_id":"additional-check","result":{"proposal":proposal(),"status":status,"request_id":request_id}}])
        state=json.loads(req.child_choice_json);state["required_request_ids"]=[]
        projection=json_text(state)
        req=replace(req,child_choice_json=projection,prompt=child_coordination_payload(req.operation_id,req.system_instructions,projection))
        with pytest.raises(ValueError,match="Root admission"):
            validate_intent(base.intent(req,"finish",None),req)


def test_dynamic_prompt_uses_actual_admitted_output_budget():
    req=request();large={**proposal(),"prompt":"x"*20000}
    encoded=intent(req,large)
    validate_intent(encoded,req)
    with pytest.raises(ValueError):
        validate_intent(encoded,replace(req,max_output_bytes=16384))


def test_root_admission_during_decision_does_not_interrupt_bound_task(monkeypatch):
    import asyncio
    from test_sdk_child_loop import fixture
    from sdk_execution import runtime
    loop,calls=fixture(monkeypatch,actions=[("execute","first"),("execute","second")])
    outcomes={}
    loop._authority.proposal_results=lambda assignment:dict(outcomes)
    old_decide=runtime.SdkCoordinationWorker.__call__
    async def decide(worker,req):
        result=await old_decide(worker,req)
        outcomes["additional-check"]={"proposal":proposal(),"status":"accepted","request_id":"unbound-task"}
        return result
    monkeypatch.setattr(runtime.SdkCoordinationWorker,"__call__",decide)
    result=asyncio.run(loop.run())
    assert result["status"]=="needs-host-refresh"
    assert [x for x in calls if x.startswith("execute:")]==["execute:first","execute:second"]


def test_root_optional_unbound_task_does_not_become_mandatory():
    req=request([{"proposal_id":"additional-check","result":{"proposal":proposal(),"status":"accepted","request_id":"not-bound","required":False}}])
    state=json.loads(req.child_choice_json);state["required_request_ids"]=[]
    projection=json_text(state)
    req=replace(req,child_choice_json=projection,prompt=child_coordination_payload(req.operation_id,req.system_instructions,projection))
    validate_intent(base.intent(req,"finish",None),req)


def test_unreceipted_proposal_is_refused_by_canonical_owner_before_any_task(monkeypatch):
    import asyncio
    from test_sdk_child_loop import fixture
    from sdk_execution import runtime
    loop,calls=fixture(monkeypatch)
    loop._authority.proposal_results=lambda assignment:{}
    def refuse(assignment,worker,value):raise runtime.RuntimeBindingError("child_proposal_not_received")
    loop._authority.submit_child_proposal=refuse
    def factory(assignment,projection):
        req=base.base.request()
        req=replace(req,child_choice_json=projection,prompt=child_coordination_payload(req.operation_id,req.system_instructions,projection))
        worker=object.__new__(runtime.SdkCoordinationWorker)
        worker.test_request=req;worker.test_intent=intent(req)
        return worker
    loop._factory=factory
    with pytest.raises(ValueError,match="not_received"):asyncio.run(loop.run())
    assert not any(call.startswith("execute:") for call in calls)


def test_received_conflicting_proposal_disposition_does_not_block_independent_task(monkeypatch):
    import asyncio
    from test_sdk_child_loop import fixture
    from sdk_execution import runtime
    loop,calls=fixture(monkeypatch,actions=[("execute","first"),("execute","second")])
    outcomes={};submits=[]
    loop._authority.proposal_results=lambda assignment:dict(outcomes)
    def submit(assignment,worker,value):
        submits.append(value)
        return outcomes[value["proposal_id"]]
    loop._authority.submit_child_proposal=submit
    old_factory=loop._factory
    def factory(assignment,projection):
        if outcomes:return old_factory(assignment,projection)
        req=base.base.request()
        req=replace(req,child_choice_json=projection,prompt=child_coordination_payload(req.operation_id,req.system_instructions,projection))
        worker=object.__new__(runtime.SdkCoordinationWorker)
        worker.test_request=req;worker.test_intent=intent(req)
        return worker
    loop._factory=factory
    old_decide=runtime.SdkCoordinationWorker.__call__
    async def decide(worker,req):
        result=await old_decide(worker,req)
        if json.loads(result.result.intent_json)["action"]=="propose":
            outcomes["additional-check"]={"proposal":{**proposal(),"prompt":"Earlier canonical proposal."},
                "status":"pending","request_id":None,"rejected_duplicates":[{"reason":"payload_changed"}]}
        return result
    monkeypatch.setattr(runtime.SdkCoordinationWorker,"__call__",decide)
    assert asyncio.run(loop.run())["status"]=="needs-admission"
    assert len(submits)==1 and [x for x in calls if x.startswith("execute:")]==["execute:first","execute:second"]

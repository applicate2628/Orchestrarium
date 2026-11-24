"""An explicit Root goal can start a child without invented executable tasks."""
import asyncio
import json
from dataclasses import replace
import pytest
import test_sdk_child_proposal as proposal
import test_sdk_child_choice as base
from sdk_execution.coordination import child_coordination_payload, validate_child_choice, validate_intent, intent_schema
from sdk_execution.contracts import json_text


def empty_request(**updates):
    original=proposal.request()
    value=json.loads(original.child_choice_json)
    value.update(catalog=[],required_request_ids=[],completed_request_ids=[],received_results=[],
                 unavailable_results=[],goal="Investigate the scoped question.",context="Root supplied background.")
    value.update(updates)
    encoded=json_text(value)
    return replace(original,child_choice_json=encoded,
        prompt=child_coordination_payload(original.operation_id,original.system_instructions,encoded))


def test_empty_goal_request_can_propose_but_cannot_execute_unadmitted_id():
    request=empty_request()
    assert json.loads(validate_intent(proposal.intent(request),request))["action"]=="propose"
    assert intent_schema(request)["properties"]["request_id"]["enum"]==[None]
    with pytest.raises(ValueError,match="unavailable"):
        validate_intent(base.intent(request,"execute","invented"),request)
    # No invented minimum task count: actual Root lifecycle remains the owner.
    validate_intent(base.intent(request,"finish",None),request)


@pytest.mark.parametrize("change",[
    {"goal":""},{"goal":" "},{"goal":False},{"context":{}}
])
def test_invalid_goal_context_rejected(change):
    with pytest.raises(ValueError):empty_request(**change)


def test_goal_and_context_are_paired_and_empty_catalog_requires_goal():
    value=json.loads(empty_request().child_choice_json)
    for field in ("goal","context"):
        changed=dict(value);del changed[field]
        with pytest.raises(ValueError):validate_child_choice(json_text(changed))
    value.pop("goal");value.pop("context")
    with pytest.raises(ValueError,match="catalog"):validate_child_choice(json_text(value))
    empty_request(context=None)
    empty_request(context="")


def test_goal_context_are_hash_bound_not_model_controls():
    original=empty_request()
    for field in ("goal","context"):
        changed=empty_request(**{field:"Changed Root input."})
        with pytest.raises(ValueError,match="mismatched"):
            validate_intent(base.intent(original,"finish",None),changed)
    value=json.loads(proposal.intent(original))
    value["goal"]="Override"
    with pytest.raises(ValueError):validate_intent(json_text(value),original)


def test_empty_loop_runs_real_decision_boundary_then_waits_for_root(monkeypatch):
    from test_sdk_child_loop import fixture
    from sdk_execution import runtime
    loop,calls=fixture(monkeypatch,actions=[("finish",None)])
    assignment=loop._authority.resolve_child("child")
    assignment.request_ids=();assignment.required_request_ids=()
    assignment.goal="Investigate the scoped question.";assignment.context="Root background."
    loop._executors={}
    outcomes={}
    loop._authority.proposal_results=lambda a:dict(outcomes)
    loop._authority.submit_child_proposal=lambda a,w,p:outcomes[p["proposal_id"]]
    old_factory=loop._factory
    def factory(a,projection):
        assert json.loads(projection)["catalog"]==[]
        assert json.loads(projection)["goal"]==assignment.goal
        worker=old_factory(a,projection)
        worker.test_intent=proposal.intent(worker.test_request)
        return worker
    loop._factory=factory
    old_decide=runtime.SdkCoordinationWorker.__call__
    async def decide(worker,req):
        result=await old_decide(worker,req)
        item=json.loads(result.result.intent_json)["proposal"]
        outcomes[item["proposal_id"]]={"proposal":item,"status":"pending","request_id":None}
        return result
    monkeypatch.setattr(runtime.SdkCoordinationWorker,"__call__",decide)
    assert asyncio.run(loop.run())["status"]=="needs-admission"
    assert len(loop.decisions)==1
    assert not any(call.startswith("execute:") for call in calls)
    assert "closed" not in calls


def test_legacy_projection_has_no_synthetic_goal_fields():
    request=base.request()
    assert "goal" not in json.loads(request.child_choice_json)
    assert "context" not in json.loads(request.child_choice_json)
    validate_intent(base.intent(request),request)

"""Empty Root child assignment: a goal is not an executable seed task."""
import hashlib,time
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_sdk_runtime import fixture as base
from test_mutate_work_item import quick_status,closure
from test_sdk_child_lead_authority import INSTANT
from sdk_execution import runtime
from sdk_execution.contracts import json_text
from sdk_execution.coordination import CoordinationInferenceRequest,child_coordination_payload
from provider_prompt import ProviderOutputContext,assemble_external_prompt


def empty_fixture(tmp_path,monkeypatch,**overrides):
    template,root=base(tmp_path)
    Path(root.work_item,'status.md').write_text(quick_status())
    child=Path(root.work_item).parent/'goal-child';child.mkdir();(child/'status.md').write_text(quick_status())
    decision=replace(root,work_item=str(child),config_overrides=runtime.CODEX_BOUNDED_REVIEW_OVERRIDES)
    requests={};root_authority=SimpleNamespace(resolve=lambda key:requests[key],assert_current=lambda request,effect:None)
    options=dict(root_selection=root,root_authority=root_authority,selections={},child_id='goal-child-grant',
        coordinator_binding='goal-coordinator',scope=template.scope,required_request_ids=(),
        lifecycle_permissions=('delegate','finish','cancel'),artifact='goal-grant.json',started_at=INSTANT,
        child_work_item=str(child),goal='Investigate the assigned objective and propose concrete work.',
        context='Root supplies task context without an executable seed.',decision_selection=decision)
    options.update(overrides)
    assignment=runtime.publish_child_assignment(**options)
    authority=runtime.ChildLeadAuthority(root_authority=root_authority,root_selection=root,child_id=assignment.child_id,
        selections={},closure_data=closure(INSTANT).encode(),terminal_instant=INSTANT,repository_root=tmp_path)
    monkeypatch.setattr(runtime,'prepare_environment',lambda *a:({},ProviderOutputContext(())))
    return authority,assignment,requests,{},root,template,decision


def decision_candidate(values,process,key='goal-decision',**projection_changes):
    owner,assignment,requests,selections,root,template,selection=values
    projection=json_text({'assignment_sha256':assignment.assignment_sha256,'catalog':[],
        'required_request_ids':[],'completed_request_ids':[],'received_results':[],'unavailable_results':[],
        'proposal_results':[],'goal':assignment.goal,'context':assignment.context,**projection_changes})
    system='Choose scoped work from the Root objective.'
    request=CoordinationInferenceRequest(**{**template.to_dict(),'scope':assignment.scope,
        'work_item_id':Path(assignment.child_work_item).name,'cwd':assignment.child_work_item,
        'coordinator_binding':assignment.coordinator_binding,'role':'lead','result_kind':'review',
        'external_dispatch_id':key+'-dispatch','external_evidence_run_id':key+'-evidence','artifact_id':key,
        'prompt':assemble_external_prompt(child_coordination_payload(key,system,projection).encode()).decode(),
        'operation_id':key,'admitted_request_id':assignment.child_id,'outer_budget_id':key+'-outer','inner_budget_id':key+'-inner',
        'inner_request_sha256':hashlib.sha256(projection.encode()).hexdigest(),'system_instructions':system,'child_choice_json':projection,
        'decision_session_mode':assignment.decision_session_mode})
    request=owner.prepare_child_decision(assignment,request,selection)
    requests[key]=request
    worker=runtime.SdkCoordinationWorker(request_id=key,authority=owner,selection=selection,process_owner=process,
        source_environment={},artifact=key+'.json',deadline_monotonic=time.monotonic()+600,
        cancellation_probe=lambda:False,started_at=INSTANT)
    return worker,request,projection


def test_empty_goal_grant_restores_without_fabricating_task_or_root_request(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root,template,decision=empty_fixture(tmp_path,monkeypatch)
    assert assignment.catalog==assignment.required_request_ids==()
    assert requests=={} and owner.child_catalog(assignment)==()
    assert owner.resolve_child(assignment.child_id)==assignment
    assert assignment.goal and assignment.context
    owner.attach_executors({})
    assert owner.proposal_results(assignment)=={}
    assert len(runtime._events(root)[2])==1
    assert not Path(assignment.child_work_item,'agent-runs.jsonl').exists()


@pytest.mark.parametrize('change',[{'goal':None},{'goal':''},{'child_work_item':None},{'child_work_item':'relative-child'},{'context':42},{'scope':()}])
def test_empty_grant_requires_explicit_valid_goal_path_and_scope(tmp_path,monkeypatch,change):
    with pytest.raises(ValueError):empty_fixture(tmp_path,monkeypatch,**change)


@pytest.mark.parametrize('field',['goal','context'])
def test_decision_cannot_substitute_root_goal_context(tmp_path,monkeypatch,field):
    from process_supervision.process_runner import ProcessRunnerV1
    values=empty_fixture(tmp_path,monkeypatch)
    with ProcessRunnerV1() as process,pytest.raises(ValueError,match='goal_changed'):
        decision_candidate(values,process,**{field:'Different unadmitted objective.'})
    assert not Path(values[1].child_work_item,'agent-runs.jsonl').exists()


def test_existing_seeded_grant_wire_does_not_gain_goal_fields(tmp_path,monkeypatch):
    from test_sdk_child_lead_authority import fixture
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    doc=runtime._child_assignment_document(assignment)
    assert 'goal' not in doc and 'context' not in doc
    assert assignment.goal is None and assignment.context is None
    assert owner.resolve_child(assignment.child_id)==assignment

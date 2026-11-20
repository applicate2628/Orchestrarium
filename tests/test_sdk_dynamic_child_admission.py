"""Root admission of received child proposals, with real ledger/receiving owners."""
import hashlib,json
from dataclasses import replace
from unittest.mock import patch
import pytest
import test_sdk_persistent_child_lead as support
from test_sdk_child_lead_authority import INSTANT
from sdk_execution import runtime
from sdk_execution.contracts import json_text
from sdk_execution.coordination import child_choice_sha256
from process_supervision.process_runner import ProcessRunnerV1


def proposed(tmp_path,monkeypatch,*,proposal_prompt="Investigate another scoped question."):
    values=support.persistent_fixture(tmp_path,monkeypatch)
    owner,assignment,requests,selections,root=values
    task=requests['task-one']
    proposal={'proposal_id':'investigate-next','prompt':proposal_prompt,'role':'consultant','scope':list(task.scope)}
    projection=json_text({'assignment_sha256':assignment.assignment_sha256,'catalog':[
        {'request_id':'task-one','request_sha256':hashlib.sha256(json_text(task.to_dict()).encode()).hexdigest(),
         'role':task.role,'scope':list(task.scope),'prompt':task.prompt}],
        'required_request_ids':['task-one'],'completed_request_ids':[],'received_results':[],'unavailable_results':[], 'proposal_results':[]})
    intent=json_text({'operation_id':'decision-one','child_choice_sha256':child_choice_sha256(projection),
        'action':'propose','request_id':None,'proposal':proposal})
    original=support.candidate
    with ProcessRunnerV1() as process,patch.object(support,'candidate',side_effect=lambda *a,**kw:original(*a,**kw,projection=projection)):
        support.receive_decision(owner,assignment,requests,selections,process,monkeypatch,intent_json=intent)
    return (*values,proposal)


def addition(owner,requests,selections):
    request=replace(requests['task-one'],prompt='Root-admitted follow-up.',external_dispatch_id='new-task-dispatch',external_evidence_run_id='new-task-evidence',artifact_id='new-task')
    request=runtime.prepare_codex_request(request)
    requests['new-task']=request
    return selections['task-one']


def test_received_proposal_is_data_until_root_admits_and_restart_claims_exact_task(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root,proposal=proposed(tmp_path,monkeypatch)
    assert owner.proposal_results(assignment)[proposal['proposal_id']]['status']=='pending'
    assert owner.child_catalog(assignment)==assignment.catalog
    with pytest.raises(ValueError,match='unassigned'):owner.resolve('new-task')
    selection=addition(owner,requests,selections)
    result=runtime.publish_child_task_admission(authority=owner,proposal_id=proposal['proposal_id'],accepted=True,
        request_id='new-task',selection=selection,artifact='admission.json',started_at=INSTANT)
    assert result['status']=='accepted' and result['required'] is True
    owner.assert_current(requests['task-one'],'existing_worker_effect')
    with pytest.raises(ValueError,match='refresh_required'):owner.resolve('new-task')
    unbound=runtime.ChildLeadAuthority(root_authority=owner._root_authority,root_selection=root,child_id=assignment.child_id,
        selections=selections,closure_data=owner._closure_data,terminal_instant=INSTANT,repository_root=tmp_path)
    assert unbound.child_bound_request_ids(assignment)==('task-one',)
    assert unbound.child_required_request_ids(assignment)==('task-one','new-task')
    selections={**selections,'new-task':selection}
    restored=runtime.ChildLeadAuthority(root_authority=owner._root_authority,root_selection=root,child_id=assignment.child_id,
        selections=selections,closure_data=owner._closure_data,terminal_instant=INSTANT,repository_root=tmp_path)
    assert restored.resolve_child(assignment.child_id)==assignment
    assert restored.child_required_request_ids(assignment)==('task-one','new-task')
    runtime.claim_launch(restored.resolve('new-task'),selection,authority=restored.assert_current,started_at=INSTANT)
    with pytest.raises(ValueError):runtime.claim_launch(restored.resolve('new-task'),selection,authority=restored.assert_current,started_at=INSTANT)
    assert len(runtime._events(selection)[2])==3


def test_rejection_is_durable_idempotent_and_cannot_later_grant(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root,proposal=proposed(tmp_path,monkeypatch)
    kwargs=dict(authority=owner,proposal_id=proposal['proposal_id'],accepted=False,artifact='rejection.json',started_at=INSTANT)
    first=runtime.publish_child_task_admission(**kwargs)
    assert runtime.publish_child_task_admission(**kwargs)==first
    assert owner.child_catalog(assignment)==assignment.catalog
    selection=addition(owner,requests,selections)
    with pytest.raises(ValueError,match='already_decided'):
        runtime.publish_child_task_admission(**{**kwargs,'accepted':True,'request_id':'new-task','selection':selection,'artifact':'contradict.json'})


@pytest.mark.parametrize('change',[{'scope':('outside',)}, {'coordinator_binding':'other-child'}])
def test_root_admission_cannot_cross_child_scope(tmp_path,monkeypatch,change):
    owner,assignment,requests,selections,root,proposal=proposed(tmp_path,monkeypatch)
    selection=addition(owner,requests,selections)
    requests['new-task']=replace(requests['new-task'],**change)
    with pytest.raises(ValueError,match='scope'):
        runtime.publish_child_task_admission(authority=owner,proposal_id=proposal['proposal_id'],accepted=True,
            request_id='new-task',selection=selection,artifact='bad.json',started_at=INSTANT)
    assert owner.proposal_results(assignment)[proposal['proposal_id']]['status']=='pending'


def test_changed_proposal_artifact_does_not_create_admission(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root,proposal=proposed(tmp_path,monkeypatch)
    from pathlib import Path
    (Path(assignment.child_work_item)/'decision-one.json').write_text('{}')
    with pytest.raises(ValueError,match='changed|current_ledger_invalid'):owner.proposal_results(assignment)


def test_persisted_proposal_handoff_is_scanned_before_next_model_effect(tmp_path,monkeypatch):
    from provider_prompt import ProviderOutputContext,assemble_external_prompt
    from sdk_execution.coordination import child_coordination_payload
    secret='fixture-'+__import__('uuid').uuid4().hex
    owner,assignment,requests,selections,root,proposal=proposed(tmp_path,monkeypatch,proposal_prompt=secret)
    with ProcessRunnerV1() as process:
        worker,request,projection=support.candidate(owner,assignment,requests,selections,process,'next-decision')
        value=json.loads(projection)
        value['proposal_results']=[{'proposal_id':proposal['proposal_id'],'result':owner.proposal_results(assignment)[proposal['proposal_id']]}]
        projection=json_text(value)
        request=replace(request,child_choice_json=projection,prompt=assemble_external_prompt(
            child_coordination_payload(request.operation_id,request.system_instructions,projection).encode()).decode())
        requests['next-decision']=request
        monkeypatch.setattr(runtime,'prepare_environment',lambda *a:({},ProviderOutputContext((secret.encode(),))))
        with pytest.raises(ValueError,match='E_EXTERNAL_PROVIDER'):
            owner.attach_decision_worker(assignment,worker,projection)
        assert worker.runtime_run is None
        assert len(runtime._events(selections['task-one'])[2])==2


@pytest.mark.parametrize('conflicting',[False,True])
def test_later_received_proposal_identity_cannot_replace_first_or_block_existing_task(tmp_path,monkeypatch,conflicting):
    owner,assignment,requests,selections,root,proposal=proposed(tmp_path,monkeypatch)
    first=owner.proposal_results(assignment)[proposal['proposal_id']]
    later={**proposal,'prompt':'Conflicting later task.'} if conflicting else proposal
    projection=requests['decision-one'].child_choice_json
    intent=json_text({'operation_id':'decision-two','child_choice_sha256':child_choice_sha256(projection),
        'action':'propose','request_id':None,'proposal':later})
    original=support.candidate
    with ProcessRunnerV1() as process,patch.object(support,'candidate',side_effect=lambda *a,**kw:original(*a,**kw,projection=projection)):
        support.receive_decision(owner,assignment,requests,selections,process,monkeypatch,key='decision-two',
            intent_json=intent,native_turn_id='turn-two')
    current=owner.submit_child_proposal(assignment,None,later)
    assert current['proposal']==proposal and current['source_evidence_id']==first['source_evidence_id']
    assert bool(current.get('rejected_duplicates')) is conflicting
    owner.assert_current(requests['task-one'],'independent_task_effect')
    assert owner.child_catalog(assignment)==assignment.catalog
    runtime.publish_child_task_admission(authority=owner,proposal_id=proposal['proposal_id'],accepted=False,
        artifact='rejection.json',started_at=INSTANT)
    assert owner.proposal_results(assignment)[proposal['proposal_id']]['source_evidence_id']==first['source_evidence_id']

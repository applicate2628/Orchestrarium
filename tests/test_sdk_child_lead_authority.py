"""Concrete Root grants and scoped child owners, entirely offline."""
import asyncio,json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_sdk_runtime import fixture as base
from test_sdk_claude_consultant_receiving import observed
from test_mutate_work_item import quick_status,closure,write_empty_bug_dispositions
from sdk_execution import runtime,receiving
from provider_prompt import ProviderOutputContext

INSTANT='2026-10-23T10:05:00Z'


def fixture(tmp_path,monkeypatch):
    request,root_selection=base(tmp_path)
    root=Path(root_selection.work_item);(root/'status.md').write_text(quick_status())
    child=root.parent/'child-lane';child.mkdir();(child/'status.md').write_text(quick_status())
    req=runtime.prepare_codex_request(replace(request,work_item_id=child.name,cwd=str(child),role='consultant',result_kind='task',coordinator_binding='child-coordinator'))
    selections={'task-one':replace(root_selection,work_item=str(child))}
    requests={'task-one':req}
    root_owner=SimpleNamespace(resolve=lambda i:requests[i],assert_current=lambda r,e:None)
    assignment=runtime.publish_child_assignment(root_selection=root_selection,root_authority=root_owner,selections=selections,
        child_id='child-grant',coordinator_binding=req.coordinator_binding,scope=req.scope,required_request_ids=('task-one',),
        lifecycle_permissions=('delegate','finish','cancel','delegate-child'),artifact='child-assignment.json',started_at=INSTANT)
    authority=runtime.ChildLeadAuthority(root_authority=root_owner,root_selection=root_selection,child_id=assignment.child_id,
        selections=selections,closure_data=closure(INSTANT).encode(),terminal_instant=INSTANT,repository_root=tmp_path)
    return authority,assignment,requests,selections,root_selection


def test_root_grant_is_durable_and_catalog_changes_rejected(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    assert assignment.task_depth==1 and assignment.request_ids==('task-one',)
    owner.assert_child_current(assignment,'delegate')
    assert owner.resolve('task-one')==requests['task-one']
    requests['task-one']=replace(requests['task-one'],prompt='unadmitted')
    with pytest.raises(ValueError,match='catalog_changed'):owner.resolve('task-one')


def test_revocation_is_durable_before_any_more_delegation(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    asyncio.run(owner.cancel_child(assignment))
    with pytest.raises(ValueError,match='cancelled'):owner.resolve('task-one')


def test_actual_received_child_task_archives_only_child_and_recovers_result(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    req=requests['task-one'];selection=selections['task-one']
    selected=runtime.claim_launch(req,selection,authority=owner.assert_current,started_at=INSTANT)
    run=runtime.RuntimeRun(req,selected,ProviderOutputContext(()),observed(monkeypatch,req,selected))
    terminal=receiving.receive_runtime_run(run,artifact='task.json',started_at=INSTANT,updated_at=INSTANT)
    assert owner.completed_requests(assignment)['task-one']==terminal
    assert owner.received_context(assignment)['task-one']['artifact']['task']['role']=='consultant'
    write_empty_bug_dispositions(tmp_path,'child-lane',INSTANT)
    archived=owner.receive_child_result(assignment)
    assert Path(archived).is_dir() and 'archive' in Path(archived).parts
    assert Path(root.work_item).is_dir()
    assert not Path(assignment.child_work_item).exists()


def test_revoked_assignment_reloads_and_cancellation_drains_again(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    first=asyncio.run(owner.cancel_child(assignment))
    second=asyncio.run(owner.cancel_child(assignment))
    assert first==second=={'status':'revoked','receipts':{}}
    assert owner.resolve_child(assignment.child_id)==assignment
    with pytest.raises(ValueError,match='cancelled'):owner.assert_child_current(assignment,'child_model')
    events=runtime._events(root)[2]
    assert sum(row['runId']=='child-grant-cancel' for row in events)==1


def test_wrong_repository_cannot_close_same_slug(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    other=tmp_path/'other';other.mkdir()
    fake=other/'work-items'/'active'/'child-lane';fake.mkdir(parents=True)
    (fake/'status.md').write_text(quick_status())
    with pytest.raises(ValueError,match='repository_identity'):
        runtime.ChildLeadAuthority(root_authority=owner._root_authority,root_selection=root,child_id=assignment.child_id,
            selections=selections,closure_data=closure(INSTANT).encode(),terminal_instant=INSTANT,repository_root=other)
    assert fake.exists() and Path(assignment.child_work_item).exists()


def test_unstarted_then_uncertain_task_is_not_completed_or_replayable(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    assert owner.completed_requests(assignment)==owner.attempted_requests(assignment)=={}
    request=requests['task-one'];selection=selections['task-one']
    runtime.claim_launch(request,selection,authority=owner.assert_current,started_at=INSTANT)
    assert list(owner.attempted_requests(assignment))==['task-one']
    assert owner.completed_requests(assignment)=={}
    with pytest.raises(ValueError,match='pending'):owner.receive_child_result(assignment)
    with pytest.raises(ValueError):runtime.claim_launch(request,selection,authority=owner.assert_current,started_at=INSTANT)


def test_existing_invalid_ledger_is_not_treated_as_unstarted(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    (Path(assignment.child_work_item)/'agent-runs.jsonl').write_text('not-json')
    with pytest.raises(ValueError):owner.attempted_requests(assignment)


def test_decision_worker_requires_exact_scoped_authority(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='decision_authority'):
        owner.attach_decision_worker(assignment,SimpleNamespace(_authority=owner), '{}')


def test_assignment_artifact_tamper_prevents_current_authority(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    (Path(root.work_item)/'child-assignment.json').write_text('{}')
    with pytest.raises(ValueError,match='changed|current_ledger_invalid'):owner.resolve_child(assignment.child_id)


def test_nested_depth_is_derived_and_parent_revocation_blocks_subtree(tmp_path,monkeypatch):
    owner,parent,requests,selections,root=fixture(tmp_path,monkeypatch)
    child=Path(parent.child_work_item).parent/'nested-lane';child.mkdir();(child/'status.md').write_text(quick_status())
    req=replace(requests['task-one'],work_item_id=child.name,cwd=str(child),coordinator_binding='nested-coordinator',
        external_dispatch_id='nested-dispatch',external_evidence_run_id='nested-evidence')
    requests['nested-task']=req
    nested=runtime.publish_child_assignment(root_selection=root,root_authority=owner._root_authority,
        selections={'nested-task':replace(selections['task-one'],work_item=str(child))},child_id='nested-grant',
        coordinator_binding=req.coordinator_binding,scope=req.scope,required_request_ids=('nested-task',),
        lifecycle_permissions=('delegate','finish','cancel'),artifact='nested-assignment.json',started_at=INSTANT,
        parent_child_id=parent.child_id,max_task_depth=2)
    assert nested.task_depth==2 and nested.parent_child_id==parent.child_id
    asyncio.run(owner.cancel_child(parent))
    with pytest.raises(ValueError,match='cancelled'):runtime._load_child_assignment(root,nested.child_id)
    assert runtime._load_child_assignment(root,nested.child_id,allow_cancelled=True)==nested
    nested_owner=runtime.ChildLeadAuthority(root_authority=owner._root_authority,root_selection=root,child_id=nested.child_id,
        selections={'nested-task':replace(selections['task-one'],work_item=str(child))},closure_data=closure(INSTANT).encode(),
        terminal_instant=INSTANT,repository_root=tmp_path)
    assert asyncio.run(nested_owner.cancel_child(nested))['status']=='revoked'
    assert asyncio.run(nested_owner.cancel_child(nested))['status']=='revoked'


def test_another_grant_cannot_take_same_child_scope(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    with pytest.raises(ValueError,match='already_assigned'):
        runtime.publish_child_assignment(root_selection=root,root_authority=owner._root_authority,selections=selections,
            child_id='second-grant',coordinator_binding=assignment.coordinator_binding,scope=assignment.scope,
            required_request_ids=assignment.required_request_ids,lifecycle_permissions=assignment.lifecycle_permissions,
            artifact='second-assignment.json',started_at=INSTANT)


def test_cancellation_owner_failure_does_not_stop_other_drain(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    calls=[]
    async def failed(run):
        calls.append('first')
        raise RuntimeError('fixture cancellation failed')
    async def drained(run):
        calls.append('second')
        return {'requested':True,'acknowledged':True}
    requests['decision-test']=replace(requests['task-one'],external_dispatch_id='decision-test')
    # Isolated cancellation owner test; no execution/admission bypass is exercised.
    owner._executors={'task-one':SimpleNamespace(cancel=failed)}
    owner._decision_workers={'decision-test':SimpleNamespace(cancel=drained)}
    owner._executor_requests={'task-one':requests['task-one']}
    owner._decision_requests={'decision-test':requests['decision-test']}
    requests.clear()  # Root revocation/removal must not prevent stopping owned work.
    result=asyncio.run(owner.cancel_child(assignment))
    assert calls==['first','second'] and result['status']=='revoked'
    assert result['receipts']['task-one']['acknowledged'] is False
    assert result['receipts']['decision-test']['acknowledged'] is True


def decision_fixture(owner,assignment,requests,selections,process,secret=None):
    import hashlib,time
    from sdk_execution.coordination import CoordinationInferenceRequest,child_coordination_payload
    from sdk_execution.contracts import json_text
    from provider_prompt import assemble_external_prompt
    task=requests['task-one'];system='Choose scoped work.'
    projection=json_text({'assignment_sha256':assignment.assignment_sha256,
        'catalog':[{'request_id':'task-one','request_sha256':dict(assignment.catalog)['task-one'],
            'role':task.role,'scope':list(task.scope),'prompt':task.prompt}],
        'required_request_ids':['task-one'],'completed_request_ids':[],
        'received_results':[],'unavailable_results':[]})
    if secret:
        data=json.loads(projection);data['unavailable_results']=[{'request_id':'task-one','result':{'note':secret}}]
        projection=json_text(data)
    key='decision-test'
    values={**task.to_dict(),'scope':task.scope,'role':'lead','result_kind':'review',
        'external_dispatch_id':key+'-dispatch','external_evidence_run_id':key+'-evidence','artifact_id':key,
        'prompt':assemble_external_prompt(child_coordination_payload(key,system,projection).encode()).decode(),
        'operation_id':key,'admitted_request_id':assignment.child_id,'outer_budget_id':key+'-outer','inner_budget_id':key+'-inner',
        'inner_request_sha256':hashlib.sha256(projection.encode()).hexdigest(),'system_instructions':system,'child_choice_json':projection}
    requests[key]=CoordinationInferenceRequest(**values)
    worker=runtime.SdkCoordinationWorker(request_id=key,authority=owner,
        selection=replace(selections['task-one'],config_overrides=runtime.CODEX_BOUNDED_REVIEW_OVERRIDES),
        process_owner=process,source_environment={},artifact='decision-test.json',deadline_monotonic=time.monotonic()+300,
        cancellation_probe=lambda:False,started_at=INSTANT)
    return worker,projection,requests[key]


def test_real_decision_registration_scans_projection_before_any_effect(tmp_path,monkeypatch):
    from process_supervision.process_runner import ProcessRunnerV1
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    secret='fixture-'+__import__('uuid').uuid4().hex
    monkeypatch.setattr(runtime,'prepare_environment',lambda *a:({},ProviderOutputContext((secret.encode(),))))
    with ProcessRunnerV1() as process:
        worker,projection,request=decision_fixture(owner,assignment,requests,selections,process,secret)
        with pytest.raises(ValueError,match='E_EXTERNAL_PROVIDER'):
            owner.attach_decision_worker(assignment,worker,projection)
        assert not owner._decision_workers and worker.runtime_run is None
        assert not (Path(assignment.child_work_item)/'agent-runs.jsonl').exists()


def test_registered_decision_rechecks_its_own_root_grant_per_effect(tmp_path,monkeypatch):
    from process_supervision.process_runner import ProcessRunnerV1
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(runtime,'prepare_environment',lambda *a:({},ProviderOutputContext(())))
    with ProcessRunnerV1() as process:
        worker,projection,request=decision_fixture(owner,assignment,requests,selections,process)
        owner.attach_decision_worker(assignment,worker,projection)
        def current(req,effect):
            if req==request:raise ValueError('decision revoked')
        owner._root_authority.assert_current=current
        with pytest.raises(ValueError,match='revoked'):owner.assert_current(request,'turn_start')
        owner.assert_current(requests['task-one'],'turn_start')
        assert worker.runtime_run is None


def test_root_selected_source_path_is_not_mistaken_for_output_echo(tmp_path,monkeypatch):
    from process_supervision.process_runner import ProcessRunnerV1
    owner,assignment,requests,selections,root=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(runtime,'prepare_environment',lambda *a:({},ProviderOutputContext(())))
    with ProcessRunnerV1() as process:
        worker,projection,request=decision_fixture(owner,assignment,requests,selections,process)
        # The admitted catalog is source context, not a model output channel.
        data=json.loads(projection);data['catalog'][0]['prompt']='Inspect C:/Users/example/project/file.py'
        from sdk_execution.contracts import json_text
        projection=json_text(data)
        from sdk_execution.coordination import child_coordination_payload
        from provider_prompt import assemble_external_prompt
        prompt=assemble_external_prompt(child_coordination_payload(request.operation_id,request.system_instructions,projection).encode()).decode()
        request=replace(request,child_choice_json=projection,prompt=prompt)
        requests['decision-test']=request
        owner.attach_decision_worker(assignment,worker,projection)
        assert worker.runtime_run is None


@pytest.mark.parametrize('version,operation,digest_name',[(3,'coordination-inference','innerRequestSha256'),(5,'scoped-child-coordination','childChoiceSha256')])
def test_coordination_schema_and_owner_pair_operation_kind(version,operation,digest_name):
    schema=json.loads((Path(__file__).parents[1]/'shared/schemas/agent-runs.schema.json').read_text())['properties']['sdkExecution']
    branch=next(b for b in schema['oneOf'] if b['properties']['schemaVersion']['const']==version)
    assert branch['properties']['operationKind']=={'const':operation}
    value={'schemaVersion':version,'adapter':'openai-codex','model':'fixture-model','effort':'high',
        'sandboxMode':'read-only','approvalPolicy':'deny_all','accountBinding':'fixture-account','requestSha256':'a'*64,
        'operationKind':operation,digest_name:'b'*64,'outerBudgetBinding':'outer','innerBudgetBinding':'inner'}
    validator=runtime._owner()._ledger_owner().load_validator()
    assert validator.validate_sdk_execution(value,provider='codex',model='fixture-model',effort='high')==value
    crossed={**value,'operationKind':'scoped-child-coordination' if version==3 else 'coordination-inference'}
    with pytest.raises(ValueError):validator.validate_sdk_execution(crossed,provider='codex',model='fixture-model',effort='high')

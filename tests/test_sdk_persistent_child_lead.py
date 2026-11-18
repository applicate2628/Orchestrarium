"""Canonical persistent child receipts and restore; no native providers run."""
import json,time,hashlib
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import pytest
from test_sdk_child_lead_authority import fixture,INSTANT
from sdk_execution import runtime,receiving
from sdk_execution.contracts import json_text
from sdk_execution.coordination import CoordinationInferenceRequest,CoordinationInferenceResult,child_coordination_payload,child_choice_sha256
from process_supervision import process_runner as processes,sdk_worker
from sdk_execution.worker import encode_frame
from provider_prompt import ProviderOutputContext,assemble_external_prompt


def persistent_fixture(tmp_path,monkeypatch,*,extra_task=False):
    publish=runtime.publish_child_assignment
    def publish_scoped(**kw):
        if extra_task:
            root=kw['root_authority'];original=root.resolve
            other=replace(original('task-one'),external_dispatch_id='task-two-dispatch',external_evidence_run_id='task-two-evidence',artifact_id='task-two')
            root.resolve=lambda key:other if key=='task-two' else original(key)
            kw['selections']['task-two']=kw['selections']['task-one']
        return publish(**kw,decision_session_mode='native-persistent')
    with patch.object(runtime,'publish_child_assignment',side_effect=publish_scoped):
        values=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(runtime,'prepare_environment',lambda *a:({},ProviderOutputContext(())))
    return values


def candidate(owner,assignment,requests,selections,process,key='decision-one',projection=None,**changes):
    task=requests['task-one'];selection=replace(selections['task-one'],config_overrides=runtime.CODEX_BOUNDED_REVIEW_OVERRIDES)
    if projection is None:
        projection=json_text({'assignment_sha256':assignment.assignment_sha256,'catalog':[
            {'request_id':'task-one','request_sha256':hashlib.sha256(json_text(task.to_dict()).encode()).hexdigest(),
             'role':task.role,'scope':list(task.scope),'prompt':task.prompt}],
            'required_request_ids':['task-one'],'completed_request_ids':[],'received_results':[],'unavailable_results':[]})
    system='Choose scoped work.'
    values={**task.to_dict(),'scope':task.scope,'role':'lead','result_kind':'review','decision_session_mode':'native-persistent',
        'external_dispatch_id':key+'-dispatch','external_evidence_run_id':key+'-evidence','artifact_id':key,
        'prompt':assemble_external_prompt(child_coordination_payload(key,system,projection).encode()).decode(),
        'operation_id':key,'admitted_request_id':assignment.child_id,'outer_budget_id':key+'-outer','inner_budget_id':key+'-inner',
        'inner_request_sha256':hashlib.sha256(projection.encode()).hexdigest(),'system_instructions':system,'child_choice_json':projection,**changes}
    request=CoordinationInferenceRequest(**values)
    request=owner.prepare_child_decision(assignment,request,selection)
    requests[key]=request
    worker=runtime.SdkCoordinationWorker(request_id=key,authority=owner,selection=selection,process_owner=process,
        source_environment={},artifact=key+'.json',deadline_monotonic=time.monotonic()+600,
        cancellation_probe=lambda:False,started_at=INSTANT)
    return worker,request,projection


def receive_decision(owner,assignment,requests,selections,process,monkeypatch,key='decision-one',**result_changes):
    worker,request,projection=candidate(owner,assignment,requests,selections,process,key)
    owner.attach_decision_worker(assignment,worker,projection)
    selected=runtime.claim_launch(request,worker._selection,authority=owner.assert_current,started_at=INSTANT)
    reported={k:v for k,v in runtime.selected_sdk_execution(request,selected).items() if k in
        {'adapter','model','effort','sandboxMode','approvalPolicy','accountBinding','continuationSourceSha256'}}
    reported.update(schemaVersion=1,sdkVersion='fixture',runtimeVersion='fixture')
    intent=json_text({'operation_id':request.operation_id,'child_choice_sha256':child_choice_sha256(projection),'action':'execute','request_id':'task-one'})
    values=dict(request=request,status='completed',provider_status='completed',intent_json=intent,
        native_thread_id='persistent-thread',native_turn_id='turn-one',sdk_execution_json=json_text(reported),protocol_closed=True)
    values.update(result_changes);result=CoordinationInferenceResult(**values)
    def simulated_run(pr,*,dialogue):
        frames=iter([encode_frame({'kind':'coordination_result','result':result.to_dict()})])
        class Channel:
            def write_line(self,value):pass
            def read_line(self):
                try:return next(frames)
                except StopIteration:raise EOFError()
        dialogue.handler(Channel())
        failed=processes._request_failure(pr,processes.ProcessSupervisionError('PSV1-INTERNAL','execution'),time.monotonic())
        return replace(failed,outcome='success',terminal_stage='completed',failure_id=None,target_exit_code=0,
            resources_closed=True,policy_id='sdk-worker-v1',tree=processes.TreeObservationV1('synthetic',True,'EMPTY',True,True,True,True))
    with patch.object(process,'run',side_effect=simulated_run):
        observation=sdk_worker.run_sdk_worker(process,request,environment=(),deadline_monotonic=time.monotonic()+600,
            job_memory_limit_bytes=selected.job_memory_limit_bytes,cancellation_probe=lambda:False,
            runtime_selection=selected.to_dict(),authority=lambda *a:None)
    run=runtime.RuntimeRun(request,selected,ProviderOutputContext(()),observation)
    terminal=receiving.receive_runtime_run(run,artifact=key+'.json',started_at=INSTANT,updated_at=INSTANT)
    return run,terminal,projection


def test_durable_receipt_binds_context_and_recovers_pending_intent_without_new_claim(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=persistent_fixture(tmp_path,monkeypatch)
    with processes.ProcessRunnerV1() as process:
        prior,terminal,projection=receive_decision(owner,assignment,requests,selections,process,monkeypatch)
        worker,request,_=candidate(owner,assignment,requests,selections,process,'decision-two',projection)
        assert request.native_continuation.native_thread_id=='persistent-thread'
        intent=owner.recover_child_decision(assignment,worker,projection)
        assert intent['request_id']=='task-one'
        assert len(runtime._events(worker._selection)[2])==2
        owner.attach_decision_worker(assignment,worker,projection)
        with pytest.raises(ValueError,match='intent_pending'):
            runtime.claim_launch(request,worker._selection,authority=owner.assert_current,started_at=INSTANT)
        assert len(runtime._events(worker._selection)[2])==2


@pytest.mark.parametrize('field,value',[('model','other-model'),('account_binding','other-context'),('scope',('other-scope',))])
def test_receipt_does_not_grant_changed_native_context(tmp_path,monkeypatch,field,value):
    owner,assignment,requests,selections,root=persistent_fixture(tmp_path,monkeypatch)
    with processes.ProcessRunnerV1() as process:
        receive_decision(owner,assignment,requests,selections,process,monkeypatch)
        with pytest.raises(ValueError):candidate(owner,assignment,requests,selections,process,'decision-two',**{field:value})


def test_uncertain_decision_cannot_create_another_thread(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=persistent_fixture(tmp_path,monkeypatch)
    with processes.ProcessRunnerV1() as process:
        worker,request,projection=candidate(owner,assignment,requests,selections,process)
        owner.attach_decision_worker(assignment,worker,projection)
        runtime.claim_launch(request,worker._selection,authority=owner.assert_current,started_at=INSTANT)
        with pytest.raises(ValueError):candidate(owner,assignment,requests,selections,process,'decision-two')
        assert len(runtime._events(worker._selection)[2])==1


def test_changed_artifact_never_supplies_native_ids(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=persistent_fixture(tmp_path,monkeypatch)
    with processes.ProcessRunnerV1() as process:
        receive_decision(owner,assignment,requests,selections,process,monkeypatch)
        (Path(assignment.child_work_item)/'decision-one.json').write_text('{}')
        with pytest.raises(ValueError):candidate(owner,assignment,requests,selections,process,'decision-two')


def test_unrelated_task_attempt_does_not_block_received_pending_choice(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=persistent_fixture(tmp_path,monkeypatch,extra_task=True)
    with processes.ProcessRunnerV1() as process:
        _,terminal,projection=receive_decision(owner,assignment,requests,selections,process,monkeypatch)
        other=owner.resolve('task-two')
        runtime.claim_launch(other,selections['task-two'],authority=owner.assert_current,started_at=INSTANT)
        changed=json.loads(projection)
        changed['catalog'].append({'request_id':'task-two','request_sha256':hashlib.sha256(json_text(other.to_dict()).encode()).hexdigest(),
            'role':other.role,'scope':list(other.scope),'prompt':other.prompt})
        changed['unavailable_results']=[{'request_id':'task-two','result':owner.attempted_requests(assignment)['task-two']}]
        changed=json_text(changed)
        worker,request,_=candidate(owner,assignment,requests,selections,process,'decision-two',changed)
        assert child_choice_sha256(changed)!=terminal['sdkExecution']['childChoiceSha256']
        assert owner.recover_child_decision(assignment,worker,changed)['request_id']=='task-one'


def test_failed_decision_keeps_evidence_but_cannot_resume_or_fallback(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=persistent_fixture(tmp_path,monkeypatch)
    with processes.ProcessRunnerV1() as process:
        _,terminal,_=receive_decision(owner,assignment,requests,selections,process,monkeypatch,
            status='failed',provider_status='failed',execution_error='fixture native failure')
        assert terminal['status']=='blocked'
        document=json.loads((Path(assignment.child_work_item)/'decision-one.json').read_text())
        assert 'native_continuation' not in document
        assert document['evidence']['native_thread_id']=='persistent-thread'
        with pytest.raises(ValueError):candidate(owner,assignment,requests,selections,process,'decision-two')
        with pytest.raises(ValueError,match='mode_changed'):
            candidate(owner,assignment,requests,selections,process,'decision-three',decision_session_mode='fresh-handoff')


def test_completed_response_on_wrong_native_thread_is_nonresumable(tmp_path,monkeypatch):
    owner,assignment,requests,selections,root=persistent_fixture(tmp_path,monkeypatch)
    with processes.ProcessRunnerV1() as process:
        receive_decision(owner,assignment,requests,selections,process,monkeypatch)
        runtime.claim_launch(owner.resolve('task-one'),selections['task-one'],authority=owner.assert_current,started_at=INSTANT)
        _,terminal,_=receive_decision(owner,assignment,requests,selections,process,monkeypatch,key='decision-two',
            native_thread_id='unexpected-thread',native_turn_id='turn-two')
        assert terminal['status']=='blocked'
        assert 'native_continuation' not in json.loads((Path(assignment.child_work_item)/'decision-two.json').read_text())
        with pytest.raises(ValueError):candidate(owner,assignment,requests,selections,process,'decision-three')


def test_new_python_process_restores_received_decision_without_observation_cache(tmp_path,monkeypatch):
    import os,subprocess,sys,textwrap
    owner,assignment,requests,selections,root=persistent_fixture(tmp_path,monkeypatch)
    with processes.ProcessRunnerV1() as process:
        receive_decision(owner,assignment,requests,selections,process,monkeypatch)
    payload={'root':root.to_dict(),'selection':selections['task-one'].to_dict(),'task':requests['task-one'].to_dict(),
        'child_id':assignment.child_id,'repository_root':str(tmp_path),'closure':owner._closure_data.decode()}
    code=textwrap.dedent("""
        import json,sys
        from types import SimpleNamespace
        from sdk_execution import runtime
        from sdk_execution.contracts import ExecutionRequest
        from provider_prompt import ProviderOutputContext
        from test_sdk_persistent_child_lead import candidate,INSTANT
        from process_supervision.process_runner import ProcessRunnerV1
        data=json.load(sys.stdin)
        root=runtime.CodexRuntimeSelection.from_dict(data['root'])
        selection=runtime.CodexRuntimeSelection.from_dict(data['selection'])
        requests={'task-one':ExecutionRequest.from_dict(data['task'])}
        authority=SimpleNamespace(resolve=lambda key:requests[key],assert_current=lambda request,effect:None)
        owner=runtime.ChildLeadAuthority(root_authority=authority,root_selection=root,child_id=data['child_id'],
            selections={'task-one':selection},closure_data=data['closure'].encode(),terminal_instant=INSTANT,repository_root=data['repository_root'])
        assignment=owner.resolve_child(data['child_id'])
        runtime.prepare_environment=lambda *args:({},ProviderOutputContext(()))
        with ProcessRunnerV1() as process:
            worker,request,projection=candidate(owner,assignment,requests,{'task-one':selection},process,'restored-decision')
            intent=owner.recover_child_decision(assignment,worker,projection)
            print(json.dumps({'thread':request.native_continuation.native_thread_id,'turn':request.native_continuation.native_turn_id,
                'action':intent['action'],'request_id':intent['request_id'],'native_run':worker.runtime_run}))
    """)
    repo=Path(__file__).resolve().parents[1]
    env=dict(os.environ);env['PYTHONDONTWRITEBYTECODE']='1'
    env['PYTHONPATH']=os.pathsep.join((str(repo/'scripts'),str(repo/'tests'),env.get('PYTHONPATH','')))
    result=subprocess.run([sys.executable,'-c',code],input=json.dumps(payload),text=True,capture_output=True,cwd=repo,env=env)
    assert result.returncode==0,result.stderr
    assert json.loads(result.stdout)=={'thread':'persistent-thread','turn':'turn-one','action':'execute','request_id':'task-one','native_run':None}

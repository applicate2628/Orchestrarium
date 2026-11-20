"""Actual Root artifacts/ledger/CLI; no native agent invocation or fabricated receipt."""
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from test_agent_run_ledger import prepare_valid_work_item
from test_mutate_work_item import quick_status
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"scripts"))
from sdk_execution import native_binding as native

INSTANT="2026-11-18T15:00:00Z"


def setup(tmp_path):
    item=prepare_valid_work_item(tmp_path)
    (item/'status.md').write_text(quick_status())
    context=native.NativeBindingContext(str(item))
    assignment={'schema_version':1,'kind':'native-child-assignment','assignment_id':'native-research',
        'provider':'antigravity','parent_conversation_id':'parent-session','role':'researcher',
        'scope':['source analysis'],'task':'Inspect the admitted source without modification.',
        'expected_artifact':'research.md','acceptance':'Root independently verifies cited source evidence.'}
    return context,assignment


def attach(context,prepared,**changes):
    values=dict(assignment_sha256=prepared['assignment_sha256'],child_conversation_id='child-session',
        evidence_reference='Root observed the child session in the native UI',started_at=INSTANT)
    values.update(changes)
    return native.bind(context,prepared['assignment']['assignment_id'],**values)


def test_prepare_bind_restart_and_identical_retry(tmp_path):
    context,assignment=setup(tmp_path)
    first=native.prepare(context,assignment,started_at=INSTANT)
    assert first['status']=='prepared-unbound' and first['binding'] is None
    second=attach(context,first)
    assert second['status']=='root-bound'
    assert not second['authorizing'] and not second['native_execution_verified'] and not second['completion_verified']
    image=(Path(context.work_item)/'agent-runs.jsonl').read_bytes()
    restored=native.NativeBindingContext(context.work_item)
    assert native.readback(restored,assignment['assignment_id'])==second
    assert attach(restored,first)==second
    assert native.prepare(restored,assignment,started_at=INSTANT)==second
    assert (Path(context.work_item)/'agent-runs.jsonl').read_bytes()==image
    rows=[json.loads(line) for line in image.splitlines()]
    assert len(rows)==2 and all(row['eventKind']=='standalone' and row['gate']=='none' and 'authorizing' not in row and 'closesRunIds' not in row for row in rows)
    assert all('sdkExecution' not in row and 'launchRunId' not in row for row in rows)


@pytest.mark.parametrize('change', ['hash','parent','conflict','tamper','unknown'])
def test_invalid_native_associations_do_not_append(tmp_path,change):
    context,assignment=setup(tmp_path);prepared=native.prepare(context,assignment,started_at=INSTANT)
    kwargs={}
    if change=='hash': kwargs['assignment_sha256']='0'*64
    if change=='parent': kwargs['child_conversation_id']='parent-session'
    if change=='conflict':
        attach(context,prepared);kwargs['child_conversation_id']='another-child'
    if change=='tamper':
        rows=native._rows(context)
        (Path(context.work_item)/rows[0]['artifact']).write_text('{}')
    image=(Path(context.work_item)/'agent-runs.jsonl').read_bytes()
    with pytest.raises(ValueError):
        if change=='unknown':native.bind(context,'unknown',assignment_sha256='0'*64,child_conversation_id='child',evidence_reference='untrusted hook',started_at=INSTANT)
        else:attach(context,prepared,**kwargs)
    assert (Path(context.work_item)/'agent-runs.jsonl').read_bytes()==image


def test_explicit_retry_receives_identical_orphan_without_launch(tmp_path,monkeypatch):
    context,assignment=setup(tmp_path)
    writer,_,_=native._ledger(context)
    append=writer._append_event_transaction
    def fail_after_artifact(item,validator,factory,**kwargs):
        factory('')
        raise OSError('synthetic failure before ledger publication')
    monkeypatch.setattr(writer,'_append_event_transaction',fail_after_artifact)
    with pytest.raises(OSError):native.prepare(context,assignment,started_at=INSTANT)
    assert not (Path(context.work_item)/'agent-runs.jsonl').exists()
    monkeypatch.setattr(writer,'_append_event_transaction',append)
    recovered=native.prepare(context,assignment,started_at=INSTANT)
    assert recovered['status']=='prepared-unbound'
    assert len(native._rows(context))==1


def test_public_cli_prepare_bind_and_new_process_readback(tmp_path):
    context,assignment=setup(tmp_path)
    source=tmp_path/'assignment-input.json';source.write_text(json.dumps(assignment))
    scripts=Path(__file__).resolve().parents[1]/'scripts'
    env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1',PYTHONPATH=str(scripts)+os.pathsep+os.environ.get('PYTHONPATH',''))
    def command(*args):
        result=subprocess.run([sys.executable,str(scripts/'sdk_execution/native_binding.py'),'--work-item',context.work_item,*args],cwd=scripts,env=env,text=True,capture_output=True)
        assert result.returncode==0,result.stderr+result.stdout
        return json.loads(result.stdout.splitlines()[-1])
    prepared=command('prepare','--assignment-file',str(source),'--started-at',INSTANT)
    bound=command('bind','--assignment-id',assignment['assignment_id'],'--assignment-sha256',prepared['assignment_sha256'],
        '--child-conversation-id','native-observed-child','--evidence-reference','Root native UI observation','--started-at',INSTANT)
    assert command('readback','--assignment-id',assignment['assignment_id'])==bound
    assert bound['status']=='root-bound' and bound['completion_verified'] is False


@pytest.mark.parametrize("field,value", [("scope", ["different association"]), ("executionRole", "subagent")])
def test_readback_rejects_changed_ledger_tuple(tmp_path,field,value):
    context,assignment=setup(tmp_path)
    native.prepare(context,assignment,started_at=INSTANT)
    path=Path(context.work_item)/'agent-runs.jsonl'
    rows=[json.loads(line) for line in path.read_text().splitlines()]
    rows[0][field]=value
    path.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    with pytest.raises(ValueError):native.readback(context,assignment['assignment_id'])


def test_binding_does_not_settle_existing_execution_or_close_work_item(tmp_path):
    from test_sdk_runtime import fixture as sdk_fixture
    from sdk_execution import runtime
    request,selection=sdk_fixture(tmp_path)
    item=Path(selection.work_item)
    (item/'status.md').write_text(quick_status())
    selected=runtime.claim_launch(request,selection,authority=lambda req,effect:None,started_at=INSTANT)
    status=(item/'status.md').read_bytes()
    context=native.NativeBindingContext(str(item))
    assignment={'schema_version':1,'kind':'native-child-assignment','assignment_id':'native-research',
        'provider':'antigravity','parent_conversation_id':'parent-session','role':'researcher',
        'scope':['source analysis'],'task':'Inspect the admitted source.',
        'expected_artifact':'research.md','acceptance':'Root checks evidence.'}
    prepared=native.prepare(context,assignment,started_at=INSTANT)
    attach(context,prepared)
    rows=native._rows(context)
    original=[row for row in rows if row['runId']==request.external_dispatch_id]
    assert len(original)==1 and original[0]['eventKind']=='launch' and original[0]['status']=='running'
    assert not any(row.get('launchRunId')==request.external_dispatch_id for row in rows)
    assert not any(row.get('gate')=='PASS' for row in rows)
    assert (item/'status.md').read_bytes()==status and item.is_dir()
    assert not (item/'closure.md').exists()
    runtime.assert_current_launch(request,selected,'native_binding_did_not_settle_task')


def test_oversized_orphan_rejected_before_unbounded_read(tmp_path,monkeypatch):
    context,assignment=setup(tmp_path)
    target=Path(context.work_item)/(native._key(assignment['assignment_id'],'assignment')+'.json')
    expected=(native.json_text(assignment)+'\n').encode()
    target.write_bytes(expected+b' ')
    original=Path.read_bytes
    def deny_unbounded(path):
        if path==target: raise AssertionError('orphan must use bounded artifact reader')
        return original(path)
    monkeypatch.setattr(Path,'read_bytes',deny_unbounded)
    with pytest.raises(ValueError):native.prepare(context,assignment,started_at=INSTANT)
    assert not (Path(context.work_item)/'agent-runs.jsonl').exists()
    assert target.stat().st_size==len(expected)+1


def test_concurrent_different_children_keep_single_binding_and_running_task(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier
    from test_sdk_runtime import fixture as sdk_fixture
    from sdk_execution import runtime
    request,selection=sdk_fixture(tmp_path)
    item=Path(selection.work_item)
    (item/'status.md').write_text(quick_status())
    selected=runtime.claim_launch(request,selection,authority=lambda req,effect:None,started_at=INSTANT)
    context=native.NativeBindingContext(str(item))
    assignment={'schema_version':1,'kind':'native-child-assignment','assignment_id':'native-race',
        'provider':'antigravity','parent_conversation_id':'parent-session','role':'researcher',
        'scope':['source analysis'],'task':'Inspect the admitted source.',
        'expected_artifact':'research.md','acceptance':'Root checks evidence.'}
    prepared=native.prepare(context,assignment,started_at=INSTANT)
    barrier=Barrier(2)
    def attempt(child):
        barrier.wait()
        try:return attach(context,prepared,child_conversation_id=child)
        except ValueError as exc:return str(exc)
    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes=list(pool.map(attempt,['first-child','second-child']))
    successes=[v for v in outcomes if isinstance(v,dict)]
    assert len(successes)==1
    assert [v for v in outcomes if isinstance(v,str)]==['native_binding_conflict']
    assert native.readback(context,assignment['assignment_id'])==successes[0]
    rows=native._rows(context)
    assert len(rows)==3
    assert sum(row['runId']==native._key(assignment['assignment_id'],'binding') for row in rows)==1
    assert not any(row.get('launchRunId')==request.external_dispatch_id for row in rows)
    runtime.assert_current_launch(request,selected,'concurrent_binding_did_not_settle_task')

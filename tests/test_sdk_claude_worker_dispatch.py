"""Public Claude Worker dispatch; offline native-shaped fixtures, no model."""
from dataclasses import replace
import json
from pathlib import Path
import pytest
from test_sdk_claude_dispatch import fixture as task_fixture, owner, dispatch, runtime, binding


def fixture(tmp_path,monkeypatch,role='backend-engineer'):
    selected,path,env,mutable=task_fixture(tmp_path,monkeypatch)
    selected.control.ledger_role=role
    selected=replace(selected,role_provenance=owner.external_role_provenance(selected.control,'claude'))
    codex_capture=tmp_path/'codex-capture';codex_capture.mkdir()
    monkeypatch.setenv('CODEX_PROMPTS_DIR',str(codex_capture))
    workspace=tmp_path/'workspace';workspace.mkdir()
    install=tmp_path/'install';install.mkdir()
    executable=install/'fixture.exe';executable.write_bytes(b'never execute')
    monkeypatch.setattr(owner,'_resolve_launch_provider_command',lambda *a:([str(executable)],None))
    monkeypatch.setattr(runtime,'_worker_authority_roots',lambda provider='codex':(tmp_path/'authority',))
    monkeypatch.chdir(workspace)
    data=dict(binding(),schemaVersion=4,installedHookRoot=None,contextMode='fresh',contextHandoff=None,writeWorkspace=str(workspace))
    path.write_text(json.dumps(data))
    return selected,path,env,mutable


def prepare(tmp_path,monkeypatch,**kw):
    selected,path,env,mutable=fixture(tmp_path,monkeypatch,**kw)
    op=dispatch.prepare_dispatch(selected,path,provider='claude',source_environment=env,cancellation_probe=lambda:False)
    return op,mutable


def bind_capture(op):
    child=Path(op.selection.prompts_dir)/'run';child.mkdir()
    op.bind_capture_directory(child)


def test_explicit_write_binding_keeps_worker_scope(tmp_path,monkeypatch):
    op,_=prepare(tmp_path,monkeypatch)
    assert op.request.write_workspace==op.request.cwd and op.request.tool_profile=='default'
    assert op.request.result_kind=='task' and runtime.execution_role(op.request)=='external-worker'
    assert runtime.selected_sdk_execution(op.request,op.selection)['sandboxMode']=='tool-restricted-workspace-write'
    assert op._capture_root==Path(op.selection.prompts_dir)


@pytest.mark.parametrize('role',['consultant','qa-engineer'])
def test_readonly_role_cannot_gain_write_scope(tmp_path,monkeypatch,role):
    with pytest.raises(ValueError):prepare(tmp_path,monkeypatch,role=role)


def test_read_selector_cannot_gain_write_scope(tmp_path,monkeypatch):
    selected,path,env,_=fixture(tmp_path,monkeypatch)
    selected.control.sdk_task_binding=None;selected.control.sdk_review_binding=path
    with pytest.raises(ValueError):dispatch.prepare_dispatch(selected,path,provider='claude',source_environment=env,cancellation_probe=lambda:False)


def test_worker_requires_bound_external_capture(tmp_path,monkeypatch):
    op,_=prepare(tmp_path,monkeypatch)
    monkeypatch.setattr(runtime,'run_admitted_review',lambda *a,**k:pytest.fail('unbound effect'))
    with pytest.raises(ValueError):op.execute(object())


def test_filesystem_callback_uses_exact_selected_owner(tmp_path,monkeypatch):
    op,_=prepare(tmp_path,monkeypatch)
    file=Path(op.request.cwd)/'source.py';file.write_text('x=1')
    assert op._authorize_tool(op.request,'Read',{'file_path':str(file)}) is None
    assert op._authorize_tool(op.request,'Write',{'file_path':str(file),'content':'x=2'}) is None
    assert op._authorize_tool(op.request,'Edit',{'file_path':str(file),'old_string':'x=1','new_string':'x=2'}) is None
    for name,args in [('Read',{'file_path':str(file.parent.parent/'outside')}),('Bash',{'command':'echo nope'})]:
        with pytest.raises(ValueError):op._authorize_tool(op.request,name,args)
    with pytest.raises(ValueError):op._authorize_tool(replace(op.request,scope=('other',)),'Read',{'file_path':str(file)})


def test_credentials_revoked_before_file_effect(tmp_path,monkeypatch):
    op,mutable=prepare(tmp_path,monkeypatch)
    mutable['mode']='claude-subscription-override'
    with pytest.raises(ValueError):op._authorize_tool(op.request,'Write',{'file_path':str(Path(op.request.cwd)/'new'),'content':'x'})


def test_public_worker_runtime_receiving_and_tool_callback(tmp_path,monkeypatch):
    import process_supervision.sdk_worker as worker
    from process_supervision.process_runner import ProcessRunnerV1
    import test_sdk_claude_consultant_receiving as evidence
    op,_=prepare(tmp_path,monkeypatch);bind_capture(op)
    monkeypatch.setattr(runtime,'prepare_environment',lambda *a:({},owner.ProviderOutputContext(())))
    calls=[]
    def simulated(process,req,**kwargs):
        calls.append(req)
        for effect in dispatch._CLAUDE_STAGES[4:]:
            if effect=='account':
                phase={5:'before_connect',7:'initialize',9:'system_init'}[op._stage]
                kwargs['authority'](req,effect,{'kind':'account','evidence':{'phase':phase,'data':{}}})
            else:kwargs['authority'](req,effect)
        kwargs['authority'](req,'tool',{'kind':'tool','name':'Write','arguments':{'file_path':str(Path(req.cwd)/'new.py'),'content':'x=1'}})
        selection=runtime.runtime_selection_from_dict('claude',kwargs['runtime_selection'])
        return evidence.observed(monkeypatch,req,selection)
    monkeypatch.setattr(worker,'run_sdk_worker',simulated)
    with ProcessRunnerV1() as process:op.execute(process)
    result=op.receive()
    assert result.terminal['executionRole']=='external-worker' and result.terminal['gate']=='none'
    assert result.terminal['authorizing'] is False and len(calls)==1
    assert not (Path(op.request.cwd)/'new.py').exists()  # Admission fixture, not native execution.
    with pytest.raises(ValueError):op.execute(object())


def test_capture_under_workspace_rejected(tmp_path,monkeypatch):
    selected,path,env,_=fixture(tmp_path,monkeypatch)
    capture=Path.cwd()/'captures';capture.mkdir()
    env['CLAUDE_PROMPTS_DIR']=str(capture);monkeypatch.setenv('CLAUDE_PROMPTS_DIR',str(capture))
    with pytest.raises(ValueError):dispatch.prepare_dispatch(selected,path,provider='claude',source_environment=env,cancellation_probe=lambda:False)


def test_original_workspace_identity_checked_before_callback(tmp_path,monkeypatch):
    op,_=prepare(tmp_path,monkeypatch)
    root=Path(op.request.cwd)
    monkeypatch.chdir(tmp_path)
    root.rename(tmp_path/'former-workspace');root.mkdir()
    with pytest.raises(ValueError):op._authorize_tool(op.request,'Write',{'file_path':str(root/'new'),'content':'x'})


@pytest.mark.parametrize('name,args',[('Write',{'file_path':'new'}),('Edit',{'file_path':'new','old_string':'a'}),('Read',{'file_path':123})])
def test_malformed_tool_inputs_rejected(tmp_path,monkeypatch,name,args):
    op,_=prepare(tmp_path,monkeypatch)
    with pytest.raises(ValueError):op._authorize_tool(op.request,name,args)


def test_real_worker_adapter_routes_write_hook_to_cli_authority(tmp_path,monkeypatch):
    import asyncio
    import test_sdk_claude_worker as native_worker
    op,_=prepare(tmp_path,monkeypatch);bind_capture(op)
    op._consumed=True
    for effect in dispatch._CLAUDE_STAGES[:4]:op.assert_current(op.request,effect)
    def verify(req,evidence):
        op.assert_current(req,'account');return op._verify_auth_context(req,evidence)
    def authorize(req,name,args):
        op.assert_current(req,'tool');return op._authorize_tool(req,name,args)
    adapter,client=native_worker.setup(monkeypatch,authority=op.assert_current,authorize=authorize,verify=verify,instructions=lambda req:op.selection.instructions)
    client.terminal_change['structured_output']=dict(run_id=op.request.external_evidence_run_id,artifact_id=op.request.artifact_id,role=op.request.role,content='Work evidence')
    async def effect():
        args=dict(tool_name='Write',tool_input={'file_path':str(Path(op.request.cwd)/'new.py'),'content':'x=1'})
        decision=await client.hook('PreToolUse',**args)
        assert decision['hookSpecificOutput']['permissionDecision']=='allow'
        await client.hook('PostToolUse',**args)
    client.before_terminal=effect
    result=asyncio.run(adapter.execute(op.request))
    assert result.status=='completed' and result.task and result.review is None

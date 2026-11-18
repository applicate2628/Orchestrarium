"""Real bounded Host file effects with an offline official-shaped SDK."""
import asyncio
from pathlib import Path
from types import SimpleNamespace
import pytest
from test_sdk_copilot import request, payload, FakeSdk
import provider_prompt
from test_sdk_copilot_runtime import selection
from sdk_execution import copilot, runtime
from sdk_execution.contracts import json_text


def worker(tmp_path,monkeypatch):
    state=tmp_path/'state';state.mkdir();workspace=tmp_path/'workspace';workspace.mkdir()
    trusted=tmp_path/'trusted';trusted.mkdir()
    monkeypatch.setattr(runtime,'_worker_authority_roots',lambda provider='codex':(trusted,))
    chosen=selection(state);sdk=FakeSdk()
    sdk.Tool=lambda **kw:SimpleNamespace(**kw)
    sdk.ToolResult=lambda **kw:SimpleNamespace(**kw)
    sdk.PermissionDecisionApproveOnce=lambda:SimpleNamespace(kind='approve-once')
    req=request(role='backend-engineer',cwd=str(workspace),write_workspace=str(workspace),tool_profile='default')
    sdk.content=json_text(payload(role=req.role));effects=[]
    adapter=copilot.CopilotExecutor(runtime_path=chosen.executable,base_directory=chosen.base_directory,
        environment={},github_token='fixture-'+'worker-token',assert_current=lambda r,e:effects.append(e),
        output_context=provider_prompt.ProviderOutputContext(()),timeout_seconds=30,cleanup_timeout_seconds=30,
        sdk=sdk,instructions=chosen.instructions,worker_selection=chosen,authorize_tool=lambda r,n,a:None)
    return adapter,sdk,req,workspace


async def invoke(sdk,op,arguments,key='call'):
    tool=next(t for t in sdk.options['tools']['definitions'] if t.name=='orchestrarium_'+op)
    return await tool.handler(SimpleNamespace(session_id=sdk.session_id,tool_call_id=key,
        tool_name=tool.name,arguments=arguments,agent_id=None))


def test_actual_read_write_edit_and_exact_custom_allowlist(tmp_path,monkeypatch):
    adapter,sdk,req,root=worker(tmp_path,monkeypatch);target=root/'nested'/'code.txt';values=[]
    async def send():
        values.append(await invoke(sdk,'write',{'file_path':str(target),'content':'before'},'write'))
        values.append(await invoke(sdk,'edit',{'file_path':str(target),'old_string':'before','new_string':'after'},'edit'))
        values.append(await invoke(sdk,'read',{'file_path':str(target)},'read'))
    sdk.on_send=send;result=asyncio.run(adapter.execute(req))
    assert result.status=='completed' and target.read_text()=='after'
    assert [r.result_type for r in values]==['success']*3 and values[-1].text_result_for_llm=='after'
    assert set(sdk.options['tools']['available_tools'])==set(copilot.FILE_TOOLS)
    assert all(not t.skip_permission and not t.idempotent and not t.overrides_built_in_tool for t in sdk.options['tools']['definitions'])
    assert result.sdk_execution['sandboxMode']=='tool-restricted-workspace-write'


@pytest.mark.parametrize('kind',['outside','control','unknown-field'])
def test_rejected_effect_does_not_write(tmp_path,monkeypatch,kind):
    adapter,sdk,req,root=worker(tmp_path,monkeypatch);target=(tmp_path/'outside.txt' if kind=='outside' else root/'.git'/'config' if kind=='control' else root/'valid.txt');values=[]
    args={'file_path':str(target),'content':'test'}
    if kind=='unknown-field':args['extra']='unexpected'
    async def send():values.append(await invoke(sdk,'write',args))
    sdk.on_send=send;asyncio.run(adapter.execute(req))
    assert values[0].result_type=='failure' and not target.exists()


def test_partial_write_retained_incomplete_no_retry(tmp_path,monkeypatch):
    adapter,sdk,req,root=worker(tmp_path,monkeypatch);target=root/'file.txt';calls=[]
    original=Path.open
    class Partial:
        def __enter__(self):self.f=original(target,'wb');return self
        def __exit__(self,*args):self.f.close()
        def write(self,data):calls.append(1);self.f.write(data[:2]);raise OSError('private native detail')
    def opened(path,*args,**kwargs):
        return Partial() if path==target and args and args[0]=='wb' else original(path,*args,**kwargs)
    monkeypatch.setattr(Path,'open',opened)
    async def send():
        await invoke(sdk,'write',{'file_path':str(target),'content':'abcdef'})
        later=await invoke(sdk,'write',{'file_path':str(root/'later.txt'),'content':'no'},'later')
        assert later.result_type=='failure' and not (root/'later.txt').exists()
    sdk.on_send=send;result=asyncio.run(adapter.execute(req))
    assert result.status=='incomplete' and result.execution_error=='copilot_file_effect_may_be_partial'
    assert calls==[1] and target.read_bytes()==b'ab'
    assert 'effect_may_be_partial' in str(result.observations) and 'private native detail' not in str(result.to_dict())


def test_read_credential_not_transmitted(tmp_path,monkeypatch):
    adapter,sdk,req,root=worker(tmp_path,monkeypatch);target=root/'secret.txt';target.write_text('fixture-'+'worker-token');values=[]
    async def send():values.append(await invoke(sdk,'read',{'file_path':str(target)}))
    sdk.on_send=send;asyncio.run(adapter.execute(req))
    assert values[0].result_type=='failure' and 'worker-token' not in values[0].text_result_for_llm


def test_repeated_execute_cannot_replace_owned_workspace_pin(tmp_path,monkeypatch):
    adapter,sdk,req,root=worker(tmp_path,monkeypatch)
    async def run():
        entered=asyncio.Event();release=asyncio.Event()
        async def current(value,effect):
            if effect=='copilot_start':entered.set();await release.wait()
        adapter._authority=current
        active=asyncio.create_task(adapter.execute(req))
        await entered.wait();pin=adapter._workspace_identity
        monkeypatch.setattr(runtime,'validate_worker_custody',lambda *args,**kwargs:('replacement',1,2))
        with pytest.raises(ValueError,match='operation_already_consumed'):
            await adapter.execute(req)
        assert adapter._workspace_identity==pin
        release.set();await active
    asyncio.run(run())


def test_arguments_snapshot_survives_authority_await(tmp_path,monkeypatch):
    adapter,sdk,req,root=worker(tmp_path,monkeypatch)
    target=root/'admitted.txt';other=root/'changed.txt'
    args={'file_path':str(target),'content':'admitted'}
    async def authorize(value,name,arguments):
        args.update(file_path=str(other),content='changed')
    adapter._authorize_tool=authorize
    async def send():
        outcome=await invoke(sdk,'write',args)
        assert outcome.result_type=='success'
    sdk.on_send=send;result=asyncio.run(adapter.execute(req))
    assert result.status=='completed' and target.read_text()=='admitted' and not other.exists()

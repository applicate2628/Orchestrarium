"""Offline selected-runtime/factory tests, not native acceptance."""
import asyncio
from dataclasses import replace
import hashlib
import os
from types import SimpleNamespace
import pytest
from test_sdk_copilot import request, FakeSdk
import provider_prompt
from sdk_execution import copilot, runtime


def selection(tmp_path):
    executable=tmp_path/'provisioned.exe'; executable.write_bytes(b'offline fixture')
    return copilot.CopilotRuntimeSelection(str(executable),hashlib.sha256(executable.read_bytes()).hexdigest(),
        str(tmp_path),'copilot-explicit-token',provider_prompt.assemble_external_prompt(b'').decode(),
        str(tmp_path),None,None,128*1024*1024,30,30)


def test_selection_roundtrip_auth_and_exact_commitment(tmp_path):
    selected=selection(tmp_path); req=request()
    assert runtime.runtime_selection_from_dict('copilot',selected.to_dict())==selected
    runtime.validate_admitted_request(req,selected)
    secret='fixture-'+'credential-context'
    env,output=runtime.prepare_environment(selected,{'COPILOT_GITHUB_TOKEN':secret,'UNRELATED_SECRET':'not inherited'})
    assert env['COPILOT_GITHUB_TOKEN']==secret and 'UNRELATED_SECRET' not in env
    assert secret.encode() in output.needles
    metadata=runtime.selected_sdk_execution(req,selected)
    assert metadata['adapter']=='microsoft-copilot-sdk' and metadata['approvalPolicy']=='deny_all'
    assert 'sdkVersion' not in metadata and secret not in str(metadata)
    assert runtime.request_sha256(req,replace(selected,timeout_seconds=31)) != metadata['requestSha256']


@pytest.mark.parametrize('changes',[{'auth_mode':'ambient'},{'ledger_max_events':1},{'timeout_seconds':float('inf')},{'job_memory_limit_bytes':True},{'instructions':''}])
def test_invalid_selection(tmp_path,changes):
    with pytest.raises(ValueError): replace(selection(tmp_path),**changes)


def test_explicit_auth_no_ambient_fallback(tmp_path):
    with pytest.raises(ValueError): runtime.prepare_environment(selection(tmp_path),{'GH_TOKEN':'ambient'})


def test_factory_actual_governance_and_observed_controls(tmp_path,monkeypatch):
    selected=selection(tmp_path); req=request(); sdk=FakeSdk(); effects=[]
    async def authorize(value,effect):
        assert value==req; effects.append(effect)
    monkeypatch.setattr(runtime,'assert_current_launch',lambda *args: None)
    monkeypatch.setattr(copilot,'_load_sdk',lambda:sdk)
    monkeypatch.setenv('COPILOT_GITHUB_TOKEN','fixture-'+'private-token')
    adapter=copilot.create_copilot_adapter(req,SimpleNamespace(authorize=authorize),selected)
    result=asyncio.run(adapter.execute(req))
    assert result.status=='completed'
    assert sdk.options['system_message']=={'mode':'append','content':selected.instructions}
    assert sdk.prompt==req.prompt
    assert result.sdk_execution['model']==req.model
    assert result.sdk_execution['accountBinding']==req.account_binding
    assert 'runtimeVersion' not in result.sdk_execution
    assert effects[0]=='copilot_start' and effects[-1]=='copilot_result'
    assert result.to_tool_output()['process_settlement']=='not_established'

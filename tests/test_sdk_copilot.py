"""Offline official SDK-shaped fixtures; no runtime, SDK installation or model."""
import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'scripts'))
import provider_prompt
from sdk_execution.copilot import CopilotExecutor
from sdk_execution.contracts import ExecutionRequest, ExecutionResult, json_text
from _sdk_copilot_support import FakeSdk, payload


def request(**changes):
    values=dict(work_item_id='item',provider='copilot',external_dispatch_id='dispatch',
        external_evidence_run_id='evidence',artifact_id='advice.json',role='consultant',
        model='selected-model',effort='high',cwd='/fixture/repo',account_binding='selected-context',
        prompt='Analyze supplied context only.',coordinator_binding='root-lead',scope=('advice',),
        result_kind='task',tool_profile='prompt-only')
    values.update(changes)
    return ExecutionRequest(**values)


def make_executor(tmp_path, sdk=None, **changes):
    sdk=sdk or FakeSdk()
    runtime=tmp_path/'provisioned-runtime'; runtime.write_bytes(b'offline placeholder, never executed')
    effects=[]
    values=dict(runtime_path=str(runtime),base_directory=str(tmp_path/'state'),environment={},
        github_token=''.join(('fixture','-credential')),assert_current=lambda req,effect:effects.append(effect),
        output_context=provider_prompt.ProviderOutputContext(()),timeout_seconds=5,cleanup_timeout_seconds=1,sdk=sdk)
    values.update(changes)
    return CopilotExecutor(**values),sdk,effects


def test_prompt_only_success_uses_exact_provisioned_runtime_and_structured_result(tmp_path):
    executor,sdk,effects=make_executor(tmp_path)
    req=request(); result=asyncio.run(executor.execute(req))
    assert result.status==result.provider_status=='completed'
    assert result.task.content=='Bounded advice.' and result.review is None
    assert result.protocol_closed and result.cleanup_error is None
    assert result.to_tool_output()['process_settlement']=='not_established'
    assert result.to_tool_output()['authoritative'] is False
    assert ExecutionResult.from_dict(result.to_dict())==result
    assert sdk.client_options['mode']=='empty'
    assert sdk.client_options['github']['use_logged_in_user'] is False
    assert sdk.runtime['path']==str(tmp_path/'provisioned-runtime')
    assert sdk.runtime['env']=={'COPILOT_SKIP_CLI_DOWNLOAD':'1'}
    assert sdk.options['tools']=={'available_tools':[]}
    assert sdk.options['mcp']=={'servers':{},'enable_apps':False}
    assert sdk.options['enable_config_discovery'] is False
    assert sdk.options['skills']['enabled'] is False
    assert sdk.options['hooks']['enable_repository_hooks'] is False
    assert sdk.options['inference']['reasoning_effort']=='high'
    assert sdk.send_options['source'].agent_id=='root-lead'
    assert sdk.send_options['response_schema']['properties']['run_id']['enum']==['evidence']
    assert sdk.calls[-3:]==['unsubscribe','disconnect','stop']
    assert effects[-1]=='copilot_result'
    assert executor.execution_result is result


@pytest.mark.parametrize('changes',[{'result_kind':'unsupported'},{'role':'backend-engineer'},{'tool_profile':'default'},{'context_mode':'handoff'}])
def test_unsupported_current_contract_is_explicit(changes):
    with pytest.raises(ValueError):request(**changes)


def test_request_codec_roundtrip():
    req=request()
    assert ExecutionRequest.from_dict(req.to_dict())==req


@pytest.mark.parametrize('kind',['session.error','tool.execution_start'])
def test_unexpected_runtime_event_never_completes(tmp_path,kind):
    sdk=FakeSdk(); sdk.events=[SimpleNamespace(type=kind,data=None)]
    executor,_,_=make_executor(tmp_path,sdk)
    result=asyncio.run(executor.execute(request()))
    assert result.status=='incomplete' and result.task is not None
    assert 'abort' in sdk.calls and 'stop' in sdk.calls


def test_permission_callback_rejects_without_new_authority(tmp_path):
    sdk=FakeSdk();sdk.permission=True
    executor,_,_=make_executor(tmp_path,sdk)
    result=asyncio.run(executor.execute(request()))
    assert sdk.permission_result.kind=='reject'
    assert result.status=='incomplete' and result.execution_error=='copilot_unexpected_permission_request'


def test_empty_response_is_not_success(tmp_path):
    sdk=FakeSdk();sdk.reply_none=True
    executor,_,_=make_executor(tmp_path,sdk)
    result=asyncio.run(executor.execute(request()))
    assert result.status=='incomplete' and result.task is None


def test_event_budget_aborts_without_unbounded_adapter_buffer(tmp_path):
    sdk=FakeSdk();sdk.events=[SimpleNamespace(type='session.info',data=None)]*4
    executor,_,_=make_executor(tmp_path,sdk)
    result=asyncio.run(executor.execute(request(max_events=2)))
    assert result.status=='incomplete' and result.execution_error=='copilot_capture_limit'
    assert len(result.observations)<=2


@pytest.mark.parametrize("when",["before","after"])
def test_profile_readback_mismatch_preserves_completed_evidence_without_success(tmp_path,when):
    sdk=FakeSdk()
    if when=="before": sdk.profile_model="other-model"
    else:
        async def drift(): sdk.profile_effort="low"
        sdk.on_send=drift
    executor,_,_=make_executor(tmp_path,sdk)
    result=asyncio.run(executor.execute(request()))
    assert result.status=="incomplete" and result.execution_error=="copilot_profile_mismatch"
    assert ("send" in sdk.calls)==(when=="after")
    assert (result.task is not None)==(when=="after")
    assert sdk.calls[-1]=="stop"


def test_acquired_message_survives_later_sdk_exception(tmp_path):
    sdk=FakeSdk();sdk.failure="send"
    sdk.events=[SimpleNamespace(type="assistant.message",data=SimpleNamespace(content="Partial acquired advice."))]
    executor,_,_=make_executor(tmp_path,sdk)
    result=asyncio.run(executor.execute(request()))
    assert result.status=="incomplete" and result.task is None
    assert "Partial acquired advice." in result.observations[0].payload_json
    assert executor.execution_result is result and sdk.calls[-1]=="stop"

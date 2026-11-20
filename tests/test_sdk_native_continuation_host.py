"""Continuation Host chain with real receiving and synthetic worker transport."""
import asyncio,time
from dataclasses import replace
from types import SimpleNamespace
import pytest
from test_sdk_native_continuation_runtime import prepare, observed
from sdk_execution import runtime, receiving
from process_supervision.process_runner import ProcessRunnerV1
from provider_prompt import ProviderOutputContext


def test_new_turn_host_operation_receives_and_can_supply_next_predecessor(tmp_path,monkeypatch):
    import process_supervision.sdk_worker as worker
    req,selection,prior,terminal=prepare(tmp_path,monkeypatch)
    monkeypatch.setattr(runtime,'prepare_environment',lambda *a:({},ProviderOutputContext(())))
    monkeypatch.setattr(runtime._owner(),'require_codex_hook_trust',lambda *a,**k:0)
    calls=[]
    def simulated(process,value,**kwargs):
        calls.append(value)
        kwargs['authority'](value,'resume')
        selected=runtime.runtime_selection_from_dict('codex',kwargs['runtime_selection'])
        return observed(monkeypatch,value,selected,result_changes={'native_turn_id':'new-native-turn'})
    monkeypatch.setattr(worker,'run_sdk_worker',simulated)
    with ProcessRunnerV1() as process:
        executor=runtime.SdkReviewExecutor(request_id='next',authority=SimpleNamespace(resolve=lambda _:req,assert_current=lambda *a:None),selection=selection,process_owner=process,source_environment={},artifact='next.json',deadline_monotonic=time.monotonic()+120,cancellation_probe=lambda:False,started_at='2026-10-23T10:02:00Z',previous_run=prior,previous_terminal=terminal)
        result=asyncio.run(executor.execute(req))
        assert result.status=='completed' and result.native_turn_id=='new-native-turn'
        assert executor.terminal['gate']=='none' and executor.terminal['authorizing'] is False
        later=replace(req,context_mode='fresh',native_continuation=None,external_dispatch_id='third-dispatch',external_evidence_run_id='third-evidence',artifact_id='third-artifact')
        bound=runtime.prepare_continuation_request(later,selection,executor.runtime_run,executor.terminal)
        assert bound.native_continuation.native_turn_id=='new-native-turn'
        with pytest.raises(ValueError):asyncio.run(executor.execute(req))
        assert len(calls)==1


@pytest.mark.parametrize('change',[{'native_thread_id':'wrong-thread'},{'native_turn_id':'fixture-turn'}])
def test_receiving_rejects_wrong_thread_or_old_turn_as_complete(tmp_path,monkeypatch,change):
    req,selection,prior,terminal=prepare(tmp_path,monkeypatch)
    obs=observed(monkeypatch,req,selection,result_changes=change)
    payload=receiving.terminal_payload(req,obs,output_context=ProviderOutputContext(()),admitted_sdk_execution=runtime.selected_sdk_execution(req,selection))
    assert payload['status']=='blocked' and payload['gate']=='none'

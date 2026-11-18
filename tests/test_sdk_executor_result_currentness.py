"""Final Host currentness after durable receiving; no GitHub or model calls."""
import asyncio
from dataclasses import replace
import pytest
import test_sdk_claude_executor as host
from sdk_execution import runtime, receiving


def test_result_currentness_is_observed_after_receiving(tmp_path,monkeypatch):
    case=host.setup(tmp_path,monkeypatch)
    with case.process:
        result=asyncio.run(case.executor.execute(case.req))
        assert result.status=='completed'
        assert case.effects[-1]=='executor_result'
        assert case.executor.terminal['status']=='completed'


def test_owner_revision_changed_during_receiving_withholds_return_not_history(tmp_path,monkeypatch):
    case=host.setup(tmp_path,monkeypatch)
    original=receiving.receive_runtime_run
    def receive(*args,**kwargs):
        value=original(*args,**kwargs)
        case.current[0]=replace(case.req,artifact_id='new-reviewed-revision')
        return value
    monkeypatch.setattr(receiving,'receive_runtime_run',receive)
    with case.process:
        with pytest.raises(runtime.RuntimeBindingError,match='admitted_request_changed'):
            asyncio.run(case.executor.execute(case.req))
        assert case.executor.execution_result is None
        assert case.executor.runtime_run.observation.result.task is not None
        assert case.executor.terminal['status']=='completed'
        before=(case.item/'agent-runs.jsonl').read_bytes()
        with pytest.raises(runtime.RuntimeBindingError,match='operation_already_consumed'):
            asyncio.run(case.executor.execute(case.req))
        assert (case.item/'agent-runs.jsonl').read_bytes()==before and len(case.worker_calls)==1


def test_current_request_final_authority_denial_is_preserved(tmp_path,monkeypatch):
    case=host.setup(tmp_path,monkeypatch,denied='executor_result')
    with case.process,pytest.raises(ValueError,match='fixture authority revoked'):
        asyncio.run(case.executor.execute(case.req))
    assert case.executor.execution_result is None
    assert case.executor.terminal['status']=='completed'
    assert case.executor.runtime_run.observation.result.request==case.req


def test_no_worker_result_also_checks_current_owner(tmp_path,monkeypatch):
    case=host.setup(tmp_path,monkeypatch)
    def unstarted(req,selection,**kwargs):
        case.current[0]=replace(req,artifact_id='new-revision')
        return runtime.RuntimeRun(req,selection,host.ProviderOutputContext(()),None,{'status':'blocked'},'preworker_failure')
    monkeypatch.setattr(runtime,'run_admitted_review',unstarted)
    with case.process,pytest.raises(runtime.RuntimeBindingError,match='admitted_request_changed'):
        asyncio.run(case.executor.execute(case.req))
    assert case.executor.terminal=={'status':'blocked'}
    assert case.executor.runtime_run is not None and case.executor.execution_result is None

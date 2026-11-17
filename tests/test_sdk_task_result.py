"""Offline typed advice contract; no provider import or process."""
import asyncio
from dataclasses import replace
import json
import pytest
from test_sdk_codex import request, FakeClient, ClientBinding, answer, successful_events, completed
from sdk_execution.contracts import ExecutionRequest, ExecutionResult, TaskResult, validate_task, task_schema
from sdk_execution.codex import CodexReviewAdapter
from sdk_execution.codex import CodexConsultantAdapter
from sdk_execution.codex_tools import CodexMcpScope


def task_request(**changes):
    return request(role="consultant", result_kind="task", **changes)


def task_payload(**changes):
    data = dict(run_id="evidence-1", artifact_id="review.md", role="consultant", content="Bounded advice with evidence.")
    data.update(changes)
    return data


def consultant(client=None, adapter_type=CodexConsultantAdapter):
    client = client or FakeClient(successful_events(answer(task_payload())))
    def factory(handler):
        client.handler = handler
        return ClientBinding(client, "fixture-1", client.read_configuration, client.list_mcp_status)
    return adapter_type(client_factory=factory, assert_current=lambda *a:None,
                       verify_account=lambda req,data:req.account_binding, record=lambda obs:None,
                       mcp_scope=CodexMcpScope(())), client


def test_task_roundtrip_nonauthority_and_review_wire_compatibility():
    req = task_request()
    result = ExecutionResult(req, "completed", provider_status="completed", protocol_closed=True,
                             task=validate_task(task_payload(), request=req))
    assert ExecutionResult.from_dict(result.to_dict()) == result
    assert result.review is None and result.to_tool_output()["task"] == task_payload()
    assert result.to_tool_output()["authoritative"] is False
    old_req = request().to_dict()
    assert "result_kind" not in old_req
    assert ExecutionRequest.from_dict(old_req).to_dict() == old_req
    old_result = ExecutionResult(request(), "incomplete").to_dict()
    assert "task" not in old_result
    assert ExecutionResult.from_dict(old_result).to_dict() == old_result


@pytest.mark.parametrize("change", [{"run_id":"other"},{"artifact_id":"other"},{"role":"worker"},
                                     {"content":""},{"content":"x"*1500},{"verdict":"PASS"}])
def test_invalid_task_evidence(change):
    with pytest.raises(ValueError):
        validate_task(json.dumps(task_payload(**change)),request=task_request(max_output_bytes=1000))


def test_duplicate_keys_and_cross_kind_results_are_rejected():
    with pytest.raises(ValueError):
        validate_task('{"content":"a","content":"b"}',request=task_request())
    with pytest.raises(ValueError):
        validate_task(task_payload(),request=request())
    with pytest.raises(ValueError):
        ExecutionResult(request(),"incomplete",task=TaskResult(**task_payload()))
    from sdk_execution.contracts import ReviewResult
    with pytest.raises(ValueError):
        ExecutionResult(task_request(),"incomplete",review=ReviewResult("evidence-1","review.md","consultant","PASS",()))


def test_consultant_executes_same_read_only_lifecycle_without_review_verdict():
    adapter, client = consultant()
    result = asyncio.run(adapter.execute(task_request()))
    assert result.status == "completed" and result.protocol_closed
    assert result.task.content == task_payload()["content"] and result.review is None
    thread = next(c[1] for c in client.calls if c[0]=="thread_start")
    turn = next(c[3] for c in client.calls if c[0]=="turn_start")
    assert thread["sandbox"] == "read-only" and thread["approvalPolicy"] == "never"
    assert turn["sandboxPolicy"] == {"type":"readOnly","networkAccess":False}
    assert "verdict" not in turn["outputSchema"]["properties"]
    assert turn["outputSchema"] == task_schema(task_request())


@pytest.mark.parametrize("kind,role", [("review","consultant"),("task","backend-engineer"),("task","lead")])
def test_consultant_rejects_wrong_contract_before_factory(kind,role):
    adapter,client=consultant()
    with pytest.raises(ValueError):
        asyncio.run(adapter.execute(request(result_kind=kind,role=role)))
    assert client.calls == []


def test_review_adapter_rejects_task_and_consultant_resume_before_factory():
    adapter,client=consultant(adapter_type=CodexReviewAdapter)
    with pytest.raises(ValueError):
        asyncio.run(adapter.execute(task_request()))
    assert client.calls == []
    adapter,client=consultant()
    with pytest.raises(ValueError):
        asyncio.run(adapter.reconcile(task_request(),thread_id="thread-1",turn_id="turn-1"))
    assert client.calls == []


@pytest.mark.parametrize("failure", ["failed","interrupted","cleanup","stream"])
def test_consultant_failure_does_not_become_task_completion(failure):
    client=FakeClient(successful_events(answer(task_payload())))
    if failure in {"failed","interrupted"}: client.events=[completed(status=failure,items=[])]
    elif failure=="cleanup": client.close_error=True
    else: client.events=[]
    adapter,_=consultant(client)
    result=asyncio.run(adapter.execute(task_request()))
    assert result.status != "completed" and result.review is None
    assert result.to_tool_output()["authoritative"] is False


def test_new_fields_preserve_positional_constructor_contracts():
    import inspect
    from sdk_execution.coordination import CoordinationInferenceRequest
    assert inspect.signature(ExecutionRequest).parameters["result_kind"].kind is inspect.Parameter.KEYWORD_ONLY
    assert inspect.signature(CoordinationInferenceRequest).parameters["result_kind"].kind is inspect.Parameter.KEYWORD_ONLY
    assert inspect.signature(ExecutionResult).parameters["task"].kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.parametrize("provider",["claude","kimi","grok","minimax","mimo"])
def test_unimplemented_task_adapters_rejected_at_request_boundary(provider):
    with pytest.raises(ValueError,match="not implemented"):
        task_request(provider=provider)




def test_consultant_denies_provider_approval():
    client=FakeClient(successful_events(answer(task_payload())))
    def request_approval():
        response=client.handler("item/commandExecution/requestApproval", {})
        assert response == {"decision": "cancel"}
    client.on_turn=request_approval
    adapter,_=consultant(client)
    result=asyncio.run(adapter.execute(task_request()))
    assert result.status != "completed"
    assert result.execution_error == "unexpected_approval_request"


def test_consultant_cancels_only_its_owned_turn():
    import threading
    async def scenario():
        entered,released=threading.Event(),threading.Event()
        client=FakeClient([completed("interrupted",items=[])])
        client.on_next=lambda:(entered.set(),released.wait(5))
        adapter,_=consultant(client)
        operation=asyncio.create_task(adapter.execute(task_request()))
        try:
            assert await asyncio.to_thread(entered.wait,5)
            assert not (await adapter.cancel("foreign")).requested
            receipt=await adapter.cancel("dispatch-1")
            assert receipt.requested and receipt.acknowledged
        finally:
            released.set()
        result=await operation
        assert result.status == "interrupted" and result.task is None
        assert result.to_tool_output()["process_settlement"] == "not_established"
    asyncio.run(scenario())

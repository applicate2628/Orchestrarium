"""Offline Reviewer schema/lifecycle tests; no native runtime or model."""
import asyncio
import pytest
from test_sdk_copilot import request, payload, make_executor
from sdk_execution.contracts import json_text, review_schema
from sdk_execution import runtime
from test_sdk_copilot_runtime import selection


def review_request(**changes):
    return request(result_kind='review',role=changes.pop('role','architecture-reviewer'),**changes)


def review_payload(**changes):
    value=dict(run_id='evidence',artifact_id='advice.json',role='architecture-reviewer',verdict='PASS',findings=[])
    value.update(changes); return value


@pytest.mark.parametrize('verdict',['PASS','REVISE'])
def test_review_uses_exact_schema_and_non_authorizing_output(tmp_path,verdict):
    executor,sdk,effects=make_executor(tmp_path)
    req=review_request();sdk.content=json_text(review_payload(verdict=verdict))
    result=asyncio.run(executor.execute(req))
    assert result.status=='completed' and result.review.verdict==verdict and result.task is None
    assert sdk.send_options['response_schema']==review_schema(req)
    assert result.to_tool_output()['authoritative'] is False
    assert result.to_tool_output()['process_settlement']=='not_established'
    assert sdk.calls[-1]=='stop' and effects[-1]=='copilot_result'


@pytest.mark.parametrize('data',[payload(),review_payload(role='consultant'),review_payload(run_id='other'),review_payload(artifact_id='other'),review_payload(extra='unexpected')])
def test_crossed_or_malformed_review_not_complete(tmp_path,data):
    executor,sdk,effects=make_executor(tmp_path);sdk.content=json_text(data)
    result=asyncio.run(executor.execute(review_request()))
    assert result.status=='incomplete' and result.review is None and result.task is None
    assert result.observations and result.protocol_closed


@pytest.mark.parametrize('role',['consultant','backend-engineer','lead'])
def test_nonreview_role_rejected_before_effect(tmp_path,role):
    executor,sdk,effects=make_executor(tmp_path)
    req=review_request(role=role)
    with pytest.raises(ValueError,match='copilot_request_unsupported'):
        asyncio.run(executor.execute(req))
    assert not sdk.calls and not effects
    with pytest.raises(ValueError,match='copilot_request_unsupported'):
        runtime.validate_admitted_request(req,selection(tmp_path))


def test_review_request_commitment_preserves_same_runtime_controls(tmp_path):
    req=review_request();selected=selection(tmp_path)
    runtime.validate_admitted_request(req,selected)
    assert runtime.execution_role(req)=='external-reviewer'
    assert runtime.selected_sdk_execution(req,selected)['sandboxMode']=='tool-restricted-read-only'
    assert runtime.request_sha256(req,selected)!=runtime.request_sha256(request(),selected)

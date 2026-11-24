"""Scoped child decision transport offline, never actual model invocation."""
import asyncio
from dataclasses import replace
import json
import pytest
import test_sdk_coordination as base
from sdk_execution.coordination import (
    CoordinationInferenceRequest, child_coordination_payload, child_choice_sha256,
    intent_schema, validate_intent, function_call,
)
from sdk_execution.contracts import json_text
from sdk_execution.codex import ClientBinding
from sdk_execution.coordination_codex import CodexCoordinationAdapter


def choice(**changes):
    value = {"assignment_sha256": "a"*64,
        "catalog": [{"request_id": key, "request_sha256": "b"*64, "role":"consultant",
                     "scope":["owned"], "prompt": "Complete " + key} for key in ("first", "second")],
        "required_request_ids": ["first"], "completed_request_ids": [], "received_results": [], "unavailable_results": []}
    value.update(changes)
    return json_text(value)


def request(**changes):
    payload = choice(**changes)
    original = base.request()
    return replace(original, child_choice_json=payload,
        prompt=child_coordination_payload(original.operation_id, original.system_instructions, payload))


def intent(req, action="execute", request_id="second"):
    return json_text({"operation_id":req.operation_id,
        "child_choice_sha256":child_choice_sha256(req.child_choice_json),
        "action":action,"request_id":request_id})


def adapter(client):
    return CodexCoordinationAdapter(
        client_factory=lambda handler: ClientBinding(client, "fixture", client.read_configuration, client.list_mcp_status),
        assert_current=lambda *args:None, verify_account=lambda req,account:req.account_binding, record=lambda obs:None)


def test_native_adapter_selects_nonfixed_catalog_entry_without_executing_it():
    req=request()
    client=base.Client(req,text=intent(req))
    result=asyncio.run(adapter(client).execute(req))
    assert result.status=="completed",result.execution_error
    assert json.loads(result.intent_json)["request_id"]=="second"
    assert CoordinationInferenceRequest.from_dict(req.to_dict())==req
    assert "child_choice_json" not in base.request().to_dict()
    with pytest.raises(ValueError,match="child lifecycle"):
        function_call(result)


@pytest.mark.parametrize("action,request_id", [
    ("execute","unadmitted"),("execute",None),("finish","first"),("cancel","first"),("grant",None),("finish",None),
])
def test_wrong_or_premature_intent(action,request_id):
    with pytest.raises(ValueError):
        validate_intent(intent(request(),action,request_id),request())


def test_received_required_allows_finish_optional_not_falsely_completed():
    req=request(completed_request_ids=["first"],received_results=[{"request_id":"first","result":{"status":"completed"}}])
    assert json.loads(validate_intent(intent(req,"finish",None),req))["action"]=="finish"
    assert intent_schema(req)["properties"]["request_id"]["enum"]==[None,"second"]
    with pytest.raises(ValueError):
        validate_intent(intent(req,"execute","first"),req)


def test_state_or_assignment_digest_cannot_be_substituted():
    req=request()
    bad=json.loads(intent(req));bad["child_choice_sha256"]="f"*64
    with pytest.raises(ValueError):
        validate_intent(json_text(bad),req)
    with pytest.raises(ValueError):
        replace(req,child_choice_json=json.dumps(json.loads(req.child_choice_json),indent=2))


def test_actual_cancel_intent_is_non_authorizing_evidence():
    req=request()
    result=asyncio.run(adapter(base.Client(req,text=intent(req,"cancel",None))).execute(req))
    assert result.status=="completed"
    assert result.to_tool_output()["authoritative"] is False
    assert json.loads(result.intent_json)["action"]=="cancel"


def test_missing_or_forged_received_projection_is_invalid():
    with pytest.raises(ValueError):
        request(completed_request_ids=["first"])
    with pytest.raises(ValueError):
        request(received_results=[{"request_id":"first","result":"forged"}])


def test_attempted_unresolved_task_is_not_selectable_but_ready_sibling_is():
    req=request(unavailable_results=[{"request_id":"first","result":{"status":"blocked"}}])
    validate_intent(intent(req,"execute","second"),req)
    with pytest.raises(ValueError):
        validate_intent(intent(req,"execute","first"),req)
    with pytest.raises(ValueError):
        validate_intent(intent(req,"finish",None),req)

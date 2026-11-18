"""Shared Copilot Reviewer entry and receiving invariants, without execution."""
import pytest
from test_sdk_copilot_public_selection import owner
from test_sdk_copilot_metadata import metadata
from test_sdk_provider_result import payload,encode

def review_payload():
    value=payload();value.update(provider="copilot",sdkExecution=metadata())
    value["model"]=value["sdkExecution"]["model"]
    return value

def test_review_selector_remains_explicit():
    value=owner.parse_control(["review","--sdk-review-binding","binding.json"],provider="copilot")
    assert value.sdk_review_binding is not None and value.sdk_task_binding is None

@pytest.mark.parametrize("gate,status",[("PASS","completed"),("REVISE","revise"),("BLOCKED","blocked")])
def test_review_receipt_retains_nonauthorizing_verdict(gate,status):
    value=review_payload()
    value.update(gate=gate,status=status)
    value["primaryOutcome"].update(gate=gate,status=status)
    assert owner.parse_provider_result(encode(owner,value))==value
    assert not value["authorizing"] and not value["closesRunIds"]

@pytest.mark.parametrize("role",["consultant","backend-engineer","lead","nonexistent"])
def test_reviewer_cannot_claim_nonreview_profession(role):
    value=review_payload();value["assignedRole"]=role
    with pytest.raises(ValueError):owner.parse_provider_result(encode(owner,value))

def event(**changes):
    value=review_payload()
    value.update(schemaVersion=2,runId="dispatch-fixture-001",eventKind="launch",
                 role="external-reviewer",status="running",gate="none")
    for key in ("terminalClass","authorizing","closesRunIds"):value.pop(key)
    value.update(changes)
    return value

def test_canonical_launch_accepts_reviewer_taxonomy():
    errors=[];owner._ledger_owner().load_validator()._validate_sdk_event(event(),errors)
    assert not errors

@pytest.mark.parametrize("change",[
    {"assignedRole":"consultant"},{"assignedRole":"backend-engineer"},
    {"executionRole":"consultant"},{"role":"consultant"},{"gate":"PASS"},
])
def test_canonical_launch_rejects_role_confusion(change):
    errors=[];owner._ledger_owner().load_validator()._validate_sdk_event(event(**change),errors)
    assert errors

def schema_event(**changes):
    schema=owner._ledger_owner().load_validator().AGENT_RUN_SCHEMA
    value={key:val for key,val in event().items() if key in schema["properties"]}
    value.update(workItem="fixture-item",scope=["review source"],
                 startedAt="2026-11-18T00:00:00Z",updatedAt="2026-11-18T00:00:00Z")
    value.update(changes)
    return schema,value

def test_full_event_schema_accepts_copilot_reviewer():
    import jsonschema
    schema,value=schema_event()
    jsonschema.validate(value,schema)

def test_full_event_schema_still_rejects_launch_pass():
    import jsonschema
    schema,value=schema_event(gate="PASS")
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(value,schema)

def test_full_event_schema_keeps_copilot_consultant():
    import jsonschema
    schema,value=schema_event(role="consultant",executionRole="consultant",
                              assignedRole="consultant",gate="none")
    jsonschema.validate(value,schema)
    errors=[]
    owner._ledger_owner().load_validator()._validate_sdk_event(value,errors)
    assert not errors

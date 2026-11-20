"""Copilot scoped Worker metadata and shared nonauthorizing receiving."""
import jsonschema
import pytest
from test_sdk_copilot_metadata import metadata,validate,owner
from test_sdk_copilot_review_binding import schema_event
from test_sdk_copilot_public_selection import copilot_payload
from test_sdk_provider_result import encode
import provider_prompt

def worker_metadata(version=2,**changes):
    return metadata(version,sandboxMode="tool-restricted-workspace-write",
                    approvalPolicy="deny_unadmitted",writeWorkspaceSha256="b"*64,**changes)

@pytest.mark.parametrize("version",[1,2])
def test_worker_selected_and_observed_profile(version):
    value=worker_metadata(version)
    assert validate(value)==value
    jsonschema.validate(value,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])

@pytest.mark.parametrize("change",[
    {"approvalPolicy":"deny_all"},{"sandboxMode":"read-only"},
    {"sandboxMode":"tool-restricted-read-only"},{"writeWorkspaceSha256":None},
    {"writeWorkspaceSha256":"bad"},{"continuationSourceSha256":"c"*64},
])
def test_unbound_or_mixed_worker_profile_is_rejected(change):
    value=worker_metadata();value.update(change)
    with pytest.raises(ValueError):validate(value)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])

def worker_event(**changes):
    schema,value=schema_event(role="external-worker",executionRole="external-worker",
        assignedRole="backend-engineer",sdkExecution=worker_metadata())
    value.update(changes)
    return schema,value

def test_canonical_worker_launch_matches_shared_role_taxonomy():
    schema,value=worker_event()
    errors=[];owner()._validate_sdk_event(value,errors)
    assert not errors
    jsonschema.validate(value,schema)

@pytest.mark.parametrize("change",[
    {"assignedRole":"qa-engineer"},{"executionRole":"consultant"},
    {"role":"consultant"},{"gate":"PASS"},
])
def test_worker_ledger_does_not_grant_review_authority(change):
    _,value=worker_event(**change)
    errors=[];owner()._validate_sdk_event(value,errors)
    assert errors

def worker_payload():
    value=copilot_payload()
    value.update(executionRole="external-worker",assignedRole="backend-engineer",
                 sdkExecution=worker_metadata())
    return value

def test_worker_public_receipt_is_task_not_review():
    value=worker_payload()
    assert provider_prompt.parse_provider_result(encode(provider_prompt,value))==value
    assert value["gate"]=="none" and not value["authorizing"] and not value["closesRunIds"]

@pytest.mark.parametrize("change",[
    {"assignedRole":"qa-engineer"},{"gate":"PASS"},{"authorizing":True},
    {"executionRole":"external-reviewer"},{"executionRole":"consultant","assignedRole":"consultant"},
])
def test_worker_receipt_cannot_change_lane_or_authority(change):
    value=worker_payload();value.update(change)
    with pytest.raises(ValueError):provider_prompt.parse_provider_result(encode(provider_prompt,value))

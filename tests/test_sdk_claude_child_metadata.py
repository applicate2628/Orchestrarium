"""Claude scoped fresh handoff metadata, never persistent-session authority."""
import jsonschema
import pytest
from test_sdk_copilot_child_metadata import selected as copilot_selected
from test_sdk_copilot_metadata import owner
from test_sdk_copilot_review_binding import schema_event


def selected():
    value = copilot_selected()
    value.update(adapter="claude-agent-sdk", approvalPolicy="deny_unadmitted")
    return value


def validate(value):
    return owner().validate_sdk_execution(value, provider="claude", model=value["model"], effort=value["effort"])


def test_claude_fresh_scoped_profile_and_full_launch():
    value = selected()
    assert validate(value) == value
    schema, event = schema_event(provider="claude", role="lead", executionRole="main", assignedRole="lead", sdkExecution=value)
    errors = []
    owner()._validate_sdk_event(event, errors)
    assert not errors
    jsonschema.validate(event, schema)


@pytest.mark.parametrize("change", [
    {"decisionSessionMode":"native-persistent", "childAssignmentSha256":"c"*64},
    {"continuationSourceSha256":"d"*64}, {"forkSourceSha256":"d"*64},
    {"sandboxMode":"tool-restricted-workspace-write", "writeWorkspaceSha256":"d"*64},
    {"approvalPolicy":"deny_all"},
    {"schemaVersion":3,"operationKind":"coordination-inference","innerRequestSha256":"f"*64},
])
def test_claude_scoped_profile_cannot_expand_authority(change):
    value = selected(); value.update(change)
    with pytest.raises(ValueError): validate(value)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value, owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])


@pytest.mark.parametrize("change", [{"role":"consultant"}, {"executionRole":"consultant"}, {"assignedRole":"consultant"}, {"gate":"PASS"}])
def test_claude_scoped_event_cannot_become_task_or_gate(change):
    schema, event = schema_event(provider="claude",role="lead",executionRole="main",assignedRole="lead",sdkExecution=selected())
    event.update(change)
    errors=[]; owner()._validate_sdk_event(event, errors)
    assert errors
    with pytest.raises(jsonschema.ValidationError): jsonschema.validate(event,schema)

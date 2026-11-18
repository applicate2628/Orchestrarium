"""Fresh recovery commitments are not native session capabilities."""
import jsonschema
import pytest
from test_sdk_copilot_child_metadata import selected as base
from test_sdk_copilot_metadata import owner


def value(provider, committed=True):
    data=base()
    if provider == "codex": data.update(adapter="openai-codex",sandboxMode="read-only")
    if provider == "claude": data.update(adapter="claude-agent-sdk",approvalPolicy="deny_unadmitted")
    if committed: data.update(childAssignmentSha256="c"*64,childDecisionContextSha256="d"*64)
    return data


def validate(data,provider):
    return owner().validate_sdk_execution(data,provider=provider,model=data["model"],effort=data["effort"])


@pytest.mark.parametrize("provider",["codex","claude","copilot"])
@pytest.mark.parametrize("committed",[False,True])
def test_legacy_and_committed_fresh_selected_metadata(provider,committed):
    data=value(provider,committed)
    assert validate(data,provider)==data
    jsonschema.validate(data,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])


@pytest.mark.parametrize("provider",["codex","claude","copilot"])
@pytest.mark.parametrize("change",[
    {"childAssignmentSha256":None},{"childDecisionContextSha256":None},
    {"decisionSessionMode":"native-persistent"},{"continuationSourceSha256":"e"*64},
    {"forkSourceSha256":"e"*64},{"schemaVersion":2},
    {"sandboxMode":"workspace-write","writeWorkspaceSha256":"e"*64},
])
def test_fresh_commitment_cannot_be_partial_or_native(provider,change):
    data=value(provider)
    for key,item in change.items():
        if item is None:data.pop(key)
        else:data[key]=item
    with pytest.raises(ValueError):validate(data,provider)
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(data,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])


@pytest.mark.parametrize("provider",["codex","copilot"])
def test_persistent_pair_remains_compatible(provider):
    data=value(provider,False)
    data.update(childAssignmentSha256="c"*64,decisionSessionMode="native-persistent",continuationSourceSha256="e"*64)
    assert validate(data,provider)==data
    jsonschema.validate(data,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])

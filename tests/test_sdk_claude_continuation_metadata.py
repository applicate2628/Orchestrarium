"""Claude transcript continuation metadata is not a native turn-tip claim."""
import jsonschema
import pytest
from test_sdk_copilot_metadata import metadata as base, owner


def metadata(revision=2, **changes):
    return base(revision,adapter="claude-agent-sdk",approvalPolicy="deny_unadmitted",
                continuationSourceSha256="d"*64,**changes)


def validate(value):
    return owner().validate_sdk_execution(value,provider="claude",model=value["model"],effort=value["effort"])


@pytest.mark.parametrize("revision",[1,2])
def test_claude_readonly_received_source(revision):
    value=metadata(revision)
    assert validate(value)==value
    jsonschema.validate(value,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])


@pytest.mark.parametrize("change",[
    {"forkSourceSha256":"e"*64},
    {"sandboxMode":"tool-restricted-workspace-write","writeWorkspaceSha256":"e"*64},
    {"approvalPolicy":"deny_all"},
    {"continuationSourceSha256":"invalid"},
    {"decisionSessionMode":"native-persistent","childAssignmentSha256":"e"*64},
])
def test_claude_source_cannot_expand_controls(change):
    value=metadata();value.update(change)
    with pytest.raises(ValueError):validate(value)
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(value,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])

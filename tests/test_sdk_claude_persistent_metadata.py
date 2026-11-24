"""Scoped persistent Claude metadata does not grant fork/write or generic Lead."""
import jsonschema
import pytest
from test_sdk_claude_child_metadata import selected as fresh,validate
from test_sdk_copilot_metadata import owner


def selected(**changes):
    value=fresh()
    value.update(decisionSessionMode="native-persistent",childAssignmentSha256="c"*64)
    value.update(changes)
    return value


@pytest.mark.parametrize("continuation",[False,True])
def test_scoped_assignment_first_and_continued_decision(continuation):
    value=selected()
    if continuation:value["continuationSourceSha256"]="d"*64
    assert validate(value)==value
    jsonschema.validate(value,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])


@pytest.mark.parametrize("change",[
    {"forkSourceSha256":"d"*64},
    {"sandboxMode":"tool-restricted-workspace-write","writeWorkspaceSha256":"d"*64},
    {"approvalPolicy":"deny_all"},
    {"childDecisionContextSha256":"e"*64},
    {"schemaVersion":2},
    {"schemaVersion":3,"operationKind":"coordination-inference","innerRequestSha256":"f"*64},
])
def test_persistent_assignment_cannot_expand_route(change):
    value=selected(continuationSourceSha256="d"*64);value.update(change)
    with pytest.raises(ValueError):validate(value)
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(value,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])


@pytest.mark.parametrize("missing",["childAssignmentSha256","decisionSessionMode"])
def test_persistent_source_requires_complete_assignment(missing):
    value=selected(continuationSourceSha256="d"*64);del value[missing]
    with pytest.raises(ValueError):validate(value)
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(value,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])

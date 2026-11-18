"""Copilot continuation metadata, not a permission to fork or write."""
import jsonschema
import pytest
from test_sdk_copilot_metadata import metadata,validate,owner


@pytest.mark.parametrize("revision",[1,2])
def test_copilot_readonly_source_binding(revision):
    value=metadata(revision,continuationSourceSha256="d"*64)
    assert validate(value)==value
    jsonschema.validate(value,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])


@pytest.mark.parametrize("change",[
    {"forkSourceSha256":"e"*64},
    {"sandboxMode":"tool-restricted-workspace-write","approvalPolicy":"deny_unadmitted","writeWorkspaceSha256":"e"*64},
    {"continuationSourceSha256":"invalid"},
    {"decisionSessionMode":"native-persistent","childAssignmentSha256":"e"*64},
])
def test_selected_source_cannot_become_fork_write_or_child_route(change):
    value=metadata(2,continuationSourceSha256="d"*64);value.update(change)
    with pytest.raises(ValueError):validate(value)
    with pytest.raises(jsonschema.ValidationError):jsonschema.validate(value,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])

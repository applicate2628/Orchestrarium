"""Scoped Copilot child decisions retain the canonical nonauthorizing ledger."""
import jsonschema
import pytest
from test_sdk_copilot_metadata import metadata, validate, owner
from test_sdk_copilot_review_binding import schema_event


def selected(persistent=False):
    value = metadata(2, schemaVersion=5, operationKind="scoped-child-coordination",
                     childChoiceSha256="b"*64, outerBudgetBinding="outer",
                     innerBudgetBinding="inner")
    if persistent:
        value.update(decisionSessionMode="native-persistent",
                     childAssignmentSha256="c"*64, continuationSourceSha256="d"*64)
    return value


@pytest.mark.parametrize("persistent", [False, True])
def test_scoped_selected_profile_and_full_launch(persistent):
    value = selected(persistent)
    assert validate(value) == value
    jsonschema.validate(value, owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])
    schema, event = schema_event(role="lead", executionRole="main", assignedRole="lead",
                                 sdkExecution=value)
    errors = []
    owner()._validate_sdk_event(event, errors)
    assert not errors
    jsonschema.validate(event, schema)


def test_observed_and_selected_continuation_share_source_binding():
    value = metadata(1, continuationSourceSha256="d"*64)
    assert validate(value) == value
    jsonschema.validate(value, owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])
    value["schemaVersion"] = 2
    value.pop("sdkVersion"); value.pop("runtimeVersion")
    value["requestSha256"] = "a"*64
    # The selected Consultant continuation route now binds the same source;
    # metadata is not standalone role or launch authority.
    assert validate(value) == value
    jsonschema.validate(value, owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])


@pytest.mark.parametrize("change", [
    {"sandboxMode":"tool-restricted-workspace-write", "approvalPolicy":"deny_unadmitted", "writeWorkspaceSha256":"e"*64},
    {"approvalPolicy":"deny_unadmitted"}, {"forkSourceSha256":"e"*64},
    {"decisionSessionMode":None}, {"childAssignmentSha256":None},
    {"schemaVersion":3,"operationKind":"coordination-inference","innerRequestSha256":"f"*64},
])
def test_scoped_metadata_cannot_expand_capability(change):
    value = selected(True); value.update(change)
    with pytest.raises(ValueError): validate(value)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value, owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])


@pytest.mark.parametrize("change", [
    {"role":"consultant"}, {"executionRole":"consultant"},
    {"assignedRole":"consultant"}, {"gate":"PASS"}, {"provider":"claude"},
])
def test_scoped_launch_cannot_change_authority(change):
    schema, event = schema_event(role="lead",executionRole="main",assignedRole="lead",
                                 sdkExecution=selected(True))
    event.update(change)
    errors = []; owner()._validate_sdk_event(event, errors)
    assert errors
    with pytest.raises(jsonschema.ValidationError): jsonschema.validate(event, schema)


def test_equal_reservations_rejected_by_semantic_owner():
    value = selected(); value["innerBudgetBinding"] = value["outerBudgetBinding"]
    with pytest.raises(ValueError): validate(value)

"""Copilot SDK metadata describes controls, not account or OS proof."""
import jsonschema
import pytest
from test_agent_run_ledger import load_ledger_module
from test_sdk_ledger import SDK_CONFIG

def metadata(version=2, **changes):
    value=dict(SDK_CONFIG, schemaVersion=version, adapter="microsoft-copilot-sdk",
               sandboxMode="tool-restricted-read-only")
    if version == 2:
        value.pop("sdkVersion")
        value.pop("runtimeVersion")
        value["requestSha256"]="a"*64
    value.update(changes)
    return value

def owner():
    return load_ledger_module().load_validator()

def validate(value, provider="copilot"):
    return owner().validate_sdk_execution(value,provider=provider,
                                         model=SDK_CONFIG["model"],effort="high")

@pytest.mark.parametrize("version",[1,2])
def test_selected_and_observed_copilot_metadata(version):
    value=metadata(version)
    assert validate(value)==value
    jsonschema.validate(value,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])

@pytest.mark.parametrize("change",[
    {"sandboxMode":"read-only"},{"sandboxMode":"workspace-write"},
    {"approvalPolicy":"deny_unadmitted"},{"writeWorkspaceSha256":"b"*64},
    {"continuationSourceSha256":"b"*64},{"forkSourceSha256":"b"*64},
    {"accountVerified":True},{"processSettlement":"proved"},
])
def test_copilot_metadata_rejects_unqualified_controls(change):
    value=metadata(**change)
    with pytest.raises(ValueError): validate(value)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])

@pytest.mark.parametrize("provider",["codex","claude","grok"])
def test_adapter_cannot_be_relabelled_as_another_provider(provider):
    with pytest.raises(ValueError): validate(metadata(),provider)

@pytest.mark.parametrize("role,assigned,gate",[
    ("external-reviewer","consultant","none"),
    ("external-worker","backend-engineer","none"),
    ("consultant","consultant","PASS"),
])
def test_copilot_event_requires_consultant_nonauthorizing_lane(role,assigned,gate):
    event=dict(schemaVersion=2,runId="dispatch",provider="copilot",
        model=SDK_CONFIG["model"],effort="high",sdkExecution=metadata(),
        actualExecutionPath="direct-external-sdk",eventKind="launch",
        role=role,executionRole=role,assignedRole=assigned,gate=gate,status="running",
        artifactIdentity="artifact",externalDispatchId="dispatch",
        externalEvidenceRunId="evidence",effortMappingLoss="none")
    errors=[]
    owner()._validate_sdk_event(event,errors)
    assert errors

@pytest.mark.parametrize("missing",[
    ("runtimeVersion",),("sdkVersion",),("runtimeVersion","sdkVersion"),
])
def test_unobserved_copilot_versions_are_absent_not_fabricated(missing):
    value=metadata(1)
    for key in missing: value.pop(key)
    assert validate(value)==value
    jsonschema.validate(value,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])
    historical=dict(value,adapter="openai-codex",sandboxMode="read-only")
    with pytest.raises(ValueError): validate(historical,"codex")
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(historical,owner().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])

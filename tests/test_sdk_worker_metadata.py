"""Worker metadata parity and canonical ledger admission; offline only."""
import pytest
import jsonschema
from test_sdk_ledger import SDK_CONFIG, sdk_launch_args, sdk_settle_args, read_events
from test_agent_run_ledger import load_ledger_module, prepare_valid_work_item, run_ledger, run_validator

def metadata(version=2, **changes):
    data = dict(SDK_CONFIG, schemaVersion=version, sandboxMode="workspace-write",
                writeWorkspaceSha256="b"*64)
    if version == 2:
        data.pop("sdkVersion")
        data.pop("runtimeVersion")
        data["requestSha256"]="a"*64
    data.update(changes)
    return data

def validate(value):
    validator=load_ledger_module().load_validator()
    return validator.validate_sdk_execution(value,provider="codex",model=SDK_CONFIG["model"],effort="high")

@pytest.mark.parametrize("version",[1,2])
def test_worker_metadata_versioned_positive_and_schema_parity(version):
    value=metadata(version)
    assert validate(value)==value
    jsonschema.validate(value,load_ledger_module().load_validator().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])

@pytest.mark.parametrize("change",[
    {"writeWorkspaceSha256":None},{"writeWorkspaceSha256":"relative"},
    {"writeWorkspaceSha256":"a"*63},{"writeWorkspaceSha256":"A"*64},
    {"writeWorkspaceSha256":"g"*64},{"writeWorkspaceSha256":"a"*65},
    {"sandboxMode":"read-only"},{"schemaVersion":3}])
def test_bad_write_metadata_rejected_by_python_and_schema(change):
    value=metadata(**change)
    with pytest.raises(ValueError): validate(value)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value,load_ledger_module().load_validator().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])

def test_missing_write_root_rejected_without_affecting_historical_readonly():
    value=metadata()
    value.pop("writeWorkspaceSha256")
    with pytest.raises(ValueError): validate(value)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value,load_ledger_module().load_validator().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])
    assert validate(SDK_CONFIG)==SDK_CONFIG

def worker_launch(value=None):
    args=sdk_launch_args(value or metadata())
    for flag,value in (("--role","external-worker"),("--execution-role","external-worker"),("--assigned-role","backend-engineer")):
        args[args.index(flag)+1]=value
    return args

@pytest.mark.parametrize("flag,value",[("--execution-role","consultant"),("--role","external-reviewer"),
                                      ("--assigned-role","qa-engineer"),("--gate","PASS")])
def test_worker_ledger_rejects_role_or_gate_confusion(tmp_path,flag,value):
    item=prepare_valid_work_item(tmp_path)
    args=worker_launch()
    args[args.index(flag)+1]=value
    result=run_ledger(item,*args)
    assert result.returncode != 0

def test_observed_write_metadata_cannot_be_selected_ledger_authority(tmp_path):
    item=prepare_valid_work_item(tmp_path)
    result=run_ledger(item,*worker_launch(metadata(1)))
    assert result.returncode != 0

def test_worker_launch_terminal_keeps_exact_root_and_nonauthority(tmp_path):
    item=prepare_valid_work_item(tmp_path)
    result=run_ledger(item,*worker_launch())
    assert result.returncode == 0,result.stdout+result.stderr
    args=sdk_settle_args(item)
    args[args.index("--gate")+1]="none"
    result=run_ledger(item,*args)
    assert result.returncode == 0,result.stdout+result.stderr
    events=read_events(item)
    assert events[0]["sdkExecution"]==events[1]["sdkExecution"]==metadata()
    assert events[1]["authorizing"] is False and events[1]["closesRunIds"]==[]
    checked=run_validator(item)
    assert checked.returncode == 0,checked.stdout+checked.stderr


def test_raw_workspace_path_is_not_a_metadata_field():
    value=metadata(writeWorkspace=r"D:\workspace\task")
    with pytest.raises(ValueError): validate(value)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(value,load_ledger_module().load_validator().AGENT_RUN_SCHEMA["properties"]["sdkExecution"])

"""SDK-only Copilot wrapper selection; no provider execution."""
import pytest
from test_sdk_dispatch import owner

def test_explicit_sdk_task_selector_and_profile():
    control=owner.parse_control(["topic","--sdk-task-binding","binding.json"],provider="copilot")
    assert str(control.sdk_task_binding)=="binding.json"
    assert owner.resolved_profile("copilot",["--model","selected-model","--effort","high"]) == (
        ["--model","selected-model","--effort","high"],"selected-model","high")

@pytest.mark.parametrize("args",[[],["--sdk-review-binding","binding.json"]])
def test_copilot_cannot_fall_back_to_legacy_cli(args):
    with pytest.raises(ValueError):
        owner.parse_control(["topic",*args],provider="copilot")

@pytest.mark.parametrize("flags",[[],["--model","selected-model"],
    ["--model","selected-model","--effort","high","--tools","Read"],
    ["-p","--model","selected-model","--effort","high"]])
def test_profile_needs_explicit_model_effort_and_no_native_options(flags):
    with pytest.raises(ValueError):owner.resolved_profile("copilot",flags)

def test_copilot_runtime_requires_explicit_absolute_existing_path(tmp_path,monkeypatch):
    monkeypatch.delenv("COPILOT_CLI_PATH",raising=False)
    assert owner.resolve_provider_command("copilot") is None
    monkeypatch.setenv("COPILOT_CLI_PATH","relative.exe")
    assert owner.resolve_provider_command("copilot") is None
    target=tmp_path/"runtime.exe";target.write_bytes(b"offline placeholder")
    monkeypatch.setenv("COPILOT_CLI_PATH",str(target))
    resolved=owner.resolve_provider_command("copilot")
    assert resolved.target==target
    assert resolved.provenance=="explicit-absolute-binding"

def test_capture_uses_explicit_copilot_namespace(tmp_path,monkeypatch):
    monkeypatch.setenv("COPILOT_PROMPTS_DIR",str(tmp_path))
    assert owner._capture_output_path("copilot")==tmp_path

def copilot_payload():
    from test_sdk_consultant_entrypoint import consultant_payload
    from test_sdk_copilot_metadata import metadata
    data=consultant_payload()
    data.update(provider="copilot",sdkExecution=metadata())
    data["model"]=data["sdkExecution"]["model"]
    data["effort"]=data["sdkExecution"]["effort"]
    return data

def test_copilot_canonical_parser_receives_selected_sdk_not_cli_flags():
    from test_sdk_provider_result import encode
    data=copilot_payload()
    assert owner.parse_provider_result(encode(owner,data))==data

@pytest.mark.parametrize("changes",[
    {"executionRole":"external-reviewer","assignedRole":"qa-engineer"},
    {"launchFlags":["--model","selected-model"]},
    {"authorizing":True},
])
def test_copilot_received_result_cannot_be_review_cli_or_authority(changes):
    from test_sdk_provider_result import encode
    data=copilot_payload();data.update(changes)
    with pytest.raises(ValueError):owner.parse_provider_result(encode(owner,data))

def test_public_entrypoint_refuses_legacy_before_any_native_effect(tmp_path):
    import subprocess,sys
    from pathlib import Path
    script=Path(__file__).resolve().parents[1]/"scripts/invoke-copilot-prompt.py"
    result=subprocess.run([sys.executable,str(script),"topic"],cwd=tmp_path,capture_output=True,text=True)
    assert result.returncode != 0
    assert "E_COPILOT_SDK_TASK_BINDING_REQUIRED" in result.stdout+result.stderr
    assert list(tmp_path.iterdir())==[]

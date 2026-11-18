"""Fresh scoped Claude decision using the existing native-shaped offline peer."""
import asyncio
from dataclasses import replace
import json
import pytest
import test_sdk_claude as base
import test_sdk_child_choice as choice
from sdk_execution.claude import ClaudeCoordinationAdapter, AdapterError
from sdk_execution.coordination import CoordinationInferenceRequest, CoordinationInferenceResult
from sdk_execution import runtime
import provider_prompt

instruction_capture_root = base.instruction_capture_root


def request(**changes):
    return replace(choice.request(), provider="claude", model="fixture-model", effort="high", **changes)


def adapter(client=None, **kwargs):
    existing, client = base.adapter(client, **kwargs)
    client.init_change.setdefault('tools', [])
    return ClaudeCoordinationAdapter(
        client_factory=existing._factory, assert_current=existing._assert_current,
        authorize_tool=existing._authorize_tool, load_instructions=existing._instructions,
        verify_account=existing._verify_account, record=existing._record), client


def test_fresh_scoped_intent_uses_actual_claude_lifecycle_without_task_tools():
    req = request()
    client = base.FakeClient()
    client.terminal_change["structured_output"] = json.loads(choice.intent(req))
    instance, client = adapter(client)
    result = asyncio.run(instance.execute(req))
    assert type(result) is CoordinationInferenceResult
    assert result.status == "completed", result.execution_error
    assert json.loads(result.intent_json)["request_id"] == "second"
    assert result.native_turn_id == client.prompt["uuid"]
    assert result.to_tool_output()["authoritative"] is False
    assert client.options["tools"] == []
    assert client.options["agents"] == {} and client.options["mcp_servers"] == {}
    assert client.options["resume"] is None and client.options["continue_conversation"] is False
    assert "child_choice_sha256" in client.options["output_format"]["schema"]["properties"]
    assert CoordinationInferenceRequest.from_dict(req.to_dict()) == req
    assert CoordinationInferenceResult.from_dict(result.to_dict()) == result


@pytest.mark.parametrize("changes", [
    {"decision_session_mode": "native-persistent", "context_mode": "fork"},
    {"child_choice_json": None}, {"context_mode": "handoff"},
    {"role": "consultant"}, {"tool_profile": "prompt-only"},
])
def test_unsupported_coordination_context_refused(changes):
    with pytest.raises(ValueError):
        request(**changes)


@pytest.mark.parametrize("mode", ["claude-direct", "claude-bedrock", "claude-vertex",
                                  "claude-subscription-override"])
def test_exact_programmatic_auth_uses_existing_admission_owner(tmp_path, mode):
    req = request()
    selected = base.claude_selection(tmp_path, auth_mode=mode,
        instructions=provider_prompt.assemble_external_prompt(b"Decision").decode())
    if mode == "claude-subscription-override":
        with pytest.raises(runtime.RuntimeBindingError, match="claude_programmatic_auth_mode_required"):
            runtime.validate_admitted_request(req, selected)
    else:
        runtime.validate_admitted_request(req, selected)
        assert runtime.selected_sdk_execution(req, selected)["schemaVersion"] == 5


def test_wrong_review_output_and_read_tool_cannot_become_coordination():
    req = request()
    client = base.FakeClient()
    instance, _ = adapter(client)
    result = asyncio.run(instance.execute(req))
    assert result.status != "completed" and result.intent_json is None
    client = base.FakeClient()
    client.use_tool = True
    client.terminal_change["structured_output"] = json.loads(choice.intent(req))
    instance, _ = adapter(client)
    result = asyncio.run(instance.execute(req))
    assert result.status != "completed"

"""Offline Consultant fixtures, not native SDK or account acceptance."""
import asyncio
from pathlib import Path

import pytest
import test_sdk_claude as base
from test_sdk_claude import instruction_capture_root
from sdk_execution.claude import ClaudeConsultantAdapter
from sdk_execution.contracts import ExecutionResult, TaskResult


def request(**changes):
    values = dict(role="consultant", result_kind="task", scope=("advice",))
    values.update(changes)
    return base.request(**values)


def payload(**changes):
    values = dict(run_id="evidence-1", artifact_id="review.md", role="consultant", content="Read-only advice.")
    values.update(changes)
    return values


def adapter(monkeypatch, client=None, **kwargs):
    client = client or base.FakeClient()
    client.terminal_change.setdefault("structured_output", payload())
    monkeypatch.setattr(base, "ClaudeReviewAdapter", ClaudeConsultantAdapter)
    return base.adapter(client, **kwargs)


def run(monkeypatch, client=None, req=None, **kwargs):
    instance, client = adapter(monkeypatch, client, **kwargs)
    return asyncio.run(instance.execute(req or request())), client


def test_task_success_is_typed_nonauthorizing_and_cleans_instructions(monkeypatch):
    result, client = run(monkeypatch)
    assert result.status == result.provider_status == "completed"
    assert result.task == TaskResult.from_dict(payload()) and result.review is None
    assert result.protocol_closed and result.cleanup_error is None
    output = result.to_tool_output()
    assert output["authoritative"] is False
    assert output["process_settlement"] == "not_established"
    assert "verdict" not in result.task.to_dict()
    assert ExecutionResult.from_dict(result.to_dict()) == result
    schema = client.options["output_format"]["schema"]
    assert set(schema["required"]) == {"run_id", "artifact_id", "role", "content"}
    assert schema["properties"]["role"]["enum"] == ["consultant"]
    assert client.options["tools"] == list(base.READ_TOOLS)
    assert client.options["allowed_tools"] == [] and client.options["mcp_servers"] == {}
    assert client.options["permission_mode"] == "default"
    assert not Path(client.options["extra_args"]["append-system-prompt-file"]).exists()


@pytest.mark.parametrize("changes", [
    {"role": "architecture-reviewer"}, {"provider": "codex"},
    {"result_kind": "review"}, {"write_workspace": "/fixture/repo"},
])
def test_wrong_request_refused_before_factory(monkeypatch, changes):
    instance, client = adapter(monkeypatch)
    try:
        result = asyncio.run(instance.execute(request(**changes)))
    except (ValueError, base.AdapterError):
        pass
    else:
        assert result.status != "completed" and result.task is None
    assert client.calls == []


@pytest.mark.parametrize("changes", [
    {"run_id": "other"}, {"artifact_id": "other"}, {"role": "architecture-reviewer"},
    {"verdict": "PASS"}, {"content": ""}, {"content": None}, {"unexpected": True},
])
def test_task_payload_must_be_exact_and_bound(monkeypatch, changes):
    client = base.FakeClient()
    client.terminal_change["structured_output"] = payload(**changes)
    result, _ = run(monkeypatch, client)
    assert result.status != "completed" and result.task is None and result.review is None


@pytest.mark.parametrize("valid", [True, False])
def test_structured_output_tool_validates_task_not_review(monkeypatch, valid):
    client = base.FakeClient()
    client.init_change["tools"] = [*base.READ_TOOLS, base.OUTPUT_TOOL]
    async def output():
        data = payload() if valid else base.review_payload()
        changes = dict(tool_name=base.OUTPUT_TOOL, tool_input=data)
        decision = await client.hook("PreToolUse", **changes)
        assert decision["hookSpecificOutput"]["permissionDecision"] == ("allow" if valid else "deny")
        if valid:
            await client.hook("PostToolUse", **changes)
    client.before_terminal = output
    result, _ = run(monkeypatch, client)
    assert (result.status == "completed") is valid
    assert result.review is None
    if not valid:
        assert result.task is None


@pytest.mark.parametrize("tool", ["Write", "Edit", "Bash"])
def test_mutating_tool_not_admitted(monkeypatch, tool):
    client = base.FakeClient()
    async def attempt():
        result = await client.hook("PreToolUse", tool_name=tool, tool_input={"path": "a.py"})
        assert result["hookSpecificOutput"]["permissionDecision"] == "deny"
    client.before_terminal = attempt
    result, _ = run(monkeypatch, client)
    assert result.status != "completed" and result.task is None


@pytest.mark.parametrize("failure", ["connect", "query", "terminal", "disconnect"])
def test_failures_never_fabricate_completed_task(monkeypatch, failure):
    client = base.FakeClient()
    if failure == "terminal":
        client.include_terminal = False
    else:
        setattr(client, "close_error" if failure == "disconnect" else failure + "_error", True)
    result, client = run(monkeypatch, client)
    assert result.status != "completed" and result.review is None
    if failure == "disconnect":
        assert result.provider_status == "completed" and result.task is not None
        assert result.cleanup_error
    else:
        assert result.task is None
    assert not Path(client.options["extra_args"]["append-system-prompt-file"]).exists()


def test_cancel_before_query_is_not_success(monkeypatch):
    instance, client = adapter(monkeypatch)
    async def scenario():
        async def stop():
            await instance.cancel("dispatch-1")
        client.before_connect = stop
        return await instance.execute(request())
    result = asyncio.run(scenario())
    assert result.status == "interrupted" and result.task is None
    assert "query" not in client.calls and result.protocol_closed


def test_review_adapter_still_rejects_task_before_factory():
    instance, client = base.adapter()
    with pytest.raises((ValueError, base.AdapterError)):
        asyncio.run(instance.execute(request()))
    assert client.calls == []

@pytest.mark.parametrize("entry", ["run", "factory"])
def test_public_runtime_remains_unqualified_before_effects(monkeypatch, tmp_path, entry):
    from sdk_execution import runtime, claude
    def no_effect(*args, **kwargs):
        pytest.fail("unqualified task reached launch/environment effects")
    monkeypatch.setattr(runtime, "assert_current_launch", no_effect)
    monkeypatch.setattr(runtime, "prepare_environment", no_effect)
    from process_supervision.process_runner import ProcessRunnerV1
    import provider_prompt
    req = request()
    selection = base.claude_selection(tmp_path, expected_launch_sha256=None,
        instructions=provider_prompt.assemble_external_prompt(b"Advice").decode())
    calls = {
        "run": lambda: runtime.run_admitted_review(req, selection, owner=object.__new__(ProcessRunnerV1), source_environment={},
            authority=no_effect, deadline_monotonic=0, cancellation_probe=lambda: False, started_at="fixture"),
        "factory": lambda: claude.create_claude_adapter(req, None, object.__new__(claude.ClaudeRuntimeSelection)),
    }
    with pytest.raises((runtime.RuntimeBindingError, base.AdapterError), match="claude_task_runtime_receiving_not_qualified"):
        calls[entry]()

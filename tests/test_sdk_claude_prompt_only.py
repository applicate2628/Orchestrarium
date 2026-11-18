"""Offline explicit prompt-only capability; no native acceptance claim."""
from dataclasses import replace
import pytest
import test_sdk_claude as base
from test_sdk_claude import instruction_capture_root
from test_sdk_claude_consultant import request, run, payload
from sdk_execution.contracts import ExecutionRequest
from sdk_execution.runtime import request_sha256


def test_profile_default_wire_and_explicit_hash(tmp_path):
    req = request()
    assert "tool_profile" not in req.to_dict()
    assert ExecutionRequest.from_dict(req.to_dict()) == req
    limited = replace(req, tool_profile="prompt-only")
    assert ExecutionRequest.from_dict(limited.to_dict()) == limited
    assert request_sha256(req, base.claude_selection(tmp_path)) != request_sha256(limited, base.claude_selection(tmp_path))


@pytest.mark.parametrize("change", [{"provider": "codex"}, {"result_kind": "review"},
    {"role": "architect"}, {"tool_profile": "unknown"}])
def test_profile_exact_route(change):
    values = {"tool_profile": "prompt-only", **change}
    with pytest.raises(ValueError):
        request(**values)


@pytest.mark.parametrize("tools", [[], [base.OUTPUT_TOOL]])
def test_prompt_only_success_no_reads(monkeypatch, tools):
    client = base.FakeClient()
    client.init_change["tools"] = tools
    result, client = run(monkeypatch, client, req=request(tool_profile="prompt-only"))
    assert result.status == "completed"
    assert client.options["tools"] == []
    assert set(base.READ_TOOLS).issubset(client.options["disallowed_tools"])
    assert any(o.kind == "auth-context/verified" for o in result.observations)


@pytest.mark.parametrize("tool", base.READ_TOOLS)
def test_prompt_only_rejects_read_hook(monkeypatch, tool):
    client = base.FakeClient()
    client.init_change["tools"] = []
    async def attempt():
        decision = await client.hook("PreToolUse", tool_name=tool, tool_input={"file_path": "/fixture/repo/a.py"})
        assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
    client.before_terminal = attempt
    result, _ = run(monkeypatch, client, req=request(tool_profile="prompt-only"))
    assert result.status != "completed" and result.task is None


def test_prompt_only_rejects_ambient_read_inventory(monkeypatch):
    result, _ = run(monkeypatch, req=request(tool_profile="prompt-only"))
    assert result.status != "completed" and result.task is None

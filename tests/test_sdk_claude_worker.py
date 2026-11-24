"""Offline Worker tool-authority protocol, not native filesystem confinement."""
import asyncio
import hashlib
import pytest
import test_sdk_claude as base
from test_sdk_claude import instruction_capture_root
from sdk_execution.claude import ClaudeWorkerAdapter
from sdk_execution.contracts import ExecutionRequest


def request(**changes):
    return base.request(**({"role": "architect", "result_kind": "task", "write_workspace": "/fixture/repo", **changes}))


def setup(monkeypatch, **kwargs):
    client = base.FakeClient()
    client.init_change["tools"] = [*base.READ_TOOLS, "Write", "Edit"]
    client.terminal_change["structured_output"] = {
        "run_id": "evidence-1", "artifact_id": "review.md", "role": "architect", "content": "Task evidence."}
    monkeypatch.setattr(base, "ClaudeReviewAdapter", ClaudeWorkerAdapter)
    adapter, _ = base.adapter(client, **kwargs)
    return adapter, client


@pytest.mark.parametrize("tool,args", [
    ("Write", {"file_path": "/fixture/repo/a.py", "content": "x=1"}),
    ("Edit", {"file_path": "/fixture/repo/a.py", "old_string": "x=1", "new_string": "x=2"}),
])
def test_exact_host_authorized_write_and_edit(monkeypatch, tool, args):
    seen = []
    def authorize(req, name, arguments):
        assert req == request()
        seen.append((name, arguments))
        assert name == tool and arguments == args
    adapter, client = setup(monkeypatch, authorize=authorize)
    async def call():
        decision = await client.hook("PreToolUse", tool_name=tool, tool_input=args)
        assert decision["hookSpecificOutput"]["permissionDecision"] == "allow"
        await client.hook("PostToolUse", tool_name=tool, tool_input=args)
    client.before_terminal = call
    result = asyncio.run(adapter.execute(request()))
    assert result.status == "completed" and result.task and result.review is None
    assert seen == [(tool, args)]
    assert set(client.options["tools"]) == {*base.READ_TOOLS, "Write", "Edit"}
    assert {"Bash", "Agent", "WebFetch"}.issubset(client.options["disallowed_tools"])
    assert result.sdk_execution["sandboxMode"] == "tool-restricted-workspace-write"
    assert result.sdk_execution["writeWorkspaceSha256"] == hashlib.sha256(b"/fixture/repo").hexdigest()
    assert ExecutionRequest.from_dict(request().to_dict()) == request()


@pytest.mark.parametrize("path", ["/outside/a.py", "../outside", "relative.py", "D:/work/example/a.py:stream", "D:/work/example/link/a.py"])
def test_host_scope_refusal_cannot_be_overridden(monkeypatch, path):
    args = {"file_path": path, "content": "x"}
    def deny(req, name, actual):
        assert actual == args
        raise PermissionError("fixture Host rejects target")
    adapter, client = setup(monkeypatch, authorize=deny)
    async def call():
        decision = await client.hook("PreToolUse", tool_name="Write", tool_input=args)
        assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
    client.before_terminal = call
    result = asyncio.run(adapter.execute(request()))
    assert result.status != "completed" and result.task is None


@pytest.mark.parametrize("tool", ["Bash", "NotebookEdit", "Agent", "WebFetch", "mcp__write"])
def test_unadmitted_tool_never_reaches_host(monkeypatch, tool):
    def unexpected(*_):
        pytest.fail("unsupported tool reached authority")
    adapter, client = setup(monkeypatch, authorize=unexpected)
    async def call():
        decision = await client.hook("PreToolUse", tool_name=tool)
        assert decision["hookSpecificOutput"]["permissionDecision"] == "deny"
    client.before_terminal = call
    result = asyncio.run(adapter.execute(request()))
    assert result.status != "completed"


@pytest.mark.parametrize("change", [{"role":"consultant"}, {"role":"architecture-reviewer"}, {"write_workspace":None}, {"result_kind":"review"}, {"tool_profile":"prompt-only"}])
def test_worker_wrong_request_before_factory(monkeypatch, change):
    adapter, client = setup(monkeypatch)
    with pytest.raises(ValueError):
        asyncio.run(adapter.execute(request(**change)))
    assert client.calls == []


def test_wrong_inventory_does_not_complete(monkeypatch):
    adapter, client = setup(monkeypatch)
    client.init_change["tools"].append("Bash")
    result = asyncio.run(adapter.execute(request()))
    assert result.status != "completed" and result.task is None


def test_cleanup_failure_preserves_task_without_completion(monkeypatch):
    adapter, client = setup(monkeypatch)
    client.close_error = True
    result = asyncio.run(adapter.execute(request()))
    assert result.task is not None and result.review is None
    assert result.status != "completed"

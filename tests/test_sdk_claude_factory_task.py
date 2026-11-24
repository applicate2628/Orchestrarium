"""Offline fixed-factory Consultant checks; no provider or account acceptance."""
import asyncio
from types import SimpleNamespace
from pathlib import Path
import pytest
import test_sdk_claude as base
from test_sdk_claude import instruction_capture_root
from test_sdk_claude_consultant import request, payload
from sdk_execution import claude, runtime
import provider_prompt


@pytest.mark.parametrize("deny", [None, "query", "tool", "account"])
def test_consultant_factory_reuses_parent_authority(tmp_path, monkeypatch, deny):
    selected = base.claude_selection(tmp_path,
        instructions=provider_prompt.assemble_external_prompt(b"Advice").decode())
    req = request()
    client = base.FakeClient()
    client.use_tool = True
    client.terminal_change["structured_output"] = payload()
    calls = []
    monkeypatch.setattr(runtime, "assert_current_launch", lambda *_: None)
    monkeypatch.setattr(runtime, "prepare_environment", lambda selection, source: (
        {"CLAUDE_CONFIG_DIR": selection.config_dir, "CLAUDE_PROMPTS_DIR": selection.prompts_dir}, object()))
    monkeypatch.setattr(claude.os, "environ", {"UNRELATED_SECRET": "not-forwarded"})
    def binding(options, *, cli_path):
        assert cli_path == selected.executable
        client.options = options
        client.instructions = Path(options["extra_args"]["append-system-prompt-file"]).read_text()
        client.calls.append("factory")
        return base.ClientBinding(client, base.SDK_VERSION)
    monkeypatch.setattr(claude, "_official_client_binding", binding)
    async def scenario():
        async def authorize(value, effect, context=None):
            assert value == req
            calls.append((effect, context))
            if effect == deny and (deny != "tool" or context is not None):
                raise PermissionError("private denial")
        async def record(_):
            pass
        adapter = claude.create_claude_adapter(req, SimpleNamespace(authorize=authorize, record=record), selected)
        assert type(adapter) is claude.ClaudeConsultantAdapter
        assert client.calls == [] and "UNRELATED_SECRET" not in claude.os.environ
        return await adapter.execute(req)
    observed = asyncio.run(scenario())
    assert observed.review is None
    if deny is None:
        assert observed.status == "completed" and observed.task.content == payload()["content"]
        assert [c["evidence"]["phase"] for e,c in calls if e == "account"] == ["before_connect", "initialize", "system_init"]
        assert any(e == "tool" and c and c["name"] == "Read" for e,c in calls)
    else:
        assert observed.status == "incomplete" and observed.task is None
        if deny == "account":
            assert client.calls == []
        else:
            assert "disconnect" in client.calls


@pytest.mark.parametrize("mode", ["claude-subscription-override", "unknown", "codex-auth-file"])
def test_factory_rejects_nonprogrammatic_before_environment(tmp_path, monkeypatch, mode):
    selected = base.claude_selection(tmp_path, auth_mode=mode)
    def forbidden(*_):
        pytest.fail("unadmitted route reached effects")
    monkeypatch.setattr(runtime, "assert_current_launch", forbidden)
    monkeypatch.setattr(runtime, "prepare_environment", forbidden)
    with pytest.raises(runtime.RuntimeBindingError, match="claude_programmatic_auth_mode_required"):
        claude.create_claude_adapter(request(), None, selected)

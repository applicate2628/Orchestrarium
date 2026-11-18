"""Real Kimi composition/receiving with synthetic ACP, not native policy acceptance."""
import asyncio
import json
from pathlib import Path
import tomllib

import pytest
from test_sdk_kimi import prepared, offline_owner, adapter, fixtures, owner
from test_agent_run_ledger import prepare_valid_work_item
from sdk_execution.kimi import KimiAcpAdapter


@pytest.mark.parametrize("nested,tools", [(False, []), (True, ["Read"])])
def test_distinct_cwd_uses_private_tool_upper_bound_and_receives_once(tmp_path, monkeypatch, nested, tools):
    item = prepare_valid_work_item(tmp_path)
    repository = tmp_path / "selected-project"
    (repository / ".git").mkdir(parents=True)
    selected = repository
    if nested:
        selected = repository / "nested-project"
        (selected / ".git").mkdir(parents=True)
    # Existing project profiles are preserved, not replaced by a run-dir file.
    profile = selected / ".kimi-code/agents/agent.md"
    profile.parent.mkdir(parents=True)
    profile.write_text("---\nname: fixture-project-agent\ntools: ['Read', 'Bash']\n---\nProject context.\n")
    original_profile = profile.read_bytes()
    capabilities = tmp_path / "capabilities.json"
    fixtures._write_kimi_capabilities(capabilities, cwd=selected, tools=tools)
    launch, request = prepared(tmp_path, monkeypatch, cwd=str(selected), extra_args=(
        "--kimi-capabilities-file", str(capabilities), "--ledger", str(item),
        "--ledger-artifact", "reviews/qa.md"))
    captured = []
    native_requests = []

    class Peer(fixtures._FakeKimiAcpPeer):
        def write_line(self, payload, **kwargs):
            message = json.loads(payload)
            if message.get("method") == "session/new":
                process = native_requests[0]
                environment = {row.name: row.value for row in process.environment}
                private_home = Path(environment["KIMI_CODE_HOME"])
                run_dir = Path(process.cwd)
                assert run_dir != selected and private_home.parent == run_dir
                assert message["params"]["cwd"] == str(selected)
                assert message["params"]["additionalDirectories"] == []
                assert not (run_dir / ".kimi-code/agents/agent.md").exists()
                config = tomllib.loads((private_home / "config.toml").read_text())
                assert config["tools"] == {"enabled": tools or ["Agent"], "disabled": ["Agent", "AgentSwarm"]}
                captured.append((run_dir, private_home, config))
            return super().write_line(payload, **kwargs)

    peer = Peer()
    native_requests, runners = offline_owner(monkeypatch, tmp_path, peer)
    monkeypatch.setattr(owner, "run_ledger", lambda runner, args: owner._ledger_owner().main(args) == 0)
    current = adapter(launch)
    result = asyncio.run(current.execute(request))
    assert result.status == "completed", result.to_dict()
    assert len(captured) == len(native_requests) == 1
    assert Path.cwd() == tmp_path
    assert profile.read_bytes() == original_profile
    assert not (captured[0][0] / ".kimi-code/agents/agent.md").exists()
    assert not (captured[0][1] / "config.toml").exists()
    methods = [row["method"] for row in peer.requests]
    assert methods.count("session/prompt") == 1
    assert methods[-2:] == ["session/close", "session/delete"]
    ledger = item / "agent-runs.jsonl"
    receipt = launch.control.terminal_receipt
    before = {path: path.read_bytes() for path in (ledger, receipt)}
    rows = [json.loads(line) for line in ledger.read_text().splitlines()]
    assert len(rows) == 2 and rows[-1]["eventKind"] == "terminal"
    assert rows[-1]["status"] == "completed" and rows[-1]["authorizing"] is False
    envelope = owner.parse_provider_result(receipt.read_text())
    assert envelope["selected"]["tools"] == tools
    assert envelope["selected"]["permission"] == "reject"
    def forbidden(*args, **kwargs):
        pytest.fail("received evidence recovery must not launch or rewrite")
    monkeypatch.setattr(owner, "launch", forbidden)
    recovered = KimiAcpAdapter(prevalidated=launch, assert_current=lambda *_: None, record=forbidden)
    first = recovered.reconcile_received(request, output_context=owner.ProviderOutputContext(()))
    assert first == recovered.reconcile_received(request, output_context=owner.ProviderOutputContext(()))
    assert before == {path: path.read_bytes() for path in before}
    assert len(native_requests) == 1

"""Pinned official auth metadata evidence only; no native authentication or launch.

xai-org/grok-build 2bdd1d6a6369de0e8c68132ea4539e9abd9e14a8:
agent/mvp_agent/mod.rs auth_response_with_meta; xai-grok-login/src/meta.rs,
model.rs. The response uses Debug AuthMode, not the selected ACP method ID.
"""
import json
import pytest
from test_sdk_grok import request, Peer, successful_frames
from sdk_execution.grok import GrokAcpExchange


@pytest.mark.parametrize("mode", ["WebLogin", "Oidc", "External", "ApiKey"])
def test_auth_mode_is_observed_not_account_identity(mode):
    frames = successful_frames()
    frames[1]["result"] = {"_meta": {"auth_mode": mode,
        "email": "unrelated@example.test", "team_id": "private-team-marker",
        "unknown_secret": "synthetic-private-marker"}}
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(), Peer(frames))
    observation = json.loads(result.observations[-1].payload_json)
    assert observation["selected"]["auth_method"] == "fixture-auth"
    assert observation["selected"]["account"] == "selected-account"
    assert observation["observed"]["auth_mode"] == mode
    assert observation["observed"]["account"] is None
    assert result.status == "incomplete" and result.execution_error is None
    exported = json.dumps(result.to_dict())
    for private in ("unrelated@example.test", "private-team-marker", "synthetic-private-marker"):
        assert private not in exported


@pytest.mark.parametrize("meta", [None, {}, [], "wrong", {"auth_mode": None},
    {"auth_mode": 5}, {"auth_mode": []}, {"auth_mode": {}},
    {"auth_mode": "FutureMode"}, {"auth_mode": "api_key"}, {"authMode": "ApiKey"}])
def test_unknown_optional_mode_does_not_add_an_auth_gate(meta):
    frames = successful_frames()
    frames[1]["result"] = {"_meta": meta}
    peer = Peer(frames)
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(), peer)
    observation = json.loads(result.observations[-1].payload_json)
    assert observation["observed"]["auth_mode"] is None
    assert observation["observed"]["account"] is None
    assert result.execution_error is None and result.protocol_closed
    assert any(row["method"] == "session/prompt" for row in peer.sent)


def test_failed_auth_does_not_invent_mode_or_replace_actual_error():
    frames = successful_frames()
    frames[1] = {"jsonrpc": "2.0", "id": 2, "error": {"code": -32000, "message": "private failure"}}
    peer = Peer(frames)
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(), peer)
    assert result.execution_error is not None
    assert result.execution_error != "grok_receiving_unavailable"
    assert json.loads(result.observations[-1].payload_json)["observed"]["auth_mode"] is None
    assert not any(row["method"] == "session/new" for row in peer.sent)
    assert "private failure" not in json.dumps(result.to_dict())

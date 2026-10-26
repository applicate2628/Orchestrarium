"""Offline source-shaped Grok ACP fixtures; never start a CLI or authenticate.

Sources (2026-10-24 research, not installed-runtime qualification):
https://agentclientprotocol.com/protocol/v1/session-config-options
https://agentclientprotocol.com/protocol/v1/schema#session-close
https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-shell/src/agent/session_config.rs
https://github.com/xai-org/grok-build/blob/main/crates/codegen/xai-grok-shell/src/agent/handlers/config_option.rs
Scalar params.value follows agent-client-protocol-schema 0.11.4 serde, not the
inconsistent nested-value example in Grok's agent-mode guide.
"""
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sdk_execution.contracts import ExecutionRequest
from sdk_execution.grok import GrokAcpExchange


def request(**changes):
    fields = dict(work_item_id="fixture", provider="grok", external_dispatch_id="dispatch",
                  external_evidence_run_id="evidence", artifact_id="artifact", role="qa-engineer",
                  model="grok-fixture", effort="high", cwd="/fixture", account_binding="selected-account",
                  prompt="Review fixture", coordinator_binding="coordinator", scope=("review",))
    return ExecutionRequest(**(fields | changes))


class Peer:
    def __init__(self, responses):
        self.responses = list(responses)
        self.sent = []
        self.cleanup = False

    def write_line(self, payload, **kwargs):
        self.sent.append(json.loads(payload))
        return len(payload)

    def read_line(self, **kwargs):
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return (json.dumps(item) + "\n").encode()

    def cancellation_requested(self):
        return False

    def begin_cleanup(self):
        self.cleanup = True


def response(number, result):
    return {"jsonrpc": "2.0", "id": number, "result": result}


def test_incompatible_protocol_stops_before_session_and_does_not_invent_readback():
    peer = Peer([response(1, {"protocolVersion": 9, "agentCapabilities": {}})])
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(), peer)
    assert [item["method"] for item in peer.sent] == ["initialize"]
    assert result.execution_error == "grok_protocol_incompatible"
    assert result.status == "incomplete"
    assert not result.protocol_closed
    assert result.cleanup_error == "grok_process_settlement_unavailable"
    observation = json.loads(result.observations[-1].payload_json)
    assert observation["selected"]["model"] == "grok-fixture"
    assert observation["observed"]["model"] is None
    assert observation["observed"]["account"] is None


def config(model="grok-fixture", effort="high"):
    return [{"id": "model", "name": "Model", "type": "select", "currentValue": model,
             "options": [{"value": "grok-fixture", "name": "Fixture"}]},
            {"id": "reasoning_effort", "name": "Reasoning Effort", "type": "select",
             "currentValue": effort, "options": [{"value": "high", "name": "High"}]}]


def successful_frames():
    return [response(1, {"protocolVersion": 1, "agentCapabilities": {"sessionCapabilities": {"close": {}}}, "authMethods": [{"id": "fixture-auth", "name": "Fixture"}]}),
            response(2, {}), response(3, {"sessionId": "session-fixture", "configOptions": config()}),
            response(4, {"configOptions": config()}), response(5, {"configOptions": config()}),
            {"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": "session-fixture",
             "update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "Native review"}}}},
            response(6, {"stopReason": "end_turn"}),
            response(7, {"_meta": {"x.ai/closeOutcome": "closed"}})]


def test_config_readback_text_and_close_are_not_account_or_process_settlement():
    peer = Peer(successful_frames())
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(), peer)
    assert [item["method"] for item in peer.sent] == ["initialize", "authenticate", "session/new", "session/set_config_option",
        "session/set_config_option", "session/prompt", "session/close"]
    assert peer.sent[3]["params"] == {"sessionId": "session-fixture", "configId": "model", "value": "grok-fixture"}
    assert peer.sent[4]["params"]["configId"] == "reasoning_effort"
    assert result.native_result_text == "Native review"
    assert result.provider_status == "completed"
    assert result.protocol_closed
    assert result.status == "incomplete"
    assert result.to_tool_output()["process_settlement"] == "not_established"
    observed = json.loads(result.observations[-1].payload_json)["observed"]
    assert observed == {"model": "grok-fixture", "effort": "high", "account": None}


import pytest


@pytest.mark.parametrize("close_result,closed", [({}, True), ({"_meta": {"x.ai/closeOutcome": "superseded"}}, False)])
def test_close_core_success_and_explicit_superseded_are_distinct(close_result, closed):
    frames = successful_frames()
    frames[-1] = response(7, close_result)
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(), Peer(frames))
    assert result.protocol_closed is closed


@pytest.mark.parametrize("options,outcome", [
    ([{"optionId": "never", "name": "Reject", "kind": "reject_once"}], {"outcome": "selected", "optionId": "never"}),
    ([{"optionId": "yes", "name": "Allow", "kind": "allow_once"}], {"outcome": "cancelled"}),
])
def test_permissions_never_approve(options, outcome):
    frames = successful_frames()
    frames.insert(5, {"jsonrpc": "2.0", "id": "permission", "method": "session/request_permission",
                      "params": {"sessionId": "session-fixture", "toolCall": {"toolCallId": "t"}, "options": options}})
    peer = Peer(frames)
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(), peer)
    reply = next(item for item in peer.sent if item.get("id") == "permission")
    assert reply["result"]["outcome"] == outcome
    assert result.native_result_text == "Native review"


def test_config_drift_during_prompt_is_not_completion_and_partial_text_survives():
    frames = successful_frames()
    frames.insert(6, {"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": "session-fixture",
        "update": {"sessionUpdate": "config_option_update", "configOptions": config(model="other")}}})
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(), Peer(frames))
    assert result.execution_error == "grok_config_mismatch"
    assert result.native_result_text == "Native review"
    assert result.status != "completed"


def test_cancel_notification_is_not_ack_until_cancelled_prompt_response():
    exchange = GrokAcpExchange(auth_method="fixture-auth")
    frames = successful_frames()
    frames[6] = response(6, {"stopReason": "cancelled"})
    class CancelPeer(Peer):
        def read_line(self, **kwargs):
            if self.sent[-1].get("method") == "session/prompt":
                exchange.cancel()
            return super().read_line(**kwargs)
    peer = CancelPeer(frames)
    result = exchange.run(request(), peer)
    assert [item for item in peer.sent if item.get("method") == "session/cancel"] == [
        {"jsonrpc": "2.0", "method": "session/cancel", "params": {"sessionId": "session-fixture"}}]
    assert exchange.cancel_acknowledged
    assert result.provider_status == "interrupted"
    assert result.status == "interrupted"
    assert peer.cleanup


def test_duplicate_permission_option_ids_cannot_select_an_approval():
    frames = successful_frames()
    frames.insert(5, {"jsonrpc": "2.0", "id": "permission", "method": "session/request_permission", "params": {
        "sessionId": "session-fixture", "toolCall": {"toolCallId": "t"}, "options": [
        {"optionId": "same", "name": "Reject", "kind": "reject_once"},
        {"optionId": "same", "name": "Allow", "kind": "allow_once"}]}})
    peer = Peer(frames)
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(), peer)
    assert next(item for item in peer.sent if item.get("id") == "permission")["result"]["outcome"] == {"outcome": "cancelled"}
    assert result.execution_error == "grok_invalid_permission_options"


def test_notification_flood_is_bounded_and_does_not_discard_acquired_text():
    frames = successful_frames()
    frames[6:6] = [{"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": "session-fixture",
        "update": {"sessionUpdate": "agent_thought_chunk", "content": {"type": "text", "text": "ignored"}}}}] * 12
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(max_events=8), Peer(frames))
    assert result.execution_error == "grok_event_limit"
    assert result.native_result_text == "Native review"


def test_auth_method_must_be_explicit_and_advertised_without_fallback():
    peer = Peer(successful_frames())
    result = GrokAcpExchange(auth_method="unadvertised").run(request(), peer)
    assert result.execution_error == "grok_auth_method_unavailable"
    assert [item["method"] for item in peer.sent] == ["initialize"]


def test_unavailable_close_capability_stops_before_authentication():
    frames = successful_frames()
    frames[0]["result"]["agentCapabilities"] = {}
    peer = Peer(frames)
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(), peer)
    assert result.execution_error == "grok_close_unavailable"
    assert len(peer.sent) == 1


def test_overlarge_chunk_preserves_bounded_prior_output_and_reports_failure():
    frames = successful_frames()
    frames.insert(6, {"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": "session-fixture",
        "update": {"sessionUpdate": "agent_message_chunk", "content": {"type": "text", "text": "x" * 4096}}}})
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(max_output_bytes=4096), Peer(frames))
    assert result.execution_error == "grok_output_limit"
    assert result.native_result_text == "Native review"


def test_tiny_evidence_budget_is_incomplete_not_an_unbounded_exception():
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(max_output_bytes=1), Peer(successful_frames()))
    assert result.status == "incomplete"
    assert result.observations == ()
    assert result.capture_error == "grok_evidence_limit"


def test_model_selection_may_change_available_effort_before_final_pair_is_required():
    frames = successful_frames()
    initial = config(effort="low")
    initial[1]["options"] = [{"value": "low", "name": "Low"}]
    frames[2]["result"]["configOptions"] = initial
    after_model = config(effort="low")
    after_model[1]["options"].append({"value": "low", "name": "Low"})
    frames[3]["result"]["configOptions"] = after_model
    frames.insert(3, {"jsonrpc": "2.0", "method": "session/update", "params": {"sessionId": "session-fixture",
        "update": {"sessionUpdate": "config_option_update", "configOptions": after_model}}})
    peer = Peer(frames)
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(), peer)
    assert result.execution_error is None
    assert result.native_result_text == "Native review"
    assert peer.sent[4]["params"]["configId"] == "reasoning_effort"


def test_standard_grouped_select_options_are_accepted_without_release_gate():
    frames = successful_frames()
    for frame in frames:
        for option in frame.get("result", {}).get("configOptions", []):
            option["options"] = [{"group": "recommended", "name": "Recommended", "options": option["options"]}]
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(), Peer(frames))
    assert result.execution_error is None
    assert result.protocol_closed


@pytest.mark.parametrize("stop_reason", [{}, [], None, "unknown"])
def test_invalid_terminal_preserves_native_result_and_cleanup(stop_reason):
    frames = successful_frames()
    frames[6]["result"]["stopReason"] = stop_reason
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(), Peer(frames))
    assert result.execution_error == "grok_invalid_stop_reason"
    assert result.native_result_text == "Native review"
    assert result.protocol_closed


def test_cleanup_cannot_extend_selected_event_budget():
    result = GrokAcpExchange(auth_method="fixture-auth").run(request(max_events=7), Peer(successful_frames()))
    assert result.native_result_text == "Native review"
    assert not result.protocol_closed

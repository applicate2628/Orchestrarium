"""Persistent decisions reuse native transcript custody, not native turn guesses."""
import asyncio
from dataclasses import replace
import json
import pytest
import test_sdk_claude_coordination as scoped
import test_sdk_child_choice as choice
from test_sdk_claude import instruction_capture_root
from test_sdk_claude_continuation_dispatch import TranscriptPeer
from sdk_execution.claude import transcript_snapshot
from sdk_execution.contracts import NativeContinuation, json_text
from sdk_execution.coordination import CoordinationInferenceRequest


def run(req, root, path):
    peer = TranscriptPeer(path, b"opaque native state\n")
    peer.terminal_change["structured_output"] = json.loads(choice.intent(req))
    instance, _ = scoped.adapter(peer)
    instance._config_dir = str(root)
    return asyncio.run(instance.execute(req)), peer


def test_persistent_scoped_decision_resumes_exact_transcript(tmp_path):
    req = scoped.request(decision_session_mode="native-persistent")
    path = tmp_path / "session.jsonl"
    first, peer = run(req, tmp_path, path)
    assert first.status == "completed"
    snapshot = transcript_snapshot(str(tmp_path), str(path))
    assert [o.payload_json for o in first.observations if o.kind == "native_transcript"] == [json_text(snapshot)]
    source = NativeContinuation(req.external_dispatch_id, req.external_evidence_run_id, "a" * 64,
        first.native_thread_id, first.native_turn_id, json_text(snapshot))
    second = replace(req, context_mode="continuation", native_continuation=source,
        external_dispatch_id="second-dispatch", external_evidence_run_id="second-evidence")
    assert CoordinationInferenceRequest.from_dict(second.to_dict()) == second
    result, resumed = run(second, tmp_path, path)
    assert result.status == "completed", result.execution_error
    assert result.native_thread_id == first.native_thread_id
    assert result.native_turn_id != first.native_turn_id
    assert resumed.options["resume"] == str(path)
    assert resumed.options["tools"] == [] and resumed.options["agents"] == {}
    assert resumed.options["continue_conversation"] is False
    assert result.sdk_execution["continuationSourceSha256"] == source.source_sha256


def test_changed_transcript_prevents_new_decision_without_fallback(tmp_path):
    req = scoped.request(decision_session_mode="native-persistent")
    path = tmp_path / "session.jsonl"
    first, _ = run(req, tmp_path, path)
    source = NativeContinuation(req.external_dispatch_id, req.external_evidence_run_id, "a" * 64,
        first.native_thread_id, first.native_turn_id, json_text(transcript_snapshot(str(tmp_path), str(path))))
    path.write_bytes(b"unexpected newer activity")
    second = replace(req, context_mode="continuation", native_continuation=source,
        external_dispatch_id="second-dispatch", external_evidence_run_id="second-evidence")
    result, peer = run(second, tmp_path, path)
    assert result.status == "incomplete" and result.intent_json is None
    assert "connect" not in peer.calls and "query" not in peer.calls


def test_persistent_claude_rejects_other_provider_native_proof():
    req = scoped.request(decision_session_mode="native-persistent")
    source = NativeContinuation("old-dispatch", "old-evidence", "a" * 64, "thread", "turn")
    with pytest.raises(ValueError, match="transcript commitment"):
        replace(req, context_mode="continuation", native_continuation=source)

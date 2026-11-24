"""Offline transcript custody and native SDK-shaped continuation, no model calls."""
import asyncio
from dataclasses import replace
from pathlib import Path
import pytest
import test_sdk_claude as base
import test_sdk_claude_consultant as advice
from test_sdk_claude import instruction_capture_root
from sdk_execution.claude import transcript_snapshot, continuation_transcript_path
from sdk_execution.contracts import NativeContinuation, json_text


def source(root, path):
    return NativeContinuation("old-dispatch", "old-evidence", "a" * 64, "native-session", "echoed-prompt", json_text(transcript_snapshot(str(root), str(path))))


def test_snapshot_roundtrip_and_append_refusal(tmp_path):
    path = tmp_path / "native.jsonl"
    path.write_bytes(b"opaque native transcript\n")
    prior = source(tmp_path, path)
    assert NativeContinuation.from_dict(prior.to_dict()) == prior
    assert continuation_transcript_path(str(tmp_path), prior) == str(path)
    path.write_bytes(path.read_bytes() + b"later activity\n")
    with pytest.raises(ValueError, match="transcript_changed"):
        continuation_transcript_path(str(tmp_path), prior)


@pytest.mark.parametrize("kind", ["outside", "hardlink", "replace"])
def test_snapshot_custody_rejected(tmp_path, kind):
    root = tmp_path / "config"
    root.mkdir()
    path = root / "native.jsonl"
    path.write_bytes(b"original")
    prior = source(root, path)
    if kind == "outside":
        (tmp_path / "outside").write_bytes(b"outside")
        with pytest.raises(ValueError):
            transcript_snapshot(str(root), str(tmp_path / "outside"))
        return
    if kind == "hardlink":
        (root / "alias").hardlink_to(path)
    else:
        path.rename(root / "old")
        path.write_bytes(b"original")
    with pytest.raises(ValueError):
        continuation_transcript_path(str(root), prior)


def test_completed_fresh_without_transcript_is_still_advice(monkeypatch, tmp_path):
    instance, client = advice.adapter(monkeypatch)
    instance._config_dir = str(tmp_path)
    result = asyncio.run(instance.execute(advice.request()))
    assert result.status == "completed"
    assert not any(o.kind == "native_transcript" for o in result.observations)


def test_completed_snapshot_is_after_disconnect(monkeypatch, tmp_path):
    path = tmp_path / "native.jsonl"
    path.write_bytes(b"initial")
    instance, client = advice.adapter(monkeypatch)
    instance._config_dir = str(tmp_path)
    client.hook_change["transcript_path"] = str(path)
    original = client.disconnect
    async def disconnect():
        await original()
        path.write_bytes(b"final after disconnect")
    client.disconnect = disconnect
    result = asyncio.run(instance.execute(advice.request()))
    assert result.status == "completed"
    proof = [o for o in result.observations if o.kind == "native_transcript"]
    assert len(proof) == 1
    assert proof[0].payload_json == json_text(transcript_snapshot(str(tmp_path), str(path)))


def test_resume_exactpath_currentness_recheck_prevents_connect(monkeypatch, tmp_path):
    path = tmp_path / "native.jsonl"
    path.write_bytes(b"original")
    prior = source(tmp_path, path)
    async def authority(req, phase):
        if phase == "connect":
            path.write_bytes(b"changed")
    instance, client = advice.adapter(monkeypatch, authority=authority)
    instance._config_dir = str(tmp_path)
    req = advice.request(context_mode="continuation", native_continuation=prior)
    result = asyncio.run(instance.execute(req))
    assert client.options["resume"] == str(path)
    assert client.options["session_id"] is None
    assert result.status == "incomplete" and "connect" not in client.calls
    assert client.calls.count("factory") == 1
    with pytest.raises(ValueError, match="consumed"):
        asyncio.run(instance.execute(req))


@pytest.mark.parametrize("changes", [{"context_mode":"fork"}, {"role":"reviewer", "result_kind":"review"}, {"write_workspace":"/fixture/repo"}])
def test_continuation_route_restrictions(tmp_path, changes):
    path = tmp_path / "native.jsonl"
    path.write_bytes(b"original")
    values = dict(context_mode="continuation", native_continuation=source(tmp_path, path))
    values.update(changes)
    with pytest.raises(ValueError):
        advice.request(**values)


def test_legacy_native_linkage_has_identical_wire_shape():
    prior = NativeContinuation("old-dispatch", "old-evidence", "a" * 64, "thread", "turn")
    req = advice.request(provider="codex", context_mode="continuation", native_continuation=prior)
    assert set(req.to_dict()["native_continuation"]) == {"prior_dispatch_id", "prior_evidence_run_id", "prior_request_sha256", "native_thread_id", "native_turn_id"}

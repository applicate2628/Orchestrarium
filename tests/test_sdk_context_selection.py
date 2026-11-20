"""Offline public context selection; no provider process, auth or model calls."""
from dataclasses import replace
import asyncio
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from sdk_execution import dispatch
from sdk_execution.contracts import ExecutionRequest, ExecutionResult
from test_sdk_dispatch import binding, fixture
from test_sdk_codex import adapter, request


def context_binding(mode, handoff=None):
    return dict(binding(), schemaVersion=3, installedHookRoot=None,
                contextMode=mode, contextHandoff=handoff)


@pytest.mark.parametrize("mode,handoff", [("fresh", None), ("handoff", "Accepted decision: use the existing owner.")])
def test_selected_context_survives_public_preparation_and_wire(tmp_path, monkeypatch, mode, handoff):
    selected, path, environment = fixture(tmp_path, monkeypatch)
    path.write_text(json.dumps(context_binding(mode, handoff)))
    operation = dispatch.prepare_dispatch(selected, path, source_environment=environment,
                                         cancellation_probe=lambda: False)
    value = operation.request
    assert value.context_mode == mode
    assert ExecutionRequest.from_dict(value.to_dict()) == value
    assert "Review fixture source only." in value.prompt
    if handoff:
        assert value.prompt.count(handoff) == 1
        assert "Selected context handoff" in value.prompt
    else:
        assert "Selected context handoff" not in value.prompt


@pytest.mark.parametrize("mode,handoff", [("fresh", "private history"), ("handoff", None),
    ("handoff", ""), ("handoff", 4), ("fork", None), ("resume", None), ("unknown", None)])
def test_invalid_or_unimplemented_context_never_becomes_fresh(tmp_path, mode, handoff):
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(context_binding(mode, handoff)))
    with pytest.raises(dispatch.DispatchError):
        dispatch.read_binding(path)


def test_legacy_binding_is_fresh_without_implicit_context(tmp_path, monkeypatch):
    selected, path, environment = fixture(tmp_path, monkeypatch)
    operation = dispatch.prepare_dispatch(selected, path, source_environment=environment,
                                         cancellation_probe=lambda: False)
    assert operation.request.context_mode == "fresh"
    assert "Selected context handoff" not in operation.request.prompt


def test_legacy_wire_stays_fresh_and_closed():
    old = request().to_dict()
    old.pop("context_mode", None)
    restored = ExecutionRequest.from_dict(old)
    assert restored.context_mode == "fresh"
    assert restored.to_dict() == old
    with pytest.raises(ValueError):
        ExecutionRequest.from_dict(dict(old, hidden_history="unexpected"))


def test_context_is_bound_in_request_and_returned_with_actual_result():
    selected = request(context_mode="handoff", prompt="Explicit selected task evidence only.")
    instance, client = adapter()
    result = asyncio.run(instance.execute(selected))
    assert result.status == "completed"
    assert result.request.context_mode == "handoff"
    assert ExecutionResult.from_dict(result.to_dict()).request == selected
    assert [row[2] for row in client.calls if row[0] == "turn_start"] == [selected.prompt]
    assert not any(row[0] == "thread_resume" for row in client.calls)
    assert replace(selected, context_mode="fresh") != selected

def test_legacy_coordination_preserves_exact_canonical_request():
    from sdk_execution.coordination import CoordinationInferenceRequest
    from test_sdk_coordination import request as coordination_request
    old = coordination_request().to_dict()
    old.pop("context_mode", None)
    restored = CoordinationInferenceRequest.from_dict(old)
    assert restored.context_mode == "fresh"
    assert restored.to_dict() == old

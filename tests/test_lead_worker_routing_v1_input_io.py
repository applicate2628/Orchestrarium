"""Input stream failures retain the public typed-denial contract."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
ENTRY = ROOT / "src.codex/skills/lead-worker-routing/scripts/resolve.py"


def _load():
    spec = importlib.util.spec_from_file_location("lead_worker_input_io", ENTRY)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("failure", [OSError, PermissionError, BlockingIOError])
def test_stdin_read_error_is_a_typed_nonauthorizing_denial(monkeypatch, capsys, failure):
    module = _load()

    class UnreadableStream:
        def read(self, limit):
            raise failure("private stream diagnostic must not enter the result")

    monkeypatch.setattr(module.sys, "stdin", SimpleNamespace(buffer=UnreadableStream()))
    status = module.main(["--request-file", "-"])
    captured = capsys.readouterr()
    assert status == 2
    assert captured.err == ""
    assert "private stream diagnostic" not in captured.out
    result = json.loads(captured.out)
    assert result["status"] == "denied"
    assert result["stableId"] == "E_LEAD_WORKER_V1_REQUEST_IO_FAILED"
    assert result["requestFingerprint"] is None
    assert result["selectedCandidate"] is None
    assert result["requiresAdapterAdmission"] is False
    assert result["executionAuthorized"] is False
    assert result["authorizing"] is False


def test_interruption_is_not_converted_to_an_input_error(monkeypatch, capsys):
    module = _load()

    class InterruptedStream:
        def read(self, limit):
            raise KeyboardInterrupt

    monkeypatch.setattr(module.sys, "stdin", SimpleNamespace(buffer=InterruptedStream()))
    with pytest.raises(KeyboardInterrupt):
        module.main(["--request-file", "-"])
    captured = capsys.readouterr()
    assert captured.out == captured.err == ""

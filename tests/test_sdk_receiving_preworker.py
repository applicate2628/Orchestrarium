"""Selected-only preworker receiving; local fixtures, never provider execution."""
from dataclasses import replace
import json
from pathlib import Path

import pytest

from test_sdk_runtime import fixture, claim
from sdk_execution import receiving, runtime
import provider_prompt


@pytest.fixture
def settled_run(tmp_path):
    request, selection = fixture(tmp_path)
    selection = claim(request, selection)
    terminal = runtime._settle_before_worker_failure(
        request, selection, started_at="2026-10-23T10:00:00Z")
    return runtime.RuntimeRun(request, selection, provider_prompt.ProviderOutputContext(()),
                              None, terminal, "selected_codex_hook_trust_unavailable")


def test_selected_only_failure_is_scanned_parsed_and_does_not_settle_again(settled_run, monkeypatch):
    run = settled_run
    ledger = Path(run.selection.work_item) / "agent-runs.jsonl"
    before = ledger.read_bytes()
    monkeypatch.setattr(runtime, "_settle_before_worker_failure", lambda *a, **k: pytest.fail("no settlement"))
    payload = receiving.preworker_failure_payload(run)
    assert provider_prompt.parse_provider_result(
        provider_prompt.SDK_RESULT_PREFIX + json.dumps(payload) + "\n") == payload
    assert ledger.read_bytes() == before
    assert payload["sdkExecution"] == runtime.selected_sdk_execution(run.request, run.selection)
    assert payload["status"] == "blocked" and payload["gate"] == "none"
    assert payload["exitCode"] == 1 and payload["cleanupStatus"] == "incomplete"
    assert payload["authorizing"] is False and payload["closesRunIds"] == []
    content = json.loads(payload["resultText"])
    assert content["workerInvoked"] is False
    assert content["exitCodeSource"] == "wrapper"
    assert not ({"process", "sdkVersion", "runtimeVersion", "reported_sdk_configuration"} & content.keys())
    assert "sdkVersion" not in payload["sdkExecution"]
    assert "runtimeVersion" not in payload["sdkExecution"]


@pytest.mark.parametrize("changes", [
    {"observation": object()}, {"terminal": None}, {"launch_error": None},
    {"launch_error": "raw exception with config=secret"}, {"output_context": None},
])
def test_missing_or_uncertain_runtime_result_is_rejected(settled_run, changes):
    with pytest.raises(ValueError):
        receiving.preworker_failure_payload(replace(settled_run, **changes))


@pytest.mark.parametrize("key,value", [
    ("eventKind", "launch"), ("status", "completed"), ("gate", "PASS"),
    ("runId", "other"), ("launchRunId", "other"), ("artifactIdentity", "other"),
    ("authorizing", True), ("scope", ["other"]), ("sdkExecution", {}),
])
def test_terminal_identity_or_outcome_drift_is_rejected(settled_run, key, value):
    with pytest.raises(ValueError):
        receiving.preworker_failure_payload(replace(
            settled_run, terminal={**settled_run.terminal, key: value}))


def test_changed_request_commitment_is_rejected(settled_run):
    with pytest.raises(ValueError):
        receiving.preworker_failure_payload(replace(
            settled_run, request=replace(settled_run.request, prompt="changed")))


def test_missing_durable_settlement_is_rejected(settled_run, monkeypatch):
    monkeypatch.setattr(provider_prompt, "read_back_external_terminal", lambda *a, **k: None)
    with pytest.raises(ValueError, match="readback"):
        receiving.preworker_failure_payload(settled_run)


def test_full_payload_is_auth_context_scanned(settled_run):
    secret = settled_run.request.model.encode()
    with pytest.raises(ValueError, match="CREDENTIAL_ECHO"):
        receiving.preworker_failure_payload(replace(
            settled_run, output_context=provider_prompt.ProviderOutputContext((secret,))))


def test_parser_failure_is_not_ignored(settled_run, monkeypatch):
    def reject(_line):
        raise ValueError("synthetic_parser_failure")
    monkeypatch.setattr(provider_prompt, "parse_provider_result", reject)
    with pytest.raises(ValueError):
        receiving.preworker_failure_payload(settled_run)

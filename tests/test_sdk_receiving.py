"""Synthetic adapter/process pairing through real canonical ledger receiving.

These fixtures never construct a vendor client and do not prove OS containment.
"""
from __future__ import annotations

import dataclasses
import json
import secrets
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from process_supervision import process_runner as processes
from process_supervision.sdk_worker import run_sdk_worker
from sdk_execution.contracts import ExecutionRequest, ExecutionResult, ReviewResult, Finding, json_text
from sdk_execution.receiving import receive_terminal, terminal_payload
from sdk_execution.worker import encode_frame
from provider_prompt import ProviderOutputContext
from test_agent_run_ledger import prepare_valid_work_item, run_ledger
from test_sdk_ledger import SDK_CONFIG, LAUNCH_ID, TERMINAL_ID, create_fixture_symlink, sdk_launch_args


def fixture_request(item):
    return ExecutionRequest(
        provider="codex", work_item_id=item.name, external_dispatch_id=LAUNCH_ID,
        external_evidence_run_id=TERMINAL_ID, artifact_id="sha256:" + "c" * 64,
        role="qa-engineer", model=SDK_CONFIG["model"], effort=SDK_CONFIG["effort"],
        cwd=str(item), account_binding=SDK_CONFIG["accountBinding"], prompt="Review fixture.",
        coordinator_binding="fixture-coordinator", scope=("synthetic repository review",),
    )


def synthetic_observation(monkeypatch, request, *, alter_process=None, review=None, runtime_selection=None, sdk_config=None, usage=None):
    result = ExecutionResult(
        request=request, status="completed", provider_status="completed",
        native_thread_id="fixture-thread", native_turn_id="fixture-turn",
        usage_json=json_text(usage) if usage is not None else None,
        sdk_execution_json=json_text(sdk_config if sdk_config is not None else {**SDK_CONFIG, "model": request.model, "effort": request.effort, "accountBinding": request.account_binding}), protocol_closed=True,
        review=review or ReviewResult(request.external_evidence_run_id, request.artifact_id, request.role, "PASS", ()),
    )
    with processes.ProcessRunnerV1() as owner:
        def simulated_run(process_request, *, dialogue):
            frames = iter([encode_frame({"kind": "result", "result": result.to_dict()})])
            class Channel:
                def write_line(self, value):
                    pass
                def read_line(self):
                    value = next(frames, None)
                    if value is None:
                        raise EOFError()
                    return value
            dialogue.handler(Channel())
            failed = processes._request_failure(
                process_request, processes.ProcessSupervisionError("PSV1-INTERNAL", "execution"),
                time.monotonic(),
            )
            clean = dataclasses.replace(
                failed, outcome="success", terminal_stage="completed", failure_id=None,
                target_exit_code=0, resources_closed=True, policy_id="sdk-worker-v1",
                tree=processes.TreeObservationV1("synthetic", True, "EMPTY", True, True, True, True),
            )
            return alter_process(clean) if alter_process else clean
        monkeypatch.setattr(owner, "run", simulated_run)
        return run_sdk_worker(
            owner, request, environment=(), deadline_monotonic=time.monotonic() + 10,
            job_memory_limit_bytes=256 * 1024 * 1024, runtime_selection=runtime_selection,
            authority=lambda request, effect: None,  # Synthetic owner; no provider is constructed.
        )


@pytest.fixture
def windows_review_text_newlines(monkeypatch):
    """Exercise Windows default text translation even when pytest runs on POSIX."""
    original_open = Path.open

    def open_artifact(path, mode="r", buffering=-1, encoding=None, errors=None, newline=None):
        if mode == "w" and newline is None and path.parts[-2:] == ("reviews", "qa.md"):
            newline = "\r\n"
        return original_open(path, mode, buffering, encoding, errors, newline)

    monkeypatch.setattr(Path, "open", open_artifact)


def test_exact_review_result_settles_real_ledger_and_replays(monkeypatch, tmp_path, windows_review_text_newlines):
    item = prepare_valid_work_item(tmp_path)
    admitted = run_ledger(item, *sdk_launch_args())
    assert admitted.returncode == 0, admitted.stdout + admitted.stderr
    request = fixture_request(item)
    observation = synthetic_observation(monkeypatch, request)
    payload = terminal_payload(request, observation, output_context=ProviderOutputContext(()),
                               admitted_sdk_execution=SDK_CONFIG)
    assert payload["sdkExecution"]["schemaVersion"] == 1
    assert json.loads(payload["resultText"]) == observation.result.review.to_dict()
    artifact = item / "reviews/qa.md"
    artifact.write_bytes((json_text(observation.result.review.to_dict()) + "\n").encode("utf-8"))
    options = dict(artifact="reviews/qa.md", started_at="2026-10-23T10:01:00Z",
                   updated_at="2026-10-23T10:01:00Z", ledger_max_events=100, ledger_max_bytes=1048576, output_context=ProviderOutputContext(()))
    terminal = receive_terminal(item, request, observation, **options)
    assert terminal["authorizing"] is False
    assert terminal["actualExecutionPath"] == "direct-external-sdk"
    before = (item / "agent-runs.jsonl").read_bytes()
    assert receive_terminal(item, request, observation, **options) == terminal
    assert (item / "agent-runs.jsonl").read_bytes() == before


@pytest.mark.parametrize("change", [
    {"resources_closed": False}, {"cleanup_uncertain": True}, {"policy_id": "unrelated"},
])
def test_unsettled_or_unrelated_process_cannot_create_success(monkeypatch, tmp_path, change):
    item = prepare_valid_work_item(tmp_path)
    request = fixture_request(item)
    observation = synthetic_observation(monkeypatch, request, alter_process=lambda p: dataclasses.replace(p, **change))
    with pytest.raises(ValueError):
        terminal_payload(request, observation, output_context=ProviderOutputContext(()))


def test_changed_admission_is_rejected_before_ledger_write(monkeypatch, tmp_path, windows_review_text_newlines):
    item = prepare_valid_work_item(tmp_path)
    assert run_ledger(item, *sdk_launch_args()).returncode == 0
    request = fixture_request(item)
    observation = synthetic_observation(monkeypatch, dataclasses.replace(request, artifact_id="changed-artifact"))
    artifact = item / "reviews/qa.md"
    artifact.write_bytes((json_text(observation.result.review.to_dict()) + "\n").encode("utf-8"))
    before = (item / "agent-runs.jsonl").read_bytes()
    with pytest.raises(ValueError, match="admitted launch"):
        receive_terminal(item, observation.request, observation, artifact="reviews/qa.md",
                         started_at="2026-10-23T10:01:00Z", updated_at="2026-10-23T10:01:00Z",
                         ledger_max_events=100, ledger_max_bytes=1048576, output_context=ProviderOutputContext(()))
    assert (item / "agent-runs.jsonl").read_bytes() == before


@pytest.mark.parametrize("change", [{"target_exit_code": 1}, {"cancelled": True}, {"timed_out": True}])
def test_settled_failure_is_nonauthorizing_blocked_evidence(monkeypatch, tmp_path, change):
    request = fixture_request(prepare_valid_work_item(tmp_path))
    observation = synthetic_observation(monkeypatch, request, alter_process=lambda p: dataclasses.replace(p, **change))
    payload = terminal_payload(request, observation, output_context=ProviderOutputContext(()))
    assert payload["status"] == "blocked"
    assert payload["gate"] == "none"
    assert payload["authorizing"] is False
    assert payload["primaryOutcome"]["exitCode"] == observation.process.target_exit_code


def test_exact_auth_secret_is_scanned_without_recognizable_label(monkeypatch, tmp_path):
    request = fixture_request(prepare_valid_work_item(tmp_path))
    secret = secrets.token_urlsafe(24)  # Unregistered per-test scan needle.
    review = ReviewResult(request.external_evidence_run_id, request.artifact_id, request.role, "REVISE",
                          (Finding("low", "source.py", 1, "Review evidence", secret),))
    observation = synthetic_observation(monkeypatch, request, review=review)
    with pytest.raises(ValueError, match="CREDENTIAL_ECHO"):
        terminal_payload(request, observation, output_context=ProviderOutputContext((secret.encode(),)))


def test_receiving_requires_explicit_auth_output_context(monkeypatch, tmp_path):
    request = fixture_request(prepare_valid_work_item(tmp_path))
    observation = synthetic_observation(monkeypatch, request)
    with pytest.raises(ValueError, match="auth-owner"):
        terminal_payload(request, observation, output_context=None)


def test_received_request_commitment_uses_retained_runtime_selection(monkeypatch, tmp_path):
    from test_sdk_runtime import fixture
    from sdk_execution.runtime import selected_sdk_execution
    request, selection = fixture(tmp_path)
    observed = synthetic_observation(monkeypatch, request, runtime_selection=selection.to_dict())
    selected = selected_sdk_execution(request, selection)
    payload = terminal_payload(request, observed, output_context=ProviderOutputContext(()), admitted_sdk_execution=selected)
    assert payload["gate"] == "PASS"
    assert payload["sdkExecution"]["requestSha256"] == selected["requestSha256"]


@pytest.mark.parametrize("change", [{"prompt": "different task"}, {"cwd": "/different"},
                                    {"coordinator_binding": "different-coordinator"}])
def test_commitment_rejects_changed_request_even_with_same_ids_profile_scope(monkeypatch, tmp_path, change):
    from test_sdk_runtime import fixture
    from sdk_execution.runtime import selected_sdk_execution
    original, selection = fixture(tmp_path)
    changed = dataclasses.replace(original, **change)
    observed = synthetic_observation(monkeypatch, changed, runtime_selection=selection.to_dict())
    with pytest.raises(ValueError, match="commitment mismatch"):
        terminal_payload(changed, observed, output_context=ProviderOutputContext(()),
                         admitted_sdk_execution=selected_sdk_execution(original, selection))


def test_declared_commitment_without_retained_selection_is_not_accepted(monkeypatch, tmp_path):
    from test_sdk_runtime import fixture
    from sdk_execution.runtime import selected_sdk_execution
    request, selection = fixture(tmp_path)
    observed = synthetic_observation(monkeypatch, request)
    with pytest.raises(ValueError, match="no retained selection"):
        terminal_payload(request, observed, output_context=ProviderOutputContext(()),
                         admitted_sdk_execution=selected_sdk_execution(request, selection))


def runtime_run_fixture(monkeypatch, tmp_path, *, context=None, alter_process=None, review=None, sdk_config=None):
    from test_sdk_runtime import fixture, claim
    from sdk_execution.runtime import RuntimeRun
    request, selection = fixture(tmp_path)
    selection = claim(request, selection)
    observed = synthetic_observation(monkeypatch, request, runtime_selection=selection.to_dict(),
                                     alter_process=alter_process, review=review, sdk_config=sdk_config)
    return RuntimeRun(request, selection, context or ProviderOutputContext(()), observed)


def receive_options():
    return dict(artifact="reviews/sdk-evidence.json", started_at="2026-10-23T10:01:00Z",
                updated_at="2026-10-23T10:01:00Z")


def test_runtime_receiving_owns_materialization_and_actual_ledger(monkeypatch, tmp_path):
    from sdk_execution.receiving import receive_runtime_run
    run = runtime_run_fixture(monkeypatch, tmp_path)
    terminal = receive_runtime_run(run, **receive_options())
    assert terminal["gate"] == "PASS"
    assert terminal["authorizing"] is False
    artifact = Path(run.selection.work_item) / receive_options()["artifact"]
    assert json.loads(artifact.read_text()) == {
        "review": run.observation.result.review.to_dict(),
        "reported_sdk_configuration": run.observation.result.sdk_execution,
    }
    owner = __import__("provider_prompt")
    readback = owner.read_back_external_terminal(
        owner.Control(ledger=run.selection.work_item, ledger_max_events=100, ledger_max_bytes=1048576),
        "codex", run.request.external_dispatch_id)
    assert readback == terminal


def test_observed_versions_are_unpinned_retained_scanned_and_artifact_bound(monkeypatch, tmp_path):
    import hashlib
    from sdk_execution import runtime
    from sdk_execution.receiving import receive_runtime_run
    from test_sdk_runtime import fixture, claim
    request, selection = fixture(tmp_path)
    selection = claim(request, selection)
    reported = {**SDK_CONFIG, "model": request.model, "accountBinding": request.account_binding,
                "sdkVersion": "2!11.2.0+vendor", "runtimeVersion": "34.5.0-preview+build"}
    observed = synthetic_observation(monkeypatch, request, runtime_selection=selection.to_dict(), sdk_config=reported)
    run = runtime.RuntimeRun(request, selection, ProviderOutputContext(()), observed)
    terminal = receive_runtime_run(run, **receive_options())
    assert terminal["gate"] == "PASS"
    assert terminal["sdkExecution"] == runtime.selected_sdk_execution(request, selection)
    raw = (Path(selection.work_item) / receive_options()["artifact"]).read_bytes()
    assert json.loads(raw)["reported_sdk_configuration"] == reported
    assert terminal["artifactRevision"] == hashlib.sha256(raw).hexdigest()
    assert terminal["artifactSizeBytes"] == len(raw)
    from test_agent_run_ledger import run_validator
    assert run_validator(Path(selection.work_item)).returncode == 0
    # Replay uses the exact already-retained bytes and does not spend a new run.
    before = (Path(selection.work_item) / "agent-runs.jsonl").read_bytes()
    assert receive_terminal(Path(selection.work_item), request, observed,
                            **receive_options(), ledger_max_events=100, ledger_max_bytes=1048576,
                            output_context=run.output_context) == terminal
    assert (Path(selection.work_item) / "agent-runs.jsonl").read_bytes() == before


@pytest.mark.parametrize("field,value", [
    ("adapter", "claude-agent-sdk"), ("model", "other-model"), ("effort", "low"),
    ("sandboxMode", "tool-restricted-read-only"), ("approvalPolicy", "deny_unadmitted"),
    ("accountBinding", "other-account"), ("unknown", "value"),
    ("sdkVersion", ""), ("runtimeVersion", None), ("runtimeVersion", "has whitespace"),
    ("requestSha256", "a" * 64),
])
def test_versionless_admission_does_not_weaken_observed_profile_checks(monkeypatch, tmp_path, field, value):
    from test_sdk_runtime import fixture
    from sdk_execution.runtime import selected_sdk_execution
    request, selection = fixture(tmp_path)
    reported = {**SDK_CONFIG, "model": request.model, "accountBinding": request.account_binding, field: value}
    observed = synthetic_observation(monkeypatch, request, runtime_selection=selection.to_dict(), sdk_config=reported)
    payload = terminal_payload(request, observed, output_context=ProviderOutputContext(()),
                               admitted_sdk_execution=selected_sdk_execution(request, selection))
    assert payload["status"] == "blocked" and payload["gate"] == "none"
    assert json.loads(payload["resultText"])["reported_sdk_configuration"] == reported


@pytest.mark.parametrize("missing", ["sdkVersion", "runtimeVersion"])
def test_versionless_admission_still_requires_actual_observed_versions(monkeypatch, tmp_path, missing):
    from test_sdk_runtime import fixture
    from sdk_execution.runtime import selected_sdk_execution
    request, selection = fixture(tmp_path)
    reported = {**SDK_CONFIG, "model": request.model, "accountBinding": request.account_binding}
    del reported[missing]
    observed = synthetic_observation(monkeypatch, request, runtime_selection=selection.to_dict(), sdk_config=reported)
    payload = terminal_payload(request, observed, output_context=ProviderOutputContext(()),
                               admitted_sdk_execution=selected_sdk_execution(request, selection))
    assert payload["status"] == "blocked"


def test_selected_profile_cannot_impersonate_an_observed_profile(monkeypatch, tmp_path):
    from test_sdk_runtime import fixture
    from sdk_execution.runtime import selected_sdk_execution
    request, selection = fixture(tmp_path)
    selected = selected_sdk_execution(request, selection)
    observed = synthetic_observation(monkeypatch, request, runtime_selection=selection.to_dict(), sdk_config=selected)
    payload = terminal_payload(request, observed, output_context=ProviderOutputContext(()), admitted_sdk_execution=selected)
    assert payload["status"] == "blocked"


def test_observed_version_secret_is_scanned_before_artifact_creation(monkeypatch, tmp_path):
    from test_sdk_runtime import fixture, claim
    from sdk_execution.runtime import RuntimeRun
    from sdk_execution.receiving import receive_runtime_run
    request, selection = fixture(tmp_path)
    selection = claim(request, selection)
    secret = secrets.token_urlsafe(24)  # Unregistered per-test scan needle.
    reported = {**SDK_CONFIG, "model": request.model, "accountBinding": request.account_binding,
                "runtimeVersion": secret}
    observed = synthetic_observation(monkeypatch, request, runtime_selection=selection.to_dict(), sdk_config=reported)
    run = RuntimeRun(request, selection, ProviderOutputContext((secret.encode(),)), observed)
    before = (Path(selection.work_item) / "agent-runs.jsonl").read_bytes()
    with pytest.raises(ValueError, match="CREDENTIAL_ECHO"):
        receive_runtime_run(run, **receive_options())
    assert not (Path(selection.work_item) / receive_options()["artifact"]).exists()
    assert (Path(selection.work_item) / "agent-runs.jsonl").read_bytes() == before


def test_runtime_receiving_preserves_existing_artifact(monkeypatch, tmp_path):
    from sdk_execution.receiving import receive_runtime_run
    run = runtime_run_fixture(monkeypatch, tmp_path)
    artifact = Path(run.selection.work_item) / receive_options()["artifact"]
    artifact.write_bytes(b"existing evidence\n")
    ledger = Path(run.selection.work_item) / "agent-runs.jsonl"
    before = ledger.read_bytes()
    with pytest.raises(ValueError, match="RECEIPT_EXISTS"):
        receive_runtime_run(run, **receive_options())
    assert artifact.read_bytes() == b"existing evidence\n"
    assert ledger.read_bytes() == before


def test_runtime_receiving_unsettled_result_writes_nothing(monkeypatch, tmp_path):
    from sdk_execution.receiving import receive_runtime_run
    run = runtime_run_fixture(monkeypatch, tmp_path,
                              alter_process=lambda p: dataclasses.replace(p, cleanup_uncertain=True))
    with pytest.raises(ValueError, match="settlement unavailable"):
        receive_runtime_run(run, **receive_options())
    assert not (Path(run.selection.work_item) / receive_options()["artifact"]).exists()


def test_runtime_receiving_scans_before_artifact_creation(monkeypatch, tmp_path):
    from sdk_execution.receiving import receive_runtime_run
    # Exact-value scanning must also cover ordinary public-looking content.
    run = runtime_run_fixture(monkeypatch, tmp_path, context=ProviderOutputContext((b"PASS",)))
    with pytest.raises(ValueError, match="CREDENTIAL_ECHO"):
        receive_runtime_run(run, **receive_options())
    assert not (Path(run.selection.work_item) / receive_options()["artifact"]).exists()


def test_runtime_receiving_retains_acquired_artifact_when_ledger_fails(monkeypatch, tmp_path):
    import sdk_execution.receiving as receiving
    run = runtime_run_fixture(monkeypatch, tmp_path)
    def fail(*args, **kwargs):
        raise ValueError("synthetic receiving failure")
    monkeypatch.setattr(receiving, "receive_terminal", fail)
    with pytest.raises(ValueError, match="synthetic receiving failure"):
        receiving.receive_runtime_run(run, **receive_options())
    assert json.loads((Path(run.selection.work_item) / receive_options()["artifact"]).read_text()) == {
        "review": run.observation.result.review.to_dict(),
        "reported_sdk_configuration": run.observation.result.sdk_execution,
    }
    assert run.observation.result.review.verdict == "PASS"


@pytest.mark.parametrize("artifact", ["../outside.json", "/outside.json", "",
    r"\outside\evidence.json", r"C:relative.json", r"C:\outside\evidence.json",
    r"\\server\share\evidence.json"])
def test_runtime_receiving_rejects_nonlocal_artifact(monkeypatch, tmp_path, artifact):
    from sdk_execution.receiving import receive_runtime_run
    run = runtime_run_fixture(monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="work-item relative"):
        receive_runtime_run(run, **{**receive_options(), "artifact": artifact})


def test_runtime_receiving_rejects_external_link_before_reservation(monkeypatch, tmp_path):
    from sdk_execution.receiving import receive_runtime_run
    run = runtime_run_fixture(monkeypatch, tmp_path)
    outside = tmp_path / "unrelated-directory"
    outside.mkdir()
    create_fixture_symlink(Path(run.selection.work_item) / "external-link", outside, target_is_directory=True)
    with pytest.raises(ValueError, match="outside work item"):
        receive_runtime_run(run, **{**receive_options(), "artifact": "external-link/evidence.json"})
    assert not (outside / "evidence.json").exists()


def test_runtime_receipt_closes_before_independent_receiving(monkeypatch, tmp_path):
    import sdk_execution.receiving as receiving
    import provider_prompt as owner
    run = runtime_run_fixture(monkeypatch, tmp_path)
    original = owner.TerminalReceiptV1.reserve
    live = set()
    class ObservedReceipt:
        def __init__(self, receipt):
            self.receipt = receipt
        def __enter__(self):
            live.add(id(self))
            self.receipt.__enter__()
            return self.receipt
        def __exit__(self, *args):
            try:
                return self.receipt.__exit__(*args)
            finally:
                live.remove(id(self))
    monkeypatch.setattr(owner.TerminalReceiptV1, "reserve", lambda path: ObservedReceipt(original(path)))
    receive = receiving.receive_terminal
    def independent_read(*args, **kwargs):
        assert not live, "exclusive receipt writer must be closed before readback"
        return receive(*args, **kwargs)
    monkeypatch.setattr(receiving, "receive_terminal", independent_read)
    assert receiving.receive_runtime_run(run, **receive_options())["gate"] == "PASS"


def test_claude_runtime_commitment_and_actual_receiving_roundtrip(monkeypatch, tmp_path):
    from test_sdk_runtime import fixture, claim
    from sdk_execution import runtime
    from sdk_execution.claude import ClaudeRuntimeSelection
    from sdk_execution.receiving import receive_runtime_run
    request, codex_selection = fixture(tmp_path)
    request = dataclasses.replace(request, provider="claude", model="claude-sonnet-4-6")
    selection = ClaudeRuntimeSelection(
        executable=codex_selection.executable, executable_sha256=codex_selection.executable_sha256,
        config_dir=codex_selection.codex_home, auth_mode="claude-direct",
        instructions=__import__("provider_prompt").assemble_external_prompt(b"Claude fixture instructions").decode(),
        prompts_dir=str(tmp_path / "private-prompts"), work_item=codex_selection.work_item,
        ledger_max_events=100, ledger_max_bytes=1048576, job_memory_limit_bytes=256 * 1024 * 1024,
    )
    selection = claim(request, selection)
    selected = runtime.selected_sdk_execution(request, selection)
    reported = {**{key: value for key, value in selected.items() if key != "requestSha256"},
                "schemaVersion": 1, "sdkVersion": "9.1.0", "runtimeVersion": "12.2.0"}
    observed = synthetic_observation(monkeypatch, request, runtime_selection=selection.to_dict(), sdk_config=reported)
    run = runtime.RuntimeRun(request, selection, ProviderOutputContext(()), observed)
    terminal = receive_runtime_run(run, **receive_options())
    assert terminal["provider"] == "claude"
    assert terminal["sdkExecution"] == selected
    assert terminal["gate"] == "PASS" and terminal["authorizing"] is False
    artifact = json.loads((Path(selection.work_item) / receive_options()["artifact"]).read_text())
    assert artifact["reported_sdk_configuration"] == reported
    changed = dataclasses.replace(selection, config_dir=str(tmp_path / "different-config"))
    with pytest.raises(ValueError, match="commitment mismatch"):
        terminal_payload(request, observed, output_context=run.output_context,
                         admitted_sdk_execution=runtime.selected_sdk_execution(request, changed))


@pytest.mark.parametrize("usage,needle,error", [
    ({"extra": "synthetic-sensitive-value"}, b"synthetic-sensitive-value", "CREDENTIAL_ECHO"),
    ({"extra": "Q:/private/session"}, b"", "MACHINE_PATH_ECHO"),
])
def test_successful_usage_is_scanned_before_public_artifact(monkeypatch, tmp_path, usage, needle, error):
    from test_sdk_runtime import fixture, claim
    from sdk_execution.runtime import RuntimeRun
    from sdk_execution.receiving import receive_runtime_run
    request, selection = fixture(tmp_path)
    selection = claim(request, selection)
    observed = synthetic_observation(monkeypatch, request, runtime_selection=selection.to_dict(), usage=usage)
    context = ProviderOutputContext((needle,) if needle else ())
    run = RuntimeRun(request, selection, context, observed)
    ledger = Path(selection.work_item) / "agent-runs.jsonl"
    before = ledger.read_bytes()
    with pytest.raises(ValueError, match=error):
        receive_runtime_run(run, **receive_options())
    assert not (Path(selection.work_item) / receive_options()["artifact"]).exists()
    assert ledger.read_bytes() == before
    assert run.observation.result.usage == usage


def test_safe_usage_survives_exact_export_scan(monkeypatch, tmp_path):
    from sdk_execution.receiving import scan_execution_output
    request = fixture_request(prepare_valid_work_item(tmp_path))
    observed = synthetic_observation(monkeypatch, request, usage={"input_tokens": 12, "output_tokens": 8})
    scan_execution_output(observed.result, ProviderOutputContext(()))
    assert observed.result.to_tool_output()["usage"] == {"input_tokens": 12, "output_tokens": 8}


def test_tool_output_scan_unavailable_cannot_export(monkeypatch, tmp_path):
    from sdk_execution.receiving import scan_execution_output
    import provider_prompt as owner
    request = fixture_request(prepare_valid_work_item(tmp_path))
    observed = synthetic_observation(monkeypatch, request)
    def unavailable(*args, **kwargs):
        raise OSError("synthetic scanner failure")
    monkeypatch.setattr(owner, "provider_output_safety_scan_terminal", unavailable)
    with pytest.raises(ValueError, match="E_EXTERNAL_PROVIDER_OUTPUT_SCAN_UNAVAILABLE"):
        scan_execution_output(observed.result, ProviderOutputContext(()))

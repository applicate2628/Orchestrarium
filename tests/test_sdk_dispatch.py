"""Offline bridge constraints; no native/provider process or network is invoked."""
from dataclasses import replace
import json
from pathlib import Path
import sys
import types

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import provider_prompt as owner
from sdk_execution import dispatch, runtime, receiving
from test_agent_run_ledger import prepare_valid_work_item


def binding():
    return dict(schemaVersion=1, accountBinding="fixture-account", expectedAccountEmail=None,
                coordinatorBinding="fixture-host-invocation", scope=["review fixture source"],
                artifactIdentity="fixture-review", maxEvents=100, jobMemoryLimitBytes=268435456)


def fixture(tmp_path, monkeypatch, **changes):
    # Explicitly simulate supported-platform preflight only; never run native code.
    monkeypatch.setattr(dispatch, "_require_supported_platform", lambda: None)
    item = prepare_valid_work_item(tmp_path)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Review fixture source only.")
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(binding()))
    executable = tmp_path / "fixture.exe"
    executable.write_bytes(b"never execute this file")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(owner, "_resolve_launch_provider_command", lambda *a: ([str(executable)], None))
    monkeypatch.setattr(owner, "resolve_provider_auth_configuration", lambda *a: types.SimpleNamespace(mode="codex-api-key"))
    control = owner.Control(topic="fixture", prompt_file=prompt, terminal_receipt=tmp_path / "receipt.json",
                            ledger=str(item), ledger_role="qa-engineer", ledger_role_explicit=True,
                            ledger_artifact="sdk-review.json", ledger_max_events=100,
                            ledger_max_bytes=1048576)
    for k, v in changes.items():
        setattr(control, k, v)
    flags, model, effort = owner.resolved_profile("codex", control.provider_flags)
    selected = owner.PolicyBoundLaunch(control, "fixture", tuple(flags), model, effort,
                                       owner.external_role_provenance(control, "codex"), None)
    return selected, path, dict(CODEX_HOME=str(home))


def prepare(tmp_path, monkeypatch, **changes):
    selected, path, environment = fixture(tmp_path, monkeypatch, **changes)
    return dispatch.prepare_dispatch(selected, path, source_environment=environment,
                                     cancellation_probe=lambda: False)


def test_binding_is_closed_nonsecret_data_contract(tmp_path):
    path = tmp_path / "input.json"
    path.write_text(json.dumps(binding()))
    assert dispatch.read_binding(path) == binding()
    for field in ("approved", "callback", "executable", "codexHome", "configOverrides", "ledgerMaxEvents", "mcpScope"):
        path.write_text(json.dumps({**binding(), field: True}))
        with pytest.raises(dispatch.DispatchError, match="BINDING_INVALID"):
            dispatch.read_binding(path)
    path.write_text('{"schemaVersion":1,"schemaVersion":1}')
    with pytest.raises(dispatch.DispatchError):
        dispatch.read_binding(path)


@pytest.mark.parametrize("key,value", [("schemaVersion", True), ("maxEvents", True),
    ("maxEvents", 0), ("jobMemoryLimitBytes", -1), ("scope", []), ("scope", ["a\nb"]),
    ("expectedAccountEmail", ""), ("accountBinding", "")])
def test_invalid_binding_values(tmp_path, key, value):
    path = tmp_path / "input.json"
    path.write_text(json.dumps({**binding(), key: value}))
    with pytest.raises(dispatch.DispatchError):
        dispatch.read_binding(path)


def test_prepare_uses_control_and_exact_canonical_ledger_demand(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    assert operation.request.role == "qa-engineer"
    assert operation.selection.mcp_scope.servers == ()
    assert operation.selection.ledger_max_events == 100
    assert operation.request.max_events == 100
    assert operation.request.external_dispatch_id != operation.request.external_evidence_run_id
    assert operation.request.prompt.count("Review fixture source only.") == 1
    assert operation.prevalidated.control.resolved_ledger_budget is not None
    assert not (Path(operation.selection.work_item) / "sdk-review.json").exists()
    assert not (Path(operation.selection.work_item) / "agent-runs.jsonl").exists()


@pytest.mark.parametrize("change", [dict(ledger_lane="review"), dict(ledger_role="consultant"),
    dict(ledger_role="backend-engineer"), dict(ledger_role_explicit=False), dict(ledger_closes=["other"]),
    dict(provider_flags=["--model", "fixture", "-c", "model_reasoning_effort=high", "--sandbox", "workspace-write"])])
def test_no_implicit_lane_loss_role_conversion_or_fallback(tmp_path, monkeypatch, change):
    with pytest.raises(dispatch.DispatchError, match="REVIEW_ONLY"):
        prepare(tmp_path, monkeypatch, **change)


def test_guard_one_invocation_stages_drift_and_cancellation(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    with pytest.raises(dispatch.DispatchError):
        operation.assert_current(operation.request, "sdk_prepare")
    operation._consumed = True  # Unit boundary; execute owns this transition in production.
    for effect in dispatch._STAGES[:7]:
        operation.assert_current(operation.request, effect)
    operation.assert_current(operation.request, "query")
    operation.assert_current(operation.request, "thread_start")
    operation.assert_current(operation.request, "query")
    operation.assert_current(operation.request, "turn_start")
    for effect in ("turn_start", "resume", "reconcile", "tool", "account", "query"):
        with pytest.raises(dispatch.DispatchError, match="EFFECT_DENIED"):
            operation.assert_current(operation.request, effect)
    with pytest.raises(dispatch.DispatchError, match="NOT_CURRENT"):
        operation.assert_current(replace(operation.request, scope=("other",)), "query")
    operation.prevalidated.control.ledger_lane = "drift"
    with pytest.raises(dispatch.DispatchError, match="NOT_CURRENT"):
        operation.assert_current(operation.request, "query")
    operation.prevalidated.control.ledger_lane = None
    operation._cancelled = lambda: True
    with pytest.raises(dispatch.DispatchError, match="NOT_CURRENT"):
        operation.assert_current(operation.request, "query")


def test_execute_retains_before_receiving_and_forwards_capture(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    run = types.SimpleNamespace(observation=object())
    called = []
    def fake_runtime(request, selection, **kwargs):
        called.append(kwargs)
        for effect in dispatch._STAGES:
            kwargs["authority"](request, effect)
        return run
    monkeypatch.setattr(runtime, "run_admitted_codex", fake_runtime)
    monkeypatch.setattr(receiving, "terminal_payload", lambda *a, **k: (_ for _ in ()).throw(ValueError("receiving failed")))
    process = object()
    assert operation.execute(process) is run
    assert operation.runtime_run is run
    assert called[0]["owner"] is process
    assert called[0]["capture_limit_bytes"] == operation.prevalidated.control.capture_max_bytes
    # A separate call is required after process-owner closure; execute never receives.
    run.request, run.selection, run.output_context = operation.request, operation.selection, object()
    with pytest.raises(ValueError, match="receiving failed"):
        operation.receive()
    assert operation.runtime_run is run
    with pytest.raises(dispatch.DispatchError, match="RECEIVING_UNAVAILABLE"):
        operation.receive()
    with pytest.raises(dispatch.DispatchError, match="OPERATION_CONSUMED"):
        operation.execute(process)


def test_receiving_success_no_second_append_or_terminal_receipt_write(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    terminal = dict(runId=operation.request.external_evidence_run_id, status="completed", gate="PASS")
    run = types.SimpleNamespace(request=operation.request, selection=operation.selection, observation=object(),
                                output_context=types.SimpleNamespace(needles=()))
    payload = dict(resultText="review", status="completed", gate="PASS", cancelled=False, timedOut=False)
    monkeypatch.setattr(runtime, "run_admitted_codex", lambda *a, **k: run)
    monkeypatch.setattr(receiving, "terminal_payload", lambda *a, **k: payload)
    receives = []
    monkeypatch.setattr(receiving, "receive_runtime_run", lambda *a, **k: receives.append(a[0]) or terminal)
    monkeypatch.setattr(owner, "parse_provider_result", lambda line: payload)
    monkeypatch.setattr(owner, "_provider_terminal_line_safety", lambda *a: None)
    monkeypatch.setattr(owner, "record_terminal", lambda *a, **k: pytest.fail("second append"))
    operation.execute(object())
    result = operation.receive()
    assert receives == [run]
    assert result.exit_code == 0
    assert result.terminal == terminal
    assert result.terminal_bytes.startswith(owner.SDK_RESULT_PREFIX.encode())
    assert not operation.prevalidated.control.terminal_receipt.exists()


def test_before_worker_receiving_uses_known_terminal_without_another_append(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    terminal = dict(runId=operation.request.external_evidence_run_id, status="blocked", gate="none")
    run = types.SimpleNamespace(request=operation.request, selection=operation.selection, observation=None,
                                terminal=terminal, output_context=types.SimpleNamespace(needles=()))
    payload = dict(resultText="worker not started", status="blocked", gate="none")
    monkeypatch.setattr(runtime, "run_admitted_codex", lambda *a, **k: run)
    monkeypatch.setattr(receiving, "preworker_failure_payload", lambda current: payload if current is run else pytest.fail("wrong run"))
    monkeypatch.setattr(receiving, "receive_runtime_run", lambda *a, **k: pytest.fail("duplicate receiving"))
    monkeypatch.setattr(owner, "parse_provider_result", lambda line: payload)
    monkeypatch.setattr(owner, "_provider_terminal_line_safety", lambda *a: None)
    operation.execute(object())
    assert operation.receive().exit_code == 1


def test_guard_deadline_and_event_query_bound(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    operation._consumed = True
    operation.deadline = 0
    with pytest.raises(dispatch.DispatchError, match="NOT_CURRENT"):
        operation.assert_current(operation.request, "sdk_prepare")
    operation.deadline = float("inf")  # Exercise query bound independently.
    for effect in dispatch._STAGES[:7]:
        operation.assert_current(operation.request, effect)
    for _ in range(operation.request.max_events):
        operation.assert_current(operation.request, "query")
    with pytest.raises(dispatch.DispatchError, match="EFFECT_DENIED"):
        operation.assert_current(operation.request, "query")


def test_unsupported_platform_refuses_before_owner_or_binding_effects(monkeypatch):
    monkeypatch.setattr(dispatch, "_require_supported_platform", lambda: (_ for _ in ()).throw(dispatch.DispatchError("E_CODEX_SDK_WINDOWS_ONLY")))
    monkeypatch.setattr(dispatch, "_owner", lambda: pytest.fail("owner reached before platform check"))
    with pytest.raises(dispatch.DispatchError, match="WINDOWS_ONLY"):
        dispatch.prepare_dispatch(None, Path("unused"), source_environment={}, cancellation_probe=lambda: False)


def test_preparation_os_error_is_stable_and_does_not_expose_path(tmp_path, monkeypatch):
    selected, path, environment = fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(owner, "prompt_bytes", lambda *a, **k: (_ for _ in ()).throw(OSError("private local path")))
    with pytest.raises(dispatch.DispatchError, match="^E_CODEX_SDK_PREPARATION_FAILED$"):
        dispatch.prepare_dispatch(selected, path, source_environment=environment, cancellation_probe=lambda: False)


def test_recovery_is_scanned_diagnostic_not_prompt_or_protocol_custody(tmp_path, monkeypatch):
    from test_sdk_receiving import synthetic_observation
    operation = prepare(tmp_path, monkeypatch)
    observation = synthetic_observation(monkeypatch, operation.request)
    operation.runtime_run = runtime.RuntimeRun(operation.request, operation.selection,
                                               owner.ProviderOutputContext(()), observation)
    payload = operation.recovery_bytes()
    record = json.loads(payload)
    assert record["restorableObservation"] is False
    assert record["replayAuthorized"] is False
    assert record["receiving"] == "not-established"
    assert record["decodedResult"]["result"]["review"]["verdict"] == "PASS"
    assert "request" not in record["decodedResult"]["result"]
    assert "observations" not in record["decodedResult"]["result"]
    assert "Review fixture source only." not in payload.decode()
    assert set(record["stdout"]) == {"byteLength", "sha256", "truncated", "payloadOmitted"}
    assert "needles" not in payload.decode()


def test_recovery_unsafe_output_omits_payload_but_keeps_process_diagnostics(tmp_path, monkeypatch):
    from test_sdk_receiving import synthetic_observation
    operation = prepare(tmp_path, monkeypatch)
    observation = synthetic_observation(monkeypatch, operation.request, usage={"unsafe": "fixture-secret"})
    operation.runtime_run = runtime.RuntimeRun(operation.request, operation.selection,
                                               owner.ProviderOutputContext((b"fixture-secret",)), observation)
    payload = operation.recovery_bytes()
    record = json.loads(payload)
    assert record["unsafeOutputOmitted"] is True
    assert "decodedResult" not in record
    assert record["process"]["authorizing"] is False
    assert b"fixture-secret" not in payload


def test_recovery_requires_original_bound_observation(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    with pytest.raises(dispatch.DispatchError, match="RECOVERY_UNAVAILABLE"):
        operation.recovery_bytes()
    operation.runtime_run = runtime.RuntimeRun(operation.request, operation.selection,
                                               owner.ProviderOutputContext(()), object())
    with pytest.raises(dispatch.DispatchError, match="RECOVERY_UNAVAILABLE"):
        operation.recovery_bytes()


@pytest.mark.parametrize("name", ["agent-runs.jsonl", "agent-runs.jsonl.lock"])
@pytest.mark.parametrize("target", ["artifact", "receipt"])
def test_output_cannot_alias_ledger_or_its_lock(tmp_path, monkeypatch, name, target):
    selected, path, environment = fixture(tmp_path, monkeypatch)
    if target == "artifact":
        selected.control.ledger_artifact = name
    else:
        selected.control.terminal_receipt = Path(selected.control.ledger) / name
    with pytest.raises(dispatch.DispatchError, match="OUTPUT_ALIAS"):
        dispatch.prepare_dispatch(selected, path, source_environment=environment, cancellation_probe=lambda: False)


@pytest.mark.parametrize("field,value", [("ledger_artifact", "different-review.json"),
                                        ("result_max_bytes", 1234), ("capture_max_bytes", 1234)])
def test_receiving_rejects_control_drift_before_any_write(tmp_path, monkeypatch, field, value):
    operation = prepare(tmp_path, monkeypatch)
    run = types.SimpleNamespace(observation=object())
    monkeypatch.setattr(runtime, "run_admitted_codex", lambda *a, **k: run)
    monkeypatch.setattr(receiving, "receive_runtime_run", lambda *a, **k: pytest.fail("write on drift"))
    operation.execute(object())
    setattr(operation.prevalidated.control, field, value)
    with pytest.raises(dispatch.DispatchError, match="RECEIVING_DRIFT"):
        operation.receive()
    assert operation.runtime_run is run


def test_recovery_cap_is_frozen_and_read_only(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    limit = operation.recovery_max_bytes
    assert limit == operation._capture_limit + 6 * operation._result_limit + 65536
    operation.prevalidated.control.capture_max_bytes *= 2
    operation.prevalidated.control.result_max_bytes *= 2
    assert operation.recovery_max_bytes == limit
    with pytest.raises(AttributeError):
        operation.recovery_max_bytes = limit * 2


def test_dispatch_selects_fixed_bounded_profile_without_endpoint_or_hook_overrides(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    assert operation.selection.config_overrides == runtime.CODEX_BOUNDED_REVIEW_OVERRIDES
    assert operation.selection.config_overrides[:4] == (
        'features.memories=false', 'notify=[]', 'model_provider="openai"', 'approvals_reviewer="user"')
    assert all('openai_base_url' not in value and 'features.hooks' not in value
               for value in operation.selection.config_overrides)


def test_prepare_preserves_omitted_ledger_caps(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch, ledger_max_events=None, ledger_max_bytes=None)
    assert operation.selection.ledger_max_events is None
    assert operation.selection.ledger_max_bytes is None
    assert operation.prevalidated.control.resolved_ledger_budget is None
    assert runtime.CodexRuntimeSelection.from_dict(operation.selection.to_dict()) == operation.selection
    assert not (Path(operation.selection.work_item) / "agent-runs.jsonl").exists()

"""Offline API-shape tests, not installed SDK, account or live-provider qualification."""
from __future__ import annotations

import asyncio
from dataclasses import replace
import importlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sdk_execution import coordinator
from sdk_execution.contracts import ExecutionRequest, ExecutionResult, ReviewResult


def request(**changes):
    values = {
        "work_item_id": "fixture-item", "provider": "codex",
        "external_dispatch_id": "fixture-dispatch", "external_evidence_run_id": "fixture-evidence",
        "artifact_id": "fixture-artifact", "role": "architecture-reviewer",
        "model": "fixture-model", "effort": "high", "cwd": "fixture-project",
        "account_binding": "fixture-account", "prompt": "Review the admitted fixture scope.",
        "coordinator_binding": "fixture-coordinator", "scope": ("src/example.py",),
    }
    return ExecutionRequest(**(values | changes))


class FakeAuthority:
    """Test owner only. This is deliberately not a production admission writer."""

    def __init__(self):
        self.current = request()
        self.effects = []
        self.claims = []
        self.denied = set()
        self.on_check = None
        self.snapshot = {"pending_request_id": "fixture-request", "saved_approval": True, "max_turns": 2}

    def resolve(self, request_id):
        if request_id != "fixture-request":
            raise KeyError(request_id)
        return self.current

    def assert_current(self, request, effect):
        self.effects.append(effect)
        if self.on_check:
            self.on_check(request, effect)
        if effect in self.denied:
            raise PermissionError("current authority denied")

    def claim_resume(self, request, snapshot_id):
        if snapshot_id != "fixture-snapshot" or snapshot_id in self.claims:
            raise PermissionError("unknown or consumed snapshot")
        self.claims.append(snapshot_id)
        return self.snapshot


class FakeExecutor:
    def __init__(self):
        self.calls = []
        self.error = None
        self.result_request = None

    async def execute(self, request):
        self.calls.append(request)
        if self.error:
            raise self.error
        observed = self.result_request or request
        review = ReviewResult(run_id=observed.external_evidence_run_id,
                              artifact_id=observed.artifact_id, role=observed.role,
                              verdict="PASS", findings=())
        return ExecutionResult(request=observed, status="completed", provider_status="completed",
                               review=review, protocol_closed=True)


class FakeModel:
    pass


class FakeTool:
    def __init__(self, function, *, name_override, failure_error_function, strict_mode):
        self.function = function
        self.name = name_override
        self.failure_error_function = failure_error_function
        self.strict_mode = strict_mode

    async def on_invoke_tool(self, context, arguments):
        return await self.function(**json.loads(arguments))


class FakeSdk:
    """Only public signatures consumed by the coordinator; no provider effects."""

    __version__ = "0.24.0"
    Model = FakeModel

    class RunHooks:
        async def on_llm_start(self, context, agent, system_prompt, input_items):
            pass

    class Configuration(SimpleNamespace):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    Agent = ModelSettings = RunConfig = ToolExecutionConfig = Configuration

    def __init__(self):
        self.calls = []
        self.restorations = []
        self.before_model = None
        self.before_tool = None
        self.after_restore = None
        self.tool_request_id = None
        self.model_calls = 0
        outer = self

        class Runner:
            @staticmethod
            async def run(starting_agent, input, *, context, max_turns, hooks, run_config, **options):
                outer.calls.append({"agent": starting_agent, "input": input, "context": context,
                                    "max_turns": max_turns, "hooks": hooks, "run_config": run_config, **options})
                if isinstance(input, str):
                    request_id = json.loads(input)["admitted_request_id"]
                    if outer.before_model:
                        outer.before_model()
                    await hooks.on_llm_start(None, starting_agent, starting_agent.instructions, [])
                    outer.model_calls += 1
                else:
                    # A resumed pending tool can run before another model call.
                    request_id = input.snapshot["pending_request_id"]
                if outer.before_tool:
                    outer.before_tool()
                output = await starting_agent.tools[0].on_invoke_tool(
                    None, json.dumps({"request_id": outer.tool_request_id or request_id})
                )
                assert starting_agent.tool_use_behavior == "stop_on_first_tool"
                return SimpleNamespace(final_output=output)

        class RunState:
            @staticmethod
            async def from_json(initial_agent, state_json, *, context_override, strict_context):
                outer.restorations.append({"agent": initial_agent, "snapshot": state_json,
                                           "context_override": context_override,
                                           "strict_context": strict_context})
                if outer.after_restore:
                    outer.after_restore()
                return SimpleNamespace(snapshot=state_json)

        self.Runner = Runner
        self.RunState = RunState


@pytest.fixture
def harness(monkeypatch):
    sdk = FakeSdk()
    authority = FakeAuthority()
    executor = FakeExecutor()
    model = FakeModel()
    monkeypatch.setattr(coordinator, "_load_agents_sdk", lambda: (sdk, FakeTool))
    instance = coordinator.AgentsCoordinator(
        model=model, coordinator_binding="fixture-coordinator", authority=authority,
        executor=executor, max_turns=2,
    )
    return SimpleNamespace(sdk=sdk, authority=authority, executor=executor, model=model, instance=instance)


def test_one_tool_calls_one_executor_and_returns_nonauthorizing_evidence(harness):
    result = asyncio.run(harness.instance.run("fixture-request"))
    assert harness.executor.calls == [harness.authority.current]
    assert harness.authority.effects == ["coordinator_start", "coordinator_model", "execute"]
    output = json.loads(result.final_output)
    assert output["authoritative"] is False
    assert output["process_settlement"] == "not_established"
    assert output["usage"] is None
    assert harness.sdk.model_calls == 1
    call = harness.sdk.calls[0]
    assert call["max_turns"] == 2
    assert call["context"] == {}
    assert call["agent"].model is harness.model
    assert call["agent"].model_settings.parallel_tool_calls is False
    assert call["agent"].model_settings.tool_choice == "execute_admitted"
    assert len(call["agent"].tools) == 1
    tool = call["agent"].tools[0]
    assert tool.failure_error_function is None
    assert tool.strict_mode is True
    config = call["run_config"]
    assert config.model is harness.model
    assert config.tracing_disabled is True
    assert config.trace_include_sensitive_data is False
    assert config.tool_execution.max_function_tool_concurrency == 1
    assert "fixture-account" not in call["input"]
    assert "Review the admitted fixture scope" not in call["input"]


@pytest.mark.parametrize("effect", ["coordinator_start", "coordinator_model", "execute"])
def test_current_authority_is_required_at_each_effect(harness, effect):
    harness.authority.denied.add(effect)
    with pytest.raises(PermissionError, match="current authority"):
        asyncio.run(harness.instance.run("fixture-request"))
    assert harness.executor.calls == []
    if effect != "execute":
        assert harness.sdk.model_calls == 0


def test_revocation_between_model_and_tool_is_not_a_model_retry(harness):
    harness.sdk.before_tool = lambda: harness.authority.denied.add("execute")
    with pytest.raises(PermissionError):
        asyncio.run(harness.instance.run("fixture-request"))
    assert harness.executor.calls == []
    assert harness.sdk.model_calls == 1
    assert len(harness.sdk.calls) == 1


@pytest.mark.parametrize("changes", [
    {"model": "changed-model"}, {"account_binding": "changed-account"},
    {"scope": ("another/path",)}, {"role": "qa-engineer"},
    {"external_dispatch_id": "changed-run"}, {"prompt": "changed task"},
])
def test_current_binding_drift_cannot_reuse_admission(harness, changes):
    harness.sdk.before_tool = lambda: setattr(
        harness.authority, "current", replace(harness.authority.current, **changes)
    )
    with pytest.raises(coordinator.CoordinatorBindingError, match="binding changed"):
        asyncio.run(harness.instance.run("fixture-request"))
    assert harness.executor.calls == []


def test_other_coordination_owner_is_rejected_before_sdk_run(harness):
    harness.authority.current = replace(harness.authority.current, coordinator_binding="host-led")
    with pytest.raises(coordinator.CoordinatorBindingError, match="another coordination owner"):
        asyncio.run(harness.instance.run("fixture-request"))
    assert harness.sdk.calls == []


def test_model_cannot_select_another_admitted_request(harness):
    harness.sdk.tool_request_id = "different-request"
    with pytest.raises(coordinator.CoordinatorBindingError, match="unbound request identity"):
        asyncio.run(harness.instance.run("fixture-request"))
    assert harness.executor.calls == []


def test_executor_cannot_substitute_result_identity(harness):
    harness.executor.result_request = replace(harness.authority.current, external_dispatch_id="another-run")
    with pytest.raises(coordinator.CoordinatorBindingError, match="another request"):
        asyncio.run(harness.instance.run("fixture-request"))


@pytest.mark.parametrize("error", [RuntimeError("execution failed"), asyncio.CancelledError()])
def test_failure_and_cancellation_propagate_without_fallback(harness, error):
    harness.executor.error = error
    with pytest.raises(type(error)):
        asyncio.run(harness.instance.run("fixture-request"))
    assert len(harness.executor.calls) == 1
    assert len(harness.sdk.calls) == 1


def test_repeated_invocation_uses_existing_owner_not_an_in_memory_replay_registry(harness):
    asyncio.run(harness.instance.run("fixture-request"))
    harness.authority.denied.add("execute")
    with pytest.raises(PermissionError):
        asyncio.run(harness.instance.run("fixture-request"))
    assert len(harness.executor.calls) == 1
    assert harness.authority.effects.count("execute") == 2


def test_resume_claims_owner_state_and_rebinds_tool_without_a_model_call(harness):
    result = asyncio.run(harness.instance.resume("fixture-request", "fixture-snapshot"))
    assert harness.authority.claims == ["fixture-snapshot"]
    assert harness.authority.effects == ["coordinator_resume", "coordinator_resume", "execute"]
    assert harness.sdk.model_calls == 0
    assert json.loads(result.final_output)["authoritative"] is False
    restored = harness.sdk.restorations[0]
    assert restored["context_override"] == {}
    assert restored["strict_context"] is True
    assert restored["agent"] is harness.sdk.calls[0]["agent"]
    assert harness.sdk.calls[0]["run_config"].tracing_disabled is True


def test_saved_approval_cannot_override_current_resume_revocation(harness):
    harness.authority.denied.add("coordinator_resume")
    with pytest.raises(PermissionError):
        asyncio.run(harness.instance.resume("fixture-request", "fixture-snapshot"))
    assert harness.authority.claims == []
    assert harness.sdk.restorations == []
    assert harness.executor.calls == []


def test_authority_revoked_during_deserialization_prevents_resume(harness):
    harness.sdk.after_restore = lambda: harness.authority.denied.add("coordinator_resume")
    with pytest.raises(PermissionError):
        asyncio.run(harness.instance.resume("fixture-request", "fixture-snapshot"))
    assert harness.authority.claims == ["fixture-snapshot"]
    assert harness.sdk.calls == []
    assert harness.executor.calls == []


def test_resumed_pending_tool_rechecks_current_authority(harness):
    harness.sdk.before_tool = lambda: harness.authority.denied.add("execute")
    with pytest.raises(PermissionError):
        asyncio.run(harness.instance.resume("fixture-request", "fixture-snapshot"))
    assert harness.executor.calls == []
    assert harness.sdk.model_calls == 0


def test_resume_replay_is_rejected_by_owner_before_deserialization(harness):
    asyncio.run(harness.instance.resume("fixture-request", "fixture-snapshot"))
    with pytest.raises(PermissionError, match="consumed snapshot"):
        asyncio.run(harness.instance.resume("fixture-request", "fixture-snapshot"))
    assert len(harness.sdk.restorations) == 1
    assert len(harness.executor.calls) == 1


def test_resume_without_owner_support_is_unavailable(harness):
    harness.authority.claim_resume = None
    with pytest.raises(coordinator.CoordinatorUnavailable, match="claim_resume"):
        asyncio.run(harness.instance.resume("fixture-request", "fixture-snapshot"))
    assert harness.sdk.calls == []


def test_raw_resume_payload_is_not_accepted(harness):
    with pytest.raises(coordinator.CoordinatorBindingError, match="snapshot_id"):
        asyncio.run(harness.instance.resume("fixture-request", {"saved_approval": True}))
    assert harness.authority.claims == []


@pytest.mark.parametrize("value", [True, False, "allowed"])
def test_miswired_boolean_authority_callback_fails_closed(harness, value):
    harness.authority.assert_current = lambda request, effect: value
    with pytest.raises(coordinator.CoordinatorBindingError, match="return None"):
        asyncio.run(harness.instance.run("fixture-request"))
    assert harness.sdk.calls == []


@pytest.mark.parametrize("model", [None, "fixture-model"])
def test_model_defaults_and_string_provider_resolution_are_not_allowed(model):
    with pytest.raises(coordinator.CoordinatorBindingError, match="explicit Model"):
        coordinator.AgentsCoordinator(model=model, coordinator_binding="fixture-coordinator",
                                      authority=FakeAuthority(), executor=FakeExecutor(), max_turns=2)


@pytest.mark.parametrize("max_turns", [None, True, False, 0, -1, 1.5])
def test_turn_bound_is_explicit_positive_integer(max_turns):
    with pytest.raises(coordinator.CoordinatorBindingError, match="positive integer"):
        coordinator.AgentsCoordinator(model=FakeModel(), coordinator_binding="fixture-coordinator",
                                      authority=FakeAuthority(), executor=FakeExecutor(), max_turns=max_turns)


def test_non_sdk_model_object_cannot_execute(harness):
    harness.instance._model = object()
    with pytest.raises(coordinator.CoordinatorBindingError, match="SDK Model"):
        asyncio.run(harness.instance.run("fixture-request"))
    assert harness.sdk.calls == []


def test_missing_authority_methods_have_no_permissive_default():
    with pytest.raises(coordinator.CoordinatorUnavailable, match="resolve"):
        coordinator.AgentsCoordinator(model=FakeModel(), coordinator_binding="fixture-coordinator",
                                      authority=object(), executor=FakeExecutor(), max_turns=2)


def test_module_import_and_construction_do_not_load_optional_sdk(monkeypatch):
    calls = []
    monkeypatch.setattr(importlib, "import_module", lambda name: calls.append(name))
    importlib.reload(coordinator)
    coordinator.AgentsCoordinator(model=FakeModel(), coordinator_binding="fixture-coordinator",
                                  authority=FakeAuthority(), executor=FakeExecutor(), max_turns=2)
    assert calls == []


def test_missing_optional_distribution_never_attempts_import(monkeypatch):
    def absent(name):
        raise coordinator.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(coordinator.metadata, "version", absent)
    monkeypatch.setattr(importlib, "import_module", lambda name: pytest.fail("unexpected SDK import"))
    with pytest.raises(coordinator.CoordinatorUnavailable, match="not provisioned"):
        coordinator._load_agents_sdk()


def install_fake_sdk(monkeypatch, sdk, version):
    monkeypatch.setattr(coordinator.metadata, "version", lambda name: version)
    sdk.__version__ = version
    calls = []

    def load(name):
        calls.append(name)
        return {"agents": sdk, "agents.decorators": SimpleNamespace(tool=FakeTool)}[name]

    monkeypatch.setattr(importlib, "import_module", load)
    return calls


@pytest.mark.parametrize("version", ["0.23.1", "0.24.0", "0.25.0", "1.0.0rc1+fixture", "vendor/1!2.0+build"])
def test_loader_accepts_compatible_public_api_independent_of_release(monkeypatch, version):
    sdk = FakeSdk()
    calls = install_fake_sdk(monkeypatch, sdk, version)
    assert coordinator._load_agents_sdk() == (sdk, FakeTool)
    assert calls == ["agents", "agents.decorators"]
    assert sdk.__version__ == version


def test_changed_release_runs_with_existing_model_authority_and_executor_contracts(monkeypatch):
    sdk, authority, executor = FakeSdk(), FakeAuthority(), FakeExecutor()
    install_fake_sdk(monkeypatch, sdk, "1.2.3")
    instance = coordinator.AgentsCoordinator(
        model=FakeModel(), coordinator_binding="fixture-coordinator", authority=authority,
        executor=executor, max_turns=2,
    )
    result = asyncio.run(instance.run("fixture-request"))
    assert json.loads(result.final_output)["authoritative"] is False
    assert executor.calls == [authority.current] and sdk.model_calls == 1


@pytest.mark.parametrize("version", [None, "", " ", "malformed value", "0.25.0\n", 3, True, "1" * 129])
def test_malformed_distribution_metadata_is_rejected_before_import(monkeypatch, version):
    monkeypatch.setattr(coordinator.metadata, "version", lambda name: version)
    monkeypatch.setattr(importlib, "import_module", lambda name: pytest.fail("unexpected SDK import"))
    with pytest.raises(coordinator.CoordinatorUnavailable, match="invalid version metadata"):
        coordinator._load_agents_sdk()


@pytest.mark.parametrize("name", ["Model", "RunHooks", "Agent", "ModelSettings", "RunConfig", "ToolExecutionConfig", "Runner"])
def test_missing_required_sdk_api_fails_before_any_model_or_executor_effect(monkeypatch, name):
    sdk, authority, executor = FakeSdk(), FakeAuthority(), FakeExecutor()
    install_fake_sdk(monkeypatch, sdk, "0.25.0")
    setattr(sdk, name, None)
    instance = coordinator.AgentsCoordinator(
        model=FakeModel(), coordinator_binding="fixture-coordinator", authority=authority,
        executor=executor, max_turns=2,
    )
    with pytest.raises(coordinator.CoordinatorUnavailable, match="required .* API"):
        asyncio.run(instance.run("fixture-request"))
    assert sdk.calls == [] and sdk.model_calls == 0 and executor.calls == []


def test_missing_tool_decorator_fails_before_sdk_effects(monkeypatch):
    sdk = FakeSdk()
    install_fake_sdk(monkeypatch, sdk, "0.25.0")
    monkeypatch.setattr(importlib, "import_module", lambda name: sdk if name == "agents" else SimpleNamespace())
    with pytest.raises(coordinator.CoordinatorUnavailable, match="required decorators.tool API"):
        coordinator._load_agents_sdk()
    assert sdk.calls == []


def test_missing_concurrency_option_fails_before_sdk_effects(monkeypatch):
    sdk = FakeSdk()
    install_fake_sdk(monkeypatch, sdk, "0.25.0")
    sdk.ToolExecutionConfig = lambda: None
    with pytest.raises(coordinator.CoordinatorUnavailable, match="incompatible ToolExecutionConfig API"):
        coordinator._load_agents_sdk()
    assert sdk.calls == []


def test_missing_resume_api_does_not_consume_snapshot_or_prevent_fresh_run(harness):
    harness.sdk.RunState = None
    with pytest.raises(coordinator.CoordinatorUnavailable, match="required RunState.from_json API"):
        asyncio.run(harness.instance.resume("fixture-request", "fixture-snapshot"))
    assert harness.authority.claims == [] and harness.sdk.calls == []
    assert harness.executor.calls == []
    asyncio.run(harness.instance.run("fixture-request"))
    assert harness.sdk.model_calls == 1


def test_imported_module_cannot_silently_differ_from_distribution(monkeypatch):
    monkeypatch.setattr(coordinator.metadata, "version", lambda name: "0.24.0")
    monkeypatch.setattr(importlib, "import_module", lambda name: SimpleNamespace(__version__="0.25.0"))
    with pytest.raises(coordinator.CoordinatorUnavailable, match="does not match"):
        coordinator._load_agents_sdk()


@pytest.mark.parametrize("saved_turns", [None, True, 0, 3])
def test_saved_turn_bound_cannot_override_current_selected_bound(harness, saved_turns):
    harness.authority.snapshot["max_turns"] = saved_turns
    with pytest.raises(coordinator.CoordinatorBindingError, match="saved turn bound"):
        asyncio.run(harness.instance.resume("fixture-request", "fixture-snapshot"))
    assert harness.sdk.restorations == []
    assert harness.executor.calls == []


def test_tighter_saved_turn_bound_is_preserved_without_private_state_mutation(harness):
    harness.authority.snapshot["max_turns"] = 1
    asyncio.run(harness.instance.resume("fixture-request", "fixture-snapshot"))
    assert harness.sdk.restorations[0]["snapshot"]["max_turns"] == 1


def test_unexpected_provider_tool_argument_cannot_expand_the_fixed_boundary(harness):
    _, agent, _, _, _ = harness.instance._prepare("fixture-request", "coordinator_start")
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        asyncio.run(agent.tools[0].on_invoke_tool(
            None, json.dumps({"request_id": "fixture-request", "provider": "another-provider"})
        ))
    assert harness.executor.calls == []


def composed_harness(monkeypatch, tmp_path, *, provider="codex", alter_process=None, before_result=None):
    """Actual coordinator/runtime/receiver/ledger, synthetic SDK and OS endpoints."""
    import time
    import provider_prompt
    from process_supervision import process_runner as processes
    from sdk_execution import runtime
    from sdk_execution.contracts import json_text
    from sdk_execution.worker import decode_frame, encode_frame, request_binding
    from test_sdk_runtime import fixture

    raw, selection = fixture(tmp_path)
    source = {}
    account_evidence, tools = [], []
    if provider == "codex":
        effective = runtime.prepare_codex_request(raw)
    else:
        from sdk_execution.claude import ClaudeRuntimeSelection
        prompts = tmp_path / "selected-prompts"
        prompts.mkdir()
        effective = replace(raw, provider="claude", model="claude-fixture-concrete-20260101")
        selection = ClaudeRuntimeSelection(
            executable=selection.executable, executable_sha256=selection.executable_sha256,
            config_dir=selection.codex_home, auth_mode="claude-direct",
            instructions=provider_prompt.assemble_external_prompt(b"Explicit fixture project and Claude rules.").decode(),
            prompts_dir=str(prompts), work_item=selection.work_item,
            ledger_max_events=selection.ledger_max_events, ledger_max_bytes=selection.ledger_max_bytes,
            job_memory_limit_bytes=selection.job_memory_limit_bytes,
        )
        source = {"ANTHROPIC_API_KEY": "synthetic-never-transmitted-secret"}
    authority, sdk = FakeAuthority(), FakeSdk()
    authority.current = effective
    monkeypatch.setattr(coordinator, "_load_agents_sdk", lambda: (sdk, FakeTool))
    monkeypatch.setattr(provider_prompt, "require_codex_hook_trust", lambda *args, **kwargs: 0)
    selected = runtime.selected_sdk_execution(effective, selection)
    observed = {key: value for key, value in selected.items() if key != "requestSha256"}
    observed.update(schemaVersion=1, sdkVersion="1.2.3", runtimeVersion="4.5.6")
    result = ExecutionResult(
        request=effective, status="completed", provider_status="completed", protocol_closed=True,
        native_thread_id="synthetic-thread", native_turn_id="synthetic-turn", sdk_execution_json=json_text(observed),
        review=ReviewResult(effective.external_evidence_run_id, effective.artifact_id, effective.role, "PASS", ()),
    )
    h = SimpleNamespace(authority=authority, sdk=sdk, request=effective, selection=selection,
                        result=result, replies=[], frames=[], process_calls=0, accounts=account_evidence,
                        tools=tools, received=[], source=source)

    def simulated_run(self, process_request, *, dialogue):
        h.process_calls += 1
        h.process_request = process_request
        effects = [("client_start", None), ("thread_start", None), ("turn_start", None)]
        if provider == "claude":
            effects = [("client_start", None),
                       ("account", {"kind": "account", "evidence": {"phase": "system_init", "data": {"fixture": True}}}),
                       ("tool", {"kind": "tool", "name": "Read", "arguments": {"file_path": "source.py"}})]
        frames = [encode_frame({"kind": "authority_request", "run_id": effective.run_id,
                    "request_sha256": request_binding(effective), "sequence": index, "effect": effect,
                    **({"context": context} if context is not None else {})})
                  for index, (effect, context) in enumerate(effects)]
        class Channel:
            def write_line(self, value):
                frame = decode_frame(value)
                h.frames.append(frame)
                if frame["kind"] == "execute":
                    assert frame["request"] == effective.to_dict()
                    assert frame["runtime_selection"]["expected_launch_sha256"] is not None
                elif frame["kind"] == "authority_response":
                    h.replies.append(frame)
            def read_line(self):
                if frames:
                    return frames.pop(0)
                if not getattr(self, "sent_result", False):
                    self.sent_result = True
                    if before_result:
                        before_result(h)
                    return encode_frame({"kind": "result", "result": h.result.to_dict()})
                raise EOFError()
        error = None
        try:
            dialogue.handler(Channel())
        except processes.ProcessSupervisionError as failure:
            error = failure
        failed = processes._request_failure(process_request, processes.ProcessSupervisionError("PSV1-INTERNAL", "execution"), time.monotonic())
        clean = replace(failed, outcome="success", terminal_stage="completed", failure_id=None,
                        target_exit_code=0, resources_closed=True, policy_id="sdk-worker-v1",
                        tree=processes.TreeObservationV1("synthetic", True, "EMPTY", True, True, True, True))
        if error is not None:
            clean = replace(clean, outcome="supervisor-failure", terminal_stage=error.terminal_stage,
                            failure_id=error.failure_id)
        return alter_process(clean) if alter_process else clean
    monkeypatch.setattr(processes.ProcessRunnerV1, "run", simulated_run)
    from sdk_execution import receiving
    receive = receiving.receive_runtime_run
    def receive_once(run, **kwargs):
        h.received.append(run)
        return receive(run, **kwargs)
    monkeypatch.setattr(receiving, "receive_runtime_run", receive_once)
    h.owner = processes.ProcessRunnerV1()
    h.owner.__enter__()
    def verify_account(request, evidence):
        account_evidence.append((request, evidence))
        return request.account_binding
    h.options = dict(model=FakeModel(), coordinator_binding=effective.coordinator_binding,
                     authority=authority, request_id="fixture-request", selection=selection,
                     process_owner=h.owner, source_environment=source, artifact="reviews/sdk-result.json",
                     deadline_monotonic=time.monotonic() + 30, cancellation_probe=lambda: False,
                     started_at="2026-10-23T10:00:00Z", max_turns=2,
                     authorize_tool=lambda request, name, args: tools.append((request, name, args)),
                     verify_account=verify_account)
    h.coordinator, h.executor = coordinator.create_review_coordinator(**h.options)
    return h


def composed_events(h):
    return [json.loads(line) for line in (Path(h.selection.work_item) / "agent-runs.jsonl").read_text().splitlines()]


@pytest.mark.parametrize("provider", ["codex", "claude"])
def test_concrete_coordinator_executes_receives_and_reads_real_ledger(monkeypatch, tmp_path, provider):
    from sdk_execution import runtime
    h = composed_harness(monkeypatch, tmp_path, provider=provider)
    try:
        response = asyncio.run(h.coordinator.run("fixture-request"))
        output = json.loads(response.final_output)
        run = h.executor.runtime_run
        assert h.sdk.model_calls == h.process_calls == len(h.received) == 1
        assert h.received[0] is run
        assert run.request == h.authority.current == h.request
        assert run.observation.result is h.executor.execution_result
        assert json.loads(run.observation.runtime_selection_json) == run.selection.to_dict()
        assert run.selection.expected_launch_sha256 is not None
        assert runtime.request_sha256(run.request, run.selection) == runtime.request_sha256(h.request, h.selection)
        assert all(frame["allowed"] for frame in h.replies)
        launch, terminal = composed_events(h)
        assert terminal == h.executor.terminal
        assert terminal["launchRunId"] == launch["runId"] == h.request.external_dispatch_id
        assert terminal["runId"] == h.request.external_evidence_run_id
        assert terminal["sdkExecution"] == launch["sdkExecution"] == runtime.selected_sdk_execution(h.request, h.selection)
        assert terminal["authorizing"] is False
        assert output["authoritative"] is False
        assert output["status"] == "completed"
        assert json.loads((Path(h.selection.work_item) / "reviews/sdk-result.json").read_text()) == {
            "review": h.result.review.to_dict(), "reported_sdk_configuration": h.result.sdk_execution,
        }
        if provider == "claude":
            assert run.output_context.needles == (h.source["ANTHROPIC_API_KEY"].encode(),)
            assert h.accounts == [(h.request, {"phase": "system_init", "data": {"fixture": True}})]
            assert h.tools == [(h.request, "Read", {"file_path": "source.py"})]
    finally:
        h.owner.__exit__(None, None, None)


def test_concrete_chain_policy_revocation_retains_blocked_evidence(monkeypatch, tmp_path):
    h = composed_harness(monkeypatch, tmp_path)
    h.authority.denied.add("turn_start")
    try:
        output = json.loads(asyncio.run(h.coordinator.run("fixture-request")).final_output)
        assert [reply["allowed"] for reply in h.replies] == [True, True, False]
        assert h.executor.runtime_run.observation.result.status == "completed"
        assert h.executor.terminal["status"] == "blocked"
        assert output["status"] == "incomplete"
        assert h.executor.execution_result.execution_error == "received_execution_incomplete"
        assert len(composed_events(h)) == 2
    finally:
        h.owner.__exit__(None, None, None)


def test_concrete_chain_unsettled_process_retains_run_without_artifact(monkeypatch, tmp_path):
    h = composed_harness(monkeypatch, tmp_path, alter_process=lambda result: replace(result, resources_closed=False))
    try:
        with pytest.raises(ValueError):
            asyncio.run(h.coordinator.run("fixture-request"))
        assert h.executor.runtime_run.observation.result == h.result
        assert h.executor.execution_result is None and h.executor.terminal is None
        assert len(h.received) == 1 and len(composed_events(h)) == 1
        assert not (Path(h.selection.work_item) / "reviews/sdk-result.json").exists()
    finally:
        h.owner.__exit__(None, None, None)


def test_concrete_chain_changed_launch_commitment_cannot_receive(monkeypatch, tmp_path):
    def change(h):
        path = Path(h.selection.work_item) / "agent-runs.jsonl"
        event = json.loads(path.read_text())
        event["sdkExecution"]["requestSha256"] = "f" * 64
        path.write_text(json.dumps(event) + "\n")
    h = composed_harness(monkeypatch, tmp_path, before_result=change)
    try:
        with pytest.raises(ValueError):
            asyncio.run(h.coordinator.run("fixture-request"))
        assert h.executor.runtime_run.observation.result == h.result
        assert h.executor.execution_result is None
        assert len(composed_events(h)) == 1
    finally:
        h.owner.__exit__(None, None, None)


def test_concrete_chain_failed_receive_preserves_exact_acquired_run(monkeypatch, tmp_path):
    from sdk_execution import receiving
    h = composed_harness(monkeypatch, tmp_path)
    def fail(*args, **kwargs):
        raise OSError("synthetic receiving failure")
    monkeypatch.setattr(receiving, "receive_terminal", fail)
    try:
        with pytest.raises(OSError, match="synthetic receiving failure"):
            asyncio.run(h.coordinator.run("fixture-request"))
        assert h.executor.runtime_run.request == h.request
        assert h.executor.runtime_run.observation.result == h.result
        assert h.executor.execution_result is None
        assert len(composed_events(h)) == 1
        assert (Path(h.selection.work_item) / "reviews/sdk-result.json").is_file()
        with pytest.raises(ValueError, match="operation_already_consumed"):
            asyncio.run(h.executor.execute(h.request))
        assert h.process_calls == 1
    finally:
        h.owner.__exit__(None, None, None)


def test_concrete_chain_known_preworker_failure_is_not_clean_completion(monkeypatch, tmp_path):
    import provider_prompt
    h = composed_harness(monkeypatch, tmp_path)
    monkeypatch.setattr(provider_prompt, "require_codex_hook_trust", lambda *args, **kwargs: 1)
    try:
        output = json.loads(asyncio.run(h.coordinator.run("fixture-request")).final_output)
        assert h.process_calls == len(h.received) == 0
        assert h.executor.runtime_run.observation is None
        assert h.executor.terminal["status"] == "blocked"
        assert output["status"] == "incomplete"
        assert h.executor.execution_result.sdk_execution_json is None
        assert h.executor.execution_result.protocol_closed is False
        assert len(composed_events(h)) == 2
    finally:
        h.owner.__exit__(None, None, None)


def test_concrete_chain_resume_pending_tool_uses_current_owner_and_no_extra_model(monkeypatch, tmp_path):
    h = composed_harness(monkeypatch, tmp_path)
    try:
        output = json.loads(asyncio.run(h.coordinator.resume("fixture-request", "fixture-snapshot")).final_output)
        assert output["status"] == "completed"
        assert h.sdk.model_calls == 0
        assert h.process_calls == len(h.received) == 1
        assert len(composed_events(h)) == 2
        with pytest.raises(ValueError, match="RECEIPT_EXISTS"):
            asyncio.run(h.coordinator.resume("fixture-request", "fixture-snapshot"))
    finally:
        h.owner.__exit__(None, None, None)


@pytest.mark.parametrize("artifact", ["../outside.json", r"C:\\outside.json", "reviews/qa.md", "missing/result.json"])
def test_concrete_chain_artifact_preflight_precedes_model_and_provider(monkeypatch, tmp_path, artifact):
    h = composed_harness(monkeypatch, tmp_path)
    try:
        with pytest.raises(ValueError):
            coordinator.create_review_coordinator(**{**h.options, "artifact": artifact})
        assert h.sdk.model_calls == h.process_calls == 0
        assert not (Path(h.selection.work_item) / "agent-runs.jsonl").exists()
    finally:
        h.owner.__exit__(None, None, None)


def test_concrete_chain_rechecks_artifact_immediately_before_model(monkeypatch, tmp_path):
    h = composed_harness(monkeypatch, tmp_path)
    target = Path(h.selection.work_item) / "reviews/sdk-result.json"
    h.sdk.before_model = lambda: target.write_text("other owner's artifact")
    try:
        with pytest.raises(ValueError, match="RECEIPT_EXISTS"):
            asyncio.run(h.coordinator.run("fixture-request"))
        assert h.sdk.model_calls == h.process_calls == 0
        assert target.read_text() == "other owner's artifact"
    finally:
        h.owner.__exit__(None, None, None)


@pytest.mark.parametrize("option,value", [("deadline_monotonic", 0), ("cancellation_probe", lambda: True)])
def test_concrete_chain_deadline_and_cancel_preflight_precede_model(monkeypatch, tmp_path, option, value):
    h = composed_harness(monkeypatch, tmp_path)
    try:
        with pytest.raises(ValueError):
            coordinator.create_review_coordinator(**{**h.options, option: value})
        assert h.sdk.model_calls == h.process_calls == 0
    finally:
        h.owner.__exit__(None, None, None)


def test_concrete_chain_unframed_request_never_reaches_model(monkeypatch, tmp_path):
    h = composed_harness(monkeypatch, tmp_path)
    h.authority.current = replace(h.request, prompt="unframed task")
    try:
        with pytest.raises(ValueError, match="governance_frame"):
            asyncio.run(h.coordinator.run("fixture-request"))
        assert h.sdk.model_calls == h.process_calls == 0
    finally:
        h.owner.__exit__(None, None, None)


@pytest.mark.parametrize("effect", ["account", "tool"])
def test_concrete_claude_exact_owner_denial_cannot_settle_success(monkeypatch, tmp_path, effect):
    h = composed_harness(monkeypatch, tmp_path, provider="claude")
    def denied(*args):
        raise PermissionError("synthetic owner denial")
    if effect == "account":
        h.executor._verify_account = denied
    else:
        h.executor._authorize_tool = denied
    try:
        output = json.loads(asyncio.run(h.coordinator.run("fixture-request")).final_output)
        assert output["status"] == "incomplete"
        assert h.executor.terminal["status"] == "blocked"
        assert any(reply["effect"] == effect and not reply["allowed"] for reply in h.replies)
        assert h.process_calls == len(h.received) == 1
    finally:
        h.owner.__exit__(None, None, None)


@pytest.mark.parametrize("cancel_method", ["task", "explicit"])
def test_concrete_chain_cancellation_drains_owned_worker_and_retains_evidence(monkeypatch, tmp_path, cancel_method):
    import threading
    arrived, release = threading.Event(), threading.Event()
    def paused(h):
        arrived.set()
        assert release.wait(5), "test failed to release synthetic worker"
        assert h.process_request.cancellation_probe() is True
    h = composed_harness(monkeypatch, tmp_path, before_result=paused,
                         alter_process=lambda process: replace(process, cancelled=True))
    async def run():
        task = asyncio.create_task(h.coordinator.run("fixture-request"))
        while not arrived.is_set():
            if task.done():
                return await task
            await asyncio.sleep(0.001)
        if cancel_method == "task":
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()  # Repeated cancellation must not abandon the owned thread.
        else:
            receipt = await h.executor.cancel(h.request.run_id)
            assert receipt.requested and not receipt.acknowledged
        release.set()
        return await task
    try:
        output = json.loads(asyncio.run(run()).final_output)
        assert output["status"] == "incomplete"
        assert h.executor.runtime_run.observation.process.cancelled
        assert h.executor.terminal["status"] == "blocked"
        assert h.process_calls == len(h.received) == 1
        assert len(composed_events(h)) == 2
    finally:
        release.set()
        h.owner.__exit__(None, None, None)


def test_concrete_chain_unresolved_launch_is_reconciliation_hold_before_model(monkeypatch, tmp_path):
    from sdk_execution import runtime
    h = composed_harness(monkeypatch, tmp_path)
    runtime.claim_launch(h.request, h.selection, authority=h.authority.assert_current,
                         started_at="2026-10-23T10:00:00Z")
    try:
        with pytest.raises(ValueError, match="not_replay_authority"):
            asyncio.run(h.coordinator.run("fixture-request"))
        assert h.sdk.model_calls == h.process_calls == 0
        assert len(composed_events(h)) == 1
    finally:
        h.owner.__exit__(None, None, None)


def test_concrete_chain_completed_delivery_does_not_reexecute_with_new_artifact(monkeypatch, tmp_path):
    h = composed_harness(monkeypatch, tmp_path)
    try:
        asyncio.run(h.coordinator.run("fixture-request"))
        before = composed_events(h)
        with pytest.raises(ValueError, match="not_replay_authority"):
            coordinator.create_review_coordinator(**{**h.options, "artifact": "reviews/another.json"})
        assert h.sdk.model_calls == h.process_calls == len(h.received) == 1
        assert composed_events(h) == before
        assert not (Path(h.selection.work_item) / "reviews/another.json").exists()
    finally:
        h.owner.__exit__(None, None, None)


def test_concrete_claude_preserves_scanned_benign_usage(monkeypatch, tmp_path):
    h = composed_harness(monkeypatch, tmp_path, provider="claude")
    usage = {"input_tokens": 12, "output_tokens": 8, "cache": {"read_tokens": 4}, "extra": "fixture-public-usage"}
    h.result = replace(h.result, usage_json=json.dumps(usage))
    try:
        output = json.loads(asyncio.run(h.coordinator.run("fixture-request")).final_output)
        assert output["usage"] == usage
        assert h.executor.execution_result.usage == usage
        assert h.executor.terminal["gate"] == "PASS"
        assert h.process_calls == len(h.received) == 1
    finally:
        h.owner.__exit__(None, None, None)


@pytest.mark.parametrize("unsafe_kind", ["secret", "machine_path"])
def test_concrete_claude_unsafe_success_usage_never_reaches_output_or_artifact(monkeypatch, tmp_path, unsafe_kind):
    h = composed_harness(monkeypatch, tmp_path, provider="claude")
    unsafe = h.source["ANTHROPIC_API_KEY"] if unsafe_kind == "secret" else "Q:/private/session"
    h.result = replace(h.result, usage_json=json.dumps({"input_tokens": 12, "untrusted_extra": unsafe}))
    code = "CREDENTIAL_ECHO" if unsafe_kind == "secret" else "MACHINE_PATH_ECHO"
    try:
        with pytest.raises(ValueError, match=code) as error:
            asyncio.run(h.coordinator.run("fixture-request"))
        assert unsafe not in str(error.value)
        assert h.executor.runtime_run.observation.result == h.result
        assert h.executor.runtime_run.observation.result.usage["untrusted_extra"] == unsafe
        assert h.executor.execution_result is None and h.executor.terminal is None
        assert h.process_calls == len(h.received) == 1
        assert len(composed_events(h)) == 1
        assert composed_events(h)[0]["eventKind"] == "launch"
        assert not (Path(h.selection.work_item) / "reviews/sdk-result.json").exists()
    finally:
        h.owner.__exit__(None, None, None)


def test_concrete_executor_scans_no_worker_error_before_return(monkeypatch, tmp_path):
    from sdk_execution import runtime
    h = composed_harness(monkeypatch, tmp_path, provider="claude")
    h.authority.denied.add("sdk_worker_start")
    original = runtime.run_admitted_review
    unsafe = h.source["ANTHROPIC_API_KEY"]
    def unsafe_preworker(*args, **kwargs):
        run = original(*args, **kwargs)
        assert run.observation is None and run.terminal["status"] == "blocked"
        return replace(run, launch_error=unsafe)
    monkeypatch.setattr(runtime, "run_admitted_review", unsafe_preworker)
    try:
        with pytest.raises(ValueError, match="CREDENTIAL_ECHO") as error:
            asyncio.run(h.coordinator.run("fixture-request"))
        assert unsafe not in str(error.value)
        assert h.executor.runtime_run.launch_error == unsafe
        assert h.executor.runtime_run.observation is None
        assert h.executor.execution_result is None
        assert h.executor.terminal["status"] == "blocked"
        assert h.process_calls == len(h.received) == 0
        assert len(composed_events(h)) == 2
    finally:
        h.owner.__exit__(None, None, None)


def test_concrete_executor_scans_exact_final_downgraded_result(monkeypatch, tmp_path):
    from sdk_execution import receiving
    h = composed_harness(monkeypatch, tmp_path)
    h.authority.denied.add("turn_start")
    observed = []
    original = receiving.scan_execution_output
    def scan(result, context):
        observed.append(result)
        return original(result, context)
    monkeypatch.setattr(receiving, "scan_execution_output", scan)
    try:
        asyncio.run(h.coordinator.run("fixture-request"))
        assert observed[-1] is h.executor.execution_result
        assert observed[-1].status == "incomplete"
        assert observed[-1].execution_error == "received_execution_incomplete"
        assert h.executor.runtime_run.observation.result.status == "completed"
    finally:
        h.owner.__exit__(None, None, None)


class FakeSession:
    """Public Session protocol shape only; no local substitute history engine."""

    session_id = "fixture-conversation"

    async def get_items(self, limit=None):
        return []

    async def add_items(self, items):
        pass

    async def pop_item(self):
        return None

    async def clear_session(self):
        pass


def with_session(harness, session):
    return coordinator.AgentsCoordinator(
        model=harness.model, coordinator_binding="fixture-coordinator",
        authority=harness.authority, executor=harness.executor, max_turns=2,
        session=session,
    )


def test_explicit_session_is_passed_unchanged_to_run_and_recreated_resume(harness):
    session = FakeSession()
    asyncio.run(with_session(harness, session).run("fixture-request"))
    # Caller restores the selected backend after restart; the coordinator neither
    # creates nor clears a store and RunState still comes only from its owner.
    restored_session = FakeSession()
    asyncio.run(with_session(harness, restored_session).resume("fixture-request", "fixture-snapshot"))
    assert harness.sdk.calls[0]["session"] is session
    assert harness.sdk.calls[1]["session"] is restored_session
    assert harness.authority.claims == ["fixture-snapshot"]
    assert harness.authority.effects == [
        "coordinator_start", "coordinator_model", "execute",
        "coordinator_resume", "coordinator_resume", "execute",
    ]


def test_no_session_keeps_original_runner_call(harness):
    asyncio.run(harness.instance.run("fixture-request"))
    asyncio.run(harness.instance.resume("fixture-request", "fixture-snapshot"))
    assert all("session" not in call for call in harness.sdk.calls)


@pytest.mark.parametrize("method", ["get_items", "add_items", "pop_item", "clear_session"])
def test_missing_session_protocol_stops_before_snapshot_claim(harness, method):
    session = FakeSession()
    setattr(session, method, None)
    with pytest.raises(coordinator.CoordinatorUnavailable, match=f"Session.{method}"):
        asyncio.run(with_session(harness, session).resume("fixture-request", "fixture-snapshot"))
    assert harness.authority.claims == harness.sdk.calls == harness.executor.calls == []


def test_missing_runner_session_support_stops_before_snapshot_claim(harness):
    async def run(agent, input, *, context, max_turns, hooks, run_config):
        pytest.fail("incompatible Runner must not be invoked")
    harness.sdk.Runner.run = run
    with pytest.raises(coordinator.CoordinatorUnavailable, match="Runner.run"):
        asyncio.run(with_session(harness, FakeSession()).resume("fixture-request", "fixture-snapshot"))
    assert harness.authority.claims == harness.executor.calls == []


@pytest.mark.parametrize("phase", ["before_model", "before_tool", "after_restore"])
def test_session_identity_drift_stops_dependent_effect(harness, phase):
    session = FakeSession()
    instance = with_session(harness, session)
    setattr(harness.sdk, phase, lambda: setattr(session, "session_id", "different-conversation"))
    with pytest.raises(coordinator.CoordinatorBindingError, match="session identity changed"):
        if phase == "after_restore":
            asyncio.run(instance.resume("fixture-request", "fixture-snapshot"))
        else:
            asyncio.run(instance.run("fixture-request"))
    assert harness.executor.calls == []


@pytest.mark.parametrize("change", [
    {"account_binding": "other-account"}, {"artifact_id": "other-artifact"},
    {"model": "other-model"}, {"coordinator_binding": "other-owner"},
])
def test_session_history_does_not_reauthorize_changed_resume_binding(harness, change):
    harness.sdk.after_restore = lambda: setattr(
        harness.authority, "current", replace(harness.authority.current, **change)
    )
    with pytest.raises(coordinator.CoordinatorBindingError):
        asyncio.run(with_session(harness, FakeSession()).resume("fixture-request", "fixture-snapshot"))
    assert harness.executor.calls == harness.sdk.calls == []


def test_session_resume_retains_owner_replay_exclusion(harness):
    instance = with_session(harness, FakeSession())
    asyncio.run(instance.resume("fixture-request", "fixture-snapshot"))
    with pytest.raises(PermissionError, match="consumed snapshot"):
        asyncio.run(instance.resume("fixture-request", "fixture-snapshot"))
    assert len(harness.executor.calls) == len(harness.sdk.calls) == 1


def test_factory_passes_caller_session_to_actual_executor_chain(monkeypatch, tmp_path):
    h = composed_harness(monkeypatch, tmp_path)
    session = FakeSession()
    try:
        instance, executor = coordinator.create_review_coordinator(**h.options, session=session)
        asyncio.run(instance.run("fixture-request"))
        assert h.sdk.calls[0]["session"] is session
        assert executor.terminal["status"] == "completed"
        assert h.process_calls == len(h.received) == 1
    finally:
        h.owner.__exit__(None, None, None)

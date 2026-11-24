"""Copilot Worker public wiring with actual scoped Host file effects, offline only."""
from dataclasses import replace
import json
from pathlib import Path

import pytest
from test_sdk_copilot_dispatch import prepare as task_prepare, execute_offline
from test_sdk_copilot import FakeSdk
from test_sdk_dispatch import owner, dispatch, runtime


def prepare(tmp_path, monkeypatch, *, role="backend-engineer"):
    task = task_prepare(tmp_path, monkeypatch)
    control = task.prevalidated.control
    control.ledger_role = role
    selected = replace(task.prevalidated,
        role_provenance=owner.external_role_provenance(control, "copilot"))
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    install = tmp_path / "install"
    install.mkdir()
    executable = install / "fixture.exe"
    executable.write_bytes(b"offline placeholder")
    monkeypatch.setattr(owner, "_resolve_launch_provider_command", lambda *a: ([str(executable)], None))
    monkeypatch.setenv("COPILOT_CLI_PATH", str(executable))
    state = tmp_path / "worker-state"
    state.mkdir()
    monkeypatch.setattr(runtime, "_worker_authority_roots",
        lambda provider="copilot": (tmp_path / "authority",))
    monkeypatch.chdir(workspace)
    path = control.sdk_task_binding
    binding = json.loads(path.read_text())
    binding.update(schemaVersion=4, installedHookRoot=None, contextMode="fresh",
        contextHandoff=None, writeWorkspace=str(workspace))
    path.write_text(json.dumps(binding))
    environment = {**task._environment, "COPILOT_BASE_DIRECTORY": str(state),
        "COPILOT_CLI_PATH": str(executable)}
    operation = dispatch.prepare_dispatch(selected, path, provider="copilot",
        source_environment=environment, cancellation_probe=lambda: False)
    capture = tmp_path / "capture" / "worker-run"
    capture.mkdir()
    operation.bind_capture_directory(capture)
    return operation

from types import SimpleNamespace
import asyncio
import os
from test_sdk_copilot_dispatch import sealed_result
from sdk_execution import copilot
from sdk_execution.contracts import json_text


def native():
    sdk = FakeSdk()
    sdk.Tool = lambda **kw: SimpleNamespace(**kw)
    sdk.ToolResult = lambda **kw: SimpleNamespace(**kw)
    sdk.PermissionDecisionApproveOnce = lambda: SimpleNamespace(kind="approve-once")
    return sdk


async def invoke(sdk, name, arguments, *, call_id, **changes):
    definition = next(row for row in sdk.options["tools"]["definitions"] if row.name == name)
    values = dict(session_id=sdk.session_id, tool_call_id=call_id, tool_name=name,
        arguments=arguments, agent_id=None)
    values.update(changes)
    return await definition.handler(SimpleNamespace(**values))


def execute_worker(operation, monkeypatch, sdk):
    import process_supervision.sdk_worker as worker
    from process_supervision.process_runner import ProcessRunnerV1
    req = operation.request
    sdk.content = json_text(dict(run_id=req.external_evidence_run_id,
        artifact_id=req.artifact_id, role=req.role, content="Scoped work evidence."))
    monkeypatch.setattr(copilot, "_load_sdk", lambda: sdk)
    def simulated(process, request, **kwargs):
        selection = runtime.runtime_selection_from_dict("copilot", kwargs["runtime_selection"])
        async def authorize(value, effect, context=None):
            if context is None:
                return kwargs["authority"](value, effect)
            return kwargs["authority"](value, effect, context)
        observations = []
        async def record(value):
            observations.append(value)
        with monkeypatch.context() as patch:
            for row in kwargs["environment"]:
                patch.setenv(row.name, row.value)
            executor = copilot.create_copilot_adapter(request,
                SimpleNamespace(authorize=authorize, record=record), selection)
            result = asyncio.run(executor.execute(request))
            assert tuple(observations) == result.observations
            return sealed_result(request, selection, result)
    monkeypatch.setattr(worker, "run_sdk_worker", simulated)
    with ProcessRunnerV1() as process:
        operation.execute(process)
    return operation.runtime_run


def test_actual_custom_write_edit_read_and_receiving_no_builtin_tools(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    target = Path(operation.request.cwd) / "source.txt"
    sdk = native()
    answers = []
    async def effects():
        answers.append(await invoke(sdk, "orchestrarium_write",
            {"file_path": str(target), "content": "old"}, call_id="write-1"))
        answers.append(await invoke(sdk, "orchestrarium_edit",
            {"file_path": str(target), "old_string": "old", "new_string": "new"}, call_id="edit-1"))
        answers.append(await invoke(sdk, "orchestrarium_read",
            {"file_path": str(target)}, call_id="read-1"))
    sdk.on_send = effects
    execute_worker(operation, monkeypatch, sdk)
    assert [answer.result_type for answer in answers] == ["success"] * 3
    assert answers[-1].text_result_for_llm == "new" and target.read_text() == "new"
    assert set(sdk.options["tools"]["available_tools"]) == {
        "orchestrarium_read", "orchestrarium_write", "orchestrarium_edit"}
    assert all(not tool.idempotent and not tool.overrides_built_in_tool
        for tool in sdk.options["tools"]["definitions"])
    result = operation.receive()
    assert result.terminal["executionRole"] == "external-worker"
    assert result.terminal["gate"] == "none" and result.terminal["authorizing"] is False
    assert result.terminal["closesRunIds"] == []


def test_forbidden_paths_and_foreign_invocations_do_not_write(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    root = Path(operation.request.cwd)
    outside = tmp_path / "outside.txt"
    outside.write_text("unchanged")
    protected = root / ".git" / "config"
    protected.parent.mkdir()
    protected.write_text("unchanged")
    linked = root / "hardlink.txt"
    os.link(outside, linked)
    sdk = native()
    answers = []
    async def effects():
        for index, path in enumerate((outside, protected, linked)):
            answers.append(await invoke(sdk, "orchestrarium_write",
                {"file_path": str(path), "content": "wrong"}, call_id=f"denied-{index}"))
        for index, change in enumerate(({"session_id": "foreign"}, {"agent_id": "child"})):
            answers.append(await invoke(sdk, "orchestrarium_write",
                {"file_path": str(root / "foreign.txt"), "content": "wrong"},
                call_id=f"foreign-{index}", **change))
    sdk.on_send = effects
    execute_worker(operation, monkeypatch, sdk)
    assert all(answer.result_type == "failure" for answer in answers)
    assert outside.read_text() == protected.read_text() == linked.read_text() == "unchanged"
    assert not (root / "foreign.txt").exists()
    operation.receive()


def test_revoked_host_before_custom_effect_never_writes(tmp_path, monkeypatch):
    operation = prepare(tmp_path, monkeypatch)
    target = Path(operation.request.cwd) / "denied.txt"
    sdk = native()
    answers = []
    async def effects():
        operation._cancelled = lambda: True
        answers.append(await invoke(sdk, "orchestrarium_write",
            {"file_path": str(target), "content": "wrong"}, call_id="revoked"))
    sdk.on_send = effects
    with pytest.raises(ValueError):
        execute_worker(operation, monkeypatch, sdk)
    assert len(answers) == 1 and answers[0].result_type == "failure"
    assert not target.exists()
    assert sdk.calls.count("send") == 1


def test_junction_cannot_redirect_host_write(tmp_path, monkeypatch):
    from _filesystem_fixture_support import _make_directory_junction
    operation = prepare(tmp_path, monkeypatch)
    outside = tmp_path / "outside-dir"
    outside.mkdir()
    target = outside / "source.txt"
    target.write_text("unchanged")
    link = Path(operation.request.cwd) / "junction"
    _make_directory_junction(link, outside)
    sdk = native()
    answers = []
    async def effects():
        answers.append(await invoke(sdk, "orchestrarium_write",
            {"file_path": str(link / "source.txt"), "content": "wrong"}, call_id="junction"))
    sdk.on_send = effects
    execute_worker(operation, monkeypatch, sdk)
    assert answers[0].result_type == "failure" and target.read_text() == "unchanged"


def test_committed_worker_receiving_recovery_never_repeats_file_effect(tmp_path, monkeypatch):
    from sdk_execution import receiving
    operation = prepare(tmp_path, monkeypatch)
    target = Path(operation.request.cwd) / "once.txt"
    sdk = native()
    answers = []
    async def effects():
        answers.append(await invoke(sdk, "orchestrarium_write",
            {"file_path": str(target), "content": "one effect"}, call_id="once"))
    sdk.on_send = effects
    execute_worker(operation, monkeypatch, sdk)
    assert answers[0].result_type == "success"
    original = receiving.receive_terminal
    options = {}
    def lost_ack(*args, **kwargs):
        options.update(kwargs)
        original(*args, **kwargs)
        raise RuntimeError("synthetic acknowledgement loss")
    with monkeypatch.context() as patch:
        patch.setattr(receiving, "receive_terminal", lost_ack)
        with pytest.raises(RuntimeError, match="acknowledgement loss"):
            operation.receive()
    item = Path(operation.selection.work_item)
    before = (item / "agent-runs.jsonl").read_bytes()
    file_before = target.stat().st_mtime_ns
    terminal = original(item, operation.request, operation.runtime_run.observation, **options)
    assert terminal["executionRole"] == "external-worker"
    assert terminal["authorizing"] is False
    assert target.read_text() == "one effect" and target.stat().st_mtime_ns == file_before
    assert (item / "agent-runs.jsonl").read_bytes() == before
    assert len(answers) == sdk.calls.count("send") == 1

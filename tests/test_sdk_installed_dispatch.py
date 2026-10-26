"""Source and installer-materialized entrypoint integration, offline only.

These tests do NOT claim Windows qualification. Real wrapper/dispatch/runtime/
duplex/receiving/ledger/receipt/capture owners execute in both layouts. Only native
platform admission, hook trust, and ProcessRunner.run are substituted; no SDK or
model is launched. Installed modules are loaded in an isolated module graph.
"""
from dataclasses import replace
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import provider_prompt as owner
from process_supervision import process_runner as processes
from sdk_execution import dispatch
from sdk_execution.contracts import ExecutionRequest, ExecutionResult, ReviewResult, json_text
from sdk_execution.worker import decode_frame, encode_frame, request_binding
from test_agent_run_ledger import prepare_valid_work_item


ENTRYPOINT_SCRIPT = ROOT / "scripts/invoke-codex-prompt.py"


EFFECTS = ("start", "client_start", "query", "thread_start", "query", "turn_start")


def entrypoint():
    spec = importlib.util.spec_from_file_location("source_codex_sdk_entrypoint", ENTRYPOINT_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.main


@pytest.fixture(params=("source", "installed"), autouse=True)
def runtime_layout(request, tmp_path, monkeypatch):
    if request.param == "source":
        yield
        return
    import production_installer as installer
    requested_target = tmp_path / "project/.agents/skills/lead/scripts"
    # Production composition includes lead hooks used by output safety scanning;
    # runtime helpers alone are not the complete installed lead dependency tree.
    with monkeypatch.context() as placement:
        placement.setattr(installer.tempfile, "tempdir", str(tmp_path))
        staged = installer._stage_canonical_lead_tree(
            ROOT, ROOT / "src.codex/skills/lead", requested_target)
    # Execute from the actual project-installed scope, not the temporary stage.
    # The current ledger owner deliberately rejects unassociated staging roots.
    requested_target.parent.parent.mkdir(parents=True)
    staged.path.rename(requested_target.parent)
    target = requested_target
    prefixes = ("provider_prompt", "sdk_execution", "process_supervision", "solution_attempt",
                "review_loop_state", "linked_runtime_subroots", "skill_pack_validator_runtime")
    def owned(name):
        return any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)
    saved = {name: module for name, module in sys.modules.items() if owned(name)}
    for name in saved:
        del sys.modules[name]
    try:
        with monkeypatch.context() as local:
            # A regular source package would outrank the installed namespace
            # package even with the installed directory first on sys.path.
            local.setattr(sys, "path", [str(target), *[path for path in sys.path
                if Path(path or ".").resolve() not in {ROOT, ROOT / "scripts"}]])
            importlib.invalidate_caches()
            installed_owner = importlib.import_module("provider_prompt")
            installed_processes = importlib.import_module("process_supervision.process_runner")
            installed_dispatch = importlib.import_module("sdk_execution.dispatch")
            contracts = importlib.import_module("sdk_execution.contracts")
            worker = importlib.import_module("sdk_execution.worker")
            for module in (installed_owner, installed_processes, installed_dispatch, contracts, worker):
                assert Path(module.__file__).is_relative_to(target)
            assert installed_owner.ledger_helper() == target / "agent-run-ledger.py"
            assert installed_owner.external_governance_capsule_path() == target / "external-prompt-governance.md"
            for name, value in dict(owner=installed_owner, processes=installed_processes,
                dispatch=installed_dispatch, ExecutionRequest=contracts.ExecutionRequest,
                ExecutionResult=contracts.ExecutionResult, ReviewResult=contracts.ReviewResult,
                json_text=contracts.json_text, decode_frame=worker.decode_frame,
                encode_frame=worker.encode_frame, request_binding=worker.request_binding,
                ENTRYPOINT_SCRIPT=target / "invoke-codex-prompt.py").items():
                local.setitem(globals(), name, value)
            yield
    finally:
        for name in list(sys.modules):
            if owned(name):
                del sys.modules[name]
        sys.modules.update(saved)


def setup_source(tmp_path, monkeypatch):
    item = prepare_valid_work_item(tmp_path)
    prompt = tmp_path / "prompt.txt"
    prompt.write_text("Review only this synthetic fixture. SOURCE_ENTRYPOINT_PRIVATE_TASK")
    binding = tmp_path / "binding.json"
    binding.write_text(json.dumps(dict(schemaVersion=1, accountBinding="synthetic-account",
        expectedAccountEmail=None, coordinatorBinding="synthetic-invocation",
        scope=["synthetic scope"], artifactIdentity="synthetic-artifact", maxEvents=100,
        jobMemoryLimitBytes=268435456)))
    executable = tmp_path / "synthetic-codex.exe"
    executable.write_bytes(b"This file is NEVER executed.")
    executable.chmod(0o700)
    home = tmp_path / "synthetic-home"
    home.mkdir()
    captures = tmp_path / "captures"
    monkeypatch.setenv("CODEX_BIN", str(executable))
    monkeypatch.setenv("CODEX_HOME", str(home))
    monkeypatch.setenv("CODEX_PROMPTS_DIR", str(captures))
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key-never-authenticated-123456789")
    monkeypatch.chdir(tmp_path)
    receipt = tmp_path / "terminal.json"
    artifact = item / "sdk-review.json"
    argv = ["synthetic-review", "--sdk-review-binding", str(binding),
        "--prompt-file", str(prompt), "--terminal-receipt", str(receipt),
        "--ledger", str(item), "--ledger-role", "qa-engineer",
        "--ledger-artifact", artifact.name, "--ledger-max-events", "100",
        "--ledger-max-bytes", "1048576", "--timeout-secs", "120",
        "--", "--model", "fixture-model", "-c", "model_reasoning_effort=high"]
    return item, receipt, artifact, captures, argv


def native_boundary(monkeypatch, artifact, *, receiving_collision=False):
    effects, requests, hook_calls = [], [], []
    monkeypatch.setattr(dispatch, "_require_supported_platform", lambda: None)
    monkeypatch.setattr(owner, "require_codex_hook_trust",
                        lambda *args, **kwargs: hook_calls.append((args, kwargs)) or 0)

    def forbidden(*args, **kwargs):
        pytest.fail("SDK entrypoint used a legacy CLI ledger/finalizer")
    monkeypatch.setattr(owner, "record_terminal", forbidden)
    monkeypatch.setattr(owner, "finalize_reserved_run_once", forbidden)

    def run(self, process_request, *, dialogue):
        assert type(process_request) is processes.SdkWorkerProcessRequestV1
        assert dialogue.protocol_id == processes.SdkWorkerWindowsProfileV1.profile_id
        assert len(hook_calls) == 1
        class Channel:
            def __init__(self):
                self.frames = []
                self.pending = None
                self.current = None
                self.sequence = 0

            def write_line(self, raw):
                value = decode_frame(raw)
                if value["kind"] == "execute":
                    assert self.current is None
                    self.current = ExecutionRequest.from_dict(value["request"])
                    requests.append((self.current, value["runtime_selection"]))
                    self.frames = list(EFFECTS) + ["result"]
                else:
                    assert value["kind"] == "authority_response"
                    assert value["sequence"] == self.pending
                    assert value["allowed"] is True
                    self.pending = None

            def read_line(self):
                assert self.pending is None
                if not self.frames:
                    raise EOFError()
                effect = self.frames.pop(0)
                request = self.current
                if effect != "result":
                    effects.append(effect)
                    self.pending = self.sequence
                    self.sequence += 1
                    return encode_frame(dict(kind="authority_request", run_id=request.run_id,
                        request_sha256=request_binding(request), sequence=self.pending, effect=effect))
                observed = dict(schemaVersion=1, adapter="openai-codex", sdkVersion="0.163.0",
                    runtimeVersion="0.163.0", model=request.model, effort=request.effort,
                    sandboxMode="read-only", approvalPolicy="deny_all", accountBinding=request.account_binding)
                result = ExecutionResult(request=request, status="completed", provider_status="completed",
                    native_thread_id="synthetic-thread", native_turn_id="synthetic-turn", protocol_closed=True,
                    sdk_execution_json=json_text(observed), review=ReviewResult(
                        request.external_evidence_run_id, request.artifact_id, request.role, "PASS", ()))
                return encode_frame({"kind": "result", "result": result.to_dict()})
        dialogue.handler(Channel())
        if receiving_collision:
            # A real exclusive-create failure, not a stub of receiving/ledger.
            artifact.write_text("independent concurrent owner; must remain untouched")
        failed = processes._request_failure(process_request,
            processes.ProcessSupervisionError("PSV1-INTERNAL", "execution"), time.monotonic())
        return replace(failed, outcome="success", terminal_stage="completed", failure_id=None,
            target_exit_code=0, resources_closed=True, policy_id="sdk-worker-v1",
            tree=processes.TreeObservationV1("synthetic", True, "EMPTY", True, True, True, True))
    monkeypatch.setattr(processes.ProcessRunnerV1, "run", run)
    return effects, requests, hook_calls


@pytest.mark.parametrize("explicit_ledger_caps", [True, False])
def test_entrypoint_real_dispatch_duplex_receiving_and_cleanup(tmp_path, monkeypatch, capsys, explicit_ledger_caps):
    item, receipt, artifact, captures, argv = setup_source(tmp_path, monkeypatch)
    if not explicit_ledger_caps:
        for flag in ("--ledger-max-events", "--ledger-max-bytes"):
            index = argv.index(flag)
            del argv[index:index + 2]
    effects, requests, hooks = native_boundary(monkeypatch, artifact)
    code = entrypoint()(argv)
    output = capsys.readouterr()
    assert code == 0, output.err
    assert effects == list(EFFECTS)
    assert len(requests) == len(hooks) == 1
    request, selection = requests[0]
    assert selection["expected_launch_sha256"]
    assert (selection["ledger_max_events"], selection["ledger_max_bytes"]) == (
        (100, 1048576) if explicit_ledger_caps else (None, None))
    assert request.prompt.count("SOURCE_ENTRYPOINT_PRIVATE_TASK") == 1
    assert receipt.read_text() == output.out
    payload = owner.parse_provider_result(output.out)
    assert payload["status"] == "completed" and payload["gate"] == "PASS"
    assert payload["authorizing"] is False
    assert artifact.read_text() == payload["resultText"] + "\n"
    rows = [json.loads(line) for line in (item / "agent-runs.jsonl").read_text().splitlines()]
    assert [row["eventKind"] for row in rows] == ["launch", "terminal"]
    assert rows[0]["runId"] == request.external_dispatch_id
    assert rows[1]["runId"] == request.external_evidence_run_id
    assert rows[1]["launchRunId"] == rows[0]["runId"]
    assert rows[1]["sdkExecution"] == payload["sdkExecution"]
    assert not list(captures.iterdir())
    assert "diagnostic retained" not in output.err


def test_entrypoint_receiving_failure_retains_diagnostic_without_replay(tmp_path, monkeypatch, capsys):
    item, receipt, artifact, captures, argv = setup_source(tmp_path, monkeypatch)
    effects, requests, hooks = native_boundary(monkeypatch, artifact, receiving_collision=True)
    code = entrypoint()(argv)
    output = capsys.readouterr()
    assert code == 1
    assert effects == list(EFFECTS) and len(requests) == len(hooks) == 1
    assert "E_SDK_REVIEW_RECEIVING_UNCONFIRMED" in output.err
    assert "SDK diagnostic retained:" in output.err
    assert output.out == "" and receipt.read_bytes() == b""
    assert artifact.read_text() == "independent concurrent owner; must remain untouched"
    rows = [json.loads(line) for line in (item / "agent-runs.jsonl").read_text().splitlines()]
    assert [row["eventKind"] for row in rows] == ["launch"]
    files = list(captures.rglob("sdk-recovery.json"))
    assert len(files) == 1
    diagnostic = json.loads(files[0].read_text())
    assert diagnostic["kind"] == "sdk-diagnostic-custody"
    assert diagnostic["externalDispatchId"] == requests[0][0].external_dispatch_id
    assert diagnostic["authorizing"] is False
    assert diagnostic["restorableObservation"] is False and diagnostic["replayAuthorized"] is False
    assert "SOURCE_ENTRYPOINT_PRIVATE_TASK" not in files[0].read_text()
    assert "synthetic-test-key" not in files[0].read_text()
    # Retry of the same entrypoint is rejected by the existing receipt owner;
    # neither provider execution nor a second ledger append can happen.
    before = (item / "agent-runs.jsonl").read_bytes()
    assert entrypoint()(argv) == 1
    capsys.readouterr()
    assert len(requests) == 1
    assert (item / "agent-runs.jsonl").read_bytes() == before


@pytest.mark.skipif(os.name == "nt", reason="Actual unsupported-platform check is POSIX-specific")
def test_entrypoint_unsupported_platform_has_no_effects(tmp_path, monkeypatch, capsys):
    item, receipt, artifact, captures, argv = setup_source(tmp_path, monkeypatch)
    def forbidden(*args, **kwargs):
        pytest.fail("unsupported platform reached native process boundary")
    monkeypatch.setattr(processes.ProcessRunnerV1, "run", forbidden)
    monkeypatch.setattr(owner, "require_codex_hook_trust", forbidden)
    assert entrypoint()(argv) == 1
    output = capsys.readouterr()
    assert "E_CODEX_SDK_WINDOWS_ONLY" in output.err
    assert output.out == ""
    assert not receipt.exists() and not artifact.exists() and not captures.exists()
    assert not (item / "agent-runs.jsonl").exists()

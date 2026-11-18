"""AGY-installed Codex SDK bridge; only native execution/trust is synthetic.

No source-checkout or global Codex runtime fallback is permitted. This does not
claim native Antigravity execution, model access, or Windows qualification.
"""
import importlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
import test_sdk_installed_dispatch as existing

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def installed_bridge(tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "isolated-home"
    home.mkdir()
    neighbor = project / ".agents/skills/codex-owned/SKILL.md"
    neighbor.parent.mkdir(parents=True)
    neighbor.write_bytes(b"Unrelated Codex installation stays unchanged")
    environment = dict(os.environ)
    environment.update(HOME=str(home), USERPROFILE=str(home), PYTHONDONTWRITEBYTECODE="1")
    environment.pop("ORCHESTRARIUM_NO_HYPOTHESIS_HOOK", None)
    installed = subprocess.run([sys.executable, str(ROOT / "scripts/install-client.py"),
        "--client", "antigravity", "--target", str(project), "--allow-unsafe-target"],
        cwd=ROOT, env=environment, capture_output=True, text=True, encoding="utf-8")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    target = project / ".agents/orchestrarium-antigravity/scripts"
    assert (target / "invoke-codex-prompt.py").is_file()
    prefixes = ("provider_prompt", "sdk_execution", "process_supervision", "solution_attempt",
                "review_loop_state", "linked_runtime_subroots", "skill_pack_validator_runtime")
    def owned(name):
        return any(name == prefix or name.startswith(prefix + ".") for prefix in prefixes)
    saved = {name: module for name, module in sys.modules.items() if owned(name)}
    for name in saved:
        del sys.modules[name]
    try:
        with monkeypatch.context() as local:
            local.setattr(sys, "path", [str(target), *[path for path in sys.path
                if Path(path or ".").resolve() not in {ROOT, ROOT / "scripts"}]])
            importlib.invalidate_caches()
            owner = importlib.import_module("provider_prompt")
            processes = importlib.import_module("process_supervision.process_runner")
            dispatch = importlib.import_module("sdk_execution.dispatch")
            contracts = importlib.import_module("sdk_execution.contracts")
            worker = importlib.import_module("sdk_execution.worker")
            for module in (owner, processes, dispatch, contracts, worker):
                assert Path(module.__file__).is_relative_to(target)
            assert owner.ledger_helper() == target / "agent-run-ledger.py"
            assert owner.external_governance_capsule_path() == target / "external-prompt-governance.md"
            for name, value in dict(owner=owner, processes=processes, dispatch=dispatch,
                ExecutionRequest=contracts.ExecutionRequest, ExecutionResult=contracts.ExecutionResult,
                ReviewResult=contracts.ReviewResult, json_text=contracts.json_text,
                decode_frame=worker.decode_frame, encode_frame=worker.encode_frame,
                request_binding=worker.request_binding, ENTRYPOINT_SCRIPT=target / "invoke-codex-prompt.py").items():
                local.setattr(existing, name, value)
            yield project, target, owner
            assert neighbor.read_bytes() == b"Unrelated Codex installation stays unchanged"
    finally:
        for name in list(sys.modules):
            if owned(name):
                del sys.modules[name]
        sys.modules.update(saved)


def test_installed_agy_reviewer_claim_receiving_and_one_launch(installed_bridge, monkeypatch, capsys):
    project, target, owner = installed_bridge
    item, receipt, artifact, captures, argv = existing.setup_source(project, monkeypatch)
    effects, requests, hooks = existing.native_boundary(monkeypatch, artifact)
    assert existing.entrypoint()(argv) == 0
    output = capsys.readouterr()
    payload = owner.parse_provider_result(output.out)
    assert payload["status"] == "completed" and payload["gate"] == "PASS"
    assert payload["authorizing"] is False
    assert receipt.read_text() == output.out
    assert artifact.read_text() == payload["resultText"] + "\n"
    rows = [json.loads(line) for line in (item / "agent-runs.jsonl").read_text().splitlines()]
    assert [row["eventKind"] for row in rows] == ["launch", "terminal"]
    assert rows[-1]["authorizing"] is False
    assert effects == list(existing.EFFECTS) and len(requests) == len(hooks) == 1
    assert not list(captures.iterdir())
    before = {path: path.read_bytes() for path in (receipt, artifact, item / "agent-runs.jsonl")}
    assert existing.entrypoint()(argv) == 1
    capsys.readouterr()
    assert len(requests) == 1
    assert before == {path: path.read_bytes() for path in before}


def test_installed_agy_unconfirmed_receiving_preserves_diagnostic_without_replay(installed_bridge, monkeypatch, capsys):
    project, _, _ = installed_bridge
    existing.test_entrypoint_receiving_failure_retains_diagnostic_without_replay(project, monkeypatch, capsys)


def test_installed_agy_missing_terminal_target_stops_before_native(installed_bridge, monkeypatch, capsys):
    project, _, _ = installed_bridge
    item, receipt, artifact, captures, argv = existing.setup_source(project, monkeypatch)
    index = argv.index("--terminal-receipt")
    del argv[index:index + 2]
    _, requests, _ = existing.native_boundary(monkeypatch, artifact)
    assert existing.entrypoint()(argv) == 1
    assert not requests and not receipt.exists() and not artifact.exists()
    assert not (item / "agent-runs.jsonl").exists()
    capsys.readouterr()


def test_installed_agy_held_helper_drift_and_missing_helper_never_fallback(installed_bridge):
    project, target, owner = installed_bridge
    held = owner._ledger_helper_binding()
    assert held is not None and held.helper == target / "agent-run-ledger.py"
    held.assert_current()
    original = held.helper.read_bytes()
    held.helper.write_bytes(original + b"\n# fixture currentness change\n")
    with pytest.raises((OSError, RuntimeError, ValueError)):
        held.assert_current()
    retained = project / "retained-ledger-helper.py"
    held.helper.rename(retained)
    assert owner._ledger_helper_binding() is None
    assert retained.exists()


def test_installed_agy_consultant_uses_task_receiving_without_review_authority(installed_bridge, monkeypatch, capsys):
    project, _, owner = installed_bridge
    item, receipt, artifact, captures, argv = existing.setup_source(project, monkeypatch)
    argv[argv.index("--sdk-review-binding")] = "--sdk-task-binding"
    argv[argv.index("--ledger-role") + 1] = "consultant"
    from sdk_execution.contracts import ExecutionResult, TaskResult, json_text
    def task_result(request, observed):
        return ExecutionResult(request=request, status="completed", provider_status="completed",
            native_thread_id="synthetic-thread", native_turn_id="synthetic-turn", protocol_closed=True,
            sdk_execution_json=json_text(observed), task=TaskResult(
                request.external_evidence_run_id, request.artifact_id, request.role, "Bounded synthetic advice."))
    _, requests, _ = existing.native_boundary(monkeypatch, artifact, result_factory=task_result)
    assert existing.entrypoint()(argv) == 0
    output = capsys.readouterr()
    payload = owner.parse_provider_result(output.out)
    assert payload["status"] == "completed" and payload["gate"] == "none"
    assert payload["authorizing"] is False
    task = json.loads(payload["resultText"])["task"]
    assert task["role"] == "consultant" and task["content"] == "Bounded synthetic advice."
    rows = [json.loads(line) for line in (item / "agent-runs.jsonl").read_text().splitlines()]
    assert [row["eventKind"] for row in rows] == ["launch", "terminal"]
    assert rows[-1]["gate"] == "none" and rows[-1]["authorizing"] is False
    assert len(requests) == 1 and requests[0][0].result_kind == "task"

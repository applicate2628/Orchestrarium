from __future__ import annotations

from dataclasses import replace
import io
import importlib.util
import json
import sys
from pathlib import Path
import inspect
from types import SimpleNamespace

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("slice_b_fix_controls", ROOT / "scripts/provider_prompt.py")
assert SPEC and SPEC.loader
OWNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = OWNER
SPEC.loader.exec_module(OWNER)


class _NoopRunner:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _execution_provenance() -> object:
    return OWNER.ExecutionProvenance(
        work_item="item-frozen",
        assigned_internal_role="qa-engineer",
        provider="kimi",
        model="kimi-code/k3",
        effort="unsupported",
        launch_flags=(),
        artifact_identity="sha256:" + "a" * 64,
        external_dispatch_id="dispatch-frozen",
        external_evidence_run_id="evidence-frozen",
        effort_mapping_loss="no-native-effort-control",
    )


def _terminal_outcome() -> object:
    return OWNER.FinalOutcome(
        0,
        "COMPLETE:EXTERNAL_NONAUTHORIZING",
        "completed",
        "PASS",
        "fixture",
        0,
        "COMPLETE:PASS",
        "completed",
        "PASS",
        "fixture",
        "complete",
        0,
        "",
        False,
        0,
    )


def _external_terminal_row(provenance: object) -> dict[str, object]:
    return {
        "schemaVersion": 2,
        "runId": provenance.external_evidence_run_id,
        "eventKind": "terminal",
        "launchRunId": provenance.external_dispatch_id,
        "terminalClass": "external-nonauthorizing",
        "authorizing": False,
        "closesRunIds": [],
        **provenance.terminal_projection(),
    }


@pytest.mark.parametrize("field", tuple(OWNER.ExecutionProvenance.__dataclass_fields__))
def test_execution_provenance_drift_is_rejected_before_envelope_or_ledger_sink(
    field: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _execution_provenance()
    changed_value = (
        ("--model", "changed")
        if field == "launch_flags"
        else f"changed-{field}"
    )
    if field in {"provider", "model", "effort", "launch_flags"}:
        with pytest.raises(ValueError, match="E_EXTERNAL_PROVENANCE_INVALID"):
            replace(expected, **{field: changed_value})
        return
    changed = replace(expected, **{field: changed_value})
    output = io.StringIO()
    monkeypatch.setattr(OWNER.sys, "stdout", output)
    ledger_calls: list[list[str]] = []
    monkeypatch.setattr(
        OWNER,
        "run_ledger",
        lambda _runner, args: ledger_calls.append(args) or True,
    )

    with pytest.raises(ValueError, match="E_EXTERNAL_PROVENANCE_MISMATCH"):
        OWNER.build_provider_result_line(
            "kimi",
            "kimi-code/k3",
            "unsupported",
            "fixture",
            _terminal_outcome(),
            cancelled=False,
            timed_out=False,
            provenance=changed,
            expected_provenance=expected,
        )
    assert output.getvalue() == ""

    with pytest.raises(ValueError, match="E_EXTERNAL_PROVENANCE_MISMATCH"):
        OWNER.record_terminal(
            OWNER.Control(ledger="mutable-item", ledger_artifact="mutable-artifact"),
            "kimi",
            "kimi-code/k3",
            "unsupported",
            "mutable-topic",
            "mutable-launch",
            _terminal_outcome(),
            cancelled=False,
            timed_out=False,
            result_delivered=True,
            runner=object(),
            role_provenance=OWNER.ExternalRoleProvenance(
                "qa-engineer", "external-reviewer"
            ),
            provenance=changed,
            expected_provenance=expected,
        )
    assert ledger_calls == []


def test_execution_provenance_has_identical_envelope_and_ledger_projection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    provenance = _execution_provenance()
    encoded = OWNER.build_provider_result_line(
        "kimi",
        "kimi-code/k3",
        "unsupported",
        "fixture",
        _terminal_outcome(),
        cancelled=False,
        timed_out=False,
        provenance=provenance,
        expected_provenance=provenance,
        role_provenance=OWNER.ExternalRoleProvenance(
            "qa-engineer", "external-reviewer"
        ),
    )
    envelope = OWNER.parse_provider_result(encoded)
    assert {key: envelope[key] for key in provenance.payload()} == provenance.payload()

    ledger = tmp_path / "item-frozen"
    ledger_args: list[list[str]] = []

    def persist_terminal(_runner: object, args: list[str]) -> bool:
        ledger_args.append(args)
        values = {
            args[index]: args[index + 1]
            for index in range(len(args) - 1)
            if isinstance(args[index], str) and args[index].startswith("--")
        }
        terminal = {
            "schemaVersion": 2,
            "runId": values["--run-id"],
            "eventKind": "terminal",
            "launchRunId": values["--launch-run-id"],
            "terminalClass": values["--terminal-class"],
            "authorizing": values["--authorizing"] == "true",
            "closesRunIds": [],
            "workItem": values["--work-item-name"],
            "assignedRole": values["--assigned-role"],
            "provider": values["--provider"],
            "model": values["--model"],
            "effort": values["--effort"],
            "launchFlags": json.loads(values["--launch-flags-json"]),
            "artifactIdentity": values["--artifact-identity"],
            "externalDispatchId": values["--external-dispatch-id"],
            "externalEvidenceRunId": values["--external-evidence-run-id"],
            "effortMappingLoss": values["--effort-mapping-loss"],
            "actualExecutionPath": values["--actual-execution-path"],
        }
        ledger.mkdir()
        (ledger / "agent-runs.jsonl").write_text(
            json.dumps(terminal) + "\n", encoding="utf-8"
        )
        return True

    monkeypatch.setattr(OWNER, "run_ledger", persist_terminal)
    assert OWNER.record_terminal(
        OWNER.Control(ledger=ledger, ledger_artifact="mutable-artifact"),
        "kimi",
        "kimi-code/k3",
        "unsupported",
        "mutable-topic",
        provenance.external_dispatch_id,
        _terminal_outcome(),
        cancelled=False,
        timed_out=False,
        result_delivered=True,
        runner=object(),
        role_provenance=OWNER.ExternalRoleProvenance(
            "qa-engineer", "external-reviewer"
        ),
        provenance=provenance,
        expected_provenance=provenance,
    )
    args = ledger_args[0]
    values = {
        args[index]: args[index + 1]
        for index in range(len(args) - 1)
        if isinstance(args[index], str) and args[index].startswith("--")
    }
    assert values["--work-item-name"] == provenance.work_item
    assert values["--run-id"] == provenance.external_evidence_run_id
    assert values["--artifact-identity"] == provenance.artifact_identity
    assert values["--external-dispatch-id"] == provenance.external_dispatch_id
    assert values["--external-evidence-run-id"] == provenance.external_evidence_run_id
    assert values["--effort-mapping-loss"] == provenance.effort_mapping_loss
    persisted = json.loads((ledger / "agent-runs.jsonl").read_text(encoding="utf-8"))
    assert {
        key: persisted[key] for key in provenance.terminal_projection()
    } == provenance.terminal_projection()


@pytest.mark.parametrize("field", tuple(_execution_provenance().terminal_projection()))
def test_external_terminal_readback_rejects_each_post_append_provenance_mutation(
    field: str, tmp_path: Path
) -> None:
    provenance = _execution_provenance()
    ledger = tmp_path / "item-frozen"
    ledger.mkdir()
    ledger_path = ledger / "agent-runs.jsonl"
    terminal = _external_terminal_row(provenance)
    ledger_path.write_text(json.dumps(terminal) + "\n", encoding="utf-8")

    control = OWNER.Control(ledger=ledger)
    assert OWNER.read_back_external_terminal(
        control, provenance.provider, provenance.external_dispatch_id, provenance
    ) == terminal

    terminal[field] = f"mutated-{field}"
    ledger_path.write_text(json.dumps(terminal) + "\n", encoding="utf-8")
    assert OWNER.read_back_external_terminal(
        control, provenance.provider, provenance.external_dispatch_id, provenance
    ) is None


class _ReadlineOnlyStream:
    """Virtual text stream that rejects whole-file and iterator consumption."""

    def __init__(self, content: str) -> None:
        self._content = content
        self._offset = 0
        self.readline_sizes: list[int] = []

    @property
    def eof(self) -> bool:
        return self._offset == len(self._content)

    def __enter__(self) -> _ReadlineOnlyStream:
        return self

    def __exit__(self, *_args: object) -> bool:
        return False

    def read(self, *_args: object) -> str:
        pytest.fail("whole-file read reached")

    def read_text(self, *_args: object) -> str:
        pytest.fail("Path.read_text reached")

    def readlines(self, *_args: object) -> list[str]:
        pytest.fail("whole-file readlines reached")

    def __iter__(self) -> object:
        pytest.fail("stream iteration reached")

    def readline(self, size: int = -1) -> str:
        assert size > 0, "readline must have a bound"
        self.readline_sizes.append(size)
        if self._offset == len(self._content):
            return ""
        stop = min(self._offset + size, len(self._content))
        newline = self._content.find("\n", self._offset, stop)
        if newline >= 0:
            stop = newline + 1
        value = self._content[self._offset:stop]
        self._offset = stop
        return value


class _ReadlineOnlyLedgerPath:
    def __init__(self, stream: _ReadlineOnlyStream) -> None:
        self._stream = stream

    def __truediv__(self, child: str) -> _ReadlineOnlyLedgerPath:
        assert child == "agent-runs.jsonl"
        return self

    def open(self, *_args: object, **_kwargs: object) -> _ReadlineOnlyStream:
        return self._stream


def _readback_from_virtual_stream(
    content: str,
    provenance: object,
    monkeypatch: pytest.MonkeyPatch,
    *,
    max_line_chars: int,
    max_events: int,
) -> tuple[dict[str, object] | None, _ReadlineOnlyStream]:
    stream = _ReadlineOnlyStream(content)
    monkeypatch.setattr(OWNER, "Path", lambda _value: _ReadlineOnlyLedgerPath(stream))
    monkeypatch.setattr(
        OWNER,
        "_agent_run_jsonl_limits",
        lambda: (max_line_chars, max_events),
    )
    result = OWNER.read_back_external_terminal(
        OWNER.Control(ledger="virtual-ledger"),
        provenance.provider,
        provenance.external_dispatch_id,
        provenance,
    )
    return result, stream


def test_external_terminal_readback_streams_one_target_to_eof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provenance = _execution_provenance()
    terminal = _external_terminal_row(provenance)
    other = {"eventKind": "launch", "launchRunId": "other"}
    limit = len(json.dumps(terminal)) + 16
    result, stream = _readback_from_virtual_stream(
        "\n".join((json.dumps(other), json.dumps(terminal), json.dumps(other))) + "\n",
        provenance,
        monkeypatch,
        max_line_chars=limit,
        max_events=8,
    )
    assert result == terminal
    assert stream.eof
    assert stream.readline_sizes and set(stream.readline_sizes) == {limit + 2}


def test_external_terminal_readback_limits_match_canonical_schema() -> None:
    schema = json.loads(
        (ROOT / "shared" / "schemas" / "agent-runs.schema.json").read_text(
            encoding="utf-8"
        )
    )["x-orchestrarium-jsonl"]
    assert OWNER._agent_run_jsonl_limits() == (
        schema["maxLineChars"],
        schema["maxEvents"],
    )


@pytest.mark.parametrize(
    ("rows", "trailing_newline"),
    (
        (lambda terminal, _limit: (json.dumps(terminal), json.dumps(terminal)), True),
        (lambda terminal, _limit: ("{malformed", json.dumps(terminal)), True),
        (lambda terminal, _limit: (json.dumps(terminal), "{malformed"), True),
        (lambda terminal, limit: ("x" * (limit + 1), json.dumps(terminal)), True),
        (lambda terminal, _limit: (json.dumps(terminal), '{"truncated":'), False),
    ),
    ids=("duplicate", "malformed-before", "malformed-after", "overlong", "truncated-json"),
)
def test_external_terminal_readback_stream_rejects_invalid_ledger_to_eof(
    rows: object, trailing_newline: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    provenance = _execution_provenance()
    terminal = _external_terminal_row(provenance)
    limit = len(json.dumps(terminal)) + 16
    content = "\n".join(rows(terminal, limit)) + ("\n" if trailing_newline else "")
    result, stream = _readback_from_virtual_stream(
        content,
        provenance,
        monkeypatch,
        max_line_chars=limit,
        max_events=8,
    )
    assert result is None
    assert stream.eof


def test_external_terminal_readback_stream_rejects_event_overflow_to_eof(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provenance = _execution_provenance()
    terminal = _external_terminal_row(provenance)
    other = {"eventKind": "launch", "launchRunId": "other"}
    limit = len(json.dumps(terminal)) + 16
    result, stream = _readback_from_virtual_stream(
        "\n".join((json.dumps(other), json.dumps(other), json.dumps(terminal))) + "\n",
        provenance,
        monkeypatch,
        max_line_chars=limit,
        max_events=2,
    )
    assert result is None
    assert stream.eof


def test_external_terminal_readback_counts_malformed_records_toward_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provenance = _execution_provenance()
    terminal = _external_terminal_row(provenance)
    limit = len(json.dumps(terminal)) + 16
    result, stream = _readback_from_virtual_stream(
        "{bad-1\n{bad-2\n{bad-3\n" + json.dumps(terminal) + "\n",
        provenance,
        monkeypatch,
        max_line_chars=limit,
        max_events=2,
    )
    assert result is None
    assert not stream.eof
    assert len(stream.readline_sizes) == 3


def test_unavailable_providers_ship_no_unreachable_executor_surface() -> None:
    launch_source = inspect.getsource(OWNER.launch)
    forbidden_runtime_branches = (
        "resolve_grok_executable",
        "_probe_grok_capabilities",
        "build_kimi_launch_plan",
        "build_grok_launch_plan",
        "external_child_environment",
        "capture_grok_repo_snapshot",
    )
    assert all(name not in launch_source for name in forbidden_runtime_branches)


def test_unavailable_provider_removal_preserves_codex_claude_flag_forwarding() -> None:
    legacy = OWNER.parse_control(["topic", "--task-class", "review", "--role", "qa-engineer"])
    assert legacy.task_class is None and legacy.role is None
    assert legacy.provider_flags == ["--task-class", "review", "--role", "qa-engineer"]
    assert not hasattr(OWNER, "parse_external_control")


def test_external_prompt_snapshot_is_bounded_and_strict_utf8(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_bytes(b"12345")
    control = OWNER.Control(prompt_file=prompt)
    monkeypatch.setattr(OWNER, "PROMPT_SNAPSHOT_MAX_BYTES", 4)
    with pytest.raises(ValueError, match="E_EXTERNAL_PROMPT_INVALID"):
        OWNER.prompt_bytes(control, external=True)
    prompt.write_bytes(b"\xff")
    with pytest.raises(ValueError, match="E_EXTERNAL_PROMPT_INVALID"):
        OWNER.prompt_bytes(control, external=True)


@pytest.mark.parametrize(
    ("provider", "stable_id"),
    (
        ("grok", "E_EXTERNAL_DISPATCH_POLICY_DENIED"),
    ),
)
def test_admitted_unavailable_route_stops_before_prompt_resolution_capture_probe_or_popen(
    provider: str, stable_id: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(name: str):
        return lambda *_args, **_kwargs: pytest.fail(f"{name} reached")

    def unavailable_decision(selected_provider: str, task_class: str, role: str):
        return {
            "schemaVersion": 1,
            "status": "unavailable",
            "stableId": None,
            "provider": selected_provider,
            "taskClass": task_class,
            "role": role,
            "requiredModelTier": "balanced",
            "requiredEffort": "high",
            "mutationClass": "read-only",
            "nativeEffort": "high",
            "effortMappingLoss": "none",
            "finalAuthorizingRole": False,
            "executionAuthorized": False,
            "independentVerification": True,
            "fallback": "none",
        }

    monkeypatch.setattr(
        OWNER,
        "_load_external_dispatch_resolver",
        lambda: SimpleNamespace(resolve_external_dispatch=unavailable_decision),
        raising=False,
    )
    monkeypatch.setattr(OWNER, "prompt_bytes", forbidden("prompt_bytes"))
    monkeypatch.setattr(OWNER, "resolve_provider_command", forbidden("resolution"))
    monkeypatch.setattr(OWNER, "resolve_enrolled_kimi_command", forbidden("enrollment"))
    monkeypatch.setattr(OWNER.RunCaptureLifecycle, "create", forbidden("capture"))
    monkeypatch.setattr(OWNER, "ProcessRunnerV1", forbidden("runner"))
    monkeypatch.setattr(OWNER, "ledger_helper", forbidden("ledger"))
    monkeypatch.setattr(OWNER.subprocess, "Popen", forbidden("Popen"))
    monkeypatch.setattr(OWNER.shutil, "which", forbidden("probe"))

    assert OWNER.launch(
        provider, ["admitted-route", "--task-class", "exploration", "--role", "analyst"]
    ) == 1
    assert stable_id in capsys.readouterr().err


def _accepted_kimi_decision(task_class: str, role: str) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "status": "external-authorized",
        "stableId": None,
        "provider": "kimi",
        "taskClass": task_class,
        "role": role,
        "requiredModelTier": "balanced",
        "requiredEffort": "high",
        "mutationClass": "read-only",
        "nativeEffort": "unsupported",
        "effortMappingLoss": "no-native-effort-control",
        "finalAuthorizingRole": False,
        "executionAuthorized": True,
        "independentVerification": True,
        "fallback": "none",
    }


@pytest.mark.parametrize(
    "decision",
    (
        {**_accepted_kimi_decision("review", "qa-engineer"), "status": "denied"},
        {**_accepted_kimi_decision("review", "qa-engineer"), "provider": "grok"},
        {"schemaVersion": 1},
        {**_accepted_kimi_decision("review", "qa-engineer"), "unexpected": True},
    ),
)
def test_policy_rejection_stops_before_kimi_prompt_auth_enrollment_run_ledger_or_runner(
    decision: dict[str, object], monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(name: str):
        return lambda *_args, **_kwargs: pytest.fail(f"{name} reached")

    monkeypatch.setattr(
        OWNER,
        "_load_external_dispatch_resolver",
        lambda: SimpleNamespace(
            resolve_external_dispatch=lambda *_args: decision
        ),
        raising=False,
    )
    for name in (
        "prompt_bytes",
        "resolve_provider_auth_configuration",
        "resolve_enrolled_kimi_command",
        "ledger_helper",
        "run_ledger",
        "run_provider_process",
    ):
        monkeypatch.setattr(OWNER, name, forbidden(name))
    monkeypatch.setattr(OWNER.RunCaptureLifecycle, "create", forbidden("capture"))
    monkeypatch.setattr(OWNER, "ProcessRunnerV1", forbidden("runner"))

    assert OWNER.launch(
        "kimi", ["policy-trap", "--task-class", "review", "--role", "qa-engineer"]
    ) == 1
    assert "E_EXTERNAL_DISPATCH_POLICY_DENIED" in capsys.readouterr().err


def test_kimi_admission_failure_commits_nonauthorizing_terminal_without_downstream_side_effects(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt = tmp_path / "terminal.jsonl"

    def forbidden(name: str):
        return lambda *_args, **_kwargs: pytest.fail(f"{name} reached")

    monkeypatch.setattr(
        OWNER,
        "_load_external_dispatch_resolver",
        lambda: SimpleNamespace(
            resolve_external_dispatch=lambda *_args: _accepted_kimi_decision(
                "review", "qa-engineer"
            )
        ),
        raising=False,
    )
    monkeypatch.setattr(
        OWNER,
        "_resolve_enrolled_kimi_launch",
        lambda: (_ for _ in ()).throw(ValueError("E_KIMI_ADMISSION_EQUIVOCATION")),
    )
    for name in (
        "prompt_bytes",
        "resolve_provider_auth_configuration",
        "ledger_helper",
        "run_ledger",
        "materialize_kimi_agent_payload",
        "run_provider_process",
    ):
        monkeypatch.setattr(OWNER, name, forbidden(name))
    monkeypatch.setattr(OWNER.RunCaptureLifecycle, "create", forbidden("capture"))

    assert OWNER.launch(
        "kimi",
        [
            "admission-rejection",
            "--task-class",
            "review",
            "--role",
            "qa-engineer",
            "--terminal-receipt",
            str(receipt.resolve()),
        ],
    ) == 1

    line = receipt.read_text(encoding="utf-8").strip()
    assert line.startswith(OWNER.RESULT_PREFIX)
    payload = json.loads(line[len(OWNER.RESULT_PREFIX) :])
    assert payload["authorizing"] is False
    assert payload["terminalClass"] == "external-nonauthorizing"
    assert payload["status"] == "blocked"


@pytest.mark.parametrize(
    "argv",
    (
        ["missing-task", "--role", "qa-engineer"],
        ["missing-role", "--task-class", "review"],
        ["duplicate-task", "--task-class", "review", "--task-class", "review", "--role", "qa-engineer"],
        ["duplicate-role", "--task-class", "review", "--role", "qa-engineer", "--role", "qa-engineer"],
        ["mismatched-ledger", "--task-class", "review", "--role", "qa-engineer", "--ledger-role", "analyst"],
    ),
)
def test_invalid_kimi_policy_arguments_stop_before_resolver_or_side_effects(
    argv: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(name: str):
        return lambda *_args, **_kwargs: pytest.fail(f"{name} reached")

    monkeypatch.setattr(OWNER, "_load_external_dispatch_resolver", forbidden("resolver"), raising=False)
    monkeypatch.setattr(OWNER, "prompt_bytes", forbidden("prompt"))
    monkeypatch.setattr(OWNER, "ProcessRunnerV1", forbidden("runner"))
    monkeypatch.setattr(OWNER.RunCaptureLifecycle, "create", forbidden("capture"))

    assert OWNER.launch("kimi", argv) == 1


def test_missing_or_malformed_external_policy_loader_stops_before_kimi_side_effects(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(name: str):
        return lambda *_args, **_kwargs: pytest.fail(f"{name} reached")

    monkeypatch.setattr(
        OWNER,
        "_load_external_dispatch_resolver",
        lambda: (_ for _ in ()).throw(RuntimeError("malformed resolver")),
    )
    monkeypatch.setattr(OWNER, "prompt_bytes", forbidden("prompt"))
    monkeypatch.setattr(OWNER, "resolve_enrolled_kimi_command", forbidden("enrollment"))
    monkeypatch.setattr(OWNER, "ProcessRunnerV1", forbidden("runner"))
    monkeypatch.setattr(OWNER.RunCaptureLifecycle, "create", forbidden("capture"))

    assert OWNER.launch(
        "kimi", ["missing-resolver", "--task-class", "review", "--role", "qa-engineer"]
    ) == 1
    assert "E_EXTERNAL_DISPATCH_POLICY_DENIED" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("task_class", "role"),
    (
        ("engineering", "backend-engineer"),
        ("review", "architecture-reviewer"),
        ("review", "security-reviewer"),
        ("planning", "lead"),
        ("review", "unknown-role"),
    ),
)
def test_policy_denies_unadmitted_kimi_roles_before_side_effects(
    task_class: str,
    role: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def forbidden(name: str):
        return lambda *_args, **_kwargs: pytest.fail(f"{name} reached")

    monkeypatch.setattr(OWNER, "prompt_bytes", forbidden("prompt"))
    monkeypatch.setattr(OWNER, "resolve_enrolled_kimi_command", forbidden("enrollment"))
    monkeypatch.setattr(OWNER, "ProcessRunnerV1", forbidden("runner"))
    monkeypatch.setattr(OWNER.RunCaptureLifecycle, "create", forbidden("capture"))

    assert OWNER.launch(
        "kimi", ["policy-denial", "--task-class", task_class, "--role", role]
    ) == 1
    assert "E_EXTERNAL_DISPATCH_POLICY_DENIED" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("task_class", "role", "execution_role"),
    (
        ("exploration", "explorer", "external-worker"),
        ("exploration", "analyst", "external-worker"),
        ("planning", "planner", "external-worker"),
        ("review", "qa-engineer", "external-reviewer"),
    ),
)
def test_authorized_kimi_policy_matrix_binds_policy_role_to_provenance_before_runner(
    task_class: str,
    role: str,
    execution_role: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, str, str]] = []

    def resolve(selected_provider: str, selected_task: str, selected_role: str):
        calls.append((selected_provider, selected_task, selected_role))
        return _accepted_kimi_decision(selected_task, selected_role)

    monkeypatch.setattr(
        OWNER,
        "_load_external_dispatch_resolver",
        lambda: SimpleNamespace(resolve_external_dispatch=resolve),
        raising=False,
    )
    prevalidated = OWNER._prevalidate_policy_bound_external_launch(
        "kimi", ["policy-positive", "--task-class", task_class, "--role", role]
    )

    assert calls == [("kimi", task_class, role)]
    assert prevalidated.control.ledger_role == role
    assert prevalidated.role_provenance.assigned_role == role
    assert prevalidated.role_provenance.execution_role == execution_role


def test_kimi_launch_rejects_non_windows_before_runner(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module_os = OWNER.os

    class NonWindowsPlatform:
        name = "posix"

        def __getattr__(self, name: str) -> object:
            return getattr(module_os, name)

    monkeypatch.setattr(OWNER, "os", NonWindowsPlatform())
    monkeypatch.setattr(
        OWNER,
        "_load_external_dispatch_resolver",
        lambda: SimpleNamespace(
            resolve_external_dispatch=lambda *_args: _accepted_kimi_decision(
                "review", "qa-engineer"
            )
        ),
        raising=False,
    )
    monkeypatch.setattr(
        OWNER,
        "_launch_with_runner",
        lambda *_args, **_kwargs: pytest.fail("runner reached"),
    )

    assert OWNER.launch(
        "kimi", ["non-windows", "--task-class", "review", "--role", "qa-engineer"]
    ) == 1
    assert "E_KIMI_WINDOWS_ONLY" in capsys.readouterr().err


def test_installed_kimi_grok_contract_splits_admitted_and_unavailable_routes() -> None:
    """Installed contracts admit Kimi read-only while keeping Grok unavailable."""
    live_consumers = (
        "shared/AGENTS.shared.md",
        "src.claude/agents/contracts/external-dispatch.md",
        "src.claude/agents/contracts/operating-model.md",
        "src.claude/agents/contracts/subagent-contracts.md",
        "src.codex/skills/lead/external-dispatch.md",
        "src.codex/skills/lead/operating-model.md",
    )
    for relative in live_consumers:
        text = (ROOT / relative).read_text(encoding="utf-8")
        assert "Kimi" in text and "read-only" in text, relative
        assert "independent" in text and (
            "nonauthorizing" in text or "non-authorizing" in text
        ), relative
        assert "Grok" in text and "unavailable" in text, relative
        assert "Kimi/Grok are unavailable" not in text, relative

from __future__ import annotations

import importlib.util
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
        "_kimi_sanitized_runtime_home",
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
    observed: list[object] = []

    def resolve(selected_provider: str, selected_task: str, selected_role: str):
        calls.append((selected_provider, selected_task, selected_role))
        return _accepted_kimi_decision(selected_task, selected_role)

    monkeypatch.setattr(
        OWNER,
        "_load_external_dispatch_resolver",
        lambda: SimpleNamespace(resolve_external_dispatch=resolve),
        raising=False,
    )
    monkeypatch.setattr(OWNER, "ProcessRunnerV1", _NoopRunner)
    monkeypatch.setattr(
        OWNER,
        "_launch_with_runner",
        lambda *_args, prevalidated=None: observed.append(prevalidated) or 0,
    )

    assert OWNER.launch(
        "kimi", ["policy-positive", "--task-class", task_class, "--role", role]
    ) == 0
    assert calls == [("kimi", task_class, role)]
    assert observed[0].control.ledger_role == role
    assert observed[0].role_provenance.assigned_role == role
    assert observed[0].role_provenance.execution_role == execution_role


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
        assert "independent" in text and "nonauthorizing" in text, relative
        assert "Grok" in text and "unavailable" in text, relative
        assert "Kimi/Grok are unavailable" not in text, relative

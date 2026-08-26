from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
import inspect

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("slice_b_fix_controls", ROOT / "scripts/provider_prompt.py")
assert SPEC and SPEC.loader
OWNER = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = OWNER
SPEC.loader.exec_module(OWNER)


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
        ("grok", "E_GROK_CONTAINMENT_UNAVAILABLE"),
    ),
)
def test_admitted_unavailable_route_stops_before_prompt_resolution_capture_probe_or_popen(
    provider: str, stable_id: str, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def forbidden(name: str):
        return lambda *_args, **_kwargs: pytest.fail(f"{name} reached")

    monkeypatch.setattr(OWNER, "prompt_bytes", forbidden("prompt_bytes"))
    monkeypatch.setattr(OWNER, "parse_control", forbidden("parse_control"))
    monkeypatch.setattr(OWNER, "resolve_provider_command", forbidden("resolution"))
    monkeypatch.setattr(OWNER.RunCaptureLifecycle, "create", forbidden("capture"))
    monkeypatch.setattr(OWNER.subprocess, "Popen", forbidden("Popen"))
    monkeypatch.setattr(OWNER.shutil, "which", forbidden("probe"))

    assert OWNER.launch(
        provider, ["admitted-route", "--task-class", "exploration", "--role", "analyst"]
    ) == 1
    assert stable_id in capsys.readouterr().err


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
